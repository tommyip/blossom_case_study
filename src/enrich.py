"""
Enrichment functions for company data.
"""

import io
import json
import zipfile
from pathlib import Path

import aiohttp
import polars as pl

from src.http import cache, TTL

DATA_DIR = Path(__file__).parent.parent / "data"
CORDIS_URL = "https://cordis.europa.eu/data/cordis-HORIZONprojects-json.zip"


async def download_cordis() -> pl.DataFrame:
    """Download CORDIS organization data and filter for Irish companies."""
    cache_key = "cordis:organizations:IE"

    if cache_key in cache:
        return pl.DataFrame(cache[cache_key])

    print("  Downloading CORDIS data...")
    async with aiohttp.ClientSession() as session:
        async with session.get(CORDIS_URL) as resp:
            if resp.status != 200:
                print(f"  Failed to download CORDIS data: {resp.status}")
                return pl.DataFrame()
            data = await resp.read()

    # Extract organization.json from zip
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("organization.json") as f:
            orgs = json.load(f)

    # Filter for Irish organizations
    irish_orgs = [o for o in orgs if o.get("country") == "IE"]
    print(f"  Found {len(irish_orgs)} Irish organizations in CORDIS")

    if not irish_orgs:
        return pl.DataFrame()

    # Convert to DataFrame
    df = pl.DataFrame(irish_orgs)

    # Cache the result
    cache.set(cache_key, df.to_dicts(), expire=TTL)

    return df


def match_grants(companies: pl.DataFrame, cordis: pl.DataFrame) -> pl.DataFrame:
    """Match companies to CORDIS grants by name."""
    if cordis.is_empty():
        return companies.with_columns(
            pl.lit(False).alias("has_eu_grant"),
            pl.lit(None).cast(pl.Float64).alias("eu_grant_amount"),
            pl.lit(None).cast(pl.Utf8).alias("eu_project_title"),
        )

    # Normalize company names for matching
    companies = companies.with_columns(
        pl.col("company_name")
        .str.to_uppercase()
        .str.replace_all(r"\s+(LIMITED|LTD|DAC|PLC|DESIGNATED ACTIVITY COMPANY)\.?$", "")
        .str.strip_chars()
        .alias("_name_norm")
    )

    # Normalize CORDIS names
    cordis = cordis.with_columns(
        pl.col("name")
        .str.to_uppercase()
        .str.replace_all(r"\s+(LIMITED|LTD|DAC|PLC)\.?$", "")
        .str.strip_chars()
        .alias("_name_norm")
    )

    # Cast ecContribution to float (it can be string or number)
    cordis = cordis.with_columns(
        pl.col("ecContribution").cast(pl.Float64, strict=False).alias("ecContribution")
    )

    # Aggregate grants per organization
    grant_agg = cordis.group_by("_name_norm").agg(
        pl.lit(True).alias("has_eu_grant"),
        pl.col("ecContribution").sum().alias("eu_grant_amount"),
        pl.col("projectAcronym").first().alias("eu_project_title"),
    )

    # Left join
    result = companies.join(grant_agg, on="_name_norm", how="left")

    # Fill nulls for non-matches
    result = result.with_columns(
        pl.col("has_eu_grant").fill_null(False),
    )

    return result.drop("_name_norm")
