"""Company research for podcast guests using Tongyi DeepResearch."""

import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path

from openai import AsyncOpenAI

from src.http import cache, TTL

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RESEARCH_MODEL = "alibaba/tongyi-deepresearch-30b-a3b"

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "podcast" / "research"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    return _client


def _build_prompt(guest: dict) -> str:
    """Build research prompt from guest info."""
    return f"""Research this startup founder and their company for investment analysis.

Today's date: {date.today().isoformat()}

Founder: {guest.get("guest_name", "Unknown")}
Company: {guest.get("company_name", "Unknown")}
Role: {guest.get("role", "Unknown")}
Recent podcast appearance: {guest.get("podcast", "Unknown")}
Appearance date: {guest.get("last_appearance", "Unknown")}

Investigate and provide:

## Company Overview
What the company does, their main product/service, and value proposition.

## Stage & Funding
Current stage (pre-seed, seed, Series A, etc.), total funding, latest round details, notable investors.

## Traction
Revenue/ARR if known, user/customer metrics, growth indicators.

## Technology & Product
Core product/tech, competitive differentiation.

## Recent News
Press from last 6 months, product launches, partnerships, signals of upcoming raise.

## Investment Assessment
- Likelihood of active fundraise (high/medium/low)
- Strengths and concerns
- Attractiveness score (1-10)

---

At the end, provide structured data inside <json></json> tags:

<json>
{{
    "website": "company website URL or Unknown",
    "industry": "primary category (SaaS/Fintech/Biotech/Healthcare/AI-ML/Cybersecurity/EdTech/etc)",
    "stage": "Pre-seed/Seed/Series A/Growth/Unknown",
    "funding_total": "amount or Unknown",
    "latest_round": "amount and date or Unknown",
    "notable_investors": ["investor names"],
    "employee_count": "number or Unknown",
    "founded_year": "year or Unknown",
    "fundraise_likelihood": "high/medium/low",
    "attractiveness_score": 1-10,
    "key_signals": ["list of notable signals"]
}}
</json>

If the company cannot be found or has minimal online presence, still provide the JSON with "Unknown" values."""


def _clean_value(value) -> str | None:
    """Return None for unknown/empty values."""
    if value is None:
        return None
    value = str(value)
    if not value or value.lower() == "unknown":
        return None
    return value


def _parse_response(text: str) -> dict:
    """Parse response into markdown report + structured data."""
    json_match = re.search(r"<json>\s*(\{.*?\})\s*</json>", text, re.DOTALL)
    if not json_match:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)

    if json_match:
        json_start = json_match.start()
        markdown_report = text[:json_start].strip()
        try:
            structured = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            structured = {}
    else:
        markdown_report = text
        structured = {}

    return {
        "research_report": markdown_report,
        "website": _clean_value(structured.get("website")),
        "industry": _clean_value(structured.get("industry")),
        "stage": _clean_value(structured.get("stage")),
        "funding_total": _clean_value(structured.get("funding_total")),
        "latest_round": _clean_value(structured.get("latest_round")),
        "notable_investors": json.dumps(structured.get("notable_investors", [])) or None,
        "employee_count": _clean_value(structured.get("employee_count")),
        "founded_year": _clean_value(str(structured.get("founded_year", ""))),
        "fundraise_likelihood": _clean_value(structured.get("fundraise_likelihood")),
        "attractiveness_score": structured.get("attractiveness_score"),
        "key_signals": json.dumps(structured.get("key_signals", [])) or None,
    }


async def research_guest(guest: dict) -> dict | None:
    """Research a guest's company using Tongyi DeepResearch."""
    company = guest.get("company_name", "")
    cache_key = f"podcast_research:{company}"

    if cache_key in cache:
        result = cache[cache_key]
        result["guest_name"] = guest.get("guest_name")
        result["company_name"] = company
        return result

    prompt = _build_prompt(guest)

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=RESEARCH_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content
        result = _parse_response(text)
        result["guest_name"] = guest.get("guest_name")
        result["company_name"] = company
        cache.set(cache_key, result, expire=TTL)

        # Save research JSON
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", company)[:50]
        (OUTPUT_DIR / f"{safe_name}.json").write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        print(f"    Research failed: {company} - {e}")
        return None


async def research_high_signal(guests: list[dict], limit: int = 20) -> list[dict]:
    """Research high-signal guests concurrently."""
    # Dedupe by company, take first limit
    seen = set()
    unique = []
    for g in guests:
        company = g.get("company_name")
        if company and company not in seen:
            seen.add(company)
            unique.append(g)
            if len(unique) >= limit:
                break

    print(f"  Researching {len(unique)} companies with Tongyi DeepResearch...")

    semaphore = asyncio.Semaphore(5)
    completed = 0

    async def limited_research(guest: dict) -> dict | None:
        nonlocal completed
        async with semaphore:
            result = await research_guest(guest)
            completed += 1
            print(f"    {completed}/{len(unique)}: {guest.get('company_name')}")
            return result

    results = await asyncio.gather(*[limited_research(g) for g in unique])
    return [r for r in results if r is not None]
