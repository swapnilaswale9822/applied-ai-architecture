"""Checkpoint storage.

Two tables. ``workflow_run`` is the run; ``workflow_step_run`` is the per-step ledger that
makes resumption possible.

The invariant everything depends on: **a step's output and its status are written in the
same transaction.** If they were separate writes, a crash between them leaves a step marked
complete with no output (resume skips work that never happened) or an output with no status
(resume redoes completed work). One transaction removes the window entirely.

SQLite here so the tests run with no infrastructure; the schema and the transaction boundary
are the same on Postgres.
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

PENDING, RUNNING, COMPLETED, FAILED = "pending", "running", "completed", "failed"

SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_run (
    run_id              TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL,
    definition_version  TEXT NOT NULL,
    status              TEXT NOT NULL,
    current_step        TEXT,
    lease_expires_at    REAL,
    created_at          REAL NOT NULL,
    updated_at          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_step_run (
    run_id       TEXT NOT NULL,
    step_key     TEXT NOT NULL,
    attempt      INTEGER NOT NULL DEFAULT 1,
    status       TEXT NOT NULL,
    input_hash   TEXT NOT NULL,
    output       TEXT,
    error        TEXT,
    started_at   REAL,
    ended_at     REAL,
    PRIMARY KEY (run_id, step_key),
    FOREIGN KEY (run_id) REFERENCES workflow_run(run_id)
);

CREATE INDEX IF NOT EXISTS idx_run_lease ON workflow_run(status, lease_expires_at);
"""


@dataclass
class WorkflowRun:
    run_id: str
    tenant_id: str
    definition_version: str
    status: str
    current_step: Optional[str]
    lease_expires_at: Optional[float]


@dataclass
class StepRecord:
    run_id: str
    step_key: str
    attempt: int
    status: str
    input_hash: str
    output: Any
    error: Optional[str]


class CheckpointStore:
    def __init__(self, dsn: str = ":memory:", clock=None):
        self._clock = clock or time.time
        self._conn = sqlite3.connect(dsn)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- runs ----------------------------------------------------------

    def create_run(self, run_id, tenant_id, definition_version, lease_seconds=60.0) -> WorkflowRun:
        now = self._clock()
        self._conn.execute(
            "INSERT INTO workflow_run (run_id, tenant_id, definition_version, status,"
            " current_step, lease_expires_at, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (run_id, tenant_id, definition_version, RUNNING, None,
             now + lease_seconds, now, now),
        )
        self._conn.commit()
        return self.get_run(run_id)

    def get_run(self, run_id) -> Optional[WorkflowRun]:
        r = self._conn.execute(
            "SELECT * FROM workflow_run WHERE run_id = ?", (run_id,)).fetchone()
        if not r:
            return None
        return WorkflowRun(r["run_id"], r["tenant_id"], r["definition_version"],
                           r["status"], r["current_step"], r["lease_expires_at"])

    def set_run_status(self, run_id, status, current_step=None) -> None:
        self._conn.execute(
            "UPDATE workflow_run SET status = ?, current_step = COALESCE(?, current_step),"
            " updated_at = ? WHERE run_id = ?",
            (status, current_step, self._clock(), run_id))
        self._conn.commit()

    def renew_lease(self, run_id, lease_seconds=60.0) -> None:
        self._conn.execute(
            "UPDATE workflow_run SET lease_expires_at = ?, updated_at = ? WHERE run_id = ?",
            (self._clock() + lease_seconds, self._clock(), run_id))
        self._conn.commit()

    def find_abandoned_runs(self) -> List[WorkflowRun]:
        """Runs still marked running whose lease expired — the worker died holding them."""
        rows = self._conn.execute(
            "SELECT * FROM workflow_run WHERE status = ? AND lease_expires_at < ?",
            (RUNNING, self._clock())).fetchall()
        return [WorkflowRun(r["run_id"], r["tenant_id"], r["definition_version"],
                            r["status"], r["current_step"], r["lease_expires_at"])
                for r in rows]

    # ---- steps ---------------------------------------------------------

    def get_step(self, run_id, step_key) -> Optional[StepRecord]:
        r = self._conn.execute(
            "SELECT * FROM workflow_step_run WHERE run_id = ? AND step_key = ?",
            (run_id, step_key)).fetchone()
        if not r:
            return None
        return StepRecord(r["run_id"], r["step_key"], r["attempt"], r["status"],
                          r["input_hash"],
                          json.loads(r["output"]) if r["output"] is not None else None,
                          r["error"])

    def start_step(self, run_id, step_key, input_hash) -> int:
        prior = self.get_step(run_id, step_key)
        attempt = (prior.attempt + 1) if prior else 1
        self._conn.execute(
            "INSERT INTO workflow_step_run (run_id, step_key, attempt, status, input_hash,"
            " started_at) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(run_id, step_key) DO UPDATE SET attempt = excluded.attempt,"
            " status = excluded.status, input_hash = excluded.input_hash,"
            " started_at = excluded.started_at, error = NULL",
            (run_id, step_key, attempt, RUNNING, input_hash, self._clock()))
        self._conn.commit()
        return attempt

    def complete_step(self, run_id, step_key, output) -> None:
        """Write the output and the completed status **atomically**.

        This single transaction is the entire durability guarantee. Splitting it reintroduces
        the crash window that checkpointing exists to close.
        """
        with self._conn:  # BEGIN ... COMMIT, rolled back on any exception
            self._conn.execute(
                "UPDATE workflow_step_run SET status = ?, output = ?, ended_at = ?"
                " WHERE run_id = ? AND step_key = ?",
                (COMPLETED, json.dumps(output), self._clock(), run_id, step_key))
            self._conn.execute(
                "UPDATE workflow_run SET current_step = ?, updated_at = ? WHERE run_id = ?",
                (step_key, self._clock(), run_id))

    def fail_step(self, run_id, step_key, error) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE workflow_step_run SET status = ?, error = ?, ended_at = ?"
                " WHERE run_id = ? AND step_key = ?",
                (FAILED, str(error), self._clock(), run_id, step_key))

    def completed_steps(self, run_id) -> Dict[str, Any]:
        rows = self._conn.execute(
            "SELECT step_key, output FROM workflow_step_run"
            " WHERE run_id = ? AND status = ?", (run_id, COMPLETED)).fetchall()
        return {r["step_key"]: json.loads(r["output"]) for r in rows}
