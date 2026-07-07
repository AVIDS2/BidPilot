"""Email sending adapter.

Supports two backends:
- SMTP: configured via DOCPILOT_SMTP_* environment variables.
- Console: prints email content to stdout (default when SMTP is not configured).

All email functions accept the same parameters regardless of backend.
"""

import os
import logging
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
SMTP_FROM = os.environ.get("DOCPILOT_SMTP_FROM", "noreply@docpilot.local")
SMTP_FROM_NAME = os.environ.get("DOCPILOT_SMTP_FROM_NAME", "BidPilot")
SMTP_USE_TLS = os.environ.get("DOCPILOT_SMTP_TLS", "true").lower() == "true"

SMTP_CONFIGURED = bool(SMTP_HOST and SMTP_USER)
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


# --- Public API ---

_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        _backend = SmtpEmailBackend() if SMTP_CONFIGURED else ConsoleEmailBackend()
    return _backend


def send_email(message: EmailMessage) -> None:
    """Send an email using the configured backend."""
    get_email_backend().send(message)


# --- Template helpers ---

def _get_from_addresses() -> tuple[str, str]:
    """Return RFC 5322 From header and SMTP envelope sender separately."""
    parsed_name, parsed_address = parseaddr(SMTP_FROM)
    address = parsed_address or SMTP_FROM
    display_name = SMTP_FROM_NAME or parsed_name
    if display_name:
        return formataddr((str(Header(display_name, "utf-8")), address)), address
    return address, address


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password reset email with a link containing the token."""
    reset_url = f"{get_app_url()}/reset-password?token={token}"
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
    verify_url = f"{get_app_url()}/verify-email?token={token}"
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
        "approved": "approved",
        "rejected": "rejected",
        "needs_revision": "marked for revision",
    }.get(action, action)

    send_email(EmailMessage(
        to=email,
        subject=f"{PRODUCT_NAME} — Section \"{section_title}\" {action_label}",
        body_text=(
            f"Section \"{section_title}\" in project \"{project_name}\" has been {action_label}.\n\n"
            f"View the project at {get_app_url()}/projects\n"
        ),
        body_html=(
            f"<h2>Review Update</h2>"
            f"<p>Section <strong>\"{section_title}\"</strong> in project "
            f"<strong>\"{project_name}\"</strong> has been <strong>{action_label}</strong>.</p>"
            f'<p><a href="{get_app_url()}/projects" style="display:inline-block;padding:10px 20px;'
            f'background:{BRAND_ACCENT};color:#061006;border-radius:6px;text-decoration:none;font-weight:700;">'
            f"View Project</a></p>"
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
    link = f"{get_app_url()}/register?invitation={token}"
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
            f"<p>You've been invited to join the <strong>{org_slug}</strong> organization on {PRODUCT_NAME}.</p>"
            f"<p><a href=\"{link}\">Click here to register and join</a></p>"
            f"<p>This invitation expires in 7 days.</p>"
        ),
    ))
