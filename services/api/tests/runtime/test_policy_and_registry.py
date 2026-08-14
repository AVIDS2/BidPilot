from __future__ import annotations

import pytest

from app.runtime.policy import evaluate_policy
from app.runtime.registry import format_public_result, get_capability_definition
from contracts.runtime import RuntimePolicyOutcome, RuntimeRiskLevel


@pytest.mark.parametrize(
    ("capability", "risk", "requires_approval_in_risky_only"),
    [
        ("search_projects", RuntimeRiskLevel.READ, False),
        ("list_knowledge_portfolio", RuntimeRiskLevel.READ, False),
        ("get_readiness_summary", RuntimeRiskLevel.READ, False),
        ("create_project", RuntimeRiskLevel.LOW_RISK_WRITE, True),
        ("start_draft_section", RuntimeRiskLevel.COSTING, True),
        ("propose_memory_graph", RuntimeRiskLevel.COSTING, True),
        ("delete_project", RuntimeRiskLevel.DESTRUCTIVE, True),
    ],
)
def test_registry_policy_metadata(
    capability: str,
    risk: RuntimeRiskLevel,
    requires_approval_in_risky_only: bool,
) -> None:
    definition = get_capability_definition(capability)
    decision = evaluate_policy(definition, approval_mode="risky_only")

    assert definition.risk_level is risk
    assert decision.requires_approval is requires_approval_in_risky_only


def test_full_access_keeps_hard_confirmation_for_destructive_actions() -> None:
    create_decision = evaluate_policy(get_capability_definition("create_project"), approval_mode="full_access")
    delete_decision = evaluate_policy(get_capability_definition("delete_project"), approval_mode="full_access")

    assert create_decision.outcome is RuntimePolicyOutcome.ALLOW
    assert delete_decision.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL
    assert delete_decision.requires_typed_confirmation is True


def test_public_formatter_owns_user_facing_summary() -> None:
    result = format_public_result("search_projects", {"count": 2})

    assert result.summary == "找到 2 个项目。"
    assert "search_projects" not in result.summary
    assert result.payload == {"count": 2}


def test_search_projects_formatter_exposes_ids_for_name_collisions() -> None:
    result = format_public_result(
        "search_projects",
        {
            "items": [
                {
                    "id": "aaaaaaaa-1111-2222-3333-444444444444",
                    "short_id": "aaaaaaaa",
                    "name": "AI KIMI投资",
                    "status": "active",
                    "created_at": "2026-07-20T00:00:00",
                    "name_collision": True,
                },
                {
                    "id": "bbbbbbbb-1111-2222-3333-444444444444",
                    "short_id": "bbbbbbbb",
                    "name": "AI KIMI投资",
                    "status": "active",
                    "created_at": "2026-07-21T00:00:00",
                    "name_collision": True,
                },
            ]
        },
    )

    assert "同名" in result.summary
    assert "aaaaaaaa" in result.summary
    assert "bbbbbbbb" in result.summary
    assert result.payload["count"] == 2
    assert result.payload["projects"][0]["id"].startswith("aaaaaaaa")
    assert result.payload["projects"][0]["short_id"] == "aaaaaaaa"


def test_knowledge_portfolio_formatter_exposes_only_safe_aggregate_fields() -> None:
    result = format_public_result(
        "list_knowledge_portfolio",
        {
            "items": [
                {
                    "project_id": "project-1",
                    "project_name": "投标项目 A",
                    "active_shared_count": 3,
                    "proposed_shared_count": 1,
                    "latest_compilation_status": "succeeded",
                    "body_markdown": "must-not-leak",
                    "citations": [{"label": "must-not-leak"}],
                }
            ]
        },
    )

    assert result.summary == "已检查 1 个可访问项目的知识状态。"
    assert result.payload == {
        "count": 1,
        "projects": [
            {
                "project_id": "project-1",
                "project_name": "投标项目 A",
                "active_shared_count": 3,
                "proposed_shared_count": 1,
                "latest_compilation_status": "succeeded",
            }
        ],
    }


def test_workflow_formatter_exposes_only_safe_run_identifiers() -> None:
    result = format_public_result(
        "start_draft_section",
        {
            "run_id": "execution-run-1",
            "runtime_run_id": "runtime-run-1",
            "provider_api_key": "must-not-leak",
        },
    )

    assert result.summary == "起草工作流已启动。"
    assert result.payload == {"run_id": "execution-run-1", "runtime_run_id": "runtime-run-1"}


def test_memory_graph_formatter_exposes_only_workflow_status() -> None:
    result = format_public_result(
        "propose_memory_graph",
        {
            "run_id": "execution-run-1",
            "runtime_run_id": "runtime-run-1",
            "memory_record_id": "source-memory-id",
            "structured_data_json": {"must_not": "leak"},
            "reused": False,
        },
    )

    assert result.summary == "实体关系提案已启动。"
    assert result.payload == {
        "run_id": "execution-run-1",
        "runtime_run_id": "runtime-run-1",
        "reused": False,
    }


def test_retry_formatter_exposes_only_the_new_attempt_identifiers() -> None:
    result = format_public_result(
        "retry_run",
        {
            "id": "execution-run-2",
            "runtime_run_id": "runtime-run-2",
            "parent_execution_run_id": "execution-run-1",
            "input_json": {"provider_api_key": "must-not-leak"},
        },
    )

    assert result.summary == "已创建新的工作流尝试。"
    assert result.payload == {"run_id": "execution-run-2", "runtime_run_id": "runtime-run-2"}


