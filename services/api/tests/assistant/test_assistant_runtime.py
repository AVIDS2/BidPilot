from app.assistant.runtime import _extract_project_name


def test_extract_project_name_preserves_spaces() -> None:
    assert _extract_project_name("创建项目，名字叫 星河 2026 投标") == "星河 2026 投标"
