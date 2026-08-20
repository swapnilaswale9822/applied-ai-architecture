# ADR 002 — Step checkpointing on Celery, not a replay engine

**Status:** Accepted · **Scope:** durable workflow execution

## Context

Multi-step agent workflows — ingest, enrich, generate, validate, publish — can run for
minutes. A worker that dies mid-run currently loses its progress: the run restarts from the
beginning, repeating work that already succeeded and, worse, repeating any external side
effect it had already applied.

The platform already runs Celery over Redis with Postgres as the system of record.

## Options considered

**Temporal (or a replay-based engine).** Durable execution as a product: automatic retries,
history replay, versioning, visibility. The cost is a determinism constraint — workflow code
must produce identical decisions when replayed, so no unguarded clock reads, no randomness,
no direct I/O outside activities. That is a real constraint to hold across a team, and it
fails *quietly*: the code works until a replay happens, which is precisely during an
incident. Plus a new stateful service to operate.

**Celery's own retries alone.** Already available, no new concepts. But retries are
per-task, not per-workflow: a task that fails at step four re-runs from step one, which is
the problem, not the fix.

**Step checkpointing on the existing stack.** A `workflow_run` / `workflow_step_run` ledger.
Before each step, look for a completed record whose input hash matches; if it exists, reuse
its output instead of executing. Output and status are written in the **same transaction**,
so no crash window exists between them.

## Decision

Step checkpointing, on the infrastructure already in production. Redis stays the transport;
**Postgres is the truth**.

Two details carry the design:

- **The input hash, not just a completion flag.** If an earlier step now produces something
  different, the downstream step's cached output was computed from inputs that no longer
  exist and must not be reused.
- **A janitor for expired leases.** Without it a crashed run sits in `running` forever —
  nothing retries it and nothing reports it failed. This is the piece people leave out, and
  the reason "durable" systems quietly lose work.

Built and tested in [`../../reliability/durable_workflow/`](../../reliability/durable_workflow/).
The acceptance test kills a worker mid-run and asserts the resume skips completed steps.

## Consequences

**Good.** No determinism constraint on step code — steps can call the clock, use randomness
and do I/O directly, which for LLM steps at temperature > 0 is not negotiable. No new
stateful service. The ledger is queryable with ordinary SQL, so "where did run X stop" is a
`SELECT`, not a UI.

**Bad.** No free history replay, no workflow versioning, no built-in visibility UI. We own
the janitor, the lease semantics and the idempotency discipline for side-effecting steps.

**Subtle.** Checkpointing resumes from the last *completed* step, so a step that is not
idempotent must carry an idempotency key — the driver derives one from run id plus step key.
A replay engine would not have made this go away; it would have moved it into activity
design.

## What I would revisit at 10x scale

**Workflow versioning is the real trigger.** Checkpointing has no answer for "this run
started under definition v3 and we have since shipped v4." Today the version is recorded and
in-flight runs finish on their original definition. Once long-running workflows routinely
outlive deploys, replay-based versioning stops being a luxury.

**Also reconsider if** cross-workflow visibility becomes an operational need — Temporal's UI
is genuinely better than the dashboards we would otherwise build — or if the janitor and
lease logic start accumulating edge cases, which is the signal that we are reimplementing a
workflow engine badly.

**What I would keep:** Postgres as the system of record. Whatever drives the workflow, the
step ledger being ordinary queryable rows has been worth more during incidents than any
feature on this list.
