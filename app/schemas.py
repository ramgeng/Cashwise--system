"""Request bodies. Field limits here are the first line of input checking."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    business_name: str = Field(min_length=1, max_length=160)
    city: str = Field(default="", max_length=120)
    industry: str = Field(default="", max_length=160)
    with_demo_data: bool = False


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class BusinessIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    city: str = Field(default="", max_length=120)
    owner_name: str = Field(default="", max_length=120)
    industry: str = Field(default="", max_length=160)
    with_demo_data: bool = False


class BusinessUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=160)
    opening_cash_balance: int | None = Field(default=None, ge=-10**12, le=10**12)
    opening_date: date | None = None
    low_cash_threshold: int | None = Field(default=None, ge=0, le=10**12)
    bank_balance: int | None = Field(default=None, ge=-10**12, le=10**12)
    bank_balance_date: date | None = None
    clear_bank_balance: bool = False
    clear_low_cash_threshold: bool = False
    as_of_date: date | None = None
    clear_as_of_date: bool = False


class ScenarioIn(BaseModel):
    changes: list[dict] = Field(default_factory=list, max_length=20)
    horizon_days: int = Field(default=28, ge=1, le=180)
    target_date: date | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    memory: bool = True


class FeedbackIn(BaseModel):
    text: str = Field(default="", max_length=1000)
    helpful: bool | None = None
    question: str | None = Field(default=None, max_length=1000)


class OutcomeIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ReportIn(BaseModel):
    kind: str = Field(default="summary", pattern="^(summary|comparison)$")
    a_from: date | None = None
    a_to: date | None = None
    b_from: date | None = None
    b_to: date | None = None
    title: str | None = Field(default=None, max_length=200)


class EmailIn(BaseModel):
    to: list[str] = Field(default_factory=list, max_length=20)
    use_management: bool = False
    note: str = Field(default="", max_length=1000)
    mode: str = Field(default="send", pattern="^(send|draft)$")
    link_days: int | None = Field(default=30, ge=1, le=365)


class ShareIn(BaseModel):
    days: int | None = Field(default=30, ge=1, le=365)    # None = never expires


class RecipientsIn(BaseModel):
    emails: list[str] = Field(default_factory=list, max_length=20)


class ScheduleIn(BaseModel):
    frequency: str = Field(pattern="^(weekly|monthly)$")
    weekday: int = Field(default=0, ge=0, le=6)
    day_of_month: int = Field(default=1, ge=1, le=28)
    hour: int = Field(default=9, ge=0, le=23)
    kind: str = Field(default="summary", pattern="^(summary|comparison)$")
    recipients: list[str] = Field(default_factory=list, max_length=20)
    active: bool = True
