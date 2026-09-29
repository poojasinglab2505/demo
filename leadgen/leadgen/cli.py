import time

import click

from .apollo_client import ApolloClient
from .config import Settings
from .csv_import import parse_leads_csv
from .email_gen import render_email
from .emailer import SendGridClient
from .storage import (
    already_sent,
    connect,
    is_unsubscribed,
    leads_to_email,
    mark_sent,
    mark_unsubscribed,
    upsert_lead,
)


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
    click.echo(f"Found {len(leads)} leads, added {added} new ones to leads.db")


@cli.command(name="import-csv")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def import_csv_cmd(csv_path):
    """Import leads from a CSV file (no paid API needed).

    The CSV needs an 'email' column, plus any of: first_name, last_name,
    title, company, linkedin_url, industry. Header names are matched
    loosely (e.g. "Email Address" or "First Name" both work).
    """
    with open(csv_path, encoding="utf-8-sig") as f:
        leads = parse_leads_csv(f.read())

    added = 0
    with connect() as conn:
        for lead in leads:
            if upsert_lead(conn, lead):
                added += 1
    click.echo(f"Parsed {len(leads)} rows, added {added} new leads to leads.db")


@cli.command()
@click.option("--pitch", required=True, help="One or two sentences describing your offer.")
@click.option("--limit", default=50, show_default=True, help="Max number of emails to send this run.")
@click.option("--dry-run", is_flag=True, help="Print emails instead of sending them.")
def send(pitch, limit, dry_run):
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

            subject, body = render_email(
                row, pitch, settings.from_name, settings.company_postal_address
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
