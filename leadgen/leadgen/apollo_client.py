"""Client for Apollo.io's People Search API — a legitimate, ToS-compliant
source of LinkedIn-derived business contact data (no LinkedIn scraping)."""
from __future__ import annotations

import requests

from .models import Lead

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"


class ApolloClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("APOLLO_API_KEY is not set")
        self.api_key = api_key

    def search_leads(
        self,
        job_titles: list[str],
        industries: list[str] | None = None,
        locations: list[str] | None = None,
        company_sizes: list[str] | None = None,
        max_results: int = 25,
    ) -> list[Lead]:
        payload = {
            "api_key": self.api_key,
            "person_titles": job_titles,
            "organization_industry_tag_ids": industries or [],
            "person_locations": locations or [],
            "organization_num_employees_ranges": company_sizes or [],
            "page": 1,
            "per_page": min(max_results, 100),
        }
        response = requests.post(APOLLO_SEARCH_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        records = data.get("people", [])[:max_results]
        return [Lead.from_apollo_record(r) for r in records]
