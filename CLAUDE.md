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

## Code Style
- **Minimal**. No defensive programming.
- **Concise**. Short names OK.
- **Few comments**. Only when non-obvious.

---

## Commands

```bash
uv run python -m src.main        # run scraper
uv run streamlit run src/app.py  # run dashboard
```

---

## What's Implemented

### Core Pipeline
- **CRO bulk download** - 805k companies from opendata.cro.ie
- **Filtering** - Normal status, last 5 years, LTD/DAC types → ~107k companies
- **NACE mapping** - Industry categories, tech company identification → ~24k tech companies
- **Streamlit dashboard** - Filters, KPIs, data table, charts

### Infrastructure
- Per-domain rate limiting via `aiolimiter`
- Disk caching with 1-day TTL for resume/retry
- Async HTTP with `aiohttp`

---

## Pending Implementation (Blocked)

### CORE Directors Scraper
**Status**: Blocked by Cloudflare (403)
**URL**: `https://core.cro.ie/company/{company_number}`
**Solution needed**: Browser automation (playwright/selenium)

### Job Postings (Indeed/LinkedIn)
**Status**: Blocked (403)
**Solution needed**: Browser automation or API access

### CORDIS EU Grants
**Status**: URL changed, needs manual download
**Source**: https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027
**Action**: Download CSV manually to `data/cordis_horizon.csv`

---

## Future Enrichment Ideas

### Company Website (HIGHEST VALUE)
Scrape homepage + /about page, use LLM for:
- One-line product description
- Product category (SaaS, Fintech, Biotech, etc.)
- Target market

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
| Website/product | What they actually build |
| NACE code | Industry classification |
| Job postings | Growth trajectory |
| EU grants | Technical validation |
| GitHub | Developer traction |

**Blossom cares about**:
- Mission-driven founders
- Product-led/engineering-led teams
- $10bn+ market potential
- Network effects
