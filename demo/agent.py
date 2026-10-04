"""
agent.py — The AI Pen-Test Agent Demo

WHAT THIS DEMONSTRATES:
    This is a working mini-implementation of the architecture described in
    output/ARCHITECTURE.md. It shows every core concept running in a real terminal:

    ┌─────────────────────────────────────────────────────────────────┐
    │  PLAN → SCOPE CHECK → EXECUTE → REFLECT → VERIFY → repeat       │
    └─────────────────────────────────────────────────────────────────┘

    ┌─── Architecture concept ───────────────────────────┬── Where it is in this file ───┐
    │ Agent reasoning loop (plan-act-observe-reflect)    │ build_graph()                 │
    │ Structured state model (not chat history)          │ state.py + AgentState         │
    │ Scope enforcement (deterministic, LLM-free)        │ scope_guard.py + scope_check()│
    │ Sandboxed tool execution                           │ tools.py + execute_tool()     │
    │ LLM-based planning and reflection                  │ planner() + reflector()       │
    │ Independent finding verification                   │ verifier.py + verify()        │
    │ Evidence chain of custody (SHA-256)                │ verifier.py                   │
    │ Budget enforcement (max steps)                     │ should_stop() routing         │
    │ Findings lifecycle (suspected → confirmed)         │ verifier() node               │
    └────────────────────────────────────────────────────┴───────────────────────────────┘

SETUP:
    1. Copy demo/.env.example to demo/.env
    2. Set OPENAI_API_KEY in .env
    3. pip install -r requirements.txt
    4. python agent.py

NOTE:
    If no OPENAI_API_KEY is set, the agent uses a SCRIPTED FALLBACK
    (a rule-based planner) so the demo always runs and shows the structure.
"""

import json
import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Local modules
from scope_guard import RiskClass, ScopeDecision, ScopeGuard
from state import AgentState
from tools import run_tool
from verifier import Verifier

load_dotenv()

console = Console()

# ── Configuration ─────────────────────────────────────────────────────────────

TARGET      = os.getenv("DEMO_TARGET", "http://httpbin.org")
MAX_STEPS   = int(os.getenv("DEMO_MAX_STEPS", "8"))
OPENAI_KEY  = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Determine LLM backend: Groq > OpenAI > Scripted
USE_GROQ    = bool(GROQ_KEY and GROQ_KEY.startswith("gsk_"))
USE_OPENAI  = bool(not USE_GROQ and OPENAI_KEY and OPENAI_KEY.startswith("sk-"))
USE_LLM     = USE_GROQ or USE_OPENAI

# Scripted methodology fallback — used when no LLM is available
# Mirrors what an LLM planner would produce for a web app assessment
SCRIPTED_PLAN = [
    {"tool": "check_security_headers", "objective": "Check which security headers are present or missing"},
    {"tool": "http_headers",           "objective": "Gather full header set and server information"},
    {"tool": "find_links",             "objective": "Discover all links, forms, and interesting endpoints"},
    {"tool": "dns_lookup",             "objective": "Resolve IP addresses and inspect reverse DNS"},
]

# Scripted reflector — maps tool outputs to suspected findings without LLM
def scripted_reflect(tool_name: str, tool_output: dict, target: str) -> list[dict]:
    """
    Rule-based finding identification — used as fallback when no LLM is available.
    In production, this logic is handled by the LLM reflector node.
    """
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
            })
        if tool_output.get("server_version_disclosed"):
            findings.append({
                "title": "Server Version Disclosure",
                "description": (
                    f"The 'Server' response header discloses the server software and version: "
                    f"'{tool_output.get('server_header')}'. "
                    f"Attackers use this to look up known CVEs for the specific version."
                ),
                "severity": "LOW",
                "cwe_id": "CWE-200",
                "evidence": {
                    "url": target,
                    "server_header": tool_output.get("server_header"),
                    "type": "version_disclosure"
                },
            })

    elif tool_name == "find_links":
        interesting = tool_output.get("interesting_endpoints", [])
        if interesting:
            findings.append({
                "title": "Sensitive Endpoint Discovered",
                "description": (
                    f"Discovered {len(interesting)} potentially sensitive endpoint(s): "
                    + ", ".join(e["href"] for e in interesting[:3])
                    + ". These may expose admin functionality or sensitive data."
                ),
                "severity": "INFO",
                "cwe_id": "CWE-538",
                "evidence": {
                    "url": target,
                    "endpoints": interesting,
                    "type": "endpoint_discovery"
                },
            })

    return findings


