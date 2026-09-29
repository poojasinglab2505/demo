# leadgen

Manages business leads and sends them personalized cold emails via SendGrid.
Leads can come from three sources: a **CSV you build yourself** (fully free),
**Hunter.io's Domain Search** (free plan includes API access), or, if you have
a paid Apollo.io plan, Apollo's People Search API.

## Why not scrape LinkedIn directly?

Automated scraping of LinkedIn breaches its User Agreement, risks account
bans and legal action (see *hiQ v. LinkedIn* and LinkedIn's own enforcement
history), and provides no reliable delivery infrastructure. If you want
automated lead search, use a licensed data provider instead:

- **[Hunter.io](https://hunter.io)** — recommended for free use. Its free plan
  includes API access (~25 searches/month) to find email addresses at a given
  company domain.
- **[Apollo.io](https://apollo.io)** — richer search filters (job title,
  location, etc), but **its free plan blocks API access entirely**; the
  People Search API requires a paid plan (roughly $59+/month).

CSV import needs no API or payment at all — you supply the lead list yourself.

## Setup

```bash
cd leadgen
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

You'll need:
- A [SendGrid](https://sendgrid.com) API key and a verified sender for sending mail.
- Optionally, a [Hunter.io](https://hunter.io/api-keys) API key (free plan works) for automated lead search by company domain.
- Optionally, a **paid** [Apollo.io](https://apollo.io) plan and API key, for richer automated lead search.

## Usage

### Web dashboard

```bash
python -m leadgen.cli serve
# then open http://127.0.0.1:5000
```

The dashboard lets you: import leads from a CSV, search via Hunter.io (free
plan works) or Apollo (paid plan required), preview a campaign (dry run) or
send it for real, see every lead's status, and unsubscribe anyone with one
click.

Running it locally with no `DASHBOARD_PASSWORD` set is fine (open access).
**If you deploy it publicly, set `DASHBOARD_PASSWORD`** (see below) — otherwise
anyone with the URL can burn your Apollo/SendGrid credits or send email as you.

### Deploying it publicly

This is a normal Flask app packaged with a `Dockerfile`, so any host that runs
containers works (Railway, Fly.io, Render, a VPS, etc).

#### Railway (recommended)

1. Push this repo to GitHub (already done if you're reading this from the repo).
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → select this repo.
3. Open the new service's **Settings**:
   - **Root Directory**: `leadgen`
   - Railway will detect the `Dockerfile` automatically and use it to build — no build/start command needed.
4. Go to **Variables** and add: `HUNTER_API_KEY` and/or `APOLLO_API_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL`,
   `FROM_NAME`, `COMPANY_POSTAL_ADDRESS`, and — important for a public URL —
   `DASHBOARD_PASSWORD` and `FLASK_SECRET_KEY` (set both to random strings, e.g.
   from `python -c "import secrets; print(secrets.token_hex(16))"`).
5. Under **Settings → Networking**, click **Generate Domain** to get a public
   `https://<your-app>.up.railway.app` URL.
6. Deploy. Log in to the dashboard with `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.

#### Render (alternative)

Render also works, using the included `render.yaml` (New → Blueprint,
pointed at the branch that has this code) or the same Root Directory /
Dockerfile settings as above under a manually created Web Service.

**Note on the database:** `leads.db` is a local SQLite file. On most free
hosting tiers the filesystem is wiped on every redeploy/restart, so your
lead list and send history won't persist. That's fine for trying it out; for
real use, either enable Render's persistent disk add-on, or swap `storage.py`
for a hosted Postgres database once you outgrow SQLite.

### CLI

```bash
# 1a. Import leads from a CSV (see leads_template.csv for the expected format —
#     just needs an 'email' column, plus optional first_name/last_name/title/
#     company/linkedin_url/industry columns)
python -m leadgen.cli import-csv leads_template.csv

# 1b. Or find leads at a company automatically via Hunter.io (free plan works):
python -m leadgen.cli hunter-find --domain stripe.com --max-results 25

# 1c. Or, if you have a paid Apollo.io plan, find leads automatically:
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
  csv_import.py       # lead sourcing from a CSV file (no paid API needed)
  hunter_client.py     # lead sourcing via Hunter.io Domain Search (free plan works)
  apollo_client.py     # lead sourcing via Apollo.io People Search API (paid plan required)
  emailer.py           # sending (SendGrid API)
  email_gen.py         # renders personalized email from a Jinja2 template
  templates/            # editable cold email template
  storage.py            # SQLite: dedupe, sent/unsubscribe tracking
  cli.py                # `import-csv`, `hunter-find`, `find`, `send`, `unsubscribe`, `serve` commands
  web/                  # Flask dashboard (app.py, templates/, static/)
leads_template.csv     # example CSV for import-csv / the dashboard's Import panel
```
