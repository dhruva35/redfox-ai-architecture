# Plan: AI-powered penetration-testing platform architecture

## Requirements extracted from JD (R1-R28)

### AI and agent development
- **R1**: Design and develop AI agents for complex, multi-step pen-testing tasks
- **R2**: Build core reasoning and action loop (understand objectives, determine next action, execute tools, interpret results, continue)
- **R3**: Maintain context and state across multiple steps; information gathered influences subsequent actions
- **R4**: AI-driven tool orchestration (CLI tools, scripts, APIs, custom cybersecurity utilities)
- **R5**: Self-critique, validation, and verification; distinguish genuine findings from false positives
- **R6**: Operate within defined scope, methodologies, skills, rules, engagement-specific requirements
- **R7**: Reusable AI capabilities for 8 assessment types: Web, API, Internal Network, External Network, Active Directory, Source Code, Cloud, Firewall
- **R8**: Dynamically select and use appropriate tools based on assessment context

### LLM and generative AI engineering
- **R9**: Work with LLMs for cybersecurity applications; prompts, structured outputs, function calling, tool-use
- **R10**: LLM-based decision-making and reasoning for long-running, multi-step tasks
- **R11**: RAG for pen-testing knowledge, methodologies, engagement docs
- **R12**: Embeddings and vector databases (FAISS, PGVector, Weaviate, Milvus)
- **R13**: Evaluate foundation models on capability, accuracy, latency, context window, reliability, cost
- **R14**: Model routing (different models for different tasks)
- **R15**: Fine-tune/adapt models (LoRA, QLoRA) where required
- **R16**: Model abstraction layer for swappable providers

### AI and cybersecurity integration
- **R17**: Work with pen testers to understand real-world requirements
- **R18**: Integrate cybersecurity tools and custom scripts; interpret outputs (Nmap, fuzzers, BloodHound)
- **R19**: Dynamically load capabilities/skills based on assessment type
- **R20**: Continuously improve finding identification, validation, reproduction

### AI evaluation and quality
- **R21**: Evaluation and benchmarking framework against controlled pen-testing environments
- **R22**: Evaluation datasets/scenarios: recon, vuln discovery, exploitation, multi-step chains, finding validation
- **R23**: Metrics: findings discovered, TP/FP rate, validation rate, multi-step completion, tool-selection accuracy, context preservation, latency, tokens, cost
- **R24**: Regression testing on model/prompt/agent changes; benchmark models per task
- **R25**: Identify failure modes: hallucination, wrong tool, context loss, incomplete execution, wrong conclusions

### AI infrastructure and production
- **R26**: Scalable infra (Docker, GCP); REST APIs, WebSockets; long-running sessions, queues, state; caching, batching, model selection, context management; logging, tracing, monitoring; model/prompt/agent versioning
- **R27**: Work with Full Stack Developer; define APIs, data contracts; rapid prototyping to productionisation
- **R28**: Research emerging AI tech; contribute to proprietary IP

## What I learned from redfoxsec.com

| Source | Key facts |
|--------|-----------|
| Homepage | "Protect Your Business from Cyber Threats"; global consulting; 2000+ clients; pen testing and offensive security |
| Origins | ~50 employees, 5000+ engagements, 4 countries, 16+ years offensive security; CEO Karan Patel; HQ Ottawa, Canada |
| Services | 20+ services: Web App PT, API PT, Internal/External Network PT, Mobile App PT, Cloud Config Reviews, AD Security, PCI DSS, Red Teaming, OSINT, Source Code Review, Container Security, K8s Config Reviews, Managed Vuln Scanning, Purple Teaming, Host Reviews, Phishing Simulations, Firewall Config Reviews, Wireless PT, Smart Contract Auditing |
| Blog | Active; topics include Burp Suite skills, AD home lab, chaining IDOR/race conditions, pen-test reporting, red team skills; authored by CEO |
| FoxRadar 360 | External product (separate domain), likely an attack surface management tool; could not confirm details |
| Academy | Training platform at academy.redfoxsec.com |

**Could not find**: No blog posts specifically about AI for pen testing. No public details about their AI-powered pen-testing platform beyond what the JD states. The JD is the authoritative source for all claims about their AI product.

## Section-by-section approach

1. **Executive summary**: Position the platform as a human-AI collaborative pen-testing system, not a replacement. Emphasise trustworthiness through verification, scope enforcement, and auditability.
2. **Context and goals**: Map users (testers, leads, Full Stack Dev); define assist vs autonomous modes; design principles.
3. **Pen-test phases and AI fit**: Short primer on PTES phases mapped to Redfox's 8 JD assessment types plus their broader service portfolio.
4. **System architecture**: Layered diagram with 10 layers; component table; justify single agent with internal roles + independent verifier.
5. **Agent Core**: Reasoning loop, engagement state model (ERD), findings lifecycle, verifier design, two worked examples.
6. **Tool and skill layer**: Tool registry contract, wrapper design, sandbox, skill packs manifest, assessment-type mapping.
7. **Knowledge and model layer**: RAG pipeline, model gateway with routing table, fine-tuning strategy, inference optimisation.
8. **Safety, scope, human oversight**: Threat model, scope enforcement engine, action risk classes, approval matrix, audit.
9. **Infrastructure (GCP, Docker)**: Deployment diagram, service list, long-running sessions, API/event contract, observability.
10. **Evaluation and quality**: Eval environments (verified labs), scenario types, metrics definitions, regression gates.
11. **Roadmap, team, risks**: MVP (8-12 weeks), v1, v2; roles; risk register.
12. **JD traceability matrix**: R1-R28 to sections and components.
13. **Assumptions and open questions**.

## Diagrams (7 minimum)

(a) Layered system architecture, (b) Agent loop flowchart, (c) Finding verification sequence, (d) Engagement state ERD, (e) Trust boundaries and scope enforcement, (f) GCP deployment, (g) Skill-pack loading flow.

Proceeding to write ARCHITECTURE.md now.
