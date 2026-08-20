"""The driver: run steps, checkpoint each one, resume from where a crash left off.

Resumption rule, in one line: **before running a step, look for a completed record whose
input hash matches; if it exists, reuse its output instead of executing.**

The input hash matters as much as the completion flag. If an earlier step now produces a
different value, the downstream step's input has changed and its old output is stale — so
it re-executes rather than silently reusing a result computed from different inputs.

Why checkpointing rather than a replay engine (Temporal and friends): replay requires every
step to be deterministic, which is a real constraint to hold across a team and easy to break
by accident. Checkpointing has no determinism requirement and runs on the queue you already
operate. The trade is losing free history replay and workflow versioning — worth revisiting
at much higher volume, documented in the ADR.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .store import CheckpointStore, COMPLETED


class StepFailed(Exception):
    def __init__(self, step_key: str, cause: BaseException):
        super().__init__(f"step '{step_key}' failed: {cause}")
        self.step_key = step_key
        self.cause = cause


@dataclass
class Step:
    key: str
    #: Receives the dict of prior step outputs; returns a JSON-serialisable result.
    run: Callable[[Dict[str, Any]], Any]
    #: Marks a step with an external side effect (a payment, an email). Its idempotency key
    #: is derived from run_id + step_key so a retry after a crash cannot double-apply it.
    side_effect: bool = False


def input_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


class WorkflowDriver:
    def __init__(self, store: CheckpointStore, steps: List[Step], lease_seconds: float = 60.0):
        self.store = store
        self.steps = steps
        self.lease_seconds = lease_seconds
        #: Step keys actually executed by this driver instance — the resume assertion.
        self.executed: List[str] = []
        self.skipped: List[str] = []

    def idempotency_key(self, run_id: str, step: Step) -> str:
        return f"{run_id}:{step.key}"

    def drive(self, run_id: str, initial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Context is rebuilt *incrementally*, in the same order as the original run.
        # Pre-loading every completed output would change what each step sees before its
        # hash is computed, so no hash would match and resume would redo everything.
        context: Dict[str, Any] = dict(initial or {})

        for step in self.steps:
            digest = input_hash(context)
            prior = self.store.get_step(run_id, step.key)

            if prior and prior.status == COMPLETED and prior.input_hash == digest:
                self.skipped.append(step.key)
                context[step.key] = prior.output
                continue

            self.store.renew_lease(run_id, self.lease_seconds)
            self.store.start_step(run_id, step.key, digest)
            try:
                result = step.run(context)
            except BaseException as exc:
                self.store.fail_step(run_id, step.key, exc)
                self.store.set_run_status(run_id, "failed", step.key)
                raise StepFailed(step.key, exc)

            # Output and status land together — see CheckpointStore.complete_step.
            self.store.complete_step(run_id, step.key, result)
            self.executed.append(step.key)
            context[step.key] = result

        self.store.set_run_status(run_id, "completed")
        return context


class Janitor:
    """Re-drives runs whose worker died while holding the lease.

    Without this, a crashed run sits in ``running`` forever: nothing is retrying it and
    nothing reports it as failed. It is the piece people forget, and the reason 'durable'
    systems quietly lose work.
    """

    def __init__(self, store: CheckpointStore, driver_factory: Callable[[], WorkflowDriver]):
        self.store = store
        self.driver_factory = driver_factory

    def sweep(self) -> List[str]:
        recovered = []
        for run in self.store.find_abandoned_runs():
            self.driver_factory().drive(run.run_id)
            recovered.append(run.run_id)
        return recovered
