import os
import secrets
import time

from flask import Flask, Response, flash, redirect, render_template, request, url_for

from ..apollo_client import ApolloClient
from ..config import Settings
from ..csv_import import parse_leads_csv
from ..email_gen import render_email
from ..emailer import SendGridClient
from ..storage import (
    already_sent,
    connect,
    is_unsubscribed,
    list_leads,
    mark_sent,
    mark_unsubscribed,
    status_counts,
    upsert_lead,
)


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
        with connect() as conn:
            leads = list_leads(conn)
            counts = status_counts(conn)
        return render_template("index.html", leads=leads, counts=counts)

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

        added = 0
        with connect() as conn:
            for lead in leads:
                if upsert_lead(conn, lead):
                    added += 1

        flash(f"Imported {len(leads)} rows, added {added} new leads.", "success")
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

        flash(f"Found {len(leads)} leads, added {added} new ones.", "success")
        return redirect(url_for("index"))

    @app.route("/send", methods=["POST"])
    def send_campaign():
        settings = Settings.load()
        pitch = request.form.get("pitch", "").strip()
        limit = min(int(request.form.get("limit") or 50), settings.daily_send_limit)
        dry_run = request.form.get("dry_run") == "on"

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
                subject, body = render_email(row, pitch, settings.from_name, settings.company_postal_address)
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
