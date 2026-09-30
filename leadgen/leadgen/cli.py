import time

import click

from .apollo_client import ApolloClient
from .config import Settings
from .csv_import import parse_leads_csv
from .email_gen import render_email
from .emailer import SendGridClient
from .hunter_client import HunterClient
from .icebreaker import generate_icebreaker
from .icp import ICPConfig
from .signals import check_funding_mentions
from .storage import (
    add_signal_note,
    already_sent,
    connect,
    is_unsubscribed,
    leads_to_email,
    mark_sent,
    mark_unsubscribed,
    recompute_icp_scores,
    upsert_lead,
)


def _icp_from_settings(settings: Settings) -> ICPConfig:
    return ICPConfig.from_csv(settings.icp_title_keywords, settings.icp_industry_keywords)


@click.group()
def cli():
    """Find business leads and send them personalized cold emails."""


@cli.command()
@click.option("--title", "titles", multiple=True, required=True, help="Job title to target, e.g. 'Head of Sales'. Repeatable.")
@click.option("--industry", "industries", multiple=True, help="Industry tag id to target. Repeatable.")
@click.option("--location", "locations", multiple=True, help="Location to target, e.g. 'United States'. Repeatable.")
@click.option("--max-results", default=25, show_default=True)
def find(titles, industries, locations, max_results):
    """Find leads via Apollo.io and store them locally.

    Note: Apollo's People Search API requires a paid Apollo plan (their
    free tier blocks this endpoint entirely). If you're on the free tier,
    use `import-csv` instead.
    """
    settings = Settings.load()
    client = ApolloClient(settings.apollo_api_key)
    leads = client.search_leads(
        job_titles=list(titles),
        industries=list(industries),
        locations=list(locations),
        max_results=max_results,
    )
    added = 0
    with connect() as conn:
        for lead in leads:
            if not lead.email:
                continue
            if upsert_lead(conn, lead):
                added += 1
        recompute_icp_scores(conn, _icp_from_settings(settings))
    click.echo(f"Found {len(leads)} leads, added {added} new ones to leads.db")


@cli.command(name="hunter-find")
@click.option("--domain", required=True, help="Company domain to search, e.g. stripe.com")
@click.option("--company-name", default="", help="Company display name (optional, defaults to domain/organization).")
@click.option("--max-results", default=25, show_default=True)
def hunter_find(domain, company_name, max_results):
    """Find leads at a company via Hunter.io's Domain Search.

    Hunter's free plan includes API access (~25 searches/month), unlike
    Apollo's free plan which blocks API access entirely.
    """
    settings = Settings.load()
    client = HunterClient(settings.hunter_api_key)
    leads = client.search_by_domain(domain, company_name, max_results)
    added = 0
    with connect() as conn:
        for lead in leads:
            if upsert_lead(conn, lead):
                added += 1
        recompute_icp_scores(conn, _icp_from_settings(settings))
    click.echo(f"Found {len(leads)} leads at {domain}, added {added} new ones to leads.db")


@cli.command(name="import-csv")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def import_csv_cmd(csv_path):
    """Import leads from a CSV file (no paid API needed).

    The CSV needs an 'email' column, plus any of: first_name, last_name,
    title, company, linkedin_url, industry. Header names are matched
    loosely (e.g. "Email Address" or "First Name" both work).
    """
    settings = Settings.load()
    with open(csv_path, encoding="utf-8-sig") as f:
        leads = parse_leads_csv(f.read())

    added = 0
    with connect() as conn:
        for lead in leads:
            if upsert_lead(conn, lead):
                added += 1
        recompute_icp_scores(conn, _icp_from_settings(settings))
    click.echo(f"Parsed {len(leads)} rows, added {added} new leads to leads.db")


@cli.command()
def rescore():
    """Recompute ICP fit scores for all leads (see ICP_TITLE_KEYWORDS / ICP_INDUSTRY_KEYWORDS in .env)."""
    settings = Settings.load()
    with connect() as conn:
        count = recompute_icp_scores(conn, _icp_from_settings(settings))
    click.echo(f"Recomputed ICP scores for {count} leads.")


@cli.command(name="add-signal")
@click.argument("email")
@click.argument("note")
def add_signal_cmd(email, note):
    """Attach a free-text buying-signal note to a lead (e.g. "Raised Series A")."""
    with connect() as conn:
        add_signal_note(conn, email, note)
    click.echo(f"Added signal note to {email}.")


@cli.command(name="check-funding-signal")
@click.argument("email")
def check_funding_signal_cmd(email):
    """Best-effort, free check for recent funding-related HN mentions of a lead's company.

    Not comparable to a paid intent-data platform — just a zero-cost signal
    source. See leadgen/signals.py for the caveats.
    """
    with connect() as conn:
        row = conn.execute("SELECT company FROM leads WHERE email = ?", (email,)).fetchone()
        if not row:
            click.echo(f"No lead found for {email}.")
            return
        hits = check_funding_mentions(row["company"])
        if not hits:
            click.echo(f"No funding mentions found for {row['company']}.")
            return
        for hit in hits:
            add_signal_note(conn, email, f"Funding mention: {hit}")
        click.echo(f"Found {len(hits)} mention(s), added as signal notes.")


@cli.command()
@click.option("--pitch", required=True, help="One or two sentences describing your offer.")
@click.option("--limit", default=50, show_default=True, help="Max number of emails to send this run.")
@click.option("--dry-run", is_flag=True, help="Print emails instead of sending them.")
@click.option(
    "--use-ai-icebreaker",
    is_flag=True,
    help="Generate a unique opening sentence per lead via the Claude API (needs ANTHROPIC_API_KEY, costs apply).",
)
def send(pitch, limit, dry_run, use_ai_icebreaker):
    """Draft and send cold emails to leads that haven't been emailed yet."""
    settings = Settings.load()
    limit = min(limit, settings.daily_send_limit)
    sender = None if dry_run else SendGridClient(
        settings.sendgrid_api_key, settings.from_email, settings.from_name
    )

    with connect() as conn:
        rows = leads_to_email(conn, limit)
        if not rows:
            click.echo("No leads to email.")
            return

        for row in rows:
            if is_unsubscribed(conn, row["email"]) or already_sent(conn, row["email"]):
                continue

            icebreaker = ""
            if use_ai_icebreaker:
                icebreaker = generate_icebreaker(
                    settings.anthropic_api_key,
                    row["first_name"],
                    row["title"],
                    row["company"],
                    row["industry"],
                    settings.icebreaker_model,
                )

            subject, body = render_email(
                row, pitch, settings.from_name, settings.company_postal_address, icebreaker
            )

            if dry_run:
                click.echo(f"--- To: {row['email']} ---\nSubject: {subject}\n\n{body}\n")
                continue

            sender.send(row["email"], subject, body)
            mark_sent(conn, row["email"])
            click.echo(f"Sent to {row['email']}")
            time.sleep(settings.send_delay_seconds)


@cli.command()
@click.argument("email")
def unsubscribe(email):
    """Mark an email address as unsubscribed so it's never emailed again."""
    with connect() as conn:
        mark_unsubscribed(conn, email)
    click.echo(f"{email} marked as unsubscribed.")


@cli.command()
@click.option("--port", default=5000, show_default=True)
@click.option("--debug", is_flag=True)
def serve(port, debug):
    """Run the web dashboard for finding leads and sending campaigns."""
    from .web.app import create_app

    create_app().run(port=port, debug=debug)


if __name__ == "__main__":
    cli()
