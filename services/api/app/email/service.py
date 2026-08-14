"""Transactional email adapter.

Backends are selected in order: Resend HTTP API, SMTP, then a local console
fallback. The same templates are used for registration, password reset and
operational notifications, so delivery configuration lives in one place.
"""

import logging
import json
import os
from collections.abc import Callable
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, parseaddr
from typing import Protocol

from app.core.settings import get_app_url

logger = logging.getLogger(__name__)

# --- Configuration ---

SMTP_HOST = os.environ.get("DOCPILOT_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("DOCPILOT_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("DOCPILOT_SMTP_USER", "")
SMTP_PASS = os.environ.get("DOCPILOT_SMTP_PASS", "")
SMTP_FROM = os.environ.get("DOCPILOT_SMTP_FROM", "")
SMTP_FROM_NAME = os.environ.get("DOCPILOT_SMTP_FROM_NAME", "BidPilot")
SMTP_USE_TLS = os.environ.get("DOCPILOT_SMTP_TLS", "true").lower() == "true"
RESEND_API_KEY = os.environ.get("DOCPILOT_RESEND_API_KEY", "") or os.environ.get("RESEND_API_KEY", "")
DEFAULT_RESEND_FROM = "BidPilot <notifications@updates.rglens.com>"


def _resolve_resend_from(explicit_sender: str | None) -> str:
    """Return only a Resend-specific sender, never an SMTP fallback.

    SMTP credentials are often kept around during a mail-provider migration.
    Reusing their sender for Resend can silently select an unverified domain,
    leaving newly registered users unable to receive a verification link.
    """
    return (explicit_sender or "").strip() or DEFAULT_RESEND_FROM


# A verified Resend sender makes an API-key-only local or production setup
# usable. SMTP's sender is intentionally not a fallback: it may belong to a
# different provider and domain-verification policy.
RESEND_FROM = _resolve_resend_from(os.environ.get("DOCPILOT_RESEND_FROM"))
RESEND_API_URL = os.environ.get("DOCPILOT_RESEND_API_URL", "https://api.resend.com/emails")


def _smtp_is_configured(*, host: str, user: str, password: str, from_address: str) -> bool:
    return bool(host and user and password and from_address)


SMTP_CONFIGURED = _smtp_is_configured(
    host=SMTP_HOST,
    user=SMTP_USER,
    password=SMTP_PASS,
    from_address=SMTP_FROM,
)
RESEND_CONFIGURED = bool(RESEND_API_KEY and RESEND_FROM)
PRODUCT_NAME = "BidPilot"
BRAND_ACCENT = "#8bd84f"


# --- Data types ---

@dataclass
class EmailMessage:
    to: str
    subject: str
    body_text: str
    body_html: str | None = None


# --- Backend protocol ---

class EmailBackend(Protocol):
    def send(self, message: EmailMessage) -> None: ...


# --- Console backend ---

class ConsoleEmailBackend:
    """Prints emails to stdout. Used when SMTP is not configured."""

    def send(self, message: EmailMessage) -> None:
        logger.info("=== EMAIL (console fallback) ===")
        logger.info("To: %s", message.to)
        logger.info("Subject: %s", message.subject)
        logger.info("Body:\n%s", message.body_text)
        if message.body_html:
            logger.info("HTML:\n%s", message.body_html)
        logger.info("=== END EMAIL ===")
        print(f"\n[EMAIL] To: {message.to} | Subject: {message.subject}")
        print(f"[EMAIL] Body:\n{message.body_text}\n")


# --- SMTP backend ---

class SmtpEmailBackend:
    """Sends emails via SMTP. Supports both STARTTLS (port 587) and SSL (port 465)."""

    def send(self, message: EmailMessage) -> None:
        import smtplib

        from_header, envelope_from = _get_from_addresses()
        msg = MIMEMultipart("alternative")
        msg["From"] = from_header
        msg["To"] = message.to
        msg["Subject"] = message.subject

        msg.attach(MIMEText(message.body_text, "plain"))
        if message.body_html:
            msg.attach(MIMEText(message.body_html, "html"))

        use_ssl = SMTP_PORT == 465
        smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_cls(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS and not use_ssl:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(envelope_from, [message.to], msg.as_string())

        logger.info("Email sent to %s: %s", message.to, message.subject)


class ResendEmailBackend:
    """Send transactional email through Resend's HTTPS API without an SDK."""

    def send(self, message: EmailMessage) -> None:
        payload = {
            "from": RESEND_FROM,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body_text,
        }
        if message.body_html:
            payload["html"] = message.body_html

        request = Request(
            RESEND_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
                # Resend's edge layer rejects urllib's default anonymous
                # signature (403/1010), so identify this server explicitly.
                "User-Agent": "BidPilot/1.0 (+https://bidpilot.rglens.com)",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Resend returned HTTP {response.status}")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Resend rejected transactional email ({error.code}): {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Resend request failed: {error.reason}") from error

        logger.info("Transactional email accepted by Resend for %s: %s", message.to, message.subject)


# --- Public API ---

_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        if RESEND_CONFIGURED:
            _backend = ResendEmailBackend()
        elif SMTP_CONFIGURED:
            _backend = SmtpEmailBackend()
        else:
            _backend = ConsoleEmailBackend()
    return _backend


def send_email(message: EmailMessage) -> None:
    """Send an email using the configured backend."""
    get_email_backend().send(message)


def send_email_best_effort(callback: Callable[[], None], *, event: str) -> bool:
    """Run an external delivery without invalidating an already-committed action.

    Transactional email is a notification channel, not business truth. Callers
    persist the token, invitation, or review decision first, then use this
    helper so a provider outage is observable in logs without turning a
    successful user action into a misleading 5xx response.
    """
    try:
        callback()
    except Exception:
        logger.exception("Transactional email delivery failed for %s", event)
        return False
    return True


def is_external_email_delivery_configured() -> bool:
    """Whether an email hand-off can leave this process.

    The console backend is useful in development but must not be presented to
    an end user as a successfully delivered verification email.
    """
    return RESEND_CONFIGURED or SMTP_CONFIGURED


# --- Template helpers ---

def _get_from_addresses() -> tuple[str, str]:
    """Return RFC 5322 From header and SMTP envelope sender separately."""
    parsed_name, parsed_address = parseaddr(SMTP_FROM)
    address = parsed_address or SMTP_FROM
    display_name = SMTP_FROM_NAME or parsed_name
    if display_name:
        return formataddr((str(Header(display_name, "utf-8")), address)), address
    return address, address


def _app_link(path: str, **query: str) -> str:
    base_url = get_app_url().rstrip("/")
    query_string = urlencode(query)
    return f"{base_url}{path}?{query_string}" if query_string else f"{base_url}{path}"


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password reset email with a link containing the token."""
    reset_url = _app_link("/reset-password", token=token)
    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} — Password Reset",
        body_text=(
            f"You requested a password reset for your {PRODUCT_NAME} account.\n\n"
            f"Click the link below to set a new password. This link expires in 30 minutes.\n\n"
            f"{reset_url}\n\n"
            f"If you did not request this, you can safely ignore this email."
        ),
        body_html=(
            f"<h2>Password Reset</h2>"
            f"<p>You requested a password reset for your {PRODUCT_NAME} account.</p>"
            f'<p><a href="{reset_url}" style="display:inline-block;padding:10px 20px;'
            f'background:{BRAND_ACCENT};color:#061006;border-radius:6px;text-decoration:none;font-weight:700;">'
            f"Reset Password</a></p>"
            f"<p>This link expires in 30 minutes.</p>"
            f"<p>If you did not request this, you can safely ignore this email.</p>"
        ),
    ))


def send_email_verification_email(email: str, token: str) -> None:
    """Send an email verification link."""
    verify_url = _app_link("/verify-email", token=token)
    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} — Verify Your Email",
        body_text=(
            f"Welcome to {PRODUCT_NAME}! Please verify your email address by clicking the link below.\n\n"
            f"{verify_url}\n\n"
            f"This link expires in 24 hours."
        ),
        body_html=(
            f"<h2>Verify Your Email</h2>"
            f"<p>Welcome to {PRODUCT_NAME}! Please verify your email address.</p>"
            f'<p><a href="{verify_url}" style="display:inline-block;padding:10px 20px;'
            f'background:{BRAND_ACCENT};color:#061006;border-radius:6px;text-decoration:none;font-weight:700;">'
            f"Verify Email</a></p>"
            f"<p>This link expires in 24 hours.</p>"
        ),
    ))


def send_review_notification_email(email: str, project_name: str, section_title: str, action: str) -> None:
    """Send a review action notification (approved/rejected/needs-revision)."""
    action_label = {
        "approved": "已通过",
        "rejected": "已退回修改",
        "needs_revision": "需要修订",
    }.get(action, action)
    project_name_html = escape(project_name)
    section_title_html = escape(section_title)

    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} - 章节“{section_title}”{action_label}",
        body_text=(
            f"项目“{project_name}”中的章节“{section_title}”{action_label}。\n\n"
            f"查看项目：{_app_link('/projects')}\n"
        ),
        body_html=(
            f"<h2>审核更新</h2>"
            f"<p>项目 <strong>“{project_name_html}”</strong> 中的章节 "
            f"<strong>“{section_title_html}”</strong><strong>{escape(action_label)}</strong>。</p>"
            f'<p><a href="{_app_link("/projects")}" style="display:inline-block;padding:10px 20px;'
            f'background:{BRAND_ACCENT};color:#061006;border-radius:6px;text-decoration:none;font-weight:700;">'
            f"查看项目</a></p>"
        ),
    ))


def send_account_deletion_confirmation_email(email: str) -> None:
    """Send confirmation that account deletion has been processed."""
    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} — Account Deleted",
        body_text=(
            f"Your {PRODUCT_NAME} account and all associated data have been deleted.\n\n"
            f"If you did not request this, please contact support immediately."
        ),
        body_html=(
            f"<h2>Account Deleted</h2>"
            f"<p>Your {PRODUCT_NAME} account and all associated data have been deleted.</p>"
            f"<p>If you did not request this, please contact support immediately.</p>"
        ),
    ))


def send_invitation_email(email: str, token: str, org_slug: str) -> None:
    """Send an invitation email with a registration link including the token."""
    link = _app_link("/register", invitation=token)
    org_slug_html = escape(org_slug)
    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} — You've been invited to join {org_slug}",
        body_text=(
            f"You've been invited to join the '{org_slug}' organization on {PRODUCT_NAME}.\n\n"
            f"To accept, register at: {link}\n\n"
            f"This invitation expires in 7 days."
        ),
        body_html=(
            f"<h2>You've been invited!</h2>"
            f"<p>You've been invited to join the <strong>{org_slug_html}</strong> organization on {PRODUCT_NAME}.</p>"
            f"<p><a href=\"{link}\">Click here to register and join</a></p>"
            f"<p>This invitation expires in 7 days.</p>"
        ),
    ))
