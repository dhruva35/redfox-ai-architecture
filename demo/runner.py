"""
runner.py — Assessment Runner with Real-Time Event Dispatching

Acts as the bridge between the Core Agent (LangGraph/methodology) and the
Web UI Dashboard (FastAPI SSE/WebSockets). Emits fine-grained telemetry
for every phase of the 5-layer Redfox AI Architecture:
  Layer 1: Scope & Target definition
  Layer 2: Plan-Act-Observe-Reflect core cycle
  Layer 3: Independent verification & SHA-256 evidence chain of custody
  Layer 4: Sandboxed tool execution & container telemetry
  Layer 5: Methodology rules & finding lifecycle
"""

import hashlib
import json
import logging
import os
import queue
import threading
import time
from typing import Callable, Optional, Dict, Any, List
from urllib.parse import urlparse

from scope_guard import RiskClass, ScopeDecision, ScopeGuard
from state import AgentState
from tools import run_tool
from verifier import Verifier

logger = logging.getLogger("redfox.runner")

# Predefined scripted plan fallback
SCRIPTED_PLAN = [
    {"tool": "check_security_headers", "objective": "Analyze HTTP response headers for missing security baselines (CSP, HSTS, X-Frame-Options)"},
    {"tool": "http_headers",           "objective": "Inspect server banner, technology stack disclosures, and redirect chains"},
    {"tool": "find_links",             "objective": "Crawl target HTML to enumerate attack surface links, forms, and hidden parameters"},
    {"tool": "dns_lookup",             "objective": "Resolve canonical DNS records, multi-homed IP addresses, and reverse PTR lookups"},
]

def scripted_reflect(tool_name: str, tool_output: dict, target: str) -> list[dict]:
    """Rule-based reflection mapping raw tool output to suspected claims."""
    findings = []
    if tool_name == "check_security_headers":
        for h in tool_output.get("missing_security_headers", []):
            findings.append({
                "title": f"Missing {h['header']} Header",
                "description": h["description"],
                "severity": h["severity"],
                "cwe_id": h["cwe"],
                "evidence": {
                    "url": target,
                    "missing_header": h["header"],
                    "type": "missing_security_header"
                },
                "remediation": h.get("remediation", f"Configure {h['header']} on the web server.")
            })
        if tool_output.get("server_version_disclosed"):
            findings.append({
                "title": "Server Banner Information Disclosure",
                "description": (
                    f"The 'Server' response header discloses backend technology: "
                    f"'{tool_output.get('server_header')}'. "
                    f"Adversaries utilize detailed version headers to cross-reference known CVE vulnerabilities."
                ),
                "severity": "LOW",
                "cwe_id": "CWE-200",
                "evidence": {
                    "url": target,
                    "server_header": tool_output.get("server_header"),
                    "type": "version_disclosure"
                },
                "remediation": "Disable server banner emission or mask it with generic server tokens (e.g. 'Server: webserver')."
            })
    elif tool_name == "find_links":
        interesting = tool_output.get("interesting_endpoints", [])
        if interesting:
            findings.append({
                "title": "Potentially Sensitive Endpoint Discovered",
                "description": (
                    f"Discovered {len(interesting)} potentially sensitive endpoint(s) on target: "
                    + ", ".join(e.get("href", "") for e in interesting[:3])
                    + ". These routes may expose administrative surfaces, debug facilities, or unauthenticated interfaces."
                ),
                "severity": "INFO",
                "cwe_id": "CWE-538",
                "evidence": {
                    "url": target,
                    "endpoints": interesting,
                    "type": "endpoint_discovery"
                },
                "remediation": "Ensure administrative and internal routes require robust authentication and are not publicly indexed."
            })
    return findings


