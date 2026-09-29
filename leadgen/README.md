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
It's a local tool with no authentication — don't expose it on the open internet.

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
