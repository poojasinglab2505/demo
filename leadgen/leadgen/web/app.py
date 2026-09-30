import os
import secrets
import time

from flask import Flask, Response, flash, redirect, render_template, request, url_for

from ..apollo_client import ApolloClient
from ..config import Settings
from ..csv_import import parse_leads_csv
from ..email_gen import render_email
from ..emailer import SendGridClient
from ..hunter_client import HunterClient
from ..icebreaker import generate_icebreaker
from ..icp import ICPConfig
from ..signals import check_funding_mentions
from ..storage import (
    add_signal_note,
    already_sent,
    connect,
    is_unsubscribed,
    list_leads,
    mark_sent,
    mark_unsubscribed,
    recompute_icp_scores,
    status_counts,
    upsert_lead,
)


def _icp_from_settings(settings: Settings) -> ICPConfig:
    return ICPConfig.from_csv(settings.icp_title_keywords, settings.icp_industry_keywords)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)

    dashboard_user = os.environ.get("DASHBOARD_USERNAME", "admin")
    dashboard_password = os.environ.get("DASHBOARD_PASSWORD", "")

    @app.before_request
    def require_auth():
        if not dashboard_password:
            return  # no password configured (local/dev use) — leave open
        auth = request.authorization
        if not auth or auth.username != dashboard_user or auth.password != dashboard_password:
            return Response(
                "Login required", 401, {"WWW-Authenticate": 'Basic realm="Leadgen"'}
            )

    @app.route("/")
    def index():
        sort_by_score = request.args.get("sort") == "score"
        with connect() as conn:
            leads = list_leads(conn, sort_by_score=sort_by_score)
            counts = status_counts(conn)
        return render_template("index.html", leads=leads, counts=counts, sort_by_score=sort_by_score)

    @app.route("/import", methods=["POST"])
    def import_csv():
        file = request.files.get("csv_file")
        if not file or not file.filename:
            flash("Choose a CSV file to import.", "error")
            return redirect(url_for("index"))

        try:
            text = file.stream.read().decode("utf-8-sig")
            leads = parse_leads_csv(text)
        except Exception as exc:
            flash(f"CSV import failed: {exc}", "error")
            return redirect(url_for("index"))

        settings = Settings.load()
        added = 0
        with connect() as conn:
            for lead in leads:
                if upsert_lead(conn, lead):
                    added += 1
            recompute_icp_scores(conn, _icp_from_settings(settings))

        flash(f"Imported {len(leads)} rows, added {added} new leads.", "success")
        return redirect(url_for("index"))

    @app.route("/hunter-find", methods=["POST"])
    def hunter_find():
        settings = Settings.load()
        domain = request.form.get("domain", "").strip()
        company_name = request.form.get("company_name", "").strip()
        max_results = int(request.form.get("hunter_max_results") or 25)

        if not domain:
            flash("Enter a company domain to search.", "error")
            return redirect(url_for("index"))

        try:
            client = HunterClient(settings.hunter_api_key)
            leads = client.search_by_domain(domain, company_name, max_results)
        except Exception as exc:
            flash(f"Hunter search failed: {exc}", "error")
            return redirect(url_for("index"))

        added = 0
        with connect() as conn:
            for lead in leads:
                if upsert_lead(conn, lead):
                    added += 1
            recompute_icp_scores(conn, _icp_from_settings(settings))

        flash(f"Found {len(leads)} leads at {domain}, added {added} new ones.", "success")
        return redirect(url_for("index"))

    @app.route("/find", methods=["POST"])
    def find():
        settings = Settings.load()
        titles = [t.strip() for t in request.form.get("titles", "").split(",") if t.strip()]
        locations = [l.strip() for l in request.form.get("locations", "").split(",") if l.strip()]
        max_results = int(request.form.get("max_results") or 25)

        if not titles:
            flash("Enter at least one job title to search for.", "error")
            return redirect(url_for("index"))

        try:
            client = ApolloClient(settings.apollo_api_key)
            leads = client.search_leads(job_titles=titles, locations=locations, max_results=max_results)
        except Exception as exc:  # surfaced to the user rather than a 500 page
            flash(f"Lead search failed: {exc}", "error")
            return redirect(url_for("index"))

        added = 0
        with connect() as conn:
            for lead in leads:
                if lead.email and upsert_lead(conn, lead):
                    added += 1
            recompute_icp_scores(conn, _icp_from_settings(settings))

        flash(f"Found {len(leads)} leads, added {added} new ones.", "success")
        return redirect(url_for("index"))

    @app.route("/rescore", methods=["POST"])
    def rescore():
        settings = Settings.load()
        with connect() as conn:
            count = recompute_icp_scores(conn, _icp_from_settings(settings))
        flash(f"Recomputed ICP scores for {count} leads.", "success")
        return redirect(url_for("index"))

    @app.route("/signal/<email>", methods=["POST"])
    def add_signal(email):
        note = request.form.get("note", "").strip()
        if not note:
            flash("Enter a signal note to add.", "error")
            return redirect(url_for("index"))
        with connect() as conn:
            add_signal_note(conn, email, note)
        flash(f"Added signal note to {email}.", "success")
        return redirect(url_for("index"))

    @app.route("/check-signal/<email>", methods=["POST"])
    def check_signal(email):
        with connect() as conn:
            row = conn.execute("SELECT company FROM leads WHERE email = ?", (email,)).fetchone()
            if not row:
                flash(f"No lead found for {email}.", "error")
                return redirect(url_for("index"))
            hits = check_funding_mentions(row["company"])
            for hit in hits:
                add_signal_note(conn, email, f"Funding mention: {hit}")
        if hits:
            flash(f"Found {len(hits)} mention(s) for {row['company']}, added as signal notes.", "success")
        else:
            flash(f"No funding mentions found for {row['company']}.", "success")
        return redirect(url_for("index"))

    @app.route("/send", methods=["POST"])
    def send_campaign():
        settings = Settings.load()
        pitch = request.form.get("pitch", "").strip()
        limit = min(int(request.form.get("limit") or 50), settings.daily_send_limit)
        dry_run = request.form.get("dry_run") == "on"
        use_ai_icebreaker = request.form.get("use_ai_icebreaker") == "on"

        if not pitch:
            flash("Write a pitch before sending a campaign.", "error")
            return redirect(url_for("index"))

        sender = None
        if not dry_run:
            try:
                sender = SendGridClient(settings.sendgrid_api_key, settings.from_email, settings.from_name)
            except Exception as exc:
                flash(f"Could not start sender: {exc}", "error")
                return redirect(url_for("index"))

        previews = []
        sent_count = 0
        with connect() as conn:
            from ..storage import leads_to_email

            for row in leads_to_email(conn, limit):
                if is_unsubscribed(conn, row["email"]) or already_sent(conn, row["email"]):
                    continue

                icebreaker = ""
                if use_ai_icebreaker:
                    try:
                        icebreaker = generate_icebreaker(
                            settings.anthropic_api_key,
                            row["first_name"],
                            row["title"],
                            row["company"],
                            row["industry"],
                            settings.icebreaker_model,
                        )
                    except Exception as exc:
                        flash(f"AI icebreaker failed for {row['email']}: {exc}", "error")

                subject, body = render_email(
                    row, pitch, settings.from_name, settings.company_postal_address, icebreaker
                )
                if dry_run:
                    previews.append({"email": row["email"], "subject": subject, "body": body})
                    continue
                sender.send(row["email"], subject, body)
                mark_sent(conn, row["email"])
                sent_count += 1
                time.sleep(settings.send_delay_seconds)

        if dry_run:
            with connect() as conn:
                leads = list_leads(conn)
                counts = status_counts(conn)
            return render_template("index.html", leads=leads, counts=counts, previews=previews)

        flash(f"Sent {sent_count} emails.", "success")
        return redirect(url_for("index"))

    @app.route("/unsubscribe/<email>", methods=["POST"])
    def unsubscribe(email):
        with connect() as conn:
            mark_unsubscribed(conn, email)
        flash(f"{email} unsubscribed.", "success")
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
