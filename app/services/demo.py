"""Load the Malabar Electronics demo data into a business, through the same import path as uploads."""
from __future__ import annotations

import csv

from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.errors import AppError
from app.core.money import as_date
from app.db import tenant
from app.services import ingest
from app.services.books import Books

ORDER = ["customers", "suppliers", "invoices", "payments_received", "supplier_bills", "payments_made",
         "expenses", "memory_events"]


def demo_profile() -> dict:
    path = settings.demo_data_dir / "business_profile.csv"
    if not path.exists():
        raise AppError(404, "Demo data not found. Run 'python generate_data.py' first.", "no_demo_data")
    with open(path, encoding="utf-8") as f:
        return {r["field"]: r["value"] for r in csv.DictReader(f)}


def clear(eng: Engine) -> None:
    tenant.metadata.drop_all(eng)
    tenant.metadata.create_all(eng)


def load(eng: Engine) -> dict:
    """Replace this business's records with the demo data. Returns row counts."""
    prof = demo_profile()
    clear(eng)
    books = Books(eng)
    books.set_profile({"opening_cash_balance": prof["opening_cash_balance"], "opening_date": prof["data_start"],
                       "as_of_date": prof["as_of_date"],
                       # anything typed in on the demo goes back to normal when it's reloaded
                       "bank_balance_amount": None, "bank_balance_date": None, "low_cash_threshold": None})
    as_of = as_date(prof["as_of_date"])
    counts = {}
    for kind in ORDER:
        content = (settings.demo_data_dir / f"{kind}.csv").read_bytes()
        rows, errors, _ = ingest.validate(eng, kind, ingest.read_csv(content))
        if errors:
            raise AppError(500, f"Demo file {kind}.csv has problems: {errors[0]}", "bad_demo_data")
        ingest.write(eng, kind, rows, "replace")
        counts[kind] = len(rows)
    counts["books"] = ingest.recompute(eng, as_of)
    return counts


def meta() -> dict:
    p = demo_profile()
    return {"name": p.get("business_name", "Malabar Electronics Distributors"), "city": p.get("city", ""),
            "owner_name": p.get("owner", ""), "industry": p.get("industry", "")}
