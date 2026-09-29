from __future__ import annotations

import csv
from io import StringIO

from .models import Lead

FIELD_ALIASES = {
    "email": ["email", "email address"],
    "first_name": ["first_name", "first name", "firstname"],
    "last_name": ["last_name", "last name", "lastname"],
    "title": ["title", "job title", "job_title"],
    "company": ["company", "company name", "organization"],
    "linkedin_url": ["linkedin_url", "linkedin", "linkedin url"],
    "industry": ["industry"],
}


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    mapping = {}
    for field, aliases in FIELD_ALIASES.items():
        for name in fieldnames or []:
            if name and name.strip().lower() in aliases:
                mapping[field] = name
                break
    return mapping


def parse_leads_csv(text: str) -> list[Lead]:
    """Parses a CSV with an 'email' column plus any of: first_name, last_name,
    title, company, linkedin_url, industry (header names are matched loosely,
    e.g. "First Name" or "Email Address" both work)."""
    reader = csv.DictReader(StringIO(text))
    mapping = _map_headers(reader.fieldnames)
    if "email" not in mapping:
        raise ValueError("CSV must have an 'email' (or 'Email Address') column")

    leads = []
    for row in reader:
        email = (row.get(mapping["email"]) or "").strip()
        if not email:
            continue
        leads.append(
            Lead(
                first_name=(row.get(mapping.get("first_name", "")) or "").strip(),
                last_name=(row.get(mapping.get("last_name", "")) or "").strip(),
                title=(row.get(mapping.get("title", "")) or "").strip(),
                company=(row.get(mapping.get("company", "")) or "").strip(),
                email=email,
                linkedin_url=(row.get(mapping.get("linkedin_url", "")) or "").strip(),
                industry=(row.get(mapping.get("industry", "")) or "").strip(),
            )
        )
    return leads
