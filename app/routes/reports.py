"""Reports: make, print, email, share, schedule and compare, with an audit trail of every step."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import AppError
from app.db import tenant
from app.routes.deps import BusinessContext, current_business
from app.schemas import EmailIn, RecipientsIn, ReportIn, ScheduleIn, ShareIn
from app.services import audit, mailer, reports, scheduler

router = APIRouter(prefix="/api", tags=["reports"])


def _eng(ctx: BusinessContext):
    return tenant.engine_for(ctx.id)


def _who(ctx: BusinessContext) -> str:
    return audit.actor(ctx.user)


def _owner(ctx: BusinessContext):
    if ctx.role != "owner":
        raise AppError(403, "Only the owner can change this.", "forbidden")


def _link(token: str) -> str:
    return f"{settings.app_url}/r/{token}"


# ------------------------------------------------------------------ make and look back
@router.get("/reports")
def history(ctx: BusinessContext = Depends(current_business)):
    """Every report made for this business, newest first."""
    return {"reports": reports.history(_eng(ctx)), "email_configured": settings.email_configured,
            "management": scheduler.management(_eng(ctx))}


@router.post("/reports", status_code=201)
def make(body: ReportIn, ctx: BusinessContext = Depends(current_business)):
    a = (body.a_from, body.a_to) if body.a_from and body.a_to else None
    b = (body.b_from, body.b_to) if body.b_from and body.b_to else None
    if body.kind == "comparison" and (a is None) != (b is None):
        raise AppError(422, "Give both periods, or neither for last month vs the month before.", "bad_period")
    rep = reports.create(_eng(ctx), ctx.forecaster, ctx.business, _who(ctx), body.kind, a=a, b=b, title=body.title)
    audit.log(_eng(ctx), _who(ctx), "report.generated", "report", f"{rep['title']} ({rep['report_id']})")
    return rep


@router.get("/reports/{report_id}")
def one(report_id: str, ctx: BusinessContext = Depends(current_business)):
    return reports.get(_eng(ctx), report_id)


@router.post("/reports/{report_id}/printed", status_code=204)
def printed(report_id: str, ctx: BusinessContext = Depends(current_business)):
    """The browser opened the print dialog for this report (for the audit trail)."""
    rep = reports.get(_eng(ctx), report_id)
    audit.log(_eng(ctx), _who(ctx), "report.printed", "report", f"{rep['title']} ({report_id})")


@router.delete("/reports/{report_id}")
def remove(report_id: str, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    rep = reports.delete(_eng(ctx), report_id)
    audit.log(_eng(ctx), _who(ctx), "report.deleted", "report", f"{rep['title']} ({report_id}); its links were turned off")
    return {"deleted": report_id}


# ------------------------------------------------------------------ email
@router.get("/reports-settings/recipients")
def get_recipients(ctx: BusinessContext = Depends(current_business)):
    return {"emails": scheduler.management(_eng(ctx)), "email_configured": settings.email_configured}


@router.put("/reports-settings/recipients")
def set_recipients(body: RecipientsIn, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    emails = mailer.clean_recipients(body.emails)
    ctx.books.set_profile({"report_recipients": ",".join(emails) or None})
    audit.log(_eng(ctx), _who(ctx), "recipients.changed", "settings",
              f"Management list: {', '.join(emails) if emails else '(empty)'}")
    return {"emails": emails, "email_configured": settings.email_configured}


@router.post("/reports/{report_id}/email")
async def email(report_id: str, body: EmailIn, ctx: BusinessContext = Depends(current_business)):
    """Send the report by email (mode=send), or get the text and a link to send it yourself (mode=draft)."""
    eng = _eng(ctx)
    rep = reports.get(eng, report_id)
    to = mailer.clean_recipients(list(body.to) + (scheduler.management(eng) if body.use_management else []))
    if body.mode == "send" and not settings.email_configured:
        raise AppError(503, "Email isn't set up on this server yet. Use 'Open in my email app' instead, "
                            "or add SMTP settings (see DEPLOY.md).", "email_not_configured")
    if not to and body.mode == "send":
        raise AppError(422, "Add at least one email address.", "no_recipients")
    share = reports.share(eng, ctx.id, report_id, _who(ctx), body.link_days)
    url = _link(share["token"])
    subject, text, html = mailer.compose(rep, url, body.note, ctx.user.get("name", ""))
    if body.mode == "draft":
        audit.log(eng, _who(ctx), "report.email_drafted", "report",
                  f"{rep['title']} for {', '.join(to) or 'your email app'}; read-only link made")
        return {"mode": "draft", "to": to, "subject": subject, "text": text, "link": url}
    await run_in_threadpool(mailer.send, to, subject, text, html)
    audit.log(eng, _who(ctx), "report.emailed", "report", f"{rep['title']} to {', '.join(to)}")
    return {"mode": "send", "sent_to": to, "link": url}


# ------------------------------------------------------------------ read-only links
@router.post("/reports/{report_id}/share", status_code=201)
def make_share(report_id: str, body: ShareIn, ctx: BusinessContext = Depends(current_business)):
    s = reports.share(_eng(ctx), ctx.id, report_id, _who(ctx), body.days)
    audit.log(_eng(ctx), _who(ctx), "share.created", "sharing",
              f"{s['title']}: read-only link, {'expires ' + s['expires_at'][:10] if s['expires_at'] else 'never expires'}")
    return {**s, "url": _link(s["token"])}


@router.get("/shares")
def list_shares(ctx: BusinessContext = Depends(current_business)):
    return {"shares": [{**s, "url": _link(s["token"])} for s in reports.shares(_eng(ctx))]}


@router.delete("/shares/{token}")
def revoke_share(token: str, ctx: BusinessContext = Depends(current_business)):
    if not token.startswith(f"{ctx.id}-"):
        raise AppError(404, "Link not found.", "share_not_found")
    s = reports.revoke(_eng(ctx), token)
    audit.log(_eng(ctx), _who(ctx), "share.revoked", "sharing", f"{s['title']}: link turned off after {s['views']} view(s)")
    return s


@router.get("/public/reports/{token}", tags=["public"])
def public_report(token: str):
    """Anyone with the link can read the report. No sign-in, read-only, nothing else in the business is visible."""
    bid, rep = reports.open_shared(token)
    audit.log(tenant.engine_for(bid), "Someone with the link", "share.viewed", "sharing", f"{rep['title']} was opened")
    return {"title": rep["title"], "kind": rep["kind"], "created_at": rep["created_at"], "data": rep["data"]}


# ------------------------------------------------------------------ schedules
@router.get("/schedules")
def list_schedules(ctx: BusinessContext = Depends(current_business)):
    return {"schedules": scheduler.list_for(_eng(ctx)), "email_configured": settings.email_configured,
            "timezone": settings.report_tz, "management": scheduler.management(_eng(ctx))}


@router.post("/schedules", status_code=201)
def add_schedule(body: ScheduleIn, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    s = scheduler.save(_eng(ctx), _who(ctx), body.model_dump())
    audit.log(_eng(ctx), _who(ctx), "schedule.created", "report", s["description"])
    return s


@router.put("/schedules/{sid}")
def edit_schedule(sid: int, body: ScheduleIn, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    s = scheduler.save(_eng(ctx), _who(ctx), body.model_dump(), sid)
    audit.log(_eng(ctx), _who(ctx), "schedule.updated", "report", f"{s['description']}{'' if s['active'] else ' (paused)'}")
    return s


@router.delete("/schedules/{sid}")
def delete_schedule(sid: int, ctx: BusinessContext = Depends(current_business)):
    _owner(ctx)
    s = scheduler.remove(_eng(ctx), sid)
    audit.log(_eng(ctx), _who(ctx), "schedule.deleted", "report", s["description"])
    return {"deleted": sid}


@router.post("/schedules/{sid}/run")
async def run_schedule(sid: int, ctx: BusinessContext = Depends(current_business)):
    """Make this schedule's report right now (it still runs at its normal time too)."""
    s = scheduler.get(_eng(ctx), sid)
    res = await run_in_threadpool(scheduler.run_one, ctx.business, s, f"{_who(ctx)}, via schedule")
    return {"status": res["status"], "report": {k: res["report"][k] for k in ("report_id", "title", "kind", "created_at")}}


# ------------------------------------------------------------------ audit trail
@router.get("/audit")
def audit_trail(category: str | None = Query(None, pattern="^(report|sharing|money|data|settings)$"),
                limit: int = Query(200, ge=1, le=1000), ctx: BusinessContext = Depends(current_business)):
    return {"entries": audit.entries(_eng(ctx), category, limit)}
