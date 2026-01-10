# Ireland CRO Company Registry Scraper

## Project Overview
Scraper for Irish CRO to identify Series A investment opportunities. Case study for Blossom Capital.

**Goal**: Find 100 companies incorporated in last 5 years with €500k+ assets, enriched with product/industry data for filtering.

## Tech Stack
- `uv` - packages
- `aiohttp` - async HTTP
- `aiolimiter` - per-domain rate limiting
- `diskcache` - persistent cache with TTL
- `beautifulsoup4` + `lxml` - parsing
- `polars` - data (NOT pandas)
- `streamlit` - dashboard

## Code Style
- **Minimal**. No defensive programming.
- **Concise**. Short names OK.
- **Few comments**. Only when non-obvious.

---

## Data Sources

### 1. CRO Companies (bulk CSV)
```
https://opendata.cro.ie/dataset/bf6f837d-0946-4c14-9a99-82cd6980c121/resource/3fef41bc-b8f4-4b10-8434-ce51c29b1bba/download/companies.csv.zip
```
Fields: company_number, company_name, status, company_type, incorporation_date, registered_address, **nace_code**

### 2. CRO Financial Statements
```
2022: https://opendata.cro.ie/dataset/99e64d94-0a2f-4cd1-b237-7164bec1426e/resource/508d4f8a-74a1-40c7-8b86-cdf0d54a4929/download/financial_statements.csv
2023: https://opendata.cro.ie/dataset/99e64d94-0a2f-4cd1-b237-7164bec1426e/resource/dd413039-f628-4931-9788-dfc38eaf6b99/download/financial_statements_2023.csv
```
Fields: total_assets, shareholders_funds, turnover, profit_loss, cash, creditors, debtors, employees

### 3. CORE Website (directors)
```
https://core.cro.ie/company/{company_number}
```
Scrape: director names, secretary

---

## Enrichment Sources (IDEAS-BASED)

These tell you *what* the company does and *why* it's interesting.

### 4. Company Website (HIGHEST VALUE)
**Why**: Product description, positioning, what they actually build.

**How**:
1. Extract domain from registered address or Google search "{company_name} Ireland"
2. Scrape homepage + /about page
3. Use LLM to extract: one-line description, product category, target market

```python
async def get_company_description(name: str) -> dict:
    # Google search for domain
    domain = await search_domain(name)
    if not domain: return {}
    
    html = await fetch(f"https://{domain}")
    soup = BeautifulSoup(html, "lxml")
    
    # Get meta description + first few paragraphs
    meta = soup.find("meta", {"name": "description"})
    text = " ".join(p.text for p in soup.find_all("p")[:5])
    
    return {"domain": domain, "description": meta.get("content", ""), "text": text[:1000]}
```

**Output fields**:
- `website_url`
- `meta_description`
- `product_summary` (LLM-generated one-liner)
- `product_category` (SaaS, Fintech, Biotech, Hardware, etc.)

### 5. Job Postings (TRACTION SIGNAL)
**Why**: Hiring = growth. Engineering-heavy = product-led (Blossom likes this).

**Sources**:
- LinkedIn Jobs: `https://www.linkedin.com/jobs/search/?keywords={company_name}&location=Ireland`
- Indeed: `https://ie.indeed.com/jobs?q={company_name}`

**What to extract**:
- `open_roles_count`
- `engineering_roles_count`
- `is_hiring_engineers` (boolean)
- `recent_job_posted` (date)

```python
async def get_job_count(company_name: str) -> dict:
    url = f"https://ie.indeed.com/jobs?q={quote(company_name)}"
    html = await fetch(url)
    soup = BeautifulSoup(html, "lxml")
    count = soup.select_one("#searchCountPages")
    return {"open_roles": parse_count(count.text) if count else 0}
```

### 6. EU Grants - CORDIS (VALIDATION SIGNAL)
**Why**: EU grant = technical validation, non-dilutive funding, serious R&D.

**Source**: CORDIS bulk data (free CSV download)
```
https://cordis.europa.eu/data/cordis-HORIZONprojects.csv
```

**How**: Download CSV, filter for Ireland, join on company_name (fuzzy match).

**Output fields**:
- `has_eu_grant` (boolean)
- `eu_grant_amount`
- `eu_project_title`
- `eu_programme` (Horizon Europe, H2020, EIC Accelerator)

EIC Accelerator companies are especially interesting - up to €2.5M grant + €15M equity.

### 7. Enterprise Ireland HPSU (VALIDATION SIGNAL)
**Why**: EI does due diligence. HPSU status = "high potential startup" badge.

**Source**: No public API, but can scrape news/press releases:
- Silicon Republic startup articles
- Enterprise Ireland press releases
- Tech.eu funding announcements

**Alternative**: Check if company has "Enterprise Ireland" in their website/LinkedIn mentions.

**Output fields**:
- `is_ei_client` (boolean)
- `ei_funding_amount` (if found)

### 8. Crunchbase (FUNDING HISTORY)
**Why**: Previous funding rounds, investors, founder backgrounds.

**Source**: Crunchbase API (requires key) or scrape:
```
https://www.crunchbase.com/organization/{company_slug}
```

**Output fields**:
- `total_funding`
- `last_funding_round`
- `last_funding_date`
- `investors` (list)
- `founder_names`

### 9. GitHub Organization (TECH SIGNAL)
**Why**: Open source activity = developer-focused, technical team.

**Source**: GitHub API (free)
```
https://api.github.com/orgs/{org_name}
https://api.github.com/orgs/{org_name}/repos
```

**Output fields**:
- `github_url`
- `public_repos_count`
- `total_stars`
- `primary_language`

