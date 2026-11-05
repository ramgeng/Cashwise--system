"""Test setup: a throwaway storage folder, demo account seeded, no real AI or memory calls."""
import os
import shutil
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="cashwise-test-")
os.environ.update({"CASHWISE_STORAGE": _TMP, "GROQ_API_KEY": "", "HINDSIGHT_API_KEY": "",
                   "HINDSIGHT_URL": "https://example.invalid", "SEED_DEMO": "true", "JWT_SECRET": "test-secret-key-that-is-long-enough-for-hs256",
                   "RUN_SCHEDULER": "false", "SMTP_HOST": ""})

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def demo(client):
    s = client.post("/api/auth/login", json={"email": "demo@cashwise.app", "password": "demo1234"}).json()
    return {"Authorization": f"Bearer {s['token']}", "X-Business-Id": str(s["businesses"][0]["id"])}


_n = [0]


@pytest.fixture
def new_account(client):
    """A fresh user with one empty business."""
    _n[0] += 1
    r = client.post("/api/auth/register", json={
        "name": f"Owner {_n[0]}", "email": f"owner{_n[0]}@example.com", "password": "password123",
        "business_name": f"Shop {_n[0]}", "city": "Kochi"})
    assert r.status_code == 201, r.text
    s = r.json()
    return {"Authorization": f"Bearer {s['token']}", "X-Business-Id": str(s["businesses"][0]["id"]),
            "_business_id": s["businesses"][0]["id"]}


def hdr(h):
    return {k: v for k, v in h.items() if not k.startswith("_")}
