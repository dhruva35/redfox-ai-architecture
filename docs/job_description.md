# Job description: AI Engineer, Agentic Cybersecurity (Redfox Cyber Security Private Limited)

Location: Andheri West, Mumbai. Work mode: Work From Office. Experience: 2-3+ years. Full-time.

## About Redfox Cybersecurity
Redfox Cybersecurity is a cybersecurity company focused on offensive security, penetration testing, adversary simulation, cybersecurity training, and innovative security solutions.

They are building the next generation of AI-powered cybersecurity products that combine AI agents with established penetration-testing capabilities, security tooling, and human expertise.

They are looking for an AI Engineer to help build the AI layer of their AI-powered penetration-testing platform. This is a hands-on role involving LLMs, AI agents, reasoning systems, tool orchestration, RAG, model evaluation, AI infrastructure, and production deployment.

The engineer works closely with the Full Stack Developer, penetration testers, and security researchers to build, integrate, and continuously improve the AI capabilities of the platform. The ideal candidate can take an AI capability from idea, research, prototype, development, product integration to production.

## Key responsibilities

### AI and agent development
- Design and develop AI agents capable of performing complex, multi-step penetration-testing tasks.
- Build the core reasoning and action loop: understand objectives, determine the next action, execute tools, interpret results, continue toward an objective.
- Develop systems that maintain context and state across multiple steps, so information gathered during an assessment influences subsequent actions.
- Build AI-driven tool orchestration that lets LLMs interact with command-line tools, scripts, APIs, and custom cybersecurity utilities.
- Implement mechanisms for self-critique, validation, and verification to distinguish genuine security findings from false positives.
- Develop AI capabilities that can understand and operate within defined scope, methodologies, skills, rules, and engagement-specific requirements.
- Build reusable AI capabilities supporting the platform's penetration-testing use cases: Web, API, Internal Network, External Network, Active Directory, Source Code, Cloud, and Firewall assessments.
- Develop mechanisms for the AI to dynamically select and use appropriate tools based on assessment context.

### LLM and generative AI engineering
- Work extensively with LLMs and generative AI for cybersecurity applications.
- Design and optimise prompts, system instructions, structured outputs, function calling, and tool-use mechanisms.
- Build LLM-based decision-making and reasoning systems for long-running, multi-step tasks.
- Implement RAG and retrieval systems to provide relevant penetration-testing knowledge, methodologies, engagement documentation, and other context.
- Work with embeddings and vector databases such as FAISS, PGVector, Weaviate, Milvus, or equivalents.
- Evaluate and experiment with foundation models on capability, accuracy, latency, context window, reliability, and cost.
- Implement model routing so different models serve different tasks.
- Fine-tune or adapt models with LoRA, QLoRA, or other parameter-efficient approaches where required.
- Build model abstraction layers so models and inference providers can be evaluated and integrated without significant changes to the core platform.

### AI and cybersecurity integration
- Work closely with Redfox penetration testers and security researchers to understand real-world requirements and incorporate them into the AI-powered pen-testing tool.
- Understand real-world techniques, tool usage, assessment requirements, and common challenges faced by security professionals.
- Integrate cybersecurity tools and custom scripts into the platform.
- Enable the AI to interpret outputs from tools such as Nmap, web fuzzers, BloodHound, and custom security tooling.
- Develop mechanisms for dynamically loading capabilities and skills based on assessment type and engagement requirements.
- Continuously improve the AI's ability to identify, validate, and reproduce security findings.
- Contribute to Redfox's proprietary AI and cybersecurity capabilities.

### AI evaluation and quality
- Build an evaluation and benchmarking framework for testing models and agents against controlled penetration-testing environments.
- Develop evaluation datasets and scenarios covering reconnaissance, vulnerability discovery, exploitation, multi-step attack chains, and finding validation.
- Measure performance with metrics such as findings discovered, true-positive/false-positive rate, finding validation rate, multi-step task completion, tool-selection accuracy, context/state preservation, latency, token usage, and cost per assessment.
- Run regression testing whenever models, prompts, agent behaviour, or other AI components change.
- Benchmark different models and configurations to find the most effective approach per task.
- Identify and address failure modes: hallucination, incorrect tool selection, loss of context, incomplete task execution, incorrect conclusions.

