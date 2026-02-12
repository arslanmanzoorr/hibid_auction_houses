"""
HiBid Company List Scraper — Vercel Serverless Endpoint

GET /api/get-company-list?page=1

Scrapes the HiBid company search page and extracts company data
from the server-side rendered HTML table.

The SSR page always renders 100 companies (page 1 of the full dataset).
To access all ~3,025 companies, use the companion /api/get-company-details
endpoint to visit each company's profile page individually.

Returns:
    JSON with list of companies, each containing:
    - name: Company name
    - location: City, State, Country
    - profile_url: Full URL to company's HiBid profile page
    - company_id: Numeric company identifier
"""

from http.server import BaseHTTPRequestHandler
import json
import traceback

from api._lib.scraper import (
    fetch_company_list_from_html,
    fetch_company_list_from_apollo_state,
    build_error_response,
    build_success_response,
)
from api._lib.config import (
    MAX_PAGE_NUMBER,
    DEFAULT_PAGE_SIZE,
    COMPANYSEARCH_URL,
)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for GET /api/get-company-list."""

    def do_GET(self):
        try:
            # Parse query parameters
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            page = int(params.get("page", ["1"])[0])

            if page < 1 or page > MAX_PAGE_NUMBER:
                self._send_json(
                    400,
                    build_error_response(
                        f"Page must be between 1 and {MAX_PAGE_NUMBER}. "
                        f"Note: The SSR page only pre-renders page 1 (~100 companies). "
                        f"Use /api/get-company-details to fetch individual company data."
                    ),
                )
                return

            # Strategy: Parse the SSR HTML table for company list data.
            # The SSR always renders the first ~100 companies alphabetically.
            # We also attempt to parse the Apollo transfer state if available.
            companies = []
            source = "html_table"
            total_count = None

            # Try Apollo state first (richer data)
            apollo_result = fetch_company_list_from_apollo_state(page)
            if apollo_result and apollo_result.get("companies"):
                companies = apollo_result["companies"]
                total_count = apollo_result.get("total_count")
                source = "apollo_state"
            else:
                # Fall back to HTML table parsing
                html_result = fetch_company_list_from_html()
                if html_result:
                    companies = html_result.get("companies", [])

            if not companies:
                self._send_json(
                    502,
                    build_error_response(
                        "Failed to extract company data from HiBid. "
                        "The site structure may have changed."
                    ),
                )
                return

            response = build_success_response(
                data={
                    "page": page,
                    "page_size": len(companies),
                    "total_count": total_count,
                    "source": source,
                    "companies": companies,
                },
                meta={
                    "note": (
                        "The SSR page pre-renders ~100 companies (page 1). "
                        "For all ~3,025 companies, iterate over the returned profile_urls "
                        "using /api/get-company-details with 1-2s delays between calls."
                    )
                },
            )

            self._send_json(200, response)

        except ValueError as e:
            self._send_json(400, build_error_response(f"Invalid parameter: {e}"))
        except Exception as e:
            traceback.print_exc()
            self._send_json(
                500,
                build_error_response(f"Internal server error: {type(e).__name__}"),
            )

    def _send_json(self, status_code: int, data: dict):
        """Send a JSON response with proper headers."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300, s-maxage=600")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
