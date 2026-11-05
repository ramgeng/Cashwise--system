"""Books: read access to one business's financial records."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from app.core.money import as_date
from app.db import tenant


class Books:
    def __init__(self, engine: Engine):
        self.engine = engine

    # -------------------------------------------------------------- raw access
    def rows(self, sql: str, **params) -> list[dict]:
        params = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in params.items()}
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(text(sql), params)]

    def count(self, table: str) -> int:
        with self.engine.connect() as c:
            return c.execute(select(func.count()).select_from(tenant.TABLES[table])).scalar() or 0

    # -------------------------------------------------------------- profile / settings
    def profile(self) -> dict[str, str]:
        return {r["field"]: r["value"] for r in self.rows("SELECT field, value FROM business_profile")}

    def set_profile(self, values: dict) -> None:
        t = tenant.business_profile
        with self.engine.begin() as c:
            for k, v in values.items():
                c.execute(t.delete().where(t.c.field == k))
                if v not in (None, ""):
                    c.execute(t.insert().values(field=k, value=str(v)))

    def as_of_date(self) -> date:
        """'Today' for forecasts. Set in settings for demo data; otherwise the real date."""
        v = self.profile().get("as_of_date")
        return as_date(v) if v else date.today()

    def opening_balance(self) -> int:
        try:
            return int(float(self.profile().get("opening_cash_balance") or 0))
        except ValueError:
            return 0

    def cash_on(self, day: date) -> int:
        r = self.rows("SELECT balance FROM cash_ledger WHERE date <= :d ORDER BY date DESC, entry_id DESC LIMIT 1",
                      d=day)
        return int(r[0]["balance"]) if r else self.opening_balance()

    # -------------------------------------------------------------- people
    def customers(self) -> dict[str, dict]:
        return {r["customer_id"]: r for r in self.rows("SELECT * FROM customers ORDER BY name")}

    def suppliers(self) -> dict[str, dict]:
        return {r["supplier_id"]: r for r in self.rows("SELECT * FROM suppliers ORDER BY name")}

    def find_customer(self, name_or_id: str) -> str | None:
        """Map 'mehta', 'Mehta Traders' or 'C001' to a customer id."""
        q = (name_or_id or "").strip().lower()
        if not q:
            return None
        for cid, c in self.customers().items():
            if q == cid.lower() or q in c["name"].lower():
                return cid
        return None

    def find_supplier(self, name_or_id: str) -> str | None:
        q = (name_or_id or "").strip().lower()
        if not q:
            return None
        for sid, s in self.suppliers().items():
            if q == sid.lower() or q in s["name"].lower():
                return sid
        return None

    def counts(self) -> dict[str, int]:
        return {k: self.count(k) for k in ("customers", "suppliers", "invoices", "payments_received",
                                           "supplier_bills", "payments_made", "expenses", "memory_events")}
