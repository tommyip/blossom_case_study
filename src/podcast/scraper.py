"""Main podcast scraper pipeline."""

import asyncio
from pathlib import Path

import polars as pl

from src.podcast.feeds import fetch_all_feeds
from src.podcast.extract import extract_all_guests, cluster_guests
from src.podcast.analysis import analyze_guests, get_high_signal
from src.podcast.research import research_high_signal

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "podcast"


async def main():
    print("=" * 60)
    print("Podcast Guest Tracker")
    print("=" * 60)

    # Step 1: Fetch RSS feeds
    print("\n[1/5] Fetching RSS feeds (last year)...")
    episodes = fetch_all_feeds(days=365)
    print(f"  Total episodes: {len(episodes)}")

    if not episodes:
        print("No episodes found. Exiting.")
        return

    # Step 2: Extract guests
    print("\n[2/5] Extracting guests with DeepSeek...")
    guests = await extract_all_guests(episodes)
    print(f"  Episodes with guests: {len(guests)}")

    if not guests:
        print("No guests extracted. Exiting.")
        return

    # Step 3: Cluster guests (identify same person across name variations)
    print("\n[3/5] Clustering guests...")
    unique_before = len({(g["guest_name"], g["company_name"]) for g in guests})
    guests = await cluster_guests(guests)
    unique_after = len({(g["guest_name"], g["company_name"]) for g in guests})
    print(f"  Unique guests: {unique_before} -> {unique_after}")

    # Save all episodes
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    episodes_df = pl.DataFrame(guests)
    episodes_df.write_parquet(OUTPUT_DIR / "all_episodes.parquet")

    # Step 4: Analyze and score
    print("\n[4/5] Analyzing guest signals...")
    analysis = analyze_guests(episodes_df)
    analysis.write_parquet(OUTPUT_DIR / "guest_analysis.parquet")

    high_signal = get_high_signal(analysis)
    high_signal.write_parquet(OUTPUT_DIR / "high_signal.parquet")
    print(f"  Total unique guests: {analysis.shape[0]}")
    print(f"  High-signal founders: {high_signal.shape[0]}")

    # Step 5: Deep research for high-signal guests
    if high_signal.shape[0] > 0:
        print("\n[5/5] Researching high-signal founders with Tongyi...")
        high_signal_dicts = high_signal.to_dicts()
        researched = await research_high_signal(high_signal_dicts, limit=20)
        print(f"  Companies researched: {len(researched)}")

        if researched:
            research_df = pl.DataFrame(researched)
            research_df.write_parquet(OUTPUT_DIR / "researched.parquet")
    else:
        print("\n[5/5] No high-signal founders to research.")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Output saved to {OUTPUT_DIR}")
    print("=" * 60)

    # Show top signals
    print("\nTop signal founders:")
    print(high_signal.select(["guest_name", "company_name", "appearances", "unique_podcasts", "signal_score"]).head(10))


if __name__ == "__main__":
    asyncio.run(main())
