"""Dashboard read-outs built on the forecast: the key bill, this week's actions, the chart series."""
from __future__ import annotations

from datetime import timedelta
from math import ceil

from app.core.money import as_date, inr
from app.services.forecast import Forecaster


def key_bill(fc: Forecaster, horizon_days: int) -> dict | None:
    """The biggest unpaid bill in the window: the natural 'can I pay this?' date for the headline."""
    start = fc.b.as_of_date()
    bills = [b for b in fc.b.rows("SELECT * FROM supplier_bills WHERE status != 'Paid'")
             if as_date(b["due_date"]) <= start + timedelta(days=horizon_days)]
    if not bills:
        return None
    b = max(bills, key=lambda x: x["outstanding"] or x["amount"])
    amount = int(b["outstanding"] or b["amount"])
    sup = fc.b.suppliers().get(b["supplier_id"], {}).get("name", b["supplier_id"])
    return {"bill_id": b["bill_id"], "supplier": sup, "due": max(as_date(b["due_date"]), start).isoformat(),
            "amount": amount, "amount_text": inr(amount)}


def _pick(s: dict) -> dict:
    return {"lowest": s["lowest_balance"], "lowest_text": inr(s["lowest_balance"]), "lowest_date": s["lowest_date"],
            "on_target": s.get("balance_on_target"), "on_target_text": inr(s.get("balance_on_target"))}


def _flow(s: dict, opening: int) -> dict:
    """Net cash flow over the forecast window: what comes in, what goes out, and the difference."""
    cash_in = sum(e["amount"] for e in s["events"] if e["amount"] > 0)
    cash_out = -sum(e["amount"] for e in s["events"] if e["amount"] < 0)
    by_kind: dict[str, int] = {}
    for e in s["events"]:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + e["amount"]
    return {"in": cash_in, "out": cash_out, "net": cash_in - cash_out, "by_kind": by_kind,
            "opening": opening, "closing": s["end_balance"]}


def _series(scen: dict, naive: dict | None = None) -> list[dict]:
    days = []
    for i, d in enumerate(scen["likely"]["daily"]):
        trio = [scen[n]["daily"][i]["balance"] for n in ("best", "likely", "worst")]
        row = {"date": d["date"], "best": max(trio), "likely": d["balance"], "worst": min(trio)}
        if naive is not None:
            row["naive"] = naive["daily"][i]["balance"]
        days.append(row)
    return days


def dashboard_forecast(fc: Forecaster, horizon_days: int = 28, target_date: str | None = None) -> dict:
    """Both views at once (history-based and naive), so the UI can switch instantly."""
    key = key_bill(fc, horizon_days)
    target = target_date or (key["due"] if key else (fc.b.as_of_date() + timedelta(days=14)).isoformat())
    smart = fc.forecast(horizon_days, target)
    naive = fc.forecast(horizon_days, target, use_history=False)
    return {
        "as_of": smart["as_of"], "target_date": target, "key_bill": key,
        "opening_cash": smart["opening_cash"], "opening_cash_text": inr(smart["opening_cash"]),
        "days": _series(smart["scenarios"], naive["scenarios"]["dashboard"]),
        "summary": {name: _pick(s) for name, s in smart["scenarios"].items()} | {"naive": _pick(naive["scenarios"]["dashboard"])},
        "flow": {name: _flow(sc, smart["opening_cash"]) for name, sc in smart["scenarios"].items()}
                | {"naive": _flow(naive["scenarios"]["dashboard"], smart["opening_cash"])},
        "horizon_end": smart["horizon_end"], "horizon_days": horizon_days,
        "events": smart["scenarios"]["likely"]["events"],
        "naive_events": naive["scenarios"]["dashboard"]["events"],
        "invoice_outlook": smart["invoice_outlook"],
        "assumptions": smart["assumptions"],
    }


def scenario(fc: Forecaster, changes: list[dict], horizon_days: int = 28, target_date: str | None = None) -> dict:
    key = key_bill(fc, horizon_days)
    target = target_date or (key["due"] if key else (fc.b.as_of_date() + timedelta(days=14)).isoformat())
    s = fc.forecast(horizon_days, target, changes=changes)["scenarios"]
    return {"changes": changes, "days": _series(s), "target_date": target,
            "likely": {"on_target": s["likely"].get("balance_on_target"), "lowest": s["likely"]["lowest_balance"],
                       "lowest_date": s["likely"]["lowest_date"]}}


