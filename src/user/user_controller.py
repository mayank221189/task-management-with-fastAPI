from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt
from fastapi import BackgroundTasks, HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from src.user.user_dtos import (
    LoginRequestSchema,
    UserAccessUpdateSchema,
    UserBaseSchema,
)
from src.user.user_models import Role, User
from src.utils.mail import send_email
from src.utils.settings import settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password.encode())


def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


async def register_user(
    user: UserBaseSchema, db: Session, background_tasks: BackgroundTasks
) -> User:
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
    member_role = db.query(Role).filter(Role.name == "member").one_or_none()
    if member_role is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default member role is not configured",
        )
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=get_password_hash(user.password),
        first_name=user.first_name,
        last_name=user.last_name,
        created_at=datetime.now(UTC),
        role=member_role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    background_tasks.add_task(send_email, [db_user.email], db_user.first_name)
    return db_user


def user_login(user: LoginRequestSchema, db: Session) -> dict[str, str]:
    is_registered_user = db.query(User).filter(User.username == user.username).first()
    if not is_registered_user or not is_registered_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(user.password, is_registered_user.hashed_password):
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


def list_roles(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def update_user_access(
    user_id: int,
    changes: UserAccessUpdateSchema,
    db: Session,
    administrator: User,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == administrator.id:
        raise HTTPException(
            status_code=400, detail="Administrators cannot change their own access"
        )

    desired_role = user.role
    if "role" in changes.model_fields_set:
        desired_role = db.query(Role).filter(Role.name == changes.role).one_or_none()
        if desired_role is None:
            raise HTTPException(status_code=400, detail="Unknown role")

    if user.direct_reports and desired_role.name != "manager":
        raise HTTPException(
            status_code=409,
            detail="Reassign this user's reports before changing their role",
        )
    if user.role.name == "admin" and desired_role.name != "admin":
        administrator_count = db.query(User).filter(User.role.has(name="admin")).count()
        if administrator_count <= 1:
            raise HTTPException(
                status_code=409, detail="The last administrator cannot be demoted"
            )

    if "manager_id" in changes.model_fields_set:
        manager_id = changes.manager_id
    else:
        manager_id = user.manager_id

    if desired_role.name == "admin":
        if "manager_id" in changes.model_fields_set and manager_id is not None:
            raise HTTPException(
                status_code=400, detail="Administrators cannot be assigned a manager"
            )
        manager_id = None

    if manager_id is not None:
        manager = db.get(User, manager_id)
        if manager is None or not manager.is_active or manager.role.name != "manager":
            raise HTTPException(
                status_code=400,
                detail="manager_id must identify an active manager",
            )
        if manager.id == user.id:
            raise HTTPException(
                status_code=400, detail="A user cannot be their own manager"
            )

        visited_manager_ids: set[int] = set()
        current_manager: User | None = manager
        while current_manager is not None:
            if current_manager.id == user.id:
                raise HTTPException(
                    status_code=400, detail="Manager assignment would create a cycle"
                )
            if current_manager.id in visited_manager_ids:
                raise HTTPException(
                    status_code=409,
                    detail="Existing manager hierarchy contains a cycle",
                )
            visited_manager_ids.add(current_manager.id)
            current_manager = current_manager.manager

    user.role = desired_role
    user.manager_id = manager_id
    db.commit()
    db.refresh(user)
    return user
