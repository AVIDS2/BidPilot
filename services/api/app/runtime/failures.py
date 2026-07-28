"""Safe public failures for governed runtime boundaries.

Runtime exceptions may include provider payloads, SQL fragments, or internal
resource details.  This module maps them to the small stable contract that can
be stored in RuntimeRun/RuntimeAction and rendered to an end user.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError


@dataclass(frozen=True)
class PublicRuntimeFailure:
    error_code: str
    message: str


def classify_capability_failure(exc: BaseException) -> PublicRuntimeFailure:
    """Return a stable public failure without serializing exception text."""
    if isinstance(exc, HTTPException):
        if exc.status_code in {401, 403}:
            return PublicRuntimeFailure(
                "capability_forbidden",
                "当前账号没有执行这项操作的权限。",
            )
        if exc.status_code == 404:
            return PublicRuntimeFailure(
                "capability_resource_not_found",
                "未找到需要操作的项目或资料。",
            )
        if exc.status_code == 409:
            return PublicRuntimeFailure(
                "capability_conflict",
                "当前操作与最新状态冲突，请刷新项目状态后再试。",
            )
        if exc.status_code in {400, 413, 415, 422}:
            return PublicRuntimeFailure(
                "capability_input_invalid",
                "操作参数无效或缺少必要信息，请补充后重试。",
            )
        if exc.status_code == 429:
            return PublicRuntimeFailure(
                "capability_rate_limited",
                "当前操作请求过于频繁，请稍后重试。",
            )
        if exc.status_code >= 500:
            return PublicRuntimeFailure(
                "capability_unavailable",
                "当前操作服务暂时不可用，请稍后重试。",
            )
    if isinstance(exc, PermissionError):
        return PublicRuntimeFailure(
            "capability_forbidden",
            "当前账号没有执行这项操作的权限。",
        )
    if isinstance(exc, IntegrityError):
        return PublicRuntimeFailure(
            "capability_conflict",
            "当前操作与最新状态冲突，请刷新项目状态后再试。",
        )
    if isinstance(exc, OperationalError):
        return PublicRuntimeFailure(
            "capability_unavailable",
            "当前操作服务暂时不可用，请稍后重试。",
        )
    if isinstance(exc, LookupError):
        return PublicRuntimeFailure(
            "capability_resource_not_found",
            "未找到需要操作的项目或资料。",
        )
    if isinstance(exc, ValueError):
        # These are server-owned validation outcomes. Keep their public meaning
        # without echoing a dynamic project name or any raw exception payload.
        raw = str(exc)
        if "审批已过期" in raw:
            return PublicRuntimeFailure(
                "approval_expired",
                "审批已过期或不可用，请重新发起操作。",
            )
        if "完整项目名称" in raw:
            return PublicRuntimeFailure(
                "capability_confirmation_invalid",
                "删除项目需要输入完整项目名称进行确认。",
            )
        if "审批数据异常" in raw:
            return PublicRuntimeFailure(
                "approval_unavailable",
                "审批状态异常，请重新发起操作。",
            )
        if _contains_sensitive_error_marker(raw):
            return PublicRuntimeFailure(
                "capability_execution_failed",
                "操作未能完成，敏感错误详情已隐藏（***redacted***）。",
            )
    if isinstance(exc, (TypeError, ValueError)):
        return PublicRuntimeFailure(
            "capability_input_invalid",
            "操作参数无效或缺少必要信息，请补充后重试。",
        )
    return PublicRuntimeFailure(
        "capability_execution_failed",
        "操作未能完成，请稍后重试。",
    )


def _contains_sensitive_error_marker(raw: str) -> bool:
    normalized = raw.casefold()
    return any(
        marker in normalized
        for marker in ("api_key", "api key", "authorization", "bearer ", "token=", "password=")
    )
