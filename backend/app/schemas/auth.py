from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.core.security import validate_password_strength

class UserRegister(BaseModel):
    """Data required to register a Consumer or SME account."""

    full_name: str = Field(
        min_length=2,
        max_length=120,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    account_type: Literal["consumer", "sme"] = "consumer"

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned_name = " ".join(value.split())

        if len(cleaned_name) < 2:
            raise ValueError("Full name must contain at least 2 characters.")

        return cleaned_name
@field_validator("password")
@classmethod
def validate_password(cls, value: str) -> str:
    return validate_password_strength(value)


class UserResponse(BaseModel):
    """Safe user information returned by the API."""

    id: int
    full_name: str
    email: EmailStr
    roles: list[str]
    is_active: bool
    is_verified: bool
    created_at: datetime

class UserLogin(BaseModel):
    """Credentials required to authenticate a user."""

    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=128,
    )


class TokenResponse(BaseModel):
    """Authentication response containing an access token."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse