"""Bring a business's own records in from CSV files, check them, and keep the books consistent.

After any upload we recompute what can be derived (amount received, what is still owed,
invoice and bill status, the cash ledger), so uploaded files only need the raw facts.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from app.core.errors import AppError
from app.core.money import as_date
from app.db import tenant

MAX_ERRORS = 50
MAX_BYTES = 5 * 1024 * 1024
CLOSED = {"paid", "closed", "settled", "written off", "written-off", "cancelled", "canceled"}


@dataclass(frozen=True)
class Col:
    name: str
    kind: str = "str"          # str | money | int | float | date | choice
    required: bool = False
    default: object = None
    example: str = ""
    choices: tuple = ()
    help: str = ""


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    table: str
    pk: str | None
    cols: tuple
    help: str
    computed: tuple = ()       # columns we work out ourselves; ignored if present in the file


SPECS: dict[str, Spec] = {s.key: s for s in [
    Spec("customers", "Customers", "customers", "customer_id", (
        Col("customer_id", required=True, example="C001"),
        Col("name", required=True, example="Mehta Traders"),
        Col("city", example="Ernakulam"),
        Col("contact_person", example="Rajesh Mehta"),
        Col("payment_terms_days", "int", default=30, example="30", help="Days to pay after the invoice date"),
    ), "Everyone who buys from you on credit."),
    Spec("suppliers", "Suppliers", "suppliers", "supplier_id", (
        Col("supplier_id", required=True, example="S001"),
        Col("name", required=True, example="Vertex Electronics"),
        Col("category", example="Stock"),
        Col("payment_terms_days", "int", default=30, example="30"),
        Col("early_payment_discount_pct", "float", default=0, example="2"),
        Col("discount_window_days", "int", default=0, example="10"),
        Col("late_fee_pct_per_month", "float", default=0, example="1.5"),
    ), "Everyone you buy from on credit, with their terms."),
    Spec("invoices", "Sales invoices", "invoices", "invoice_id", (
        Col("invoice_id", required=True, example="INV-1001"),
        Col("customer_id", required=True, example="C001"),
        Col("issue_date", "date", required=True, example="2026-10-08"),
        Col("due_date", "date", example="2026-11-07", help="Left blank: invoice date + the customer's terms"),
        Col("amount", "money", required=True, example="330000"),
        Col("status", "str", example="", help="Only needed to mark an invoice settled, e.g. after a write-off: Paid"),
    ), "What customers owe you. Payments go in a separate file.", computed=("amount_received", "outstanding")),
    Spec("payments_received", "Payments received", "payments_received", "receipt_id", (
        Col("receipt_id", example="RCPT-0001", help="Left blank: numbered for you"),
        Col("invoice_id", example="INV-1001", help="Blank for other income, e.g. owner capital"),
        Col("customer_id", example="C001", help="Left blank: taken from the invoice"),
        Col("date", "date", required=True, example="2026-11-09"),
        Col("amount", "money", required=True, example="330000"),
        Col("method", example="Bank transfer"),
    ), "Money that came in. Part-payments are fine: one row each."),
    Spec("supplier_bills", "Supplier bills", "supplier_bills", "bill_id", (
        Col("bill_id", required=True, example="BILL-586"),
        Col("supplier_id", required=True, example="S001"),
        Col("bill_date", "date", required=True, example="2026-10-14"),
        Col("due_date", "date", example="2026-11-13", help="Left blank: bill date + the supplier's terms"),
        Col("amount", "money", required=True, example="1500000"),
        Col("status", "str", example="", help="Only needed to mark a bill settled: Paid"),
    ), "What you owe suppliers. Payments go in a separate file.", computed=("amount_paid", "outstanding")),
    Spec("payments_made", "Payments made", "payments_made", "payment_id", (
        Col("payment_id", example="PAY-0001", help="Left blank: numbered for you"),
        Col("bill_id", example="BILL-586"),
        Col("supplier_id", example="S001", help="Left blank: taken from the bill"),
        Col("date", "date", required=True, example="2026-11-13"),
        Col("amount", "money", required=True, example="1500000"),
        Col("note", example="Paid early, 2% discount taken"),
    ), "Money paid to suppliers."),
    Spec("expenses", "Expenses", "expenses", None, (
        Col("date", "date", required=True, example="2026-11-01"),
        Col("category", required=True, example="Rent"),
        Col("amount", "money", required=True, example="120000"),
        Col("vendor", example="Landlord"),
        Col("recurring", "choice", default="No", example="Monthly", choices=("Monthly", "Variable", "Yearly", "No"),
            help="Monthly and Variable expenses are projected forward in the forecast"),
    ), "Rent, salaries, utilities and other spending not tied to a supplier bill."),
    Spec("memory_events", "History for memory", "memory_events", "event_id", (
        Col("event_id", example="E0001", help="Left blank: numbered for you"),
        Col("date", "date", required=True, example="2026-04-07"),
        Col("entity_type", "choice", required=True, example="customer",
            choices=("customer", "supplier", "owner", "expense", "other")),
        Col("entity_id", example="C001", help="Customer or supplier id, or OWNER"),
        Col("event_type", required=True, example="collection_attempt",
            help="e.g. collection_attempt, dispute, extension_request, decision, preference, customer_note"),
        Col("description", required=True, example="Phoned Rajesh Mehta about INV-1153"),
        Col("outcome", example="Paid 5 days late"),
    ), "What happened and what worked: calls, disputes, negotiations, decisions. Sent to Hindsight memory."),
]}

ALIASES = {"invoice_no": "invoice_id", "invoice_number": "invoice_id", "bill_no": "bill_id", "bill_number": "bill_id",
           "receipt_no": "receipt_id", "payment_no": "payment_id", "customer_code": "customer_id",
           "supplier_code": "supplier_id", "terms": "payment_terms_days", "amount_inr": "amount",
           "invoice_date": "issue_date", "payment_date": "date", "expense_date": "date"}


# ------------------------------------------------------------------ parsing helpers
def _key(h: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")
    return ALIASES.get(k, k)


_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
                 "%d-%b-%Y", "%d-%b-%y", "%d/%m/%y")


def parse_date(v: str) -> date:
    s = v.strip()
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError("use a date like 2026-11-05 or 05/11/2026")


def parse_money(v: str) -> int:
    s = re.sub(r"(?i)(rs\.?|inr|₹|,|\s)", "", v.strip())
    if not s:
        raise ValueError("is empty")
    n = float(s)
    if n < 0:
        raise ValueError("can't be negative")
    return int(round(n))


def parse_float(v: str) -> float:
    return float(v.strip().rstrip("%").replace(",", ""))


def parse_int(v: str) -> int:
    return int(round(float(v.strip().replace(",", ""))))


def _convert(col: Col, raw: str):
    if raw is None or str(raw).strip() == "":
        return col.default
    raw = str(raw)
    if col.kind == "date":
        return parse_date(raw)
    if col.kind == "money":
        return parse_money(raw)
    if col.kind == "int":
        return parse_int(raw)
    if col.kind == "float":
        return parse_float(raw)
    if col.kind == "choice":
        for c in col.choices:
            if raw.strip().lower() == c.lower():
                return c
        raise ValueError(f"use one of {', '.join(col.choices)}")
    return raw.strip()


def read_csv(content: bytes) -> list[dict]:
    if len(content) > MAX_BYTES:
        raise AppError(413, "That file is larger than 5 MB. Split it into smaller files.", "file_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise AppError(422, "That file is empty. It needs a header row and at least one data row.", "empty_file")
    rows = [{_key(k): v for k, v in r.items() if k is not None} for r in reader
            if any((v or "").strip() for v in r.values() if isinstance(v, str))]
    if not rows:
        raise AppError(422, "That file has a header row but no data rows.", "empty_file")
    return rows


def template_csv(kind: str) -> str:
    spec = SPECS[kind]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([c.name for c in spec.cols])
    w.writerow([c.example for c in spec.cols])
    return out.getvalue()


def describe() -> list[dict]:
    return [{"kind": s.key, "label": s.label, "help": s.help,
             "columns": [{"name": c.name, "required": c.required, "type": c.kind, "help": c.help,
                          "choices": list(c.choices)} for c in s.cols]} for s in SPECS.values()]


# ------------------------------------------------------------------ validation
def _existing_ids(eng: Engine, table: str, col: str) -> set[str]:
    t = tenant.TABLES[table]
    with eng.connect() as c:
        return {r[0] for r in c.execute(select(t.c[col]))}


def validate(eng: Engine, kind: str, raw_rows: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Return (clean rows, errors, warnings). Row numbers match the spreadsheet (header is row 1)."""
    spec = SPECS[kind]
    known = {c.name for c in spec.cols} | set(spec.computed)
    headers = set(raw_rows[0].keys())
    errors: list[dict] = []
    warnings: list[str] = []

    missing = [c.name for c in spec.cols if c.required and c.name not in headers]
    if missing:
        raise AppError(422, f"The file is missing these columns: {', '.join(missing)}. Download the template to see the layout.",
                       "missing_columns", [{"row": 1, "column": m, "message": "column is missing"} for m in missing])
    extra = sorted(h for h in headers - known if h)
    if extra:
        warnings.append(f"Ignored columns not used by Cashwise: {', '.join(extra)}")

    terms = {}
    if kind == "invoices":
        terms = {r["customer_id"]: r["payment_terms_days"] for r in _rows(eng, "SELECT customer_id, payment_terms_days FROM customers")}
    if kind == "supplier_bills":
        terms = {r["supplier_id"]: r["payment_terms_days"] for r in _rows(eng, "SELECT supplier_id, payment_terms_days FROM suppliers")}
    parents = {
        "invoices": ("customer_id", _existing_ids(eng, "customers", "customer_id"), "customer", "customers"),
        "supplier_bills": ("supplier_id", _existing_ids(eng, "suppliers", "supplier_id"), "supplier", "suppliers"),
        "payments_received": ("invoice_id", _existing_ids(eng, "invoices", "invoice_id"), "invoice", "sales invoices"),
        "payments_made": ("bill_id", _existing_ids(eng, "supplier_bills", "bill_id"), "bill", "supplier bills"),
    }.get(kind)
    owner_of = {}
    if kind == "payments_received":
        owner_of = {r["invoice_id"]: r["customer_id"] for r in _rows(eng, "SELECT invoice_id, customer_id FROM invoices")}
    if kind == "payments_made":
        owner_of = {r["bill_id"]: r["supplier_id"] for r in _rows(eng, "SELECT bill_id, supplier_id FROM supplier_bills")}

    clean, seen = [], set()
    for idx, raw in enumerate(raw_rows):
        line = idx + 2
        row, bad = {}, False
        for col in spec.cols:
            value = raw.get(col.name)
            try:
                v = _convert(col, value)
                if col.required and v in (None, ""):
                    raise ValueError("is required")
                row[col.name] = v
            except ValueError as e:
                bad = True
                errors.append({"row": line, "column": col.name, "value": (value or "")[:40], "message": str(e)})
        if bad:
            if len(errors) >= MAX_ERRORS:
                break
            continue

        # fill in what can be worked out
        if kind in ("invoices", "supplier_bills") and not row.get("due_date"):
            party = row["customer_id" if kind == "invoices" else "supplier_id"]
            start = row["issue_date" if kind == "invoices" else "bill_date"]
            row["due_date"] = start + timedelta(days=int(terms.get(party) or 30))
        if kind in ("invoices", "supplier_bills"):
            row["declared_status"] = row.pop("status", None) or None
        if kind == "payments_received" and row.get("invoice_id") and not row.get("customer_id"):
            row["customer_id"] = owner_of.get(row["invoice_id"])
        if kind == "payments_made" and row.get("bill_id") and not row.get("supplier_id"):
            row["supplier_id"] = owner_of.get(row["bill_id"])
        if kind == "memory_events" and row.get("entity_id") is None:
            row["entity_id"] = "OWNER" if row["entity_type"] == "owner" else ""

        if parents:
            col, ids, what, table_label = parents
            if row.get(col) and row[col] not in ids:
                errors.append({"row": line, "column": col, "value": str(row[col]),
                               "message": f"no {what} with this id. Upload {table_label} first"})
                continue
        if spec.pk:
            if not row.get(spec.pk):
                prefix = {"receipt_id": "RCPT", "payment_id": "PAY", "event_id": "E"}[spec.pk]
                row[spec.pk] = f"{prefix}-U{idx + 1:05d}"
            if row[spec.pk] in seen:
                errors.append({"row": line, "column": spec.pk, "value": row[spec.pk], "message": "appears twice in this file"})
                continue
            seen.add(row[spec.pk])
        clean.append(row)
        if len(errors) >= MAX_ERRORS:
            break
    return clean, errors, warnings


