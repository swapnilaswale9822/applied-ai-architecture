# ADR 005 — Isolation enforced at the retrieval boundary

**Status:** Accepted · **Scope:** multi-tenancy, security

## Context

One platform serves many organisations. Each has its own knowledge base, and their content
is commercially sensitive — in the regulated cases, legally so. Tenant A's document
surfacing in tenant B's answer is not a bug report, it is an incident and possibly a
notifiable one.

The failure mode is what makes this hard: a missing tenant filter does not raise an error.
It returns **more** results. Nothing looks wrong. Tests pass, because a test that asserts
"the right documents came back" still passes when extra ones did too.

## Options considered

**Database per tenant.** Strongest isolation, and a hard boundary that is easy to reason
about. Also: migrations across hundreds of databases, connection pool exhaustion,
cross-tenant analytics becoming a data-warehouse project, and per-tenant operational cost
that does not fit the pricing model.

**Row-level security in Postgres.** The database enforces it, so application bugs cannot
bypass it — genuinely strong. It requires every connection to carry the correct session
context, which with a pooled connection pool is a discipline of its own, and one that fails
in the same silent direction if a pooled connection is reused without resetting the setting.

**Application-level filters.** Pass a tenant id into each query. Simple, and the default
almost everyone ships. It relies on every code path remembering — and there is always one
that does not.

**Enforced at a boundary object.** A retriever constructed *with* a tenant, applying the
predicate itself, with no parameter for callers to widen the scope.

## Decision

Enforce at the boundary object, over pgvector in a shared database ([ADR 003](003-pgvector-over-dedicated-vector-db.md)).

`GovernedRetriever` is constructed with a tenant and a classification ceiling. Its
`retrieve()` signature accepts a query and a result count — and nothing else. There is no
argument that widens the scope, so no caller can forget the filter or opt out of it.

The same object owns **fetch-by-id**, which is where this bug usually actually lives:
search results are correctly scoped, and then a detail endpoint loads a document by id and
returns it to anyone who can guess the id. Missing and forbidden return the identical error,
so the response cannot be used to probe for existence.

Built and tested in
[`../../reliability/governance-layer/`](../../reliability/governance-layer/) — including a
test asserting the method signature itself, so widening it fails CI rather than review.

## Consequences

**Good.** Isolation is structural rather than remembered. A new endpoint gets it by
construction. Freshness and classification ceilings ride the same boundary, so an expired
or over-classified document cannot leak through a path that only thought about tenancy.

**Bad.** It is application-level. A developer who bypasses the retriever and queries the
store directly bypasses everything — the guarantee is "you cannot do this by accident", not
"you cannot do this." That gap is covered by review and tests, which is weaker than a
database guarantee.

**Cost.** The retriever over-fetches and filters in application code, so heavily
cross-tenant queries do work that is thrown away.

## What I would revisit at 10x scale

**Row-level security is the upgrade path**, and the trigger is organisational rather than
technical: once enough engineers touch the data layer that "nobody bypasses the retriever"
stops being enforceable by review, the guarantee needs to move into the database. The two
compose — RLS as the backstop, the boundary object as the ergonomic default — and adopting
both is the mature end state, not a replacement.

**Database-per-tenant becomes right** only if a specific customer contractually requires
physical isolation. That is a deployment-model decision, not an architecture-wide one.

**What I would keep:** the rule that the filter is a property of the object, never a
parameter of the call. Every silent cross-tenant leak I have seen traces back to an argument
someone was allowed to omit.
