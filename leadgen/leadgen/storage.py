import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "leads.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    email TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    title TEXT,
    company TEXT,
    linkedin_url TEXT,
    industry TEXT,
    status TEXT NOT NULL DEFAULT 'new',   -- new | drafted | sent | bounced | unsubscribed
    sent_at TEXT
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_lead(conn, lead) -> bool:
    """Insert a lead if new. Returns True if it was newly added."""
    cur = conn.execute(
        """INSERT INTO leads (email, first_name, last_name, title, company, linkedin_url, industry)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(email) DO NOTHING""",
        (lead.email, lead.first_name, lead.last_name, lead.title, lead.company, lead.linkedin_url, lead.industry),
    )
    return cur.rowcount > 0


def is_unsubscribed(conn, email: str) -> bool:
    row = conn.execute("SELECT 1 FROM leads WHERE email = ? AND status = 'unsubscribed'", (email,)).fetchone()
    return row is not None


def already_sent(conn, email: str) -> bool:
    row = conn.execute("SELECT 1 FROM leads WHERE email = ? AND status = 'sent'", (email,)).fetchone()
    return row is not None


def mark_sent(conn, email: str):
    conn.execute(
        "UPDATE leads SET status = 'sent', sent_at = datetime('now') WHERE email = ?",
        (email,),
    )


def mark_unsubscribed(conn, email: str):
    conn.execute("UPDATE leads SET status = 'unsubscribed' WHERE email = ?", (email,))


def leads_to_email(conn, limit: int):
    return conn.execute(
        "SELECT * FROM leads WHERE status NOT IN ('sent', 'unsubscribed', 'bounced') LIMIT ?",
        (limit,),
    ).fetchall()


def list_leads(conn):
    return conn.execute("SELECT * FROM leads ORDER BY rowid DESC").fetchall()


def status_counts(conn) -> dict:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM leads GROUP BY status").fetchall()
    counts = {row["status"]: row["n"] for row in rows}
    counts["total"] = sum(counts.values())
    return counts
