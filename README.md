# Applied AI Architecture — Swapnil Aswale

Architecture and design notes from production AI systems I have built: a multi-tenant agent
platform, and the agents and pipelines running on top of it.

No proprietary code or client names — this covers **architecture, system design, technologies,
my contribution, and technical approach**.

📧 swapnila302@gmail.com

---

## Contents

| # | Project | What it is |
|---|---|---|
| 1 | [Agent Platform](01-agent-platform.md) | Multi-tenant platform for building, running and governing AI agents. Used by 100+ organisations. |
| 2 | [IT Support Agent](02-it-support-agent.md) | L1 support agent on Slack + Freshdesk. ~50% ticket deflection, 92% KB-hit rate. |
| 3 | [Invoice → ERP Automation](03-invoice-to-erp.md) | AP invoices to SAP-ready output for a large pharma manufacturer. On-prem model, no external API calls. |
| 4 | [Compliance-Gated Content Engine](04-content-compliance.md) | Growth platform for regulated wellness brands. ~10× content throughput at flat headcount; hallucination control built as retrieval, not prompting. |
| 5 | [Evaluation & Reliability](05-evaluation-and-reliability.md) | How I keep these systems from silently degrading: eval gates, resilience patterns, observability. |
| 6 | [AI Development Lifecycle](06-ai-development-lifecycle.md) | A governance framework I designed and rolled out so a team could use AI coding assistants without losing traceability. |

---

## Technology

| Layer | Used |
|---|---|
| **Languages** | Python, TypeScript, C# / .NET, SQL |
| **AI** | Anthropic Claude, OpenAI, Agno agent framework, multi-provider routing |
| **RAG** | PostgreSQL + pgvector, hybrid search, reranking, per-tenant isolation |
| **Backend** | FastAPI, Celery, Redis, Gunicorn, REST + webhooks |
| **Data** | PostgreSQL, Alembic migrations, multi-tenant schema design |
| **Frontend** | React 18, TypeScript, Vite, Tailwind, ReactFlow (visual workflow builder) |
| **Evaluation** | Promptfoo, LLM-as-judge, CI quality gates |
| **Observability** | OpenTelemetry + OpenInference (works with Phoenix / Langfuse / Braintrust) |
| **Infra** | Docker, Docker Compose, Kubernetes, Kong, Cloudflare AI Gateway, Azure, nginx |

---

## Maturity labels

Every component in these documents is labelled, so it is clear what carries live traffic and
what is designed and built but not yet deployed.

| | Meaning |
|---|---|
| 🟢 **Production** | Running in a live multi-tenant system with real traffic |
| 🔵 **Reference implementation** | Built and runnable, with tests — not yet in production |
| ⚪ **Design** | Architecture and migration plan documented, not built |

---

## How I approach this work

**Ship the boring version first.** Production today runs on Docker Compose and Celery rather
than Kubernetes, because at current tenant count the operational cost was not justified. The
migration is designed and the trigger is written down.

**Decide what AI is not allowed to do.** In the invoice system, GL account selection is
deliberately manual — it is accounting judgement, not extraction. Knowing where to stop is
most of the design.

**Make failure detectable rather than impossible.** Hallucination is not eliminated; it is
grounded, checked, bounded, and cheap to fail on. The real design question is what the system
does when it does not know — guessing is the bug.

**Write the decision down.** Architecture decisions live in the repo with their trade-offs and
what I would revisit at 10x scale.
