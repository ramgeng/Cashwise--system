"""The audit trail: who changed what, and when. Written for important financial changes and every report action."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.db import tenant

CATEGORIES = ("report", "sharing", "money", "data", "settings")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def actor(user: dict | None) -> str:
    if not user:
        return "Cashwise"
    return f"{user.get('name') or user.get('email')} ({user.get('email')})" if user.get("email") else user.get("name", "Someone")


def log(eng: Engine, who: str, action: str, category: str, detail: str = "") -> None:
    try:
        with eng.begin() as c:
            c.execute(tenant.audit_log.insert().values(at=now(), actor=who[:160], action=action[:60],
                                                       category=category, detail=detail[:2000]))
    except Exception:   # the trail must never break the thing being done
        pass


def entries(eng: Engine, category: str | None = None, limit: int = 200) -> list[dict]:
    t = tenant.audit_log
    q = select(t).order_by(t.c.at.desc(), t.c.entry_id.desc()).limit(limit)
    if category:
        q = q.where(t.c.category == category)
    with eng.connect() as c:
        rows = c.execute(q).mappings().all()
    return [{**dict(r), "at": r["at"].isoformat() + "Z"} for r in rows]
