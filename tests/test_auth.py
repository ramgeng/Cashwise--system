from tests.conftest import hdr


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_business_routes_need_sign_in(client):
    for path in ("/api/forecast", "/api/business", "/api/customers", "/api/actions", "/api/data/status"):
        r = client.get(path)
        assert r.status_code == 401, path
        assert r.json()["code"] == "not_signed_in"


def test_bad_token_is_rejected(client):
    r = client.get("/api/business", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
    assert r.json()["code"] == "session_expired"


def test_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "demo@cashwise.app", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["detail"] == "That email and password don't match."


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"name": "Priya", "email": "Priya@Example.com", "password": "secret-pass",
                                                "business_name": "Priya Textiles"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "priya@example.com"
    assert [b["name"] for b in body["businesses"]] == ["Priya Textiles"]

    again = client.post("/api/auth/register", json={"name": "P", "email": "priya@example.com", "password": "secret-pass",
                                                    "business_name": "X"})
    assert again.status_code == 409

    tok = client.post("/api/auth/login", json={"email": "PRIYA@example.com", "password": "secret-pass"}).json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["user"]["name"] == "Priya"


def test_register_rejects_short_password(client):
    r = client.post("/api/auth/register", json={"name": "A", "email": "a@b.co", "password": "short", "business_name": "B"})
    assert r.status_code == 422


def test_one_business_needs_no_header(client, new_account):
    h = {"Authorization": new_account["Authorization"]}
    assert client.get("/api/business", headers=h).status_code == 200


def test_second_business_needs_header(client, new_account):
    h = {"Authorization": new_account["Authorization"]}
    r = client.post("/api/businesses", headers=h, json={"name": "Second shop"})
    assert r.status_code == 201
    assert client.get("/api/business", headers=h).json()["code"] == "business_required"
    assert client.get("/api/business", headers=hdr(new_account)).status_code == 200
