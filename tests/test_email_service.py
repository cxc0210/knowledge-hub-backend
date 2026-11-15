from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from services.email import EmailConfigurationError, EmailService


class EmailServiceTests(IsolatedAsyncioTestCase):
    async def test_sends_plain_text_email_with_configured_smtp(self) -> None:
        send = AsyncMock()

        with patch("services.email.aiosmtplib.send", new=send):
            message_id = await EmailService.send(
                recipients=["user@example.com"],
                subject="测试邮件",
                body="你好",
            )

        await_args = send.await_args
        assert await_args is not None
        message = await_args.args[0]
        self.assertEqual(message["To"], "user@example.com")
        self.assertEqual(message["Subject"], "测试邮件")
        self.assertEqual(message_id, message["Message-ID"])
        self.assertEqual(await_args.kwargs["hostname"], "127.0.0.1")
        self.assertEqual(await_args.kwargs["port"], 1025)

    async def test_rejects_conflicting_tls_settings(self) -> None:
        with (
            patch("services.email.settings.smtp_use_tls", True),
            patch("services.email.settings.smtp_start_tls", True),
            self.assertRaises(EmailConfigurationError),
        ):
            await EmailService.send(
                recipients=["user@example.com"],
                subject="测试邮件",
                body="你好",
            )
