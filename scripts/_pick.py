"""Find a business for the command-line scripts (defaults to the demo business)."""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.config import settings
from app.db import platform, tenant
from app.db.platform import businesses
from app.services import accounts
from app.services.books import Books
from app.services.forecast import Forecaster
from app.services.memory import MemoryService


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--business", type=int, help="business id (default: the demo business)")
    return p


def pick(business_id: int | None) -> dict:
    platform.init()
    if settings.seed_demo:
        accounts.seed_demo()
    with platform.engine.connect() as c:
        q = select(businesses).where(businesses.c.id == business_id) if business_id else \
            select(businesses).where(businesses.c.is_demo.is_(True))
        b = c.execute(q.order_by(businesses.c.id)).mappings().first()
    if not b:
        raise SystemExit("Business not found. Start the backend once so the demo account is created.")
    return dict(b)


def context(b: dict):
    books = Books(tenant.engine_for(b["id"]))
    return books, Forecaster(books), MemoryService(b["bank_id"], b["name"], b["industry"] or "", b["city"] or "")