# ── UI helpers ────────────────────────────────────────────────────────────────

SEVERITY_COLOR = {"CRITICAL": "red", "HIGH": "bright_red", "MEDIUM": "yellow", "LOW": "cyan", "INFO": "blue"}
VERDICT_ICON   = {"CONFIRMED": "✅", "REJECTED": "❌", "NEEDS_HUMAN_REVIEW": "⚠️"}
VERDICT_COLOR  = {"CONFIRMED": "green", "REJECTED": "red", "NEEDS_HUMAN_REVIEW": "yellow"}

def print_banner():
    if USE_GROQ:
        mode = f"[green]LLM mode (Groq / {GROQ_MODEL})[/green]"
    elif USE_OPENAI:
        mode = "[green]LLM mode (OpenAI GPT-4o-mini)[/green]"
    else:
        mode = "[yellow]Scripted mode (no API key)[/yellow]"
    console.print(Panel.fit(
        f"[bold red]🦊  Redfox AI Pen-Test Agent — Demo[/bold red]\n\n"
        f"[white]Target   :[/white] [yellow]{TARGET}[/yellow]\n"
        f"[white]Mode     :[/white] {mode}\n"
        f"[white]Max steps:[/white] {MAX_STEPS}\n\n"
        f"[dim]This demo shows the architecture's core loop:[/dim]\n"
        f"[dim]PLAN → SCOPE CHECK → EXECUTE → REFLECT → VERIFY → repeat[/dim]",
        border_style="bright_red",
        padding=(1, 4),
    ))

def step_header(step: int, phase: str, icon: str, color: str):
    bar = "─" * 60
    console.print(f"\n[{color}]{bar}[/{color}]")
    console.print(f"[bold {color}]{icon}  STEP {step}  ·  {phase}[/bold {color}]")
    console.print(f"[{color}]{bar}[/{color}]")


# ── LangGraph nodes ───────────────────────────────────────────────────────────

def planner(state: AgentState) -> dict:
    """
    PLAN: Decide the next action.

    In LLM mode: asks GPT-4o-mini what to do next based on current state.
    In scripted mode: follows the hardcoded SCRIPTED_PLAN list.

    Either way, it returns:
    - current_objective: what we're trying to achieve
    - last_tool_name:    which tool to use
    - last_tool_input:   input for that tool
    """
    step = state["step_number"]
    step_header(step, "PLANNING", "🧠", "bright_cyan")

    # ── Stop conditions ───────────────────────────────────────────────────────
    if step > MAX_STEPS:
        console.print(f"  [yellow]Max steps ({MAX_STEPS}) reached — stopping.[/yellow]")
        return {"done": True, "stop_reason": "Max steps reached"}

    # ── LLM planning ─────────────────────────────────────────────────────────
    if USE_LLM:
        return _llm_plan(state)
    else:
        return _scripted_plan(state)


def _scripted_plan(state: AgentState) -> dict:
    """Scripted fallback — no LLM required."""
    step = state["step_number"]
    idx = step - 1

    if idx >= len(SCRIPTED_PLAN):
        console.print("  [green]All scripted steps complete — stopping.[/green]")
        return {"done": True, "stop_reason": "All methodology steps complete"}

    plan = SCRIPTED_PLAN[idx]
    console.print(f"  [dim](Scripted mode — no LLM)[/dim]")
    console.print(f"  [white]Objective:[/white] {plan['objective']}")
    console.print(f"  [white]Tool     :[/white] [yellow]{plan['tool']}[/yellow]")
    console.print(f"  [white]Target   :[/white] {TARGET}")

    return {
        "done": False,
        "current_objective": plan["objective"],
        "last_tool_name": plan["tool"],
        "last_tool_input": {"url": TARGET},
    }


