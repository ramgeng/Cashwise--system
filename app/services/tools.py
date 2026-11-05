"""Tools the LLM can call. Every number comes from the Forecaster (Python), never the LLM."""
from __future__ import annotations

from app.core.money import inr
from app.services import insights
from app.services.forecast import Forecaster
from app.services.memory import MemoryService


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


class ToolBox:
    def __init__(self, fc: Forecaster, memory: MemoryService | None):
        self.fc, self.b, self.memory = fc, fc.b, memory

    def normalize_change(self, ch: dict) -> dict:
        """Accept names ('Mehta', 'Vertex') as well as ids, and fill in sensible defaults."""
        ch = dict(ch)
        if "type" not in ch:
            raise ValueError("Each change needs a type")
        if ch.get("customer") and not ch.get("customer_id"):
            cid = self.b.find_customer(ch["customer"])
            if not cid:
                raise ValueError(f"Unknown customer '{ch['customer']}'")
            ch["customer_id"] = cid
        if ch["type"] in ("pay_bill_on", "extend_bill", "split_bill") and not ch.get("bill_id"):
            sid = self.b.find_supplier(ch.get("supplier", ""))
            if not sid:
                raise ValueError(f"Need a bill_id or a known supplier for {ch['type']}")
            bills = self.b.rows("SELECT bill_id FROM supplier_bills WHERE supplier_id = :s AND status != 'Paid' "
                                "ORDER BY due_date LIMIT 1", s=sid)
            if not bills:
                raise ValueError(f"No open bill for supplier '{ch['supplier']}'")
            ch["bill_id"] = bills[0]["bill_id"]
        if ch["type"] == "pay_bill_on" and not ch.get("date"):
            ch["date"] = self.b.as_of_date().isoformat()
        if ch["type"] == "split_bill" and not ch.get("rest_date"):
            raise ValueError("split_bill needs rest_date (when the rest is paid)")
        return ch

    def cash_forecast(self, horizon_days=21, target_date=None, use_history=True):
        s = Forecaster.summarize(self.fc.forecast(int(horizon_days or 21), target_date, use_history=use_history))
        s["opening_cash_text"] = inr(s["opening_cash"])
        s["scenarios"] = {k: _add_text(v) for k, v in s["scenarios"].items()}
        for o in s["invoice_outlook"]:
            o["outstanding_text"] = inr(o["outstanding"])
        return s

    def what_if(self, changes, target_date=None, horizon_days=30):
        norm = [self.normalize_change(c) for c in changes or []]
        res = self.fc.simulate(norm, int(horizon_days or 30), target_date)
        res["comparison"] = {k: _add_text(v) for k, v in res["comparison"].items()}
        return res

    def customer_profile(self, customer):
        cid = self.b.find_customer(customer)
        if not cid:
            return {"error": f"No customer matches '{customer}'",
                    "customers": [c["name"] for c in self.b.customers().values()]}
        p = self.fc.customer_profile(cid)
        for o in p.get("open_invoices", []):
            o["outstanding_text"] = inr(o["outstanding"])
        return p

    def run(self, name: str, args: dict, use_memory: bool = True):
        if name == "cash_forecast":
            return self.cash_forecast(args.get("horizon_days"), args.get("target_date"), use_history=use_memory)
        if name == "what_if" and use_memory:
            return self.what_if(args.get("changes", []), args.get("target_date"), args.get("horizon_days"))
        if name == "customer_profile" and use_memory:
            return self.customer_profile(args.get("customer", ""))
        if name == "upcoming_bills":
            return insights.upcoming_bills(self.fc, args.get("days") or 30)
        if name == "recall_memory" and use_memory and self.memory is not None:
            return {"memories": self.memory.recall(args.get("query", ""))[:8]}
        return {"error": f"Tool '{name}' is not available"}
