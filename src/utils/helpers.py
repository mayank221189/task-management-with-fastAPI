from datetime import UTC, datetime
from typing import Any, cast

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.user.user_models import User
from src.utils.db import get_db
from src.utils.settings import settings

dbSession = Depends(get_db)


def is_authenticated(request: Request, db: Session = dbSession) -> User:
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
