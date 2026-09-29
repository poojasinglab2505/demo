# leadgen

Finds business leads (sourced from LinkedIn-derived data via Apollo.io's
API — not scraped directly, which would violate LinkedIn's Terms of
Service) and sends them personalized cold emails via SendGrid.

## Why not scrape LinkedIn directly?

Automated scraping of LinkedIn breaches its User Agreement, risks account
bans and legal action (see *hiQ v. LinkedIn* and LinkedIn's own enforcement
history), and provides no reliable delivery infrastructure. This tool
instead uses [Apollo.io](https://apollo.io), a data provider that licenses
LinkedIn-derived contact data through a proper API.

## Setup

```bash
cd leadgen
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

You'll need:
- An [Apollo.io](https://apollo.io) API key (free tier available) for lead search.
- A [SendGrid](https://sendgrid.com) API key and a verified sender for sending mail.

## Usage

### Web dashboard

```bash
python -m leadgen.cli serve
# then open http://127.0.0.1:5000
```

The dashboard lets you: search for leads, preview a campaign (dry run) or send
it for real, see every lead's status, and unsubscribe anyone with one click.

Running it locally with no `DASHBOARD_PASSWORD` set is fine (open access).
**If you deploy it publicly, set `DASHBOARD_PASSWORD`** (see below) — otherwise
anyone with the URL can burn your Apollo/SendGrid credits or send email as you.

### Deploying it publicly (e.g. on Render)

This is a normal Flask app, so any host that runs Python works (Render,
Railway, Fly.io, a VPS, etc). Steps for [Render](https://render.com), free tier:

1. Push this repo to GitHub (already done if you're reading this from the repo).
2. In Render: **New → Web Service**, connect the repo.
3. Set **Root Directory** to `leadgen`.
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `gunicorn leadgen.wsgi:app`
6. Under **Environment**, add the variables from `.env.example`
   (`APOLLO_API_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL`, `FROM_NAME`,
   `COMPANY_POSTAL_ADDRESS`, and — important for a public URL —
   `DASHBOARD_PASSWORD` and `FLASK_SECRET_KEY`, both set to random strings).
7. Deploy. Render gives you a public `https://<your-app>.onrender.com` URL —
   log in with `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.

**Note on the database:** `leads.db` is a local SQLite file. On most free
hosting tiers the filesystem is wiped on every redeploy/restart, so your
lead list and send history won't persist. That's fine for trying it out; for
real use, either enable Render's persistent disk add-on, or swap `storage.py`
for a hosted Postgres database once you outgrow SQLite.

### CLI

```bash
# 1. Find leads and store them locally (deduped) in leads.db
python -m leadgen.cli find --title "Head of Sales" --location "United States" --max-results 25

# 2. Preview the emails before sending anything
python -m leadgen.cli send --pitch "We help sales teams cut outreach time in half." --dry-run

# 3. Actually send (rate-limited by DAILY_SEND_LIMIT / SEND_DELAY_SECONDS in .env)
python -m leadgen.cli send --pitch "We help sales teams cut outreach time in half."

# Honor an opt-out request immediately
python -m leadgen.cli unsubscribe someone@example.com
```

## Compliance checklist (CAN-SPAM / GDPR)

This tool builds in the basics, but **you are responsible for compliance**:

- Every email includes your real postal address (`COMPANY_POSTAL_ADDRESS` in `.env`) and an opt-out instruction.
- `leads.db` tracks who's been emailed and who's unsubscribed so you never re-contact them.
- Keep subject lines and content truthful and non-deceptive; identify the message as an ad if required in your jurisdiction.
- If you operate in the EU/UK, confirm you have a lawful basis (e.g. legitimate interest for B2B outreach) under GDPR/PECR before sending.
- Respect `DAILY_SEND_LIMIT` and `SEND_DELAY_SECONDS` — don't blast large volumes; that hurts deliverability and crosses into spam territory.
- Process unsubscribe/"not interested" replies promptly — this project only automates the send; you still need a process to catch replies (e.g. SendGrid inbound parse or manual review) and call `unsubscribe`.

## Project layout

```
leadgen/
  apollo_client.py   # lead sourcing (Apollo.io People Search API)
  emailer.py          # sending (SendGrid API)
  email_gen.py        # renders personalized email from a Jinja2 template
  templates/           # editable cold email template
  storage.py           # SQLite: dedupe, sent/unsubscribe tracking
  cli.py               # `find`, `send`, `unsubscribe`, `serve` commands
  web/                 # Flask dashboard (app.py, templates/, static/)
```
