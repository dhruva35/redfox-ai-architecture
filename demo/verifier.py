"""
verifier.py — The Independent Verifier

ARCHITECTURE CONCEPT:
    The verifier is the platform's defence against hallucinated findings
    and false positives.

    KEY DESIGN PRINCIPLE — ISOLATION:
    The verifier receives ONLY:
    1. The claim (what the suspected finding is)
    2. The evidence bundle (raw tool output)

    It does NOT receive:
    - The agent's reasoning chain
    - The conversation history
    - The agent's confidence or explanation

    This isolation means the verifier must independently confirm the finding
    through its OWN test. It cannot be "talked into" agreeing with the agent.

    HOW IT WORKS IN THIS DEMO:
    The agent finds a suspected vulnerability (e.g., "X-Frame-Options missing").
    The verifier makes its own independent HTTP request (with a different User-Agent
    to avoid cache hits) and checks for itself whether the header is missing.
    Only if the verifier independently confirms → status = CONFIRMED.

    WHY THIS MATTERS:
    LLMs can hallucinate. Without verification, the agent might claim
    "X-Frame-Options is missing" when it's actually present (because the LLM
    misread the headers). The verifier catches this because it checks independently.

    EVIDENCE HASHING:
    Every piece of evidence is SHA-256 hashed. The hash is stored in the finding record.
    If the evidence file is later modified, the hash mismatch is detectable.
    This is the "chain of custody" for a professional pen test report.
"""

import hashlib
import json
import time
from typing import Optional

import httpx


