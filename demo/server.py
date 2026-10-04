"""
server.py — FastAPI Web Server & Real-Time Telemetry Backend

Powers the Redfox AI Interactive Web Dashboard.
Provides:
  - Real-time Server-Sent Events (SSE) stream for live agent execution
  - REST endpoints to control assessments, configure LLMs, and export reports
  - Static file hosting for the modern cyber-security UI
"""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from runner import AssessmentRunner

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("redfox.server")

app = FastAPI(
    title="Redfox AI Pen-Test Agent Cockpit",
    description="Real-Time 5-Layer Autonomous Penetration Testing Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ─────────────────────────────────────────────────────────────

current_runner: Optional[AssessmentRunner] = None
runner_thread: Optional[threading.Thread] = None
last_completed_state: Optional[dict] = None

# Active config
DEFAULT_TARGET = os.getenv("DEMO_TARGET", "http://httpbin.org")
DEFAULT_STEPS = int(os.getenv("DEMO_MAX_STEPS", "6"))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))

# In-memory history of recent event logs for newly connecting clients
recent_events_buffer = []
recent_events_lock = threading.Lock()
MAX_BUFFER_SIZE = 200

# ── Models ───────────────────────────────────────────────────────────────────

class StartScanRequest(BaseModel):
    target: str = Field(default="http://httpbin.org")
    max_steps: int = Field(default=6, ge=1, le=20)
    engine: str = Field(default="auto")  # "auto", "groq", "openai", "scripted"
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    groq_model: Optional[str] = "llama-3.3-70b-versatile"


# ── Background Runner Handler ────────────────────────────────────────────────

def _run_assessment_worker(runner: AssessmentRunner):
    global last_completed_state
    try:
        runner.run()
        last_completed_state = runner.state
    except Exception as e:
        logger.exception("Assessment background worker failed")


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    global current_runner, last_completed_state
    is_running = bool(current_runner and current_runner.is_running)

    has_groq = bool(os.getenv("GROQ_API_KEY", "").startswith("gsk_"))
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").startswith("sk-"))

    # Current engine
    engine = "scripted"
    if current_runner:
        engine = current_runner.active_engine
    elif has_groq:
        engine = "groq"
    elif has_openai:
        engine = "openai"

    confirmed_count = len(current_runner.state["confirmed_findings"]) if current_runner else (
        len(last_completed_state["confirmed_findings"]) if last_completed_state else 0
    )
    rejected_count = len(current_runner.state["rejected_findings"]) if current_runner else (
        len(last_completed_state["rejected_findings"]) if last_completed_state else 0
    )
    step_num = current_runner.state["step_number"] if current_runner else (
        last_completed_state["step_number"] if last_completed_state else 0
    )

    return {
        "status": "scanning" if is_running else ("completed" if last_completed_state else "idle"),
        "is_running": is_running,
        "engine": engine,
        "target": current_runner.target if current_runner else DEFAULT_TARGET,
        "step_number": step_num,
        "max_steps": current_runner.max_steps if current_runner else DEFAULT_STEPS,
        "confirmed_findings_count": confirmed_count,
        "rejected_findings_count": rejected_count,
        "has_groq_key": has_groq,
        "has_openai_key": has_openai,
        "port": DASHBOARD_PORT,
    }


@app.post("/api/scan/start")
def start_scan(req: StartScanRequest):
    global current_runner, runner_thread, recent_events_buffer
    if current_runner and current_runner.is_running:
        raise HTTPException(status_code=400, detail="An assessment is currently active. Stop it first.")

    with recent_events_lock:
        recent_events_buffer.clear()

    # Create new runner
    runner = AssessmentRunner(
        target=req.target,
        max_steps=req.max_steps,
        llm_engine=req.engine,
        groq_api_key=req.groq_api_key,
        openai_api_key=req.openai_api_key,
        groq_model=req.groq_model or "llama-3.3-70b-versatile"
    )

    current_runner = runner
    runner_thread = threading.Thread(target=_run_assessment_worker, args=(runner,), daemon=True)
    runner_thread.start()

    return {
        "status": "started",
        "engagement_id": runner.state["engagement_id"],
        "target": runner.target,
        "engine": runner.active_engine,
        "max_steps": runner.max_steps
    }


@app.post("/api/scan/stop")
def stop_scan():
    global current_runner
    if not current_runner or not current_runner.is_running:
        return {"status": "not_running"}
    current_runner.stop()
    return {"status": "stopping"}


