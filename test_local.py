"""
Local test server for the HiBid scraper API.

Run with: python test_local.py
Then visit:
    http://localhost:8000/api/get-company-list?page=1
    http://localhost:8000/api/get-company-details?url=/company/133721/0--buyers-premium-coin-auction
"""

import sys
import os
import json

# Add project root to path so imports work locally
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_company_list():
    """Test the company list scraper directly."""
    print("=" * 60)
    print("TESTING: Company List (Apollo State)")
    print("=" * 60)

    from api._lib.scraper import fetch_company_list_from_apollo_state

    result = fetch_company_list_from_apollo_state(page=1)

    if result:
        companies = result.get("companies", [])
        total = result.get("total_count")
        print(f"  Total companies on platform: {total}")
        print(f"  Companies fetched (page 1): {len(companies)}")
        if companies:
            print(f"\n  First company:")
            print(f"    {json.dumps(companies[0], indent=4)}")
            print(f"\n  Last company:")
            print(f"    {json.dumps(companies[-1], indent=4)}")
    else:
        print("  FAILED: No data returned")

    print()


def test_company_list_html():
    """Test the HTML fallback scraper."""
    print("=" * 60)
    print("TESTING: Company List (HTML Table Fallback)")
    print("=" * 60)

    from api._lib.scraper import fetch_company_list_from_html

    result = fetch_company_list_from_html()

    if result:
        companies = result.get("companies", [])
        print(f"  Companies fetched: {len(companies)}")
        if companies:
            print(f"\n  First company:")
            print(f"    {json.dumps(companies[0], indent=4)}")
    else:
        print("  FAILED: No data returned")

    print()


def test_company_details():
    """Test the company details scraper."""
    print("=" * 60)
    print("TESTING: Company Details")
    print("=" * 60)

    from api._lib.scraper import fetch_company_details
    from api._lib.security import validate_url

    test_urls = [
        "/company/133721/0--buyers-premium-coin-auction",
        "https://hibid.com/company/86903/105-auction-gallery",
    ]

    for raw_url in test_urls:
        print(f"\n  URL: {raw_url}")
        validated = validate_url(raw_url)
        if not validated:
            print("    FAILED: URL validation")
            continue

        print(f"  Validated: {validated}")
        details = fetch_company_details(validated)
        if details:
            print(f"    {json.dumps(details, indent=4)}")
        else:
            print("    FAILED: No details returned")

    print()


def test_security():
    """Test SSRF prevention."""
    print("=" * 60)
    print("TESTING: SSRF Prevention")
    print("=" * 60)

    from api._lib.security import validate_url

    test_cases = [
        ("/company/133721/slug", True, "Valid relative path"),
        ("https://hibid.com/company/133721/slug", True, "Valid full URL"),
        ("https://evil.com/company/133721/slug", False, "Wrong domain"),
        ("http://localhost/company/133721/slug", False, "Localhost"),
        ("http://127.0.0.1/company/133721/slug", False, "Loopback IP"),
        ("http://192.168.1.1/company/133721/slug", False, "Private IP"),
        ("ftp://hibid.com/company/133721/slug", False, "Wrong scheme"),
        ("/admin/secret", False, "Not a company path"),
        ("", False, "Empty string"),
        (None, False, "None"),
    ]

    for url, should_pass, description in test_cases:
        result = validate_url(url)
        passed = (result is not None) == should_pass
        status = "PASS" if passed else "FAIL"
        print(f"  {status} {description}: {url} -> {result}")

    print()


if __name__ == "__main__":
    print("\nHiBid Scraper API — Local Tests\n")

    test_security()
    test_company_list()
    test_company_list_html()
    test_company_details()

    print("Done!")
