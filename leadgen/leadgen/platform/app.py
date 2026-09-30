import os
import time

from flask import Flask, flash, g, redirect, render_template, request, url_for

from ..email_gen import render_email
from ..emailer import SendGridClient
from . import crypto
from .agent_runner import run_agent_for_company
from .auth import authenticate, current_user, login_required, login_user, logout_user, register_company
from .db import SessionLocal, init_db
from .models import AgentConfig, Lead
from .scheduler import start_scheduler


def create_platform_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("APP_SECRET_KEY", "")
    if not app.secret_key:
        raise RuntimeError("APP_SECRET_KEY must be set (used for sessions and encrypting stored API keys)")

    init_db()
    if os.environ.get("ENABLE_SCHEDULER", "true").lower() != "false":
        start_scheduler()

    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            company_name = request.form.get("company_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not company_name or not email or len(password) < 8:
                flash("Fill in a company name, email, and a password of at least 8 characters.", "error")
                return redirect(url_for("register"))
            try:
                user = register_company(company_name, email, password)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("register"))
            login_user(user)
            flash(f"Welcome, {company_name}! Configure your agent to get started.", "success")
            return redirect(url_for("agent_config_view"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = authenticate(email, password)
            if not user:
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))
            login_user(user)
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        with SessionLocal() as db:
            leads = (
                db.query(Lead)
                .filter_by(company_id=g.company_id)
                .order_by(Lead.icp_score.desc(), Lead.id.desc())
                .all()
            )
            config = db.query(AgentConfig).filter_by(company_id=g.company_id).first()
        return render_template("dashboard.html", leads=leads, config=config)

    @app.route("/agent/config", methods=["GET", "POST"])
    @login_required
    def agent_config_view():
        with SessionLocal() as db:
            config = db.query(AgentConfig).filter_by(company_id=g.company_id).first()
            if not config:
                config = AgentConfig(company_id=g.company_id)
                db.add(config)
                db.commit()
                db.refresh(config)

            if request.method == "POST":
                config.title_keywords = request.form.get("title_keywords", "").strip()
                config.industry_keywords = request.form.get("industry_keywords", "").strip()
                config.target_domains = request.form.get("target_domains", "").strip()
                config.company_size_min = int(request.form.get("company_size_min") or 0)
                config.company_size_max = int(request.form.get("company_size_max") or 0)
                config.revenue_min = int(request.form.get("revenue_min") or 0)
                config.revenue_max = int(request.form.get("revenue_max") or 0)
                config.enable_funding_signal_check = request.form.get("enable_funding_signal_check") == "on"
                config.run_frequency_hours = int(request.form.get("run_frequency_hours") or 24)
                config.from_email = request.form.get("from_email", "").strip()
                config.from_name = request.form.get("from_name", "").strip()
                config.company_postal_address = request.form.get("company_postal_address", "").strip()

                for field, enc_field in [
                    ("hunter_api_key", "hunter_api_key_enc"),
                    ("apollo_api_key", "apollo_api_key_enc"),
                    ("sendgrid_api_key", "sendgrid_api_key_enc"),
                    ("anthropic_api_key", "anthropic_api_key_enc"),
                ]:
                    new_value = request.form.get(field, "").strip()
                    if new_value:  # blank means "leave unchanged" so we don't wipe secrets on every save
                        setattr(config, enc_field, crypto.encrypt(new_value))

                db.commit()
                flash("Agent configuration saved.", "success")
                return redirect(url_for("agent_config_view"))

            return render_template("agent_config.html", config=config)

    @app.route("/agent/run-now", methods=["POST"])
    @login_required
    def run_now():
        summary = run_agent_for_company(g.company_id)
        flash(summary, "success")
        return redirect(url_for("dashboard"))

    @app.route("/send", methods=["POST"])
    @login_required
    def send_campaign():
        pitch = request.form.get("pitch", "").strip()
        dry_run = request.form.get("dry_run") == "on"
        if not pitch:
            flash("Write a pitch before sending a campaign.", "error")
            return redirect(url_for("dashboard"))

        with SessionLocal() as db:
            config = db.query(AgentConfig).filter_by(company_id=g.company_id).first()
            sendgrid_key = crypto.decrypt(config.sendgrid_api_key_enc) if config else ""
            if not dry_run and not sendgrid_key:
                flash("Add a SendGrid API key in Agent Config before sending for real.", "error")
                return redirect(url_for("dashboard"))

            sender = None if dry_run else SendGridClient(sendgrid_key, config.from_email, config.from_name)
            leads = (
                db.query(Lead)
                .filter_by(company_id=g.company_id)
                .filter(Lead.status.notin_(["sent", "unsubscribed", "bounced"]))
                .all()
            )

            sent_count = 0
            for lead in leads:
                row = {
                    "first_name": lead.first_name,
                    "title": lead.title,
                    "company": lead.lead_company,
                }
                subject, body = render_email(row, pitch, config.from_name, config.company_postal_address)
                if dry_run:
                    continue
                sender.send(lead.email, subject, body)
                lead.status = "sent"
                sent_count += 1
                time.sleep(1)

            db.commit()

        if dry_run:
            flash(f"Dry run: would send to {len(leads)} lead(s).", "success")
        else:
            flash(f"Sent {sent_count} emails.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/unsubscribe/<int:lead_id>", methods=["POST"])
    @login_required
    def unsubscribe(lead_id):
        with SessionLocal() as db:
            lead = db.query(Lead).filter_by(id=lead_id, company_id=g.company_id).first()
            if lead:
                lead.status = "unsubscribed"
                db.commit()
        return redirect(url_for("dashboard"))

    return app


if __name__ == "__main__":
    create_platform_app().run(debug=True, port=5050)
