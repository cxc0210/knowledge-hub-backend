import argparse
import asyncio
import json
from uuid import uuid4

from sqlalchemy import select

from core.database import engine, session_factory
from models.user import User
from schemas.ai_action import EmailActionResponse
from services.ai_action import AIActionService


async def run(recipient: str) -> None:
    async with session_factory() as session:
        user_id = await session.scalar(
            select(User.id)
            .where(User.deleted.is_(False))
            .order_by(User.id)
            .limit(1)
        )
        if user_id is None:
            raise RuntimeError("create a user before running the email check")

        action = await AIActionService.create_email_send(
            session,
            user_id=user_id,
            recipients=[recipient],
            subject="Knowledge Hub 本地邮件测试",
            body="这封邮件由 kh_ai_action 确认流程发送到 Mailpit。",
            tool_call_id=f"email-check-{uuid4().hex}",
        )
        action = await AIActionService.approve_email_send(
            session,
            action_id=action.id,
            user_id=user_id,
        )
        print(
            json.dumps(
                EmailActionResponse.from_action(action).model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a test email through the local kh_ai_action workflow.",
    )
    parser.add_argument(
        "--recipient",
        default="mailpit-test@example.com",
    )
    args = parser.parse_args()
    asyncio.run(_run_and_close(args.recipient))


async def _run_and_close(recipient: str) -> None:
    try:
        await run(recipient)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    main()