def _get_llm():
    """Return the appropriate LLM client (Groq or OpenAI)."""
    if USE_GROQ:
        from langchain_groq import ChatGroq
        return ChatGroq(model=GROQ_MODEL, temperature=0, api_key=GROQ_KEY)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _llm_plan(state: AgentState) -> dict:
    """LLM-based planning using Groq (llama-3.3-70b-versatile) or OpenAI with structured output."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field

    class PlannerOutput(BaseModel):
        reasoning: str = Field(description="Brief reasoning for your choice")
        stop: bool     = Field(description="True if no more useful actions remain")
        tool_name: Optional[str] = Field(default=None, description="Tool to use next")
        objective: str = Field(description="What you are trying to achieve")

    step = state["step_number"]
    obs_text = ""
    if state["observations"]:
        last = state["observations"][-1]
        obs_text = f"\nLast observation (step {last.get('step','?')}, tool={last.get('tool','?')}):\n{json.dumps(last.get('output', {}), indent=2)[:800]}"

    system = """You are an AI penetration testing assistant running a web application security assessment.
Your job is to systematically test the target using these READ_ONLY tools:
  - check_security_headers: Check for missing/misconfigured security headers
  - http_headers: Fetch raw HTTP headers and status
  - find_links: Discover links, forms, and interesting endpoints
  - dns_lookup: Resolve domain to IP addresses

Follow this order:
  1. check_security_headers
  2. http_headers  
  3. find_links
  4. dns_lookup
  5. Stop

Return structured output."""

    user = f"""Target: {TARGET}
Step: {step}/{MAX_STEPS}
Steps completed: {step - 1}
Confirmed findings so far: {len(state['confirmed_findings'])}
{obs_text}

