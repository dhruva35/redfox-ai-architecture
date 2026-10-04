"""
state.py — The Engagement State Model

ARCHITECTURE CONCEPT:
    Instead of using chat history to track what the agent knows,
    we maintain a TYPED, STRUCTURED state model.

    Why? Three reasons:
    1. Chat history grows forever and eventually exceeds the LLM context window,
       causing the agent to "forget" things discovered early in the engagement.
    2. Important facts (like discovered credentials or open ports) can get buried
       in a wall of text and the LLM might miss them.
    3. A typed model is queryable, serializable, and survives crashes.
       Chat history is none of these things.

    In production, this state is stored in PostgreSQL and checkpointed
    after every step so the agent can be restarted from where it left off.
"""

from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    """
    The complete, typed state of one assessment session.
    LangGraph nodes read from this and return partial updates to it.

    Think of it like a "blackboard" — every component reads from it
    and writes back to it. Nothing is stored in anyone's local memory.
    """

    # ── Engagement metadata ─────────────────────────────────────────────────
    engagement_id: str          # Unique ID for this assessment
    target: str                 # Primary target URL
    scope: List[str]            # Allowed targets (scope guard reads this)
    assessment_type: str        # "web_app", "api", "network", etc.

    # ── Budget & progress ────────────────────────────────────────────────────
    step_number: int            # Current step (increments each loop)
    max_steps: int              # Hard stop — agent cannot exceed this
    done: bool                  # True = agent should stop
    stop_reason: str            # Why did the agent stop?

    # ── Accumulated discoveries (grow across steps) ──────────────────────────
    assets: List[dict]          # Discovered URLs, endpoints, hosts
    observations: List[dict]    # Raw observations from tool outputs

    # ── Findings (lifecycle: suspected → verified → confirmed/rejected) ──────
    suspected_findings: List[dict]   # Waiting for verification
    confirmed_findings: List[dict]   # Verified as real — will appear in report
    rejected_findings: List[dict]    # Verified as false positives

    # ── Current step context (reset each loop) ───────────────────────────────
    current_objective: str           # What the agent is trying to do THIS step
    last_tool_name: Optional[str]    # Tool the planner chose
    last_tool_input: Optional[dict]  # Input to that tool
    last_tool_output: Optional[dict] # Raw output from the tool

    # ── Approval gate state ──────────────────────────────────────────────────
    pending_approval: Optional[dict] # Set when an action needs human approval
