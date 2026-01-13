# Ireland CRO Company Screener

Investment opportunity screener for Irish companies, built for Series A deal sourcing.

## Data Pipeline

### 1. Company Registry (CRO)
**Source:** opendata.cro.ie bulk download (~805k companies)

**Fields obtained:**
- Company name, number, type (LTD, DAC, etc.)
- Registration date
- Registered address, Eircode
- NACE code (industry classification)

**Filtering applied:**
- Status: Normal (active companies only)
- Incorporated: Last 5 years
- Type: LTD or DAC (excludes sole traders, partnerships)
- Result: ~107k companies

**Deal sourcing value:** Provides the universe of potential targets. Registration date identifies early-stage companies (Series A sweet spot). Address shows Dublin tech hub concentration vs regional players.

### 2. Industry Classification (NACE)
**Source:** NACE code mapping

**Fields derived:**
- Industry category (Software & IT, Financial Services, Healthcare, etc.)
- Tech company flag (software, data, telecom sectors)
- Result: ~24k tech companies identified

**Deal sourcing value:** Enables sector-focused screening. Quickly filter to software/SaaS companies or specific verticals (fintech, healthtech). NACE codes are self-reported so useful for initial triage but not definitive.

### 3. EU Grants (CORDIS Horizon)
**Source:** cordis.europa.eu JSON API (auto-downloaded)

**Fields obtained:**
- Grant amount (EC contribution)
- Project acronym
- Has EU grant flag

**Matching:** Company name normalization (strips LTD/DAC suffixes)

**Deal sourcing value:** EU grant recipients have passed rigorous technical review - strong signal for deep tech and R&D-heavy companies. Grant amount indicates project scale. Horizon Europe focuses on breakthrough innovation.

### 4. Deep Research (Tongyi DeepResearch)
**Source:** Tongyi DeepResearch via OpenRouter API

**Applied to:** Top 100 software/IT companies

**Fields obtained:**
- Investment memo (markdown report covering company overview, market, technology, team, funding, competitive landscape)
- Industry & sub-industry
- Business model (B2B/B2C)
- Company stage (Seed/Series A/Growth)
- Key people
- Funding total
- Employee count
- Founded year
- Investment verdict (Promising/Maybe/Pass) with reasoning

**Cost:** ~$0.0016 per company

**Deal sourcing value:** Automates the initial research phase. Verdict and reasoning enable quick triage. Founder backgrounds, funding history, and competitive positioning inform outreach priority. Replaces hours of manual Googling per company.

**Note:** Perplexity Sonar Deep Research produces significantly better results (more detailed, accurate research with citations) but costs ~$1 per company and takes 60-90s per query. Tongyi was chosen for this exercise due to cost, but Sonar would be worth it in production.

## Data Not Available

### Company Directors (CORE)
**Source:** core.cro.ie
**Status:** Blocked by Cloudflare Turnstile captcha
**Workaround needed:** Captcha-solving service or manual session

**Would provide:** Director names, appointments, resignations. Useful for identifying serial founders, tracking team changes, and finding warm intro paths.

### Job Postings
**Source:** Indeed, LinkedIn
**Status:** Blocked (403 responses)
**Workaround needed:** Browser automation or API access

**Would provide:** Open roles, hiring velocity. Strong signal for growth stage and runway - companies hiring aggressively are scaling.

## Usage

```bash
# Run pipeline
uv run python -m src.main

# View dashboard
uv run streamlit run src/app.py
```

## Environment Variables

```bash
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_API_KEY="your-openrouter-key"
```
