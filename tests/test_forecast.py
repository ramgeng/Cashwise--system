"""The demo story the hackathon pitch depends on."""


def test_demo_cash_and_headline(client, demo):
    b = client.get("/api/business", headers=demo).json()
    assert b["cash"] == 1_200_325
    assert b["as_of"] == "2026-11-05"

    f = client.get("/api/forecast", headers=demo).json()
    assert f["key_bill"]["amount"] == 1_500_000
    assert f["target_date"] == "2026-11-13"
    s = f["summary"]
    assert s["naive"]["on_target"] == 991_492        # a due-date dashboard says "fine"
    assert s["likely"]["on_target"] == -194_008      # memory of how customers pay says "short"
    assert s["best"]["on_target"] > 0 > s["worst"]["on_target"]
    for d in f["days"]:
        assert d["worst"] <= d["likely"] <= d["best"]


def test_this_week_actions(client, demo):
    a = client.get("/api/actions", headers=demo).json()["actions"]
    assert a[0]["kind"] == "negotiate" and "Vertex" in a[0]["title"]
    assert {x["who"] for x in a[1:]} == {"Mehta Traders", "Fortune Appliances"}


def test_part_payment_fixes_the_shortfall(client, demo):
    first = client.get("/api/actions", headers=demo).json()["actions"][0]
    r = client.post("/api/scenario", headers=demo, json={"changes": [first["change"]]}).json()
    assert r["likely"]["on_target"] > 0


def test_what_if_accepts_names(client, demo):
    r = client.post("/api/scenario", headers=demo,
                    json={"changes": [{"type": "delay_customer", "customer": "mehta", "days": 15}]})
    assert r.status_code == 200
    bad = client.post("/api/scenario", headers=demo,
                      json={"changes": [{"type": "delay_customer", "customer": "nobody", "days": 3}]})
    assert bad.status_code == 400
    assert "Unknown customer" in bad.json()["detail"]


def test_customer_patterns(client, demo):
    cs = {c["name"]: c for c in client.get("/api/customers", headers=demo).json()}
    assert cs["Mehta Traders"]["median_days_late"] >= 10
    assert cs["Fortune Appliances"]["pays_in_instalments"] is True
    assert cs["Sreeram Retail Chain"]["quarterly_trend"].startswith("getting slower")
    assert cs["Kerala Digital Store"]["median_days_late"] <= 0


def test_ai_not_configured_is_a_clear_error(client, demo):
    r = client.post("/api/ask", headers=demo, json={"question": "Can I pay Vertex on Friday?"})
    assert r.status_code == 503
    assert "GROQ_API_KEY" in r.json()["detail"]
