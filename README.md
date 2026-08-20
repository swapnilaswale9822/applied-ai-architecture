# Applied AI Architecture — Swapnil Aswale

Architecture and design notes from production AI systems I have built: a multi-tenant agent
platform, and the agents, pipelines and reliability tooling that run on it.

No proprietary code and no client names — this covers **architecture, system design,
technologies used, my role and contribution, and technical approach**.

📧 swapnilaswale@hotmail.com

---

## Start here

| | |
|---|---|
| [**How I work**](HOW_I_WORK.md) | Engineering principles, each with the decision in this repo that demonstrates it — and what it cost |
| [**The platform**](platform/) | A multi-tenant agent platform used by multiple organisations: [architecture](platform/architecture.md) · [one run end to end](platform/runtime-sequence.md) · [decision records](platform/decisions/) |
| [**Case studies**](case-studies/) | Three systems shipped under real constraints |
| [**Reliability**](reliability/) | The last mile: what breaks, the patterns that handle it, and working code with 96 tests |

---

## Case studies

| | What it is |
|---|---|
| [IT support deflection](case-studies/01-it-support-deflection.md) | L1 support agent on Slack and Freshdesk. **~50% ticket deflection, 92% KB-hit rate.** The engineering is the decision gate — deciding when *not* to answer. |
| [Invoice → ERP grounding](case-studies/02-invoice-to-erp-grounding.md) | AP invoices to SAP-ready output for a large pharma manufacturer, on a private on-premise model. Grounded against structured master data, not document vector search. |
| [Compliance-gated content](case-studies/03-compliance-gated-content.md) | Growth platform for regulated wellness brands. **~10× content throughput at flat headcount**, with hallucination control built as retrieval rather than prompting. |

And the framework I designed for how a team builds *with* AI:
[AI Development Lifecycle](platform/ai-development-lifecycle.md) — seven phases, a risk-tiered
approval matrix, and an explicit list of what AI is never permitted to do.

---

## Reliability — the part that is running code

[`reliability/`](reliability/) opens with a twelve-row failure taxonomy: what breaks, the
pattern that handles it, and where it lives. Below it, working implementations:

| | |
|---|---|
| [`resilience/`](reliability/resilience/) | Timeout budget · retry with full jitter · circuit breaker on rolling error rate · bulkhead · fallback chain · load shedding |
| [`durable_workflow/`](reliability/durable_workflow/) | Step checkpointing with a kill-the-worker-mid-run resume test |
| [`evaluation-harness/`](reliability/evaluation-harness/) | Four scenario classes, tiered quality gates, CI verdict, production failure → permanent regression — and [how the production service wraps **Promptfoo**](reliability/evaluation-harness/PROMPTFOO.md) |
| [`governance-layer/`](reliability/governance-layer/) | Tenant-scoped retrieval, PII scrubbing, guardrails, tamper-evident audit log |
| [`gateway/`](reliability/gateway/) · [`k8s/`](reliability/k8s/) | Kong + Cloudflare AI Gateway configs · probes, autoscaling on queue depth, graceful drain |

```bash
cd reliability && python3 -m pytest      # 96 tests, no external dependencies
```

Every test induces the failure it is about rather than asserting a happy path.

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
| **Evaluation** | Promptfoo, LLM-as-judge, tiered CI quality gates |
| **Observability** | OpenTelemetry + OpenInference (works with Phoenix / Langfuse / Braintrust) |
| **Infra** | Docker, Docker Compose, Kubernetes, Kong, Cloudflare AI Gateway, Azure, nginx |

---

## Maturity labels

Every component is labelled, so it is clear what carries live traffic and what is built or
designed but not deployed.

| | Meaning |
|---|---|
| 🟢 **Production** | Running in a live multi-tenant system with real traffic |
| 🔵 **Built and tested** | Runnable here with tests — not yet in production |
| ⚪ **Design** | Architecture and migration plan documented, not built |

Labelling maturity is not modesty. A document where everything is implied production
collapses under one probing question, and takes the true claims down with it.
