"""Signal analysis for podcast guests."""

from datetime import datetime, timezone

import polars as pl


def analyze_guests(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate signal scores and identify high-activity founders."""
    # Calculate metrics per guest/company
    analysis = df.group_by(["guest_name", "company_name"]).agg([
        pl.count().alias("appearances"),
        pl.col("podcast").n_unique().alias("unique_podcasts"),
        pl.col("is_founder").first().alias("is_founder"),
        pl.col("role").first().alias("role"),
        pl.col("pub_date").max().alias("last_appearance"),
        pl.col("link").first().alias("latest_link"),
    ])

    # Calculate days since last appearance
    now = datetime.now(timezone.utc)
    analysis = analysis.with_columns(
        (pl.lit(now) - pl.col("last_appearance").str.to_datetime(format="%+"))
        .dt.total_days()
        .alias("days_since_last")
    )

    # Calculate signal score
    # score = appearances×2 + unique_podcasts×1.5 + founder_bonus(3) + recency_bonus(2 if <30 days)
    analysis = analysis.with_columns(
        (
            pl.col("appearances") * 2
            + pl.col("unique_podcasts") * 1.5
            + pl.when(pl.col("is_founder") == True).then(3).otherwise(0)
            + pl.when(pl.col("days_since_last") < 30).then(2).otherwise(0)
        ).alias("signal_score")
    )

    # Flag high-activity (2+ appearances OR 2+ unique podcasts)
    analysis = analysis.with_columns(
        ((pl.col("appearances") >= 2) | (pl.col("unique_podcasts") >= 2)).alias("high_signal")
    )

    return analysis.sort("signal_score", descending=True)


def get_high_signal(df: pl.DataFrame) -> pl.DataFrame:
    """Filter to high-signal founders only."""
    return df.filter(pl.col("high_signal") == True)
