from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from src.user import user_controller
from src.user.user_dtos import (
    LoginRequestSchema,
    RoleResponseSchema,
    UserAccessUpdateSchema,
    UserBaseSchema,
    UserResponseSchema,
)
from src.user.user_models import User
from src.utils.db import get_db
from src.utils.helpers import is_authenticated, require_roles

user_router = APIRouter(prefix="/user")
DbSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(is_authenticated)]
Administrator = Annotated[User, Depends(require_roles("admin"))]


@user_router.post(
    "/register",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def user_register(
    user: UserBaseSchema, db: DbSession, background_tasks: BackgroundTasks
):
    return await user_controller.register_user(user, db, background_tasks)


@user_router.post("/login", status_code=status.HTTP_200_OK)
def login(user: LoginRequestSchema, db: DbSession):
    return user_controller.user_login(user, db)


@user_router.get(
    "/is-auth",
    response_model=UserResponseSchema,
    status_code=status.HTTP_200_OK,
)
def get_authenticated_user(user: AuthenticatedUser):
    return user


@user_router.get(
    "/roles",
    response_model=list[RoleResponseSchema],
    status_code=status.HTTP_200_OK,
)
def list_roles(db: DbSession, _: Administrator):
    return user_controller.list_roles(db)


@user_router.get(
    "/users",
    response_model=list[UserResponseSchema],
    status_code=status.HTTP_200_OK,
)
def list_users(db: DbSession, _: Administrator):
    return user_controller.list_users(db)


@user_router.patch(
    "/users/{user_id}/access",
    response_model=UserResponseSchema,
    status_code=status.HTTP_200_OK,
)
def update_user_access(
    user_id: int,
    changes: UserAccessUpdateSchema,
    db: DbSession,
    administrator: Administrator,
):
    return user_controller.update_user_access(user_id, changes, db, administrator)
