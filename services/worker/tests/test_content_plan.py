"""Unit tests for the deterministic content-plan node."""

from app.graph.nodes.content_plan import build_content_plan, content_plan_node


def test_build_content_plan_picks_evidence_and_key_points() -> None:
    plan = build_content_plan(
        section_key="technical-approach",
        evidence_chunks=[
            {
                "chunk_id": "c1",
                "content": "智慧社区综合管理平台采用微服务架构，支持门禁、停车与安防统一接入。",
            },
            {
                "chunk_id": "c2",
                "content": "系统架构图展示三层部署拓扑，并支持国产数据库与中间件。",
            },
        ],
        requirements=[{"requirement_text": "须支持信创环境部署。"}],
    )
    assert plan["section_key"] == "technical-approach"
    assert plan["evidence_picks"]
    assert any("信创" in point for point in plan["key_points"])
    assert plan["figures"]  # architecture cue
    assert plan["tables"]
    assert not plan["gaps"]


def test_content_plan_node_clears_stale_draft_on_replan() -> None:
    result = content_plan_node(
        {
            "section_key": "technical-approach",
            "evidence_chunks": [
                {"chunk_id": "c1", "content": "一期完成基础平台与门禁联动。"}
            ],
            "requirements": [],
            "draft_created": True,
            "draft_markdown": "old draft",
            "review_result": {"passed": False, "issues": ["too short"], "suggestions": [], "overall_score": 0.2},
            "review_passed": False,
            "human_decision": "rejected_with_feedback",
        }
    )
    assert result["content_plan_ready"] is True
    assert result["draft_created"] is False
    assert result["draft_markdown"] == ""
    assert result["review_result"] is None
    assert result["human_decision"] is None
    assert result["content_plan"]["key_points"]