def this_week(fc: Forecaster, horizon_days: int = 28) -> dict:
    """A short to-do list worked out from the forecast (no LLM): what to negotiate, who to chase."""
    key = key_bill(fc, horizon_days)
    target = key["due"] if key else None
    smart = fc.forecast(horizon_days, target)
    likely = smart["scenarios"]["likely"]
    out = []

    short_by = -(likely.get("balance_on_target") or 0)
    if key and short_by > 0:
        hold_back = min(key["amount"], int(ceil((short_by + 100000) / 50000.0) * 50000))
        pay_now = key["amount"] - hold_back
        rest = (as_date(key["due"]) + timedelta(days=14)).isoformat()
        change = {"type": "split_bill", "bill_id": key["bill_id"], "amount": pay_now, "date": key["due"], "rest_date": rest}
        after = fc.forecast(horizon_days, target, changes=[change])["scenarios"]["likely"]["balance_on_target"]
        out.append({"kind": "negotiate", "who": key["supplier"], "amount": hold_back,
                    "title": f"Ask {key['supplier'].split(' ')[0]} to take {inr(pay_now)} on {as_date(key['due']):%d %b}",
                    "detail": f"Holding back {inr(hold_back)} for two weeks turns a likely {inr(short_by)} shortfall "
                              f"into {inr(after)} left on the day.",
                    "change": change})

    by_date = target or smart["horizon_end"]
    chance_key = f"chance_paid_in_full_by_{by_date}"
    risky: dict[str, dict] = {}
    for o in smart["invoice_outlook"]:
        p = o.get(chance_key)
        if p is None or p >= 70 or o["due"] > by_date:
            continue
        r = risky.setdefault(o["customer"], {"invoices": [], "amount": 0, "risk": 0, "best_chance": 0})
        r["invoices"].append(o["invoice_id"])
        r["amount"] += o["outstanding"]
        r["risk"] += o["outstanding"] * (100 - p)
        r["best_chance"] = max(r["best_chance"], p)
    for name, r in sorted(risky.items(), key=lambda x: -x[1]["risk"])[:2]:
        cid = fc.b.find_customer(name)
        prof = fc.customer_profile(cid) if cid else {}
        habit = (f"usually pays {prof['median_days_late']:.0f} days late" if (prof.get("median_days_late") or 0) > 0
                 else "usually pays on time")
        if prof.get("recent_change") == "slower lately":
            habit += " and slower lately"
        if prof.get("pays_in_instalments"):
            habit += ", in two halves"
        odds = ("none of their recent invoices were paid this fast" if r["best_chance"] == 0
                else f"at best a {r['best_chance']}% chance of arriving by {as_date(by_date):%d %b}")
        out.append({"kind": "chase", "who": name, "amount": r["amount"],
                    "title": f"Chase {name} for {inr(r['amount'])}",
                    "detail": f"{', '.join(r['invoices'])}: {habit}; {odds}.",
                    "change": {"type": "customer_pays_on", "customer_id": cid,
                               "date": (fc.b.as_of_date() + timedelta(days=3)).isoformat()}})
    return {"target_date": target, "likely_on_target": likely.get("balance_on_target"), "actions": out}


def customer_list(fc: Forecaster) -> list[dict]:
    out = []
    for cid in fc.b.customers():
        p = fc.customer_profile(cid)
        p["open_total"] = sum(o["outstanding"] for o in p.get("open_invoices", []))
        p["open_total_text"] = inr(p["open_total"])
        out.append(p)
    return sorted(out, key=lambda x: -x["open_total"])


LESSON_TYPES = {"decision", "preference", "extension_request", "late_payment_penalty", "dispute_resolved",
                "early_payment_discount", "capital_infusion", "customer_note", "feedback", "outcome"}


