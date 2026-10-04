# Learning notes: AI-powered penetration-testing architecture

A companion guide for understanding the architecture document and preparing for the interview.

---

## 1. Glossary (30 terms)

| Term | Plain-language meaning |
|------|----------------------|
| **Penetration test (pen test)** | A controlled, authorised attack on a computer system to find security weaknesses before real attackers do. Think of hiring someone to try to break into your house so you can fix the locks. |
| **Rules of engagement (RoE)** | The agreed-upon rules for a pen test: what can be tested, what cannot, when testing happens, and what actions are off-limits. Like a contract before the "break-in." |
| **Reconnaissance (recon)** | The first phase of testing: gathering information about the target (domain names, IP addresses, technologies used) without directly attacking it. |
| **Enumeration** | Actively probing the target to discover open ports, running services, and their versions. More direct than recon but still gathering information, not attacking. |
| **Vulnerability** | A weakness in a system that an attacker could exploit. For example, a web form that does not properly check user input. |
| **Exploitation** | Actually using a vulnerability to demonstrate its impact, like extracting data through a SQL injection. |
| **Post-exploitation** | After gaining initial access, exploring how far an attacker could go: accessing other systems, escalating privileges, reaching sensitive data. |
| **OWASP** | Open Worldwide Application Security Project. A non-profit that publishes guides and standards for web security, including the famous "Top 10" list of web vulnerabilities. |
| **OWASP Top 10** | A ranked list of the ten most critical web application security risks (for example, injection, broken access control). Updated periodically. |
| **MITRE ATT&CK** | A knowledge base of adversary tactics and techniques based on real-world observations. Organises attack techniques into categories (reconnaissance, initial access, privilege escalation, etc.). |
| **CWE (Common Weakness Enumeration)** | A standardised dictionary of software weakness types. Each weakness has an ID (like CWE-89 for SQL injection). Used to consistently label what type of vulnerability was found. |
| **CVE (Common Vulnerabilities and Exposures)** | A list of publicly known security vulnerabilities, each with a unique ID (like CVE-2024-12345). Used to identify specific bugs in specific software versions. |
| **CVSS (Common Vulnerability Scoring System)** | A standardised system for rating the severity of vulnerabilities on a 0-10 scale, based on factors like how easy it is to exploit and what damage it can cause. |
| **SQL injection (SQLi)** | A vulnerability where an attacker inserts malicious database commands through a web form or URL parameter. For example, entering `' OR 1=1 --` into a login form. |
| **XSS (Cross-site scripting)** | A vulnerability where an attacker injects malicious JavaScript into a web page that other users see, potentially stealing their session cookies. |
| **IDOR (Insecure Direct Object Reference)** | A vulnerability where changing a number in a URL (like `/user/123` to `/user/124`) lets you access another user's data because the application does not check permission. |
| **Active Directory (AD)** | Microsoft's system for managing users, computers, and permissions in a corporate network. A common target because compromising AD can give access to everything. |
| **Kerberoasting** | An Active Directory attack where you request encrypted service tickets and try to crack the passwords offline. Works because some service accounts have weak passwords. |
| **BloodHound** | A tool that maps relationships in Active Directory (who can access what, who has admin rights where) and finds attack paths from a low-privilege user to domain admin. |
| **Nmap** | A widely used network scanning tool that discovers hosts, open ports, and running services on a network. |
| **RAG (Retrieval-Augmented Generation)** | A technique where an LLM retrieves relevant documents from a knowledge base before generating its answer. Instead of relying only on its training data, it looks up current, specific information. |
| **Vector database** | A database optimised for storing and searching embeddings (numerical representations of text). Used in RAG to find documents that are semantically similar to a query. |
| **Embedding** | A numerical representation of text as a list of numbers (a vector) that captures its meaning. Similar texts have similar embeddings, enabling semantic search. |
| **LoRA (Low-Rank Adaptation)** | A technique for fine-tuning a large language model efficiently by training only a small set of additional parameters rather than the entire model. Requires much less GPU memory and data. |
| **Prompt injection** | An attack where malicious text in the input tricks an LLM into ignoring its instructions and doing something else. In this platform, target-controlled content (HTML, headers) could try this. |
| **Scope guard** | The component in our architecture that checks every action against the engagement's rules before allowing execution. It is deterministic code, not an LLM. |
| **Skill pack** | A YAML configuration file that adapts the agent for a specific assessment type (web, API, network, etc.) by specifying methodology, tools, knowledge, and prompts. |
| **MCP (Model Context Protocol)** | An emerging standard for how LLMs interact with external tools. Provides a standardised interface for tool discovery and execution. |
| **Idempotent** | An operation that produces the same result no matter how many times you run it. Important for crash recovery: if a step is replayed, it should not cause duplicate actions. |
| **Kill switch** | An immediate stop mechanism that terminates all agent activity. The tester can activate it at any time through the UI. |

