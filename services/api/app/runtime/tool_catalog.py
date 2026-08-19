"""Server-owned tool schemas shared by Pi and the retired Python harness.

This module contains declarative capability metadata only. It must never inspect
user text or select a tool/skill from phrases. Model-native Pi decides tool use.
"""

from __future__ import annotations

from typing import Any

from .registry import CAPABILITY_REGISTRY

_READ_SKILL_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "read_skill",
        "description": "Load one server-owned procedural skill by its exact AVAILABLE_SKILLS name.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact skill name from AVAILABLE_SKILLS",
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

# Minimal OpenAI-compatible argument schemas. Keep these product-facing and
# small; execute_capability remains the real validation boundary.
_TOOL_PARAMETER_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_projects": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Optional project name or phrase"}},
        "additionalProperties": False,
    },
    "create_demo_workspace": {"type": "object", "properties": {}, "additionalProperties": False},
    "create_project": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
            "scenario_package": {"type": "string", "description": "Scenario package key", "default": "bidpilot"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    "get_project_summary": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_project_bundles": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_sections": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "get_project_outline": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_pending_reviews": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "submit_review_decision": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_id": {"type": "string"},
            "section_version_id": {
                "type": "string",
                "description": "Immutable candidate version selected from list_pending_reviews",
            },
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "comment": {"type": "string"},
        },
        "required": ["project_id", "section_id", "section_version_id", "decision"],
        "additionalProperties": False,
    },
    "list_requirements": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_claim_review_queue": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "get_readiness_summary": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_readiness_gaps": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "kind": {
                "type": "string",
                "enum": ["all", "high_risk", "mandatory", "evidence", "contradictions", "overdue", "uncovered"],
                "description": "Gap kind filter. Use mandatory for requirement gaps and evidence for evidence gaps.",
                "default": "all",
            },
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "open_requirement_source": {
        "type": "object",
        "properties": {"requirement_id": {"type": "string"}},
        "required": ["requirement_id"],
        "additionalProperties": False,
    },
    "list_evidence": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_deliverables": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_documents": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "attach_uploaded_documents": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "attachment_ids": {"type": "array", "items": {"type": "string"}},
            "bundle_id": {"type": "string"},
        },
        "required": ["project_id", "attachment_ids"],
        "additionalProperties": False,
    },
    "get_section_versions": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "section_key": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "create_deliverable": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "title": {"type": "string"}},
        "required": ["project_id", "title"],
        "additionalProperties": False,
    },
    "start_draft_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {"type": "string"},
            "section_id": {
                "type": "string",
                "description": "Exact section id returned by get_project_outline/list_sections",
            },
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
            "allow_empty_evidence": {
                "type": "boolean",
                "description": (
                    "Set true only when the user explicitly asks to draft without "
                    "uploaded materials (e.g. 自行拟草)."
                ),
            },
        },
        "required": ["project_id", "section_key"],
        "additionalProperties": False,
    },
    "write_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {
                "type": "string",
                "description": "Outline section_key from get_project_outline/list_sections",
            },
            "section_id": {
                "type": "string",
                "description": "Exact section id when an outline has duplicate section_key values",
            },
            "content_markdown": {
                "type": "string",
                "description": "Full markdown body to persist as a new section version",
            },
            "title": {
                "type": "string",
                "description": "Optional section title when creating a missing outline chapter",
            },
        },
        "required": ["project_id", "section_key", "content_markdown"],
        "additionalProperties": False,
    },
    "start_redraft_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {"type": "string"},
            "section_id": {
                "type": "string",
                "description": "Exact section id returned by get_project_outline/list_sections",
            },
            "review_feedback": {
                "type": "string",
                "description": "Human review feedback to guide the redraft",
            },
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id", "section_key"],
        "additionalProperties": False,
    },
    "resume_draft_run": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Execution run id awaiting human approval"},
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "feedback": {"type": "string", "description": "Optional feedback when rejecting"},
        },
        "required": ["run_id", "decision"],
        "additionalProperties": False,
    },
    "propose_memory_graph": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "memory_record_id": {"type": "string"},
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id", "memory_record_id"],
        "additionalProperties": False,
    },
    "get_runtime_status": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "retry_run": {
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
        "additionalProperties": False,
    },
    "export_deliverable": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "deliverable_id": {"type": "string"},
            "format": {"type": "string", "enum": ["docx", "pdf"], "default": "docx"},
        },
        "required": ["deliverable_id"],
        "additionalProperties": False,
    },
    "generate_readiness_pack": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "semantic_search": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["project_id", "query"],
        "additionalProperties": False,
    },
    "web_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for the public web"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "discover_remote_documents": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "One public notice page to inspect for direct PDF/DOCX/XLSX links; never persisted",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project scope used only for read authorization",
            },
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    "fetch_url_to_project": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "url": {"type": "string", "description": "http(s) URL of one chosen direct artifact or explicitly requested web evidence"},
            "filename": {"type": "string"},
            "bundle_id": {"type": "string"},
            "import_mode": {
                "type": "string",
                "enum": ["artifact", "web_evidence"],
                "default": "artifact",
                "description": "artifact for a real file; web_evidence only when the user explicitly asks to preserve webpage text",
            },
        },
        "required": ["project_id", "url"],
        "additionalProperties": False,
    },
    "upload_document": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "attachment_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Staged chat attachment IDs to ingest into the project",
            },
            "filename": {"type": "string"},
            "content_base64": {
                "type": "string",
                "description": "Small agent-generated file body (base64), max 10MB",
            },
            "content_type": {"type": "string"},
            "bundle_id": {"type": "string"},
            "bundle_label": {"type": "string"},
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "search_bid_wiki": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "query": {"type": "string"}},
        "required": ["project_id", "query"],
        "additionalProperties": False,
    },
    "list_knowledge_portfolio": {"type": "object", "properties": {}, "additionalProperties": False},
    "propose_memory": {
        "type": "object",
        "properties": {
            "body_markdown": {"type": "string"},
            "title": {"type": "string"},
            "scope": {"type": "string"},
            "kind": {"type": "string"},
        },
        "required": ["body_markdown"],
        "additionalProperties": False,
    },
    "forget_memory": {
        "type": "object",
        "properties": {"memory_id": {"type": "string"}},
        "required": ["memory_id"],
        "additionalProperties": False,
    },
    "open_page": {
        "type": "object",
        "properties": {"route": {"type": "string"}},
        "required": ["route"],
        "additionalProperties": False,
    },
    "delete_project": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "run_section_campaign": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["plan", "framework", "draft_workflow"],
                "description": (
                    "plan: planner-only worklist; "
                    "framework: write short outline-first skeletons into empty sections; "
                    "draft_workflow: start governed draft workflows per empty section"
                ),
            },
            "max_sections": {
                "type": "integer",
                "description": "Max sections to process per wave (1-8, default 3)",
            },
            "auto_continue": {
                "type": "boolean",
                "description": "Process multiple waves in one call until empty or max_waves (default true for framework)",
            },
            "max_waves": {
                "type": "integer",
                "description": "Max waves when auto_continue is true (1-6, default 4)",
            },
            "section_keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit section_key list; default = empty template sections",
            },
            "allow_empty_evidence": {
                "type": "boolean",
                "description": "For draft_workflow mode when project has no parsed materials",
            },
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
}


def build_capability_tool_specs(*, allowed_names: frozenset[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI-compatible tool specs derived from the product capability registry."""
    tools: list[dict[str, Any]] = []
    for definition in sorted(CAPABILITY_REGISTRY.values(), key=lambda item: item.name):
        if allowed_names is not None and definition.name not in allowed_names:
            continue
        parameters = _TOOL_PARAMETER_SCHEMAS.get(
            definition.name,
            {"type": "object", "properties": {}, "additionalProperties": True},
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": f"{definition.label_zh} / {definition.label_en}",
                    "parameters": parameters,
                },
            }
        )
    return tools
