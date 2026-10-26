from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import MerchantStatus, UserRole
from app.schemas.common import ORMModel


class RegisterIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [
            {"email": "carol@demo.com", "password": "Password123!", "full_name": "Carol Diaz", "role": "consumer"},
            {"email": "store@demo.com", "password": "Password123!", "full_name": "Sam Lee", "role": "merchant",
             "business_name": "Sam's Bikes"},
        ]}
    )

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=100)
    # Admin accounts are internal: they can't be self-registered.
    role: Literal["consumer", "merchant"] = "consumer"
    business_name: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def merchant_needs_business(self) -> "RegisterIn":
        if self.role == "merchant" and not self.business_name:
            raise ValueError("business_name is required for merchant accounts")
        return self


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    merchant_status: MerchantStatus | None = Field(description="Merchant accounts only: pending, active or suspended")
    business_name: str | None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
    role: UserRole
