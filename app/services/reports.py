"""Reports: a snapshot of the numbers, saved so it can be printed, emailed, shared and looked at again later.

Two kinds:
- summary:     the cash-flow report (cash, net cash flow, financial position, alerts, who owes, what's due)
- comparison:  two periods side by side (money in and out, invoicing, how fast customers paid, expenses by category)

A report is a frozen copy: later uploads don't change a report that was already sent to someone.
"""
from __future__ import annotations

import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from app.core.errors import AppError
from app.core.money import as_date, inr
from app.db import tenant
from app.services import alerts as smart_alerts, insights
from app.services.audit import now
from app.services.books import Books
from app.services.forecast import Forecaster


# ------------------------------------------------------------------ building reports
def summary(fc: Forecaster, business: dict) -> dict:
    b = fc.b
    dash = insights.dashboard_forecast(fc)
    pos = insights.position(fc)
    al = smart_alerts.smart_alerts(fc)
    acts = insights.this_week(fc).get("actions", [])
    customers = insights.customer_list(fc)
    bills = insights.upcoming_bills(fc, 45)
    today = b.as_of_date()
    spend: dict[str, int] = defaultdict(int)
    for e in b.rows("SELECT category, amount FROM expenses WHERE date > :s AND date <= :t",
                    s=(today - timedelta(days=30)).isoformat(), t=today.isoformat()):
        spend[e["category"]] += int(e["amount"])
    return {
        "business": {"name": business["name"], "city": business.get("city") or ""},
        "as_of": today.isoformat(),
        "cash": pos["cash"],
        "flow": dash["flow"], "horizon_end": dash["horizon_end"], "horizon_days": dash["horizon_days"],
        "key_bill": dash["key_bill"], "target_date": dash["target_date"],
        "on_target": {k: dash["summary"][k]["on_target"] for k in ("best", "likely", "worst", "naive")},
        "lowest": {k: {"amount": dash["summary"][k]["lowest"], "date": dash["summary"][k]["lowest_date"]}
                   for k in ("best", "likely", "worst")},
        "position": pos,
        "alerts": [a for a in al["alerts"] if a["severity"] in ("critical", "warning")][:8],
        "alert_counts": al["counts"],
        "actions": [{"title": a["title"], "detail": a["detail"]} for a in acts],
        "receivables": [{"name": c["name"], "open": c["open_total"], "days_late": c.get("median_days_late"),
                         "on_time_pct": c.get("on_time_rate_pct")} for c in customers if c["open_total"] > 0][:8],
        "payables": [{"supplier": x["supplier"], "bill_id": x["bill_id"], "due": x["due"], "amount": x["amount"]}
                     for x in bills["bills"]][:10],
        "payables_total": bills["total"],
        "expenses_30": sorted(({"category": k, "amount": v} for k, v in spend.items()), key=lambda x: -x["amount"]),
    }


def period_stats(b: Books, start: date, end: date) -> dict:
    """What actually happened between two dates (both included)."""
    if end < start:
        raise AppError(422, "A period's end date can't be before its start date.", "bad_period")
    s, e = start.isoformat(), end.isoformat()
    moves = b.rows("SELECT type, amount FROM cash_ledger WHERE date >= :s AND date <= :e", s=s, e=e)
    cash_in = sum(int(m["amount"]) for m in moves if m["type"] == "Receipt")
    paid_suppliers = -sum(int(m["amount"]) for m in moves if m["type"] == "Supplier payment")
    expenses = -sum(int(m["amount"]) for m in moves if m["type"] == "Expense")
    adjust = sum(int(m["amount"]) for m in moves if m["type"] == "Balance adjustment")
    inv = b.rows("SELECT amount FROM invoices WHERE issue_date >= :s AND issue_date <= :e", s=s, e=e)
    bills = b.rows("SELECT amount FROM supplier_bills WHERE bill_date >= :s AND bill_date <= :e", s=s, e=e)
    pays = b.rows("SELECT p.date, p.amount, i.due_date FROM payments_received p JOIN invoices i "
                  "ON p.invoice_id = i.invoice_id WHERE p.date >= :s AND p.date <= :e", s=s, e=e)
    late = [(as_date(p["date"]) - as_date(p["due_date"])).days for p in pays]
    on_time_amt = sum(int(p["amount"]) for p in pays if as_date(p["date"]) <= as_date(p["due_date"]))
    paid_amt = sum(int(p["amount"]) for p in pays)
    by_cat: dict[str, int] = defaultdict(int)
    for x in b.rows("SELECT category, amount FROM expenses WHERE date >= :s AND date <= :e", s=s, e=e):
        by_cat[x["category"]] += int(x["amount"])
    return {
        "from": s, "to": e, "days": (end - start).days + 1,
        "opening": b.cash_on(start - timedelta(days=1)), "closing": b.cash_on(end),
        "cash_in": cash_in, "paid_suppliers": paid_suppliers, "expenses": expenses, "adjustments": adjust,
        "cash_out": paid_suppliers + expenses, "net": cash_in - paid_suppliers - expenses + adjust,
        "invoiced": sum(int(i["amount"]) for i in inv), "invoices": len(inv),
        "billed": sum(int(x["amount"]) for x in bills), "bills": len(bills),
        "avg_days_late": round(sum(late) / len(late), 1) if late else None,
        "on_time_pct": round(on_time_amt / paid_amt * 100) if paid_amt else None,
        "expenses_by_category": dict(by_cat),
    }