What should I do next?"""

    try:
        llm = _get_llm().with_structured_output(PlannerOutput)
        decision = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])

        backend = "Groq" if USE_GROQ else "OpenAI"
        console.print(f"  [dim][{backend}] Reasoning: {decision.reasoning[:200]}[/dim]")

        if decision.stop:
            console.print("  [green]LLM decided to stop — sufficient information gathered.[/green]")
            return {"done": True, "stop_reason": "LLM decided to stop"}

        console.print(f"  [white]Objective:[/white] {decision.objective}")
        console.print(f"  [white]Tool     :[/white] [yellow]{decision.tool_name}[/yellow]")
        console.print(f"  [white]Target   :[/white] {TARGET}")

        return {
            "done": False,
            "current_objective": decision.objective,
            "last_tool_name": decision.tool_name,
            "last_tool_input": {"url": TARGET},
        }
    except Exception as e:
        console.print(f"  [red]LLM error: {e} — falling back to scripted plan[/red]")
        return _scripted_plan(state)


def scope_check(state: AgentState) -> dict:
    """
    SCOPE CHECK: Deterministic, LLM-free gate before every action.

    This is the most important safety node. It runs REGARDLESS of what the
    LLM decided in the planning step. The LLM cannot bypass this.

    Checks:
    1. Is the target in the approved scope list?
    2. Is the tool registered?
    3. Is the tool's risk class within the engagement's limit?
    """
    step = state["step_number"]
    step_header(step, "SCOPE CHECK", "🔒", "bright_yellow")

    tool_name = state.get("last_tool_name", "")
    tool_input = state.get("last_tool_input", {})
    target = tool_input.get("url") or tool_input.get("target") or TARGET

    guard = ScopeGuard(
        allowed_targets=state["scope"],
        max_risk_class=RiskClass.READ_ONLY,  # This demo allows only read-only actions
    )

    console.print(f"  Checking: [yellow]{tool_name}[/yellow] → {target}")
    decision, reason = guard.check(tool_name, target)

    icon  = {"ALLOW": "✅", "DENY": "❌", "NEEDS_APPROVAL": "⚠️"}[decision.value]
    color = {"ALLOW": "green", "DENY": "red", "NEEDS_APPROVAL": "yellow"}[decision.value]
    console.print(f"  {icon} [{color}]{decision.value}[/{color}]: {reason}")

    if decision == ScopeDecision.DENY:
        console.print(f"  [red]Action blocked. Agent must choose a different action.[/red]")
        # Mark step as failed — planner will reconsider
        return {
            "pending_approval": {"decision": "DENY", "reason": reason},
            "last_tool_name": None,
        }
    elif decision == ScopeDecision.NEEDS_APPROVAL:
        console.print(f"  [yellow]In production: this would send a notification to the tester's dashboard.[/yellow]")
        console.print(f"  [yellow]Demo: auto-denying to show the approval gate concept.[/yellow]")
        return {
            "pending_approval": {"decision": "NEEDS_APPROVAL", "reason": reason},
            "last_tool_name": None,
        }
    else:
        return {"pending_approval": None}


def execute_tool(state: AgentState) -> dict:
    """
    EXECUTE: Run the approved tool and capture structured output.

    In production, this spawns an ephemeral container:
    - Separate network namespace (only reaches in-scope IPs)
    - Resource limits (CPU/memory caps)
    - Destroyed immediately after execution
    - Output artifacts captured to Cloud Storage

    In this demo, we run the tool function directly in Python,
    but the contract (typed input → structured output) is the same.
    """
    step = state["step_number"]
    step_header(step, "EXECUTING", "⚙️ ", "bright_magenta")

    tool_name = state.get("last_tool_name")
    tool_input = state.get("last_tool_input", {})
    target = tool_input.get("url") or tool_input.get("target") or TARGET

    console.print(f"  Running [yellow]{tool_name}[/yellow] on {target}")
    console.print(f"  [dim](In production: this runs inside an ephemeral sandboxed container)[/dim]")

    start = time.time()
    output = run_tool(tool_name, target)
    elapsed = round((time.time() - start) * 1000)

    # Print a human-readable summary based on tool type
    if not output.get("success", True):
        console.print(f"  [red]Tool error: {output.get('error')}[/red]")
    elif tool_name == "check_security_headers":
        missing = output.get("missing_security_headers", [])
        present = output.get("present_security_headers", [])
        console.print(f"  → Status code    : {output.get('status_code')}")
        console.print(f"  → Missing headers: [red]{len(missing)}[/red]")
        console.print(f"  → Present headers: [green]{len(present)}[/green]")
        for h in missing:
            sev_color = SEVERITY_COLOR.get(h["severity"], "white")
            console.print(f"    [red]✗[/red] {h['header']} [{sev_color}]{h['severity']}[/{sev_color}]")
        for h in present:
            console.print(f"    [green]✓[/green] {h['header']}")
        if output.get("server_version_disclosed"):
            console.print(f"  → Server version : [yellow]{output.get('server_header')}[/yellow] ← disclosed!")
    elif tool_name == "http_headers":
        headers = output.get("headers", {})
        console.print(f"  → Status code    : {output.get('status_code')}")
        console.print(f"  → Server         : {headers.get('server', headers.get('Server', 'not disclosed'))}")
        console.print(f"  → Response time  : {output.get('response_time_ms')}ms")
        console.print(f"  → Content-Length : {output.get('content_length_bytes')} bytes")
    elif tool_name == "find_links":
        console.print(f"  → Page title     : {output.get('page_title', 'N/A')}")
        console.print(f"  → Links found    : {output.get('links_found', 0)}")
        console.print(f"  → Forms found    : [yellow]{output.get('forms_found', 0)}[/yellow]")
        interesting = output.get("interesting_endpoints", [])
        if interesting:
            console.print(f"  → [yellow]Interesting endpoints ({len(interesting)}):[/yellow]")
            for ep in interesting[:5]:
                console.print(f"    • {ep.get('href')}")
    elif tool_name == "dns_lookup":
        console.print(f"  → IPs            : {output.get('ip_addresses', [])}")
        for r in output.get("reverse_dns", []):
            console.print(f"  → Reverse DNS    : {r['ip']} → {r.get('hostname') or '(no reverse DNS)'}")

    console.print(f"  [dim]Completed in {elapsed}ms[/dim]")

    observation = {"step": step, "tool": tool_name, "target": target, "output": output}
    new_observations = state["observations"] + [observation]

    return {
        "last_tool_output": output,
        "observations": new_observations,
    }


def reflector(state: AgentState) -> dict:
    """
    REFLECT: Analyse tool output and identify potential security issues.

    This node looks at what the tool found and asks:
    "Does this indicate a vulnerability?"

    If yes → creates a SUSPECTED finding and passes it to the verifier.
    If no  → loops back to the planner for the next step.

    In LLM mode: the LLM analyses the output.
    In scripted mode: rule-based analysis from scripted_reflect().
    """
    step = state["step_number"]
    step_header(step, "REFLECTING", "🔍", "bright_blue")

    tool_name   = state.get("last_tool_name", "")
    tool_output = state.get("last_tool_output", {})

    if not tool_output or not tool_output.get("success", True) and tool_output.get("error"):
        console.print(f"  [red]Tool output was an error — skipping reflection[/red]")
        return {"step_number": step + 1, "suspected_findings": []}

    # Choose analysis method
    if USE_LLM:
        new_suspected = _llm_reflect(tool_name, tool_output, step)
    else:
        new_suspected = scripted_reflect(tool_name, tool_output, TARGET)

    if new_suspected:
        for f in new_suspected:
            sev = f.get("severity", "INFO")
            console.print(f"  [yellow]⚠  SUSPECTED:[/yellow] {f['title']} [[{SEVERITY_COLOR.get(sev, 'white')}]{sev}[/{SEVERITY_COLOR.get(sev, 'white')}]] [{f.get('cwe_id', '')}]")
    else:
        console.print(f"  [green]✓  No findings suspected in this step[/green]")

    # Add step number to each finding for traceability
    for f in new_suspected:
        f["discovered_at_step"] = step

    # Merge with any existing suspected findings from earlier steps
    all_suspected = state["suspected_findings"] + new_suspected

    return {
        "step_number": step + 1,
        "suspected_findings": all_suspected,
    }


def _llm_reflect(tool_name: str, tool_output: dict, step: int) -> list[dict]:
    """LLM-based reflection using Groq or OpenAI."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field

    class FindingModel(BaseModel):
        title: str        = Field(description="Short, clear title of the finding")
        description: str  = Field(description="Detailed description explaining the risk")
        severity: str     = Field(description="One of: CRITICAL, HIGH, MEDIUM, LOW, INFO")
        cwe_id: str       = Field(description="CWE identifier, e.g. CWE-200")
        evidence: dict    = Field(description="Evidence extracted from the tool output")

    class ReflectorOutput(BaseModel):
        summary: str                   = Field(description="What did this tool output tell you?")
        new_findings: list[FindingModel] = Field(default=[], description="Suspected vulnerabilities found")

    system = """You are a security analyst reviewing the output from a penetration test tool.
Identify real security vulnerabilities from the output.
Focus only on what the data ACTUALLY shows — do not hallucinate findings.
For each finding, extract specific evidence from the tool output."""

    user = f"""Tool: {tool_name}
Output: {json.dumps(tool_output, indent=2)[:1500]}

What security issues do you see? Identify any suspected vulnerabilities."""

    try:
        llm = _get_llm().with_structured_output(ReflectorOutput)
        analysis = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])

        backend = "Groq" if USE_GROQ else "OpenAI"
        console.print(f"  [dim][{backend}] {analysis.summary[:200]}[/dim]")

        return [
            {
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "cwe_id": f.cwe_id,
                "evidence": f.evidence,
            }
            for f in analysis.new_findings
        ]
    except Exception as e:
        console.print(f"  [red]Reflector LLM error: {e} — using rule-based fallback[/red]")
        return scripted_reflect(tool_name, tool_output, TARGET)


