"""Reusable SMTP email delivery for VEXTRO notifications.

All connection details come from :mod:`app.core.config`. No credential,
sender address or host is ever hard-coded here, and nothing in this module
logs a password.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import Settings, settings as default_settings


logger = logging.getLogger(__name__)


class EmailNotConfiguredError(Exception):
    """Raised when SMTP settings are incomplete for delivery."""


class EmailDeliveryError(Exception):
    """Raised when an SMTP delivery attempt fails."""

    def __init__(
        self,
        message: str,
        *,
        is_permanent: bool = False,
    ) -> None:
        super().__init__(message)

        self.is_permanent = is_permanent


@dataclass(frozen=True)
class EmailAttachment:
    """One binary attachment carried by an outbound email."""

    filename: str
    content: bytes
    media_type: str


@dataclass(frozen=True)
class EmailContent:
    """A rendered email ready for delivery."""

    subject: str
    html_body: str
    text_body: str
    attachments: tuple[EmailAttachment, ...] = field(
        default=(),
    )


def _build_message(
    *,
    recipient: str,
    content: EmailContent,
    settings: Settings,
) -> EmailMessage:
    """Assemble a multipart alternative message with a text fallback."""

    sender_address = settings.email_sender_address

    if sender_address is None:
        raise EmailNotConfiguredError(
            "No SMTP sender address is configured."
        )

    message = EmailMessage()
    message["Subject"] = content.subject
    message["From"] = formataddr(
        (
            settings.smtp_from_name,
            sender_address,
        )
    )
    message["To"] = recipient

    message.set_content(content.text_body)
    message.add_alternative(
        content.html_body,
        subtype="html",
    )

    for attachment in content.attachments:
        maintype, _, subtype = attachment.media_type.partition("/")

        message.add_attachment(
            attachment.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
        )

    return message


def _open_connection(
    settings: Settings,
) -> smtplib.SMTP | smtplib.SMTP_SSL:
    """Open an authenticated SMTP connection using configured settings."""

    if settings.smtp_host is None:
        raise EmailNotConfiguredError(
            "No SMTP host is configured."
        )

    if settings.smtp_use_ssl:
        connection: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=ssl.create_default_context(),
        )
    else:
        connection = smtplib.SMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )

        if settings.smtp_use_tls:
            connection.starttls(
                context=ssl.create_default_context(),
            )

    if settings.smtp_username and settings.smtp_password:
        connection.login(
            settings.smtp_username,
            settings.smtp_password,
        )

    return connection


def send_email(
    *,
    recipient: str,
    content: EmailContent,
    settings: Settings | None = None,
) -> None:
    """Deliver one email, raising on configuration or transport failure."""

    active_settings = settings or default_settings

    if not active_settings.is_email_configured:
        raise EmailNotConfiguredError(
            "SMTP delivery is not configured."
        )

    normalized_recipient = (recipient or "").strip()

    if not normalized_recipient:
        raise EmailNotConfiguredError(
            "The recipient has no email address."
        )

    message = _build_message(
        recipient=normalized_recipient,
        content=content,
        settings=active_settings,
    )

    try:
        connection = _open_connection(active_settings)

        try:
            connection.send_message(message)
        finally:
            try:
                connection.quit()
            except smtplib.SMTPException:
                connection.close()

    except smtplib.SMTPRecipientsRefused as error:
        raise EmailDeliveryError(
            "The SMTP server refused the recipient address.",
            is_permanent=True,
        ) from error

    except smtplib.SMTPSenderRefused as error:
        raise EmailDeliveryError(
            "The SMTP server refused the sender address.",
            is_permanent=True,
        ) from error

    except smtplib.SMTPAuthenticationError as error:
        raise EmailDeliveryError(
            "SMTP authentication was rejected.",
            is_permanent=True,
        ) from error

    except (smtplib.SMTPException, OSError, ssl.SSLError) as error:
        raise EmailDeliveryError(
            f"SMTP delivery failed: {type(error).__name__}",
        ) from error

    logger.info(
        "email.delivery.successful subject=%r recipient_domain=%s",
        content.subject,
        normalized_recipient.rpartition("@")[2],
    )
