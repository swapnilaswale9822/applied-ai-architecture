# ADR 001 — A thin platform layer over an agent framework

**Status:** Accepted · **Scope:** agent runtime

## Context

The platform needed to run many agents for many tenants, each with different knowledge,
tools and guardrails, configured by non-engineers through a UI rather than written as code.

That last constraint drove everything. Most agent frameworks assume the agent *is* code
written by a developer. Here the agent is a row in a database, and something has to turn it
into a running process safely, repeatedly, and with tenant isolation intact.

## Options considered

**Build the runtime from scratch.** Total control over the execution model and state.
Also means owning tool-calling loops, streaming, structured output coercion, provider
differences and retry semantics — months of work re-implementing what several teams already
maintain, and every provider API change becomes our problem.

**LangGraph.** Explicit graph-based state machine, strong ecosystem, well-suited to
developer-authored workflows with branching and cycles. The friction is that its graph is
defined in Python at import time, while ours has to be constructed at runtime from a
database row. That is possible, but it means generating graphs dynamically per tenant —
using the framework against its grain, and inheriting its assumptions about state
persistence anyway.

**Agno with a platform layer on top.** A lighter runtime with hooks at the points that
matter — pre/post hooks, retriever injection, tool registration — which is exactly the seam
a configuration-driven platform needs. Less opinionated about orchestration, which meant
building the workflow compiler ourselves.

## Decision

Agno for the agent runtime, with a platform layer owning multi-tenancy, the workflow
compiler, guardrail policy and evaluation.

The deciding factor was the **hook surface**. Governance is cross-cutting: it has to sit at
ingest, retrieval, and both sides of the model call. A framework that lets those be injected
per-agent-instance is worth more here than a richer orchestration model, because
orchestration is the part we could build and governance is the part we could not bolt on
afterwards.

## Consequences

**Good.** Guardrails and tenant scoping are enforced below the agent, so no agent
configuration can opt out of them. The workflow compiler is ours, so node types map to
product concepts rather than to framework primitives.

**Bad.** We own the workflow engine, including its gaps — it is not a true DAG scheduler and
runs are not resumable ([ADR 002](002-celery-redis-over-temporal.md)). A more opinionated
framework would have given us some of that for free.

**Honest.** Choosing a less mainstream framework means a smaller hiring pool and fewer
answers already written down. The mitigation is that the platform layer, not the framework,
is where our actual complexity lives — which is also why porting the runtime is a bounded
piece of work rather than a rewrite.

## What I would revisit at 10x scale

**If agent authoring moves from configuration to code**, the reason for this decision
disappears. A developer-authored agent is exactly LangGraph's case, and its persistence and
branching model would then be earning its keep instead of being worked around.

**If we need durable execution with history replay**, the combination of a graph framework
with built-in checkpointing plus a workflow engine starts to beat maintaining our own — see
ADR 002 for the same trade at the orchestration layer.

**What I would keep either way:** the platform layer. It is the part that makes agents
configuration rather than code, and it is framework-independent by design.
