def generate_section(project_id: str, section_key: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "section_key": section_key,
        "markdown": "Generated section",
        "evidence_ids": [],
    }