def _rows(eng: Engine, sql: str) -> list[dict]:
    from sqlalchemy import text
    with eng.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


# ------------------------------------------------------------------ write + recompute
def write(eng: Engine, kind: str, rows: list[dict], mode: str) -> dict:
    spec = SPECS[kind]
    t = tenant.TABLES[spec.table]
    inserted = replaced = 0
    with eng.begin() as c:
        if mode == "replace":
            replaced = c.execute(delete(t)).rowcount or 0
        elif spec.pk:
            keys = [r[spec.pk] for r in rows]
            for i in range(0, len(keys), 500):
                replaced += c.execute(delete(t).where(t.c[spec.pk].in_(keys[i:i + 500]))).rowcount or 0
        if rows:
            c.execute(t.insert(), [{k: v for k, v in r.items() if k in t.c} for r in rows])
            inserted = len(rows)
    return {"inserted": inserted, "replaced": replaced}


def recompute(eng: Engine, as_of: date) -> dict:
    """Work out received/owed/status for invoices and bills, then rebuild the cash ledger."""
    profile = {r["field"]: r["value"] for r in _rows(eng, "SELECT field, value FROM business_profile")}
    received, paid = {}, {}
    for r in _rows(eng, "SELECT invoice_id, amount FROM payments_received WHERE invoice_id IS NOT NULL AND invoice_id != ''"):
        received[r["invoice_id"]] = received.get(r["invoice_id"], 0) + r["amount"]
    for r in _rows(eng, "SELECT bill_id, amount FROM payments_made WHERE bill_id IS NOT NULL AND bill_id != ''"):
        paid[r["bill_id"]] = paid.get(r["bill_id"], 0) + r["amount"]
    discount = {r["supplier_id"]: r["early_payment_discount_pct"] or 0
                for r in _rows(eng, "SELECT supplier_id, early_payment_discount_pct FROM suppliers")}

    inv, bil, led = tenant.invoices, tenant.supplier_bills, tenant.cash_ledger
    with eng.begin() as c:
        for r in _rows(eng, "SELECT invoice_id, due_date, amount, declared_status FROM invoices"):
            got = received.get(r["invoice_id"], 0)
            closed = (r["declared_status"] or "").strip().lower() in CLOSED
            owed = 0 if closed else max(r["amount"] - got, 0)
            status = ("Paid" if owed == 0 else "Partially paid" if got else
                      "Overdue" if as_date(r["due_date"]) < as_of else "Open")
            c.execute(inv.update().where(inv.c.invoice_id == r["invoice_id"])
                      .values(amount_received=got, outstanding=owed, status=status))
        for r in _rows(eng, "SELECT bill_id, supplier_id, due_date, amount, declared_status FROM supplier_bills"):
            got = paid.get(r["bill_id"], 0)
            closed = (r["declared_status"] or "").strip().lower() in CLOSED
            settled = closed or (got > 0 and got >= r["amount"] * (1 - discount.get(r["supplier_id"], 0) / 100) - 1)
            owed = 0 if settled else max(r["amount"] - got, 0)
            status = ("Paid" if owed == 0 else "Partially paid" if got else
                      "Overdue" if as_date(r["due_date"]) < as_of else "Open")
            c.execute(bil.update().where(bil.c.bill_id == r["bill_id"])
                      .values(amount_paid=got, outstanding=owed, status=status))

    # cash ledger
    cust = {r["customer_id"]: r["name"] for r in _rows(eng, "SELECT customer_id, name FROM customers")}
    sup = {r["supplier_id"]: r["name"] for r in _rows(eng, "SELECT supplier_id, name FROM suppliers")}
    moves = []
    for r in _rows(eng, "SELECT * FROM payments_received"):
        desc = f"{cust.get(r['customer_id'], r['customer_id'] or '')} - {r['invoice_id']}" if r["invoice_id"] else (r["method"] or "Other income")
        moves.append((as_date(r["date"]), 0, "Receipt", r["receipt_id"], desc, r["amount"]))
    for r in _rows(eng, "SELECT * FROM payments_made"):
        moves.append((as_date(r["date"]), 1, "Supplier payment", r["payment_id"],
                      f"{sup.get(r['supplier_id'], r['supplier_id'] or '')} - {r['bill_id'] or ''}".strip(" -"), -r["amount"]))
    for r in _rows(eng, "SELECT * FROM expenses"):
        moves.append((as_date(r["date"]), 2, "Expense", f"EXP-{r['expense_id']:04d}", r["category"], -r["amount"]))
    opening_date = as_date(profile["opening_date"]) if profile.get("opening_date") else None
    if opening_date:
        moves = [m for m in moves if m[0] >= opening_date]
    moves.sort(key=lambda m: (m[0], m[1]))
    bal = int(float(profile.get("opening_cash_balance") or 0))
    entries = []
    for d, _, typ, ref, desc, amt in moves:
        bal += amt
        entries.append({"date": d, "type": typ, "reference": ref, "description": desc[:240], "amount": amt, "balance": bal})
    # The owner can type in the real bank balance for a day. We then add one "Balance adjustment" entry on that
    # day for whatever the records don't explain (bank charges, cash sales not uploaded, ...), so the ledger agrees
    # with the bank from then on, and every later payment still moves the balance as usual.
    if profile.get("bank_balance_amount") not in (None, "") and profile.get("bank_balance_date"):
        set_on = as_date(profile["bank_balance_date"])
        target = int(float(profile["bank_balance_amount"]))
        before = [e["balance"] for e in entries if e["date"] <= set_on]
        on_books = before[-1] if before else int(float(profile.get("opening_cash_balance") or 0))
        diff = target - on_books
        if diff:
            at = len(before)
            entries.insert(at, {"date": set_on, "type": "Balance adjustment", "reference": "BANK",
                                "description": "Matched to the bank balance you entered", "amount": diff,
                                "balance": target})
            for e in entries[at + 1:]:
                e["balance"] += diff

    with eng.begin() as c:
        c.execute(delete(led))
        if entries:
            c.execute(led.insert(), entries)

    today = [e["balance"] for e in entries if e["date"] <= as_of]
    cash = today[-1] if today else int(float(profile.get("opening_cash_balance") or 0))
    return {"cash_today": cash,
            "open_invoices": _rows(eng, "SELECT COUNT(*) AS n FROM invoices WHERE status != 'Paid'")[0]["n"],
            "open_bills": _rows(eng, "SELECT COUNT(*) AS n FROM supplier_bills WHERE status != 'Paid'")[0]["n"]}


