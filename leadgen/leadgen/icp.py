"""Rule-based ICP (Ideal Customer Profile) fit scoring.

Deliberately simple and free: no ML model, no paid data. Scores a lead
0-100 based on keyword overlap with your configured target titles/
industries, plus small bonuses for data completeness.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ICPConfig:
    title_keywords: list[str]
    industry_keywords: list[str]

    @classmethod
    def from_csv(cls, title_keywords_csv: str, industry_keywords_csv: str) -> "ICPConfig":
        return cls(
            title_keywords=[t.strip().lower() for t in title_keywords_csv.split(",") if t.strip()],
            industry_keywords=[i.strip().lower() for i in industry_keywords_csv.split(",") if i.strip()],
        )


def score_lead(title: str, company: str, industry: str, linkedin_url: str, icp: ICPConfig) -> int:
    title = (title or "").lower()
    industry = (industry or "").lower()

    score = 0
    if icp.title_keywords:
        score += 50 if any(k in title for k in icp.title_keywords) else 0
    else:
        score += 25  # no title filter configured — neutral partial credit

    if icp.industry_keywords:
        score += 30 if any(k in industry for k in icp.industry_keywords) else 0
    else:
        score += 15

    if company:
        score += 10
    if linkedin_url:
        score += 10

    return min(score, 100)
