"""Email over SMTP (stdlib ``smtplib`` in a worker thread, with a timeout): an HTML part and a
plain-text alternative. Only the account email is used (no address verification in Y15)."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from app.core.config import get_settings
from app.notifications.channels import PermanentError, TransientError


def enabled() -> bool:
    return bool(get_settings().smtp_host)


def sender() -> str:
    settings = get_settings()
    return settings.smtp_from or settings.smtp_user or "notifications@localhost"


def build(to: str, subject: str, text: str, html: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender()
    message["To"] = to
    message["Subject"] = subject
    domain = sender().rsplit("@", 1)[-1] or "localhost"
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


def _send_sync(message: EmailMessage) -> str:
    settings = get_settings()
    timeout = settings.notification_timeout_seconds
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            refused = smtp.send_message(message)
    except smtplib.SMTPRecipientsRefused as exc:
        codes = sorted({code for code, _ in exc.recipients.values()})
        raise PermanentError(f"smtp: recipient refused {codes}") from None
    except smtplib.SMTPResponseException as exc:
        text = f"smtp {exc.smtp_code}"
        if exc.smtp_code >= 500 and not isinstance(exc, smtplib.SMTPAuthenticationError):
            raise PermanentError(text) from None
        raise TransientError(text) from None  # 4xx, or a credentials problem (breaker)
    except (TimeoutError, OSError, smtplib.SMTPException) as exc:
        raise TransientError(f"smtp: {type(exc).__name__}") from None
    if refused:
        raise PermanentError("smtp: recipient refused")
    return str(message["Message-ID"])


async def send(to: str, subject: str, text: str, html: str) -> str:
    """The Message-ID, or a channel error."""
    return await asyncio.to_thread(_send_sync, build(to, subject, text, html))
