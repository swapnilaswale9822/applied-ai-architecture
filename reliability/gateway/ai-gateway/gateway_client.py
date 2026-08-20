"""Routing LLM traffic through Cloudflare AI Gateway.

The reason this is worth adopting early: integration is a **base-URL swap**, not a code
restructure. The provider SDK is unchanged; only the endpoint moves. That makes it one of
the cheapest pieces of production hygiene available.

    client = OpenAI(api_key=key)                      # before
    client = OpenAI(api_key=key, base_url=gw.base_url("openai"))   # after

Once traffic flows through it you get, without touching application code:

- **Caching** — identical (and optionally similar) prompts served without a provider call
- **Analytics** — tokens, cost, latency and error rate per model, in one place
- **Rate limiting** — a ceiling that is yours, independent of the provider's
- **Failover** — provider outage handled at the edge

What it does *not* replace: per-tenant authorisation, guardrails, and grounding checks.
Those need request context the edge does not have. See ``../../governance-layer/``.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import quote

BASE = "https://gateway.ai.cloudflare.com/v1"

#: Path segment Cloudflare expects per upstream provider.
PROVIDER_SLUGS: Dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "azure-openai": "azure-openai",
    "workers-ai": "workers-ai",
    "google-ai-studio": "google-ai-studio",
    "bedrock": "aws-bedrock",
}


class GatewayConfigError(ValueError):
    """Configuration is incomplete — fail at startup, not on the first request."""


@dataclass(frozen=True)
class AIGateway:
    account_id: str
    gateway_id: str

    def __post_init__(self):
        if not self.account_id or not self.gateway_id:
            raise GatewayConfigError("account_id and gateway_id are both required")

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "AIGateway":
        """Build from ``CF_ACCOUNT_ID`` / ``CF_AI_GATEWAY_ID``.

        Raises rather than silently returning a direct-to-provider client: a gateway that
        quietly stops being used is worse than one that was never configured, because the
        metering and caching disappear without any signal.
        """
        env = env if env is not None else os.environ
        try:
            return cls(env["CF_ACCOUNT_ID"], env["CF_AI_GATEWAY_ID"])
        except KeyError as exc:
            raise GatewayConfigError(f"missing environment variable: {exc.args[0]}") from exc

    def base_url(self, provider: str) -> str:
        """Base URL to hand to the provider SDK."""
        if provider not in PROVIDER_SLUGS:
            raise GatewayConfigError(
                f"unknown provider '{provider}'; expected one of {sorted(PROVIDER_SLUGS)}")
        # safe="" so an id containing a slash cannot inject an extra path segment.
        account = quote(self.account_id, safe="")
        gateway = quote(self.gateway_id, safe="")
        return f"{BASE}/{account}/{gateway}/{PROVIDER_SLUGS[provider]}"

    def headers(self, cache_ttl: Optional[int] = None,
                skip_cache: bool = False,
                metadata: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Per-request gateway controls.

        ``metadata`` is the useful one: tagging each call with a tenant makes the analytics
        answer "which customer is generating this spend", which is the question that
        actually gets asked.
        """
        headers: Dict[str, str] = {}
        if skip_cache:
            headers["cf-aig-skip-cache"] = "true"
        elif cache_ttl is not None:
            if cache_ttl < 0:
                raise GatewayConfigError("cache_ttl must be non-negative")
            headers["cf-aig-cache-ttl"] = str(cache_ttl)
        if metadata:
            import json
            headers["cf-aig-metadata"] = json.dumps(metadata, sort_keys=True)
        return headers


def build_clients(gateway: AIGateway, keys: Dict[str, str], factories: Dict[str, object]):
    """Construct provider SDK clients pointed at the gateway.

    ``factories`` is injected so this is testable without importing provider SDKs:

        build_clients(gw, {"openai": key}, {"openai": OpenAI})
    """
    clients = {}
    for provider, factory in factories.items():
        if provider not in keys:
            raise GatewayConfigError(f"no API key supplied for provider '{provider}'")
        clients[provider] = factory(api_key=keys[provider],
                                    base_url=gateway.base_url(provider))
    return clients