def _label(start: date, end: date) -> str:
    if start.day == 1 and (end + timedelta(days=1)).day == 1 and start.month == end.month:
        return start.strftime("%B %Y")
    return f"{start:%d %b %Y} – {end:%d %b %Y}"


# (label, key, which way is good)
COMPARE_ROWS = [
    ("Cash at start", "opening", None), ("Cash at end", "closing", "up"),
    ("Money in", "cash_in", "up"), ("Paid to suppliers", "paid_suppliers", None),
    ("Expenses", "expenses", "down"), ("Net cash flow", "net", "up"),
    ("Invoiced to customers", "invoiced", "up"), ("Bills from suppliers", "billed", None),
    ("Average days late (customers)", "avg_days_late", "down"), ("Paid on time (by value)", "on_time_pct", "up"),
]


def comparison(fc: Forecaster, business: dict, a: tuple[date, date], b_: tuple[date, date]) -> dict:
    A, B = period_stats(fc.b, *a), period_stats(fc.b, *b_)
    rows = []
    for label, key, good in COMPARE_ROWS:
        va, vb = A[key], B[key]
        change = None if va is None or vb is None else round(va - vb, 1)
        pct = None if change is None or not vb else round(change / abs(vb) * 100)
        rows.append({"label": label, "key": key, "a": va, "b": vb, "change": change, "pct": pct, "good": good,
                     "unit": "days" if key == "avg_days_late" else "%" if key == "on_time_pct" else "inr"})
    cats = sorted(set(A["expenses_by_category"]) | set(B["expenses_by_category"]),
                  key=lambda k: -(A["expenses_by_category"].get(k, 0) + B["expenses_by_category"].get(k, 0)))
    return {
        "business": {"name": business["name"], "city": business.get("city") or ""},
        "as_of": fc.b.as_of_date().isoformat(),
        "a": {"label": _label(*a), **A}, "b": {"label": _label(*b_), **B},
        "rows": rows,
        "expenses": [{"category": k, "a": A["expenses_by_category"].get(k, 0), "b": B["expenses_by_category"].get(k, 0)}
                     for k in cats],
    }


def month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def default_periods(today: date, frequency: str = "monthly") -> tuple[tuple[date, date], tuple[date, date]]:
    """Last full month vs the month before (or the last 7 days vs the 7 before)."""
    if frequency == "weekly":
        a = (today - timedelta(days=6), today)
        return a, (a[0] - timedelta(days=7), a[0] - timedelta(days=1))
    last = month_bounds(today.replace(day=1) - timedelta(days=1))
    return last, month_bounds(last[0] - timedelta(days=1))


# ------------------------------------------------------------------ saving and reading
def _row(r) -> dict:
    d = dict(r)
    d["created_at"] = d["created_at"].isoformat() + "Z"
    for k in ("period_from", "period_to"):
        if d.get(k):
            d[k] = d[k].isoformat()
    if "data" in d:
        d["data"] = json.loads(d["data"])
    return d


def create(eng: Engine, fc: Forecaster, business: dict, who: str, kind: str = "summary", *,
           a: tuple[date, date] | None = None, b: tuple[date, date] | None = None, source: str = "manual",
           title: str | None = None) -> dict:
    today = fc.b.as_of_date()
    if kind == "summary":
        data = summary(fc, business)
        pf, pt = today, as_date(data["horizon_end"])
        title = title or f"Cash-flow report · {today:%d %b %Y}"
    elif kind == "comparison":
        if not a or not b:
            a, b = default_periods(today)
        data = comparison(fc, business, a, b)
        pf, pt = min(a[0], b[0]), max(a[1], b[1])
        title = title or f"{data['a']['label']} vs {data['b']['label']}"
    else:
        raise AppError(422, "kind must be 'summary' or 'comparison'.", "bad_kind")
    rid = "R" + secrets.token_hex(5).upper()
    row = {"report_id": rid, "kind": kind, "title": title[:200], "period_from": pf, "period_to": pt,
           "created_at": now(), "created_by": who[:160], "source": source, "data": json.dumps(data, default=str)}
    with eng.begin() as c:
        c.execute(tenant.reports.insert().values(**row))
    return get(eng, rid)


