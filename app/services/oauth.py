"""Sign in with Google, GitHub or Apple (OAuth 2.0 authorization-code flow).

1. /api/auth/oauth/{provider}/start  sends the browser to the provider, with a signed `state`
   and a matching one-time cookie (stops someone tricking you into signing in as them).
2. The provider sends the browser back to /api/auth/oauth/{provider}/callback with a code.
3. We swap the code for the person's verified email, find or create the Cashwise user,
   and send the browser to the app with a Cashwise token in the URL fragment (#token=...),
   which never reaches any server log.
"""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppError
from app.db import platform
from app.db.platform import oauth_identities, users
from app.services import accounts

log = logging.getLogger("cashwise.oauth")
STATE_TTL = 600
NO_PASSWORD = "!oauth-only"   # never matches a password, so these accounts can't sign in with one


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    authorize_url: str
    token_url: str
    scope: str

    @property
    def configured(self) -> bool:
        s = settings
        if self.key == "google":
            return bool(s.google_client_id and s.google_client_secret)
        if self.key == "github":
            return bool(s.github_client_id and s.github_client_secret)
        return bool(s.apple_client_id and s.apple_team_id and s.apple_key_id and s.apple_private_key)

    @property
    def client_id(self) -> str:
        return {"google": settings.google_client_id, "github": settings.github_client_id,
                "apple": settings.apple_client_id}[self.key]

    @property
    def redirect_uri(self) -> str:
        return f"{settings.app_url}/api/auth/oauth/{self.key}/callback"


PROVIDERS = {p.key: p for p in [
    Provider("google", "Google", "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token",
             "openid email profile"),
    Provider("github", "GitHub", "https://github.com/login/oauth/authorize", "https://github.com/login/oauth/access_token",
             "read:user user:email"),
    Provider("apple", "Apple", "https://appleid.apple.com/auth/authorize", "https://appleid.apple.com/auth/token",
             "name email"),
]}

SETUP_HELP = {
    "google": "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env (see BACKEND.md).",
    "github": "Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to .env (see BACKEND.md).",
    "apple": "Needs an Apple Developer account and an https website. See BACKEND.md.",
}


def get(key: str) -> Provider:
    p = PROVIDERS.get(key)
    if not p:
        raise AppError(404, f"Unknown sign-in provider '{key}'.", "unknown_provider")
    if not p.configured:
        raise AppError(503, f"Sign in with {p.label} isn't set up. {SETUP_HELP[key]}", "provider_not_configured")
    return p


def status() -> list[dict]:
    return [{"key": p.key, "label": p.label, "configured": p.configured,
             "help": None if p.configured else SETUP_HELP[p.key]} for p in PROVIDERS.values()]


# ------------------------------------------------------------------ step 1
def start(p: Provider) -> tuple[str, str]:
    """Return (provider URL to send the browser to, nonce for the one-time cookie)."""
    nonce = secrets.token_urlsafe(24)
    state = jwt.encode({"p": p.key, "n": nonce, "exp": int(time.time()) + STATE_TTL}, settings.jwt_secret, algorithm="HS256")
    params = {"client_id": p.client_id, "redirect_uri": p.redirect_uri, "response_type": "code", "scope": p.scope,
              "state": state}
    if p.key == "google":
        params |= {"prompt": "select_account", "access_type": "online"}
    if p.key == "apple":
        params |= {"response_mode": "form_post"}   # Apple posts the answer back
    return f"{p.authorize_url}?{urlencode(params)}", nonce


