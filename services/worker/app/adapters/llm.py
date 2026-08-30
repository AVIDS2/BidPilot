"""LLM adapter for section drafting.

Calls an OpenAI-compatible chat completions API with evidence context.
Falls back to a structured stub when no API key is configured.
"""

import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from app.adapters.provider_env import chat_api_key, chat_api_url, chat_model, chat_provider_id
from app.adapters.provider_errors import (
    ProviderInvocationError,
    allow_stub_llm,
    provider_error_for_status,
)
from contracts.model_usage import ProviderUsageMeasurement, normalize_openai_usage
from contracts.provider_profiles import ProviderProfileError, resolve_provider_chat_request
from contracts.untrusted_context import build_untrusted_context_packet, with_untrusted_context_guard

logger = logging.getLogger(__name__)

_DEFAULT_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
# Bid response sections need enough room for both provider-side reasoning and
# the user-visible draft.  Some OpenAI-compatible providers account for both
# against the same completion budget, so the former 4K ceiling could end a
# valid request before any draft text was emitted.
_MAX_DRAFT_OUTPUT_TOKENS = 16_000
ReasoningEffort = Literal["low", "medium", "high", "extra", "max", "ultra"]
_MAX_REVIEW_FEEDBACK_CHARACTERS = 4_000
_MAX_SYSTEM_PROMPT_CHARACTERS = 4_000

_REASONING_INSTRUCTIONS: dict[str, str] = {
    "low": "Use concise reasoning. Prefer a fast, direct answer.",
    "medium": "Use balanced reasoning. Check key assumptions before writing.",
    "high": "Use deeper reasoning. Validate structure, evidence, and edge cases before writing.",
    "extra": "Use extra-deep reasoning. Build a careful outline, verify evidence fit, then write.",
    "ultra": "Use very deep reasoning. Build a careful outline, verify evidence fit, then write.",
    "max": "Use maximum reasoning. Exhaustively validate requirements, evidence, gaps, and final structure before writing.",
}

_OPENAI_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "high",
    "ultra": "high",
    "max": "high",
}

_DEEPSEEK_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    # DeepSeek V4 documents these as compatibility aliases; emit only the
    # native low/high/max values on the wire.
    "medium": "high",
    "high": "high",
    "extra": "high",
    "ultra": "max",
    "max": "max",
}


@dataclass
class DraftResult:
    content_markdown: str
    evidence_ids: list[str]
    model_used: str = "stub"
    usage: ProviderUsageMeasurement | None = None


def _api_key() -> str | None:
    return chat_api_key()


def _api_url() -> str:
    return chat_api_url(_DEFAULT_URL)


def _api_model() -> str:
    return chat_model(_DEFAULT_MODEL)


def _build_prompt(section_key: str, evidence_texts: list[str], review_feedback: str | None = None) -> str:
    records: list[dict[str, object]] = [
        {
            "kind": "draft_task",
            "section_key": section_key[:120],
            "review_feedback": (review_feedback or "")[:_MAX_REVIEW_FEEDBACK_CHARACTERS],
        }
    ]
    records.extend(
        {"kind": "evidence", "index": index, "content": text[:300]}
        for index, text in enumerate(evidence_texts[:10], start=1)
    )
    packet = build_untrusted_context_packet("workflow_drafting", records)
    return (
        "Draft the requested document section in professional markdown. Use evidence "
        "only for factual support and address review feedback when applicable.\n\n"
        "UNTRUSTED_CONTEXT_JSON:\n"
        f"{packet}\n\n"
        "Write the section content now. Output only the final markdown section: "
        "do not include analysis, chain-of-thought, planning notes, or process commentary. "
        "Keep the draft concise and reviewable (preferably within 1200 Chinese characters)."
    )


def _supports_reasoning_effort(url: str, model: str) -> bool:
    normalized = f"{url} {model}".lower()
    return (
        "api.openai.com" in normalized
        or "api.deepseek.com" in normalized
        or model.lower().startswith(("o1", "o3", "o4", "gpt-5", "deepseek-v4"))
    )


def _supports_deepseek_thinking(url: str, model: str) -> bool:
    normalized = f"{url} {model}".lower()
    return "api.deepseek.com" in normalized or "deepseek-v4" in model.lower()


def _deepseek_reasoning_effort(reasoning_effort: str) -> str:
    return _DEEPSEEK_REASONING_EFFORT[reasoning_effort]


