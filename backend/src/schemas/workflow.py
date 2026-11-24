from typing import Any

from pydantic import BaseModel, Field


class LoginForm(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class CaseForm(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any]


class ReviewForm(BaseModel):
    note: str = Field(min_length=1, max_length=500)


class RenumberForm(BaseModel):
    base_version: int = Field(ge=1)
    items: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class SlipForm(BaseModel):
    range_start: int = Field(ge=1, le=999_999_999)
    range_end: int = Field(ge=1, le=999_999_999)
