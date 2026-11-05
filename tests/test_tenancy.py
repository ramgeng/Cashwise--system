"""One business must never see another business's data."""
from tests.conftest import hdr


def test_cannot_open_someone_elses_business(client, demo, new_account):
    other = dict(hdr(new_account))
    other["X-Business-Id"] = demo["X-Business-Id"]   # the demo business, which this user doesn't belong to
    for path in ("/api/business", "/api/forecast", "/api/customers", "/api/timeline"):
        r = client.get(path, headers=other)
        assert r.status_code == 404, path
        assert r.json()["code"] == "business_not_found"


def test_new_business_starts_empty(client, new_account):
    h = hdr(new_account)
    b = client.get("/api/business", headers=h).json()
    assert b["has_data"] is False
    assert all(v == 0 for v in b["counts"].values())
    assert client.get("/api/customers", headers=h).json() == []


def test_empty_business_endpoints_do_not_crash(client, new_account):
    h = hdr(new_account)
    f = client.get("/api/forecast", headers=h)
    assert f.status_code == 200
    assert f.json()["key_bill"] is None
    assert f.json()["summary"]["likely"]["on_target"] == 0
    assert client.get("/api/actions", headers=h).json()["actions"] == []
    assert client.get("/api/bills", headers=h).json()["bills"] == []
    assert client.get("/api/timeline", headers=h).json()["items"] == []
    assert client.post("/api/scenario", headers=h, json={"changes": []}).status_code == 200


def test_demo_data_in_own_business_is_separate(client, demo, new_account):
    h = hdr(new_account)
    r = client.post("/api/data/demo", headers=h)
    assert r.status_code == 200
    assert client.get("/api/business", headers=h).json()["counts"]["invoices"] == 182
    # clearing this copy leaves the demo account untouched
    client.delete("/api/data/invoices", headers=h)
    assert client.get("/api/business", headers=h).json()["counts"]["invoices"] == 0
    assert client.get("/api/business", headers=demo).json()["counts"]["invoices"] == 182
