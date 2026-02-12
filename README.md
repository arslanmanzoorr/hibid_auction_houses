# HiBid Auction House Scraper API

A minimal, serverless Python API designed for **Vercel deployment** that scrapes company data from [HiBid.com](https://hibid.com/companysearch).

## Architecture

```
├── api/
│   ├── _lib/                    # Shared modules (not exposed as endpoints)
│   │   ├── __init__.py
│   │   ├── config.py            # Centralized configuration constants
│   │   ├── scraper.py           # Core scraping logic (Apollo state + HTML fallback)
│   │   └── security.py          # SSRF prevention & URL validation
│   ├── get_company_list.py      # GET /api/get-company-list
│   └── get_company_details.py   # GET /api/get-company-details
├── requirements.txt             # requests, beautifulsoup4
├── vercel.json                  # Route & build configuration
├── test_local.py                # Local test harness
└── README.md
```

## Endpoints

### `GET /api/get-company-list?page=1`

Scrapes the HiBid company search page and extracts company data from the **Apollo transfer state** embedded in the server-side rendered HTML.

**Response:**
```json
{
  "success": true,
  "data": {
    "page": 1,
    "page_size": 100,
    "total_count": 3025,
    "source": "apollo_state",
    "companies": [
      {
        "company_id": 133721,
        "name": "0% Buyers Premium Coin Auction",
        "location": "Wichita, KS, United States",
        "address": "11310 E 21st St North",
        "city": "Wichita",
        "state": "KS",
        "postal_code": "67206",
        "country": "United States",
        "profile_url": "https://hibid.com/company/133721/0-buyers-premium-coin-auction"
      }
    ]
  }
}
```

### `GET /api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction`

Visits a company's profile page and extracts contact details.

**Response:**
```json
{
  "success": true,
  "data": {
    "company_id": 133721,
    "name": "0% Buyers Premium Coin Auction",
    "location": "Wichita, KS, United States",
    "address": "11310 E 21st St North",
    "city": "Wichita",
    "state": "KS",
    "postal_code": "67206",
    "country": "United States",
    "phone": "316-530-5660",
    "email": "nobuyerspremium@gmail.com",
    "website": "ZeroBP.hibid.com",
    "fax": "",
    "profile_url": "https://hibid.com/company/133721/0--buyers-premium-coin-auction"
  }
}
```

## How It Works

### Data Extraction Strategy

HiBid is an **Angular SSR application** that embeds an **Apollo GraphQL transfer state** (`<script id="hibid-state">`) in the server-rendered HTML. This scraper leverages this embedded JSON rather than brittle DOM selectors.

| Strategy | Source | Data Completeness |
|----------|--------|-------------------|
| **Apollo State** (primary) | `<script id="hibid-state">` JSON | Full: name, address, city, state, zip, country, phone, email |
| **HTML Table** (fallback) | `<table id="companySearch">` | Basic: name, location, profile URL |
| **HTML Detail** (fallback) | `.auctioneer-details` div | Full: via regex extraction |

### Important: SSR Pagination Limitation

The SSR page always pre-renders **the first 100 companies** (page 1, alphabetically sorted). HiBid's Angular app handles pagination via a **GraphQL endpoint** (`/graphql`) that is **protected by Cloudflare WAF** and blocks direct API calls.

**To get all ~3,025 companies**, use this strategy:

1. Call `/api/get-company-list` to get the first 100 companies with their `profile_url` values
2. For each company, call `/api/get-company-details?url=<profile_url>` to get full contact details
3. The `total_count` in the response tells you there are ~3,025 companies total

## Security

- **SSRF Prevention**: URLs are validated against an allowlist of HiBid domains, private/loopback IPs are blocked via DNS resolution
- **Domain Allowlist**: Only `hibid.com` and `www.hibid.com` are permitted
- **Scheme Enforcement**: Only `http://` and `https://` schemes are allowed
- **Path Validation**: Only `/company/{id}/{slug}` paths are accepted

## Rate Limiting Strategy (for n8n / automation)

> **Slow is smooth. Smooth is fast.**

If you're calling `/api/get-company-details` for all ~3,025 companies:

- **Add 1–2 second delay** between calls
- **Batch 50 at a time**, then wait 30 seconds
- **Run state-wise** over days for large-scale extraction
- HiBid **will rate-limit** aggressive scraping

## Local Testing

```bash
pip install requests beautifulsoup4
python test_local.py
```

## Deployment

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

## Tech Stack

- **Python 3.11+**
- **requests** — HTTP client
- **BeautifulSoup4** — HTML parsing
- **Vercel Python Runtime** — Serverless deployment
