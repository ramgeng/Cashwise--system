"""Cashwise API.

Run from the project root:   uvicorn app.main:app --reload
Docs (try every endpoint):   http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core import errors, logging as applog
from app.core.config import ROOT, settings
from app.db import platform
from app.routes import agent, auth, businesses, dashboard, data, reports
from app.services import accounts, scheduler

VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    platform.init()
    if settings.seed_demo:
        accounts.seed_demo()
    task = asyncio.create_task(scheduler.loop()) if settings.run_scheduler else None
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Cashwise API", version=VERSION, lifespan=lifespan,
                  description="Memory-powered cash-flow forecasting for small businesses.")
    applog.setup(app)
    errors.install(app)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["x-request-id"])

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "version": VERSION, "ai_configured": bool(settings.groq_api_key),
                "memory_configured": settings.hindsight_configured}

    for r in (auth.router, businesses.router, dashboard.router, agent.router, data.router, reports.router):
        app.include_router(r)

    dist = ROOT / "frontend" / "dist"
    if dist.exists():   # serve the built React app from the same server
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = dist / path
            return FileResponse(f if path and f.is_file() else dist / "index.html")

    return app


app = create_app()
