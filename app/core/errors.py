"""One error format for the whole API: {"detail": "...", "code": "...", "errors": [...]}.

The frontend shows `detail` to the user, so it is always a plain, actionable sentence.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("cashwise")


class AppError(Exception):
    def __init__(self, status: int, detail: str, code: str = "error", errors: list | None = None):
        super().__init__(detail)
        self.status, self.detail, self.code, self.errors = status, detail, code, errors or []


def not_found(what: str) -> AppError:
    return AppError(404, f"{what} not found.", "not_found")


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, e: AppError):
        body = {"detail": e.detail, "code": e.code}
        if e.errors:
            body["errors"] = e.errors
        return JSONResponse(body, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in err["loc"][1:]) or "body", "message": err["msg"]}
                  for err in e.errors()]
        first = errors[0] if errors else {"field": "body", "message": "is invalid"}
        return JSONResponse({"detail": f"Check {first['field']}: {first['message']}.", "code": "invalid_input",
                             "errors": errors}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        return JSONResponse({"detail": str(e.detail), "code": "http_error"}, status_code=e.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, e: Exception):
        log.exception("Unhandled error")
        return JSONResponse({"detail": "Something went wrong on the server. Check the backend terminal for details.",
                             "code": "server_error"}, status_code=500)