---

## NACE Codes (Industry Filtering)

Map NACE to human-readable categories:

```python
NACE_CATEGORIES = {
    "62": "Software & IT",
    "63": "Data & Hosting",
    "58.2": "Software Publishing",
    "64": "Financial Services",
    "66": "FinTech Support",
    "21": "Pharma & Biotech",
    "72": "R&D",
    "26": "Electronics & Hardware",
    "70.2": "Consulting",
    "73": "Marketing & Advertising",
}

TECH_NACE_PREFIXES = ["62", "63", "58.2", "64", "66", "21", "72", "26"]
```

---

## Filters

1. `status == "Normal"`
2. `incorporation_date >= 5 years ago`
3. `total_assets >= 500_000`
4. `company_type in ["LTD", "DAC"]`

Sort by: total_assets desc, then by is_tech desc

---

## Output Schema

```python
@dataclass
class Company:
    # CRO Core
    company_number: str
    company_name: str
    company_type: str
    incorporation_date: date
    registered_address: str
    county: str
    
    # Industry
    nace_code: str
    nace_category: str  # mapped
    is_tech: bool
    
    # Financials
    total_assets: float
    shareholders_funds: float
    turnover: float | None
    profit_loss: float | None
    cash: float | None
    employees: int | None
    
    # Directors
    directors: list[str]
    num_directors: int
    
    # Enrichment - Website
    website_url: str | None
    product_summary: str | None  # LLM one-liner
    product_category: str | None  # SaaS, Fintech, etc.
    
    # Enrichment - Traction
    open_roles_count: int
    is_hiring_engineers: bool
    
    # Enrichment - Validation
    has_eu_grant: bool
    eu_grant_amount: float | None
    is_ei_client: bool
    
    # Enrichment - Funding
    crunchbase_url: str | None
    total_funding: float | None
    last_funding_date: date | None
    
    # Enrichment - Tech
    github_url: str | None
    github_stars: int | None
```

---

## Project Structure

```
ireland-cro-scraper/
├── CLAUDE.md
├── README.md
├── NOTES.md
├── pyproject.toml
├── src/
│   ├── main.py           # orchestrator
│   ├── cro.py            # CRO downloads
│   ├── core.py           # CORE scraper
│   ├── enrich.py         # website, jobs, grants
│   ├── nace.py           # NACE mappings
│   └── app.py            # streamlit
├── data/
│   └── .cache/           # diskcache (TTL 1 day)
└── output/
```

---

## Commands

```bash
uv init ireland-cro-scraper && cd ireland-cro-scraper
uv add aiohttp aiolimiter diskcache beautifulsoup4 lxml polars streamlit pydantic tenacity

uv run python src/main.py          # run scraper
uv run streamlit run src/app.py    # run dashboard
```

---

## Streamlit Dashboard

**Sidebar Filters**:
- Industry category (multi-select)
- Product category (SaaS, Fintech, Biotech, etc.)
- Min assets slider
- Tech only toggle
- Has EU grant toggle
- Is hiring toggle
- Company name search

**Main View**:
- KPI cards: Total, Avg assets, % tech, % hiring
- Data table with: name, product_summary, category, assets, employees, is_hiring
- Click row → detail panel with all fields

**Charts**:
- Bar: Companies by product_category
- Bar: Companies by nace_category
- Scatter: Assets vs Employees (color by category)

---

## Rate Limiting & Caching

Use `aiolimiter` for per-domain rate limiting and `diskcache` for persistent caching with 1-day TTL. This enables:
- Concurrent scraping across domains while respecting rate limits
- Resume from failures without re-fetching cached data
- Skip already-scraped companies on re-runs

```python
from aiolimiter import AsyncLimiter
from diskcache import Cache

cache = Cache("data/.cache")
TTL = 86400  # 1 day

RATE_LIMITS = {
    "core.cro.ie": AsyncLimiter(1, 1),        # 1 req/sec
    "default": AsyncLimiter(1, 2),             # 0.5 req/sec for company websites
    "indeed.com": AsyncLimiter(2, 1),          # 2 req/sec
    "linkedin.com": AsyncLimiter(2, 1),        # 2 req/sec
    "github.com": AsyncLimiter(60, 3600),      # 60 req/hour
}

async def fetch(url: str) -> str | None:
    if url in cache:
        return cache[url]

    domain = urlparse(url).netloc
    limiter = RATE_LIMITS.get(domain, RATE_LIMITS["default"])
    async with limiter:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            text = await resp.text()
            cache.set(url, text, expire=TTL)
            return text
```

---

## Implementation Priority

1. **CRO bulk data** - companies + financials (fast, reliable)
2. **NACE mapping** - instant industry filtering
3. **Website scraping** - highest value enrichment
4. **CORDIS grants** - bulk CSV, easy join
5. **Job postings** - traction signal
6. **CORE directors** - nice to have
7. **Crunchbase/GitHub** - if time permits

---

## Interview Notes

**Why these enrichment sources matter for Series A**:

| Signal | What it tells you |
|--------|-------------------|
| Website/product | What they actually build |
| NACE code | Industry classification |
| Job postings | Growth trajectory |
| EU grants | Technical validation |
| EI HPSU | Irish gov due diligence |
| GitHub | Developer traction |
| Crunchbase | Funding history |

**Blossom cares about**:
- Mission-driven founders
- Product-led/engineering-led teams
- $10bn+ market potential
- Network effects
- Distribution advantage

**CRO data alone tells you**: Company exists, has money, is active.
**Enriched data tells you**: What they build, if they're growing, if they're validated.
