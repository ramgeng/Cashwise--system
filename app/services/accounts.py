"""Users, businesses and who can open which business."""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func, select

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.db import platform, tenant
from app.db.platform import businesses, memberships, users

log = logging.getLogger("cashwise.accounts")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL.match(e):
        raise AppError(422, "Enter a valid email address.", "invalid_email")
    return e


def public_user(u) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u["name"]}


def public_business(b, role: str | None = None) -> dict:
    out = {"id": b["id"], "name": b["name"], "city": b["city"] or "", "owner_name": b["owner_name"] or "",
           "industry": b["industry"] or "", "is_demo": bool(b["is_demo"])}
    if role:
        out["role"] = role
    return out


def create_user(email: str, name: str, password: str) -> dict:
    email = _clean_email(email)
    if len(password or "") < 8:
        raise AppError(422, "Use a password with at least 8 characters.", "weak_password")
    if not (name or "").strip():
        raise AppError(422, "Enter your name.", "missing_name")
    with platform.engine.begin() as c:
        if c.execute(select(users.c.id).where(users.c.email == email)).first():
            raise AppError(409, "An account with this email already exists. Sign in instead.", "email_taken")
        uid = c.execute(users.insert().values(email=email, name=name.strip(), password_hash=hash_password(password))
                        ).inserted_primary_key[0]
    return get_user(uid)


def authenticate(email: str, password: str) -> dict:
    with platform.engine.connect() as c:
        u = c.execute(select(users).where(users.c.email == (email or "").strip().lower())).mappings().first()
    if not u or not verify_password(password or "", u["password_hash"]):
        raise AppError(401, "That email and password don't match.", "bad_credentials")
    return public_user(u)


def get_user(user_id: int) -> dict | None:
    with platform.engine.connect() as c:
        u = c.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return public_user(u) if u else None


def create_business(user_id: int, name: str, city: str = "", owner_name: str = "", industry: str = "",
                    bank_id: str | None = None, is_demo: bool = False) -> dict:
    if not (name or "").strip():
        raise AppError(422, "Enter the business name.", "missing_business_name")
    with platform.engine.begin() as c:
        bid = c.execute(businesses.insert().values(
            name=name.strip(), city=(city or "").strip(), owner_name=(owner_name or "").strip(),
            industry=(industry or "").strip(), bank_id=bank_id or f"cashwise-{uuid.uuid4().hex[:12]}",
            is_demo=is_demo)).inserted_primary_key[0]
        c.execute(memberships.insert().values(user_id=user_id, business_id=bid, role="owner"))
    tenant.engine_for(bid)  # creates the business's own database
    return get_business(bid)


def get_business(business_id: int) -> dict | None:
    with platform.engine.connect() as c:
        b = c.execute(select(businesses).where(businesses.c.id == business_id)).mappings().first()
    return dict(b) if b else None


def update_business(business_id: int, **fields) -> dict:
    allowed = {k: (v or "").strip() for k, v in fields.items() if k in ("name", "city", "owner_name", "industry") and v is not None}
    if "name" in allowed and not allowed["name"]:
        raise AppError(422, "The business name can't be empty.", "missing_business_name")
    if allowed:
        with platform.engine.begin() as c:
            c.execute(businesses.update().where(businesses.c.id == business_id).values(**allowed))
    return get_business(business_id)


def list_businesses(user_id: int) -> list[dict]:
    with platform.engine.connect() as c:
        rows = c.execute(select(businesses, memberships.c.role)
                         .join(memberships, memberships.c.business_id == businesses.c.id)
                         .where(memberships.c.user_id == user_id).order_by(businesses.c.id)).mappings().all()
    return [public_business(r, r["role"]) for r in rows]


def role_in(user_id: int, business_id: int) -> str | None:
    with platform.engine.connect() as c:
        return c.execute(select(memberships.c.role).where(memberships.c.user_id == user_id,
                                                           memberships.c.business_id == business_id)).scalar()


def delete_business(business_id: int) -> None:
    with platform.engine.begin() as c:
        c.execute(memberships.delete().where(memberships.c.business_id == business_id))
        c.execute(businesses.delete().where(businesses.c.id == business_id))
    tenant.drop(business_id)


def seed_demo() -> None:
    """First start only: a demo account with the Malabar Electronics demo business loaded."""
    from app.services import demo
    with platform.engine.connect() as c:
        if c.execute(select(func.count()).select_from(users)).scalar():
            return
    try:
        meta = demo.meta()
    except AppError as e:
        log.warning("Demo account not created: %s", e.detail)
        return
    user = create_user(settings.demo_email, meta["owner_name"] or "Demo owner", settings.demo_password)
    biz = create_business(user["id"], meta["name"], meta["city"], meta["owner_name"], meta["industry"],
                          bank_id=settings.demo_bank_id, is_demo=True)
    demo.load(tenant.engine_for(biz["id"]))
    log.info("Demo account ready: %s / %s", settings.demo_email, settings.demo_password)