def verify(state: AgentState) -> dict:
    """
    VERIFY: Independently verify each suspected finding.

    KEY ARCHITECTURE CONCEPT:
    The verifier is completely isolated from the planner and reflector.
    It receives only:
    - The claim (title, description, severity, CWE)
    - The evidence bundle (URL, what was found)

    It does NOT receive the agent's conversation history or reasoning.
    It must independently reproduce each finding.

    This prevents hallucinated findings from reaching the final report.
    """
    step = state["step_number"]
    step_header(step, "VERIFYING", "🔬", "bright_green")

    suspected = state.get("suspected_findings", [])

    if not suspected:
        console.print("  [dim]No suspected findings to verify in this batch[/dim]")
        return {}

    console.print(f"  Verifying [yellow]{len(suspected)}[/yellow] suspected finding(s)...")
    console.print(f"  [dim](In production: verifier runs in a SEPARATE isolated process with no access to agent reasoning)[/dim]\n")

    v = Verifier()
    confirmed = list(state["confirmed_findings"])
    rejected  = list(state["rejected_findings"])

    for i, finding in enumerate(suspected, 1):
        console.print(f"  [{i}/{len(suspected)}] Claim: [yellow]{finding['title']}[/yellow]")
        console.print(f"        CWE: {finding.get('cwe_id', 'N/A')} | Severity: {finding.get('severity', 'N/A')}")
        console.print(f"        Independent re-check in progress...")

        time.sleep(0.3)   # Simulate network round-trip time
        result = v.verify(finding)

        verdict = result["verdict"]
        icon  = VERDICT_ICON.get(verdict, "?")
        color = VERDICT_COLOR.get(verdict, "white")

        console.print(f"        {icon} [{color}]{verdict}[/{color}] | Confidence: {result.get('confidence', 0):.0%}")
        console.print(f"        [dim]{result.get('reasoning', '')[:200]}[/dim]")
        if result.get("evidence_hash"):
            console.print(f"        [dim]Evidence hash: sha256:{result['evidence_hash']}...[/dim]")
        console.print()

        full_finding = {**finding, **result, "status": verdict}

        if verdict == "CONFIRMED":
            confirmed.append(full_finding)
        elif verdict == "REJECTED":
            rejected.append(full_finding)
        else:
            # NEEDS_HUMAN_REVIEW — still add to confirmed list for reporting
            confirmed.append(full_finding)

    return {
        "confirmed_findings": confirmed,
        "rejected_findings": rejected,
        "suspected_findings": [],   # Clear — these have all been processed
    }


