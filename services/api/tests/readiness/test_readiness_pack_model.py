from app.models import ReadinessPack


def test_readiness_pack_is_versioned_and_persists_artifact_metadata() -> None:
    columns = ReadinessPack.__table__.columns
    constraints = {constraint.name for constraint in ReadinessPack.__table__.constraints}

    assert "project_id" in columns
    assert "version_number" in columns
    assert "formula_version" in columns
    assert "source_fingerprint" in columns
    assert "summary_json" in columns
    assert "xlsx_storage_key" in columns
    assert "docx_storage_key" in columns
    assert "generated_by_user_id" in columns
    assert "uq_readiness_pack_project_version" in constraints
