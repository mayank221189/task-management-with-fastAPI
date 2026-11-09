from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.user import user_controller
from src.user.user_dtos import (
    LoginRequestSchema,
    UserBaseSchema,
    UserResponseSchema,
)
from src.utils.db import get_db

user_router = APIRouter(prefix="/user")
DbSession = Annotated[Session, Depends(get_db)]


@user_router.post(
    "/register",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def user_register(user: UserBaseSchema, db: DbSession):
    return user_controller.register_user(user, db)


@user_router.post("/login", status_code=status.HTTP_200_OK)
def login(user: LoginRequestSchema, db: DbSession):
    return user_controller.user_login(user, db)


@user_router.get(
    "/is-auth",
    response_model=UserResponseSchema,
    status_code=status.HTTP_200_OK,
)
def is_authenticated(request: Request, db: DbSession):
    return user_controller.is_authenticated(request, db)
