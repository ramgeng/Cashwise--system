"""Read-outs for the dashboard. All numbers come from the Forecaster, scoped to the current business."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.errors import AppError
from app.routes.deps import BusinessContext, current_business
from app.schemas import ScenarioIn
from app.services import alerts as smart_alerts, insights
from app.services.tools import ToolBox

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/forecast")
def forecast(horizon_days: int = Query(28, ge=1, le=180), target_date: str | None = None,
             ctx: BusinessContext = Depends(current_business)):
    return insights.dashboard_forecast(ctx.forecaster, horizon_days, target_date)


@router.post("/scenario")
def scenario(body: ScenarioIn, ctx: BusinessContext = Depends(current_business)):
    """The forecast with what-if changes applied, in the same day-by-day shape as /api/forecast."""
    tools = ToolBox(ctx.forecaster, None)
    try:
        changes = [tools.normalize_change(c) for c in body.changes]
    except (ValueError, KeyError) as e:
        raise AppError(400, f"That what-if can't be worked out: {e}", "bad_change")
    target = body.target_date.isoformat() if body.target_date else None
    return insights.scenario(ctx.forecaster, changes, body.horizon_days, target)


@router.get("/position")
def position(ctx: BusinessContext = Depends(current_business)):
    """Overall financial position: cash, receivables, payables and the net of them."""
    return insights.position(ctx.forecaster)


@router.get("/alerts")
def alerts(horizon_days: int = Query(28, ge=7, le=90), ctx: BusinessContext = Depends(current_business)):
    """Smart alerts: unusual expenses, low cash warnings and cash-flow risks."""
    return smart_alerts.smart_alerts(ctx.forecaster, horizon_days)


@router.get("/actions")
def actions(horizon_days: int = Query(28, ge=1, le=180), ctx: BusinessContext = Depends(current_business)):
    return insights.this_week(ctx.forecaster, horizon_days)


@router.get("/customers")
def customers(ctx: BusinessContext = Depends(current_business)):
    return insights.customer_list(ctx.forecaster)


@router.get("/bills")
def bills(days: int = Query(45, ge=1, le=365), ctx: BusinessContext = Depends(current_business)):
    return insights.upcoming_bills(ctx.forecaster, days)


@router.get("/timeline")
def timeline(ctx: BusinessContext = Depends(current_business)):
    return insights.timeline(ctx.forecaster)
