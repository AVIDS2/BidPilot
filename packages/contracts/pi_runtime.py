"""Pure Pi runtime mappings shared by API and Worker processes."""

from __future__ import annotations


def pi_thinking_level(reasoning_effort: str | None) -> str:
    return {
        None: "off",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "extra": "high",
        "max": "xhigh",
    }.get(reasoning_effort, "off")


def pi_model_api(provider_type: str, provider_id: str | None) -> str:
    value = f"{provider_type} {provider_id or ''}".casefold()
    return "anthropic-messages" if "anthropic" in value else "openai-completions"


def pi_model_provider(provider_type: str, provider_id: str | None, base_url: str | None) -> str:
    """Map platform profiles to Pi's built-in provider identifiers.

    The API keeps ``mimo`` as its stable product profile. Pi's official catalog
    calls the direct-balance endpoint ``xiaomi`` and reserves the regional
    Token Plan endpoints for their own provider IDs. Unknown/custom URLs stay
    custom so a user gateway is never silently replaced by a built-in endpoint.
    """
    profile = (provider_id or "").casefold()
    url = (base_url or "").casefold()
    xiaomi_hosts = (
        "api.xiaomimimo.com",
        "token-plan-cn.xiaomimimo.com",
        "token-plan-ams.xiaomimimo.com",
        "token-plan-sgp.xiaomimimo.com",
    )
    official_host = any(host in url for host in xiaomi_hosts)
    if profile == "mimo" and not url:
        return "xiaomi"
    if not (profile in {"xiaomi", "xiaomi-token-plan-cn", "xiaomi-token-plan-ams", "xiaomi-token-plan-sgp"}
            or official_host):
        return provider_id or provider_type
    if "token-plan-cn.xiaomimimo.com" in url or profile == "xiaomi-token-plan-cn":
        return "xiaomi-token-plan-cn"
    if "token-plan-ams.xiaomimimo.com" in url or profile == "xiaomi-token-plan-ams":
        return "xiaomi-token-plan-ams"
    if "token-plan-sgp.xiaomimimo.com" in url or profile == "xiaomi-token-plan-sgp":
        return "xiaomi-token-plan-sgp"
    return "xiaomi"


__all__ = ["pi_model_api", "pi_model_provider", "pi_thinking_level"]
