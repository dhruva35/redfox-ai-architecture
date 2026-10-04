# AI Penetration Testing Architecture: A Plain-English Walkthrough

## The Problem We're Solving

Imagine Redfox gets hired to test a bank's website for security weaknesses. A senior tester sits down and spends a week:
1. Scanning the site for pages
2. Testing every input box for SQL injection
3. Trying different usernames and passwords
4. Checking if User A can read User B's data
5. Writing up all the bugs they found

This is skilled, expensive, and slow. The big idea of this platform is: **what if an AI agent could do steps 1-4 automatically, so the human tester only has to do step 5 (review and sign off)?**

---

## The 10 Layers, Top to Bottom

Think of the architecture like a restaurant. The **operator UI** is the dining room (what the customer sees). The **agent core** is the head chef. The **tools** are the kitchen equipment. The **safety layer** is the health inspector who must approve every dish before it goes out.

### Layer 1: Operator UI (The Dashboard)
The human tester opens a browser and sees a live dashboard. They can:
* Start a new assessment (e.g., "test `app.acme.com`")
* Watch what the AI is doing in real-time, step by step
* Click "Approve" or "Reject" when the AI wants to perform a risky action
* Review findings the AI discovered

*(Note: The AI engineer doesn't build this — the Full Stack Developer does, using the APIs we provide.)*

### Layer 2: API Gateway (The Front Door)
Every button the tester clicks in the dashboard sends a request to the **API gateway** (a FastAPI server). It handles:
* Login and authentication (ensuring only authorized testers can use the platform)
* Routing requests to the correct internal services
* Sending real-time event updates back to the dashboard via WebSocket (so the tester sees live step-by-step updates without refreshing the page)

### Layer 3: Orchestration (The Job Queue + Session Manager)
When a tester clicks "start an assessment," that job goes into a **queue** (Google Cloud Pub/Sub). This is like a ticket system at a deli counter — the queue ensures nothing gets lost even if the system is very busy.

The **Session Manager** picks up jobs from the queue and manages the lifecycle of each assessment session: creating it, pausing it, resuming it after a crash, and terminating it when finished.

*Why a queue?* If 5 assessments start at once, the queue spreads the load. If the agent service crashes mid-way, the session is checkpointed so it can be restarted from exactly where it left off.

### Layer 4: Agent Core (The Brain)
This is the centerpiece — a Python process built with **LangGraph**. It follows a continuous loop until its budget (time or steps) runs out:

`PLAN → SELECT ACTION → SCOPE CHECK → EXECUTE → PARSE OUTPUT → UPDATE STATE → REFLECT → (repeat)`

**Real-world Example (Testing `app.acme.com`):**

| Step | What the agent actually does |
| :--- | :--- |
| **PLAN** | "My next goal is to find all the pages on this website." |
| **SELECT ACTION** | "The right tool for this is `ffuf` (a directory brute-forcing tool)." |
| **SCOPE CHECK** | "Is `app.acme.com` in scope? Is brute-forcing allowed? Yes → proceed." |
| **EXECUTE** | Runs `ffuf` in a sandboxed container. The tool tries thousands of URL paths: `/admin`, `/login`, `/api`, etc. |
| **PARSE OUTPUT** | Converts the tool's raw JSON output into clean facts: "Found `/admin` (status 200), `/api/v1` (status 200), `/secret` (status 403)." |
| **UPDATE STATE** | Saves those facts to the database: 3 new endpoints discovered. |
| **REFLECT** | "I've now got an endpoint list. I see `/api/v1` — I should test that for injection vulnerabilities next." |

This loop runs automatically. The tester simply watches it happen live.

### Layer 5: Skills and Knowledge (The Training Manual)
The agent doesn't magically know how to test everything. It loads a **Skill Pack** — a YAML config file — at the start of each engagement. Think of it as a recipe book for that specific type of test:

* **Web App Skill Pack:** "Step 1: Map the application. Step 2: Test for SQL injection. Step 3: Test for XSS. Only use these tools: ffuf, sqlmap, nikto..."
* **Active Directory Skill Pack:** "Step 1: Enumerate users. Step 2: Look for Kerberoastable accounts. Only use these tools: bloodhound, impacket..."

At each step, the agent also performs a **RAG lookup** (Retrieval-Augmented Generation). It queries a knowledge base of security documents (OWASP guides, MITRE ATT&CK, CVE databases) to get relevant context. For example, before testing for SQL injection, it retrieves the OWASP SQL injection testing guide to inform its approach.

### Layer 6: The Model Layer (The Reasoning Engine)
The Agent Core uses **LLMs** (Large Language Models, like ChatGPT) for all its reasoning. But it doesn't use one single model for everything:

| Task | Model Used | Why? |
| :--- | :--- | :--- |
| **Planning** (what to do next) | GPT-4o or Gemini Pro | Requires complex reasoning. |
| **Parsing tool output** | GPT-4o-mini or Gemini Flash | Simple extraction; high volume means we use a cheaper model. |
| **Verifying a finding** | GPT-4o (different provider) | Requires an independent check and high quality. |

A **Model Gateway** sits in the middle. It handles choosing the right model, falling back to another provider if one goes down, enforcing that outputs come back as structured JSON (not just free text), and tracking costs.

### Layer 7: Safety Layer (The Health Inspector)
This is the feature that separates a trustworthy professional tool from a dangerous toy.

**Every single action the agent proposes** — before it is executed — goes through a **Scope Guard**. This is deterministic Python code (no AI involved). It checks a strict checklist:

1. Is the target (`app.acme.com`) on the approved list? (✅)
2. Is the target in the exclusion list? (❌)
3. Is it within the testing hours (e.g., Mon-Fri 9am-6pm)? (✅)
4. Is this action's risk level below the engagement limit? (✅)

If any check fails, the action is **DENIED**. The AI cannot talk its way past this. The agent can *ask* for something, but the Scope Guard decides.

Higher-risk actions (like actually trying to exploit a database) go to the **Approval Gate**, which pauses the agent and sends a notification to the tester's dashboard. The tester reads the proposed action and clicks Approve or Reject.

### Layer 8: Execution Layer (The Sandboxed Kitchen)
When an action is approved, the tool runs inside an **ephemeral container** (a Docker container that exists only for that one execution and is destroyed immediately afterwards). This container:

* Has **hard resource limits** (e.g., max 1 CPU core, 512MB RAM).
* Has **no internet access** except to the approved target IPs.
* Cannot reach other parts of the platform (it can't read the main database or access other clients' data).
* Has its output files captured and saved to Cloud Storage before the container is destroyed.

### Layer 9: Evaluation Layer (The Test Kitchen)
This is how we prove the AI is actually good at its job. We maintain **intentionally vulnerable applications** — websites designed to be insecure for training purposes (e.g., OWASP Juice Shop, DVWA). We know exactly what vulnerabilities exist in them.

We run the AI against these test targets and measure the results: Did it find 70% of the known bugs? Did it produce any false alarms? How fast was it? This gives us concrete numbers to track over time. If we update a prompt or change an LLM and the detection rate drops, our automated CI pipeline catches it and blocks the change.

### Layer 10: Observability (The Security Cameras)
Every single thing the agent does is logged in detail: every tool call, every model request, every approval decision, and every finding (along with timestamps and cryptographic hashes). This is stored in an **append-only** database table (you can only add new rows, never change or delete existing ones).

This serves two crucial purposes:
1. **Operations:** You can diagnose exactly what went wrong if the agent behaves unexpectedly.
2. **Legal/Audit:** If a client ever disputes what was tested or how it was tested, you have an immutable, tamper-evident record.

---

## The Verifier: The Most Innovative Feature

When the agent thinks it found a vulnerability (e.g., "I found a SQL injection on the search bar"), it doesn't just report it. It sends a **verification request** to a completely separate process — the **Verifier**.

The Verifier:
* Receives only the basic claim ("SQL injection found at `/search?q=`") and the evidence (the raw tool output).
* **Cannot see the main agent's reasoning** (it doesn't know *why* the main agent thinks this is a bug).
* Tries to reproduce the vulnerability independently, ideally using a different method.
* If it successfully reproduces it → **CONFIRMED** ✅
* If it cannot reproduce it → **REJECTED** or sent to human review ⚠️

