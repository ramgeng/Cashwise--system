"""Readable request logs: method, path, status, time taken, and a request id for tracing."""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request

log = logging.getLogger("cashwise")


def setup(app: FastAPI) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
                            datefmt="%H:%M:%S")

    @app.middleware("http")
    async def _log_requests(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
        start = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            log.info("%s %s -> %s in %.0f ms [%s]", request.method, request.url.path, response.status_code,
                     (time.perf_counter() - start) * 1000, rid)
        response.headers["x-request-id"] = rid
        return response
