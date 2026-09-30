# leadgen

Manages business leads and sends them personalized cold emails via SendGrid.
Leads can come from three sources: a **CSV you build yourself** (fully free),
**Hunter.io's Domain Search** (free plan includes API access), or, if you have
a paid Apollo.io plan, Apollo's People Search API. On top of that, leads get
an automatic **ICP fit score**, you can attach free-text **buying-signal
notes** (or run a best-effort free funding-news check), and outreach can use
an **AI-personalized icebreaker** per lead instead of one fixed template line.

This is a lighter-weight, self-hosted alternative to tools like Gojiberry AI —
it covers ICP scoring, signal notes, and AI-personalized outreach, but
deliberately does **not** automate LinkedIn connection requests/DMs the way
those tools do (see below).

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

## Why not automate LinkedIn outreach (connection requests, DMs)?

Tools like Gojiberry AI also send LinkedIn connection requests and follow-up
DMs automatically. That requires automating actions on your LinkedIn account
(via their own session or a browser tool), which breaches LinkedIn's User
Agreement the same way scraping does, and risks account restriction or ban.
This project intentionally stops at **email** outreach, which has a normal,
ToS-compliant API path (SendGrid) — if you want LinkedIn messaging too, that
has to be a manual, human-in-the-loop step outside this tool.

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
- Optionally, an [Anthropic](https://console.anthropic.com) API key for AI-personalized icebreakers (small per-lead cost — see below).

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

# Recompute ICP fit scores for all leads (e.g. after changing ICP keywords in .env)
python -m leadgen.cli rescore

# Attach a free-text buying-signal note to a lead
python -m leadgen.cli add-signal jane@example.com "Raised Series A"

# Best-effort free check for funding-news mentions of a lead's company
python -m leadgen.cli check-funding-signal jane@example.com

# Send with an AI-personalized icebreaker per lead (needs ANTHROPIC_API_KEY)
python -m leadgen.cli send --pitch "We help sales teams cut outreach time in half." --use-ai-icebreaker --dry-run
```

## ICP scoring, signals, and AI icebreakers

**ICP fit scoring** (free, rule-based, automatic): every lead gets a 0-100
score based on keyword overlap with `ICP_TITLE_KEYWORDS` / `ICP_INDUSTRY_KEYWORDS`
in `.env`, plus small bonuses for having a company/LinkedIn URL on file.
Scores are computed automatically on every import; after changing your ICP
keywords, click **Rescore all leads** in the dashboard (or run
`python -m leadgen.cli rescore`) to recompute them. Sort the lead table by
fit with the "Sort by ICP fit" link.

**Signal notes** (free): attach a free-text note to any lead — e.g. "Raised
Series A", "New VP of Sales" — via the dashboard's per-lead note field or
`python -m leadgen.cli add-signal <email> "<note>"`. There's also a
best-effort **"Check funding news"** button / `check-funding-signal <email>`
CLI command that searches Hacker News' free public search API for stories
mentioning the lead's company alongside "funding" and logs any hits as
signal notes. This is *not* comparable to a paid intent-data platform (Apollo
intent add-ons, Clearbit, Crunchbase) — it's a zero-cost, best-effort
starting point, and coverage is sparse.

**AI-personalized icebreakers** (small cost per lead): instead of one fixed
opening line for every recipient, check "AI-personalized icebreaker" when
sending a campaign (or pass `--use-ai-icebreaker` to `leadgen send`) to have
Claude write a unique, relevant opening sentence per lead from their title/
company/industry. Requires `ANTHROPIC_API_KEY`. Uses `claude-sonnet-5-5` by
default (`ICEBREAKER_MODEL` in `.env` to change it) — a short sentence per
lead costs a small fraction of a cent, but it does add up across a large
list, so it's opt-in rather than automatic.

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
  icp.py                # free, rule-based ICP fit scoring
  signals.py            # free, best-effort funding-news lookup (HN search API)
  icebreaker.py         # AI-personalized icebreaker generation (Claude API)
  emailer.py            # sending (SendGrid API)
  email_gen.py          # renders personalized email from a Jinja2 template
  templates/             # editable cold email template
  storage.py             # SQLite: dedupe, sent/unsubscribe tracking, ICP scores, signal notes
  cli.py                 # `import-csv`, `hunter-find`, `find`, `send`, `rescore`, `add-signal`,
                         # `check-funding-signal`, `unsubscribe`, `serve` commands
  web/                   # Flask dashboard (app.py, templates/, static/)
leads_template.csv     # example CSV for import-csv / the dashboard's Import panel
```
