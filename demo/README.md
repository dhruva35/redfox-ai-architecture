# 🦊 Redfox AI Pen-Test Agent — Interactive Demo & Dashboard

A fully functioning reference implementation of the **Redfox AI 5-Layer Autonomous Penetration Testing Architecture** described in `output/ARCHITECTURE.md`.

This demo runs safe, read-only reconnaissance against authorized targets (such as `httpbin.org` or `testphp.vulnweb.com`) and demonstrates the core platform differentiators:
1. **Deterministic Scope Guard** (Zero hallucinations, strict boundaries)
2. **Autonomous Reasoning Loop** in LangGraph (`PLAN → SCOPE CHECK → EXECUTE → REFLECT → VERIFY`)
3. **Independent Verifier with SHA-256 Custody** (Zero false positive guarantee)
4. **Sandboxed Tool Runners** (Clean typed inputs/outputs)
5. **Multi-LLM Support**: **Groq** (LLaMA-3.3 70B - fast & free), **OpenAI** (GPT-4o-mini), and **Deterministic Methodology Mode** (Offline/Safe).

---

## 🚀 Quick Start: Launch the Web Dashboard

The web dashboard provides a live, futuristic cyber-security cockpit that visualizes every phase of the 5 layers in real-time.

```bash
# 1. Navigate to the demo directory
cd demo

# 2. Install dependencies (FastAPI, LangGraph, Groq, Rich, etc.)
pip install -r requirements.txt

# 3. Start the Web Dashboard server
python server.py
```

Open your browser to: **[http://localhost:5000](http://localhost:5000)**

### What you can do in the Dashboard:
- **Interactive 5-Layer Flowchart**: Watch active glowing node transitions (`PLANNER ➔ SCOPE GUARD ➔ RUNNER ➔ REFLECTOR ➔ VERIFIER`) as the agent executes.
- **Mission Control**: Inspect real-time agent monologue, scope evaluation latency, sandboxed tool JSON output, and the isolated verification chamber.
- **Vulnerability Report**: View confirmed findings (Missing CSP, Missing HSTS, Clickjacking X-Frame-Options, Server Banner Disclosure) with CWE IDs, severity badges, and cryptographic SHA-256 evidence fingerprints.
- **False Positives Defeated**: Real-time counter of suspicious claims tested and rejected by the independent verifier.
- **Export**: One-click download of the complete engagement as an Executive Markdown Report or JSON audit bundle.
- **Settings Modal**: Configure your free Groq API key or OpenAI key directly in the UI.

---

## 💻 Alternative: Run in the Terminal (CLI)

Prefer running directly in your shell? The terminal agent uses `rich` formatting:

```bash
python agent.py
```

Output preview:
```text
🦊 Redfox AI Pen-Test Agent — Demo
Target: http://httpbin.org | Mode: LLM (Groq / LLaMA-3.3 70B)

[Step 1] 🧠 PLANNING
  Objective: Check which security headers are present or missing
  Tool     : check_security_headers

[Step 1] 🔒 SCOPE CHECK
  Checking : check_security_headers → http://httpbin.org
  ✅ ALLOW : Target http://httpbin.org is within authorized scope

[Step 1] ⚙️  EXECUTING
  Running check_security_headers on http://httpbin.org...
  → Missing headers: Content-Security-Policy, Strict-Transport-Security, X-Frame-Options
  → Server header disclosed: gunicorn/19.9.0

[Step 1] 🔍 REFLECTING
  → Reflector identified 4 suspected vulnerability claims

[Step 1] 🔬 VERIFYING (Independent Verifier)
  [1/4] Claim: Missing X-Frame-Options Header
        Independent isolated re-check in progress...
        ✅ CONFIRMED | Confidence: 95% | sha256:7f9a2b8c4d...

══════════════════════ ASSESSMENT COMPLETE ══════════════════════
Summary:
  Confirmed findings : 6
  Rejected (false +) : 0
  Evidence chain     : Cryptographic SHA-256 hashes generated
```

---

## 🔑 AI Reasoning Backends

You can choose your LLM provider by editing `.env` or entering keys in the Web Dashboard:

### Option 1: Groq (Recommended — FREE & Fast)
Get a free instant key at [console.groq.com/keys](https://console.groq.com/keys) and add to `.env`:
```bash
GROQ_API_KEY=gsk_your-groq-key-here
GROQ_MODEL=llama-3.3-70b-versatile
```

### Option 2: OpenAI
```bash
OPENAI_API_KEY=sk-your-openai-key-here
```

### Option 3: Deterministic Methodology (No API Key Required)
If no key is configured, the agent runs in **Deterministic Methodology Mode**. It uses the exact same LangGraph pipeline, scope guard, sandboxed tools, independent verifier, and finding lifecycle—guaranteeing 100% reliable execution out of the box.

---

## 📐 Architecture Mapping

| Component | File in `demo/` | Architecture Layer |
|-----------|-----------------|-------------------|
| **Web Cockpit UI** | `static/index.html`, `static/style.css`, `static/app.js` | **Layer 1:** Client & Operator Portal |
| **Telemetry Server** | `server.py` (FastAPI + SSE Stream) | **Layer 1:** API Gateway & Audit Feed |
| **Agent Reasoning Core**| `agent.py`, `runner.py` (LangGraph) | **Layer 2:** Cognitive Loop (Plan/Reflect) |
| **Deterministic Scope Guard** | `scope_guard.py` | **Layers 1 & 4:** Safety Policy Enforcement |
| **Independent Verifier** | `verifier.py` (Isolated Reproduction + SHA-256) | **Layer 3:** 0% False Positive Verification |
| **Sandboxed Tool Runners** | `tools.py` (`http_headers`, `dns_lookup`, etc.) | **Layer 4:** Execution Sandbox |
| **Engagement State** | `state.py` (TypedDict, no chat history) | **Layer 2 & 5:** Structured Blackboard Model |

---

## 🛡️ Authorized Targets

Always ensure you only target systems you are explicitly permitted to test:
- `http://httpbin.org`: Public HTTP testing service (default).
- `http://testphp.vulnweb.com`: Acunetix deliberately vulnerable web application for security scanner testing.
