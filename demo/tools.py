"""
tools.py — Tool wrappers: the "kitchen equipment" of the agent

ARCHITECTURE CONCEPT:
    Every tool follows the same contract:
    1. Takes typed, validated input (no raw strings from the LLM directly)
    2. Runs safely (these demos use only read-only HTTP requests)
    3. Returns structured output as a dict

    In production, each tool runs inside an EPHEMERAL CONTAINER:
    - Created fresh for each execution
    - Destroyed immediately after
    - Network access restricted to in-scope targets only
    - Cannot access the platform database or other tools

    For this demo, we run them directly in Python to keep it simple,
    but the contract (typed input → structured output) is the same.

TOOLS IN THIS DEMO (all READ_ONLY):
    - http_headers:           Fetch HTTP response headers and basic response info
    - check_security_headers: Analyse which security headers are present/missing
    - find_links:             Parse HTML and find all links and forms
    - dns_lookup:             Resolve a domain to IP addresses
"""

import hashlib
import json
import socket
import time
from typing import Optional
from urllib.parse import urlparse

import httpx

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


# ── Security header definitions ───────────────────────────────────────────────
# Each entry: the header name → what its absence means for security

SECURITY_HEADERS = {
    "X-Frame-Options": {
        "cwe": "CWE-1021",
        "severity": "MEDIUM",
        "description": "Without X-Frame-Options, the site can be embedded in an iframe on a malicious page. "
                       "An attacker tricks a user into clicking something on the legitimate site while actually "
                       "clicking something on the attacker's page underneath (clickjacking).",
        "remediation": "Add: X-Frame-Options: DENY  (or SAMEORIGIN if iframe embedding by same domain is needed)"
    },
    "Content-Security-Policy": {
        "cwe": "CWE-79",
        "severity": "MEDIUM",
        "description": "A missing Content-Security-Policy increases the attack surface for Cross-Site Scripting (XSS). "
                       "CSP lets the server tell the browser which scripts are legitimate, blocking injected scripts.",
        "remediation": "Define a strict CSP header that explicitly allows only trusted script sources."
    },
    "Strict-Transport-Security": {
        "cwe": "CWE-319",
        "severity": "MEDIUM",
        "description": "Without HSTS, browsers may connect over HTTP even when HTTPS is available. "
                       "An attacker on the same network can intercept the initial HTTP request (protocol downgrade).",
        "remediation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
    },
    "X-Content-Type-Options": {
        "cwe": "CWE-430",
        "severity": "LOW",
        "description": "Without this header, browsers may guess the content type (MIME sniffing), "
                       "which can allow content that looks like text to be executed as a script.",
        "remediation": "Add: X-Content-Type-Options: nosniff"
    },
    "Referrer-Policy": {
        "cwe": "CWE-200",
        "severity": "INFO",
        "description": "Without a Referrer-Policy, the full URL (potentially containing sensitive data like "
                       "session tokens or search queries) may be leaked in the Referer header to third parties.",
        "remediation": "Add: Referrer-Policy: strict-origin-when-cross-origin"
    },
}


# ── Tool implementations ──────────────────────────────────────────────────────

