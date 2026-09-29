"""Client for Hunter.io's Domain Search API — finds business email
addresses at a given company domain. Free plan includes API access
(around 25 searches/month), unlike Apollo's free plan which blocks
API access entirely."""
from __future__ import annotations

import requests

from .models import Lead

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"


class HunterClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("HUNTER_API_KEY is not set")
        self.api_key = api_key

    def search_by_domain(self, domain: str, company_name: str = "", max_results: int = 25) -> list[Lead]:
        params = {
            "domain": domain.strip(),
            "api_key": self.api_key,
            "limit": min(max_results, 100),
        }
        response = requests.get(HUNTER_DOMAIN_SEARCH_URL, params=params, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Hunter API error {response.status_code}: {response.text}")

        data = response.json().get("data", {})
        company = company_name.strip() or data.get("organization") or domain

        leads = []
        for record in data.get("emails", [])[:max_results]:
            email = record.get("value")
            if not email:
                continue
            leads.append(
                Lead(
                    first_name=record.get("first_name") or "",
                    last_name=record.get("last_name") or "",
                    title=record.get("position") or "",
                    company=company,
                    email=email,
                    linkedin_url=record.get("linkedin") or "",
                    industry="",
                )
            )
        return leads