def timeline(fc: Forecaster) -> dict:
    """Everything the agent remembers, newest first: history plus what it learned while running."""
    b = fc.b
    names = {**{k: v["name"] for k, v in b.customers().items()},
             **{k: v["name"] for k, v in b.suppliers().items()}, "OWNER": "Owner", "RENT": "Landlord"}
    items = [{"date": as_date(e["date"]).isoformat(), "type": e["event_type"],
              "who": names.get(e["entity_id"], e["entity_id"]), "text": e["description"],
              "outcome": e["outcome"], "lesson": e["event_type"] in LESSON_TYPES, "live": False}
             for e in b.rows("SELECT * FROM memory_events ORDER BY date DESC")]
    items += [{"date": r["created_at"][:10], "type": r["kind"], "who": "Agent" if r["kind"] == "recommendation" else "Owner",
               "text": r["text"], "outcome": "", "lesson": r["kind"] != "recommendation", "live": True}
              for r in b.rows("SELECT * FROM agent_log ORDER BY log_id DESC")]
    items.sort(key=lambda x: (x["date"], x["live"]), reverse=True)
    return {"items": items, "counts": {"history": sum(not i["live"] for i in items),
                                       "learned_live": sum(i["live"] for i in items)}}


def upcoming_bills(fc: Forecaster, days: int = 30) -> dict:
    start = fc.b.as_of_date()
    sup = fc.b.suppliers()
    out = []
    for b in fc.b.rows("SELECT * FROM supplier_bills WHERE status != 'Paid' ORDER BY due_date"):
        s = sup.get(b["supplier_id"], {})
        due = as_date(b["due_date"])
        owed = int(b["outstanding"] or b["amount"])
        if (due - start).days <= int(days or 30):
            out.append({"bill_id": b["bill_id"], "supplier": s.get("name", b["supplier_id"]), "due": due.isoformat(),
                        "amount": owed, "amount_text": inr(owed), "status": b["status"],
                        "early_pay_discount_pct": s.get("early_payment_discount_pct") or 0,
                        "late_fee_pct_per_month": s.get("late_fee_pct_per_month") or 0})
    return {"as_of": start.isoformat(), "bills": out, "total": sum(b["amount"] for b in out),
            "total_text": inr(sum(b["amount"] for b in out))}


def position(fc: Forecaster) -> dict:
    """The overall financial position today: what you have, what you're owed, what you owe."""
    b = fc.b
    today = b.as_of_date()
    cash = b.cash_on(today)
    inv = b.rows("SELECT due_date, outstanding FROM invoices WHERE status != 'Paid' AND outstanding > 0")
    bills = b.rows("SELECT due_date, outstanding, amount FROM supplier_bills WHERE status != 'Paid'")
    receivable = sum(int(i["outstanding"]) for i in inv)
    receivable_overdue = sum(int(i["outstanding"]) for i in inv if as_date(i["due_date"]) < today)
    payable = sum(int(x["outstanding"] or x["amount"]) for x in bills)
    payable_overdue = sum(int(x["outstanding"] or x["amount"]) for x in bills if as_date(x["due_date"]) < today)
    payable_30 = sum(int(x["outstanding"] or x["amount"]) for x in bills
                     if as_date(x["due_date"]) <= today + timedelta(days=30))

    # what actually happened in the last 30 days, from the bank ledger
    since = (today - timedelta(days=30)).isoformat()
    moves = b.rows("SELECT amount FROM cash_ledger WHERE date > :since AND date <= :today",
                   since=since, today=today.isoformat())
    last_in = sum(int(m["amount"]) for m in moves if m["amount"] > 0)
    last_out = -sum(int(m["amount"]) for m in moves if m["amount"] < 0)

    # average monthly running costs over the last 90 days (rent, salaries, ...), for a simple runway
    spend = b.rows("SELECT amount FROM expenses WHERE date > :since AND date <= :today",
                   since=(today - timedelta(days=90)).isoformat(), today=today.isoformat())
    monthly_costs = int(sum(int(e["amount"]) for e in spend) / 3) if spend else 0

    net = cash + receivable - payable
    return {
        "as_of": today.isoformat(),
        "cash": cash, "receivable": receivable, "receivable_overdue": receivable_overdue,
        "payable": payable, "payable_overdue": payable_overdue, "payable_30": payable_30,
        "net_position": net,
        # (cash + money owed to you) for every rupee you owe; above 1 means you can cover what you owe
        "cover": round((cash + receivable) / payable, 2) if payable else None,
        "last_30": {"in": last_in, "out": last_out, "net": last_in - last_out},
        "monthly_costs": monthly_costs,
        "runway_months": round(cash / monthly_costs, 1) if monthly_costs else None,
    }
