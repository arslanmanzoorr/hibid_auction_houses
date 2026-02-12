"""
Core scraping logic for extracting company data from HiBid.

Two data extraction strategies:
1. Apollo State — Parse the JSON transfer state embedded in the SSR HTML
   for structured data (preferred, includes address/phone/email).
2. HTML Table — Fall back to parsing the visible <table> element
   (simpler, but only provides name + location + profile URL).

All HTTP requests use proper User-Agent headers and timeout handling.
"""

import json
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from api._lib.config import (
    APOLLO_STATE_KEY,
    APOLLO_STATE_SCRIPT_ID,
    AUCTIONEER_REF_PREFIX,
    COMPANYSEARCH_URL,
    DEFAULT_HEADERS,
    HIBID_BASE_URL,
    REQUEST_TIMEOUT,
    ROOT_QUERY_KEY,
)


# ─── HTTP Layer ──────────────────────────────────────────────────────────────────


def _fetch_page(url: str) -> requests.Response | None:
    """
    Fetch a page with proper headers and timeout handling.

    Returns None on any request failure rather than raising.
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        print(f"[scraper] Timeout fetching {url}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[scraper] Connection error fetching {url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[scraper] HTTP error {e.response.status_code} fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[scraper] Request failed for {url}: {e}")
        return None


def _parse_html(html: str) -> BeautifulSoup:
    """Parse HTML content into a BeautifulSoup tree."""
    return BeautifulSoup(html, "html.parser")


# ─── Apollo State Extraction ────────────────────────────────────────────────────


def _extract_apollo_state(soup: BeautifulSoup) -> dict | None:
    """
    Extract the Apollo transfer state from the SSR HTML.

    HiBid embeds a <script id="hibid-state"> tag containing the
    serialized Apollo cache as JSON. This includes structured data
    for auctioneers, lots, and other entities.
    """
    state_script = soup.find("script", id=APOLLO_STATE_SCRIPT_ID)
    if not state_script or not state_script.string:
        return None

    try:
        state = json.loads(state_script.string)
        return state.get(APOLLO_STATE_KEY)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_auctioneers_from_apollo(apollo_state: dict) -> dict[int, dict]:
    """
    Extract all Auctioneer objects from the Apollo state.

    Returns a dict keyed by company_id with full auctioneer data.
    """
    auctioneers = {}
    for key, value in apollo_state.items():
        if key.startswith(AUCTIONEER_REF_PREFIX) and isinstance(value, dict):
            company_id = value.get("id")
            if company_id:
                auctioneers[company_id] = value
    return auctioneers


def _format_auctioneer(auctioneer: dict) -> dict:
    """
    Format a raw Apollo Auctioneer object into our API response shape.
    """
    company_id = auctioneer.get("id", "")
    name = auctioneer.get("name", "")

    city = auctioneer.get("city", "") or ""
    state = auctioneer.get("state", "") or ""
    postal_code = auctioneer.get("postalCode", "") or ""
    country = auctioneer.get("country", "") or ""
    address = auctioneer.get("address", "") or ""

    # Build location string
    location_parts = [p for p in [city, state, country] if p.strip()]
    location = ", ".join(location_parts)

    # Build slug for profile URL
    slug = _make_slug(name)
    profile_url = f"{HIBID_BASE_URL}/company/{company_id}/{slug}"

    return {
        "company_id": company_id,
        "name": name,
        "location": location,
        "address": address,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": country,
        "profile_url": profile_url,
    }


def _format_auctioneer_detail(auctioneer: dict, profile_url: str = "") -> dict:
    """
    Format a raw Apollo Auctioneer object into the detailed API response.

    Includes phone, email, and website fields not available in the list view.
    """
    base = _format_auctioneer(auctioneer)

    # Add contact details
    base["phone"] = auctioneer.get("phone", "") or ""
    base["email"] = auctioneer.get("email", "") or ""
    base["website"] = auctioneer.get("internetAddress", "") or ""
    base["fax"] = auctioneer.get("fax", "") or ""

    if profile_url:
        base["profile_url"] = profile_url

    return base


# ─── Company List Scraping ───────────────────────────────────────────────────────


def fetch_company_list_from_apollo_state(page: int = 1) -> dict | None:
    """
    Fetch the company list by parsing the Apollo transfer state.

    The SSR pre-renders page 1 with 100 companies. The Apollo state
    contains the full query result with totalCount metadata.

    Note: The SSR always returns the same page regardless of query params.
    Pagination beyond page 1 requires client-side GraphQL which is
    Cloudflare-protected.

    Args:
        page: Page number (only page 1 is available via SSR).

    Returns:
        Dict with 'companies' list and 'total_count', or None on failure.
    """
    response = _fetch_page(COMPANYSEARCH_URL)
    if not response:
        return None

    soup = _parse_html(response.text)
    apollo_state = _extract_apollo_state(soup)

    if not apollo_state:
        return None

    # Extract auctioneer objects
    auctioneers = _extract_auctioneers_from_apollo(apollo_state)
    if not auctioneers:
        return None

    # Get the query result for ordering and total count
    root_query = apollo_state.get(ROOT_QUERY_KEY, {})
    total_count = None
    ordered_ids = []

    for key, value in root_query.items():
        if "auctioneerSearch" in key and isinstance(value, dict):
            total_count = value.get("totalCount")
            results = value.get("results", [])
            for ref in results:
                if isinstance(ref, dict) and "__ref" in ref:
                    ref_key = ref["__ref"]
                    # Extract ID from "Auctioneer:12345"
                    try:
                        aid = int(ref_key.split(":")[1])
                        ordered_ids.append(aid)
                    except (ValueError, IndexError):
                        pass
            break

    # Build company list in original order
    if ordered_ids:
        companies = []
        for aid in ordered_ids:
            auctioneer = auctioneers.get(aid)
            if auctioneer:
                companies.append(_format_auctioneer(auctioneer))
    else:
        # Fallback: unordered
        companies = [_format_auctioneer(a) for a in auctioneers.values()]

    return {
        "companies": companies,
        "total_count": total_count,
    }


def fetch_company_list_from_html() -> dict | None:
    """
    Fetch the company list by parsing the HTML table directly.

    Fallback strategy when Apollo state parsing fails.

    Returns:
        Dict with 'companies' list, or None on failure.
    """
    response = _fetch_page(COMPANYSEARCH_URL)
    if not response:
        return None

    soup = _parse_html(response.text)
    table = soup.find("table", id="companySearch")

    if not table:
        return None

    companies = []
    seen_urls = set()

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header row
        tds = row.find_all("td")
        if len(tds) < 2:
            continue

        link = tds[0].find("a")
        if not link:
            continue

        href = link.get("href", "")
        name = link.get_text(strip=True)
        location = tds[1].get_text(strip=True)

        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Extract company_id from path
        company_id = _extract_company_id_from_path(href)

        # Build full URL
        profile_url = f"{HIBID_BASE_URL}{href}" if href.startswith("/") else href

        companies.append(
            {
                "company_id": company_id,
                "name": name,
                "location": location,
                "profile_url": profile_url,
            }
        )

    return {"companies": companies}


# ─── Company Details Scraping ────────────────────────────────────────────────────


def fetch_company_details(url: str) -> dict | None:
    """
    Fetch detailed company information from a profile page.

    Tries two extraction strategies in order:
    1. Apollo state (from embedded JSON) — structured, includes all fields
    2. HTML parsing (from visible DOM) — fallback, uses regex for phone/email

    Args:
        url: Fully qualified HiBid company profile URL.

    Returns:
        Dict with company details, or None on failure.
    """
    response = _fetch_page(url)
    if not response:
        return None

    soup = _parse_html(response.text)

    # Strategy 1: Apollo state
    details = _extract_details_from_apollo(soup, url)
    if details:
        return details

    # Strategy 2: HTML parsing fallback
    details = _extract_details_from_html(soup, url)
    if details:
        return details

    return None


def _extract_details_from_apollo(soup: BeautifulSoup, url: str) -> dict | None:
    """
    Extract company details from the Apollo transfer state.

    The company detail page embeds a full Auctioneer object in the
    Apollo cache, including phone, email, and website.
    """
    apollo_state = _extract_apollo_state(soup)
    if not apollo_state:
        return None

    # Find the target auctioneer ID from the URL
    target_id = _extract_company_id_from_url(url)

    # Look through all Auctioneer entries
    for key, value in apollo_state.items():
        if not key.startswith(AUCTIONEER_REF_PREFIX):
            continue
        if not isinstance(value, dict):
            continue

        # If we have a target ID, match it; otherwise take any auctioneer
        # that has phone or email (detail-level data)
        auc_id = value.get("id")

        if target_id and auc_id == target_id:
            return _format_auctioneer_detail(value, url)

        # Some pages have multiple auctioneers in the Apollo cache
        # (e.g., from sidebar auctions). We prefer the one matching
        # the target ID, but if we don't have one, pick the one
        # that has contact details (phone/email).
        if not target_id and (value.get("phone") or value.get("email")):
            return _format_auctioneer_detail(value, url)

    # If target_id not found specifically, check ROOT_QUERY for the ref
    root_query = apollo_state.get(ROOT_QUERY_KEY, {})
    for key, value in root_query.items():
        if "auctioneer" in key.lower() and isinstance(value, dict):
            ref = value.get("__ref", "")
            if ref.startswith(AUCTIONEER_REF_PREFIX):
                auctioneer = apollo_state.get(ref)
                if auctioneer and isinstance(auctioneer, dict):
                    return _format_auctioneer_detail(auctioneer, url)

    return None


def _extract_details_from_html(soup: BeautifulSoup, url: str) -> dict | None:
    """
    Extract company details by parsing the visible HTML DOM.

    Fallback strategy when Apollo state is unavailable.
    Extracts data from the .auctioneer-details div and h1 tag.
    """
    # Company name from h1
    h1 = soup.find("h1")
    name = ""
    if h1:
        name = h1.get_text(strip=True)
        # Remove " - Live and Online Auctions" suffix
        name = re.sub(r"\s*-\s*Live and Online Auctions.*$", "", name, flags=re.IGNORECASE)

    # Contact details from .auctioneer-details
    details_div = soup.find("div", class_="auctioneer-details")
    if not details_div and not name:
        return None

    phone = ""
    email = ""
    website = ""
    address = ""
    location = ""

    if details_div:
        details_text = details_div.get_text(separator="\n", strip=True)

        # Extract phone from tel: link
        phone_link = details_div.find("a", href=lambda h: h and h.startswith("tel:"))
        if phone_link:
            phone = phone_link.get_text(strip=True)

        # Extract email from mailto: link
        email_link = details_div.find("a", href=lambda h: h and h.startswith("mailto:"))
        if email_link:
            email = email_link.get_text(strip=True)

        # Extract website link (not tel: or mailto:)
        for link in details_div.find_all("a"):
            href = link.get("href", "")
            if href and not href.startswith(("tel:", "mailto:", "https://maps.google")):
                if "hibid.com" in href or link.get_text(strip=True).endswith(".com"):
                    website = link.get_text(strip=True)
                    break

        # Extract address from map link
        map_link = details_div.find("a", href=lambda h: h and "maps.google" in h)
        if map_link:
            address = map_link.get_text(separator=" ", strip=True)
            location = address  # Full address as location

    company_id = _extract_company_id_from_url(url)

    return {
        "company_id": company_id,
        "name": name,
        "location": location,
        "address": address,
        "city": "",
        "state": "",
        "postal_code": "",
        "country": "",
        "phone": phone,
        "email": email,
        "website": website,
        "fax": "",
        "profile_url": url,
    }


# ─── Utility Functions ──────────────────────────────────────────────────────────


def _make_slug(name: str) -> str:
    """Generate a URL slug from a company name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


def _extract_company_id_from_path(path: str) -> int | None:
    """Extract the numeric company ID from a URL path like /company/12345/slug."""
    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except (ValueError, IndexError):
            pass
    return None


def _extract_company_id_from_url(url: str) -> int | None:
    """Extract the numeric company ID from a full URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return _extract_company_id_from_path(parsed.path)


# ─── Response Builders ──────────────────────────────────────────────────────────


def build_success_response(data: Any, meta: dict | None = None) -> dict:
    """Build a standardized success response."""
    response = {"success": True, "data": data}
    if meta:
        response["meta"] = meta
    return response


def build_error_response(message: str) -> dict:
    """Build a standardized error response."""
    return {"success": False, "error": message}
