import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RegisterInput(LoginInput):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str


class OrganizationInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Organization name cannot be blank")
        return value.strip()


class OrganizationOutput(BaseModel):
    id: uuid.UUID
    name: str
    role: Literal["admin", "member"]


class RoleInput(BaseModel):
    role: Literal["admin", "member"]


class MemberInput(RoleInput):
    email: EmailStr


class MemberOutput(BaseModel):
    user_id: uuid.UUID
    email: str
    name: str
    role: Literal["admin", "member"]
