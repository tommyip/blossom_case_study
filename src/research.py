"""
Company research using Tongyi DeepResearch via OpenRouter.
"""

import asyncio
import json
import os
import re
from datetime import date

import aiohttp
import polars as pl
from openai import AsyncOpenAI

from src.http import cache, TTL

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RESEARCH_MODEL = "alibaba/tongyi-deepresearch-30b-a3b"

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    return _client


def _build_prompt(company: dict) -> str:
    """Build research prompt from company info."""
    # Build address string
    addr_parts = []
    for i in range(1, 5):
        addr = company.get(f"company_address_{i}")
        if addr:
            addr_parts.append(addr)
    full_address = ", ".join(addr_parts)

    return f"""Research this Irish company for a Series A investment evaluation.

Today's date: {date.today().isoformat()}

Company: {company.get("company_name", "Unknown")}
Registered: {company.get("company_reg_date", "Unknown")}
Address: {full_address}
CRO Number: {company.get("company_num", "Unknown")}
Industry (NACE): {company.get("nace_category", "Unknown")}

Create a comprehensive one-page investment memo covering:

## Company Overview
What the company does, their main product/service, and value proposition.

## Market & Customers
Target market size, customer segments, and go-to-market approach.

## Technology & Product
Tech stack, platform architecture, and product differentiation.

## Team
Founders, key executives, and their backgrounds.

## Traction & Funding
Revenue signals, funding history, notable investors, and growth indicators.

## Competitive Landscape
Key competitors and how the company differentiates.

## Investment Thesis
Bull case vs bear case for Series A investment.

---

At the end, provide structured data inside <json></json> tags:

<json>
{{
    "website": "company website URL or Unknown",
    "industry": "primary category (SaaS/Fintech/Biotech/Healthcare/AI-ML/Cybersecurity/EdTech/etc)",
    "sub_industry": "specific niche",
    "tech_stack": ["list of technologies mentioned"],
    "business_model": "B2B/B2C/B2B2C/Marketplace",
    "stage": "Pre-seed/Seed/Series A/Growth/Unknown",
    "key_people": ["Name - Role"],
    "funding_total": "amount or Unknown",
    "employee_count": "number or Unknown",
    "founded_year": "year or Unknown",
    "verdict": "Promising/Maybe/Pass",
    "verdict_reason": "one sentence"
}}
</json>

If the company cannot be found or has minimal online presence, still provide the JSON with "Unknown" values."""


def _normalize_verdict(verdict: str | None) -> str | None:
    """Normalize verdict to sortable format."""
    if not verdict or verdict.lower() == "unknown":
        return None
    verdict_map = {
        "promising": "1-Promising",
        "maybe": "2-Maybe",
        "pass": "3-Pass",
    }
    return verdict_map.get(verdict.lower(), verdict)


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
    # Try <json> tags first, then fall back to ```json blocks
    json_match = re.search(r"<json>\s*(\{.*?\})\s*</json>", text, re.DOTALL)
    if not json_match:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)

    if json_match:
        # Extract markdown (everything before the JSON block)
        json_start = json_match.start()
        markdown_report = text[:json_start].strip()

        # Parse JSON
        try:
            structured = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            structured = {}
    else:
        # No JSON found, use entire response as markdown
        markdown_report = text
        structured = {}

    tech_stack = structured.get("tech_stack", [])
    key_people = structured.get("key_people", [])

    return {
        "research_report": markdown_report,
        "website": _clean_value(structured.get("website")),
        "industry": _clean_value(structured.get("industry")),
        "sub_industry": _clean_value(structured.get("sub_industry")),
        "tech_stack": json.dumps(tech_stack) if tech_stack else None,
        "business_model": _clean_value(structured.get("business_model")),
        "stage": _clean_value(structured.get("stage")),
        "key_people": json.dumps(key_people) if key_people else None,
        "funding_total": _clean_value(structured.get("funding_total")),
        "employee_count": _clean_value(structured.get("employee_count")),
        "founded_year": _clean_value(str(structured.get("founded_year", ""))),
        "verdict": _normalize_verdict(structured.get("verdict")),
        "verdict_reason": _clean_value(structured.get("verdict_reason")),
    }


async def research_company(company: dict) -> dict:
    """Research a single company using Tongyi DeepResearch."""
    company_num = str(company.get("company_num", ""))
    cache_key = f"research:{company_num}"

    if cache_key in cache:
        return cache[cache_key]

    prompt = _build_prompt(company)

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=RESEARCH_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content
        result = _parse_response(text)
        result["company_name"] = company.get("company_name")
        cache.set(cache_key, result, expire=TTL)
        return result

    except Exception as e:
        print(f"    Failed: {company.get('company_name')} - {e}")
        return None


async def _check_website(session: aiohttp.ClientSession, url: str) -> bool:
    """Check if a website URL is accessible."""
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp:
            return resp.status < 400
    except Exception:
        return False


async def _validate_websites(results: list[dict]) -> list[dict]:
    """Validate website URLs concurrently, set invalid ones to None."""
    # Collect results with websites
    with_websites = [(i, r["website"]) for i, r in enumerate(results) if r.get("website")]
    if not with_websites:
        return results

    print(f"  Validating {len(with_websites)} websites...")

    async with aiohttp.ClientSession() as session:
        checks = await asyncio.gather(*[_check_website(session, url) for _, url in with_websites])

    # Update results - set invalid websites to None
    valid_count = 0
    for (idx, _), is_valid in zip(with_websites, checks):
        if is_valid:
            valid_count += 1
        else:
            results[idx]["website"] = None

    print(f"    {valid_count}/{len(with_websites)} websites valid")
    return results


async def enrich_with_research(df: pl.DataFrame, limit: int = 100) -> pl.DataFrame:
    """Enrich DataFrame with Tongyi research for top N companies."""
    # Filter for software/IT companies (not financial SPVs)
    software_categories = ["Software & IT", "Data & Hosting", "Software Publishing"]
    subset = df.filter(
        (pl.col("nace_category").is_in(software_categories))
        & (~pl.col("company_name").str.contains("DESIGNATED ACTIVITY"))
        & (~pl.col("company_name").str.contains("ISSUER"))
        & (~pl.col("company_name").str.contains("FUND"))
    ).head(limit)

    companies = subset.to_dicts()
    print(f"  Researching {len(companies)} companies with Tongyi DeepResearch...")

    # Process 10 at a time
    semaphore = asyncio.Semaphore(10)
    completed = 0

    async def limited_research(company: dict) -> dict:
        nonlocal completed
        async with semaphore:
            result = await research_company(company)
            completed += 1
            if completed % 5 == 0 or completed == len(companies):
                print(f"    {completed}/{len(companies)}")
            return result

    results = await asyncio.gather(*[limited_research(c) for c in companies])

    # Filter out failed results
    successful = [r for r in results if r is not None]
    failed_count = len(results) - len(successful)
    if failed_count > 0:
        print(f"  {failed_count} companies failed research")

    # Validate websites concurrently
    successful = await _validate_websites(successful)

    # Create enrichment DataFrame from successful results only
    enrich_df = pl.DataFrame(successful)

    # Join back to original
    df = df.join(enrich_df, on="company_name", how="left")

    return df
