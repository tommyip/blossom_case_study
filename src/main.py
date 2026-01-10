import asyncio
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from src.cro import download_companies
from src.nace import get_nace_category, is_tech_company
from src.enrich import download_cordis, match_grants, enrich_with_jobs
from src.website import enrich_with_websites
from src.http import close_session

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def filter_companies(df: pl.DataFrame) -> pl.DataFrame:
    cutoff = date.today() - timedelta(days=5 * 365)
    cutoff_str = cutoff.isoformat()

    return df.filter(
        (pl.col("company_status").str.strip_chars() == "Normal")
        & (pl.col("company_reg_date") >= cutoff_str)
        & (
            pl.col("company_type").str.contains("LTD")
            | pl.col("company_type").str.contains("DAC")
        )
    )


def add_nace_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("nace_v2_code").map_elements(get_nace_category, return_dtype=pl.Utf8).alias("nace_category"),
        pl.col("nace_v2_code").map_elements(is_tech_company, return_dtype=pl.Boolean).alias("is_tech"),
    )


def select_output_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Select and rename columns for final output."""
    cols = [
        "company_num",
        "company_name",
        "company_type",
        "company_reg_date",
        "company_address_1",
        "company_address_2",
        "company_address_3",
        "company_address_4",
        "eircode",
        "nace_v2_code",
        "nace_category",
        "is_tech",
    ]

    # Add enrichment columns if present
    for col in ["has_eu_grant", "eu_grant_amount", "eu_project_title", "open_roles_count", "is_hiring",
                "website_url", "description", "products", "technology", "customers", "use_cases",
                "category", "target_market", "company_stage", "differentiators"]:
        if col in df.columns:
            cols.append(col)

    return df.select([c for c in cols if c in df.columns])


async def main():
    print("=" * 60)
    print("Ireland CRO Company Scraper")
    print("=" * 60)

    # Step 1: Download companies
    print("\n[1/6] Downloading companies...")
    companies = await download_companies()
    print(f"  Total companies: {companies.shape[0]:,}")

    # Step 2: Filter
    print("\n[2/6] Filtering...")
    filtered = filter_companies(companies)
    print(f"  After filters: {filtered.shape[0]:,}")

    # Step 3: Add NACE categories
    print("\n[3/6] Adding NACE categories...")
    enriched = add_nace_columns(filtered)
    tech_count = enriched.filter(pl.col("is_tech") == True).shape[0]
    print(f"  Tech companies: {tech_count:,}")

    # Step 4: CORDIS grants
    print("\n[4/6] Matching EU grants...")
    cordis = await download_cordis()
    if not cordis.is_empty():
        enriched = match_grants(enriched, cordis)
        grant_count = enriched.filter(pl.col("has_eu_grant") == True).shape[0]
        print(f"  Companies with EU grants: {grant_count:,}")
    else:
        enriched = enriched.with_columns(
            pl.lit(False).alias("has_eu_grant"),
            pl.lit(None).cast(pl.Float64).alias("eu_grant_amount"),
            pl.lit(None).cast(pl.Utf8).alias("eu_project_title"),
        )
        print("  (CORDIS data not available)")

    # Step 5: Job postings
    print("\n[5/6] Adding job data...")
    enriched = await enrich_with_jobs(enriched)
    print("  (Job scraping requires browser automation)")

    # Step 6: Website enrichment
    print("\n[6/6] Enriching with website data...")
    enriched = await enrich_with_websites(enriched, limit=100)
    enriched_count = enriched.filter(pl.col("website_url").is_not_null()).shape[0]
    print(f"  Companies with website data: {enriched_count:,}")

    # Sort: tech first, then by registration date
    enriched = enriched.sort(["is_tech", "company_reg_date"], descending=[True, True])

    # Select output columns
    output = select_output_columns(enriched)

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "companies.parquet"
    output.write_parquet(out_path)
    print(f"\n{'=' * 60}")
    print(f"Saved {output.shape[0]:,} companies to {out_path}")
    print("=" * 60)

    # Summary stats
    print("\nCategory breakdown:")
    print(output.group_by("nace_category").len().sort("len", descending=True).head(10))

    await close_session()


if __name__ == "__main__":
    asyncio.run(main())
