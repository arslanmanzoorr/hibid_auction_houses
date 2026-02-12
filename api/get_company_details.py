"""
HiBid Company Details Scraper — Vercel Serverless Endpoint (Flask)

GET /api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction

Visits a company's HiBid profile page and extracts contact details
from the Apollo transfer state embedded in the SSR HTML.
"""

from flask import Flask, request, jsonify
import traceback

from api._lib.scraper import (
    fetch_company_details,
    build_error_response,
    build_success_response,
)
from api._lib.security import validate_url

app = Flask(__name__)


@app.route("/api/get-company-details", methods=["GET"])
def get_company_details():
    try:
        raw_url = request.args.get("url")

        if not raw_url:
            return jsonify(
                build_error_response(
                    "Missing required 'url' parameter. "
                    "Example: /api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction"
                )
            ), 400

        # Validate and normalize the URL (SSRF protection)
        validated_url = validate_url(raw_url)
        if not validated_url:
            return jsonify(
                build_error_response(
                    "Invalid URL. Must be a HiBid company profile path "
                    "(e.g., /company/133721/slug) or full hibid.com URL."
                )
            ), 400

        # Fetch and parse company details
        details = fetch_company_details(validated_url)

        if not details:
            return jsonify(
                build_error_response(
                    "Failed to extract company details from the profile page. "
                    "The page may not exist or the site structure may have changed."
                )
            ), 502

        resp = jsonify(build_success_response(data=details))
        resp.headers["Cache-Control"] = "public, max-age=600, s-maxage=1800"
        return resp, 200

    except ValueError as e:
        return jsonify(build_error_response(f"Invalid parameter: {e}")), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify(build_error_response(f"Internal server error: {type(e).__name__}")), 500
