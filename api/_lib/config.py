"""
Configuration constants for the HiBid scraper.

All configurable values are centralized here — no hardcoded values
in the scraping or handler modules.
"""

# ─── Target URLs ────────────────────────────────────────────────────────────────
HIBID_BASE_URL = "https://hibid.com"
COMPANYSEARCH_URL = f"{HIBID_BASE_URL}/companysearch"
COMPANY_PROFILE_PATH_PREFIX = "/company/"

# ─── Request Settings ───────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 15  # seconds
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ─── Pagination ──────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_NUMBER = 31  # ~3,025 companies / 100 per page

# ─── Apollo State ────────────────────────────────────────────────────────────────
APOLLO_STATE_SCRIPT_ID = "hibid-state"
APOLLO_STATE_KEY = "apollo.state"
AUCTIONEER_REF_PREFIX = "Auctioneer:"
ROOT_QUERY_KEY = "ROOT_QUERY"

# ─── Security ───────────────────────────────────────────────────────────────────
ALLOWED_DOMAINS = ["hibid.com", "www.hibid.com"]
