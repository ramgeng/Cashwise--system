from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.errors import AppError
from app.core.money import inr
from app.db import tenant
from app.routes.deps import BusinessContext, current_business, current_user
from app.schemas import BusinessIn, BusinessUpdate
from app.services import accounts, audit, demo, ingest

router = APIRouter(prefix="/api", tags=["businesses"])


@router.get("/businesses")
def my_businesses(user: dict = Depends(current_user)):
    return accounts.list_businesses(user["id"])


@router.post("/businesses", status_code=201)
def add_business(body: BusinessIn, user: dict = Depends(current_user)):
    biz = accounts.create_business(user["id"], body.name, body.city, body.owner_name or user["name"], body.industry)
    if body.with_demo_data:
        demo.load(tenant.engine_for(biz["id"]))
    return accounts.public_business(biz, "owner")


def _business_view(ctx: BusinessContext) -> dict:
    b, books = ctx.business, ctx.books
    prof = books.profile()
    counts = books.counts()
    as_of = books.as_of_date()
    cash = books.cash_on(as_of)
    return {**accounts.public_business(b, ctx.role), "as_of": as_of.isoformat(),
            "as_of_fixed": bool(prof.get("as_of_date")), "cash": cash, "cash_text": inr(cash),
            "opening_cash_balance": books.opening_balance(), "opening_date": prof.get("opening_date"),
            "owner": b["owner_name"], "counts": counts,
            "has_data": counts["invoices"] > 0 or counts["supplier_bills"] > 0,
            "has_memory_history": counts["memory_events"] > 0,
            "low_cash_threshold": int(float(prof["low_cash_threshold"])) if prof.get("low_cash_threshold") else None,
            "bank_balance_set": {"amount": int(float(prof["bank_balance_amount"])), "date": prof["bank_balance_date"]}
            if prof.get("bank_balance_amount") not in (None, "") and prof.get("bank_balance_date") else None}


@router.get("/business")
def get_business(ctx: BusinessContext = Depends(current_business)):
    return _business_view(ctx)


@router.put("/business")
def update_business(body: BusinessUpdate, ctx: BusinessContext = Depends(current_business)):
    """Rename the business, or set the opening bank balance and the 'today' date used for forecasts."""
    if ctx.role != "owner":
        raise AppError(403, "Only the owner can change business settings.", "forbidden")
    eng, who = ctx.books.engine, audit.actor(ctx.user)
    before_cash = ctx.books.cash_on(ctx.books.as_of_date())
    before_biz = accounts.get_business(ctx.id)
    changed = [k for k in ("name", "city", "owner_name", "industry")
               if getattr(body, k) is not None and (getattr(body, k) or "").strip() != (before_biz.get(k) or "")]
    accounts.update_business(ctx.id, name=body.name, city=body.city, owner_name=body.owner_name, industry=body.industry)
    prof = {}
    if body.opening_cash_balance is not None:
        prof["opening_cash_balance"] = body.opening_cash_balance
    if body.opening_date is not None:
        prof["opening_date"] = body.opening_date.isoformat()
    if body.as_of_date is not None:
        prof["as_of_date"] = body.as_of_date.isoformat()
    if body.clear_as_of_date:
        prof["as_of_date"] = None
    if body.bank_balance is not None:
        on = body.bank_balance_date or ctx.books.as_of_date()
        if on > ctx.books.as_of_date():
            raise AppError(422, "The balance date can't be after today.", "invalid_date")
        prof["bank_balance_amount"] = body.bank_balance
        prof["bank_balance_date"] = on.isoformat()
    if body.clear_bank_balance:
        prof["bank_balance_amount"] = None
        prof["bank_balance_date"] = None
    alert_only = {}
    if body.low_cash_threshold is not None:
        alert_only["low_cash_threshold"] = body.low_cash_threshold
    if body.clear_low_cash_threshold:
        alert_only["low_cash_threshold"] = None
    if alert_only:          # only affects alerts, so no need to rebuild the ledger
        ctx.books.set_profile(alert_only)
    if prof:
        ctx.books.set_profile(prof)
        ingest.recompute(ctx.books.engine, ctx.books.as_of_date())
    ctx.business = accounts.get_business(ctx.id)
    view = _business_view(ctx)
    # the audit trail: important financial changes
    if body.bank_balance is not None:
        audit.log(eng, who, "balance.updated", "money",
                  f"Bank balance set to {inr(body.bank_balance)} for the end of "
                  f"{(body.bank_balance_date or ctx.books.as_of_date()).isoformat()} (was {inr(before_cash)})")
    if body.clear_bank_balance:
        audit.log(eng, who, "balance.reset", "money", f"Typed-in bank balance removed; now {inr(view['cash'])} from records")
    if body.opening_cash_balance is not None or body.opening_date is not None:
        audit.log(eng, who, "opening.changed", "money",
                  f"Opening balance {inr(view['opening_cash_balance'])} from {view['opening_date'] or 'the start'}")
    if body.low_cash_threshold is not None or body.clear_low_cash_threshold:
        audit.log(eng, who, "threshold.changed", "settings",
                  f"Low-cash buffer {inr(body.low_cash_threshold) if body.low_cash_threshold is not None else 'set back to automatic'}")
    if body.as_of_date is not None or body.clear_as_of_date:
        audit.log(eng, who, "today.changed", "settings", f"'Today' for forecasts set to {view['as_of']}")
    if changed:
        audit.log(eng, who, "business.changed", "settings", "Changed " + ", ".join(k.replace("_", " ") for k in changed))
    return view


@router.delete("/business", status_code=204)
def delete_business(ctx: BusinessContext = Depends(current_business)):
    """Delete the business, all its records, and its memory bank."""
    if ctx.role != "owner":
        raise AppError(403, "Only the owner can delete a business.", "forbidden")
    if ctx.business["is_demo"]:
        raise AppError(400, "The demo business can't be deleted. Reload its demo data instead.", "demo_protected")
    try:
        ctx.memory.delete_bank()
    except AppError:
        pass  # memory not configured: nothing to delete
    accounts.delete_business(ctx.id)
