"""
scope_guard.py — Deterministic, LLM-free scope enforcement

ARCHITECTURE CONCEPT:
    This is the most important safety component in the system.
    It answers ONE question for every proposed action:
        "Is the agent allowed to do this?"

    KEY DESIGN PRINCIPLE:
    The LLM cannot bypass this. The agent's planning role PROPOSES actions.
    This guard DECIDES whether they are allowed.
    They are separate processes. The LLM cannot talk its way past deterministic code.

    In the architecture, this is backed by:
    1. This Python policy engine (logical scope check)
    2. Kubernetes NetworkPolicy (network-level egress control)
    Both must agree before a tool can reach the target.
"""

from enum import Enum
from typing import Tuple
from urllib.parse import urlparse


# ── Risk classification for each tool ────────────────────────────────────────
# READ_ONLY  = passive observation only (safe to auto-approve in autonomous mode)
# INTRUSIVE  = active probing, may appear in logs, not destructive
# DESTRUCTIVE = can cause harm — always requires explicit human approval

class RiskClass(str, Enum):
    READ_ONLY   = "READ_ONLY"
    INTRUSIVE   = "INTRUSIVE"
    DESTRUCTIVE = "DESTRUCTIVE"


class ScopeDecision(str, Enum):
    ALLOW           = "ALLOW"
    DENY            = "DENY"
    NEEDS_APPROVAL  = "NEEDS_APPROVAL"


# Every registered tool must have a risk class.
# If a tool is not registered here, it is DENIED automatically.
TOOL_RISK_REGISTRY: dict[str, RiskClass] = {
    # Read-only reconnaissance tools
    "http_headers":           RiskClass.READ_ONLY,
    "check_security_headers": RiskClass.READ_ONLY,
    "dns_lookup":             RiskClass.READ_ONLY,
    "find_links":             RiskClass.READ_ONLY,
    "whois_lookup":           RiskClass.READ_ONLY,
    "cert_inspection":        RiskClass.READ_ONLY,

    # Intrusive (active) tools — require approval in strict mode
    "port_scan":              RiskClass.INTRUSIVE,
    "directory_bruteforce":   RiskClass.INTRUSIVE,
    "auth_testing":           RiskClass.INTRUSIVE,
    "sql_injection_test":     RiskClass.INTRUSIVE,

    # Destructive — always require explicit human approval
    "exploit_execution":      RiskClass.DESTRUCTIVE,
    "file_write":             RiskClass.DESTRUCTIVE,
    "service_disruption":     RiskClass.DESTRUCTIVE,
}

_RISK_ORDER = {
    RiskClass.READ_ONLY:   0,
    RiskClass.INTRUSIVE:   1,
    RiskClass.DESTRUCTIVE: 2,
}


class ScopeGuard:
    """
    The policy engine. Instantiated per engagement with the engagement's scope rules.

    Usage:
        guard = ScopeGuard(allowed_targets=["http://app.acme.com"], max_risk=RiskClass.READ_ONLY)
        decision, reason = guard.check("http_headers", "http://app.acme.com")
        # → (ScopeDecision.ALLOW, "Tool is READ_ONLY — auto-approved")
    """

    def __init__(
        self,
        allowed_targets: list[str],
        max_risk_class: RiskClass = RiskClass.READ_ONLY,
    ):
        self.allowed_targets = allowed_targets
        self.max_risk_class = max_risk_class

    def check(self, tool_name: str, target: str) -> Tuple[ScopeDecision, str]:
        """
        Validate a proposed action.
        Returns (decision, human-readable reason).

        This function has NO LLM involvement. It is pure deterministic logic.
        """

        # Rule 1: Is the target in scope?
        if not self._target_in_scope(target):
            return (
                ScopeDecision.DENY,
                f"Target '{target}' is NOT in the approved scope — action blocked"
            )

        # Rule 2: Is the tool registered?
        if tool_name not in TOOL_RISK_REGISTRY:
            return (
                ScopeDecision.DENY,
                f"Tool '{tool_name}' is not registered in the tool registry — action blocked"
            )

        tool_risk = TOOL_RISK_REGISTRY[tool_name]

        # Rule 3: Destructive tools always need explicit approval
        if tool_risk == RiskClass.DESTRUCTIVE:
            return (
                ScopeDecision.NEEDS_APPROVAL,
                f"Tool '{tool_name}' is DESTRUCTIVE — always requires human approval"
            )

        # Rule 4: Is the tool's risk class within the engagement's maximum?
        if _RISK_ORDER[tool_risk] > _RISK_ORDER[self.max_risk_class]:
            return (
                ScopeDecision.NEEDS_APPROVAL,
                f"Tool '{tool_name}' is {tool_risk.value} but engagement max is "
                f"{self.max_risk_class.value} — requires human approval"
            )

        # All checks passed
        return (
            ScopeDecision.ALLOW,
            f"Tool '{tool_name}' is {tool_risk.value} — auto-approved"
        )

    def _target_in_scope(self, target: str) -> bool:
        """
        Check if `target` falls within any of the allowed targets.
        Supports exact URL match, domain match, and prefix match.
        """
        parsed_target = urlparse(target)
        target_host = parsed_target.netloc or parsed_target.path.split("/")[0]

        for allowed in self.allowed_targets:
            parsed_allowed = urlparse(allowed)
            allowed_host = parsed_allowed.netloc or parsed_allowed.path.split("/")[0]

            # Exact host match
            if target_host == allowed_host:
                return True
            # Prefix match (e.g. target is a subpath of an allowed URL)
            if target.startswith(allowed):
                return True
            # Bare domain match (scope defined without protocol)
            if target_host == allowed:
                return True

        return False
