from unittest.mock import patch


def test_resend_backend_posts_transactional_html_and_text(monkeypatch):
    from app.email import service

    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(service, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(service, "RESEND_FROM", "BidPilot <updates@updates.rglens.com>")
    with patch("app.email.service.urlopen", side_effect=fake_urlopen):
        service.ResendEmailBackend().send(service.EmailMessage(
            to="user@example.com",
            subject="Verify",
            body_text="Plain text",
            body_html="<p>HTML</p>",
        ))

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["headers"]["User-agent"] == "BidPilot/1.0 (+https://bidpilot.rglens.com)"
    assert '"from": "BidPilot <updates@updates.rglens.com>"' in captured["body"]
    assert '"html": "<p>HTML</p>"' in captured["body"]
    assert captured["timeout"] == 15


def test_resend_is_preferred_over_smtp_when_both_are_configured(monkeypatch):
    from app.email import service

    monkeypatch.setattr(service, "RESEND_CONFIGURED", True)
    monkeypatch.setattr(service, "SMTP_CONFIGURED", True)
    monkeypatch.setattr(service, "_backend", None)

    assert isinstance(service.get_email_backend(), service.ResendEmailBackend)


def test_resend_sender_never_inherits_an_smtp_only_sender():
    from app.email import service

    assert service._resolve_resend_from(None) == service.DEFAULT_RESEND_FROM
    assert service._resolve_resend_from("") == service.DEFAULT_RESEND_FROM
    assert service._resolve_resend_from("BidPilot <mail@verified.example>") == "BidPilot <mail@verified.example>"


def test_invitation_email_uses_configured_app_url(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
    from app.email import service

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

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_email_verification_email("user@example.com", "verify-token")
        service.send_password_reset_email("user@example.com", "reset-token")

    bodies = "\n".join(message.body_text for message in sent)
    assert "https://bidpilot.rglens.com/verify-email?token=verify-token" in bodies
    assert "https://bidpilot.rglens.com/reset-password?token=reset-token" in bodies


def test_email_brand_and_from_header_use_bidpilot(monkeypatch):
    from app.email import service

    monkeypatch.setattr(service, "SMTP_FROM", "2141325767@qq.com")
    monkeypatch.setattr(service, "SMTP_FROM_NAME", "BidPilot")

    from_header, envelope_from = service._get_from_addresses()
    assert from_header == "BidPilot <2141325767@qq.com>"
    assert envelope_from == "2141325767@qq.com"

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_email_verification_email("user@example.com", "verify-token")

    assert sent[0].subject == "BidPilot — Verify Your Email"
    assert "Welcome to BidPilot!" in sent[0].body_text
    assert "DocPilot" not in sent[0].body_text


def test_smtp_backend_requires_a_complete_credential_set():
    from app.email import service

    assert service._smtp_is_configured(
        host="smtp.example.test",
        user="mailer@example.test",
        password="",
        from_address="noreply@example.test",
    ) is False
    assert service._smtp_is_configured(
        host="smtp.example.test",
        user="mailer@example.test",
        password="app-password",
        from_address="noreply@example.test",
    ) is True


def test_best_effort_email_reports_failure_without_raising():
    from app.email import service

    assert service.send_email_best_effort(lambda: None, event="test.success") is True

    def fail() -> None:
        raise RuntimeError("provider unavailable")

    assert service.send_email_best_effort(fail, event="test.failure") is False
