"""Best-effort, free buying-signal lookup via Hacker News' public search API
(no key required). This is NOT comparable to a paid intent-data platform —
it only surfaces HN stories that mention the company alongside "funding",
which is sparse coverage at best. It exists as a zero-cost starting point;
for real signal coverage (job changes, new hires, competitor engagement),
you'd need a paid provider (Apollo intent data, Clearbit, Crunchbase, etc).
"""
from __future__ import annotations

import requests

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def check_funding_mentions(company_name: str, max_results: int = 3) -> list[str]:
    if not company_name:
        return []

    params = {"query": f"{company_name} funding", "tags": "story", "hitsPerPage": max_results}
    try:
        response = requests.get(HN_SEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException:
        return []

    hits = response.json().get("hits", [])
    results = []
    for hit in hits:
        title = hit.get("title")
        if not title:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        results.append(f"{title} ({url})")
    return results
