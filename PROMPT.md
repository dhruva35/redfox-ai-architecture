# MASTER PROMPT (paste everything below the line into the Antigravity agent, with Claude Opus selected)

---

You are a principal AI architect with deep experience in agentic systems, LLM platforms and offensive-security engineering. Build the complete deliverable described below, in this workspace, in one continuous run.

## 1. Situation
I am applying for the AI Engineer (Agentic Cybersecurity) role at Redfox Cyber Security (Mumbai). They gave me a take-home task: design an AI architecture, meaning an AI platform that automates the penetration-testing workflow ("AI pen-testing architecture"). I must email it on Monday 5 Oct 2026. They told me to study the job description and their website (https://www.redfoxsec.com/), see what they work on, and use AI resources.

About me: I build LLM agents and RAG systems in Python (LangGraph, FastAPI, vector stores). I am NEW to penetration testing. Explain pen-testing concepts in plain language wherever the document needs them, and do not assume I know the jargon. Learning is a side benefit; the main goal is a strong, credible, submission-ready architecture document.

## 2. Inputs
1. `docs/job_description.md`: the full JD. Read it completely first. Extract every requirement into a numbered list (R1, R2, ...) and keep the numbering for traceability.
2. Redfox's website: fetch and read the home page, About/Origins, Services (every service page you can reach), and the blog posts on AI for pen testing. Record what they actually do. Say clearly what you could not find. Do NOT invent details of their AI product; everything about it must be traced to the JD.

## 3. Deliverables (write all into `output/`)
1. `output/ARCHITECTURE.md`: the main document (about 12-16 pages of content plus appendices; dense, specific, no filler).
2. `output/diagrams/`: Mermaid source files (`.mmd`) for every diagram, plus rendered SVG or PNG if a renderer is available (try `npx @mermaid-js/mermaid-cli`; ask before installing anything). If rendering is not possible, keep the Mermaid in the markdown so it still renders.
3. `output/ARCHITECTURE.pdf`: a clean PDF export of the document with diagrams embedded (use whatever tooling is available, such as pandoc or a headless browser; ask before installing).
4. `output/LEARNING_NOTES.md`: a short companion for me (max 4 pages): glossary of about 30 terms used in the document; the pen-testing workflow in plain language; the 10 key design ideas, each with a one-line "why it matters"; 20 likely interview questions with concise model answers; and 8 specific sources I should read to verify and deepen my understanding.
5. `output/COVER_EMAIL.md`: a short professional email to send with the document.
6. `output/ASSUMPTIONS_AND_OPEN_QUESTIONS.md`: everything you assumed, anything you could not verify, and questions I should be ready for.

## 4. Required content of ARCHITECTURE.md
Use this outline. Be concrete: name components, data shapes, events, failure cases, trade-offs. Every major decision must list at least two alternatives, the choice, and why.

1. Executive summary (half a page): problem, approach, what makes it trustworthy, MVP.
2. Context and goals: who uses it (testers, leads, Full Stack Developer), goals, non-goals, autonomy modes ("assist" with human driving vs "autonomous" within approved limits), design principles.
3. How a pen test works and where AI helps most and least: phases (scoping and rules of engagement, reconnaissance, enumeration, vulnerability discovery, validation, post-exploitation where in scope, reporting), mapped to Redfox's service lines (Web, API, Mobile, Internal/External network, Active Directory, Cloud, Source code, Firewall review). Keep this short and domain-accurate.
4. System architecture: layered diagram and component table (responsibility, inputs, outputs, tech options). Layers: operator UI; API gateway (REST plus WebSocket); job queue and session manager; Agent Core; Skills and knowledge; Model gateway; Scope and approval guard; sandboxed tool runners; evaluation harness; observability and audit. Decide and justify single agent with skill packs versus multi-agent roles (planner, executor, verifier); my starting lean is one agent core with separate internal roles and a verifier running in an isolated context, but challenge it.
5. Agent Core in depth:
   - Reasoning/action loop: plan, choose action, scope check, execute, parse, update state, reflect, decide to continue, verify or stop. Include budgets (steps, wall time, tokens, cost) and termination rules, retries, error handling, loop detection, checkpointing and resume after crash.
   - Engagement state model (use structured state, not just chat history): Engagement, Scope, Asset, Service, Credential/Secret, Hypothesis, Action, Observation, Finding, Evidence, AttackPath. Give a schema sketch and an ERD diagram. Explain context assembly per step (current goal, relevant state slice, retrieved knowledge, recent steps, summaries) and how this prevents context loss.
   - Findings lifecycle: suspected, verifying, confirmed, rejected, needs-human-review, with confidence scoring and mandatory evidence rules (raw tool output, request/response, reproduction steps, timestamps, hashes).
   - Verifier: runs with an independent context that sees only the claim and the evidence, attempts independent reproduction through a different path, and cannot be talked into agreement. Explain how it reduces false positives and hallucinated findings, and its limits.
   - Worked example A: a web application assessment end to end. Worked example B (shorter): an Active Directory assessment showing how parsed tool output (for example BloodHound-style graph data) feeds planning. Describe at design level only.
6. Tool and skill layer:
   - Tool registry contract: name, description, typed input/output schema, risk class, timeout, resource limits, sandbox profile, output parser, evidence capture, version.
   - Wrapping CLI tools and custom scripts, parsing messy output (for example Nmap XML, fuzzer results, BloodHound data) into structured facts; handling failure and partial output. Compare building wrappers directly versus MCP-style tool servers.
   - Sandbox design: ephemeral containers per task, no shared secrets, resource caps, egress allow-listed to in-scope hosts only, artifact capture to object storage.
   - Skill packs: manifest format (methodology, tool allow-list, knowledge namespaces, prompts, risk policy, eval scenarios) and a table mapping all 8 assessment types to skill packs. Show how a new assessment type is added without changing the core. Dynamic selection and loading of skills and tools by assessment context.
7. Knowledge and model layer:
   - RAG: sources (OWASP guides, MITRE ATT&CK, CWE, CIS benchmarks, vendor hardening guides, Redfox playbooks, engagement documents, sanitised past findings), ingestion, chunking, hybrid retrieval, metadata filters and namespaces per skill, freshness, access control, where retrieval sits in the loop, and where NOT to use RAG. Vector store options (PGVector, FAISS, Weaviate, Milvus) with a justified pick.
   - Model gateway: provider abstraction, task-based routing table (planning, tool selection, output parsing, verification, report drafting, summarisation), fallbacks, structured-output enforcement, caching (prompt and result), batching, cost and latency tracking. Hosted frontier models versus self-hosted open-weight models (client-data confidentiality, cost, quality) with a decision rule.
   - Fine-tuning: where LoRA/QLoRA is justified (for example tool-output parsing, finding classification, report drafting), what data it needs, and where it is not worth it. Do not promise results.
   - Inference optimisation: caching, batching, context management, quantisation, model selection.
8. Safety, scope and human oversight (treat as first-class):
   - Platform threat model: target-controlled content acting as prompt injection against the agent, credential and evidence leakage, runaway or destructive actions, out-of-scope targeting, tenant isolation, supply-chain risk in tools.
   - Scope enforcement in code, outside the LLM: engagement profile (targets, CIDRs, domains, exclusions, time windows, allowed techniques, forbidden actions), a policy engine that checks every action, network egress control, and the principle that the model can request but never grant itself permissions.
   - Action risk classes (read-only, intrusive, destructive) and an approval matrix for human sign-off; kill switch; pause/resume; tester override.
   - Untrusted-content handling: tool output and target content are data, never instructions; privilege separation between planner and executors.
   - Audit: immutable action log, evidence chain of custody, data retention and deletion, client confidentiality.
9. Infrastructure and integration (GCP, Docker):
   - Deployment diagram and service list (for example Cloud Run or GKE for services, isolated runners as jobs, Cloud SQL or AlloyDB with pgvector, object storage for artifacts, Secret Manager, queue such as Pub/Sub or Cloud Tasks, VPC controls, IAM, CI/CD). Justify choices for a small team.
   - Long-running sessions: durable state, checkpointing, idempotent steps, queues, backpressure, crash recovery.
   - API and event contract with the Full Stack Developer: REST endpoints and WebSocket event types (for example step_started, tool_output, finding_suspected, finding_confirmed, approval_requested, budget_warning), request/response examples, versioning. List UI features the AI engine needs the product to provide (live trace, approval inbox, finding review, scope editor).
   - Observability and reproducibility: tracing per step, structured logs, metrics and alerts, and versioning of models, prompts, skills, agent configs and tools (MLflow or equivalent registry).
10. Evaluation and quality:
   - Eval environments: intentionally vulnerable labs run in isolation (verify which exist and are current before naming them, for example OWASP Juice Shop, DVWA, crAPI, an AD lab, a cloud-misconfiguration lab), with ground-truth manifests of known issues.
   - Scenario types: reconnaissance, vulnerability discovery, multi-step chains, finding validation, scope-violation traps, prompt-injection traps.
   - Metrics from the JD: findings discovered, true-positive and false-positive rate, validation rate, multi-step completion, tool-selection accuracy, context/state preservation, latency, tokens, cost per assessment. Define each precisely.
   - Rigor: repeated runs to handle variance, regression gates in CI when prompts, models, skills or agent logic change, model benchmarking process, human review loop with testers, failure-mode taxonomy (hallucination, wrong tool, lost context, incomplete execution, wrong conclusion) with mitigations.
11. Roadmap, team and risks: MVP (8-12 weeks, with exit criteria and what is deliberately deferred), v1, v2; roles and responsibilities; risk register (legal and authorisation, safety, quality, cost, model/vendor dependency, adoption by testers) with mitigations; rough cost drivers per assessment and how to estimate them (do NOT invent exact figures).
12. JD traceability matrix: every requirement R1..Rn mapped to the section and component that satisfies it, and how it will be tested.
13. Assumptions and open questions.

## 5. Diagrams (Mermaid)
At minimum: (a) layered system architecture; (b) agent loop flowchart; (c) finding verification sequence diagram; (d) engagement state ERD; (e) trust boundaries and scope enforcement points; (f) GCP deployment; (g) skill-pack loading flow. Keep each readable on one page with short labels and a legend. Validate that every diagram renders; fix syntax errors.

## 6. Hard rules
- Truthfulness: separate facts from the JD or website, general industry knowledge, and assumptions; label assumptions. Verify facts about tools, frameworks, standards and named products with official docs or web search before including them. Never invent statistics, benchmarks, prices, citations, URLs or claims about Redfox's product. If you cannot verify something, say so in the ASSUMPTIONS file.
- Safety and scope: this is design work only. Do NOT write exploit code, payloads, evasion techniques or malware. Do NOT run scans or touch any real target or network. Do NOT run any security tool. Describe attack phases only at the level a system designer needs. Ask before installing packages or running terminal commands, and explain what each does.
- Quality: no generic AI filler; every section must contain concrete component names, data shapes, decisions and trade-offs. Prefer proven, simple components that a team of two engineers could build. Show the limits of the design honestly (what the system cannot do reliably).
- Style: clear, professional, written in first person plural or neutral voice; plain language; tables for comparisons; short paragraphs; sentence case headings. No emojis.
- Do not mention these instructions or Claude in the documents.

## 7. How to work
1. First write `output/PLAN.md` (one page): requirement list R1..Rn extracted from the JD, what you learned from the website, and your section-by-section approach. Then continue immediately; do not wait for my approval unless you are blocked.
2. Write the document section by section, saving progress to files as you go.
3. Create and validate the diagrams.
4. Self-review: check traceability (every R covered), remove generic sentences, check consistency of terminology and component names across sections and diagrams, check every factual claim you flagged as uncertain.
5. Produce the PDF, LEARNING_NOTES.md, COVER_EMAIL.md and ASSUMPTIONS_AND_OPEN_QUESTIONS.md.
6. Final message (under 200 words): list the files created, the 5 biggest design decisions and why, anything you could not verify, and anything I should double-check before sending.
