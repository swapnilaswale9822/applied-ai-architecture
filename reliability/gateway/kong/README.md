# Kong — API gateway and AI gateway  🔵

Declarative, DB-less Kong in front of the platform's services.

```bash
docker compose up -d
curl -i localhost:8000/api/agent/health                             # 401 — no key
curl -i localhost:8000/api/agent/health -H 'x-api-key: demo-key-acme'
```

## Why a gateway at all

Caching, metering, rate limits, auth and failover are **cross-cutting**. Implementing them
in application code means implementing them again in every service, slightly differently,
and discovering the differences during an incident.

## The two decisions worth arguing about

**Rate-limit on tokens, not requests.** One request can be 200 tokens or 200,000. A
requests-per-minute cap does not protect a budget — it protects a number that correlates
poorly with the thing you actually care about. `ai-rate-limiting-advanced` limits by token
consumption per consumer per window.

**Semantic cache over exact-match cache.** Exact matching almost never hits on natural
language: two users asking the same question phrase it differently. Similarity matching
hits far more often, and brings a real risk — two prompts close in embedding space can
need different answers. The threshold (`0.92` here) is therefore a deliberate trade, not a
default to accept. Set it by measuring false-hit rate on your own traffic, not by taste.

## Deliberate choices in this config

| Setting | Why |
|---|---|
| `retries: 0` | Retries live in the application, beside the circuit breaker. A gateway retrying into a dependency the breaker has already opened is exactly the cascade the breaker exists to stop. |
| `limit_by: consumer` | Per-tenant quotas. A global ceiling lets one tenant's burst consume everyone's allowance. |
| `fault_tolerant: true` | A Redis outage degrades rate limiting; it must not take the API down with it. |
| `correlation-id` | Joins a gateway access log to an OTel span without guesswork. |
| `hide_credentials: true` | Keeps the API key out of upstream logs. |

## Kong vs Cloudflare AI Gateway

They solve different halves and compose cleanly:

- **Kong** is inbound and tenant-facing — auth, per-tenant quotas, request shaping, and it
  fronts *all* APIs, not only LLM traffic. It runs in your infrastructure.
- **Cloudflare AI Gateway** is outbound and provider-facing — caching, analytics, failover,
  nothing to operate. See [`../ai-gateway/`](../ai-gateway/).

**When to use neither:** a single service calling one provider. Both earn their place once
there are multiple services, multiple providers, or a budget somebody is accountable for.
Adopting them earlier is architecture for its own sake.

## Status

🔵 Reference implementation — this config boots and serves. Production ingress is currently
nginx; the migration is designed, not deployed.
