import importlib


def test_app_url_trims_trailing_slash(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com/")
    from app.core import settings

    importlib.reload(settings)

    assert settings.get_app_url() == "https://bidpilot.rglens.com"


def test_cors_origins_include_local_defaults(monkeypatch):
    monkeypatch.delenv("DOCPILOT_CORS_ORIGINS", raising=False)
    from app.core import settings

    importlib.reload(settings)

    assert "http://localhost:5173" in settings.get_cors_origins()
    assert "http://127.0.0.1:5173" in settings.get_cors_origins()
    assert "http://localhost:5174" in settings.get_cors_origins()
    assert "http://127.0.0.1:5174" in settings.get_cors_origins()


def test_cors_origins_parse_comma_list(monkeypatch):
    monkeypatch.setenv(
        "DOCPILOT_CORS_ORIGINS",
        "https://bidpilot.rglens.com, https://api.bidpilot.rglens.com/",
    )
    from app.core import settings

    importlib.reload(settings)

    assert settings.get_cors_origins() == [
        "https://bidpilot.rglens.com",
        "https://api.bidpilot.rglens.com",
    ]
