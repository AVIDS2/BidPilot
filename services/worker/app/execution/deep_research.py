"""Worker-owned generic Deep Research pipeline.

This is deliberately separate from the Pi conversational loop. Pi starts a
durable run; this module owns bounded planning, parallel retrieval, source
reading, claim checks and report synthesis.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from trafilatura import extract
import fitz

from app.adapters.structured_llm import invoke_structured_text
from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.documents.web_import import fetch_public_http_resource
from app.models import RuntimeRun, User
from app.providers.service import get_provider_config
from app.runtime.model import resolve_agent_model
from app.security.secrets import decrypt_secret
from contracts.runtime import RuntimeEventType, RuntimeRunStatus

from app.runtime.events import (
    complete_runtime_run,
    fail_runtime_run,
    publish_runtime_event,
)
from app.execution.task_outbox import claim_workflow_task_delivery, complete_workflow_task_delivery

logger = logging.getLogger(__name__)

_MAX_QUERY_CHARS = 12_000
_MAX_EXCERPT_CHARS = 3_000
_MAX_PLAN_QUERIES = 8
_MAX_SOURCES = 16
_RESEARCH_PHASES = {"scope", "plan", "retrieve", "read", "verify", "synthesize", "package"}


def execute_deep_research(runtime_run_id: str, *, outbox_event_id: str | None = None) -> dict[str, Any]:
    if not claim_workflow_task_delivery(outbox_event_id):
        return {"status": "duplicate", "runtime_run_id": runtime_run_id}
    db = SessionLocal()
    try:
        run = db.get(RuntimeRun, runtime_run_id)
        if run is None:
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "missing", "runtime_run_id": runtime_run_id}
        if run.status in {RuntimeRunStatus.SUCCEEDED.value, RuntimeRunStatus.FAILED.value, RuntimeRunStatus.CANCELLED.value}:
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": run.status, "runtime_run_id": run.id}
        user_row = db.get(User, run.user_id)
        if user_row is None:
            fail_runtime_run(run.id, "深度调研所属用户不存在。", error_code="deep_research_user_missing")
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "failed", "runtime_run_id": run.id}
        user = _current_user(user_row)
        run.status = RuntimeRunStatus.RUNNING.value
        run.started_at = run.started_at or datetime.now(UTC).replace(tzinfo=None)
        db.commit()

        result = asyncio.run(_run_pipeline(run, user))
        complete_runtime_run(run.id, result=result)
        complete_workflow_task_delivery(outbox_event_id)
        return {"status": "succeeded", "runtime_run_id": run.id}
    except Exception as exc:  # noqa: BLE001 - terminal error is redacted
        logger.exception("Deep Research run failed: %s", runtime_run_id)
        fail_runtime_run(run.id if "run" in locals() and run is not None else runtime_run_id, str(exc), error_code="deep_research_failed")
        complete_workflow_task_delivery(outbox_event_id)
        return {"status": "failed", "runtime_run_id": runtime_run_id}
    finally:
        db.close()


async def _run_pipeline(run: RuntimeRun, user: CurrentUser) -> dict[str, Any]:
    source = run.input_json if isinstance(run.input_json, dict) else {}
    query = str(source.get("query") or "").strip()[:_MAX_QUERY_CHARS]
    depth = str(source.get("depth") or "standard")
    source_policy = str(source.get("source_policy") or "official_first")
    max_queries = min(max(int(source.get("max_queries") or 5), 1), _MAX_PLAN_QUERIES)
    max_sources = min(max(int(source.get("max_sources") or 10), 1), _MAX_SOURCES)
    if not query:
        raise ValueError("deep_research_query_missing")

    presentation = {
        "presentation_kind": "deep_research",
        "presentation_session_id": run.id,
        "presentation_title": "深度调研",
    }
    _progress(run.id, "scope", "已确定研究问题与来源边界。", {"query": query, "depth": depth, **presentation})
    provider = _resolve_provider(run, user)
    plan = await _plan_queries(query, max_queries=max_queries, source_policy=source_policy, provider=provider)
    _progress(run.id, "plan", f"研究计划已生成，将从 {len(plan)} 个互补角度检索。", {"queries": plan, **presentation})

    search_results = await asyncio.to_thread(_parallel_search, user, plan)
    sources = _deduplicate_sources(search_results, max_sources=max_sources)
    _progress(
        run.id,
        "retrieve",
        f"已收集 {len(sources)} 个候选来源，开始读取正文。",
        {"count": len(sources), "sources": _public_sources(sources), **presentation},
    )

    read_sources = await asyncio.to_thread(_parallel_read, sources)
    readable = [item for item in read_sources if item["status"] == "read"]
    for item in readable:
        _progress(
            run.id,
            "read",
            f"已读取来源：{item['title'][:120]}。",
            {"source_id": item["source_id"], "url": item["url"], **presentation},
        )

    claims = await _extract_and_verify_claims(query, readable, provider)
    _progress(
        run.id,
        "verify",
        f"已完成 {len(claims)} 条主张的来源核验。",
        {"claims": claims, **presentation},
    )
    report = await _synthesize_report(query, claims, readable, provider)
    _progress(run.id, "synthesize", "证据已综合，正在生成研究报告。", {**presentation})
    result = {
        "query": query,
        "depth": depth,
        "plan": plan,
        "sources": _public_sources(read_sources),
        "claims": claims,
        "report": report,
        "source_count": len(readable),
        "claim_count": len(claims),
        "generated_at": datetime.now(UTC).isoformat(),
        **presentation,
    }
    _progress(
        run.id,
        "package",
        "深度调研报告已生成，来源与主张均已保留。",
        {"source_count": len(readable), "claim_count": len(claims), "report_ready": True, **presentation},
    )
    return result


def _current_user(row: User) -> CurrentUser:
    return CurrentUser(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        plan=row.subscription.plan if row.subscription is not None else "starter",
        email_verified=row.email_verified,
        disabled=row.disabled,
        org_id=row.org_id,
        org_slug=row.organization.slug if row.organization is not None else "",
    )


def _resolve_provider(run: RuntimeRun, user: CurrentUser) -> dict[str, str | None]:
    db = SessionLocal()
    try:
        config = get_provider_config(db, run.provider_config_id, user.id) if run.provider_config_id else None
        resolved = (
            resolve_agent_model(
                provider_type=config.provider_type,
                provider_id=config.provider_id,
                api_key=decrypt_secret(config.api_key),
                base_url=config.api_url,
                model=run.model or config.model,
            )
            if config is not None
            else resolve_agent_model()
        )
        return {
            "provider_type": resolved.provider_type,
            "provider_id": resolved.provider_id,
            "api_key": resolved.api_key,
            "api_url": resolved.base_url,
            "model": resolved.model,
        }
    finally:
        db.close()


async def _plan_queries(
    query: str,
    *,
    max_queries: int,
    source_policy: str,
    provider: dict[str, str | None],
) -> list[dict[str, Any]]:
    system = (
        "You are a research planner. Return JSON only. Decompose one research question into "
        "independent, non-overlapping web investigation angles. Do not answer the question. "
        f"Source policy: {source_policy}; use official or primary sources first when requested."
    )
    prompt = json.dumps({"question": query, "max_queries": max_queries, "source_policy": source_policy}, ensure_ascii=False)
    try:
        response = await asyncio.to_thread(
            invoke_structured_text,
            system_prompt=system,
            user_prompt=prompt,
            provider_config={
                "api_key": provider["api_key"],
                "api_url": provider["api_url"],
                "model": provider["model"],
                "provider_id": provider["provider_id"],
            },
            provider_type=str(provider["provider_type"] or "openai"),
            max_output_tokens=1800,
            temperature=0.1,
            reasoning_effort="high",
        )
        parsed = _parse_json(response.content)
        raw = parsed.get("queries") if isinstance(parsed, dict) else None
        if isinstance(raw, list):
            result: list[dict[str, Any]] = []
            for index, item in enumerate(raw[:max_queries], start=1):
                if isinstance(item, dict):
                    value = str(item.get("query") or "").strip()
                    purpose = str(item.get("purpose") or "").strip()
                else:
                    value, purpose = str(item).strip(), ""
                if value:
                    result.append({"id": f"Q{index}", "query": value[:500], "purpose": purpose[:300]})
            if result:
                return result
    except Exception:
        logger.warning("Deep Research planner failed; using one bounded query", exc_info=True)
    return [{"id": "Q1", "query": query[:500], "purpose": "核心问题"}]


def _parallel_search(user: CurrentUser, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def search_one(item: dict[str, Any]) -> dict[str, Any]:
        db = SessionLocal()
        try:
            result = _search_public_web(item["query"], limit=6)
            return {"query_id": item["id"], "query": item["query"], "purpose": item.get("purpose", ""), "result": result}
        except Exception as exc:  # noqa: BLE001 - one angle may fail safely
            return {"query_id": item["id"], "query": item["query"], "purpose": item.get("purpose", ""), "result": {}, "error": type(exc).__name__}
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=min(5, max(1, len(plan)))) as pool:
        futures = [pool.submit(search_one, item) for item in plan]
        return sorted((future.result() for future in as_completed(futures)), key=lambda item: str(item.get("query_id") or ""))


def _search_public_web(query: str, *, limit: int) -> dict[str, Any]:
    """Worker-local search adapter; do not import the API application package.

    The Worker has a module named ``app.drafting`` for graph execution, which
    intentionally shadows the API's ``app.drafting`` package. Keeping this
    narrow HTTP adapter local prevents a cross-service import from breaking a
    queued research run while preserving the same Hikari wire contract.
    """
    query = query.strip()
    base_url = (os.getenv("TAVILY_HIKARI_BASE_URL") or os.getenv("TAVILY_API_BASE_URL") or "").strip().rstrip("/")
    tavily_key = (os.getenv("DOCPILOT_TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY") or "").strip()
    hikari_token = (os.getenv("TAVILY_HIKARI_TOKEN") or tavily_key).strip()
    provider = "duckduckgo"
    items: list[dict[str, str]] = []
    if base_url or tavily_key:
        provider = "tavily_hikari" if base_url else "tavily"
        endpoint = base_url if base_url.endswith("/search") else f"{base_url}/search" if base_url else "https://api.tavily.com/search"
        headers = {"Authorization": f"Bearer {hikari_token}"} if base_url and hikari_token else {}
        body: dict[str, Any] = {"query": query, "max_results": limit, "include_answer": False, "search_depth": "basic"}
        if not base_url:
            body["api_key"] = tavily_key
        response = httpx.post(endpoint, headers=headers, json=body, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        for row in (payload.get("results") or [])[:limit]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            snippet = str(row.get("content") or row.get("snippet") or "").strip()
            if title and url:
                items.append({"title": title[:200], "url": url[:500], "snippet": snippet[:500]})
    else:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=15.0,
            headers={"User-Agent": "BidPilotDeepResearch/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload.get("AbstractText"), str) and payload.get("AbstractURL"):
            items.append({"title": str(payload.get("Heading") or query)[:200], "url": str(payload["AbstractURL"])[:500], "snippet": str(payload["AbstractText"])[:500]})
        for row in (payload.get("RelatedTopics") or [])[:limit]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("Text") or "").strip()
            url = str(row.get("FirstURL") or "").strip()
            if title and url:
                items.append({"title": title[:120], "url": url[:500], "snippet": title[:500]})
            if len(items) >= limit:
                break
    return {"query": query, "provider": provider, "count": len(items), "items": items}


def _deduplicate_sources(search_results: list[dict[str, Any]], *, max_sources: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for batch in search_results:
        result = batch.get("result") if isinstance(batch.get("result"), dict) else {}
        items = result.get("items") if isinstance(result.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = _canonical_url(item.get("url"))
            title = str(item.get("title") or "").strip()
            if not url or not title or url in seen:
                continue
            seen.add(url)
            source_id = f"S{len(sources) + 1}"
            sources.append({
                "source_id": source_id,
                "title": title[:240],
                "url": url,
                "snippet": str(item.get("snippet") or "").strip()[:800],
                "query_ids": [batch.get("query_id")],
                "status": "candidate",
            })
            if len(sources) >= max_sources:
                return sources
    return sources


def _parallel_read(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def read_one(source: dict[str, Any]) -> dict[str, Any]:
        result = dict(source)
        try:
            data, content_type, final_url = fetch_public_http_resource(source["url"])
            text = ""
            if "pdf" in content_type.lower() or data.startswith(b"%PDF"):
                document = fitz.open(stream=data, filetype="pdf")
                text = "\n\n".join(page.get_text("text") for page in document)
                document.close()
            elif "html" in content_type or data.lstrip().lower().startswith((b"<html", b"<!doctype")):
                text = extract(data.decode("utf-8", errors="replace"), output_format="markdown", include_tables=True, include_links=True, url=final_url) or ""
            else:
                text = data.decode("utf-8", errors="replace")
            text = text.strip()
            if not text:
                raise ValueError("source_body_empty")
            result.update({"status": "read", "final_url": final_url, "content_type": content_type, "content_excerpt": text[:_MAX_EXCERPT_CHARS]})
        except Exception as exc:  # noqa: BLE001 - source failures stay in the ledger
            result.update({"status": "unreadable", "error_code": type(exc).__name__})
        return result

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(sources)))) as pool:
        futures = [pool.submit(read_one, source) for source in sources]
        return sorted((future.result() for future in as_completed(futures)), key=lambda item: str(item.get("source_id") or ""))


async def _extract_and_verify_claims(
    query: str,
    sources: list[dict[str, Any]],
    provider: dict[str, str | None],
) -> list[dict[str, Any]]:
    packet = [
        {"source_id": item["source_id"], "title": item["title"], "url": item["url"], "text": item.get("content_excerpt", "")}
        for item in sources[:12]
    ]
    prompt = json.dumps({"question": query, "sources": packet}, ensure_ascii=False)
    system = (
        "You are an evidence verifier. Return JSON only with claims. Each claim must cite one or more "
        "source_id values from the supplied packet. Mark unsupported claims as uncertain and do not invent facts. "
        "Schema: {claims:[{claim,source_ids,confidence,verification,contradiction}]}"
    )
    try:
        response = await asyncio.to_thread(
            invoke_structured_text,
            system_prompt=system,
            user_prompt=prompt,
            provider_config={"api_key": provider["api_key"], "api_url": provider["api_url"], "model": provider["model"], "provider_id": provider["provider_id"]},
            provider_type=str(provider["provider_type"] or "openai"),
            max_output_tokens=5000,
            temperature=0.1,
            reasoning_effort="high",
        )
        parsed = _parse_json(response.content)
        raw = parsed.get("claims") if isinstance(parsed, dict) else None
        if isinstance(raw, list):
            valid_ids = {item["source_id"] for item in sources}
            output: list[dict[str, Any]] = []
            for index, item in enumerate(raw[:40], start=1):
                if not isinstance(item, dict):
                    continue
                claim = str(item.get("claim") or "").strip()
                source_ids = [str(value) for value in item.get("source_ids", []) if str(value) in valid_ids]
                if not claim:
                    continue
                try:
                    confidence = max(0.0, min(float(item.get("confidence") or 0), 1.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                output.append({
                    "claim_id": f"C{index}",
                    "claim": claim[:1200],
                    "source_ids": source_ids,
                    "confidence": confidence,
                    "verification": "verified" if source_ids else "uncertain",
                    "contradiction": str(item.get("contradiction") or "")[:600],
                })
            return output
    except Exception:
        logger.warning("Deep Research claim verification failed", exc_info=True)
    return []


async def _synthesize_report(
    query: str,
    claims: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    provider: dict[str, str | None],
) -> str:
    prompt = json.dumps({"question": query, "claims": claims, "sources": _public_sources(sources)}, ensure_ascii=False)
    system = (
        "Write a concise Chinese research report in Markdown. Separate verified facts, uncertainty and inference. "
        "Cite sources inline as [S1], [S2] using only supplied source IDs. Include: executive summary, findings, risks, "
        "open questions, recommendations and sources. Never invent URLs or unsupported claims."
    )
    try:
        response = await asyncio.to_thread(
            invoke_structured_text,
            system_prompt=system,
            user_prompt=prompt,
            provider_config={"api_key": provider["api_key"], "api_url": provider["api_url"], "model": provider["model"], "provider_id": provider["provider_id"]},
            provider_type=str(provider["provider_type"] or "openai"),
            max_output_tokens=9000,
            temperature=0.2,
            reasoning_effort="high",
        )
        return response.content.strip()
    except Exception:
        logger.warning("Deep Research report synthesis failed", exc_info=True)
        lines = [f"# 深度调研：{query}", "", "## 已核验主张"]
        lines.extend(f"- {item['claim']} " + " ".join(f"[{sid}]" for sid in item["source_ids"]) for item in claims)
        return "\n".join(lines)


def _progress(runtime_run_id: str, phase: str, summary: str, payload: dict[str, Any]) -> None:
    if phase not in _RESEARCH_PHASES:
        raise ValueError(f"deep_research_phase_invalid: {phase}")
    publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_PROGRESSED,
        summary,
        {"capability": "deep_research", "phase": phase, **payload},
    )


def _canonical_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    except ValueError:
        return ""


def _public_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in source.items()
            if key in {"source_id", "title", "url", "final_url", "snippet", "status", "content_type", "query_ids", "error_code"}
        }
        for source in sources
    ]


def _parse_json(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {}


__all__ = ["execute_deep_research"]
