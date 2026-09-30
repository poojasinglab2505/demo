"""Generates a personalized one-sentence email opener per lead using the
Claude API, instead of one fixed template line for every recipient."""
from __future__ import annotations

import anthropic

DEFAULT_MODEL = "claude-sonnet-5-5"


def generate_icebreaker(
    api_key: str,
    first_name: str,
    title: str,
    company: str,
    industry: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"Write ONE short, natural opening sentence (max 25 words) for a cold outreach "
        f"email to {first_name or 'a prospect'}, who is {title or 'a professional'} at "
        f"{company or 'their company'}"
        + (f" in the {industry} industry" if industry else "")
        + ". It should sound specific to their role/company, not generic filler. "
        "Do not pitch anything in this sentence — just a warm, relevant opener. "
        "Output ONLY the sentence, no quotes, no preamble."
    )

    response = client.messages.create(
        model=model,
        max_tokens=100,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((block.text for block in response.content if block.type == "text"), "")
    return text.strip()