### AI infrastructure and production engineering
- Build scalable infrastructure for AI inference, agent execution, data processing, evaluation, and monitoring.
- Develop production-grade AI services exposed via REST APIs, WebSockets, or other interfaces.
- Work with the Full Stack Developer to integrate AI capabilities into the backend and user-facing product.
- Build mechanisms for managing long-running AI sessions, execution state, task queues, and intermediate results.
- Work with Docker and cloud infrastructure, particularly GCP, to deploy and operate AI services.
- Optimise for latency, throughput, reliability, scalability, and inference cost.
- Implement caching, batching, model selection, context management, and other inference optimisation techniques.
- Implement logging, tracing, monitoring, and observability across AI components.
- Maintain model, prompt, agent, and capability versioning for reproducibility.

### Product development and collaboration
- Convert AI capabilities into functional product features with the Full Stack Developer.
- Define APIs, data contracts, and interfaces between the AI engine and the application layer.
- Participate in architecture and technical design discussions.
- Rapidly prototype new AI capabilities and take successful prototypes through productionisation.
- Research emerging AI technologies and evaluate their practical applicability.
- Contribute to Redfox's proprietary AI technology and intellectual property.

## Requirements

### Must have
- 2-3+ years hands-on experience in AI/ML, Applied AI, AI Engineering, ML Engineering or a closely related field.
- Experience building and deploying AI/ML or LLM-based applications, preferably with at least one project in production.
- Strong Python and solid software engineering fundamentals.
- Strong hands-on experience with LLMs and generative AI.
- Practical experience building AI agents or agentic systems.
- Strong understanding of: prompt engineering, function/tool calling, structured outputs, RAG, embeddings, vector databases, context and state management, LLM evaluation.
- Experience integrating LLMs with external tools, APIs, scripts, or execution environments.
- Experience with PyTorch, TensorFlow, or equivalent.
- Experience with one or more vector databases (FAISS, PGVector, Weaviate, Milvus).
- Experience with model adaptation/fine-tuning (LoRA, QLoRA, or equivalent).
- Experience building AI APIs and backend services; strong understanding of REST and service-oriented architectures.
- Experience with Docker and cloud platforms (GCP, AWS, Azure).
- Understanding of CI/CD, Git, testing, observability, and production deployment.
- Experience with MLflow or equivalent experiment/model management.
- Ability to evaluate and benchmark AI systems with measurable criteria.
- Strong problem-solving and a product-oriented engineering mindset.

### Strongly preferred
- Autonomous or semi-autonomous AI agents; agent orchestration frameworks or custom orchestration.
- Tool-use and function-calling architectures; long-running multi-step AI tasks.
- Model serving and inference optimisation; open-weight LLMs and Hugging Face; quantisation, batching, caching.
- Evaluation environments for AI agents.
- Cybersecurity, penetration testing, vulnerability assessment, or security tooling; OWASP, pen-testing methodologies, offensive tooling, MITRE ATT&CK.

### Good to have
- AI-powered cybersecurity products; agents for security testing, vulnerability discovery, or security operations.
- Tools such as Nmap, Burp Suite, BloodHound, web fuzzers.
- Web application, API, network, or Active Directory security understanding.
- Source-code analysis or security configuration data; cloud security or cloud configuration analysis.
- Open-source contributions, GitHub projects, publications, personal projects; research in LLMs, autonomous agents, NLP, applied ML.

## Platform notes from the JD
The platform architecture places the Agent Core at the centre of the system, responsible for reasoning, model interaction, tool execution, engagement state, self-critique, and evidence generation. The platform is intended to autonomously perform and assist penetration testing across multiple assessment types, with the AI maintaining context across chained, multi-step activities. The AI engineer works alongside the Full Stack Developer to integrate these capabilities into a complete, usable product.

## What they look for
An engineer who can build, experiment, evaluate, debug, and continuously improve AI systems; goes beyond simply calling an LLM API; understands how an agent maintains state, makes decisions, uses tools, interprets outputs, validates conclusions, and operates reliably across complex multi-step tasks; works with cybersecurity professionals to translate real-world pen-testing needs into working AI capabilities; and wants to build an AI-powered cybersecurity product from the ground up.

## Application
Share CV with relevant AI/ML projects, AI agent / LLM projects, GitHub repositories, production AI systems, research/publications, cybersecurity or offensive-security projects.
