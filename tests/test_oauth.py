"""Sign in with Google / GitHub, with the providers replaced by stand-ins."""
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core import config
from app.services import oauth

REAL_FETCH = oauth.fetch_profile


@pytest.fixture
def providers_on(monkeypatch):
    s = config.settings
    for k, v in {"google_client_id": "gid", "google_client_secret": "gsecret", "github_client_id": "hid",
                 "github_client_secret": "hsecret"}.items():
        object.__setattr__(s, k, v)
    yield
    for k in ("google_client_id", "google_client_secret", "github_client_id", "github_client_secret"):
        object.__setattr__(s, k, None)


def fake_http(routes):
    def handler(req: httpx.Request):
        for (method, url), body in routes.items():
            if req.method == method and str(req.url).startswith(url):
                return httpx.Response(200, json=body)
        return httpx.Response(404, json={})
    return httpx.Client(transport=httpx.MockTransport(handler))


def run_flow(client, monkeypatch, provider, routes):
    start = client.get(f"/api/auth/oauth/{provider}/start", follow_redirects=False)
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    monkeypatch.setattr(oauth, "fetch_profile", lambda p, code, u=None: REAL_FETCH(p, code, u, http=fake_http(routes)))
    back = client.get(f"/api/auth/oauth/{provider}/callback", params={"code": "abc", "state": state},
                      follow_redirects=False)
    assert back.status_code == 303
    return back.headers["location"]


def test_providers_list_says_what_is_set_up(client):
    p = {x["key"]: x for x in client.get("/api/auth/providers").json()}
    assert set(p) == {"google", "github", "apple"}
    assert p["google"]["configured"] is False and "GOOGLE_CLIENT_ID" in p["google"]["help"]


def test_not_set_up_is_a_clear_error(client):
    r = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert r.status_code == 503 and r.json()["code"] == "provider_not_configured"


def test_google_sign_in_creates_user(client, monkeypatch, providers_on):
    loc = run_flow(client, monkeypatch, "google", {
        ("POST", "https://oauth2.googleapis.com/token"): {"access_token": "t"},
        ("GET", "https://openidconnect.googleapis.com/v1/userinfo"):
            {"sub": "g-123", "email": "Meera@Gmail.com", "email_verified": True, "name": "Meera K"}})
    frag = parse_qs(urlparse(loc).fragment)
    assert frag["new"] == ["1"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {frag['token'][0]}"}).json()
    assert me["user"]["email"] == "meera@gmail.com" and me["businesses"] == []

    # second time: same user, not new
    loc2 = run_flow(client, monkeypatch, "google", {
        ("POST", "https://oauth2.googleapis.com/token"): {"access_token": "t"},
        ("GET", "https://openidconnect.googleapis.com/v1/userinfo"):
            {"sub": "g-123", "email": "meera@gmail.com", "email_verified": True, "name": "Meera K"}})
    assert parse_qs(urlparse(loc2).fragment)["new"] == ["0"]


def test_github_links_to_existing_email(client, monkeypatch, providers_on):
    loc = run_flow(client, monkeypatch, "github", {
        ("POST", "https://github.com/login/oauth/access_token"): {"access_token": "t"},
        ("GET", "https://api.github.com/user/emails"): [{"email": "demo@cashwise.app", "primary": True, "verified": True}],
        ("GET", "https://api.github.com/user"): {"id": 42, "login": "anil", "name": None}})
    frag = parse_qs(urlparse(loc).fragment)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {frag['token'][0]}"}).json()
    assert me["businesses"][0]["is_demo"] is True        # linked to the existing demo account


def test_unverified_email_is_refused(client, monkeypatch, providers_on):
    loc = run_flow(client, monkeypatch, "google", {
        ("POST", "https://oauth2.googleapis.com/token"): {"access_token": "t"},
        ("GET", "https://openidconnect.googleapis.com/v1/userinfo"):
            {"sub": "g-9", "email": "x@y.com", "email_verified": False}})
    assert "signin_error" in urlparse(loc).fragment


def test_state_from_another_browser_is_refused(client, providers_on):
    start = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    client.cookies.clear()
    back = client.get("/api/auth/oauth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert "didn" in parse_qs(urlparse(back.headers["location"]).fragment)["signin_error"][0]


def test_oauth_only_account_has_no_password(client, monkeypatch, providers_on):
    run_flow(client, monkeypatch, "google", {
        ("POST", "https://oauth2.googleapis.com/token"): {"access_token": "t"},
        ("GET", "https://openidconnect.googleapis.com/v1/userinfo"):
            {"sub": "g-77", "email": "nopass@gmail.com", "email_verified": True, "name": "N"}})
    r = client.post("/api/auth/login", json={"email": "nopass@gmail.com", "password": "!oauth-only"})
    assert r.status_code == 401


def test_apple_sign_in(client, monkeypatch):
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    s = config.settings
    for k, v in {"apple_client_id": "app.cashwise.web", "apple_team_id": "TEAM1", "apple_key_id": "KEY1",
                 "apple_private_key": pem}.items():
        object.__setattr__(s, k, v)
    try:
        start = client.get("/api/auth/oauth/apple/start", follow_redirects=False)
        q = parse_qs(urlparse(start.headers["location"]).query)
        assert q["response_mode"] == ["form_post"]
        id_token = pyjwt.encode({"iss": "https://appleid.apple.com", "aud": "app.cashwise.web", "sub": "apple-1",
                                 "email": "priya@icloud.com", "email_verified": "true"}, "x", algorithm="HS256")
        sent = {}

        def handler(req):
            sent["secret"] = parse_qs(req.content.decode())["client_secret"][0]
            return httpx.Response(200, json={"id_token": id_token})
        monkeypatch.setattr(oauth, "fetch_profile",
                            lambda p, code, u=None: REAL_FETCH(p, code, u, http=httpx.Client(transport=httpx.MockTransport(handler))))
        client.cookies.clear()   # Apple's cross-site POST arrives without our cookie
        back = client.post("/api/auth/oauth/apple/callback", follow_redirects=False,
                           data={"code": "abc", "state": q["state"][0], "user": '{"name":{"firstName":"Priya","lastName":"S"}}'})
        frag = parse_qs(urlparse(back.headers["location"]).fragment)
        assert frag["new"] == ["1"]
        assert pyjwt.get_unverified_header(sent["secret"])["kid"] == "KEY1"     # signed client secret sent to Apple
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {frag['token'][0]}"}).json()
        assert me["user"]["name"] == "Priya S"
    finally:
        for k in ("apple_client_id", "apple_team_id", "apple_key_id", "apple_private_key"):
            object.__setattr__(s, k, None)
