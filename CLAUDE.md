# Ireland CRO Company Registry Scraper

## Project Overview
Scraper for Irish CRO to identify Series A investment opportunities. Case study for Blossom Capital.

**Goal**: Find companies incorporated in last 5 years, enriched with product/industry data for filtering.

## Tech Stack
- `uv` - packages
- `aiohttp` + `aiolimiter` - async HTTP with per-domain rate limiting
- `diskcache` - persistent cache with 1-day TTL
- `beautifulsoup4` + `lxml` - parsing
- `polars` - data (NOT pandas)
- `streamlit` - dashboard
- `openai` - Tongyi DeepResearch via OpenRouter

## Code Style
- **Minimal**. No defensive programming.
- **Concise**. Short names OK.
- **Few comments**. Only when non-obvious.

---

## Commands

```bash
# CRO Company Registry
uv run python -m src.main        # run CRO scraper
uv run streamlit run src/app.py  # run CRO dashboard

# Podcast Signal Tracker
uv run python -m src.podcast.scraper  # run podcast scraper
uv run streamlit run src/podcast/app.py  # run podcast dashboard
```

---

## What's Implemented

### Core Pipeline
- **CRO bulk download** - 805k companies from opendata.cro.ie
- **Filtering** - Normal status, last 5 years, LTD/DAC types → ~107k companies
- **NACE mapping** - Industry categories, tech company identification → ~24k tech companies
- **EU Grants** - CORDIS Horizon data auto-downloaded and matched by company name
- **Deep Research** - Tongyi DeepResearch via OpenRouter for top 100 software companies
  - Investment memos with company overview, market, technology, team, funding, competitive landscape
  - Structured data: industry, stage, verdict, key people, funding, employees
  - Cost: ~$0.0016 per company (~$0.16 for 100 companies)
- **Streamlit dashboard** - Filters, KPIs, data table, investment reports

### Infrastructure
- Per-domain rate limiting via `aiolimiter`
- Disk caching with 1-day TTL for resume/retry
- Async HTTP with `aiohttp`

### Podcast Signal Tracker
Identifies founders doing "podcast tours" before funding announcements.

- **RSS Feed Scraping** - 10 startup podcasts (20VC, The Pitch, How I Built This, etc.)
- **Guest Extraction** - DeepSeek extracts guest name, company, role from episode metadata
- **Guest Clustering** - DeepSeek identifies same person across name variations
- **Signal Scoring** - Appearances × 2 + unique podcasts × 1.5 + founder bonus + recency bonus
- **Deep Research** - Tongyi DeepResearch for founders with 2+ appearances
- **Output**: Parquet files + per-company research JSONs

**Signal**: Founders with 2+ podcast appearances across different shows = potential fundraise coming.

---

## Pending Implementation (Blocked)

### CORE Directors Scraper
**Status**: Blocked by Cloudflare Turnstile
**URL**: `https://core.cro.ie/company/{company_number}`
**Tested**: Playwright (headless/headed), playwright-stealth, nodriver - all blocked
**Solution needed**: Captcha-solving service (2Captcha) or manual session cookies


---

## Environment Variables

For Tongyi DeepResearch via OpenRouter:
```bash
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_API_KEY="your-openrouter-api-key"
```

---

## Future Enrichment Ideas

### Enterprise Ireland HPSU
Check news/press releases for HPSU status badge.

### Crunchbase
Funding history, investors, founder backgrounds.
Requires API key or scraping.

### GitHub Organization
Open source activity, stars, primary language.
Free API: `https://api.github.com/orgs/{org_name}`

---

## Blossom Investment Criteria

| Signal | What it tells you |
|--------|-------------------|
| Deep Research | Company overview, team, funding, competitive landscape |
| NACE code | Industry classification |
| EU grants | Technical validation |

**Blossom cares about**:
- Mission-driven founders
- Product-led/engineering-led teams
- $10bn+ market potential
- Network effects