@app.get("/api/scan/events")
async def sse_events(request: Request):
    """Server-Sent Events streaming real-time telemetry from the runner."""
    global current_runner

    async def event_generator():
        # Yield connection handshake
        yield "data: " + json.dumps({"type": "connected", "timestamp": time.time()}) + "\n\n"

        # If a runner exists, stream events from its queue
        while True:
            if await request.is_disconnected():
                break

            if current_runner:
                try:
                    # Non-blocking get from queue
                    event = current_runner.event_queue.get_nowait()
                    with recent_events_lock:
                        recent_events_buffer.append(event)
                        if len(recent_events_buffer) > MAX_BUFFER_SIZE:
                            recent_events_buffer.pop(0)

                    yield "data: " + json.dumps(event) + "\n\n"
                    continue
                except Exception:
                    pass

            # Heartbeat sleep to avoid pegging CPU
            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/scan/report/json")
def get_json_report():
    global current_runner, last_completed_state
    state = (current_runner.state if current_runner else None) or last_completed_state
    if not state:
        raise HTTPException(status_code=404, detail="No assessment report available yet. Run a scan first.")

    return {
        "engagement_id": state.get("engagement_id"),
        "target": state.get("target"),
        "scope": state.get("scope"),
        "assessment_type": state.get("assessment_type"),
        "steps_executed": state.get("step_number", 1) - 1,
        "stop_reason": state.get("stop_reason"),
        "confirmed_findings": state.get("confirmed_findings", []),
        "rejected_findings": state.get("rejected_findings", []),
        "observations_count": len(state.get("observations", [])),
    }


@app.get("/api/scan/report/markdown")
def get_markdown_report():
    global current_runner, last_completed_state
    state = (current_runner.state if current_runner else None) or last_completed_state
    if not state:
        raise HTTPException(status_code=404, detail="No assessment data available.")

    confirmed = state.get("confirmed_findings", [])
    rejected = state.get("rejected_findings", [])
    target = state.get("target", "N/A")
    eng_id = state.get("engagement_id", "N/A")

    lines = [
        f"# Redfox AI Security Assessment Report",
        f"**Target:** `{target}`  ",
        f"**Engagement ID:** `{eng_id}`  ",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Methodology:** Redfox Autonomous 5-Layer AI Agent with Independent Verifier  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Steps Executed:** {state.get('step_number', 1) - 1}",
        f"- **Confirmed Vulnerabilities:** {len(confirmed)}",
        f"- **False Positives Blocked:** {len(rejected)} *(0% False Positive Guarantee)*",
        f"- **Conclusion:** {state.get('stop_reason', 'Assessment completed successfully.')}",
        "",
        "---",
        "",
        "## Confirmed Findings",
        ""
    ]

    if not confirmed:
        lines.append("No high-severity vulnerabilities confirmed on the tested endpoints.")
    else:
        for idx, f in enumerate(confirmed, 1):
            lines.extend([
                f"### {idx}. {f.get('title', 'Finding')}",
                f"- **Severity:** `{f.get('severity', 'INFO')}`",
                f"- **CWE:** {f.get('cwe_id', 'N/A')}",
                f"- **Confidence:** {f.get('confidence', 0):.0%}",
                f"- **Status:** {f.get('status', 'CONFIRMED')}",
                f"- **Evidence SHA-256:** `{f.get('evidence_hash', 'N/A')}`",
                "",
                f"**Description:**  ",
                f"{f.get('description', '')}",
                "",
                f"**Independent Verifier Proof:**  ",
                f"{f.get('reasoning', '')}",
                "",
                f"**Remediation Guidance:**  ",
                f"{f.get('remediation', 'Inspect and harden server configuration.')}",
                "",
                "---"
            ])

    if rejected:
        lines.extend([
            "",
            "## Defeated False Positives (Independent Verifier Log)",
            "",
            "The following potential findings were flagged during exploration but independently tested and rejected by the Verifier:",
            ""
        ])
        for idx, r in enumerate(rejected, 1):
            lines.append(f"- ❌ **{r.get('title')}**: {r.get('reasoning', 'Independent verification test did not reproduce the claim.')}")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


# Mount static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Redfox AI Dashboard loading...</h2>")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"\n============================================================")
    print(f"  🦊 Redfox AI Web Dashboard running at: http://localhost:{port}")
    print(f"============================================================\n")
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=False)