---

## 2. The pen-testing workflow in plain language

Imagine you are testing the security of a company's website:

1. **You agree on the rules** (scoping): You and the company decide what you will test (their main website, their API), what you will not test (their production database), and when you can test (weekdays, business hours only). This is a legal agreement.

2. **You gather information** (reconnaissance): Without touching the target yet, you look up the company's domain names, find their IP addresses, check what technologies they use (Is it built with Django? React? Running on nginx?), and search for any leaked credentials.

3. **You scan the target** (enumeration): Now you actively probe the target. You scan for open ports (Is port 443 open? Port 22?), discover what software is running on each port, and map out all the website's pages and API endpoints.

4. **You look for weaknesses** (vulnerability discovery): You test each endpoint for common vulnerabilities. Can you inject SQL code? Can you access other users' data by changing an ID in the URL? Are there default passwords? Is sensitive information exposed in error messages?

5. **You prove the weaknesses are real** (validation): For each potential vulnerability, you carefully demonstrate it. If you found SQL injection, you show you can extract a single test record, not dump the entire database. You need proof, not just a scanner's guess.

6. **You explore the impact** (post-exploitation): If you gained access, you carefully explore what an attacker could do. Could they reach the internal network? Could they access the admin panel? You document the potential impact.

7. **You write it up** (reporting): You produce a detailed report for the company: what you found, how severe it is, proof that it is real, and how to fix it. This is what the client actually pays for.

The AI platform automates steps 2-5 most effectively and assists with 6-7.

---

## 3. The 10 key design ideas and why they matter

| # | Design idea | Why it matters |
|---|-------------|---------------|
| 1 | **Structured state model, not chat history** | Chat history grows without bound and loses important early information. A typed data model (assets, services, findings) lets the agent access any discovered information at any time, surviving crashes and context window limits. |
| 2 | **Independent verifier with isolated context** | The biggest risk with LLM-based pen testing is hallucinated findings: the model claims it found a vulnerability that does not exist. Running verification in a separate process that cannot see the original reasoning forces genuine reproduction. |
| 3 | **Scope enforcement outside the LLM** | If you ask an LLM "should I scan this target?" it might say yes even if it is out of scope. The scope guard is deterministic code that checks every action against explicit rules. The LLM cannot override it. |
| 4 | **Skill packs for extensibility** | Instead of modifying the agent's code for each assessment type, a YAML manifest specifies the methodology, tools, knowledge, and prompts. Adding a new assessment type is a configuration change, not a code change. |
| 5 | **Task-based model routing** | Different LLM tasks have very different quality and cost profiles. Using a frontier model for planning but a cheaper model for output parsing can reduce costs by 3-5x without quality loss. |
| 6 | **Sandboxed tool execution** | Pen-testing tools can be dangerous. Running each tool in an ephemeral container with network restrictions ensures a bug or misconfiguration cannot affect the platform or out-of-scope systems. |
| 7 | **Evidence chain of custody** | Every finding needs proof: raw tool output, request/response pairs, timestamps, cryptographic hashes. Without this, findings are just claims. The audit trail also protects against legal disputes about what was tested. |
| 8 | **Budget-limited execution** | Without hard limits on steps, time, tokens, and cost, an agent could run forever or spend unlimited money. Budgets force the agent to be efficient and protect against runaway costs. |
| 9 | **Assist mode and autonomous mode** | Not all testers will trust AI to act independently on day one. Assist mode lets the human drive while getting AI suggestions. As trust builds, they can switch to autonomous mode for routine tasks. |
| 10 | **Evaluation against known-vulnerable labs** | You cannot improve what you cannot measure. Running the agent against intentionally vulnerable applications with known answers lets you track quality over time and catch regressions when you change prompts or models. |

