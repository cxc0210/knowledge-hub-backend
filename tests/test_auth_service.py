from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.auth import LoginRequest
from services.auth import AuthService


class AuthServiceTests(IsolatedAsyncioTestCase):
    async def test_refreshes_updated_at_after_login_commit(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        user = MagicMock()
        user.password_hash = "stored-password-hash"
        user.status = 1
        session.scalar.return_value = user
        login_request = LoginRequest(
            username_or_email="andre",
            password=SecretStr("correct-password"),
        )

        with patch("services.auth.verify_password", return_value=True):
            authenticated_user = await AuthService.authenticate(
                session,
                login_request,
            )

        self.assertIs(authenticated_user, user)
        session.commit.assert_awaited_once_with()
        session.refresh.assert_awaited_once_with(
            user,
            attribute_names=["updated_at"],
        )
