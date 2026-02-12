"""
HiBid Company Details Scraper — Vercel Serverless Endpoint

GET /api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction

Visits a company's HiBid profile page and extracts contact details
from the Apollo transfer state embedded in the SSR HTML.

Returns:
    JSON with company details:
    - name: Company name
    - location: Full formatted location string
    - address: Street address
    - city: City name
    - state: State/Province code
    - postal_code: ZIP/Postal code
    - country: Country name
    - phone: Phone number
    - email: Email address
    - website: Company website URL
    - profile_url: HiBid profile URL
"""

from http.server import BaseHTTPRequestHandler
import json
import traceback

from api._lib.scraper import (
    fetch_company_details,
    build_error_response,
    build_success_response,
)
from api._lib.security import validate_url


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for GET /api/get-company-details."""

    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            raw_url = params.get("url", [None])[0]

            if not raw_url:
                self._send_json(
                    400,
                    build_error_response(
                        "Missing required 'url' parameter. "
                        "Example: /api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction"
                    ),
                )
                return

            # Validate and normalize the URL
            validated_url = validate_url(raw_url)
            if not validated_url:
                self._send_json(
                    400,
                    build_error_response(
                        "Invalid URL. Must be a HiBid company profile path "
                        "(e.g., /company/133721/slug) or full hibid.com URL."
                    ),
                )
                return

            # Fetch and parse company details
            details = fetch_company_details(validated_url)

            if not details:
                self._send_json(
                    502,
                    build_error_response(
                        "Failed to extract company details from the profile page. "
                        "The page may not exist or the site structure may have changed."
                    ),
                )
                return

            self._send_json(200, build_success_response(data=details))

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
        self.send_header("Cache-Control", "public, max-age=600, s-maxage=1800")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
