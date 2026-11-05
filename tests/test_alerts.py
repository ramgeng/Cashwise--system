"""Smart alerts, net cash flow and financial position."""
from tests.conftest import hdr
from tests.test_upload import up


def test_demo_alerts(client, demo):
    r = client.get("/api/alerts", headers=demo).json()
    kinds = {(a["group"], a["kind"]) for a in r["alerts"]}
    assert ("cash", "likely_negative") in kinds            # cash runs out on 13 Nov
    assert ("risk", "key_bill") in kinds                   # short for Vertex
    assert ("risk", "slowing") in kinds                    # Mehta paying slower
    assert ("expense", "month") in kinds                   # October spending above normal
    assert r["counts"]["critical"] >= 2
    # most serious first
    order = {"critical": 0, "warning": 1, "info": 2}
    sev = [order[a["severity"]] for a in r["alerts"]]
    assert sev == sorted(sev)
    assert r["low_cash_basis"] == "about two weeks of running costs"


def test_unusual_expense_and_threshold(client, new_account):
    h = new_account
    client.put("/api/business", headers=hdr(h), json={"opening_cash_balance": 300000, "opening_date": "2026-06-01",
                                                     "as_of_date": "2026-11-05"})
    up(client, h, "expenses", "date,category,amount,recurring\n"
                              "2026-07-03,Electricity,10000,Monthly\n2026-08-03,Electricity,11000,Monthly\n"
                              "2026-09-03,Electricity,10500,Monthly\n2026-10-03,Electricity,10000,Monthly\n"
                              "2026-11-03,Electricity,26000,Monthly\n2026-10-20,Legal fees,60000,No\n")
    r = client.get("/api/alerts", headers=hdr(h)).json()
    spike = [a for a in r["alerts"] if a["kind"] == "spike"]
    assert spike and spike[0]["who"] == "Electricity" and spike[0]["severity"] == "critical"   # 2.5x usual
    assert any(a["kind"] == "new" and a["who"] == "Legal fees" for a in r["alerts"])

    # a buffer above today's cash triggers a low-cash warning
    client.put("/api/business", headers=hdr(h), json={"low_cash_threshold": 5_000_000})
    r = client.get("/api/alerts", headers=hdr(h)).json()
    assert r["low_cash_threshold"] == 5_000_000 and r["low_cash_basis"] == "set by you"
    assert any(a["kind"] == "low_now" for a in r["alerts"])
    client.put("/api/business", headers=hdr(h), json={"clear_low_cash_threshold": True})
    assert client.get("/api/alerts", headers=hdr(h)).json()["low_cash_basis"] != "set by you"


def test_flow_and_position(client, demo):
    f = client.get("/api/forecast", headers=demo).json()
    for k in ("best", "likely", "worst", "naive"):
        x = f["flow"][k]
        assert x["opening"] + x["net"] == x["closing"] and x["in"] - x["out"] == x["net"]
    p = client.get("/api/position", headers=demo).json()
    assert p["net_position"] == p["cash"] + p["receivable"] - p["payable"]
    assert p["cash"] == 1_200_325
