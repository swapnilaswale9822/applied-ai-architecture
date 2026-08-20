# Cloudflare AI Gateway  🔵

Routes LLM traffic through an edge gateway. Integration is a **base-URL swap** on the
existing provider client — no code restructure, which is what makes it cheap enough to
adopt before you strictly need it.

```python
from gateway_client import AIGateway

gw = AIGateway.from_env()                 # CF_ACCOUNT_ID, CF_AI_GATEWAY_ID
client = OpenAI(api_key=key, base_url=gw.base_url("openai"))

client.chat.completions.create(
    model="gpt-4o", messages=[...],
    extra_headers=gw.headers(cache_ttl=3600, metadata={"tenant": "acme"}),
)
```

## What it buys, without touching application code

| | |
|---|---|
| **Caching** | Repeated prompts served without a provider call — cost and latency both drop |
| **Analytics** | Tokens, cost, latency, error rate per model, in one place |
| **Rate limiting** | A ceiling that is *yours*, independent of the provider's |
| **Failover** | Provider outage handled at the edge |

Tag every call with `metadata={"tenant": ...}`. Untagged traffic makes the analytics answer
"we spent this much"; tagged traffic answers "**which customer** generated this spend",
which is the question that actually gets asked.

## Two deliberate design choices

**Missing configuration raises instead of falling back to a direct provider call.** A
gateway that quietly stops being used is worse than one never configured: metering and
caching vanish with no signal, and nobody notices until the bill or an incident.

**Account and gateway ids are escaped with `safe=""`.** An id containing a slash would
otherwise inject an extra path segment into the URL. Caught by a test, not by review.

## What it does not replace

Per-tenant authorisation, guardrails, and grounding checks. Those need request context the
edge does not have — see [`../../governance-layer/`](../../governance-layer/).

## Status

🔵 Reference implementation, unit-tested (`../tests/test_ai_gateway.py`). Creating the
gateway itself is a dashboard step; the wiring is here and exercised.
