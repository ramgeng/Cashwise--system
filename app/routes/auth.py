from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from app.core.security import create_token
from app.db import tenant
from app.routes.deps import current_user
from app.schemas import LoginIn, RegisterIn
from app.core.config import settings
from app.core.errors import AppError
from app.services import accounts, demo, oauth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session(user: dict) -> dict:
    return {"token": create_token(user["id"]), "token_type": "bearer", "user": user,
            "businesses": accounts.list_businesses(user["id"])}


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    """Create an account and its first business. The business starts empty unless with_demo_data is true."""
    user = accounts.create_user(body.email, body.name, body.password)
    biz = accounts.create_business(user["id"], body.business_name, body.city, body.name, body.industry)
    if body.with_demo_data:
        demo.load(tenant.engine_for(biz["id"]))
    return _session(user)


@router.post("/login")
def login(body: LoginIn):
    return _session(accounts.authenticate(body.email, body.password))


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": user, "businesses": accounts.list_businesses(user["id"])}


# ------------------------------------------------------------------ Google / GitHub / Apple
COOKIE = "cashwise_oauth"


@router.get("/providers")
def providers():
    """Which sign-in providers are set up on this server."""
    return oauth.status()


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str):
    p = oauth.get(provider)
    url, nonce = oauth.start(p)
    res = RedirectResponse(url, status_code=302)
    res.set_cookie(COOKIE, nonce, max_age=oauth.STATE_TTL, httponly=True, samesite="lax",
                   secure=settings.app_url.startswith("https"), path="/api/auth/oauth")
    return res


def _back_to_app(fragment: str) -> RedirectResponse:
    res = RedirectResponse(f"{settings.app_url}/#{fragment}", status_code=303)
    res.delete_cookie(COOKIE, path="/api/auth/oauth")
    return res


@router.api_route("/oauth/{provider}/callback", methods=["GET", "POST"], include_in_schema=False)
async def oauth_callback(provider: str, request: Request):
    form = dict(await request.form()) if request.method == "POST" else {}
    q = {**dict(request.query_params), **form}
    try:
        p = oauth.get(provider)
        if q.get("error"):
            msg = "Sign-in was cancelled." if q["error"] in ("access_denied", "user_cancelled_authorize") else \
                f"{p.label} couldn't sign you in ({q['error']})."
            raise AppError(400, msg, "provider_error")
        oauth.check_state(p, q.get("state", ""), request.cookies.get(COOKIE))
        if not q.get("code"):
            raise AppError(400, "The sign-in came back without a code. Try again.", "provider_error")
        try:
            apple_user = json.loads(q["user"]) if q.get("user") else None
        except ValueError:
            apple_user = None
        profile = await run_in_threadpool(oauth.fetch_profile, p, q["code"], apple_user)
        user, new = await run_in_threadpool(oauth.sign_in, p.key, profile)
        return _back_to_app(f"token={quote(create_token(user['id']))}&new={int(new)}")
    except AppError as e:
        return _back_to_app(f"signin_error={quote(e.detail)}")
