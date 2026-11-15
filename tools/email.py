import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from pydantic import EmailStr, Field

from core.database import session_factory
from enums.permission import PermissionCode
from graphs.context import AgentContext
from schemas.ai_action import EmailActionResponse
from services.ai_action import AIActionService


@tool("request_email_send")
async def request_email_send(
    recipients: Annotated[
        list[EmailStr],
        Field(min_length=1, max_length=10, description="收件人邮箱地址"),
    ],
    subject: Annotated[
        str,
        Field(min_length=1, max_length=200, description="邮件标题"),
    ],
    body: Annotated[
        str,
        Field(min_length=1, max_length=20_000, description="纯文本邮件正文"),
    ],
    runtime: ToolRuntime[AgentContext],
) -> str:
    """创建一封待用户确认的邮件；此工具不会立即发送邮件。"""
    if PermissionCode.AI_EMAIL_SEND.value not in runtime.context.permission_codes:
        return json.dumps(
            {
                "status": "permission_denied",
                "message": "当前用户没有发送邮件的权限",
            },
            ensure_ascii=False,
        )

    async with session_factory() as session:
        action = await AIActionService.create_email_send(
            session,
            user_id=runtime.context.user_id,
            recipients=[str(recipient) for recipient in recipients],
            subject=subject,
            body=body,
            tool_call_id=runtime.tool_call_id,
        )

    response = EmailActionResponse.from_action(action)
    response_data = response.model_dump(mode="json")
    runtime.stream_writer(
        {
            "type": "email-approval",
            "data": response_data,
        }
    )
    return json.dumps(
        {
            "status": "pending_approval",
            "action_id": str(response.id),
            "recipients": response.recipients,
            "subject": response.subject,
            "message": "邮件已生成，等待用户确认后发送",
        },
        ensure_ascii=False,
    )
