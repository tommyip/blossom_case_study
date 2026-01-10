"""
Company website discovery, scraping, and LLM analysis.

Uses DuckDuckGo for website discovery and OpenAI-compatible API for analysis.
"""

import os
import asyncio
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import AsyncOpenAI
import polars as pl

from src.http import fetch, cache, TTL

# Config from environment
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    return _client


def _normalize_name(name: str) -> str:
    """Normalize company name for comparison."""
    name = name.upper()
    for suffix in [" LIMITED", " LTD", " DESIGNATED ACTIVITY COMPANY", " DAC", " PLC", " INC"]:
        name = name.replace(suffix, "")
    return name.strip()


def _domain_matches_company(domain: str, company_name: str) -> bool:
    """Check if domain looks like it belongs to the company."""
    domain = domain.lower().replace("www.", "").split(".")[0]
    clean_name = _normalize_name(company_name).lower()

    # Remove common words
    for word in ["the", "group", "ireland", "international", "solutions", "technologies", "services"]:
        clean_name = clean_name.replace(word, "")
    clean_name = "".join(clean_name.split())  # Remove spaces

    # Check if domain contains significant part of company name or vice versa
    if len(domain) >= 4 and len(clean_name) >= 4:
        return domain in clean_name or clean_name[:6] in domain
    return False


async def _try_domain(domain: str) -> str | None:
    """Check if a domain resolves to a valid website."""
    url = f"https://{domain}/"
    html = await fetch(url)
    if html and len(html) > 500:  # Basic check for real content
        return url
    return None


async def search_website(company_name: str) -> str | None:
    """Find company website via domain guessing and DuckDuckGo search."""
    cache_key = f"website:{company_name}"
    if cache_key in cache:
        return cache[cache_key]

    clean_name = _normalize_name(company_name)
    # Create URL-friendly version of company name
    slug = clean_name.lower().replace(" ", "").replace("&", "and")
    slug_dash = clean_name.lower().replace(" ", "-").replace("&", "and")

    # Try common domain patterns first (faster than search)
    domains_to_try = [
        f"{slug}.com",
        f"{slug}.ie",
        f"www.{slug}.com",
        f"{slug_dash}.com",
        f"{slug_dash}.ie",
    ]

    # Also try first word of company name
    first_word = clean_name.split()[0].lower() if clean_name else ""
    if len(first_word) >= 4:
        domains_to_try.extend([f"{first_word}.com", f"{first_word}.ie"])

    for domain in domains_to_try:
        url = await _try_domain(domain)
        if url:
            cache.set(cache_key, url, expire=TTL)
            return url

    # Fall back to DuckDuckGo search
    from duckduckgo_search import DDGS
    import warnings
    warnings.filterwarnings("ignore")

    # Skip these domains
    skip_domains = ["linkedin.com", "facebook.com", "twitter.com", "youtube.com",
                    "bloomberg.com", "crunchbase.com", "glassdoor.com", "indeed.com",
                    "wikipedia.org", "google.com", "yelp.com", "tripadvisor.com",
                    "gov.ie", "cro.ie", "companieshouse", "dnb.com", "zoominfo.com",
                    "apollo.io", "pitchbook.com", "rocketreach.co", "jeuxvideo.com",
                    "halowaypoint.com", "support.google.com", "reddit.com", "quora.com",
                    "amazon.com", "ebay.com", "alibaba.com", "trustpilot.com",
                    "zhihu.com", "baidu.com", "weibo.com"]  # Chinese sites

    try:
        import time

        # Try multiple search strategies
        queries = [
            f"{clean_name} official website",
            f"{clean_name} company Ireland",
        ]

        for query in queries:
            time.sleep(1.5)  # Rate limit
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=8))
                if not results:
                    continue

                # First pass: look for matching domains
                for r in results:
                    url = r.get("href", "")
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower()
                    if any(skip in domain for skip in skip_domains):
                        continue

                    # Convert support.company.com to company.com
                    if domain.startswith("support."):
                        main_domain = domain[8:]  # Remove "support."
                        url = f"{parsed.scheme}://{main_domain}/"
                        domain = main_domain

                    if _domain_matches_company(domain, company_name):
                        cache.set(cache_key, url, expire=TTL)
                        return url

        # Nothing found
        cache.set(cache_key, None, expire=TTL)
        return None

    except Exception:
        return None