def history(eng: Engine, limit: int = 100) -> list[dict]:
    t = tenant.reports
    cols = [t.c.report_id, t.c.kind, t.c.title, t.c.period_from, t.c.period_to, t.c.created_at, t.c.created_by, t.c.source]
    with eng.connect() as c:
        rows = c.execute(select(*cols).order_by(t.c.created_at.desc()).limit(limit)).mappings().all()
        shares = c.execute(select(tenant.report_shares.c.report_id)
                           .where(tenant.report_shares.c.revoked.is_(False))).scalars().all()
    live = defaultdict(int)
    for r in shares:
        live[r] += 1
    return [{**_row(r), "shares": live.get(r["report_id"], 0)} for r in rows]


def get(eng: Engine, report_id: str) -> dict:
    with eng.connect() as c:
        r = c.execute(select(tenant.reports).where(tenant.reports.c.report_id == report_id)).mappings().first()
    if not r:
        raise AppError(404, "Report not found.", "report_not_found")
    return _row(r)


def delete(eng: Engine, report_id: str) -> dict:
    rep = get(eng, report_id)
    with eng.begin() as c:
        c.execute(tenant.reports.delete().where(tenant.reports.c.report_id == report_id))
        c.execute(update(tenant.report_shares).where(tenant.report_shares.c.report_id == report_id).values(revoked=True))
    return rep


# ------------------------------------------------------------------ read-only share links
def share(eng: Engine, business_id: int, report_id: str, who: str, days: int | None = 30) -> dict:
    get(eng, report_id)
    token = f"{business_id}-{secrets.token_urlsafe(24)}"       # 192 random bits: can't be guessed
    expires = now() + timedelta(days=days) if days else None
    with eng.begin() as c:
        c.execute(tenant.report_shares.insert().values(token=token, report_id=report_id, created_at=now(),
                                                       created_by=who[:160], expires_at=expires, revoked=False, views=0))
    return share_info(eng, token)


def _share_row(r, titles: dict) -> dict:
    d = dict(r)
    for k in ("created_at", "expires_at", "last_viewed_at"):
        d[k] = d[k].isoformat() + "Z" if d.get(k) else None
    d["expired"] = bool(r["expires_at"] and r["expires_at"] < now())
    d["active"] = not d["revoked"] and not d["expired"]
    d["title"] = titles.get(r["report_id"], "(deleted report)")
    return d


def share_info(eng: Engine, token: str) -> dict:
    with eng.connect() as c:
        r = c.execute(select(tenant.report_shares).where(tenant.report_shares.c.token == token)).mappings().first()
        titles = dict(c.execute(select(tenant.reports.c.report_id, tenant.reports.c.title)).all())
    if not r:
        raise AppError(404, "Link not found.", "share_not_found")
    return _share_row(r, titles)


def shares(eng: Engine) -> list[dict]:
    with eng.connect() as c:
        rows = c.execute(select(tenant.report_shares).order_by(tenant.report_shares.c.created_at.desc())).mappings().all()
        titles = dict(c.execute(select(tenant.reports.c.report_id, tenant.reports.c.title)).all())
    return [_share_row(r, titles) for r in rows]


def revoke(eng: Engine, token: str) -> dict:
    info = share_info(eng, token)
    with eng.begin() as c:
        c.execute(update(tenant.report_shares).where(tenant.report_shares.c.token == token).values(revoked=True))
    return {**info, "revoked": True, "active": False}


def open_shared(token: str) -> tuple[int, dict]:
    """For the public link: which business, and the report. Same 404 for unknown, revoked or expired links."""
    gone = AppError(404, "This link has expired or been turned off. Ask for a new one.", "share_unavailable")
    try:
        business_id = int(token.split("-", 1)[0])
    except ValueError:
        raise gone
    from app.services import accounts
    if not accounts.get_business(business_id):
        raise gone
    eng = tenant.engine_for(business_id)
    with eng.connect() as c:
        r = c.execute(select(tenant.report_shares).where(tenant.report_shares.c.token == token)).mappings().first()
    if not r or r["revoked"] or (r["expires_at"] and r["expires_at"] < now()):
        raise gone
    rep = get(eng, r["report_id"])
    with eng.begin() as c:
        c.execute(update(tenant.report_shares).where(tenant.report_shares.c.token == token)
                  .values(views=tenant.report_shares.c.views + 1, last_viewed_at=now()))
    return business_id, rep
