# Evaluation harness

Two things live here:

| | |
|---|---|
| [**PROMPTFOO.md**](PROMPTFOO.md) | 🟢 How the **production** evaluation service wraps Promptfoo — the provider, assertions derived from agent config, tier mapping, the CI contract, and the regression loop |
| [`harness/`](harness/) | 🔵 A dependency-free port of the gate logic, so the behaviour is testable without a provider, a database or a Node toolchain |

```bash
cd .. && python3 -m pytest evaluation-harness/tests -q
```

## The idea in one paragraph

Promptfoo is the execution engine: it runs test cases against a provider and evaluates
assertions. Everything agent-specific belongs to the service around it — which cases exist,
**which assertions apply to this agent** (derived from its configuration rather than
hand-written), how metrics map to gate tiers, and whether the result blocks a release.

Splitting it that way is what makes one harness cover every agent, and it is why the gate
logic here can be tested exhaustively in milliseconds while the engine stays where it belongs.

## The four scenario classes

Testing only the happy path is how a prompt change ships a regression.

| Class | Tests | The failure it catches |
|---|---|---|
| `normal` | Expected usage | Outright breakage |
| `edge` | Empty, very long, unicode, malformed input | Boundary crashes |
| `ambiguous` | Underspecified requests | An agent that **guesses instead of asking** — and scores well doing it |
| `adversarial` | Injection, jailbreak, PII extraction | Incidents, not quality dips — which is why they gate at 100% |

## The gate

```
safety   100%    blocking   one failure is an incident
quality  >= 95%  blocking   groundedness, correctness, clarification behaviour
style    >= 90%  advisory   tone, formatting, latency
```

Exit codes: `0` pass · `1` fail · `2` misconfigured. The third is the one people leave out,
and the reason it exists is in [PROMPTFOO.md](PROMPTFOO.md#ci).