---

## 4. Twenty likely interview questions with concise answers

**Q1: How does the agent decide what to do next?**
The agent follows a plan-act-observe-reflect loop. At each planning step, it looks at the current engagement state (what has been discovered so far), the methodology from the skill pack (what steps remain), and relevant knowledge from RAG. It selects the next objective and the best tool for that objective. Every proposed action is checked by the scope guard before execution.

**Q2: How do you prevent the agent from attacking out-of-scope systems?**
Three independent layers: (1) the scope guard checks every action against the engagement profile; (2) network-level egress control restricts tool runner containers to in-scope IPs only; (3) the VPC firewall provides a third layer. The LLM can propose but cannot bypass deterministic code.

**Q3: How do you handle false positives?**
An independent verifier process receives only the claim and evidence, attempts to reproduce the finding through a different path, and cannot see the agent's reasoning. Findings that fail verification are rejected or sent to human review. A confidence scoring system also flags low-confidence findings.

**Q4: Why structured state instead of conversation history?**
Conversation history hits context window limits, loses early information, and mixes reasoning with facts. Structured state (a database of assets, services, credentials, findings) is queryable, persistent, and allows selective context assembly at each step.

**Q5: How do you support different assessment types?**
Skill packs: YAML manifests that specify methodology, allowed tools, knowledge namespaces, prompts, and risk policies for each assessment type. Adding a new type means writing a new manifest and tool wrappers, not modifying the agent core.

**Q6: How would you route different tasks to different models?**
The model gateway has a routing table: planning uses a frontier model (strong reasoning), output parsing uses a cheaper model (structured extraction), verification uses a frontier model from a different provider (independence). The gateway handles fallbacks and structured output enforcement.

**Q7: How do you handle tool output that is messy or unstructured?**
Each tool has a dedicated output parser. Well-structured outputs (Nmap XML, ffuf JSON) are parsed with schema-based parsers. Genuinely unstructured text uses regex first, with LLM-assisted extraction as a fallback. All parsed results are validated against the raw output.

**Q8: How does the RAG pipeline work?**
Hybrid retrieval: dense (embedding similarity) and sparse (BM25 keyword search), combined with reciprocal rank fusion. Namespace filtering ensures only relevant knowledge is retrieved. The skill pack specifies which namespaces to search.

**Q9: How do you handle long-running sessions?**
State checkpointing after every step, stored in the database. Steps are idempotent: replaying a step from a checkpoint uses cached tool outputs. Crash recovery detects orphaned sessions and restarts from the last checkpoint.

**Q10: How do you prevent prompt injection from target content?**
Tool output is enclosed in data blocks with clear delimiters. Privilege separation keeps raw target content away from the planner. The scope guard validates actions independently of LLM reasoning. Anomaly detection flags unusual behaviour.

**Q11: What is your evaluation strategy?**
Run the agent against intentionally vulnerable labs (Juice Shop, DVWA, crAPI, GOAD) with known ground-truth manifests. Measure recall, false-positive rate, multi-step completion, and other metrics. Run 3-5 times for statistical stability. Regression gates in CI prevent quality drops.

