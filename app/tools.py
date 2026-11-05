"""Tools the LLM can call. Every number comes from app.forecast (Python), never the LLM."""
from __future__ import annotations

from app import forecast as fc
from app.memory import recall


def inr(x) -> str:
    """Rs amount in Indian style: 'Rs 1.94 L' for lakhs, 'Rs 45,000' below that."""
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    return f"{sign}Rs {x / 100000:.2f} L" if x >= 100000 else f"{sign}Rs {x:,.0f}"


# ------------------------------------------------------------------ schemas (OpenAI/Groq format)
def _fn(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


CASH_FORECAST = _fn(
    "cash_forecast",
    "Day-by-day cash forecast with best / likely / worst scenarios based on how each customer "
    "really pays. Use for any question about future cash, shortfalls or whether a payment is affordable.",
    {"horizon_days": {"type": "integer", "description": "Days ahead to forecast (default 21)"},
     "target_date": {"type": "string", "description": "Optional YYYY-MM-DD date to report the balance on"}})

WHAT_IF = _fn(
    "what_if",
    "Compare the current forecast with a changed scenario. Change types: "
    "delay_customer {customer, days}; pay_bill_on {supplier or bill_id, date}; "
    "extend_bill {supplier or bill_id, days}; collections_change {pct, e.g. -20}; "
    "add_payment {date, amount, label}; split_bill {supplier or bill_id, amount paid now, date, rest_date}; "
    "customer_pays_on {customer, date, optional invoice_id} (e.g. if a collection call works).",
    {"changes": {"type": "array", "items": {"type": "object", "properties": {
        "type": {"type": "string", "enum": ["delay_customer", "pay_bill_on", "extend_bill",
                                             "collections_change", "add_payment", "split_bill",
                                             "customer_pays_on"]},
        "invoice_id": {"type": "string"}, "rest_date": {"type": "string"},
        "customer": {"type": "string"}, "supplier": {"type": "string"}, "bill_id": {"type": "string"},
        "days": {"type": "integer"}, "date": {"type": "string"}, "pct": {"type": "number"},
        "amount": {"type": "integer"}, "label": {"type": "string"}},
        "required": ["type"]}},
     "target_date": {"type": "string", "description": "Optional YYYY-MM-DD"},
     "horizon_days": {"type": "integer"}},
    ["changes"])

CUSTOMER_PROFILE = _fn(
    "customer_profile",
    "Payment behaviour of one customer from the records: median days late, trend, instalments, "
    "open invoices. Use as evidence before recommending collections.",
    {"customer": {"type": "string", "description": "Customer name or id, e.g. 'Mehta'"}},
    ["customer"])

UPCOMING_BILLS = _fn(
    "upcoming_bills",
    "Open supplier bills with due dates and each supplier's terms (early-pay discount, late fee).",
    {"days": {"type": "integer", "description": "Look-ahead in days (default 30)"}})

RECALL_MEMORY = _fn(
    "recall_memory",
    "Search the business's long-term memory: past collection attempts and what worked, disputes, "
    "supplier negotiations, past cash crunches, owner decisions and preferences, past recommendations.",
    {"query": {"type": "string"}}, ["query"])

MEMORY_TOOLS = [CASH_FORECAST, WHAT_IF, CUSTOMER_PROFILE, UPCOMING_BILLS, RECALL_MEMORY]
BASELINE_TOOLS = [CASH_FORECAST, UPCOMING_BILLS]   # "dashboard" mode: no history, no memory


# ------------------------------------------------------------------ implementations
def _add_text(d: dict) -> dict:
    """Add pre-formatted rupee strings so the LLM never converts numbers itself."""
    out = {}
    for k, v in d.items():
        out[k] = v
        if isinstance(v, int) and any(w in k for w in ("balance", "cash", "lowest", "end", "before",
                                                          "after", "outstanding", "amount", "target")):
            out[k + "_text"] = inr(v)
    return out


def tool_cash_forecast(horizon_days=21, target_date=None, use_history=True):
    s = fc.summarize(fc.forecast(int(horizon_days or 21), target_date, use_history=use_history))
    s["opening_cash_text"] = inr(s["opening_cash"])
    s["scenarios"] = {k: _add_text(v) for k, v in s["scenarios"].items()}
    for o in s["invoice_outlook"]:
        o["outstanding_text"] = inr(o["outstanding"])
    return s


def _normalize_change(ch: dict) -> dict:
    ch = dict(ch)
    if ch.get("customer") and not ch.get("customer_id"):
        cid = fc.find_customer(ch["customer"])
        if not cid:
            raise ValueError(f"Unknown customer '{ch['customer']}'")
        ch["customer_id"] = cid
    if ch["type"] in ("pay_bill_on", "extend_bill", "split_bill") and not ch.get("bill_id"):
        sid = fc.find_supplier(ch.get("supplier", ""))
        if not sid:
            raise ValueError(f"Need a bill_id or a known supplier for {ch['type']}")
        bills = fc._rows("SELECT bill_id FROM supplier_bills WHERE supplier_id = :s AND status != 'Paid' "
                         "ORDER BY due_date LIMIT 1", s=sid)
        if not bills:
            raise ValueError(f"No open bill for supplier '{ch['supplier']}'")
        ch["bill_id"] = bills[0]["bill_id"]
    if ch["type"] == "pay_bill_on" and not ch.get("date"):
        ch["date"] = fc.as_of_date().isoformat()
    return ch


def tool_what_if(changes, target_date=None, horizon_days=30):
    norm = [_normalize_change(c) for c in changes]
    res = fc.simulate(norm, int(horizon_days or 30), target_date)
    res["comparison"] = {k: _add_text(v) for k, v in res["comparison"].items()}
    return res


def tool_customer_profile(customer):
    cid = fc.find_customer(customer)
    if not cid:
        return {"error": f"No customer matches '{customer}'",
                "customers": [c["name"] for c in fc.customers().values()]}
    p = fc.customer_profile(cid)
    for o in p.get("open_invoices", []):
        o["outstanding_text"] = inr(o["outstanding"])
    return p


def tool_upcoming_bills(days=30):
    start = fc.as_of_date()
    sup = fc.suppliers()
    rows = fc._rows("SELECT * FROM supplier_bills WHERE status != 'Paid' ORDER BY due_date")
    out = []
    for b in rows:
        s = sup[b["supplier_id"]]
        due = fc._d(b["due_date"])
        if (due - start).days <= int(days or 30):
            out.append({"bill_id": b["bill_id"], "supplier": s["name"], "due": due.isoformat(),
                        "amount": b["amount"], "amount_text": inr(b["amount"]),
                        "early_pay_discount_pct": s["early_payment_discount_pct"],
                        "late_fee_pct_per_month": s["late_fee_pct_per_month"]})
    return {"as_of": start.isoformat(), "bills": out,
            "total_text": inr(sum(b["amount"] for b in out))}


def run_tool(name: str, args: dict, memory_client=None, use_memory=True):
    if name == "cash_forecast":
        return tool_cash_forecast(args.get("horizon_days"), args.get("target_date"), use_history=use_memory)
    if name == "what_if" and use_memory:
        return tool_what_if(args.get("changes", []), args.get("target_date"), args.get("horizon_days"))
    if name == "customer_profile" and use_memory:
        return tool_customer_profile(args.get("customer", ""))
    if name == "upcoming_bills":
        return tool_upcoming_bills(args.get("days"))
    if name == "recall_memory" and use_memory and memory_client is not None:
        return {"memories": recall(memory_client, args.get("query", ""))[:8]}
    return {"error": f"Tool '{name}' is not available"}
