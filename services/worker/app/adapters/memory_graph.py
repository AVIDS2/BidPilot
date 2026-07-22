"""Provider adapter for one source-bound Bid Wiki graph proposal.

The adapter returns a validated proposal only. It never writes database rows,
activates memory, logs prompts, or accepts evidence outside the caller's
already-authorized memory record.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.adapters.provider_env import chat_api_key, chat_api_url, chat_model
from app.adapters.provider_errors import ProviderInvocationError, provider_error_for_status
from contracts import (
    MemoryCitation,
    MemoryGraphProposal,
    build_untrusted_context_packet,
    with_untrusted_context_guard,
)
from contracts.model_usage import ProviderUsageMeasurement, normalize_anthropic_usage, normalize_openai_usage
from contracts.provider_profiles import ProviderProfileError, infer_provider_id, resolve_provider_chat_request


_DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_MAX_MEMORY_BODY_CHARACTERS = 12_000
_MAX_EVIDENCE_LABEL_CHARACTERS = 320
_MAX_RESPONSE_TOKENS = 1_800


@dataclass(frozen=True)
class MemoryGraphExtractionResult:
    proposal: MemoryGraphProposal
    model_used: str
    usage: ProviderUsageMeasurement | None


def extract_memory_graph(
    *,
    title: str,
    body_markdown: str,
    citations: tuple[MemoryCitation, ...],
    provider_config: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> MemoryGraphExtractionResult:
    """Produce a strict JSON proposal from one already approved memory record."""
    provider_type, provider_id, api_key, raw_url, model = _resolve_provider(provider_config)
    if not api_key:
        raise ProviderInvocationError(
            "provider_not_configured",
            "未配置可用的模型服务，无法生成实体关系提案。",
            retryable=False,
        )
    try:
        request = resolve_provider_chat_request(provider_type, provider_id, raw_url, api_key)
    except ProviderProfileError as exc:
        raise ProviderInvocationError(
            "provider_request_invalid",
            "模型服务地址配置无效，无法生成实体关系提案。",
            retryable=False,
        ) from exc

    system_prompt = (
        "You extract a conservative, evidence-bound bid-domain graph proposal. "
        "Return JSON only, with exactly the MemoryGraphProposal schema. "
        "Use only facts explicitly present in the approved memory text. "
        "Every entity and relation must cite one or more listed evidence_refs. "
        "Use only listed source_type/source_id pairs. Omit ambiguous entities or relations. "
        "Do not include analysis, rationale, markdown fences, hidden reasoning, or extra keys."
    )
    if reasoning_effort:
        system_prompt = f"{system_prompt} Extraction review depth: {reasoning_effort}."
    system_prompt = with_untrusted_context_guard(system_prompt)
    user_prompt = _build_prompt(title, body_markdown, citations)

    if provider_type == "anthropic":
        text, usage = _invoke_anthropic(request.url, request.headers, model, system_prompt, user_prompt)
    else:
        text, usage = _invoke_openai(request.url, request.headers, model, system_prompt, user_prompt)
    proposal = _parse_proposal(text)
    try:
        proposal.validate_evidence_sources({(citation.source_type.value, citation.source_id) for citation in citations})
    except ValueError as exc:
        raise _invalid_provider_response() from exc
    return MemoryGraphExtractionResult(proposal=proposal, model_used=model, usage=usage)


def _resolve_provider(provider_config: dict[str, Any] | None) -> tuple[str, str, str | None, str, str]:
    if provider_config is not None:
        provider_type = str(provider_config.get("provider_type") or "openai")
        raw_url = str(provider_config.get("api_url") or _default_url(provider_type))
        api_key = provider_config.get("api_key")
        model = str(provider_config.get("model") or _default_model(provider_type))
        provider_id = str(provider_config.get("provider_id") or infer_provider_id(provider_type, raw_url))
        return provider_type, provider_id, api_key if isinstance(api_key, str) else None, raw_url, model

    raw_url = chat_api_url(_DEFAULT_OPENAI_URL)
    return "openai", infer_provider_id("openai", raw_url), chat_api_key(), raw_url, chat_model(_DEFAULT_OPENAI_MODEL)


def _default_url(provider_type: str) -> str:
    return _DEFAULT_ANTHROPIC_URL if provider_type == "anthropic" else _DEFAULT_OPENAI_URL


def _default_model(provider_type: str) -> str:
    return _DEFAULT_ANTHROPIC_MODEL if provider_type == "anthropic" else _DEFAULT_OPENAI_MODEL


def _build_prompt(title: str, body_markdown: str, citations: tuple[MemoryCitation, ...]) -> str:
    packet = build_untrusted_context_packet(
        "memory_graph_extraction",
        (
            {
                "kind": "approved_memory",
                "title": title[:240],
                "body_markdown": body_markdown[:_MAX_MEMORY_BODY_CHARACTERS],
                "citations": [
                    {
                        "source_type": citation.source_type.value,
                        "source_id": citation.source_id,
                        "label": citation.label[:_MAX_EVIDENCE_LABEL_CHARACTERS],
                    }
                    for citation in citations
                ],
            },
        ),
    )
    return (
        "Extract only evidence-bound graph items from the source data.\n\n"
        "UNTRUSTED_CONTEXT_JSON:\n"
        f"{packet}\n\n"
        "Schema requirements:\n"
        '{"schema_version":"bidpilot.memory-graph/v1","entities":[{"local_id":"...","canonical_name":"...","entity_type":"...","evidence_refs":[{"source_type":"...","source_id":"..."}]}],"relations":[{"subject_local_id":"...","predicate":"...","object_local_id":"...","evidence_refs":[{"source_type":"...","source_id":"..."}]}]}'
    )


def _invoke_openai(
    url: str,
    headers: dict[str, str],
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, ProviderUsageMeasurement | None]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": _MAX_RESPONSE_TOKENS,
    }
    data = _post_json(url, headers, payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise _invalid_provider_response() from exc
    if not isinstance(content, str) or not content.strip():
        raise _invalid_provider_response()
    return content, normalize_openai_usage(data)


def _invoke_anthropic(
    url: str,
    headers: dict[str, str],
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, ProviderUsageMeasurement | None]:
    payload = {
        "model": model,
        "max_tokens": _MAX_RESPONSE_TOKENS,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    data = _post_json(url, headers, payload)
    try:
        content = "".join(
            block["text"]
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
        )
    except (AttributeError, TypeError) as exc:
        raise _invalid_provider_response() from exc
    if not content.strip():
        raise _invalid_provider_response()
    return content, normalize_anthropic_usage(data)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=90.0)
    except httpx.TimeoutException as exc:
        raise ProviderInvocationError(
            "provider_timeout",
            "模型服务请求超时，正在按策略重试。",
            retryable=True,
        ) from exc
    except httpx.RequestError as exc:
        raise ProviderInvocationError(
            "provider_unavailable",
            "模型服务暂时不可用，正在按策略重试。",
            retryable=True,
        ) from exc
    if response.status_code >= 400:
        raise provider_error_for_status(response.status_code)
    try:
        data = response.json()
    except ValueError as exc:
        raise _invalid_provider_response() from exc
    if not isinstance(data, dict):
        raise _invalid_provider_response()
    return data


def _parse_proposal(content: str) -> MemoryGraphProposal:
    payload = content.strip()
    if payload.startswith("```"):
        payload = payload.split("\n", 1)[1] if "\n" in payload else ""
        if payload.endswith("```"):
            payload = payload[:-3].rstrip()
    try:
        value = json.loads(payload)
        return MemoryGraphProposal.model_validate(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _invalid_provider_response() from exc


def _invalid_provider_response() -> ProviderInvocationError:
    return ProviderInvocationError(
        "provider_response_invalid",
        "模型服务未返回可审核的实体关系提案，请调整模型或稍后重试。",
        retryable=True,
    )