**Q12: How would you fine-tune a model for this platform?**
Start with output parsing: collect 200-500 examples of tool output paired with correct structured extraction. Use LoRA to fine-tune a smaller model. Measure before/after accuracy on a held-out test set. Only deploy if it meaningfully outperforms prompting alone.

**Q13: How does the agent handle errors during tool execution?**
Retry up to 2 times with exponential backoff. If still failing, log the error, mark the action as failed, and try an alternative approach. After 5 consecutive failures, pause the session for human intervention.

**Q14: How do you ensure reproducibility?**
Every session records: model version, prompt version (hash), skill pack version, tool versions, agent code version. MLflow tracks experiments. Given the same configuration, results will be similar though not identical due to model non-determinism.

**Q15: Why PGVector instead of a dedicated vector store?**
Fewer infrastructure components for a small team. PGVector runs on the same PostgreSQL instance as the engagement state. If retrieval performance becomes a bottleneck at scale, migrating to a dedicated store is straightforward because the retrieval interface is abstracted.

**Q16: How does the approval workflow work?**
When the agent proposes an action above the engagement's auto-approve risk class, the scope guard pauses execution and sends an `approval_requested` event to the UI. The tester sees the action details and approves or rejects. The agent waits until a decision is received.

**Q17: How do you measure and control costs?**
The model gateway tracks token usage and cost per model call. Budget limits (tokens, cost) are enforced per session. Task-based routing sends simple tasks to cheaper models. Caching reduces redundant calls. Cost per assessment is tracked as a metric.

**Q18: What are the biggest risks and how do you mitigate them?**
Out-of-scope targeting (mitigated by three-layer scope enforcement), hallucinated findings (mitigated by independent verification), costs spiralling (mitigated by budgets and routing), tester adoption (mitigated by assist mode and tester involvement in design).

**Q19: How would you add support for a brand-new assessment type?**
Write a skill pack YAML manifest specifying methodology, tools, knowledge namespaces, prompts, and risk policy. Write tool wrappers for any new tools. Ingest relevant knowledge documents. Write evaluation scenarios. No changes to the agent core.

**Q20: What can this system NOT do reliably?**
Novel vulnerability research (requires creativity beyond current LLM capability), business logic flaw discovery (requires understanding application purpose), social engineering, physical security testing, and making legal judgments about scope. These require human testers.

---

## 5. Eight sources to verify and deepen your understanding

1. **OWASP Web Security Testing Guide (WSTG)** — The comprehensive methodology for web application testing. Read at least the "Testing for SQL Injection" and "Testing for XSS" sections to understand what the agent automates. URL: https://owasp.org/www-project-web-security-testing-guide/

2. **MITRE ATT&CK Framework** — Browse the Enterprise matrix to understand how attack techniques are categorised. Focus on the Reconnaissance, Initial Access, and Credential Access tactics. URL: https://attack.mitre.org/

3. **LangGraph documentation** — Since you use LangGraph, study its state management and graph-based agent orchestration patterns. The agent loop in the architecture maps directly to LangGraph concepts. URL: https://langchain-ai.github.io/langgraph/

4. **OWASP Juice Shop** — Set it up locally and try to find a few vulnerabilities manually. This is the primary evaluation target in the architecture. URL: https://owasp.org/www-project-juice-shop/

5. **"Building Effective Agents" by Anthropic** — A practical guide to building reliable LLM agents. Covers tool use, structured outputs, and failure handling. URL: https://docs.anthropic.com/en/docs/build-with-claude/agent-patterns

6. **Nmap documentation** — Understand the basics of port scanning and service detection. This is the most commonly referenced tool in the architecture. URL: https://nmap.org/book/man.html

7. **PGVector documentation** — Understand how vector similarity search works in PostgreSQL, since this is the chosen vector store. URL: https://github.com/pgvector/pgvector

8. **PTES (Penetration Testing Execution Standard)** — The industry-standard methodology that structures how a pen test is conducted from start to finish. URL: http://www.pentest-standard.org/