*Why does this matter?* LLMs can hallucinate. They will confidently claim something is a vulnerability when it isn't. Sending false bug reports to clients destroys a security firm's credibility. The Verifier acts like a peer reviewer in science: you must reproduce the result before it becomes an official finding.

---

## Where This All Runs (GCP Deployment)

Everything is designed to run on Google Cloud Platform (GCP):

* The API gateway, Agent service, Verifier, and RAG service → **Cloud Run** (serverless containers; scales to zero when idle to save money).
* The tool runner pods → **GKE Autopilot** (Kubernetes; necessary because we need the fine-grained network control to restrict egress traffic to in-scope IPs only).
* Database + vector store → **Cloud SQL with pgvector extension** (one PostgreSQL instance handles both the structured engagement state AND the semantic vector search for the RAG).
* Evidence files → **Cloud Storage**.
* Secrets (API keys, client credentials) → **Secret Manager**.
* Real-time events and job queues → **Pub/Sub**.

---

## The Complete Flow (In One Sentence)

> Tester clicks Start → job queued → session manager creates session → loads web_app skill pack → agent plans: "map the site first" → scope guard approves → ffuf runs in sandboxed container → output parsed into 45 endpoints → agent reflects: "I see `/api/v1/users?id=1`, this smells like IDOR" → creates hypothesis → tests it with httpx → confirms user 1 can read user 2's data → sends to verifier → verifier independently reproduces it → CONFIRMED finding generated with CVSS score, evidence hash, and reproduction steps → tester reviews → agent continues to next hypothesis → repeats until 200 steps or 4 hours → summary generated.
