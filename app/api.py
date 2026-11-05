"""Web API for the React app.

Run from the project root:   uvicorn app.api:app --reload
Then open http://localhost:8000 (after building the frontend) or run the
frontend dev server (npm run dev) which forwards /api calls here.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import forecast as fc
from app.config import BUSINESS_NAME, ROOT
from app.tools import inr, tool_upcoming_bills, tool_what_if

app = FastAPI(title="CashFlow Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_agents: dict[bool, object] = {}
_mem_client = None


def agent(use_memory: bool):
    """One agent per mode, created on first use (keeps chat history for the session)."""
    if use_memory not in _agents:
        from app.agent import CashAgent
        try:
            _agents[use_memory] = CashAgent(use_memory=use_memory)
        except SystemExit as e:  # missing keys in .env
            raise HTTPException(503, str(e))
    return _agents[use_memory]


def memory_client():
    global _mem_client
    if _mem_client is None:
        from app.memory import get_client
        try:
            _mem_client = get_client()
        except SystemExit as e:
            raise HTTPException(503, str(e))
    return _mem_client


# ------------------------------------------------------------------ read endpoints
@app.get("/api/business")
def business():
    rows = {r["field"]: r["value"] for r in fc._rows("SELECT * FROM business_profile")}
    return {"name": BUSINESS_NAME, "owner": rows.get("owner"), "city": rows.get("city"),
            "as_of": fc.as_of_date().isoformat(), "cash": fc.cash_on(fc.as_of_date()),
            "cash_text": inr(fc.cash_on(fc.as_of_date()))}


def _key_bill(horizon_days: int):
    """The biggest bill coming up: the natural 'can I pay this?' date for the headline."""
    start = fc.as_of_date()
    bills = [b for b in fc._rows("SELECT * FROM supplier_bills WHERE status != 'Paid'")
             if fc._d(b["due_date"]) <= start + timedelta(days=horizon_days)]
    if not bills:
        return None
    b = max(bills, key=lambda x: x["amount"])
    return {"bill_id": b["bill_id"], "supplier": fc.suppliers()[b["supplier_id"]]["name"],
            "due": fc._d(b["due_date"]).isoformat(), "amount": b["amount"], "amount_text": inr(b["amount"])}


@app.get("/api/forecast")
def forecast(horizon_days: int = 28, target_date: str | None = None):
    """Both views at once, so the UI can switch instantly between memory on and off."""
    key = _key_bill(horizon_days)
    target = target_date or (key["due"] if key else None)
    smart = fc.forecast(horizon_days, target)
    naive = fc.forecast(horizon_days, target, use_history=False)

    def pick(s):
        return {"lowest": s["lowest_balance"], "lowest_text": inr(s["lowest_balance"]),
                "lowest_date": s["lowest_date"], "on_target": s.get("balance_on_target"),
                "on_target_text": inr(s.get("balance_on_target"))}

    days = []
    for i, d in enumerate(smart["scenarios"]["likely"]["daily"]):
        trio = [smart["scenarios"][n]["daily"][i]["balance"] for n in ("best", "likely", "worst")]
        days.append({"date": d["date"],
                     # per-invoice percentiles can cross on a given day; the band shows the full range
                     "best": max(trio), "likely": d["balance"], "worst": min(trio),
                     "naive": naive["scenarios"]["dashboard"]["daily"][i]["balance"]})
    return {
        "as_of": smart["as_of"], "target_date": target, "key_bill": key,
        "opening_cash": smart["opening_cash"], "opening_cash_text": inr(smart["opening_cash"]),
        "days": days,
        "summary": {name: pick(s) for name, s in smart["scenarios"].items()} |
                   {"naive": pick(naive["scenarios"]["dashboard"])},
        "events": [e for e in smart["scenarios"]["likely"]["events"]],
        "naive_events": naive["scenarios"]["dashboard"]["events"],
        "invoice_outlook": smart["invoice_outlook"],
        "assumptions": smart["assumptions"],
    }


@app.get("/api/customers")
def customers():
    out = []
    for cid in fc.customers():
        p = fc.customer_profile(cid)
        p["open_total"] = sum(o["outstanding"] for o in p.get("open_invoices", []))
        p["open_total_text"] = inr(p["open_total"])
        out.append(p)
    return sorted(out, key=lambda x: -x["open_total"])


@app.get("/api/bills")
def bills(days: int = 45):
    return tool_upcoming_bills(days)


@app.get("/api/memories")
def memories(q: str = "important patterns, decisions and preferences for this business"):
    from app.memory import recall
    try:
        return {"query": q, "memories": recall(memory_client(), q)[:12]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Hindsight recall failed: {e}")


# ------------------------------------------------------------------ actions
class AskIn(BaseModel):
    question: str
    memory: bool = True


@app.post("/api/ask")
def ask(body: AskIn):
    if not body.question.strip():
        raise HTTPException(400, "Type a question first.")
    try:
        return agent(body.memory).ask(body.question.strip())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"The agent could not answer: {str(e)[:200]}")


class WhatIfIn(BaseModel):
    changes: list[dict]
    target_date: str | None = None
    horizon_days: int = 28


@app.post("/api/what-if")
def what_if(body: WhatIfIn):
    try:
        return tool_what_if(body.changes, body.target_date, body.horizon_days)
    except ValueError as e:
        raise HTTPException(400, str(e))


class FeedbackIn(BaseModel):
    text: str = ""
    helpful: bool | None = None
    question: str | None = None


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    verdict = "" if body.helpful is None else ("The owner found this advice useful. " if body.helpful
                                              else "The owner rejected this advice. ")
    about = f'About the question "{body.question}": ' if body.question else ""
    text = (about + verdict + body.text).strip()
    if not text:
        raise HTTPException(400, "Nothing to save.")
    agent(True).feedback(text)
    return {"saved": True}


class OutcomeIn(BaseModel):
    text: str


@app.post("/api/outcome")
def outcome(body: OutcomeIn):
    if not body.text.strip():
        raise HTTPException(400, "Describe what happened first.")
    agent(True).outcome(body.text.strip())
    return {"saved": True}


# ------------------------------------------------------------------ built frontend
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