def import_file(eng: Engine, kind: str, content: bytes, mode: str, as_of: date) -> dict:
    if kind not in SPECS:
        raise AppError(404, f"Unknown data type '{kind}'.", "unknown_kind")
    if mode not in ("replace", "append"):
        raise AppError(422, "mode must be 'replace' or 'append'.", "invalid_mode")
    raw = read_csv(content)
    rows, errors, warnings = validate(eng, kind, raw)
    if errors:
        n = len(errors)
        raise AppError(422, f"{n}{'+' if n >= MAX_ERRORS else ''} problem{'s' if n != 1 else ''} found, so nothing was saved. "
                            f"First: row {errors[0]['row']}, {errors[0]['column']} {errors[0]['message']}.",
                       "invalid_rows", errors)
    result = write(eng, kind, rows, mode)
    if kind in ("customers", "suppliers") and mode == "replace":
        child, col, label = ("invoices", "customer_id", "invoices") if kind == "customers" else ("supplier_bills", "supplier_id", "bills")
        keep = {r[SPECS[kind].pk] for r in rows}
        orphans = {r[col] for r in _rows(eng, f"SELECT DISTINCT {col} FROM {child}")} - keep
        if orphans:
            warnings.append(f"{len(orphans)} id(s) used in your {label} are not in this file: {', '.join(sorted(orphans)[:5])}")
    summary = recompute(eng, as_of)
    return {"kind": kind, "mode": mode, "rows_in_file": len(raw), **result, "warnings": warnings, "books": summary,
            "rows": rows if kind == "memory_events" else None}
