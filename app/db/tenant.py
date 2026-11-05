"""One database per business: its customers, invoices, bills, cash ledger and memory events.

Keeping each business in its own database means one business can never see another's
records, even through a bug in a query. With SQLite each business is a file in
storage/businesses/; set TENANT_DB_URL to use another database server.
"""
from __future__ import annotations

from threading import Lock

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, MetaData, String, Table, Text,
                        create_engine)
from sqlalchemy.engine import Engine

from app.core.config import settings

metadata = MetaData()

business_profile = Table(
    "business_profile", metadata,
    Column("field", String(50), primary_key=True),
    Column("value", String(200)),
)

customers = Table(
    "customers", metadata,
    Column("customer_id", String(30), primary_key=True),
    Column("name", String(160), nullable=False),
    Column("city", String(80)),
    Column("contact_person", String(120)),
    Column("payment_terms_days", Integer, nullable=False),
)

suppliers = Table(
    "suppliers", metadata,
    Column("supplier_id", String(30), primary_key=True),
    Column("name", String(160), nullable=False),
    Column("category", String(120)),
    Column("payment_terms_days", Integer, nullable=False),
    Column("early_payment_discount_pct", Float, default=0),
    Column("discount_window_days", Integer, default=0),
    Column("late_fee_pct_per_month", Float, default=0),
)

invoices = Table(
    "invoices", metadata,
    Column("invoice_id", String(40), primary_key=True),
    Column("customer_id", String(30), ForeignKey("customers.customer_id"), nullable=False, index=True),
    Column("issue_date", Date, nullable=False),
    Column("due_date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("declared_status", String(20)),          # as uploaded, e.g. "Paid" for a settled/written-off invoice
    Column("amount_received", Integer, nullable=False, default=0),   # worked out from payments
    Column("outstanding", Integer, nullable=False, default=0),
    Column("status", String(20), nullable=False, default="Open", index=True),
)

payments_received = Table(
    "payments_received", metadata,
    Column("receipt_id", String(40), primary_key=True),
    Column("invoice_id", String(40), index=True),   # empty for other income, e.g. owner capital
    Column("customer_id", String(30), index=True),
    Column("date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("method", String(40)),
)

supplier_bills = Table(
    "supplier_bills", metadata,
    Column("bill_id", String(40), primary_key=True),
    Column("supplier_id", String(30), ForeignKey("suppliers.supplier_id"), nullable=False, index=True),
    Column("bill_date", Date, nullable=False),
    Column("due_date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("declared_status", String(20)),
    Column("amount_paid", Integer, nullable=False, default=0),
    Column("outstanding", Integer, nullable=False, default=0),
    Column("status", String(20), nullable=False, default="Open", index=True),
)

payments_made = Table(
    "payments_made", metadata,
    Column("payment_id", String(40), primary_key=True),
    Column("bill_id", String(40), index=True),
    Column("supplier_id", String(30), index=True),
    Column("date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("note", Text),
)

expenses = Table(
    "expenses", metadata,
    Column("expense_id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, index=True),
    Column("category", String(80), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("vendor", String(160)),
    Column("recurring", String(20)),
)

cash_ledger = Table(   # rebuilt from the tables above whenever data changes
    "cash_ledger", metadata,
    Column("entry_id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, index=True),
    Column("type", String(30), nullable=False),
    Column("reference", String(40)),
    Column("description", String(240)),
    Column("amount", Integer, nullable=False),
    Column("balance", Integer, nullable=False),
)

memory_events = Table(
    "memory_events", metadata,
    Column("event_id", String(40), primary_key=True),
    Column("date", Date, nullable=False, index=True),
    Column("entity_type", String(30), nullable=False),
    Column("entity_id", String(40), index=True),
    Column("event_type", String(60), nullable=False),
    Column("description", Text, nullable=False),
    Column("outcome", Text),
)

agent_log = Table(   # what the agent learned while running (also sent to Hindsight)
    "agent_log", metadata,
    Column("log_id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", String(30), nullable=False),
    Column("user_id", Integer),
    Column("kind", String(20), nullable=False),      # recommendation | feedback | outcome
    Column("text", Text, nullable=False),
)

TABLES = {t.name: t for t in metadata.sorted_tables}

_engines: dict[int, Engine] = {}
_lock = Lock()


# ------------------------------------------------------------------ reports and the audit trail
# Kept in their own metadata so that replacing the records (e.g. reloading the demo) never wipes
# the reports you generated, the links you shared or the audit trail.
records = MetaData()

reports = Table(
    "reports", records,
    Column("report_id", String(24), primary_key=True),
    Column("kind", String(20), nullable=False),            # summary | comparison
    Column("title", String(200), nullable=False),
    Column("period_from", Date),
    Column("period_to", Date),
    Column("created_at", DateTime, nullable=False, index=True),
    Column("created_by", String(160), nullable=False),
    Column("source", String(20), nullable=False, default="manual"),   # manual | scheduled
    Column("data", Text, nullable=False),                  # the report itself, as JSON (a snapshot)
)

report_shares = Table(   # read-only links
    "report_shares", records,
    Column("token", String(80), primary_key=True),
    Column("report_id", String(24), nullable=False, index=True),
    Column("created_at", DateTime, nullable=False),
    Column("created_by", String(160), nullable=False),
    Column("expires_at", DateTime),
    Column("revoked", Boolean, nullable=False, default=False),
    Column("views", Integer, nullable=False, default=0),
    Column("last_viewed_at", DateTime),
)

report_schedules = Table(
    "report_schedules", records,
    Column("schedule_id", Integer, primary_key=True, autoincrement=True),
    Column("frequency", String(10), nullable=False),       # weekly | monthly
    Column("weekday", Integer, default=0),                 # weekly: 0 = Monday
    Column("day_of_month", Integer, default=1),            # monthly: 1-28
    Column("hour", Integer, default=9),
    Column("kind", String(20), nullable=False, default="summary"),
    Column("recipients", Text, default=""),                # comma-separated; empty = management list
    Column("active", Boolean, nullable=False, default=True),
    Column("next_run", DateTime),
    Column("last_run", DateTime),
    Column("last_status", String(240)),
    Column("created_by", String(160), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

audit_log = Table(
    "audit_log", records,
    Column("entry_id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime, nullable=False, index=True),
    Column("actor", String(160), nullable=False),
    Column("action", String(60), nullable=False, index=True),
    Column("category", String(20), nullable=False),        # report | money | data | settings | sharing
    Column("detail", Text, default=""),
)


def engine_for(business_id: int) -> Engine:
    with _lock:
        if business_id not in _engines:
            eng = create_engine(settings.tenant_db_url.format(id=int(business_id)), future=True)
            metadata.create_all(eng)
            records.create_all(eng)
            _engines[business_id] = eng
        return _engines[business_id]


def drop(business_id: int) -> None:
    with _lock:
        eng = _engines.pop(business_id, None) or create_engine(settings.tenant_db_url.format(id=int(business_id)))
        metadata.drop_all(eng)
        records.drop_all(eng)
        eng.dispose()
