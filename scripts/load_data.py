"""Load the demo CSVs from data/ into the database.

Run from the project root:   python -m scripts.load_data
Safe to re-run: it drops and recreates the tables each time.
"""
import csv
from datetime import date

from sqlalchemy import Date, Float, Integer, func, select

from app.config import DATA_DIR, DATABASE_URL
from app.db import (business_profile, cash_ledger, customers, engine, expenses, invoices,
                    memory_events, metadata, payments_made, payments_received,
                    supplier_bills, suppliers)

# Order matters: parents before children (foreign keys).
LOAD_ORDER = [
    (business_profile, "business_profile.csv"),
    (customers, "customers.csv"),
    (suppliers, "suppliers.csv"),
    (invoices, "invoices.csv"),
    (payments_received, "payments_received.csv"),
    (supplier_bills, "supplier_bills.csv"),
    (payments_made, "payments_made.csv"),
    (expenses, "expenses.csv"),
    (cash_ledger, "cash_ledger.csv"),
    (memory_events, "memory_events.csv"),
]


def convert(table, row):
    """Turn CSV text into proper Python types based on the column definitions."""
    out = {}
    for col in table.columns:
        if col.name not in row:
            continue  # e.g. auto-increment ids
        raw = row[col.name]
        if raw == "" or raw is None:
            out[col.name] = None
        elif isinstance(col.type, Date):
            out[col.name] = date.fromisoformat(raw)
        elif isinstance(col.type, Integer):
            out[col.name] = int(float(raw))
        elif isinstance(col.type, Float):
            out[col.name] = float(raw)
        else:
            out[col.name] = raw
    return out


def main():
    missing = [name for _, name in LOAD_ORDER if not (DATA_DIR / name).exists()]
    if missing:
        raise SystemExit(f"Missing files in {DATA_DIR}: {missing}\n"
                         "Run 'python generate_data.py' first.")

    print(f"Database: {DATABASE_URL}")
    metadata.drop_all(engine)
    metadata.create_all(engine)

    with engine.begin() as conn:
        for table, filename in LOAD_ORDER:
            with open(DATA_DIR / filename, encoding="utf-8", newline="") as f:
                rows = [convert(table, r) for r in csv.DictReader(f)]
            if rows:
                conn.execute(table.insert(), rows)
            print(f"  {table.name:<18} {len(rows):>4} rows")

    # quick sanity check
    with engine.connect() as conn:
        bal = conn.execute(select(cash_ledger.c.balance)
                           .order_by(cash_ledger.c.entry_id.desc()).limit(1)).scalar()
        open_ar = conn.execute(select(func.sum(invoices.c.outstanding))
                               .where(invoices.c.status != "Paid")).scalar()
        open_ap = conn.execute(select(func.sum(supplier_bills.c.amount))
                               .where(supplier_bills.c.status != "Paid")).scalar()
    print(f"\nCash today: Rs {bal:,} | Receivables open: Rs {open_ar:,} | Bills open: Rs {open_ap:,}")
    print("Database ready.")


if __name__ == "__main__":
    main()
