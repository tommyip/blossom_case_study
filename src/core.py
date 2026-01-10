"""
CORE website scraper for director information.

NOTE: core.cro.ie is behind Cloudflare protection and returns 403 for direct requests.
Production implementation would need browser automation (playwright/selenium).
"""

from bs4 import BeautifulSoup

from src.http import fetch

CORE_URL = "https://core.cro.ie/company/{}"


async def scrape_directors(company_num: int | str) -> list[str]:
    """Scrape director names from CORE website.

    Returns empty list due to Cloudflare protection.
    Would need playwright for real implementation.
    """
    url = CORE_URL.format(company_num)
    html = await fetch(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")

    # Look for director section (would need actual page structure)
    directors = []
    for row in soup.select(".officer-row, .director-row, [data-type='director']"):
        name = row.select_one(".name, .officer-name")
        if name:
            directors.append(name.text.strip())

    return directors


async def enrich_with_directors(company_nums: list[int]) -> dict[int, list[str]]:
    """Enrich multiple companies with director data.

    Returns dict mapping company_num -> list of director names.
    """
    results = {}
    for num in company_nums:
        results[num] = await scrape_directors(num)
    return results
