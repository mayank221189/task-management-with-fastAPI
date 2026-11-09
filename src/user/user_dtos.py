from datetime import datetime

from pydantic import BaseModel


class UserBaseSchema(BaseModel):
    first_name: str
    last_name: str
    username: str
    password: str
    email: str


class UserResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    email: str
    is_active: bool
    created_at: datetime


class LoginRequestSchema(BaseModel):
    username: str
    password: str
