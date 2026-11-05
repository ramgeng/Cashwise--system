"""Database schema: the hard numbers (facts for the maths).

Works with SQLite (default) and PostgreSQL without code changes.
"""
from sqlalchemy import (Column, Date, Float, ForeignKey, Integer, MetaData, String,
                        Table, Text, create_engine)

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

business_profile = Table(
    "business_profile", metadata,
    Column("field", String(50), primary_key=True),
    Column("value", String(200)),
)

customers = Table(
    "customers", metadata,
    Column("customer_id", String(10), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("city", String(50)),
    Column("contact_person", String(100)),
    Column("payment_terms_days", Integer, nullable=False),
)

suppliers = Table(
    "suppliers", metadata,
    Column("supplier_id", String(10), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("category", String(100)),
    Column("payment_terms_days", Integer, nullable=False),
    Column("early_payment_discount_pct", Float, default=0),
    Column("discount_window_days", Integer, default=0),
    Column("late_fee_pct_per_month", Float, default=0),
)

invoices = Table(
    "invoices", metadata,
    Column("invoice_id", String(20), primary_key=True),
    Column("customer_id", String(10), ForeignKey("customers.customer_id"), nullable=False, index=True),
    Column("issue_date", Date, nullable=False),
    Column("due_date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("amount_received", Integer, nullable=False),
    Column("outstanding", Integer, nullable=False),
    Column("status", String(20), nullable=False, index=True),
)

payments_received = Table(
    "payments_received", metadata,
    Column("receipt_id", String(20), primary_key=True),
    Column("invoice_id", String(20), index=True),   # empty for owner capital
    Column("customer_id", String(10), index=True),
    Column("date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("method", String(30)),
)

supplier_bills = Table(
    "supplier_bills", metadata,
    Column("bill_id", String(20), primary_key=True),
    Column("supplier_id", String(10), ForeignKey("suppliers.supplier_id"), nullable=False, index=True),
    Column("bill_date", Date, nullable=False),
    Column("due_date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("amount_paid", Integer, nullable=False),
    Column("status", String(20), nullable=False, index=True),
)

payments_made = Table(
    "payments_made", metadata,
    Column("payment_id", String(20), primary_key=True),
    Column("bill_id", String(20), ForeignKey("supplier_bills.bill_id"), index=True),
    Column("supplier_id", String(10), index=True),
    Column("date", Date, nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("note", Text),
)

expenses = Table(
    "expenses", metadata,
    Column("expense_id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, index=True),
    Column("category", String(50), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("vendor", String(100)),
    Column("recurring", String(20)),
)

cash_ledger = Table(
    "cash_ledger", metadata,
    Column("entry_id", Integer, primary_key=True, autoincrement=True),
    Column("date", Date, nullable=False, index=True),
    Column("type", String(30), nullable=False),
    Column("reference", String(20)),
    Column("description", String(200)),
    Column("amount", Integer, nullable=False),
    Column("balance", Integer, nullable=False),
)

# Kept in the database too, so the UI can show the evidence behind a memory.
memory_events = Table(
    "memory_events", metadata,
    Column("event_id", String(10), primary_key=True),
    Column("date", Date, nullable=False, index=True),
    Column("entity_type", String(20), nullable=False),
    Column("entity_id", String(10), index=True),
    Column("event_type", String(40), nullable=False),
    Column("description", Text, nullable=False),
    Column("outcome", Text),
)
