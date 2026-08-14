from app.runtime.registry import format_public_result


def test_export_result_keeps_the_real_project_and_deliverable_navigation_facts() -> None:
    result = format_public_result(
        "export_deliverable",
        {
            "project_id": "project-1",
            "deliverable_id": "deliverable-1",
            "deliverable_title": "技术响应文件",
            "export_id": "export-1",
            "format": "docx",
            "status": "ready",
            "download_path": "/exports/export-1/docx",
            "persisted": True,
        },
    )

    assert result.summary == "交付物「技术响应文件」导出已就绪，可直接下载或打开交付页。"
    assert result.payload == {
        "project_id": "project-1",
        "deliverable_id": "deliverable-1",
        "deliverable_title": "技术响应文件",
        "export_id": "export-1",
        "format": "docx",
        "download_path": "/exports/export-1/docx",
        "persisted": True,
    }


def test_section_workflow_result_keeps_project_identity_for_the_canvas_link() -> None:
    result = format_public_result(
        "start_draft_section",
        {
            "run_id": "draft-run-1",
            "runtime_run_id": "runtime-run-1",
            "project_id": "project-1",
            "section_key": "technical-approach",
        },
    )

    assert result.summary == "章节「technical-approach」起草工作流已启动。"
    assert result.payload == {
        "run_id": "draft-run-1",
        "runtime_run_id": "runtime-run-1",
        "project_id": "project-1",
        "section_key": "technical-approach",
    }
