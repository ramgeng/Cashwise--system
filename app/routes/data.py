"""Bring your own records in: upload CSVs, download templates, load or clear demo data."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete

from app.core.errors import AppError
from app.core.money import inr
from app.db import tenant
from app.routes.deps import BusinessContext, current_business
from app.services import audit, demo, ingest

router = APIRouter(prefix="/api/data", tags=["data"])
log = logging.getLogger("cashwise.data")


def _owner(ctx: BusinessContext) -> None:
    if ctx.role != "owner":
        raise AppError(403, "Only the owner can change this business's data.", "forbidden")


def _names(ctx: BusinessContext) -> dict[str, str]:
    return {**{k: v["name"] for k, v in ctx.books.customers().items()},
            **{k: v["name"] for k, v in ctx.books.suppliers().items()}, "OWNER": "the owner"}


def _send_to_memory(ctx: BusinessContext, rows: list[dict]) -> str:
    try:
        n = ctx.memory.retain_events(rows, _names(ctx))
        return f"{n} events sent to memory. Hindsight takes a minute or two to process them."
    except AppError as e:
        return f"Saved, but not sent to memory: {e.detail}"
    except Exception as e:
        log.warning("memory upload failed: %s", e)
        return f"Saved, but sending to memory failed: {str(e)[:120]}"


@router.get("/types")
def types():
    """What can be uploaded, with the columns each file needs."""
    return ingest.describe()


@router.get("/status")
def status(ctx: BusinessContext = Depends(current_business)):
    return {"counts": ctx.books.counts(), "as_of": ctx.books.as_of_date().isoformat(),
            "opening_cash_balance": ctx.books.opening_balance()}


@router.get("/templates/{kind}", response_class=PlainTextResponse)
def template(kind: str):
    if kind not in ingest.SPECS:
        raise AppError(404, f"Unknown data type '{kind}'.", "unknown_kind")
    return PlainTextResponse(ingest.template_csv(kind), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{kind}_template.csv"'})


@router.post("/upload/{kind}")
async def upload(kind: str, file: UploadFile = File(...), mode: str = Form("replace"),
                 ctx: BusinessContext = Depends(current_business)):
    """Upload one CSV. Nothing is saved unless every row passes the checks."""
    _owner(ctx)
    content = await file.read()
    before = ctx.books.cash_on(ctx.books.as_of_date())
    res = ingest.import_file(ctx.books.engine, kind, content, mode, ctx.books.as_of_date())
    rows = res.pop("rows")
    audit.log(ctx.books.engine, audit.actor(ctx.user), "data.uploaded", "data",
              f"{ingest.SPECS[kind].label}: {res.get('rows_in_file', 0)} row(s), {mode} ({file.filename or 'file'}). "
              f"Cash today {inr(before)} → {inr(res['books']['cash_today'])}")
    if kind == "memory_events" and rows:
        res["memory"] = _send_to_memory(ctx, rows)
    return res


@router.delete("/{kind}")
def clear(kind: str, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    if kind not in ingest.SPECS:
        raise AppError(404, f"Unknown data type '{kind}'.", "unknown_kind")
    with ctx.books.engine.begin() as c:
        n = c.execute(delete(tenant.TABLES[ingest.SPECS[kind].table])).rowcount
    books = ingest.recompute(ctx.books.engine, ctx.books.as_of_date())
    audit.log(ctx.books.engine, audit.actor(ctx.user), "data.cleared", "data",
              f"{ingest.SPECS[kind].label}: {n} row(s) deleted. Cash today now {inr(books['cash_today'])}")
    return {"kind": kind, "deleted": n, "books": books}


@router.post("/demo")
def load_demo(ctx: BusinessContext = Depends(current_business)):
    """Replace this business's records with the Malabar Electronics demo data, and send its history to memory."""
    _owner(ctx)
    counts = demo.load(ctx.books.engine)
    audit.log(ctx.books.engine, audit.actor(ctx.user), "demo.loaded", "data",
              "All records replaced with the Malabar Electronics demo data")
    rows = ctx.books.rows("SELECT * FROM memory_events")
    return {"loaded": counts, "memory": _send_to_memory(ctx, rows)}


@router.post("/sync-memory")
def sync_memory(ctx: BusinessContext = Depends(current_business)):
    """Send (or re-send) all of this business's history events to its Hindsight bank."""
    _owner(ctx)
    rows = ctx.books.rows("SELECT * FROM memory_events")
    if not rows:
        raise AppError(400, "There is no history to send yet. Upload 'History for memory' first.", "no_history")
    return {"memory": _send_to_memory(ctx, rows)}
