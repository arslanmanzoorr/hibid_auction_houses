"""
HiBid Company List Scraper — Vercel Serverless Endpoint (Flask)

GET /api/get-company-list?page=1

Scrapes the HiBid company search page and extracts company data
from the server-side rendered Apollo transfer state.
"""

from flask import Flask, request, jsonify
import traceback

from api._lib.scraper import (
    fetch_company_list_from_apollo_state,
    fetch_company_list_from_html,
    build_error_response,
    build_success_response,
)
from api._lib.config import MAX_PAGE_NUMBER

app = Flask(__name__)


@app.route("/api/get-company-list", methods=["GET"])
def get_company_list():
    try:
        page = request.args.get("page", 1, type=int)

        if page < 1 or page > MAX_PAGE_NUMBER:
            return jsonify(
                build_error_response(
                    f"Page must be between 1 and {MAX_PAGE_NUMBER}. "
                    f"Note: The SSR page only pre-renders page 1 (~100 companies). "
                    f"Use /api/get-company-details to fetch individual company data."
                )
            ), 400

        # Try Apollo state first (richer data)
        companies = []
        source = "html_table"
        total_count = None

        apollo_result = fetch_company_list_from_apollo_state(page)
        if apollo_result and apollo_result.get("companies"):
            companies = apollo_result["companies"]
            total_count = apollo_result.get("total_count")
            source = "apollo_state"
        else:
            html_result = fetch_company_list_from_html()
            if html_result:
                companies = html_result.get("companies", [])

        if not companies:
            return jsonify(
                build_error_response(
                    "Failed to extract company data from HiBid. "
                    "The site structure may have changed."
                )
            ), 502

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

        resp = jsonify(response)
        resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=600"
        return resp, 200

    except ValueError as e:
        return jsonify(build_error_response(f"Invalid parameter: {e}")), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify(build_error_response(f"Internal server error: {type(e).__name__}")), 500