def check_state(p: Provider, state: str, cookie_nonce: str | None) -> None:
    try:
        data = jwt.decode(state or "", settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AppError(400, "That sign-in link has expired. Try again.", "bad_state")
    if data.get("p") != p.key:
        raise AppError(400, "That sign-in didn't match. Try again.", "bad_state")
    # Apple answers with a cross-site POST, which browsers send without our cookie; its state is still signed and short-lived.
    if p.key != "apple" and (not cookie_nonce or not secrets.compare_digest(cookie_nonce, data.get("n", ""))):
        raise AppError(400, "That sign-in didn't start in this browser. Try again.", "bad_state")


# ------------------------------------------------------------------ step 2
def _apple_client_secret() -> str:
    now = int(time.time())
    return jwt.encode({"iss": settings.apple_team_id, "iat": now, "exp": now + 3600, "aud": "https://appleid.apple.com",
                       "sub": settings.apple_client_id}, settings.apple_private_key, algorithm="ES256",
                      headers={"kid": settings.apple_key_id})


def fetch_profile(p: Provider, code: str, apple_user: dict | None = None, http: httpx.Client | None = None) -> dict:
    """Swap the code for {subject, email, name}. The email must be verified by the provider."""
    own = http is None
    http = http or httpx.Client(timeout=15)
    try:
        if p.key == "google":
            tok = http.post(p.token_url, data={"code": code, "client_id": settings.google_client_id,
                                               "client_secret": settings.google_client_secret,
                                               "redirect_uri": p.redirect_uri, "grant_type": "authorization_code"})
            tok.raise_for_status()
            info = http.get("https://openidconnect.googleapis.com/v1/userinfo",
                            headers={"Authorization": f"Bearer {tok.json()['access_token']}"}).json()
            if not info.get("email_verified"):
                raise AppError(400, "Your Google email isn't verified.", "email_not_verified")
            return {"subject": info["sub"], "email": info["email"], "name": info.get("name") or info["email"].split("@")[0]}

        if p.key == "github":
            tok = http.post(p.token_url, headers={"Accept": "application/json"},
                            data={"code": code, "client_id": settings.github_client_id,
                                  "client_secret": settings.github_client_secret, "redirect_uri": p.redirect_uri})
            tok.raise_for_status()
            access = tok.json().get("access_token")
            if not access:
                raise AppError(400, "GitHub didn't accept the sign-in. Try again.", "provider_error")
            h = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
            user = http.get("https://api.github.com/user", headers=h).json()
            emails = http.get("https://api.github.com/user/emails", headers=h).json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None) or \
                next((e for e in emails if e.get("verified")), None)
            if not primary:
                raise AppError(400, "Add and verify an email on your GitHub account first.", "email_not_verified")
            return {"subject": str(user["id"]), "email": primary["email"], "name": user.get("name") or user.get("login")}

        # apple
        tok = http.post(p.token_url, data={"code": code, "client_id": settings.apple_client_id,
                                           "client_secret": _apple_client_secret(), "redirect_uri": p.redirect_uri,
                                           "grant_type": "authorization_code"})
        tok.raise_for_status()
        # Received straight from Apple over TLS, so the token's origin is already established (OIDC Core 3.1.3.7).
        claims = jwt.decode(tok.json()["id_token"], options={"verify_signature": False})
        if claims.get("iss") != "https://appleid.apple.com" or claims.get("aud") != settings.apple_client_id:
            raise AppError(400, "Apple's answer didn't match this app.", "provider_error")
        if str(claims.get("email_verified")).lower() != "true" or not claims.get("email"):
            raise AppError(400, "Apple didn't share a verified email.", "email_not_verified")
        n = (apple_user or {}).get("name") or {}
        name = " ".join(x for x in (n.get("firstName"), n.get("lastName")) if x) or claims["email"].split("@")[0]
        return {"subject": claims["sub"], "email": claims["email"], "name": name}
    except httpx.HTTPError as e:
        log.warning("%s sign-in failed: %s", p.key, e)
        raise AppError(502, f"Couldn't reach {p.label}. Try again in a moment.", "provider_unreachable")
    finally:
        if own:
            http.close()


# ------------------------------------------------------------------ step 3
def sign_in(provider: str, profile: dict) -> tuple[dict, bool]:
    """Find the user for this provider account (or the same verified email), or create one. Returns (user, is_new)."""
    email = profile["email"].strip().lower()
    with platform.engine.begin() as c:
        uid = c.execute(select(oauth_identities.c.user_id).where(oauth_identities.c.provider == provider,
                                                                 oauth_identities.c.subject == profile["subject"])).scalar()
        new = False
        if not uid:
            uid = c.execute(select(users.c.id).where(users.c.email == email)).scalar()
            if not uid:
                uid = c.execute(users.insert().values(email=email, name=profile["name"][:120], password_hash=NO_PASSWORD)
                                ).inserted_primary_key[0]
                new = True
            c.execute(oauth_identities.insert().values(provider=provider, subject=profile["subject"], user_id=uid, email=email))
    return accounts.get_user(uid), new
