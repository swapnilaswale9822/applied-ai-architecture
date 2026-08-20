# ADR 004 — OpenTelemetry + OpenInference, not a vendor SDK

**Status:** Accepted · **Scope:** observability

## Context

Agent runs need to be inspectable: which sources were retrieved and with what scores, which
prompt version ran, tokens and cost, retries, guardrail outcomes, and where the latency
went. Both for operators debugging, and — in regulated deployments — for an auditor asking
why a specific answer was given.

The LLM observability market has several good products (Langfuse, Phoenix, Braintrust,
LangSmith), each with its own SDK, and each moving quickly.

## Options considered

**Instrument with a vendor's SDK.** Fastest to a working dashboard; best-integrated features;
the product's own semantics for spans and evaluations. The cost is that instrumentation
calls end up scattered through the agent runtime — so changing backend later is not a
configuration change, it is an edit to every instrumented call site, at exactly the moment
you are unhappy with the vendor and least want a migration project.

**Roll our own structured logging.** No dependency, full control. And no trace tree, no
context propagation across services, no ecosystem — we would rebuild a worse OpenTelemetry
and maintain it forever.

**OpenTelemetry with OpenInference semantic conventions.** The vendor-neutral standard, plus
the LLM-specific span conventions (prompt, completion, token counts, retrieval documents)
that generic OTel lacks. Most of the products above ingest it.

## Decision

Instrument once against OTel + OpenInference. The backend is an **exporter configuration**:
Phoenix locally, a hosted backend in production.

The point is that the expensive, invasive part — deciding what constitutes a span, what
attributes it carries, how context propagates across service boundaries — is done once
against a standard rather than against a company's roadmap.

## Consequences

**Good.** Switching or adding a backend is config. Traces cross service boundaries (agent →
knowledge → connector) because context propagation is the standard's job, not ours. The
gateway's correlation id joins access logs to spans without custom plumbing. Nothing about
the instrumentation depends on a vendor still existing.

**Bad.** We give up each product's most differentiated features, which tend to live in their
own SDKs — richer evaluation integrations, prompt playgrounds, annotation workflows. Some of
that we rebuilt in the evaluation harness rather than adopting.

**Also true.** Semantic conventions for LLM spans are still stabilising, so attribute names
have moved under us more than once. Version pinning matters, and instrumentation upgrades
need testing rather than trusting.

## What I would revisit at 10x scale

**If a single backend becomes clearly dominant** and its differentiated features start
mattering more than portability, the calculus changes. The migration cost we are paying
insurance against would be a one-time cost against a mature product — worth paying once.

**Also reconsider if** trace volume makes sampling strategy the main concern. Head-based
sampling loses exactly the rare failures you most want, so tail-based sampling — keep every
errored or ungrounded run, sample the successful ones — becomes necessary, and backend
support for that varies more than their ingestion formats do.

**What I would keep regardless:** the discipline of separating explainability from
observability. Operators need traces. Auditors need citations, retrieved sources, decision
path and an append-only record — a product requirement that no tracing backend satisfies,
and that has to be built deliberately.