class Verifier:
    """
    The independent verification process.

    In production, this runs as a completely separate Cloud Run service.
    It has no shared memory with the Agent Core — it communicates only through
    a well-defined interface (claim + evidence bundle).
    """

    def verify(self, finding: dict) -> dict:
        """
        Independently verify a suspected finding.

        Args:
            finding: The suspected finding dict, containing at minimum:
                     - title: what the finding claims
                     - evidence: dict with url and type fields

        Returns:
            dict with:
                - verdict: "CONFIRMED" | "REJECTED" | "NEEDS_HUMAN_REVIEW"
                - confidence: float 0.0-1.0
                - reasoning: explanation of the verdict
                - evidence: the verifier's own evidence
                - evidence_hash: SHA-256 hash of the evidence (for chain of custody)
        """
        title_lower = finding.get("title", "").lower()
        evidence = finding.get("evidence", {})
        url = evidence.get("url", "")

        # Route to the correct verification strategy based on finding type
        if "x-frame-options" in title_lower:
            return self._verify_missing_header(url, "X-Frame-Options")

        elif "content-security-policy" in title_lower:
            return self._verify_missing_header(url, "Content-Security-Policy")

        elif "strict-transport-security" in title_lower:
            return self._verify_missing_header(url, "Strict-Transport-Security")

        elif "x-content-type-options" in title_lower:
            return self._verify_missing_header(url, "X-Content-Type-Options")

        elif "referrer-policy" in title_lower:
            return self._verify_missing_header(url, "Referrer-Policy")

        elif "server version" in title_lower or "version disclosure" in title_lower:
            return self._verify_server_disclosure(url)

        elif "link" in title_lower or "form" in title_lower or "endpoint" in title_lower:
            # For discovered attack surface — confirm URL is reachable
            return self._verify_url_reachable(url)

        else:
            # Cannot auto-verify — requires a human to look at it
            return self._needs_human_review(
                f"No automated verification strategy for finding type: '{finding.get('title')}'"
            )

    # ── Verification strategies ───────────────────────────────────────────────

    def _verify_missing_header(self, url: str, header_name: str) -> dict:
        """
        Independently re-fetch the URL and check for the header.
        Uses a different User-Agent than the main agent to avoid cache artifacts.
        """
        if not url:
            return self._needs_human_review("No URL provided in evidence")

        try:
            # INDEPENDENT request — different User-Agent, different timing
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={"User-Agent": "RedfoxVerifier/1.0 (independent-verification)"}
                )

            headers_lower = {k.lower(): v for k, v in response.headers.items()}
            is_missing = header_name.lower() not in headers_lower

            verifier_evidence = {
                "verification_url": url,
                "verification_method": "independent_http_get",
                "user_agent": "RedfoxVerifier/1.0 (independent-verification)",
                "response_status": response.status_code,
                "header_checked": header_name,
                "header_found_in_response": not is_missing,
                "all_response_headers": dict(response.headers),
            }
            evidence_hash = self._hash_evidence(verifier_evidence)

            if is_missing:
                return {
                    "verdict": "CONFIRMED",
                    "confidence": 0.95,
                    "reasoning": (
                        f"Independent verification confirms: '{header_name}' is absent from the response. "
                        f"Checked via separate HTTP GET with different User-Agent to rule out caching. "
                        f"Response status: {response.status_code}."
                    ),
                    "evidence": verifier_evidence,
                    "evidence_hash": evidence_hash,
                }
            else:
                return {
                    "verdict": "REJECTED",
                    "confidence": 0.95,
                    "reasoning": (
                        f"FALSE POSITIVE: '{header_name}' IS present in the response. "
                        f"Value: '{headers_lower[header_name.lower()]}'. "
                        f"The original agent's report was incorrect."
                    ),
                    "evidence": verifier_evidence,
                    "evidence_hash": evidence_hash,
                }

        except Exception as e:
            return self._needs_human_review(f"Verification request failed: {e}")

    def _verify_server_disclosure(self, url: str) -> dict:
        """Verify server version disclosure via independent request."""
        if not url:
            return self._needs_human_review("No URL provided in evidence")

        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={"User-Agent": "RedfoxVerifier/1.0 (independent-verification)"}
                )

            server_header = response.headers.get("server", response.headers.get("Server", ""))
            version_disclosed = bool(server_header) and "/" in server_header and any(
                c.isdigit() for c in server_header
            )

            verifier_evidence = {
                "verification_url": url,
                "server_header_value": server_header,
                "version_detected": version_disclosed,
            }
            evidence_hash = self._hash_evidence(verifier_evidence)

            if version_disclosed:
                return {
                    "verdict": "CONFIRMED",
                    "confidence": 0.92,
                    "reasoning": (
                        f"Server version disclosure confirmed independently. "
                        f"Header value: 'Server: {server_header}'. "
                        f"This reveals the server software and version to potential attackers."
                    ),
                    "evidence": verifier_evidence,
                    "evidence_hash": evidence_hash,
                }
            else:
                return {
                    "verdict": "REJECTED",
                    "confidence": 0.90,
                    "reasoning": (
                        f"Server header does not disclose version in independent request. "
                        f"Header value: '{server_header or '(not present)'}'"
                    ),
                    "evidence": verifier_evidence,
                    "evidence_hash": evidence_hash,
                }

        except Exception as e:
            return self._needs_human_review(f"Verification request failed: {e}")

    def _verify_url_reachable(self, url: str) -> dict:
        """Verify a discovered URL is actually reachable."""
        if not url:
            return self._needs_human_review("No URL provided in evidence")

        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.head(url)  # HEAD request — minimal bandwidth

            verifier_evidence = {"url": url, "status_code": response.status_code}
            evidence_hash = self._hash_evidence(verifier_evidence)

            return {
                "verdict": "CONFIRMED",
                "confidence": 0.80,
                "reasoning": f"URL is reachable. Status: {response.status_code}.",
                "evidence": verifier_evidence,
                "evidence_hash": evidence_hash,
            }
        except Exception as e:
            return self._needs_human_review(f"Could not reach URL: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _needs_human_review(self, reason: str) -> dict:
        """Return a NEEDS_HUMAN_REVIEW verdict when automated verification is not possible."""
        return {
            "verdict": "NEEDS_HUMAN_REVIEW",
            "confidence": 0.0,
            "reasoning": f"Automated verification not conclusive. Reason: {reason}. A human tester must review this finding.",
            "evidence": {},
            "evidence_hash": "",
        }

    def _hash_evidence(self, evidence: dict) -> str:
        """
        SHA-256 hash of the evidence bundle.
        Stored in the finding record for chain of custody.
        If the evidence is later tampered with, the hash will not match.
        """
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        return hashlib.sha256(evidence_json.encode()).hexdigest()[:16]
