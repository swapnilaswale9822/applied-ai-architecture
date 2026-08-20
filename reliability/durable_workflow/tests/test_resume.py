"""The acceptance test for the whole design: kill a worker mid-run and prove the
resume skips completed steps instead of redoing them."""

import pytest

from durable_workflow import CheckpointStore, Step, StepFailed, WorkflowDriver
from durable_workflow.driver import Janitor, input_hash
from durable_workflow.store import COMPLETED, FAILED


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Crash(Exception):
    """Stands in for the worker process dying."""


@pytest.fixture
def store():
    s = CheckpointStore(":memory:")
    yield s
    s.close()


def pipeline(calls, crash_on=None):
    """A four-step pipeline that records every real execution."""
    def make(key, value):
        def _run(ctx):
            calls.append(key)
            if crash_on == key:
                raise Crash("worker died")
            return value
        return Step(key=key, run=_run)

    return [make("extract", {"n": 3}), make("enrich", ["a", "b"]),
            make("validate", True), make("publish", "done")]


def test_happy_path_runs_every_step_once(store):
    calls = []
    store.create_run("r1", "tenant-a", "v1")
    out = WorkflowDriver(store, pipeline(calls)).drive("r1")
    assert calls == ["extract", "enrich", "validate", "publish"]
    assert out["publish"] == "done"
    assert store.get_run("r1").status == "completed"


def test_resume_after_crash_skips_completed_steps(store):
    """The headline behaviour. First worker dies on step 3; the replacement must
    re-execute step 3 onward and nothing before it."""
    store.create_run("r2", "tenant-a", "v1")

    first_calls = []
    with pytest.raises(StepFailed) as exc:
        WorkflowDriver(store, pipeline(first_calls, crash_on="validate")).drive("r2")
    assert exc.value.step_key == "validate"
    assert first_calls == ["extract", "enrich", "validate"]

    # A fresh driver picks the run up — as a new worker would.
    second_calls = []
    driver = WorkflowDriver(store, pipeline(second_calls))
    out = driver.drive("r2")

    assert second_calls == ["validate", "publish"]        # only the unfinished tail re-ran
    assert driver.skipped == ["extract", "enrich"]        # the completed head was reused
    assert out["extract"] == {"n": 3}                     # and its output survived
    assert store.get_run("r2").status == "completed"


def test_crashed_step_is_recorded_as_failed_with_its_error(store):
    store.create_run("r3", "tenant-a", "v1")
    with pytest.raises(StepFailed):
        WorkflowDriver(store, pipeline([], crash_on="enrich")).drive("r3")

    assert store.get_step("r3", "extract").status == COMPLETED
    failed = store.get_step("r3", "enrich")
    assert failed.status == FAILED and "worker died" in failed.error
    assert store.get_step("r3", "validate") is None       # never started


def test_retry_increments_the_attempt_counter(store):
    store.create_run("r4", "tenant-a", "v1")
    with pytest.raises(StepFailed):
        WorkflowDriver(store, pipeline([], crash_on="enrich")).drive("r4")
    assert store.get_step("r4", "enrich").attempt == 1

    with pytest.raises(StepFailed):
        WorkflowDriver(store, pipeline([], crash_on="enrich")).drive("r4")
    assert store.get_step("r4", "enrich").attempt == 2


def test_changed_input_invalidates_the_checkpoint(store):
    """Completion alone is not enough to reuse a result. If the run's input changed, the
    cached output was computed from inputs that no longer exist, so it must not be reused."""
    calls = []
    steps = [Step("extract", lambda ctx: calls.append("extract") or f"read-{ctx['seed']}"),
             Step("enrich", lambda ctx: calls.append("enrich") or f"from-{ctx['extract']}")]

    store.create_run("r5", "tenant-a", "v1")
    out = WorkflowDriver(store, steps).drive("r5", initial={"seed": "A"})
    assert calls == ["extract", "enrich"] and out["enrich"] == "from-read-A"

    # Same run, different input.
    driver = WorkflowDriver(store, steps)
    out = driver.drive("r5", initial={"seed": "B"})
    assert calls == ["extract", "enrich", "extract", "enrich"]   # recomputed, not reused
    assert out["enrich"] == "from-read-B"
    assert driver.skipped == []


def test_rerunning_a_finished_workflow_executes_nothing(store):
    store.create_run("r6", "tenant-a", "v1")
    calls = []
    WorkflowDriver(store, pipeline(calls)).drive("r6")

    driver = WorkflowDriver(store, pipeline(calls))
    driver.drive("r6")
    assert calls == ["extract", "enrich", "validate", "publish"]   # unchanged
    assert len(driver.skipped) == 4 and driver.executed == []


def test_idempotency_key_is_stable_across_attempts(store):
    """A side-effecting step retried after a crash must not double-apply."""
    step = Step("charge", lambda ctx: "ok", side_effect=True)
    d = WorkflowDriver(store, [step])
    assert d.idempotency_key("r7", step) == d.idempotency_key("r7", step)
    assert d.idempotency_key("r7", step) != d.idempotency_key("r8", step)


def test_janitor_recovers_a_run_whose_lease_expired(store):
    """Without a janitor a crashed run sits in 'running' forever — nothing retries it
    and nothing reports it failed."""
    c = Clock()
    s = CheckpointStore(":memory:", clock=c)
    s.create_run("r9", "tenant-a", "v1", lease_seconds=30.0)
    calls = []
    with pytest.raises(StepFailed):
        WorkflowDriver(s, pipeline(calls, crash_on="validate"), lease_seconds=30.0).drive("r9")

    s.set_run_status("r9", "running")     # the worker died before marking it failed
    assert s.find_abandoned_runs() == []  # lease still valid — correctly left alone
    c.advance(120.0)
    assert [r.run_id for r in s.find_abandoned_runs()] == ["r9"]

    resumed = []
    recovered = Janitor(s, lambda: WorkflowDriver(s, pipeline(resumed))).sweep()
    assert recovered == ["r9"]
    assert resumed == ["validate", "publish"]
    s.close()


def test_input_hash_is_order_independent():
    assert input_hash({"a": 1, "b": 2}) == input_hash({"b": 2, "a": 1})
    assert input_hash({"a": 1}) != input_hash({"a": 2})
