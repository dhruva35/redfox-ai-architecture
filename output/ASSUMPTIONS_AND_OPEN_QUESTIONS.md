# Assumptions and open questions

## Assumptions

These are decisions made in the absence of information from Redfox. You should be ready to discuss and adjust each one during the interview.

### Architecture assumptions

| ID | Assumption | Why it matters | What to verify |
|----|-----------|---------------|---------------|
| A1 | The Full Stack Developer builds the operator UI and integrates with the API/WebSocket contract. The AI engineer does not build the frontend. | Defines the boundary of responsibility. If you are expected to build UI components, the timeline changes. | Ask about team structure and responsibilities. |
| A2 | GCP is the primary deployment platform. | The architecture is described for GCP services (Cloud Run, GKE, Cloud SQL, Pub/Sub). AWS or Azure equivalents exist but would change service names and some details. | Confirm GCP preference. |
| A3 | The initial user base is the internal Redfox pen-testing team (~10-20 testers), not external clients. | This affects multi-tenancy requirements, scale, and compliance needs. | Ask about initial deployment scope. |
| A4 | Redfox has existing pen-testing methodologies and playbooks that can be digitised for RAG. | RAG quality depends on source document quality. If playbooks do not exist, creating them is a separate effort. | Ask about existing documentation and playbooks. |
| A5 | Hosted LLM APIs (OpenAI, Google, Anthropic) are acceptable for initial development. | Client data will be sent to third-party APIs unless redacted. Some clients may not accept this. | Ask about data residency requirements and existing provider agreements. |
| A6 | Pen testers will participate in agent evaluation and training data creation (3-5 hours/week from 2-3 testers). | Without tester involvement, skill packs and evaluation will be based on public knowledge only, limiting quality. | Ask about tester availability and willingness. |
| A7 | The eight assessment types from the JD represent the priority order for development. | Web app is the MVP; if Redfox's highest demand is elsewhere (for example, AD assessments), the roadmap should change. | Ask about which assessment types are most important. |
| A8 | The platform does not need to run offensive tools against production client systems from day one. Initial testing is against controlled lab environments. | Running tools against real targets has legal and safety implications that go beyond the architecture. | Clarify the expected deployment environment for MVP. |

### Technical assumptions

| ID | Assumption | Alternative | Impact if wrong |
|----|-----------|-------------|----------------|
| A9 | Python is the primary implementation language. | Go, Rust, TypeScript | Core assumption based on JD requirements. Unlikely to be wrong. |
| A10 | PostgreSQL with pgvector is sufficient as the vector store for MVP scale. | Weaviate, Milvus, FAISS | If retrieval latency is critical, a dedicated vector store may be needed sooner. Migration path is clean. |
| A11 | LangGraph is suitable for agent orchestration. | Custom orchestration, CrewAI, AutoGen | If Redfox has strong preferences or existing code, the orchestration layer should adapt. |
| A12 | Cloud Run supports the session durations needed (up to 4 hours). | GKE for long-running services | Cloud Run supports up to 60-minute request timeouts. For sessions longer than 60 minutes, the session manager would need to use background processing with Pub/Sub rather than synchronous requests. This is accounted for in the design. |
| A13 | Open-source tools (Nmap, Nuclei, ffuf, etc.) are sufficient for MVP. | Burp Suite Professional, commercial scanners | If Redfox has commercial tool licences, integration may be more complex (licence management, GUI-based tools). |

## Things I could not verify

| Item | What I looked for | What I found | Impact |
|------|------------------|-------------|--------|
| Redfox's current AI product status | Website, blog posts about AI-powered pen testing | No public information about their AI product beyond the JD. The blog focuses on pen-testing methodology and training, not AI tooling. | All claims about Redfox's AI product in the architecture come from the JD, not from independent verification. |
| FoxRadar 360 details | foxradar360.com | Linked from the Redfox navigation as a separate product. Could not determine exact functionality from public pages. | This may be relevant context for understanding Redfox's product portfolio. Ask about it. |
| Redfox internal tooling | Website | No public information about internal tools or infrastructure. | Architecture assumes a fresh build rather than integration with existing systems. |
| Team size for the AI/platform project | JD | JD mentions an AI Engineer and a Full Stack Developer. Other team members are not specified. | Architecture is designed for a 2-person engineering team. If the team is larger, the roadmap could be more aggressive. |
| Specific LLM providers Redfox uses or plans to use | JD | JD does not specify providers. | Model gateway is designed to be provider-agnostic. |

## Open questions to ask during the interview

### Priority questions (ask these)

1. **What assessment types are highest priority for the AI platform?** The architecture starts with web app, but if AD or network assessments are more in demand, the skill pack development order should change.

2. **What is the expected level of autonomy from day one?** The architecture supports both assist and autonomous modes. Knowing which mode is the target helps prioritise features.

3. **What existing tools and infrastructure does Redfox have?** Commercial tool licences (Burp Suite, etc.), existing cloud infrastructure, internal tooling, CI/CD pipelines.

4. **What are the data confidentiality requirements?** Can client data be sent to hosted LLM APIs? Is self-hosted model serving needed from the start?

5. **How will the AI platform integrate with existing Redfox workflows?** Will testers use it alongside their current tools, or is it intended to become the primary platform?

### Good-to-ask questions

6. **What does success look like in the first 6 months?** What metrics or outcomes would demonstrate that the platform is valuable?

7. **How many concurrent assessments do you expect to run?** This affects infrastructure sizing and cost projections.

8. **Is there an existing engagement management system that the platform should integrate with?** Client management, project tracking, report delivery.

9. **What is FoxRadar 360 and how might it relate to the AI platform?** Understanding the product portfolio helps identify integration opportunities.

10. **What is the approach to compliance?** Does the platform itself need to meet SOC 2, ISO 27001, or other standards?
