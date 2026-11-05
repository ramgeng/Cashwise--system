"""Scheduled reports: weekly or monthly, generated in the background and emailed to management.

Runs inside the web server (checked every few minutes). If the server was asleep at the scheduled time
(e.g. Render's free plan), the report is made as soon as it wakes up, once, not once per missed run.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.errors import AppError
from app.db import platform, tenant
from app.services import audit, mailer, reports
from app.services.books import Books
from app.services.forecast import Forecaster

log = logging.getLogger("cashwise.scheduler")
CHECK_EVERY_SECONDS = 300
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.report_tz)
    except Exception:
        return ZoneInfo("UTC")


def next_run(frequency: str, weekday: int, day_of_month: int, hour: int, after: datetime) -> datetime:
    """The next run after `after` (naive UTC), at `hour` local time. Returns naive UTC."""
    tz = _tz()
    local = after.replace(tzinfo=timezone.utc).astimezone(tz)
    if frequency == "weekly":
        cand = local.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=(weekday - local.weekday()) % 7)
        if cand <= local:
            cand += timedelta(days=7)
    else:
        cand = local.replace(day=day_of_month, hour=hour, minute=0, second=0, microsecond=0)
        if cand <= local:
            y, m = (cand.year + (cand.month == 12), cand.month % 12 + 1)
            cand = cand.replace(year=y, month=m)
    return cand.astimezone(timezone.utc).replace(tzinfo=None)


def describe(s: dict) -> str:
    h = f"{s['hour']:02d}:00"
    what = "Cash-flow report" if s["kind"] == "summary" else "Comparison report"
    if s["frequency"] == "weekly":
        return f"{what}, every {WEEKDAYS[s['weekday']]} at {h}"
    return f"{what}, on day {s['day_of_month']} of each month at {h}"


def _public(r) -> dict:
    d = dict(r)
    for k in ("next_run", "last_run", "created_at"):
        d[k] = d[k].isoformat() + "Z" if d.get(k) else None
    d["recipients"] = [x for x in (r["recipients"] or "").split(",") if x]
    d["description"] = describe(d)
    return d


def list_for(eng: Engine) -> list[dict]:
    with eng.connect() as c:
        rows = c.execute(select(tenant.report_schedules).order_by(tenant.report_schedules.c.schedule_id)).mappings().all()
    return [_public(r) for r in rows]


def get(eng: Engine, sid: int) -> dict:
    with eng.connect() as c:
        r = c.execute(select(tenant.report_schedules).where(tenant.report_schedules.c.schedule_id == sid)).mappings().first()
    if not r:
        raise AppError(404, "Schedule not found.", "schedule_not_found")
    return _public(r)


def _validate(v: dict) -> dict:
    if v.get("frequency") not in ("weekly", "monthly"):
        raise AppError(422, "frequency must be weekly or monthly.", "bad_schedule")
    if v.get("kind") not in ("summary", "comparison"):
        raise AppError(422, "kind must be summary or comparison.", "bad_schedule")
    v["weekday"] = max(0, min(6, int(v.get("weekday") or 0)))
    v["day_of_month"] = max(1, min(28, int(v.get("day_of_month") or 1)))
    v["hour"] = max(0, min(23, int(v.get("hour") if v.get("hour") is not None else 9)))
    v["recipients"] = ",".join(mailer.clean_recipients(v.get("recipients") or []))
    return v


def save(eng: Engine, who: str, values: dict, sid: int | None = None) -> dict:
    v = _validate(dict(values))
    v["next_run"] = next_run(v["frequency"], v["weekday"], v["day_of_month"], v["hour"], audit.now())
    t = tenant.report_schedules
    cols = ("frequency", "weekday", "day_of_month", "hour", "kind", "recipients", "active", "next_run")
    data = {k: v[k] for k in cols if k in v}
    data.setdefault("active", True)
    with eng.begin() as c:
        if sid is None:
            sid = c.execute(t.insert().values(**data, created_by=who[:160], created_at=audit.now())).inserted_primary_key[0]
        else:
            get(eng, sid)
            c.execute(update(t).where(t.c.schedule_id == sid).values(**data))
    return get(eng, sid)


def remove(eng: Engine, sid: int) -> dict:
    s = get(eng, sid)
    with eng.begin() as c:
        c.execute(tenant.report_schedules.delete().where(tenant.report_schedules.c.schedule_id == sid))
    return s


def management(eng: Engine) -> list[str]:
    v = Books(eng).profile().get("report_recipients") or ""
    return [x for x in v.split(",") if x]


def run_one(business: dict, s: dict, who: str = "Scheduled report") -> dict:
    """Make the report for one schedule now, email it if possible, and record what happened."""
    eng = tenant.engine_for(business["id"])
    fc = Forecaster(Books(eng))
    if s["kind"] == "comparison":
        a, b = reports.default_periods(fc.b.as_of_date(), s["frequency"])
        rep = reports.create(eng, fc, business, who, "comparison", a=a, b=b, source="scheduled")
    else:
        rep = reports.create(eng, fc, business, who, "summary", source="scheduled")
    audit.log(eng, who, "report.generated", "report", f"{rep['title']} ({rep['report_id']}), from: {s['description']}")

    to = s["recipients"] or management(eng)
    status = f"Made {rep['report_id']}"
    if to and settings.email_configured:
        link = reports.share(eng, business["id"], rep["report_id"], who, 30)
        url = f"{settings.app_url}/r/{link['token']}"
        subject, text, html = mailer.compose(rep, url, sender="Cashwise schedule")
        try:
            mailer.send(to, subject, text, html)
            status += f", emailed to {len(to)}"
            audit.log(eng, who, "report.emailed", "report", f"{rep['title']} to {', '.join(to)}")
        except AppError as e:
            status += f", email failed: {e.detail}"
            audit.log(eng, who, "report.email_failed", "report", f"{rep['title']}: {e.detail}")
    elif to:
        status += ", not emailed (email isn't set up on the server)"
    return {"report": rep, "status": status[:240]}


def run_due(at: datetime | None = None) -> int:
    """Run every schedule that is due, in every business. Returns how many ran."""
    at = at or audit.now()
    with platform.engine.connect() as c:
        bizs = [dict(b) for b in c.execute(select(platform.businesses)).mappings().all()]
    ran = 0
    for biz in bizs:
        try:
            eng = tenant.engine_for(biz["id"])
            with eng.connect() as c:
                due = c.execute(select(tenant.report_schedules).where(
                    tenant.report_schedules.c.active.is_(True), tenant.report_schedules.c.next_run <= at)).mappings().all()
            for r in due:
                s = _public(r)
                try:
                    status = run_one(biz, s)["status"]
                except Exception as e:     # one broken schedule must not stop the others
                    log.exception("scheduled report failed")
                    status = f"Failed: {e}"[:240]
                with eng.begin() as c:
                    c.execute(update(tenant.report_schedules).where(tenant.report_schedules.c.schedule_id == r["schedule_id"])
                              .values(last_run=at, last_status=status,
                                      next_run=next_run(r["frequency"], r["weekday"], r["day_of_month"], r["hour"], at)))
                ran += 1
        except Exception:
            log.exception("could not check schedules for business %s", biz.get("id"))
    return ran


async def loop() -> None:
    while True:
        try:
            n = await asyncio.to_thread(run_due)
            if n:
                log.info("ran %d scheduled report(s)", n)
        except Exception:
            log.exception("scheduler check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
