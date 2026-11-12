from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.database import DatabaseSession
from dependencies.permission import require_permission
from enums.permission import PermissionCode
from models.user import User
from schemas.user import UserCreate, UserListResponse, UserResponse
from services.user import UserAlreadyExistsError, UserService

router = APIRouter(prefix="/users", tags=["users"])
UserManager = Annotated[
    User,
    Depends(require_permission(PermissionCode.USER_MANAGE)),
]


@router.get("", response_model=UserListResponse)
async def list_users(
    session: DatabaseSession,
    current_user: UserManager,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> UserListResponse:
    users, total = await UserService.list(session, page, size)

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate,
    session: DatabaseSession,
) -> UserResponse:
    try:
        user = await UserService.create(session, user_create)
    except UserAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return UserResponse.model_validate(user)
