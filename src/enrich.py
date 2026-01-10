"""
Enrichment functions for company data.

CORDIS data would need manual download from:
https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027
"""

from pathlib import Path

import aiohttp
import polars as pl

DATA_DIR = Path(__file__).parent.parent / "data"


async def download_cordis() -> pl.DataFrame:
    """Load CORDIS data if manually downloaded.

    Download CSV from data.europa.eu and place in data/cordis_horizon.csv
    """
    path = DATA_DIR / "cordis_horizon.csv"
    if not path.exists():
        print("CORDIS data not found. Download from data.europa.eu and save to data/cordis_horizon.csv")
        return pl.DataFrame()

    df = pl.read_csv(path, infer_schema_length=10000, ignore_errors=True)

    # Filter for Ireland
    for col in ["organizationCountry", "country"]:
        if col in df.columns:
            return df.filter(pl.col(col) == "IE")

    country_cols = [c for c in df.columns if "country" in c.lower()]
    if country_cols:
        return df.filter(pl.col(country_cols[0]) == "IE")

    return df


def match_grants(companies: pl.DataFrame, cordis: pl.DataFrame) -> pl.DataFrame:
    """Match companies to CORDIS grants by name (fuzzy match)."""
    # Simple approach: exact match on normalized names
    if cordis.is_empty():
        return companies.with_columns(
            pl.lit(False).alias("has_eu_grant"),
            pl.lit(None).cast(pl.Float64).alias("eu_grant_amount"),
            pl.lit(None).cast(pl.Utf8).alias("eu_project_title"),
        )

    # Normalize company names for matching
    companies = companies.with_columns(
        pl.col("company_name").str.to_uppercase().str.strip_chars().alias("_name_norm")
    )

    # Find the organization/name column in CORDIS
    name_col = None
    for col in ["organisationName", "organizationName", "name", "legalName"]:
        if col in cordis.columns:
            name_col = col
            break

    if not name_col:
        return companies.drop("_name_norm").with_columns(
            pl.lit(False).alias("has_eu_grant"),
            pl.lit(None).cast(pl.Float64).alias("eu_grant_amount"),
            pl.lit(None).cast(pl.Utf8).alias("eu_project_title"),
        )

    # Find grant amount column
    amount_col = None
    for col in ["ecContribution", "totalCost", "ecMaxContribution"]:
        if col in cordis.columns:
            amount_col = col
            break

    # Find project title column
    title_col = None
    for col in ["title", "projectTitle", "acronym"]:
        if col in cordis.columns:
            title_col = col
            break

    # Normalize CORDIS names
    cordis = cordis.with_columns(
        pl.col(name_col).str.to_uppercase().str.strip_chars().alias("_name_norm")
    )

    # Aggregate grants per organization
    grant_agg = cordis.group_by("_name_norm").agg(
        pl.lit(True).alias("has_eu_grant"),
        pl.col(amount_col).sum().alias("eu_grant_amount") if amount_col else pl.lit(None).alias("eu_grant_amount"),
        pl.col(title_col).first().alias("eu_project_title") if title_col else pl.lit(None).alias("eu_project_title"),
    )

    # Left join
    result = companies.join(grant_agg, on="_name_norm", how="left")

    # Fill nulls for non-matches
    result = result.with_columns(
        pl.col("has_eu_grant").fill_null(False),
    )

    return result.drop("_name_norm")