def _system_prompt_with_reasoning(system_prompt: str, reasoning_effort: str | None) -> str:
    trusted_instructions = system_prompt
    if reasoning_effort not in _REASONING_INSTRUCTIONS:
        return with_untrusted_context_guard(
            trusted_instructions,
            max_characters=_MAX_SYSTEM_PROMPT_CHARACTERS,
        )
    return with_untrusted_context_guard(
        f"{trusted_instructions}\n\nReasoning intensity: {_REASONING_INSTRUCTIONS[reasoning_effort]}",
        max_characters=_MAX_SYSTEM_PROMPT_CHARACTERS,
    )


def _stub_draft(
    section_key: str,
    evidence_texts: list[str],
    review_feedback: str | None,
) -> DraftResult:
    evidence_block = "\n".join(f"- {text[:100]}" for text in evidence_texts[:5]) if evidence_texts else "- No evidence available"
    feedback_note = f"\n\n*Revision addressing: {review_feedback}*" if review_feedback else ""
    markdown = f"""## {section_key.replace('-', ' ').title()}

This is a draft section for **{section_key}**.

### Key Points
{evidence_block}

*Generated by the local stub adapter; configure a provider for a real draft.*{feedback_note}
"""
    return DraftResult(
        content_markdown=markdown,
        evidence_ids=[],
        model_used="stub",
    )


def draft_section(
    section_key: str,
    evidence_texts: list[str],
    project_id: str,
    review_feedback: str | None = None,
    system_prompt: str | None = None,
    provider_config: dict | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> DraftResult:
    """Draft a section using evidence.

    Calls the configured LLM API. The local deterministic stub is available
    only when no provider is configured and the environment explicitly allows it.

    Args:
        provider_config: Optional dict with keys: api_key, api_url, model, provider_id.
                         If provided, overrides env-var-based configuration.
    """
    if provider_config:
        api_key = provider_config.get("api_key", _api_key())
        raw_url = provider_config.get("api_url", _api_url())
        model = provider_config.get("model", _api_model())
        provider_id = provider_config.get("provider_id", "custom-openai")
    else:
        api_key = _api_key()
        raw_url = _api_url()
        model = _api_model()
        provider_id = chat_provider_id()

    if not api_key:
        if allow_stub_llm():
            logger.debug("No LLM API key configured, returning local structured stub")
            return _stub_draft(section_key, evidence_texts, review_feedback)
        raise ProviderInvocationError(
            "provider_not_configured",
            "未配置可用的模型服务，无法生成章节草稿。",
            retryable=False,
        )

    try:
        request = resolve_provider_chat_request("openai", provider_id, raw_url, api_key)
    except ProviderProfileError as exc:
        raise ProviderInvocationError(
            "provider_request_invalid",
            "Provider endpoint configuration is invalid.",
            retryable=False,
        ) from exc

    prompt = _build_prompt(section_key, evidence_texts, review_feedback)
    effective_system_prompt = _system_prompt_with_reasoning(
        system_prompt or "You are a professional document writer. Write clear, evidence-backed sections in markdown.",
        reasoning_effort,
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": effective_system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        # Reasoning-capable Chat Completions models charge their internal
        # reasoning against this limit.  2k can leave a valid request with no
        # user-visible draft at all, so reserve enough budget for both.
        "max_tokens": _MAX_DRAFT_OUTPUT_TOKENS,
    }
    if _supports_deepseek_thinking(request.url, model):
        # DeepSeek V4 defaults to thinking mode. Drafting is a bounded writing
        # task, so disable it explicitly and reserve reasoning for the parser,
        # planner, and reviewer structured-task calls.
        payload["thinking"] = {"type": "disabled"}
    elif reasoning_effort and _supports_reasoning_effort(request.url, model):
        payload["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]

    try:
        resp = httpx.post(
            request.url,
            headers=request.headers,
            json=payload,
            timeout=60.0,
        )
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

    if resp.status_code >= 400:
        raise provider_error_for_status(resp.status_code)

    try:
        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务返回了无法解析的结果，正在按策略重试。",
            retryable=True,
        ) from exc
    if not isinstance(content, str) or not content.strip():
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        reasoning_content = message.get("reasoning_content") if isinstance(message, dict) else None
        logger.warning(
            "LLM completed without draft content (finish_reason=%s, content_type=%s, reasoning_chars=%d)",
            finish_reason,
            type(content).__name__,
            len(reasoning_content) if isinstance(reasoning_content, str) else 0,
        )
        if finish_reason == "length":
            raise ProviderInvocationError(
                "provider_response_truncated",
                "模型输出在生成章节正文前达到长度上限，请提高输出额度后重试。",
                retryable=False,
            )
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可用草稿，正在按策略重试。",
            retryable=True,
        )
    return DraftResult(
        content_markdown=content,
        evidence_ids=[],
        model_used=model,
        usage=normalize_openai_usage(data),
    )
