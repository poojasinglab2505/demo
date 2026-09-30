"""Runs one company's configured agent: searches its target domains via
Hunter.io (free) and/or Apollo.io (if a paid key is configured), scores
leads against the company's ICP, and optionally checks for funding-news
signals — writing results into that company's own lead table."""
from __future__ import annotations

from datetime import datetime

from ..hunter_client import HunterClient
from ..apollo_client import ApolloClient
from ..icp import ICPConfig, score_lead
from ..signals import check_funding_mentions
from . import crypto
from .db import SessionLocal
from .models import AgentConfig, Lead


def _upsert_lead(db, company_id: int, sourced_lead, icp: ICPConfig) -> bool:
    """Returns True if a new lead row was inserted."""
    if not sourced_lead.email:
        return False
    existing = (
        db.query(Lead)
        .filter_by(company_id=company_id, email=sourced_lead.email)
        .first()
    )
    score = score_lead(
        sourced_lead.title, sourced_lead.company, sourced_lead.industry, sourced_lead.linkedin_url, icp
    )
    if existing:
        existing.icp_score = score
        return False

    db.add(
        Lead(
            company_id=company_id,
            email=sourced_lead.email,
            first_name=sourced_lead.first_name,
            last_name=sourced_lead.last_name,
            title=sourced_lead.title,
            lead_company=sourced_lead.company,
            linkedin_url=sourced_lead.linkedin_url,
            industry=sourced_lead.industry,
            icp_score=score,
        )
    )
    return True


def run_agent_for_company(company_id: int) -> str:
    """Runs the agent once for one company. Returns a human-readable summary,
    which is also saved to AgentConfig.last_run_summary."""
    with SessionLocal() as db:
        config = db.query(AgentConfig).filter_by(company_id=company_id).first()
        if not config:
            return "No agent configuration found."

        icp = ICPConfig.from_csv(config.title_keywords, config.industry_keywords)
        domains = [d.strip() for d in config.target_domains.split(",") if d.strip()]

        found = 0
        added = 0
        errors = []

        hunter_key = crypto.decrypt(config.hunter_api_key_enc)
        apollo_key = crypto.decrypt(config.apollo_api_key_enc)

        if hunter_key and domains:
            client = HunterClient(hunter_key)
            for domain in domains:
                try:
                    leads = client.search_by_domain(domain, max_results=25)
                except Exception as exc:
                    errors.append(f"Hunter search failed for {domain}: {exc}")
                    continue
                found += len(leads)
                for lead in leads:
                    if _upsert_lead(db, company_id, lead, icp):
                        added += 1

        if apollo_key:
            titles = [t.strip() for t in config.title_keywords.split(",") if t.strip()]
            if titles:
                try:
                    client = ApolloClient(apollo_key)
                    leads = client.search_leads(job_titles=titles, max_results=25)
                    found += len(leads)
                    for lead in leads:
                        if _upsert_lead(db, company_id, lead, icp):
                            added += 1
                except Exception as exc:
                    errors.append(f"Apollo search failed: {exc}")

        if config.enable_funding_signal_check:
            target_companies = {
                lead.lead_company
                for lead in db.query(Lead).filter_by(company_id=company_id).all()
                if lead.lead_company
            }
            for name in target_companies:
                hits = check_funding_mentions(name)
                if hits:
                    lead_rows = db.query(Lead).filter_by(company_id=company_id, lead_company=name).all()
                    for lead in lead_rows:
                        for hit in hits:
                            note = f"\n- Funding mention: {hit}"
                            lead.signal_notes = (lead.signal_notes + note).strip()

        config.last_run_at = datetime.utcnow()
        summary_parts = [f"Found {found} leads, added {added} new."]
        if errors:
            summary_parts.append(f"{len(errors)} error(s): " + "; ".join(errors))
        summary = " ".join(summary_parts)
        config.last_run_summary = summary

        db.commit()
        return summary
