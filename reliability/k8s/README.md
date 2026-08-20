# Kubernetes manifests  🔵

Manifests for the API tier and the worker tier. Production currently runs Docker Compose on
VMs — see [ADR: ship the boring version first](../../HOW_I_WORK.md). These are the designed
migration, written out rather than described.

```bash
kubectl apply --dry-run=client -f agent-service.yaml -f worker.yaml
```

## The decision that matters: what each tier scales on

**API tier scales on CPU.** It is CPU-bound between model calls, so utilisation tracks load.

**Worker tier scales on queue depth, not CPU** — and this is the detail that separates
someone who has run async LLM workloads from someone who has read about autoscaling.

A Celery worker waiting on a 30-second model response is **idle on CPU** while the backlog
grows behind it. CPU-based autoscaling therefore scales *down* at exactly the moment it
should scale up, and the queue keeps growing while the cluster reports everything healthy.
Queue length is the signal that matches the workload, which is why the worker tier uses a
KEDA `ScaledObject` reading Redis directly.

The threshold (`listLength: 20`) is derived, not guessed: measure task duration and worker
concurrency, and set it so one replica drains roughly one poll interval of backlog.

## Probes

| Probe | Checks | Why |
|---|---|---|
| **Readiness** | Database and broker reachable | A probe that returns 200 unconditionally is *worse* than none — it removes the signal while looking healthy, so traffic keeps arriving at a pod that cannot serve it. |
| **Liveness** | Process responsive only — deliberately shallow | If liveness checked dependencies too, one database blip would restart every pod simultaneously, turning a degradation into an outage. |
| **Startup** | Same as liveness, generous budget | Keeps slow warm-up (index load, model client init) out of the liveness thresholds, instead of inflating `initialDelaySeconds` and blinding the check for the pod's whole life. |

## Graceful shutdown

Three settings work together, and all three are needed:

- **`terminationGracePeriodSeconds`** — 90s on the API (an in-flight LLM call must finish),
  300s on workers (a task must not die mid-run).
- **`preStop: sleep 5`** on the API — lets the endpoints controller deregister the pod
  before the server starts shutting down. Without it, a rolling deploy drops requests that
  were routed microseconds earlier.
- **`PodDisruptionBudget`** — a node drain cannot take the tier below a working minimum.

Without checkpointing ([`../durable_workflow/`](../durable_workflow/)) a worker killed
mid-run loses its progress, which is why the worker grace period is generous and why
checkpointing is the companion piece to this manifest, not a separate concern.

## Resource limits — one deliberate asymmetry

Memory limits are set on both tiers; a **CPU limit is set on neither**.

CPU limits cause throttling, and throttling a latency-critical service to enforce a number
nobody is billing for trades real user-facing latency for a tidier graph. Requests are set
so the scheduler places pods correctly; limits are omitted so a burst can use idle capacity.
Memory is different — unbounded memory growth gets a pod OOMKilled and threatens its
neighbours, so that limit stays, alongside `--max-tasks-per-child` on workers to bound the
slow growth that long-lived Python processes accumulate.

## Status

🔵 Written and validated (`kubectl --dry-run`), not applied to a production cluster.
The trigger condition for migrating is in [`HOW_I_WORK.md`](../../HOW_I_WORK.md).
