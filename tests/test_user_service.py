from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from services.user import UserService


class UserServiceTests(IsolatedAsyncioTestCase):
    async def test_lists_active_users_by_id_with_page_and_size(self) -> None:
        session = AsyncMock(spec=AsyncSession)
        users = [MagicMock(id=11), MagicMock(id=12)]
        scalar_result = MagicMock()
        scalar_result.all.return_value = users
        session.scalar.return_value = 12
        session.scalars.return_value = scalar_result

        result, total = await UserService.list(session, page=2, size=10)

        self.assertEqual(result, users)
        self.assertEqual(total, 12)

        count_statement = session.scalar.await_args.args[0]
        users_statement = session.scalars.await_args.args[0]
        count_sql = " ".join(str(count_statement).split())
        users_sql = " ".join(str(users_statement).split())

        self.assertIn("count(kh_user.id)", count_sql)
        self.assertIn("kh_user.deleted IS false", count_sql)
        self.assertIn("kh_user.deleted IS false", users_sql)
        self.assertIn("ORDER BY kh_user.id ASC", users_sql)
        self.assertIn("LIMIT :param_1 OFFSET :param_2", users_sql)
