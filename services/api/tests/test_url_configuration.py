import importlib
from unittest.mock import patch


def test_invitation_email_uses_configured_app_url(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
    from app.email import service

    importlib.reload(service)

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_invitation_email("user@example.com", "invite-token", "default")

    assert sent
    assert "https://bidpilot.rglens.com/register?invitation=invite-token" in sent[0].body_text
    assert "http://localhost:5173" not in sent[0].body_text


def test_verification_and_reset_urls_use_configured_app_url(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
    from app.email import service

    importlib.reload(service)

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_email_verification_email("user@example.com", "verify-token")
        service.send_password_reset_email("user@example.com", "reset-token")

    bodies = "\n".join(message.body_text for message in sent)
    assert "https://bidpilot.rglens.com/verify-email?token=verify-token" in bodies
    assert "https://bidpilot.rglens.com/reset-password?token=reset-token" in bodies
