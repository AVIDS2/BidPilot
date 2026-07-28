from fastapi.testclient import TestClient

from app.main import app


def test_openapi_schema_available() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()


def test_openapi_exposes_one_assistant_execution_path() -> None:
    paths = app.openapi()["paths"]
    assistant_paths = {path for path in paths if path.startswith("/assistant")}

    assert assistant_paths == {"/assistant/attachments", "/assistant/stream"}
    assert not any("operator" in path for path in paths)
