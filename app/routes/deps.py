"""Who is calling, and which business they are working in.

Every business route needs:  Authorization: Bearer <token>   and   X-Business-Id: <id>
(X-Business-Id may be left out when the user has exactly one business).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.core.security import decode_token
from app.db import tenant
from app.services import accounts
from app.services.books import Books
from app.services.forecast import Forecaster
from app.services.memory import MemoryService

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise AppError(401, "Sign in to continue.", "not_signed_in")
    uid = decode_token(creds.credentials)
    user = accounts.get_user(uid) if uid else None
    if not user:
        raise AppError(401, "Your session has ended. Sign in again.", "session_expired")
    return user


@dataclass
class BusinessContext:
    user: dict
    business: dict
    role: str

    @property
    def id(self) -> int:
        return self.business["id"]

    @cached_property
    def books(self) -> Books:
        return Books(tenant.engine_for(self.id))

    @cached_property
    def forecaster(self) -> Forecaster:
        return Forecaster(self.books)

    @cached_property
    def memory(self) -> MemoryService:
        b = self.business
        return MemoryService(b["bank_id"], b["name"], b.get("industry") or "", b.get("city") or "")


def current_business(user: dict = Depends(current_user),
                     x_business_id: str | None = Header(default=None)) -> BusinessContext:
    if x_business_id:
        try:
            bid = int(x_business_id)
        except ValueError:
            raise AppError(400, "X-Business-Id must be a number.", "bad_business_id")
    else:
        mine = accounts.list_businesses(user["id"])
        if len(mine) != 1:
            raise AppError(400, "Choose a business first (send X-Business-Id).", "business_required")
        bid = mine[0]["id"]
    role = accounts.role_in(user["id"], bid)
    biz = accounts.get_business(bid) if role else None
    if not biz:   # same answer whether it doesn't exist or isn't yours
        raise AppError(404, "Business not found.", "business_not_found")
    return BusinessContext(user, biz, role)
