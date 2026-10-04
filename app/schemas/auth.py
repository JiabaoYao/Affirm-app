from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import UserRole
from app.schemas.common import ORMModel


class RegisterIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "carol@demo.com", "password": "Password123!", "role": "consumer"}]}
    )

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.consumer


class UserOut(ORMModel):
    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    role: UserRole