def http_headers(url: str) -> dict:
    """
    Fetch HTTP response headers, status code, and basic server info.

    This is like knocking on the front door and noting everything about
    the building before you even step inside.
    """
    try:
        start = time.time()
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "RedfoxAgent/1.0 (security-assessment)"})
        elapsed_ms = round((time.time() - start) * 1000)

        return {
            "success": True,
            "url": str(response.url),              # Final URL after redirects
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "response_time_ms": elapsed_ms,
            "content_length_bytes": len(response.content),
            "error": None,
        }
    except httpx.ConnectError:
        return {"success": False, "error": f"Could not connect to {url}"}
    except httpx.TimeoutException:
        return {"success": False, "error": f"Request to {url} timed out after 15s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_security_headers(url: str) -> dict:
    """
    Analyse the security header configuration of a web server.

    In pen testing, checking security headers is one of the first things
    you do on a web application assessment. Missing headers are real, low-hanging-fruit
    findings that every client report mentions.
    """
    result = http_headers(url)
    if not result.get("success"):
        return result

    response_headers_lower = {k.lower(): v for k, v in result["headers"].items()}

    missing_headers = []
    present_headers = []

    for header_name, info in SECURITY_HEADERS.items():
        if header_name.lower() not in response_headers_lower:
            missing_headers.append({
                "header": header_name,
                "cwe": info["cwe"],
                "severity": info["severity"],
                "description": info["description"],
                "remediation": info["remediation"],
            })
        else:
            present_headers.append({
                "header": header_name,
                "value": response_headers_lower[header_name.lower()],
            })

    # Separate check: server version disclosure
    server_header = result["headers"].get("server", result["headers"].get("Server", ""))
    # Version is disclosed if the header contains a "/" followed by version numbers (e.g. "Apache/2.4.51")
    server_version_disclosed = bool(server_header) and "/" in server_header and any(
        c.isdigit() for c in server_header
    )

    return {
        "success": True,
        "url": url,
        "status_code": result["status_code"],
        "missing_security_headers": missing_headers,
        "present_security_headers": present_headers,
        "server_header": server_header,
        "server_version_disclosed": server_version_disclosed,
        "total_response_headers": len(result["headers"]),
    }


def find_links(url: str) -> dict:
    """
    Fetch the page and extract all hyperlinks and HTML forms.

    Forms are particularly interesting in pen testing — every form is a potential
    injection point (SQLi, XSS, CSRF, etc.).
    """
    if not BS4_AVAILABLE:
        return {"success": False, "error": "beautifulsoup4 not installed. Run: pip install beautifulsoup4"}

    try:
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "RedfoxAgent/1.0 (security-assessment)"})

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract links
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            text = tag.get_text(strip=True)[:60]
            links.append({"href": href, "text": text})

        # Extract forms — these are injection targets
        forms = []
        for form in soup.find_all("form"):
            inputs = []
            for inp in form.find_all(["input", "textarea", "select"]):
                inputs.append({
                    "name": inp.get("name", ""),
                    "type": inp.get("type", "text"),
                })
            forms.append({
                "action": form.get("action", ""),
                "method": form.get("method", "GET").upper(),
                "inputs": inputs,
            })

        # Interesting endpoints (potential attack surface)
        interesting = [
            link for link in links
            if any(kw in link["href"].lower() for kw in
                   ["admin", "login", "auth", "api", "config", "debug", "test", "backup", "upload"])
        ]

        return {
            "success": True,
            "url": url,
            "page_title": soup.title.string.strip() if soup.title else "",
            "links_found": len(links),
            "links": links[:25],   # first 25
            "forms_found": len(forms),
            "forms": forms,
            "interesting_endpoints": interesting,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def dns_lookup(domain: str) -> dict:
    """
    Resolve a domain to its IP addresses.

    Knowing the IP address lets us understand the hosting infrastructure,
    identify CDNs, and potentially find the real origin IP behind a WAF.
    """
    # Strip protocol and path if the full URL was passed
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]

    try:
        addr_info = socket.getaddrinfo(domain, None)
        ip_addresses = sorted(set(info[4][0] for info in addr_info))

        # Basic detection: is this behind a CDN/proxy?
        cdn_indicators = ["cloudflare", "fastly", "akamai", "aws", "azure", "gcp"]
        hostname_lookup = []
        for ip in ip_addresses[:3]:  # reverse DNS for first 3 IPs
            try:
                hostname, _, _ = socket.gethostbyaddr(ip)
                hostname_lookup.append({"ip": ip, "hostname": hostname})
            except socket.herror:
                hostname_lookup.append({"ip": ip, "hostname": None})

        return {
            "success": True,
            "domain": domain,
            "ip_addresses": ip_addresses,
            "reverse_dns": hostname_lookup,
        }
    except socket.gaierror as e:
        return {"success": False, "domain": domain, "error": f"DNS resolution failed: {e}"}


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "http_headers":           http_headers,
    "check_security_headers": check_security_headers,
    "find_links":             find_links,
    "dns_lookup":             dns_lookup,
}


def run_tool(tool_name: str, target: str) -> dict:
    """
    Execute a tool by name with a target.
    Returns structured output or an error dict.
    """
    if tool_name not in TOOL_REGISTRY:
        return {"success": False, "error": f"Tool '{tool_name}' not found in registry"}
    return TOOL_REGISTRY[tool_name](target)
