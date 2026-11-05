"""Smart alerts, worked out from the books and the forecast (no LLM, so every number is checkable).

Three groups:
- expense:  unusual expenses (much bigger than that category's usual amount, new categories, big one-offs,
            and a month that is running well above the usual total)
- cash:     low cash balance warnings (likely or worst case going below zero or below your safety buffer)
- risk:     potential cash-flow risks (a short key bill, invoices unlikely to arrive in time, customers
            paying slower, money stuck overdue, too much owed by one customer, negative net cash flow,
            supplier bills already late)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from app.core.money import as_date, inr
from app.services.forecast import Forecaster
from app.services.insights import key_bill

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

# An expense is unusual when it is at least this much bigger than that category's usual amount...
SPIKE_RATIO = 1.4
# ...and the difference is worth mentioning.
SPIKE_MIN = 5000
# A new category, or a one-off, is worth mentioning from this amount.
ONE_OFF_MIN = 25000
LOOKBACK_DAYS = 45


def _alert(group: str, severity: str, kind: str, title: str, detail: str, *, amount: int | None = None,
           when: str | None = None, view: str | None = None, who: str | None = None) -> dict:
    return {"id": f"{group}:{kind}:{who or ''}:{when or ''}", "group": group, "severity": severity, "kind": kind,
            "title": title, "detail": detail, "amount": amount, "date": when, "view": view, "who": who}


# ------------------------------------------------------------------ unusual expenses
def expense_alerts(fc: Forecaster) -> list[dict]:
    b = fc.b
    today = b.as_of_date()
    rows = b.rows("SELECT date, category, amount, vendor, recurring FROM expenses ORDER BY date")
    out: list[dict] = []
    history: dict[str, list[int]] = defaultdict(list)
    recent_from = today - timedelta(days=LOOKBACK_DAYS)

    for e in rows:
        d, cat, amt = as_date(e["date"]), e["category"], int(e["amount"])
        before = history[cat]
        if recent_from < d <= today:
            vendor = f" to {e['vendor']}" if e.get("vendor") else ""
            if len(before) >= 3:
                usual = int(median(before[-6:]))
                if usual > 0 and amt >= usual * SPIKE_RATIO and amt - usual >= SPIKE_MIN:
                    times = amt / usual
                    out.append(_alert(
                        "expense", "warning" if times < 2 else "critical", "spike",
                        f"{cat} is {times:.1f}× its usual amount",
                        f"{inr(amt)} paid{vendor} on {d:%d %b}; it is usually about {inr(usual)}.",
                        amount=amt, when=d.isoformat(), view="data", who=cat))
            elif not before and amt >= ONE_OFF_MIN:
                yearly = (e.get("recurring") or "").lower() == "yearly"
                out.append(_alert(
                    "expense", "info" if yearly else "warning", "new",
                    f"{'Yearly' if yearly else 'New'} expense: {cat}",
                    f"{inr(amt)} paid{vendor} on {d:%d %b}. "
                    + ("It comes once a year, so make room for it next year too." if yearly
                       else "There's nothing like it in your earlier expenses. Check it was expected."),
                    amount=amt, when=d.isoformat(), view="data", who=cat))
        history[cat].append(amt)

    # this month (so far, scaled to a full month) against the average of the three months before it
    by_month: dict[str, int] = defaultdict(int)
    for e in rows:
        d = as_date(e["date"])
        if d <= today:
            by_month[d.strftime("%Y-%m")] += int(e["amount"])
    this = today.strftime("%Y-%m")
    prev = sorted(m for m in by_month if m < this)[-3:]
    if len(prev) >= 2:
        usual = sum(by_month[m] for m in prev) / len(prev)
        last = prev[-1]
        # the most recent full month is the fairest comparison
        if usual and by_month[last] >= usual * 1.25 and by_month[last] - usual >= SPIKE_MIN * 4:
            pct = round((by_month[last] / usual - 1) * 100)
            month_name = date.fromisoformat(last + "-01").strftime("%B")
            out.append(_alert(
                "expense", "warning", "month",
                f"Spending in {month_name} was {pct}% above normal",
                f"{inr(by_month[last])} in expenses, against a usual {inr(int(usual))} a month.",
                amount=by_month[last], when=last + "-01", view="data", who=last))
    return out


# ------------------------------------------------------------------ low cash
def low_cash_threshold(fc: Forecaster) -> tuple[int, str]:
    """The safety buffer: what the owner set, or about two weeks of running costs."""
    prof = fc.b.profile()
    if prof.get("low_cash_threshold") not in (None, ""):
        return int(float(prof["low_cash_threshold"])), "set by you"
    today = fc.b.as_of_date()
    spend = fc.b.rows("SELECT amount FROM expenses WHERE date > :since AND date <= :today",
                      since=(today - timedelta(days=90)).isoformat(), today=today.isoformat())
    monthly = sum(int(e["amount"]) for e in spend) / 3 if spend else 0
    return int(round(monthly / 2 / 10000) * 10000), "about two weeks of running costs"


def _first(daily: list[dict], test) -> dict | None:
    return next((d for d in daily if test(d["balance"])), None)


def cash_alerts(fc: Forecaster, smart: dict, horizon_days: int) -> list[dict]:
    today = fc.b.as_of_date()
    buffer, basis = low_cash_threshold(fc)
    likely, worst = smart["scenarios"]["likely"], smart["scenarios"]["worst"]
    out: list[dict] = []
    cash = fc.b.cash_on(today)

    if cash < 0:
        out.append(_alert("cash", "critical", "overdrawn", "Your bank balance is below zero today",
                          f"You're {inr(-cash)} overdrawn.", amount=cash, when=today.isoformat(), view="forecast"))
    elif buffer and cash < buffer:
        out.append(_alert("cash", "warning", "low_now", "Cash is below your safety buffer today",
                          f"{inr(cash)} in the bank, under your {inr(buffer)} buffer ({basis}).",
                          amount=cash, when=today.isoformat(), view="forecast"))

    neg = _first(likely["daily"], lambda v: v < 0)
    if neg:
        days = (as_date(neg["date"]) - today).days
        out.append(_alert(
            "cash", "critical", "likely_negative",
            f"Cash likely runs out on {as_date(neg['date']):%a %d %b}",
            f"In {days} days, at how your customers really pay. The lowest point is "
            f"{inr(likely['lowest_balance'])} on {as_date(likely['lowest_date']):%d %b}.",
            amount=likely["lowest_balance"], when=neg["date"], view="forecast"))
    else:
        low = _first(likely["daily"], lambda v: buffer and v < buffer)
        if low:
            out.append(_alert(
                "cash", "warning", "likely_low",
                f"Cash likely drops below your buffer on {as_date(low['date']):%a %d %b}",
                f"The likely low is {inr(likely['lowest_balance'])} on {as_date(likely['lowest_date']):%d %b}, "
                f"under your {inr(buffer)} buffer ({basis}).",
                amount=likely["lowest_balance"], when=low["date"], view="forecast"))

    wneg = _first(worst["daily"], lambda v: v < 0)
    if wneg and not neg:
        out.append(_alert(
            "cash", "warning", "worst_negative",
            f"In the worst case, cash runs out on {as_date(wneg['date']):%a %d %b}",
            f"If the slowest payers are as late as they've ever been, the balance reaches "
            f"{inr(worst['lowest_balance'])}.",
            amount=worst["lowest_balance"], when=wneg["date"], view="forecast"))

    if not out:
        out.append(_alert(
            "cash", "info", "ok", f"Cash stays above your buffer for the next {horizon_days} days",
            f"The likely low is {inr(likely['lowest_balance'])} on {as_date(likely['lowest_date']):%d %b}; "
            f"your buffer is {inr(buffer)} ({basis}).",
            amount=likely["lowest_balance"], when=likely["lowest_date"], view="forecast"))
    return out


# ------------------------------------------------------------------ cash-flow risks
def risk_alerts(fc: Forecaster, smart: dict, horizon_days: int, key: dict | None) -> list[dict]:
    b = fc.b
    today = b.as_of_date()
    out: list[dict] = []
    likely = smart["scenarios"]["likely"]

    if key and likely.get("balance_on_target") is not None and likely["balance_on_target"] < 0:
        short = -likely["balance_on_target"]
        out.append(_alert(
            "risk", "critical", "key_bill",
            f"Likely {inr(short)} short for {key['supplier']} on {as_date(key['due']):%d %b}",
            f"The {inr(key['amount'])} bill is due before enough customer money is likely to arrive. "
            "See This week for what to do.", amount=-short, when=key["due"], view="overview", who=key["supplier"]))

    # invoices that are unlikely to arrive before the key bill
    by_date = smart.get("target_date") or smart["horizon_end"]
    chance_key = f"chance_paid_in_full_by_{by_date}"
    risky: dict[str, dict] = {}
    for o in smart["invoice_outlook"]:
        p = o.get(chance_key)
        if p is None or p >= 60 or o["due"] > by_date:
            continue
        r = risky.setdefault(o["customer"], {"amount": 0, "ids": [], "best": 0})
        r["amount"] += o["outstanding"]; r["ids"].append(o["invoice_id"]); r["best"] = max(r["best"], p)
    for name, r in sorted(risky.items(), key=lambda x: -x[1]["amount"])[:3]:
        out.append(_alert(
            "risk", "warning", "late_invoice",
            f"{name}: {inr(r['amount'])} may not arrive by {as_date(by_date):%d %b}",
            f"{', '.join(r['ids'])} {'is' if len(r['ids']) == 1 else 'are'} due by then, but going by how they "
            + (f"usually pay, it's unlikely to be paid in full in time." if r["best"] < 10 else
               f"usually pay, there's at best a {r['best']}% chance of it being paid in full in time."),
            amount=r["amount"], when=by_date, view="customers", who=name))

    customers = b.customers()
    open_by: dict[str, int] = defaultdict(int)
    overdue_by: dict[str, int] = defaultdict(int)
    for i in b.rows("SELECT customer_id, due_date, outstanding FROM invoices WHERE status != 'Paid' AND outstanding > 0"):
        open_by[i["customer_id"]] += int(i["outstanding"])
        if as_date(i["due_date"]) < today - timedelta(days=30):
            overdue_by[i["customer_id"]] += int(i["outstanding"])

    # customers paying slower lately
    for cid in customers:
        p = fc.customer_profile(cid)
        recent, before = p.get("avg_days_late_last_4"), p.get("avg_days_late_before_that")
        if recent is None or before is None or not open_by.get(cid):
            continue
        if recent - before >= 5 and recent >= 7:
            out.append(_alert(
                "risk", "warning", "slowing", f"{p['name']} is paying slower lately",
                f"About {round(recent)} days late on the last 4 invoices, up from {round(before)} before. "
                f"{inr(open_by[cid])} is still open.", amount=open_by[cid], view="customers", who=p["name"]))

    # money stuck more than 30 days overdue
    for cid, amt in sorted(overdue_by.items(), key=lambda x: -x[1])[:3]:
        name = customers.get(cid, {}).get("name", cid)
        out.append(_alert(
            "risk", "warning", "overdue_30", f"{inr(amt)} from {name} is over 30 days overdue",
            "The longer it waits, the less likely it is to come in full. Worth a firm call.",
            amount=amt, view="customers", who=name))

    # too much owed by one customer
    total = sum(open_by.values())
    if total and open_by:
        cid, amt = max(open_by.items(), key=lambda x: x[1])
        share = amt / total
        if share >= 0.35 and len(open_by) > 1:
            name = customers.get(cid, {}).get("name", cid)
            out.append(_alert(
                "risk", "info", "concentration", f"{round(share * 100)}% of what you're owed is from {name}",
                f"{inr(amt)} of {inr(total)}. If they pay late, it hits your cash hard.",
                amount=amt, view="customers", who=name))

    # net cash flow over the window
    net = sum(e["amount"] for e in likely["events"])
    if net < 0:
        cash_in = sum(e["amount"] for e in likely["events"] if e["amount"] > 0)
        cash_out = -sum(e["amount"] for e in likely["events"] if e["amount"] < 0)
        out.append(_alert(
            "risk", "warning" if likely["end_balance"] >= 0 else "critical", "net_negative",
            f"More money going out than coming in over the next {horizon_days} days",
            f"Likely {inr(cash_in)} in and {inr(cash_out)} out: net {inr(net)}.",
            amount=net, when=smart["horizon_end"], view="overview"))

    # supplier bills already late
    sup = b.suppliers()
    for x in b.rows("SELECT * FROM supplier_bills WHERE status != 'Paid'"):
        due = as_date(x["due_date"])
        if due < today:
            owed = int(x["outstanding"] or x["amount"])
            s = sup.get(x["supplier_id"], {})
            fee = s.get("late_fee_pct_per_month") or 0
            out.append(_alert(
                "risk", "warning", "bill_late", f"{s.get('name', x['supplier_id'])} bill is {(today - due).days} days late",
                f"{x['bill_id']}, {inr(owed)}." + (f" Late fee: {fee}% a month." if fee else ""),
                amount=owed, when=due.isoformat(), view="bills", who=s.get("name")))
    return out


# ------------------------------------------------------------------ all together
def smart_alerts(fc: Forecaster, horizon_days: int = 28) -> dict:
    key = key_bill(fc, horizon_days)
    smart = fc.forecast(horizon_days, key["due"] if key else None)
    smart["target_date"] = key["due"] if key else None
    alerts = expense_alerts(fc) + cash_alerts(fc, smart, horizon_days) + risk_alerts(fc, smart, horizon_days, key)
    alerts.sort(key=lambda a: (SEVERITY_ORDER[a["severity"]], a["group"], a["date"] or ""))
    buffer, basis = low_cash_threshold(fc)
    counts = {s: sum(a["severity"] == s for a in alerts) for s in SEVERITY_ORDER}
    groups = {g: sum(a["group"] == g for a in alerts) for g in ("expense", "cash", "risk")}
    return {"as_of": fc.b.as_of_date().isoformat(), "horizon_days": horizon_days,
            "low_cash_threshold": buffer, "low_cash_basis": basis,
            "counts": counts, "groups": groups, "alerts": alerts}
