"""Section-key → retrieval query expansion for Chinese knowledge corpora.

English kebab-case section keys (``technical-approach``) do not match Chinese
FTS/trigram indexes. Expand them into bilingual lexical queries and fall back
to a broader project-scoped scan when the primary query returns nothing.
"""

from __future__ import annotations

import re

# BidPilot / ContractPilot section keys → Chinese domain keywords.
# Keep this rule-based (no model call): retrieval must stay cheap and deterministic.
_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "exec-summary": ("执行摘要", "项目概述", "方案综述", "总体目标", "价值主张"),
    "technical-approach": (
        "技术方案",
        "技术路线",
        "架构",
        "系统",
        "平台",
        "微服务",
        "部署",
        "接口",
        "信创",
        "数据库",
        "中间件",
    ),
    "pricing-summary": ("报价", "价格", "费用", "预算", "成本", "商务"),
    "past-performance": ("业绩", "案例", "成功案例", "过往项目", "交付经验", "客户"),
    "staffing-plan": ("人员", "团队", "组织架构", "岗位", "实施团队", "项目经理"),
    "scope-of-work": ("工作范围", "服务范围", "交付范围", "职责"),
    "terms-and-conditions": ("条款", "条件", "合同", "权利义务"),
    "service-level-agreements": ("服务级别", "SLA", "可用性", "响应时间"),
    "payment-terms": ("付款", "支付", "结算", "账期"),
    "compliance-requirements": ("合规", "法规", "标准", "认证", "信创"),
    "risk-assessment": ("风险", "应对", "缓解", "应急"),
}


def expand_section_retrieval_query(section_key: str) -> str:
    """Build a bilingual lexical query from a section key.

    Example: ``technical-approach`` →
    ``technical approach 技术方案 技术路线 架构 系统 平台 ...``
    """
    key = (section_key or "").strip().lower()
    english = re.sub(r"[-_]+", " ", key).strip()
    keywords = list(_SECTION_KEYWORDS.get(key, ()))
    # Always include tokenized English pieces for mixed corpora.
    pieces = [english] if english else []
    pieces.extend(keywords)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for piece in pieces:
        token = piece.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return " ".join(ordered) if ordered else (section_key or "proposal")


def section_fallback_query(section_key: str) -> str:
    """Broader fallback query when the expanded query returns zero hits.

    Prefer high-signal Chinese domain nouns so portable lexical / FTS still
    has something to match against seeded knowledge chunks.
    """
    key = (section_key or "").strip().lower()
    keywords = _SECTION_KEYWORDS.get(key)
    if keywords:
        return " ".join(keywords[:6])
    # Generic Chinese bid-writing terms as last resort.
    return "方案 技术 系统 平台 项目 实施"
