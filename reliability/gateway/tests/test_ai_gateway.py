import json

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-gateway"))
from gateway_client import AIGateway, GatewayConfigError, build_clients


def gw():
    return AIGateway("acct-123", "prod-gw")


def test_base_url_is_provider_specific():
    assert gw().base_url("openai").endswith("/acct-123/prod-gw/openai")
    assert gw().base_url("anthropic").endswith("/acct-123/prod-gw/anthropic")
    assert gw().base_url("bedrock").endswith("/aws-bedrock")


def test_unknown_provider_is_rejected():
    with pytest.raises(GatewayConfigError):
        gw().base_url("my-llm")


def test_incomplete_config_fails_at_construction():
    with pytest.raises(GatewayConfigError):
        AIGateway("", "prod-gw")


def test_missing_env_raises_rather_than_bypassing_the_gateway():
    """Silently falling back to a direct provider call loses metering and caching with
    no signal — worse than never configuring it."""
    with pytest.raises(GatewayConfigError) as exc:
        AIGateway.from_env({"CF_ACCOUNT_ID": "acct-123"})
    assert "CF_AI_GATEWAY_ID" in str(exc.value)


def test_from_env_builds_a_usable_gateway():
    g = AIGateway.from_env({"CF_ACCOUNT_ID": "a", "CF_AI_GATEWAY_ID": "b"})
    assert g.base_url("openai") == \
        "https://gateway.ai.cloudflare.com/v1/a/b/openai"


def test_cache_ttl_header():
    assert gw().headers(cache_ttl=3600)["cf-aig-cache-ttl"] == "3600"


def test_skip_cache_wins_over_ttl():
    h = gw().headers(cache_ttl=3600, skip_cache=True)
    assert h["cf-aig-skip-cache"] == "true" and "cf-aig-cache-ttl" not in h


def test_negative_ttl_is_rejected():
    with pytest.raises(GatewayConfigError):
        gw().headers(cache_ttl=-1)


def test_metadata_tags_spend_by_tenant():
    """The analytics question people actually ask is 'which customer costs this much'."""
    h = gw().headers(metadata={"tenant": "acme", "agent": "support"})
    assert json.loads(h["cf-aig-metadata"])["tenant"] == "acme"


def test_clients_are_pointed_at_the_gateway():
    captured = {}

    def fake_sdk(api_key, base_url):
        captured["key"], captured["url"] = api_key, base_url
        return object()

    build_clients(gw(), {"openai": "sk-test"}, {"openai": fake_sdk})
    assert captured["key"] == "sk-test"
    assert captured["url"] == "https://gateway.ai.cloudflare.com/v1/acct-123/prod-gw/openai"


def test_missing_key_is_a_configuration_error():
    with pytest.raises(GatewayConfigError):
        build_clients(gw(), {}, {"openai": lambda **kw: None})


def test_account_id_is_url_escaped():
    assert "/a%2Fb/" in AIGateway("a/b", "g").base_url("openai")