class AssessmentRunner:
    """Coordinates and executes an agent assessment with real-time event streaming."""

    def __init__(
        self,
        target: str,
        max_steps: int = 5,
        llm_engine: str = "auto",  # "groq", "openai", "scripted", "auto"
        groq_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        groq_model: str = "llama-3.3-70b-versatile"
    ):
        self.target = target.strip()
        self.max_steps = max(1, min(max_steps, 20))
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.groq_model = groq_model
        self.requested_engine = llm_engine

        # Active engine resolution
        self.active_engine = self._resolve_engine()

        # Stop signal
        self._stop_event = threading.Event()
        self.is_running = False

        # Event stream queue for SSE subscribers
        self.event_queue: queue.Queue = queue.Queue(maxsize=1000)

        # Build initial target host and scope
        parsed = urlparse(self.target if "://" in self.target else f"http://{self.target}")
        self.target_host = parsed.netloc or parsed.path
        self.scope = [self.target, self.target_host]

        # Initial state
        self.state: AgentState = {
            "engagement_id": f"eng-{int(time.time())}",
            "target": self.target,
            "scope": self.scope,
            "assessment_type": "web_app",
            "step_number": 1,
            "max_steps": self.max_steps,
            "done": False,
            "stop_reason": "",
            "assets": [],
            "observations": [],
            "suspected_findings": [],
            "confirmed_findings": [],
            "rejected_findings": [],
            "current_objective": "Initialize automated penetration testing assessment",
            "last_tool_name": None,
            "last_tool_input": None,
            "last_tool_output": None,
            "pending_approval": None,
        }

    def _resolve_engine(self) -> str:
        """Determines which engine to run based on requested engine and credentials."""
        if self.requested_engine == "groq" and self.groq_api_key.startswith("gsk_"):
            return "groq"
        if self.requested_engine == "openai" and self.openai_api_key.startswith("sk-"):
            return "openai"
        if self.requested_engine == "scripted":
            return "scripted"

        # Auto detection
        if self.groq_api_key and self.groq_api_key.startswith("gsk_"):
            return "groq"
        if self.openai_api_key and self.openai_api_key.startswith("sk-"):
            # Check if this is a real key or broken proxy
            base_url = os.getenv("OPENAI_BASE_URL", "")
            if not base_url or "api.openai.com" in base_url:
                return "openai"
        return "scripted"

    def emit(self, event_type: str, data: Dict[str, Any]):
        """Publish a typed telemetry event to all subscribers."""
        payload = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        try:
            self.event_queue.put_nowait(payload)
        except queue.Full:
            pass

    def stop(self):
        """Signal the runner to abort gracefully."""
        self._stop_event.set()
        self.emit("log", {
            "level": "warn",
            "message": "User initiated assessment termination. Completing current cycle and flushing findings."
        })

    def run(self):
        """Main execution loop running the 5-layer architecture."""
        self.is_running = True
        self.emit("session_start", {
            "engagement_id": self.state["engagement_id"],
            "target": self.target,
            "scope": self.scope,
            "engine": self.active_engine,
            "engine_model": self.groq_model if self.active_engine == "groq" else ("gpt-4o-mini" if self.active_engine == "openai" else "deterministic-methodology-v1"),
            "max_steps": self.max_steps,
            "started_at": time.time(),
        })

        self.emit("log", {
            "level": "info",
            "message": f"Target locked: {self.target} (Scope allowed: {', '.join(self.scope)})"
        })
        self.emit("log", {
            "level": "info",
            "message": f"Execution backend: {self.active_engine.upper()} (Budget: {self.max_steps} max steps)"
        })

        verifier = Verifier()
        scope_guard = ScopeGuard(
            allowed_targets=self.state["scope"],
            max_risk_class=RiskClass.READ_ONLY
        )

        try:
            while not self._stop_event.is_set():
                step = self.state["step_number"]
                if step > self.max_steps:
                    self.state["done"] = True
                    self.state["stop_reason"] = f"Budget reached ({self.max_steps} maximum steps executed)"
                    break

                # ─────────────────────────────────────────────────────────────
                # LAYER 2 / NODE 1: PLANNER
                # ─────────────────────────────────────────────────────────────
                self.emit("node_transition", {
                    "node": "planner",
                    "step": step,
                    "phase": "REASONING & METHODOLOGY",
                    "icon": "🧠"
                })

                plan_decision = self._execute_planner(step)
                if plan_decision.get("done"):
                    self.state["done"] = True
                    self.state["stop_reason"] = plan_decision.get("stop_reason", "Planner completed all objectives")
                    break

                tool_name = plan_decision["tool_name"]
                objective = plan_decision["objective"]
                reasoning = plan_decision.get("reasoning", "")
                self.state["current_objective"] = objective
                self.state["last_tool_name"] = tool_name
                self.state["last_tool_input"] = {"url": self.target}

                self.emit("plan_decided", {
                    "step": step,
                    "objective": objective,
                    "tool_name": tool_name,
                    "reasoning": reasoning,
                    "engine": self.active_engine
                })
                self.emit("log", {
                    "level": "info",
                    "message": f"[Step {step}] Planner selected: '{tool_name}' — Objective: {objective}"
                })

                time.sleep(0.4)
                if self._stop_event.is_set():
                    break

                # ─────────────────────────────────────────────────────────────
                # LAYER 2 / NODE 2: SCOPE CHECK (DETERMINISTIC GATE)
                # ─────────────────────────────────────────────────────────────
                self.emit("node_transition", {
                    "node": "scope_check",
                    "step": step,
                    "phase": "SCOPE & POLICY ENFORCEMENT",
                    "icon": "🔒"
                })

                t0 = time.time()
                decision, reason = scope_guard.check(tool_name, self.target)
                scope_eval_ms = round((time.time() - t0) * 1000, 2)

                self.emit("scope_checked", {
                    "step": step,
                    "target": self.target,
                    "tool": tool_name,
                    "decision": decision.value,
                    "reason": reason,
                    "latency_ms": scope_eval_ms,
                    "risk_class": "READ_ONLY"
                })

                if decision == ScopeDecision.DENY:
                    self.emit("log", {
                        "level": "error",
                        "message": f"[Step {step}] ❌ SCOPE REJECTED: {reason}. Action blocked by deterministic policy."
                    })
                    self.state["step_number"] += 1
                    continue
                elif decision == ScopeDecision.NEEDS_APPROVAL:
                    self.emit("log", {
                        "level": "warn",
                        "message": f"[Step {step}] ⚠️ SCOPE GATE: Action requires human operator approval."
                    })
                    self.state["step_number"] += 1
                    continue
                else:
                    self.emit("log", {
                        "level": "success",
                        "message": f"[Step {step}] ✅ SCOPE PERMITTED: Target {self.target} is within authorized engagement boundary."
                    })

                time.sleep(0.4)
                if self._stop_event.is_set():
                    break

                # ─────────────────────────────────────────────────────────────
                # LAYER 4 / NODE 3: SANDBOXED TOOL EXECUTION
                # ─────────────────────────────────────────────────────────────
                self.emit("node_transition", {
                    "node": "execute_tool",
                    "step": step,
                    "phase": "SANDBOXED TOOL RUNNER",
                    "icon": "⚙️"
                })

                self.emit("log", {
                    "level": "info",
                    "message": f"[Step {step}] Spawning sandboxed executor for tool '{tool_name}' on target..."
                })

                t_exec_start = time.time()
                tool_output = run_tool(tool_name, self.target)
                exec_elapsed_ms = round((time.time() - t_exec_start) * 1000)

                self.state["last_tool_output"] = tool_output
                self.state["observations"].append({
                    "step": step,
                    "tool": tool_name,
                    "target": self.target,
                    "output": tool_output,
                    "elapsed_ms": exec_elapsed_ms,
                    "timestamp": time.time(),
                })

                self.emit("tool_executed", {
                    "step": step,
                    "tool_name": tool_name,
                    "target": self.target,
                    "elapsed_ms": exec_elapsed_ms,
                    "success": tool_output.get("success", True),
                    "summary": self._summarize_tool_output(tool_name, tool_output),
                    "output": tool_output
                })

                time.sleep(0.5)
                if self._stop_event.is_set():
                    break

                # ─────────────────────────────────────────────────────────────
                # LAYER 2 / NODE 4: REFLECTOR (EVIDENCE PARSER)
                # ─────────────────────────────────────────────────────────────
                self.emit("node_transition", {
                    "node": "reflector",
                    "step": step,
                    "phase": "EVIDENCE REFLECTION & PARSING",
                    "icon": "🔍"
                })

                new_suspected = self._execute_reflector(tool_name, tool_output)
                self.state["suspected_findings"].extend(new_suspected)

                self.emit("reflector_result", {
                    "step": step,
                    "new_suspected_count": len(new_suspected),
                    "suspected_findings": new_suspected,
                })

                if new_suspected:
                    self.emit("log", {
                        "level": "warn",
                        "message": f"[Step {step}] 🔍 Reflector identified {len(new_suspected)} suspected vulnerability claim(s). Sending to Independent Verifier..."
                    })
                else:
                    self.emit("log", {
                        "level": "info",
                        "message": f"[Step {step}] Reflector parsed output: No new suspicious patterns detected in this cycle."
                    })

                time.sleep(0.5)
                if self._stop_event.is_set():
                    break

                # ─────────────────────────────────────────────────────────────
                # LAYER 3 / NODE 5: INDEPENDENT VERIFIER & CHAIN OF CUSTODY
                # ─────────────────────────────────────────────────────────────
                if self.state["suspected_findings"]:
                    self.emit("node_transition", {
                        "node": "verify",
                        "step": step,
                        "phase": "INDEPENDENT VERIFICATION & CUSTODY",
                        "icon": "🔬"
                    })

                    batch = list(self.state["suspected_findings"])
                    self.state["suspected_findings"] = []

                    for idx, finding in enumerate(batch, 1):
                        claim_title = finding.get("title", "Unknown Claim")
                        self.emit("verification_start", {
                            "step": step,
                            "index": idx,
                            "total": len(batch),
                            "title": claim_title,
                            "cwe": finding.get("cwe_id", "N/A"),
                            "severity": finding.get("severity", "INFO"),
                        })

                        time.sleep(0.35)
                        v_res = verifier.verify(finding)
                        verdict = v_res.get("verdict", "REJECTED")
                        evidence_hash = v_res.get("evidence_hash", "")

                        full_finding = {
                            **finding,
                            **v_res,
                            "verified_at": time.time(),
                            "status": verdict,
                        }

                        if verdict == "CONFIRMED":
                            self.state["confirmed_findings"].append(full_finding)
                            self.emit("log", {
                                "level": "success",
                                "message": f"✅ VERIFIED CONFIRMED: '{claim_title}' (Confidence: {v_res.get('confidence', 0):.0%}) [SHA256: {evidence_hash[:12]}...]"
                            })
                        elif verdict == "REJECTED":
                            self.state["rejected_findings"].append(full_finding)
                            self.emit("log", {
                                "level": "error",
                                "message": f"❌ FALSE POSITIVE REJECTED: '{claim_title}' — {v_res.get('reasoning', '')[:90]}"
                            })
                        else:
                            self.state["confirmed_findings"].append(full_finding)
                            self.emit("log", {
                                "level": "warn",
                                "message": f"⚠️ NEEDS HUMAN REVIEW: '{claim_title}'"
                            })

                        self.emit("verification_result", {
                            "step": step,
                            "finding": full_finding,
                            "verdict": verdict,
                            "confidence": v_res.get("confidence", 0.0),
                            "reasoning": v_res.get("reasoning", ""),
                            "evidence_hash": evidence_hash,
                        })

                # Step increment & state sync
                self.state["step_number"] += 1
                self.emit("state_update", {
                    "step_number": self.state["step_number"] - 1,
                    "confirmed_count": len(self.state["confirmed_findings"]),
                    "rejected_count": len(self.state["rejected_findings"]),
                    "observations_count": len(self.state["observations"]),
                })

                time.sleep(0.6)

        except Exception as e:
            logger.exception("Error during assessment run")
            self.emit("error", {"message": str(e)})
            self.emit("log", {
                "level": "error",
                "message": f"Fatal execution error encountered: {str(e)}"
            })
        finally:
            self.is_running = False
            self.emit("session_complete", {
                "engagement_id": self.state["engagement_id"],
                "target": self.target,
                "completed_at": time.time(),
                "steps_executed": self.state["step_number"] - 1,
                "stop_reason": self.state.get("stop_reason") or ("User stopped" if self._stop_event.is_set() else "Completed"),
                "confirmed_findings": self.state["confirmed_findings"],
                "rejected_findings": self.state["rejected_findings"],
                "observations": self.state["observations"],
            })
            self.emit("log", {
                "level": "success",
                "message": f"Assessment finalized. {len(self.state['confirmed_findings'])} confirmed vulnerabilities, {len(self.state['rejected_findings'])} false positives filtered."
            })

    def _invoke_groq(self, schema, messages):
        """Invoke Groq with fallback to standard models (llama-3.1-8b-instant, llama-3.1-70b-versatile, etc.)."""
        from langchain_groq import ChatGroq
        candidates = [
            self.groq_model,
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "mixtral-8x7b-32768"
        ]
        seen = set()
        models_to_try = [m for m in candidates if m and not (m in seen or seen.add(m))]

        last_err = None
        for m in models_to_try:
            try:
                llm = ChatGroq(model=m, temperature=0, api_key=self.groq_api_key).with_structured_output(schema)
                res = llm.invoke(messages)
                if self.groq_model != m:
                    logger.info(f"Switched active Groq model to: {m}")
                    self.groq_model = m
                return res
            except Exception as e:
                err_str = str(e).lower()
                if "model_not_found" in err_str or "does not exist" in err_str or "404" in err_str:
                    logger.info(f"Groq model {m} not available on this key, trying next fallback model...")
                    last_err = e
                    continue
                raise e
        raise last_err or Exception("No accessible Groq models found for provided API key")

    def _execute_planner(self, step: int) -> dict:
        """Invokes either Groq/OpenAI LLM planner or fallback methodology."""
        idx = step - 1

        if self.active_engine in ("groq", "openai"):
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from pydantic import BaseModel, Field

                class PlanModel(BaseModel):
                    reasoning: str = Field(description="Pen-test reasoning for action")
                    stop: bool = Field(description="True if test complete")
                    tool_name: Optional[str] = Field(default=None, description="Tool to run")
                    objective: str = Field(description="Specific technical objective")

                system = """You are the Redfox AI Penetration Testing Agent Planner.
You test web targets systematically using these tools:
- check_security_headers: Inspect CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- http_headers: Enumerate HTTP response headers, server tokens, status codes
- find_links: Extract links, forms, parameters, endpoints
- dns_lookup: Resolve IP addresses and DNS configuration
Test in structured reconnaissance order, then stop."""

                user = f"Target: {self.target}\nStep: {step}/{self.max_steps}\nObservations so far: {len(self.state['observations'])}\nConfirmed: {len(self.state['confirmed_findings'])}\nSelect next logical action."

                if self.active_engine == "groq":
                    decision = self._invoke_groq(PlanModel, [SystemMessage(content=system), HumanMessage(content=user)])
                else:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=self.openai_api_key).with_structured_output(PlanModel)
                    decision = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])

                if decision.stop or not decision.tool_name:
                    return {"done": True, "stop_reason": "LLM determined assessment goal satisfied"}
                return {
                    "done": False,
                    "tool_name": decision.tool_name,
                    "objective": decision.objective,
                    "reasoning": decision.reasoning
                }
            except Exception as e:
                logger.warning(f"LLM planner failed: {e}. Falling back to scripted methodology.")

        # Scripted methodology fallback
        if idx >= len(SCRIPTED_PLAN):
            return {"done": True, "stop_reason": "All defined methodology assessment stages complete"}

        entry = SCRIPTED_PLAN[idx]
        return {
            "done": False,
            "tool_name": entry["tool"],
            "objective": entry["objective"],
            "reasoning": f"Standard OWASP reconnaissance methodology phase {step}: {entry['tool']}."
        }

    def _execute_reflector(self, tool_name: str, tool_output: dict) -> list[dict]:
        """Extracts suspected claims using either Groq/OpenAI or deterministic rules."""
        if self.active_engine in ("groq", "openai"):
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from pydantic import BaseModel, Field

                class FindingModel(BaseModel):
                    title: str
                    description: str
                    severity: str
                    cwe_id: str
                    evidence: dict

                class ReflectionModel(BaseModel):
                    summary: str
                    new_findings: List[FindingModel]

                system = """You are the Redfox AI Evidence Reflector.
Parse raw security tool output into suspected finding claims.
Never confirm vulnerabilities without proof. Extract accurate title, description, severity (CRITICAL, HIGH, MEDIUM, LOW, INFO), and CWE."""

                user = f"Target: {self.target}\nTool: {tool_name}\nOutput:\n{json.dumps(tool_output, indent=2)[:3000]}"

                if self.active_engine == "groq":
                    res = self._invoke_groq(ReflectionModel, [SystemMessage(content=system), HumanMessage(content=user)])
                else:
                    from langchain_openai import ChatOpenAI
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=self.openai_api_key).with_structured_output(ReflectionModel)
                    res = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])

                return [
                    {
                        "title": f.title,
                        "description": f.description,
                        "severity": f.severity,
                        "cwe_id": f.cwe_id,
                        "evidence": f.evidence,
                    }
                    for f in res.new_findings
                ]
            except Exception as e:
                logger.warning(f"LLM reflector failed: {e}. Using deterministic fallback.")

        return scripted_reflect(tool_name, tool_output, self.target)

    def _summarize_tool_output(self, tool_name: str, output: dict) -> str:
        """Generates a concise one-line summary for UI displays."""
        if not output.get("success", True):
            return f"Tool returned error: {output.get('error', 'unknown error')}"
        if tool_name == "check_security_headers":
            missing = len(output.get("missing_security_headers", []))
            present = len(output.get("present_security_headers", []))
            return f"Found {present} security headers present; {missing} security headers missing."
        if tool_name == "http_headers":
            status = output.get("status_code", "N/A")
            server = output.get("server", "unknown")
            return f"HTTP {status} OK | Server: {server} | {len(output.get('headers', {}))} response headers."
        if tool_name == "find_links":
            links = output.get("total_links_found", 0)
            forms = output.get("total_forms_found", 0)
            return f"Parsed DOM: {links} hyperlinks discovered, {forms} interactive forms indexed."
        if tool_name == "dns_lookup":
            ips = output.get("ip_addresses", [])
            return f"Resolved {len(ips)} IP addresses: {', '.join(ips[:3])}."
        return "Tool execution succeeded."
