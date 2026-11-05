"""The shared database: who can sign in and which businesses they can open.

Each business's financial records live in their own database (see tenant.py),
and each business has its own Hindsight memory bank (bank_id).
"""
from __future__ import annotations

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table,
                        UniqueConstraint, create_engine, func)

from app.core.config import settings

engine = create_engine(settings.platform_db_url, future=True)
metadata = MetaData()

users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(200), nullable=False, unique=True, index=True),
    Column("name", String(120), nullable=False),
    Column("password_hash", String(300), nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
)

businesses = Table(
    "businesses", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(160), nullable=False),
    Column("city", String(120), default=""),
    Column("owner_name", String(120), default=""),
    Column("industry", String(160), default=""),
    Column("bank_id", String(120), nullable=False, unique=True),   # Hindsight memory bank
    Column("is_demo", Boolean, default=False),
    Column("created_at", DateTime, server_default=func.now()),
)

memberships = Table(
    "memberships", metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("business_id", Integer, ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(20), nullable=False, default="owner"),
    UniqueConstraint("user_id", "business_id"),
)


oauth_identities = Table(   # "this Google / GitHub / Apple account belongs to this user"
    "oauth_identities", metadata,
    Column("provider", String(20), primary_key=True),
    Column("subject", String(200), primary_key=True),      # the provider's id for the account
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("email", String(200)),
    Column("created_at", DateTime, server_default=func.now()),
)


def init() -> None:
    metadata.create_all(engine)