def _extract_text(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)


def _extract_links(html: str, base_url: str) -> list[dict]:
    """Extract all internal links from HTML."""
    soup = BeautifulSoup(html, "lxml")
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True)[:100]

        # Skip empty, anchors, external links
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        # Make absolute
        if not href.startswith("http"):
            href = f"{parsed_base.scheme}://{base_domain}{href if href.startswith('/') else '/' + href}"

        # Skip external links
        if urlparse(href).netloc != base_domain:
            continue

        # Skip duplicates and common non-content pages
        path = urlparse(href).path.lower()
        if path in seen or any(x in path for x in ["/login", "/signup", "/cart", "/checkout", "/privacy", "/terms", "/cookie"]):
            continue
        seen.add(path)

        links.append({"url": href, "text": text, "path": path})

    return links[:50]  # Cap at 50 for LLM selection


async def _select_links_with_llm(links: list[dict], company_name: str) -> list[str]:
    """Use LLM to select most informative links to follow."""
    if not links:
        return []

    links_text = "\n".join([f"- {l['path']}: {l['text']}" for l in links])

    prompt = f"""Given these links from {company_name}'s website, select up to 10 that would be most informative for understanding:
- What the company does (products/services)
- Who their customers are
- Their technology/approach
- Company background

Links:
{links_text}

Return ONLY the paths of the most informative pages, one per line. No explanations. Example:
/about
/products
/solutions"""

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        selected_paths = [p.strip() for p in text.split("\n") if p.strip().startswith("/")]
        return selected_paths[:10]
    except Exception:
        # Fallback: select common informative paths
        priority = ["/about", "/product", "/solution", "/service", "/platform", "/company", "/team", "/customer", "/case", "/feature"]
        return [l["path"] for l in links if any(p in l["path"].lower() for p in priority)][:10]


async def scrape_website(url: str, company_name: str = "") -> dict | None:
    """Scrape homepage and LLM-selected pages."""
    html = await fetch(url)
    if not html:
        return None

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Extract homepage content
    homepage_text = _extract_text(html)[:6000]

    # Extract and select links to follow
    links = _extract_links(html, url)
    selected_paths = await _select_links_with_llm(links, company_name)

    # Scrape selected pages in parallel
    pages = {"homepage": homepage_text}

    async def fetch_page(path: str) -> tuple[str, str]:
        page_url = f"{base_url}{path}"
        page_html = await fetch(page_url)
        if page_html:
            return (path, _extract_text(page_html)[:4000])
        return (path, "")

    if selected_paths:
        results = await asyncio.gather(*[fetch_page(p) for p in selected_paths])
        for path, text in results:
            if text:
                pages[path] = text

    return {
        "url": url,
        "pages": pages,
    }


