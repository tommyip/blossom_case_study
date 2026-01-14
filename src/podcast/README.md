# Podcast Signal Tracker

Identifies founders doing "podcast tours" before funding announcements.

## The Signal

Founders do a podcast tour before funding announcements. A spike in appearances on early-stage podcasts = something is happening. This is under-monitored compared to Twitter/LinkedIn/press.

## How It Works

1. **Fetch RSS** - Pull episodes from 10 startup podcasts (last 90 days)
2. **Extract Guests** - DeepSeek extracts guest name, company, role from episode metadata
3. **Cluster Guests** - DeepSeek identifies same person across name variations
4. **Score Signals** - `appearances × 2 + unique_podcasts × 1.5 + founder_bonus + recency_bonus`
5. **Deep Research** - Tongyi DeepResearch for founders with 2+ appearances

## Podcasts Tracked

| Podcast | Focus |
|---------|-------|
| The Pitch | Live VC pitches |
| Twenty Minute VC | Seed to Series A |
| Product Market Fit Show | 0-to-1 journeys |
| Indie Hackers | Bootstrapped founders |
| My First Million | Business ideas |
| How I Built This | Founder origin stories |
| This Week in Startups | Startup ecosystem |
| The Full Ratchet | Pre-seed/seed focus |
| Equity | Startup funding news |
| Startup Savant | Early-stage interviews |

## Usage

```bash
# Run scraper
uv run python -m src.podcast.scraper

# Run dashboard
uv run streamlit run src/podcast/app.py
```

## Output

```
output/podcast/
├── all_episodes.parquet     # All extracted guests
├── guest_analysis.parquet   # Analyzed with scores
├── high_signal.parquet      # 2+ appearances only
├── researched.parquet       # Deep research results
└── research/                # Per-company JSONs
    └── {company}.json
```

## Example Results

```
┌───────────────────┬────────────────┬─────────────┬─────────────────┬──────────────┐
│ guest_name        ┆ company_name   ┆ appearances ┆ unique_podcasts ┆ signal_score │
╞═══════════════════╪════════════════╪═════════════╪═════════════════╪══════════════╡
│ Wade Foster       ┆ Zapier         ┆ 4           ┆ 2               ┆ 16.0         │
│ Sam Parr          ┆ Hampton        ┆ 2           ┆ 2               ┆ 12.0         │
│ Arthur Mensch     ┆ Mistral AI     ┆ 2           ┆ 2               ┆ 10.0         │
│ Gabe Pereyra      ┆ Harvey AI      ┆ 2           ┆ 2               ┆ 10.0         │
└───────────────────┴────────────────┴─────────────┴─────────────────┴──────────────┘
```

## Cost

- Guest extraction (DeepSeek): ~$0.01 per 100 episodes
- Deep research (Tongyi): ~$0.08 per company
- Total for typical run: ~$2-3