def test_outline_formatter_keeps_section_keys_for_harness_chaining() -> None:
    result = format_public_result(
        "get_project_outline",
        {
            "project_id": "project-1",
            "project_name": "AI KIMI投资",
            "outline_count": 2,
            "drafted_count": 0,
            "approved_count": 0,
            "items": [
                {
                    "section_key": "executive_summary",
                    "title": "执行摘要",
                    "status": "missing",
                    "has_content": False,
                    "in_template": True,
                    "secret_blob": "must-not-leak",
                },
                {
                    "section_key": "solution",
                    "title": "技术方案",
                    "status": "draft",
                    "has_content": False,
                    "in_template": True,
                },
            ],
        },
    )

    assert "大纲共 2 章" in result.summary
    assert result.payload["project_id"] == "project-1"
    assert result.payload["sections"] == [
        {
            "section_key": "executive_summary",
            "title": "执行摘要",
            "status": "missing",
            "has_content": False,
            "in_template": True,
        },
        {
            "section_key": "solution",
            "title": "技术方案",
            "status": "draft",
            "has_content": False,
            "in_template": True,
        },
    ]
    assert "secret_blob" not in result.payload["sections"][0]


def test_list_sections_formatter_keeps_section_keys() -> None:
    result = format_public_result(
        "list_sections",
        {
            "items": [
                {
                    "id": "sec-1",
                    "deliverable_id": "del-1",
                    "section_key": "executive_summary",
                    "title": "执行摘要",
                    "status": "draft",
                    "has_content": False,
                    "raw_markdown": "must-not-leak",
                }
            ],
            "drafted_count": 0,
            "approved_count": 0,
        },
    )

    assert result.payload["count"] == 1
    assert result.payload["sections"][0]["section_key"] == "executive_summary"
    assert "raw_markdown" not in result.payload["sections"][0]


def test_web_search_and_upload_formatters_keep_safe_fields() -> None:
    web = format_public_result(
        "web_search",
        {
            "query": "AI 投标",
            "provider": "tavily",
            "count": 1,
            "items": [
                {
                    "title": "示例",
                    "url": "https://example.com",
                    "snippet": "摘要",
                    "raw_score": 0.9,
                }
            ],
        },
    )
    assert web.payload["count"] == 1
    assert web.payload["items"][0]["url"] == "https://example.com"
    assert "raw_score" not in web.payload["items"][0]

    upload = format_public_result(
        "fetch_url_to_project",
        {
            "project_id": "p1",
            "bundle_id": "b1",
            "document_id": "d1",
            "filename": "policy.pdf",
            "bytes": 12,
            "source_url": "https://example.com/policy.pdf",
            "parse_status": "pending",
            "secret": "nope",
        },
    )
    assert "policy.pdf" in upload.summary
    assert upload.payload["document_id"] == "d1"
    assert "secret" not in upload.payload


def test_list_documents_formatter_exposes_readiness_without_document_content() -> None:
    result = format_public_result(
        "list_documents",
        {
            "items": [
                {
                    "id": "doc-indexed",
                    "original_filename": "招标文件.pdf",
                    "parse_status": "parsed",
                    "index_status": "indexed",
                    "bundle_label": "招标资料",
                    "bundle_status": "indexed",
                    "body_markdown": "must-not-leak",
                },
                {
                    "id": "doc-archive",
                    "original_filename": "投标工具.zip",
                    "parse_status": "not_applicable",
                    "index_status": "not_applicable",
                    "bundle_label": "招标资料",
                    "bundle_status": "stored",
                    "storage_key": "must-not-leak",
                },
            ]
        },
    )

    assert result.summary == "找到 2 个文档：1 个已完成解析并建立检索索引；1 个为仅归档附件、不可语义检索。"
    assert result.payload["indexed_count"] == 1
    assert result.payload["archived_count"] == 1
    assert result.payload["documents"] == [
        {
            "id": "doc-indexed",
            "original_filename": "招标文件.pdf",
            "parse_status": "parsed",
            "index_status": "indexed",
            "bundle_label": "招标资料",
            "bundle_status": "indexed",
        },
        {
            "id": "doc-archive",
            "original_filename": "投标工具.zip",
            "parse_status": "not_applicable",
            "index_status": "not_applicable",
            "bundle_label": "招标资料",
            "bundle_status": "stored",
        },
    ]


def test_readiness_gaps_formatter_exposes_actionable_fields_without_source_locator() -> None:
    result = format_public_result(
        "list_readiness_gaps",
        {
            "kind": "evidence",
            "items": [
                {
                    "id": "req-1",
                    "requirement_text": "提供团队资质证明",
                    "risk_level": "high",
                    "coverage_status": "uncovered",
                    "evidence_status": "missing",
                    "source_locator_json": {"page": 8, "must_not": "leak"},
                }
            ],
        },
    )

    assert result.summary == "找到 1 个待处理缺口。"
    assert result.payload == {
        "count": 1,
        "kind": "evidence",
        "gaps": [
            {
                "id": "req-1",
                "requirement_text": "提供团队资质证明",
                "risk_level": "high",
                "coverage_status": "uncovered",
                "evidence_status": "missing",
            }
        ],
    }


def test_write_section_formatter_exposes_safe_section_identifiers() -> None:
    result = format_public_result(
        "write_section",
        {
            "section_id": "sec-1",
            "section_key": "executive_summary",
            "section_title": "执行摘要",
            "section_version_id": "ver-1",
            "version_number": 2,
            "deliverable_id": "del-1",
            "content_markdown": "must-not-leak",
            "char_count": 12,
        },
    )

    assert "执行摘要" in result.summary
    assert result.payload == {
        "section_id": "sec-1",
        "section_key": "executive_summary",
        "section_title": "执行摘要",
        "section_version_id": "ver-1",
        "version_number": 2,
        "deliverable_id": "del-1",
    }
    assert "content_markdown" not in result.payload