async def analyze_company(website_data: dict, company_name: str) -> dict:
    """Use LLM to analyze company website content."""
    cache_key = f"llm2:{website_data['url']}"  # New cache key for new format
    if cache_key in cache:
        return cache[cache_key]

    # Build content from all pages
    pages = website_data.get("pages", {})
    content_parts = []
    for page_name, text in pages.items():
        if text:
            content_parts.append(f"=== {page_name} ===\n{text[:4000]}")
    content = "\n\n".join(content_parts)

    # Truncate if too long
    if len(content) > 30000:
        content = content[:30000] + "...[truncated]"

    prompt = f"""Analyze this company's website content for "{company_name}" and provide a detailed profile.

{content}

Respond in this exact JSON format:
{{
    "description": "2-4 sentences describing what the company does, their main product/service, and value proposition",
    "products": "List of main products or services offered (comma-separated)",
    "technology": "Key technologies, platforms, or technical approach mentioned",
    "customers": "Target customer segments, industries served, or notable customers mentioned",
    "use_cases": "Main use cases or problems they solve",
    "category": "Primary category: SaaS, Fintech, Biotech, Healthcare, E-commerce, Marketplace, Developer Tools, AI/ML, Cybersecurity, EdTech, PropTech, CleanTech, HRTech, MarTech, LegalTech, InsurTech, Other",
    "target_market": "B2B, B2C, or B2B2C",
    "company_stage": "Estimated stage based on website: Startup, Growth, Enterprise (or Unknown)",
    "differentiators": "What makes them unique or different from competitors"
}}

Extract as much detail as possible from the content. Use "Unknown" only if information is truly not available."""

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1000,  # Increased for detailed output
        )

        text = response.choices[0].message.content.strip()
        # Parse JSON from response
        import json
        # Handle markdown code blocks
        if "```" in text:
            text = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL).group(1)
        result = json.loads(text)
        cache.set(cache_key, result, expire=TTL)
        return result

    except Exception as e:
        return {
            "description": "Unknown",
            "products": "Unknown",
            "technology": "Unknown",
            "customers": "Unknown",
            "use_cases": "Unknown",
            "category": "Unknown",
            "target_market": "Unknown",
            "company_stage": "Unknown",
            "differentiators": "Unknown",
            "error": str(e),
        }


async def enrich_company(company_name: str) -> dict:
    """Full pipeline: search -> scrape -> analyze."""
    url = await search_website(company_name)
    if not url:
        return {
            "website_url": None, "description": None, "products": None,
            "technology": None, "customers": None, "use_cases": None,
            "category": None, "target_market": None, "company_stage": None,
            "differentiators": None,
        }

    website_data = await scrape_website(url, company_name)
    if not website_data:
        return {
            "website_url": url, "description": None, "products": None,
            "technology": None, "customers": None, "use_cases": None,
            "category": None, "target_market": None, "company_stage": None,
            "differentiators": None,
        }

    analysis = await analyze_company(website_data, company_name)

    return {
        "website_url": url,
        "description": analysis.get("description"),
        "products": analysis.get("products"),
        "technology": analysis.get("technology"),
        "customers": analysis.get("customers"),
        "use_cases": analysis.get("use_cases"),
        "category": analysis.get("category"),
        "target_market": analysis.get("target_market"),
        "company_stage": analysis.get("company_stage"),
        "differentiators": analysis.get("differentiators"),
    }


async def enrich_with_websites(df: pl.DataFrame, limit: int = 100) -> pl.DataFrame:
    """Enrich DataFrame with website data for top N companies."""
    # Filter for actual software/IT companies (not financial SPVs)
    software_categories = ["Software & IT", "Data & Hosting", "Software Publishing"]
    subset = df.filter(
        (pl.col("nace_category").is_in(software_categories))
        & (~pl.col("company_name").str.contains("DESIGNATED ACTIVITY"))  # Skip DACs/SPVs
        & (~pl.col("company_name").str.contains("ISSUER"))
        & (~pl.col("company_name").str.contains("FUND"))
    ).head(limit)
    company_names = subset["company_name"].to_list()

    print(f"  Enriching {len(company_names)} companies with website data...")

    # Process 10 companies at a time
    semaphore = asyncio.Semaphore(10)

    async def limited_enrich(name: str) -> dict:
        async with semaphore:
            result = await enrich_company(name)
            result["company_name"] = name
            return result

    # Run all in parallel (limited by semaphore)
    results = await asyncio.gather(*[limited_enrich(n) for n in company_names])
    print(f"    {len(company_names)}/{len(company_names)}")

    # Create enrichment DataFrame
    enrich_df = pl.DataFrame(list(results))

    # Join back to original
    df = df.join(enrich_df, on="company_name", how="left")

    return df
