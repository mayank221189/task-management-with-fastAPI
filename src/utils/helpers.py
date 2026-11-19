from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.user.user_models import User
from src.utils.db import get_db
from src.utils.settings import settings

jwt_authorization_header = APIKeyHeader(
    name="Authorization", scheme_name="JWTAuth", auto_error=False
)


def is_authenticated(
    authorization_token: Annotated[str | None, Security(jwt_authorization_header)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not authorization_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing",
        )

    scheme, separator, token = authorization_token.partition(" ")
    if scheme.upper() != "JWT" or not separator or not token or " " in token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use the JWT scheme",
        )

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


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    def role_dependency(
        user: Annotated[User, Depends(is_authenticated)],
    ) -> User:
        if user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return role_dependency