# ── Routing functions (conditional edges in the graph) ────────────────────────

def route_after_scope_check(state: AgentState) -> str:
    """
    After the scope check, where should we go?
    - ALLOW → execute the tool
    - DENY or NEEDS_APPROVAL → back to planner (agent must choose a different action)
    """
    if state.get("pending_approval"):
        return "plan_again"
    return "execute"


def route_after_reflect(state: AgentState) -> str:
    """
    After reflection, where should we go?
    - Have suspected findings → verify them
    - No findings → back to planner for next step
    """
    if state.get("suspected_findings"):
        return "verify"
    return "plan"


def route_after_plan(state: AgentState) -> str:
    """
    After planning, where should we go?
    - Agent says done → END
    - Otherwise → scope check
    """
    if state.get("done"):
        return "stop"
    return "check_scope"


# ── Build the LangGraph graph ─────────────────────────────────────────────────

def build_graph():
    """
    Build the LangGraph StateGraph.

    Nodes correspond to the architecture's components.
    Conditional edges implement the routing logic.

    The graph structure:
                ┌──────────┐
                │ planner  │◄─────────────────────────────────┐
                └────┬─────┘                                  │
          done?      │ not done                                │
          ↓ END      ▼                                        │
                ┌──────────────┐                              │
                │ scope_check  │                              │
                └──────┬───────┘                             │
           denied?     │ allowed                              │
           ↓ planner   ▼                                     │
                ┌──────────────┐                             │
                │ execute_tool │                             │
                └──────┬───────┘                            │
                        ▼                                    │
                ┌──────────────┐                            │
                │  reflector   │                            │
                └──────┬───────┘                            │
       no findings?    │ findings found                     │
       ↓ planner       ▼                                    │
                ┌──────────────┐                            │
                │   verify     │───────────────────────────►┘
                └──────────────┘
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner",      planner)
    graph.add_node("scope_check",  scope_check)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("reflector",    reflector)
    graph.add_node("verify",       verify)

    # Set the entry point
    graph.set_entry_point("planner")

    # Conditional edge from planner → (scope_check | END)
    graph.add_conditional_edges(
        "planner",
        route_after_plan,
        {"check_scope": "scope_check", "stop": END}
    )

    # Conditional edge from scope_check → (execute_tool | planner)
    graph.add_conditional_edges(
        "scope_check",
        route_after_scope_check,
        {"execute": "execute_tool", "plan_again": "planner"}
    )

    # execute_tool always goes to reflector
    graph.add_edge("execute_tool", "reflector")

    # Conditional edge from reflector → (verify | planner)
    graph.add_conditional_edges(
        "reflector",
        route_after_reflect,
        {"verify": "verify", "plan": "planner"}
    )

    # verify always goes back to planner (for next step)
    graph.add_edge("verify", "planner")

    return graph.compile()


# ── Final report printer ──────────────────────────────────────────────────────

def print_final_report(state: AgentState):
    confirmed = state.get("confirmed_findings", [])
    rejected  = state.get("rejected_findings", [])

    console.print("\n")
    console.print(Panel.fit(
        "[bold white]  ASSESSMENT COMPLETE  [/bold white]",
        border_style="bright_green",
        padding=(0, 8),
    ))

    console.print(f"\n[bold]Summary[/bold]")
    console.print(f"  Steps executed     : {state['step_number'] - 1}")
    console.print(f"  Observations logged: {len(state['observations'])}")
    console.print(f"  Confirmed findings : [green]{len(confirmed)}[/green]")
    console.print(f"  Rejected (false +) : [red]{len(rejected)}[/red]")
    console.print(f"  Stop reason        : {state.get('stop_reason', 'N/A')}")

    if confirmed:
        console.print(f"\n[bold yellow]Confirmed Findings[/bold yellow]")

        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "NEEDS_HUMAN_REVIEW": 5}
        sorted_findings = sorted(confirmed, key=lambda f: sev_order.get(f.get("severity", "INFO"), 5))

        table = Table(box=box.ROUNDED, border_style="yellow", show_header=True)
        table.add_column("#",           width=3,  style="dim")
        table.add_column("Status",      width=20)
        table.add_column("Sev",         width=10)
        table.add_column("Finding",     width=40)
        table.add_column("CWE",         width=10)
        table.add_column("Confidence",  width=12)

        for i, f in enumerate(sorted_findings, 1):
            sev     = f.get("severity", "INFO")
            verdict = f.get("verdict", f.get("status", "?"))
            sev_color = SEVERITY_COLOR.get(sev, "white")
            v_color   = VERDICT_COLOR.get(verdict, "white")
            table.add_row(
                str(i),
                f"[{v_color}]{VERDICT_ICON.get(verdict, '')} {verdict}[/{v_color}]",
                f"[{sev_color}]{sev}[/{sev_color}]",
                f["title"],
                f.get("cwe_id", ""),
                f"{f.get('confidence', 0):.0%}",
            )

        console.print(table)

    if rejected:
        console.print(f"\n[bold red]Rejected Findings (False Positives)[/bold red]")
        for f in rejected:
            console.print(f"  ❌ {f['title']} — {f.get('reasoning', '')[:80]}")

    console.print(f"\n[dim]Evidence hashes are stored in each finding record for chain of custody.[/dim]")
    console.print(f"[dim]In production: this report would be exported to the engagement database[/dim]")
    console.print(f"[dim]and a formatted PDF report would be generated for the client.[/dim]\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print_banner()

    if not USE_LLM:
        console.print("\n[yellow]⚠  No OPENAI_API_KEY found.[/yellow]")
        console.print("[yellow]   Running in scripted mode — the agent loop structure is identical,[/yellow]")
        console.print("[yellow]   but the planning and reflection use rule-based logic instead of an LLM.[/yellow]")
        console.print("[yellow]   Add OPENAI_API_KEY=sk-... to demo/.env to enable full LLM mode.[/yellow]\n")

    # Build initial state
    scope = [TARGET, TARGET.replace("http://", "").replace("https://", "").split("/")[0]]
    initial_state: AgentState = {
        "engagement_id":     "demo-eng-001",
        "target":            TARGET,
        "scope":             scope,
        "assessment_type":   "web_app",
        "step_number":       1,
        "max_steps":         MAX_STEPS,
        "done":              False,
        "stop_reason":       "",
        "assets":            [],
        "observations":      [],
        "suspected_findings":[],
        "confirmed_findings":[],
        "rejected_findings": [],
        "current_objective": "Begin web application assessment",
        "last_tool_name":    None,
        "last_tool_input":   None,
        "last_tool_output":  None,
        "pending_approval":  None,
    }

    app = build_graph()

    try:
        final_state = app.invoke(initial_state)
        print_final_report(final_state)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Assessment interrupted by user (Ctrl+C)[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Unexpected error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
