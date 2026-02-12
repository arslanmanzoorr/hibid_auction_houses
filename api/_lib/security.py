"""
SSRF protection and URL validation for the HiBid scraper.

Prevents:
- Requests to localhost / 127.0.0.1 / ::1
- Requests to private IP ranges (10.x, 172.16-31.x, 192.168.x)
- Requests to non-HiBid domains
- Requests to non-HTTP(S) schemes
"""

import ipaddress
import socket
from urllib.parse import urlparse

from api._lib.config import ALLOWED_DOMAINS, HIBID_BASE_URL, COMPANY_PROFILE_PATH_PREFIX


def validate_url(raw_url: str) -> str | None:
    """
    Validate and normalize a company profile URL.

    Accepts:
        - Relative paths: /company/133721/slug-name
        - Full URLs: https://hibid.com/company/133721/slug-name

    Returns:
        Fully qualified, validated URL or None if invalid.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    raw_url = raw_url.strip()

    # Handle relative paths
    if raw_url.startswith(COMPANY_PROFILE_PATH_PREFIX):
        full_url = f"{HIBID_BASE_URL}{raw_url}"
    elif raw_url.startswith("http://") or raw_url.startswith("https://"):
        full_url = raw_url
    else:
        return None

    # Parse and validate the URL
    parsed = urlparse(full_url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        return None

    # Domain check — only allow HiBid domains
    hostname = parsed.hostname
    if not hostname:
        return None

    hostname_lower = hostname.lower()
    if hostname_lower not in ALLOWED_DOMAINS:
        return None

    # Path check — must be a company profile
    if not parsed.path.startswith(COMPANY_PROFILE_PATH_PREFIX):
        return None

    # Ensure the path has at least the company ID segment
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        return None

    # Verify company ID is numeric
    try:
        int(path_parts[1])
    except (ValueError, IndexError):
        return None

    # Block private/loopback IPs via DNS resolution
    if _is_private_host(hostname_lower):
        return None

    # Reconstruct clean URL (strips query strings and fragments for safety)
    clean_url = f"https://{hostname_lower}{parsed.path}"
    return clean_url


def _is_private_host(hostname: str) -> bool:
    """
    Check if the hostname resolves to a private or loopback IP address.

    This prevents SSRF attacks that use DNS rebinding or hostnames
    pointing to internal network addresses.
    """
    # Quick check for obvious loopback names
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True

    try:
        # Resolve the hostname to check the actual IP
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return True
    except (socket.gaierror, ValueError, OSError):
        # If DNS resolution fails, block the request to be safe
        return True

    return False
