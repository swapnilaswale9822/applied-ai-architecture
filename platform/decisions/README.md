# Architecture decision records

Each record has the same shape:

**Context** → **Options considered** → **Decision** → **Consequences** → **What I would
revisit at 10x scale**

The last section is the one that matters. A decision recorded without its expiry conditions
becomes folklore: the next engineer inherits the conclusion without the reasoning and cannot
tell whether it still holds. Every record here states what would make it wrong.

| # | Decision | Status |
|---|---|---|
| [001](001-agent-framework-choice.md) | Agent framework: a thin platform layer over Agno | Accepted |
| [002](002-celery-redis-over-temporal.md) | Durable execution: step checkpointing on Celery, not a replay engine | Accepted |
| [003](003-pgvector-over-dedicated-vector-db.md) | Vector storage: pgvector in the primary database | Accepted |
| [004](004-otel-openinference-tracing.md) | Tracing: OpenTelemetry + OpenInference, not a vendor SDK | Accepted |
| [005](005-multi-tenant-isolation-model.md) | Tenant isolation enforced at the retrieval boundary | Accepted |
