# The platform  🟢

A multi-tenant platform for building, running and governing AI agents. Non-engineers
configure an agent — knowledge, tools, guardrails, workflow — through a studio UI; the
platform compiles that into a running agent with retrieval, tool access, evaluation and
tracing already wired in.

**Used by 100+ organisations.** Every case study in this repo runs on it.

| | |
|---|---|
| [`architecture.md`](architecture.md) | Service decomposition, data model, workflow engine, and the decisions behind them |
| [`runtime-sequence.md`](runtime-sequence.md) | One agent run end to end, as it appears in a trace |
| [`ai-development-lifecycle.md`](ai-development-lifecycle.md) | The governance framework the team builds *with* |
| [`decisions/`](decisions/) | Architecture decision records — the trade-offs, and their expiry conditions |

---

## Why a platform and not agents

Every team wanted the same six things — retrieval over their own documents, tool access,
guardrails, evaluation, tracing, tenant isolation — and every team was rebuilding them from
scratch, badly.

The interesting work in any given agent is the last 10%: the domain logic, the decision
boundaries, what it is allowed to do. The other 90% is infrastructure that should exist
once. So the design goal was to make the 90% a platform, and a new agent **configuration
rather than a codebase**.

The IT support agent in [`../case-studies/`](../case-studies/) is the evidence that this
worked: roughly 90% configuration, with the engineering effort going into its decision gate
rather than into plumbing retrieval and tools again.

---

## Shape

| Service | Owns | Why it is separate |
|---|---|---|
| **Agent** | Runtime, workflow execution, guardrail hooks | Latency-critical; must stay responsive |
| **Knowledge** | Ingestion, chunking, embedding, retrieval | Bursty, CPU-heavy |
| **Connector** | External tools, OAuth, inbound webhooks | Isolates third-party failure |
| **Job** | Celery workers, scheduled work, learning loop | Long-running work off the request path |
| **Evaluation** | Datasets, scoring, CI quality gates | Treats every agent as a black box over HTTP |

Split by **failure domain, not by entity**. A large document upload can saturate ingestion
without touching agent response latency. That isolation is the reason the split exists —
not tidiness, and not microservices as a default.

---

## What it is honestly not

The workflow engine compiles a visual node graph into an executable runtime, with agent
nodes, conditions, loops, parallel branches, tool calls and approval gates. It is **not a
true DAG scheduler**, and runs are **not resumable mid-execution** — a worker that dies
takes its run's progress with it.

The design that fixes it is built and tested in
[`../reliability/durable_workflow/`](../reliability/durable_workflow/), and the reasoning
for checkpointing over a replay engine is in
[ADR 002](decisions/002-celery-redis-over-temporal.md).

Stating this is not a disclaimer. An architecture document that lists only strengths tells
a reader nothing about the author's judgement — the limits are where the judgement is
visible.
