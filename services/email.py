from email.message import EmailMessage
from email.utils import make_msgid

import aiosmtplib

from core.config import settings


class EmailConfigurationError(RuntimeError):
    pass


class EmailService:
    @staticmethod
    async def send(
        *,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> str:
        if settings.smtp_use_tls and settings.smtp_start_tls:
            raise EmailConfigurationError(
                "SMTP_USE_TLS and SMTP_START_TLS cannot both be enabled",
            )

        message_id = make_msgid()
        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message["Message-ID"] = message_id
        message.set_content(body)

        username = settings.smtp_username.strip() or None
        password = settings.smtp_password.get_secret_value().strip() or None
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=username,
            password=password,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_start_tls,
            timeout=settings.smtp_timeout_seconds,
        )
        return message_id
