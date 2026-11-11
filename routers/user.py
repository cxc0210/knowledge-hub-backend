from fastapi import APIRouter, HTTPException, status

from database import DatabaseSession
from schemas.user import UserCreate, UserResponse
from services.user import UserAlreadyExistsError, UserService


router = APIRouter(prefix="/users", tags=["users"])


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
