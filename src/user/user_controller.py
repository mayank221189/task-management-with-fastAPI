from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from src.user.user_dtos import LoginRequestSchema, UserBaseSchema
from src.user.user_models import User
from src.utils.mail import send_email
from src.utils.settings import settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password.encode())


def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


async def register_user(user: UserBaseSchema, db: Session) -> dict[str, str]:
    existing_user_with_email = db.query(User).filter(User.email == user.email).first()
    if existing_user_with_email:
        raise HTTPException(
            status_code=400, detail="User with this email already exists"
        )
    existing_user_with_username = (
        db.query(User).filter(User.username == user.username).first()
    )
    if existing_user_with_username:
        raise HTTPException(
            status_code=400, detail="User with this username already exists"
        )
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=get_password_hash(user.password),
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=datetime.now(UTC),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    await send_email([cast(str, db_user.email)])
    return db_user


def user_login(user: LoginRequestSchema, db: Session) -> dict[str, str]:
    is_registered_user = db.query(User).filter(User.username == user.username).first()
    if not is_registered_user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(
        user.password, cast(str, is_registered_user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = cast(Any, jwt).encode(
        {
            "_id": is_registered_user.id,
            "username": is_registered_user.username,
            "exp": (
                datetime.now(UTC)
                + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            ).timestamp(),
        },
        settings.SECRET_KEY,
        settings.ALGORITHM,
    )
    return {"token": token}


def is_authenticated(request: Request, db: Session) -> User:
    authorization_token = request.headers.get("Authorization")
    if not authorization_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )
    token = authorization_token.split(" ")[-1]
    current_timestamp = datetime.now(UTC).timestamp()
    try:
        payload = cast(Any, jwt).decode(token, settings.SECRET_KEY, settings.ALGORITHM)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if payload.get("exp", 0) < current_timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    user = db.query(User).filter(User.id == payload.get("_id")).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
