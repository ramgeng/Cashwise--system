"""Deterministic cash-flow maths. The LLM never calculates; it calls these functions.

Core idea: an expected collection is NOT guaranteed cash. For every open invoice we
look at how that customer actually paid their recent invoices (days late, part-payments)
and build three scenarios:
    best   = customer pays like their faster past payments (20th percentile)
    likely = customer pays like their typical past payment (median)
    worst  = customer pays like their slowest recent payments (90th percentile)
Bills and regular expenses are assumed to be paid on their due dates.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, median

from sqlalchemy import text

from app.db import engine

HISTORY_WINDOW = 8          # recent paid invoices per customer used as evidence
SCENARIOS = {"best": 0.2, "likely": 0.5, "worst": 0.9}


# ------------------------------------------------------------------ data access
def _rows(sql, **params):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params)]


def _d(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x))


def as_of_date() -> date:
    r = _rows("SELECT value FROM business_profile WHERE field = 'as_of_date'")
    return _d(r[0]["value"]) if r else date.today()


def cash_on(day: date) -> int:
    r = _rows("SELECT balance FROM cash_ledger WHERE date <= :d ORDER BY date DESC, entry_id DESC LIMIT 1",
              d=day)
    return int(r[0]["balance"]) if r else 0


def customers() -> dict[str, dict]:
    return {r["customer_id"]: r for r in _rows("SELECT * FROM customers")}


def suppliers() -> dict[str, dict]:
    return {r["supplier_id"]: r for r in _rows("SELECT * FROM suppliers")}


def find_customer(name_or_id: str) -> str | None:
    """Map 'mehta', 'Mehta Traders' or 'C001' to a customer_id."""
    q = name_or_id.strip().lower()
    for cid, c in customers().items():
        if q == cid.lower() or q in c["name"].lower():
            return cid
    return None


def find_supplier(name_or_id: str) -> str | None:
    q = name_or_id.strip().lower()
    for sid, s in suppliers().items():
        if q == sid.lower() or q in s["name"].lower():
            return sid
    return None


# ------------------------------------------------------------------ payment behaviour
def payment_history(customer_id: str, before: date | None = None) -> list[dict]:
    """Paid invoices for a customer, newest first, with how they were paid.

    Each item: invoice_id, due_date, final_delay (days after due of last payment),
    parts = [(delay_days, fraction_of_amount), ...]
    """
    before = before or as_of_date()
    invs = _rows("SELECT * FROM invoices WHERE customer_id = :c AND status = 'Paid' "
                 "ORDER BY due_date DESC", c=customer_id)
    rec = defaultdict(list)
    for r in _rows("SELECT invoice_id, date, amount FROM payments_received WHERE customer_id = :c", c=customer_id):
        rec[r["invoice_id"]].append(r)
    out = []
    for inv in invs:
        pays = sorted(rec.get(inv["invoice_id"], []), key=lambda p: _d(p["date"]))
        if not pays or _d(pays[-1]["date"]) > before:
            continue
        due = _d(inv["due_date"])
        total = sum(p["amount"] for p in pays)
        parts = [((_d(p["date"]) - due).days, p["amount"] / total) for p in pays]
        out.append({"invoice_id": inv["invoice_id"], "due_date": due,
                    "final_delay": parts[-1][0], "parts": parts})
    return out


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    return sorted_vals[round(q * (len(sorted_vals) - 1))]


def customer_profile(customer_id: str) -> dict:
    """Plain-numbers summary of how a customer pays. Evidence for explanations."""
    c = customers()[customer_id]
    hist = payment_history(customer_id)
    if not hist:
        return {"customer_id": customer_id, "name": c["name"], "paid_invoices": 0,
                "note": "No payment history yet."}
    delays = [h["final_delay"] for h in hist]
    recent = delays[:4]
    older = delays[4:12]
    by_q = defaultdict(list)
    for h in hist:
        by_q[f"{h['due_date'].year}-Q{(h['due_date'].month - 1) // 3 + 1}"].append(h["final_delay"])
    open_inv = _rows("SELECT invoice_id, due_date, outstanding, status FROM invoices "
                     "WHERE customer_id = :c AND status != 'Paid' ORDER BY due_date", c=customer_id)
    split = sum(1 for h in hist[:HISTORY_WINDOW] if len(h["parts"]) > 1)
    recent_change = None
    if older:
        diff = mean(recent) - mean(older)
        recent_change = "slower lately" if diff > 2 else "faster lately" if diff < -2 else "no recent change"
    # quarter-on-quarter trend over the last 4 quarters (least-squares slope)
    qs = [mean(v) for _, v in sorted(by_q.items())][-4:]
    quarterly_trend = None
    if len(qs) >= 3:
        xs = range(len(qs))
        mx, my = mean(xs), mean(qs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, qs)) / sum((x - mx) ** 2 for x in xs)
        quarterly_trend = (f"getting slower (+{slope:.1f} days per quarter)" if slope > 1.5 else
                           f"getting faster ({slope:.1f} days per quarter)" if slope < -1.5 else "stable")
    return {
        "customer_id": customer_id,
        "name": c["name"],
        "payment_terms_days": c["payment_terms_days"],
        "paid_invoices": len(hist),
        "median_days_late": median(delays),
        "avg_days_late_last_4": round(mean(recent), 1),
        "avg_days_late_before_that": round(mean(older), 1) if older else None,
        "recent_change": recent_change,
        "quarterly_trend": quarterly_trend,
        "on_time_rate_pct": round(100 * sum(1 for x in delays if x <= 0) / len(delays)),
        "worst_delay_days": max(delays),
        "pays_in_instalments": split >= HISTORY_WINDOW // 2,
        "avg_days_late_by_quarter": {k: round(mean(v), 1) for k, v in sorted(by_q.items())},
        "recent_invoices": [{"invoice_id": h["invoice_id"], "due": h["due_date"].isoformat(),
                             "days_late": h["final_delay"]} for h in hist[:4]],
        "open_invoices": [{"invoice_id": o["invoice_id"], "due": _d(o["due_date"]).isoformat(),
                           "outstanding": o["outstanding"], "status": o["status"]} for o in open_inv],
    }


# ------------------------------------------------------------------ cash events
def _recurring_expenses(start: date, end: date) -> list[dict]:
    """Project monthly expenses (rent, salaries, drawings...) from the last 3 months."""
    since = start - timedelta(days=95)
    rows = _rows("SELECT date, category, amount, recurring FROM expenses "
                 "WHERE date > :s AND recurring IN ('Monthly', 'Variable')", s=since)
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    events = []
    for cat, rs in by_cat.items():
        amt = round(mean(r["amount"] for r in rs))
        if cat == "Salaries":
            days = ["last_working"]
        else:
            days = sorted({_d(r["date"]).day for r in rs if _d(r["date"]) >= since + timedelta(days=60)}
                          or {_d(rs[-1]["date"]).day})
        y, m = start.year, start.month
        while date(y, m, 1) <= end:
            for day in days:
                if day == "last_working":
                    dt = date(y, m, calendar.monthrange(y, m)[1])
                    while dt.weekday() == 6:
                        dt -= timedelta(days=1)
                else:
                    dt = date(y, m, min(day, calendar.monthrange(y, m)[1]))
                if start < dt <= end:
                    events.append({"date": dt, "amount": -amt, "kind": "expense",
                                   "label": f"{cat} (usual monthly)", "ref": cat})
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return events


def _open_bills(start: date, end: date, changes: list[dict]) -> list[dict]:
    sup = suppliers()
    events = []
    for b in _rows("SELECT * FROM supplier_bills WHERE status != 'Paid'"):
        due = _d(b["due_date"])
        parts = [(due, int(b["amount"]))]
        for ch in changes:
            if ch.get("bill_id") == b["bill_id"]:
                if ch["type"] == "pay_bill_on":
                    parts = [(_d(ch["date"]), int(b["amount"]))]
                elif ch["type"] == "extend_bill":
                    parts = [(due + timedelta(days=int(ch["days"])), int(b["amount"]))]
                elif ch["type"] == "split_bill":   # part-payment now, rest later
                    now = min(int(ch["amount"]), int(b["amount"]))
                    parts = [(_d(ch.get("date") or due), now),
                             (_d(ch["rest_date"]), int(b["amount"]) - now)]
        name = sup[b["supplier_id"]]["name"]
        for i, (dt, amt) in enumerate(parts):
            pay_day = max(dt, start + timedelta(days=1))
            if pay_day <= end and amt:
                label = f"{name} {b['bill_id']}" + (f" part {i + 1}" if len(parts) > 1 else "")
                events.append({"date": pay_day, "amount": -amt, "kind": "bill",
                               "label": f"{label} (due {due.isoformat()})", "ref": b["bill_id"]})
    return events


def _invoice_schedule(inv: dict, hist: list[dict], start: date, q: float, extra_delay: int) -> tuple[list, str]:
    """When (and how much) of an open invoice arrives under quantile q."""
    due = _d(inv["due_date"]) + timedelta(days=extra_delay)
    elapsed = (start - due).days
    outstanding = int(inv["outstanding"])
    recent = hist[:HISTORY_WINDOW]
    # Only past behaviour consistent with "not paid yet" is relevant (conditioning).
    cands = sorted((h for h in recent if h["final_delay"] > elapsed), key=lambda h: h["final_delay"])
    if not recent:
        lag = {0.2: 0, 0.5: 3, 0.9: 15}[q]
        return [(max(due + timedelta(days=lag), start + timedelta(days=1)), outstanding)], \
            "no history: assumed on time to 15 days late"
    if not cands:
        lag = {0.2: 2, 0.5: 5, 0.9: 14}[q]
        return [(start + timedelta(days=lag), outstanding)], \
            "already later than any recent payment: assumed 2-14 more days"
    h = _quantile(cands, q)
    received = int(inv["amount_received"] or 0)
    if received and len(h["parts"]) > 1:      # part-paid: only the remaining instalment(s)
        parts = h["parts"][1:]
    else:
        parts = h["parts"]
    total_frac = sum(f for _, f in parts)
    sched = []
    for delay, frac in parts:
        dt = max(due + timedelta(days=delay), start + timedelta(days=1))
        sched.append((dt, round(outstanding * frac / total_frac)))
    basis = f"like {h['invoice_id']} ({h['final_delay']} days late), from {len(recent)} recent invoices"
    return sched, basis


def _open_invoices():
    return _rows("SELECT * FROM invoices WHERE status != 'Paid' ORDER BY due_date")


# ------------------------------------------------------------------ main forecast
def forecast(horizon_days: int = 21, target_date: str | None = None, changes: list[dict] | None = None,
             use_history: bool = True) -> dict:
    """Day-by-day cash for best / likely / worst cases.

    use_history=False gives the naive "dashboard" view: every invoice paid exactly on its due date.
    changes: list of what-if changes (see simulate()).
    """
    changes = changes or []
    start = as_of_date()
    end = start + timedelta(days=horizon_days)
    target = _d(target_date) if target_date else None
    if target and target > end:
        end = target
    opening = cash_on(start)
    cust = customers()

    outflows = _open_bills(start, end, changes) + _recurring_expenses(start, end)
    for ch in changes:
        if ch["type"] == "add_payment":
            outflows.append({"date": _d(ch["date"]), "amount": -int(ch["amount"]), "kind": "what-if",
                             "label": ch.get("label", "extra payment"), "ref": "what-if"})

    collect_pct = 1.0
    for ch in changes:
        if ch["type"] == "collections_change":
            collect_pct *= 1 + float(ch["pct"]) / 100

    hist_cache = {}
    scenarios, outlook = {}, {}
    names = list(SCENARIOS) if use_history else ["dashboard"]
    for name in names:
        q = SCENARIOS.get(name, 0.5)
        inflows = []
        for inv in _open_invoices():
            cid = inv["customer_id"]
            extra = sum(int(c["days"]) for c in changes
                        if c["type"] == "delay_customer" and c.get("customer_id") == cid)
            if use_history:
                if cid not in hist_cache:
                    hist_cache[cid] = payment_history(cid)
                sched, basis = _invoice_schedule(inv, hist_cache[cid], start, q, extra)
            else:
                dt = max(_d(inv["due_date"]) + timedelta(days=extra), start + timedelta(days=1))
                sched, basis = [(dt, int(inv["outstanding"]))], "assumed paid on due date"
            for ch in changes:   # "this customer pays (e.g. after a call) on this date"
                if (ch["type"] == "customer_pays_on" and ch.get("customer_id") == cid
                        and (ch.get("invoice_id") in (None, "", inv["invoice_id"]))
                        and _d(inv["due_date"]) <= _d(ch["date"]) + timedelta(days=7)):
                    sched = [(max(_d(ch["date"]), start + timedelta(days=1)), int(inv["outstanding"]))]
                    basis = f"what-if: paid on {ch['date']}"
            for dt, amt in sched:
                amt = round(amt * collect_pct)
                if dt <= end and amt:
                    inflows.append({"date": dt, "amount": amt, "kind": "collection",
                                    "label": f"{cust[cid]['name']} {inv['invoice_id']}", "ref": inv["invoice_id"]})
            if name in ("likely", "dashboard"):
                outlook[inv["invoice_id"]] = {
                    "invoice_id": inv["invoice_id"], "customer": cust[cid]["name"],
                    "outstanding": int(inv["outstanding"]), "due": _d(inv["due_date"]).isoformat(),
                    "expected_date": sched[-1][0].isoformat(), "basis": basis}
        events = sorted(inflows + outflows, key=lambda e: (e["date"], e["amount"] < 0))
        bal, daily, lowest = opening, [], (start, opening)
        by_day = defaultdict(int)
        for e in events:
            by_day[e["date"]] += e["amount"]
        day = start
        while day <= end:
            bal += by_day.get(day, 0) if day > start else 0
            daily.append({"date": day.isoformat(), "balance": bal})
            if bal < lowest[1]:
                lowest = (day, bal)
            day += timedelta(days=1)
        res = {"lowest_balance": lowest[1], "lowest_date": lowest[0].isoformat(),
               "end_balance": bal, "daily": daily,
               "events": [{**e, "date": e["date"].isoformat()} for e in events]}
        if target:
            res["balance_on_target"] = next(x["balance"] for x in daily if x["date"] == target.isoformat())
        scenarios[name] = res

    # probability that each invoice arrives by the target date (or horizon end)
    by_date = target or end
    if use_history:
        for inv in _open_invoices():
            hist = hist_cache.get(inv["customer_id"]) or payment_history(inv["customer_id"])
            due = _d(inv["due_date"])
            elapsed = (start - due).days
            cands = [h for h in hist[:HISTORY_WINDOW] if h["final_delay"] > elapsed]
            if inv["invoice_id"] in outlook:
                p = (sum(1 for h in cands if due + timedelta(days=h["final_delay"]) <= by_date) / len(cands)
                     if cands else None)
                outlook[inv["invoice_id"]]["chance_paid_in_full_by_" + by_date.isoformat()] = \
                    None if p is None else round(p * 100)

    return {
        "as_of": start.isoformat(),
        "horizon_end": end.isoformat(),
        "target_date": target.isoformat() if target else None,
        "opening_cash": opening,
        "mode": "history-based" if use_history else "naive (all invoices on due date)",
        "scenarios": scenarios,
        "invoice_outlook": sorted(outlook.values(), key=lambda x: x["due"]),
        "changes_applied": changes,
        "assumptions": [
            "Collections timed from each customer's last 8 paid invoices (best=20th, likely=50th, worst=90th percentile)"
            if use_history else "Every open invoice is paid in full on its due date",
            "Supplier bills paid on their due dates unless a change says otherwise",
            "Monthly expenses (rent, salaries, owner drawings, utilities) repeat at last 3 months' average",
            "New sales made from today are not collected inside this window (30-45 day terms)",
        ],
    }


def summarize(fc: dict, max_events: int = 25) -> dict:
    """Compact version of a forecast for the LLM (no daily arrays)."""
    out = {k: fc[k] for k in ("as_of", "horizon_end", "target_date", "opening_cash", "mode",
                              "assumptions", "changes_applied")}
    out["scenarios"] = {}
    for name, s in fc["scenarios"].items():
        out["scenarios"][name] = {k: v for k, v in s.items() if k not in ("daily", "events")}
    key = "likely" if "likely" in fc["scenarios"] else "dashboard"
    out[f"{key}_cash_events"] = [
        {"date": e["date"], "amount": e["amount"], "what": e["label"]}
        for e in fc["scenarios"][key]["events"][:max_events]]
    out["invoice_outlook"] = fc["invoice_outlook"]
    return out


# ------------------------------------------------------------------ what-if
def simulate(changes: list[dict], horizon_days: int = 30, target_date: str | None = None) -> dict:
    """Compare baseline vs. a scenario with changes. Supported changes:
       {"type": "delay_customer", "customer_id": "C001", "days": 15}
       {"type": "pay_bill_on", "bill_id": "BILL-586", "date": "2026-11-06"}
       {"type": "extend_bill", "bill_id": "BILL-586", "days": 30}
       {"type": "collections_change", "pct": -20}
       {"type": "add_payment", "date": "2026-11-10", "amount": 200000, "label": "..."}
       {"type": "split_bill", "bill_id": "BILL-586", "amount": 1000000, "date": "2026-11-13", "rest_date": "2026-11-27"}
       {"type": "customer_pays_on", "customer_id": "C001", "date": "2026-11-09", "invoice_id": optional}
    """
    base = forecast(horizon_days, target_date)
    new = forecast(horizon_days, target_date, changes=changes)
    comp = {}
    for name in SCENARIOS:
        b, n = base["scenarios"][name], new["scenarios"][name]
        comp[name] = {
            "lowest_before": b["lowest_balance"], "lowest_after": n["lowest_balance"],
            "lowest_date_after": n["lowest_date"],
            "end_before": b["end_balance"], "end_after": n["end_balance"],
            "change_in_lowest": n["lowest_balance"] - b["lowest_balance"],
        }
        if target_date:
            comp[name]["target_before"] = b["balance_on_target"]
            comp[name]["target_after"] = n["balance_on_target"]
    return {"as_of": base["as_of"], "changes": changes, "comparison": comp,
            "assumptions": new["assumptions"]}
