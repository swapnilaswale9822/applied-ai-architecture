# ADR 003 — pgvector in the primary database

**Status:** Accepted · **Scope:** retrieval storage

## Context

Every tenant has a knowledge base: uploaded documents, crawled pages, transcripts, product
data. Retrieval must be filtered by tenant, by document classification, and by freshness —
on **every** query, without exception.

The relational data those filters depend on (tenant, permissions, document metadata,
effective dates) already lives in Postgres.

## Options considered

**A dedicated vector database.** Purpose-built indexing, better recall/latency at very large
scale, richer index tuning. It also means the vectors live in one system and the data that
authorises access to them lives in another.

That split is the actual problem. Tenant scoping becomes a filter you pass to the vector
store and hope stays synchronised with Postgres — two sources of truth for "who may see
this", plus a second backup story, a second consistency model, and a dual-write to keep
them aligned. Every one of those is a place isolation can silently drift.

**pgvector.** Vectors as a column next to the metadata. Retrieval filtering and access
control become the same query, in one transaction, against one source of truth.

## Decision

pgvector, with hybrid search (vector plus full-text) and reranking above it.

The decisive argument was not performance, it was **correctness of isolation**. A tenant
filter that is a `WHERE` clause on the same row as the embedding cannot drift out of sync
with permissions, because it *is* the permissions data. With a separate store, isolation
depends on a synchronisation process being correct forever — and the failure mode is silent
and severe ([ADR 005](005-multi-tenant-isolation-model.md)).

Secondary but real: one datastore to back up, restore, monitor and reason about during an
incident. At this team size that is not a minor consideration.

## Consequences

**Good.** Filtered retrieval is one query. A document's deletion, reclassification or expiry
takes effect immediately, with no reindex-and-hope. Point-in-time restore covers vectors and
metadata together, consistently.

**Bad.** A ceiling exists. HNSW index build time and memory grow with corpus size, and
Postgres will lose to a specialist store on very large single-tenant indexes. We also share
one resource pool: a heavy reindex competes with transactional traffic, which has to be
managed with scheduling rather than by architecture.

**Neutral.** Hybrid search and reranking are ours to build either way — no vector database
would have given us those for free at the quality bar we needed.

## What I would revisit at 10x scale

**The trigger is corpus size per tenant, not tenant count.** Many small tenants suit this
design well; a single tenant with tens of millions of chunks does not. When index build time
or p99 retrieval latency on the largest tenant becomes the constraint, the answer is not to
migrate everything — it is to move the outliers to a dedicated store while keeping the
authorisation predicate in Postgres, so the isolation guarantee survives the split.

**Also reconsider if** the workload shifts to needing index types Postgres does not offer,
or if retrieval traffic grows enough that isolating it from transactional load matters more
than sharing a transaction with it.

**What I would keep:** the rule that access-control data and retrieval filtering never live
in different systems. If vectors move, the predicate moves with them or the query joins back.
