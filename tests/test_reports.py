"""Reports: history, comparison, email, read-only links, schedules and the audit trail."""
import dataclasses
from datetime import timedelta

import pytest

from app.core import config
from app.services import audit, mailer, reports as reports_svc, scheduler
from tests.conftest import hdr


@pytest.fixture
def email_on(monkeypatch):
    """Pretend an SMTP server is set up, and catch what would be sent."""
    sent = []
    on = dataclasses.replace(config.settings, smtp_host="smtp.example.com", smtp_from="cashwise@example.com")
    for mod in ("app.services.mailer", "app.routes.reports", "app.services.scheduler"):
        monkeypatch.setattr(f"{mod}.settings", on)
    monkeypatch.setattr(mailer, "_send", lambda msg: sent.append(msg))
    return sent


def test_make_and_history(client, demo):
    r = client.post("/api/reports", headers=demo, json={"kind": "summary"})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["kind"] == "summary" and rep["data"]["cash"] == 1_200_325
    assert rep["data"]["flow"]["likely"]["net"] == rep["data"]["flow"]["likely"]["in"] - rep["data"]["flow"]["likely"]["out"]
    h = client.get("/api/reports", headers=demo).json()
    assert h["reports"][0]["report_id"] == rep["report_id"]
    assert "data" not in h["reports"][0]                       # history is light; open one to see it
    assert client.get(f"/api/reports/{rep['report_id']}", headers=demo).json()["data"]["as_of"] == "2026-11-05"


def test_comparison(client, demo):
    r = client.post("/api/reports", headers=demo, json={"kind": "comparison"}).json()
    assert r["title"] == "October 2026 vs September 2026"
    rows = {x["key"]: x for x in r["data"]["rows"]}
    a, b = r["data"]["a"], r["data"]["b"]
    assert a["closing"] - a["opening"] == a["net"]              # the money adds up
    assert b["closing"] == a["opening"]                          # September ends where October starts
    assert rows["expenses"]["change"] == rows["expenses"]["a"] - rows["expenses"]["b"]
    custom = client.post("/api/reports", headers=demo, json={
        "kind": "comparison", "a_from": "2026-10-16", "a_to": "2026-10-31", "b_from": "2026-10-01", "b_to": "2026-10-15"}).json()
    assert custom["data"]["a"]["days"] == 16 and custom["data"]["b"]["days"] == 15
    bad = client.post("/api/reports", headers=demo, json={"kind": "comparison", "a_from": "2026-10-10", "a_to": "2026-10-01",
                                                          "b_from": "2026-09-01", "b_to": "2026-09-30"})
    assert bad.status_code == 422


def test_read_only_link(client, demo, new_account):
    rid = client.post("/api/reports", headers=demo, json={"kind": "summary"}).json()["report_id"]
    s = client.post(f"/api/reports/{rid}/share", headers=demo, json={"days": 7}).json()
    assert s["active"] and s["url"].endswith(s["token"]) and "/r/" in s["url"]

    pub = client.get(f"/api/public/reports/{s['token']}")       # no sign-in needed
    assert pub.status_code == 200 and pub.json()["data"]["cash"] == 1_200_325
    assert set(pub.json()) == {"title", "kind", "created_at", "data"}
    assert client.get("/api/shares", headers=demo).json()["shares"][0]["views"] == 1

    # guessing or editing the token gets nothing
    assert client.get(f"/api/public/reports/{s['token']}x").status_code == 404
    assert client.get("/api/public/reports/999-abc").status_code == 404
    # someone else can't turn off this business's link
    assert client.delete(f"/api/shares/{s['token']}", headers=hdr(new_account)).status_code == 404

    client.delete(f"/api/shares/{s['token']}", headers=demo)
    assert client.get(f"/api/public/reports/{s['token']}").status_code == 404


def test_expired_link_and_deleted_report(client, demo):
    from app.db import tenant
    from sqlalchemy import update
    rid = client.post("/api/reports", headers=demo, json={"kind": "summary"}).json()["report_id"]
    s = client.post(f"/api/reports/{rid}/share", headers=demo, json={"days": 1}).json()
    bid = int(demo["X-Business-Id"])
    with tenant.engine_for(bid).begin() as c:
        c.execute(update(tenant.report_shares).where(tenant.report_shares.c.token == s["token"])
                  .values(expires_at=audit.now() - timedelta(minutes=1)))
    assert client.get(f"/api/public/reports/{s['token']}").status_code == 404

    s2 = client.post(f"/api/reports/{rid}/share", headers=demo, json={"days": None}).json()
    assert s2["expires_at"] is None
    client.delete(f"/api/reports/{rid}", headers=demo)
    assert client.get(f"/api/public/reports/{s2['token']}").status_code == 404
    assert client.get(f"/api/reports/{rid}", headers=demo).status_code == 404


def test_email_without_and_with_smtp(client, demo, email_on):
    rid = client.post("/api/reports", headers=demo, json={"kind": "summary"}).json()["report_id"]
    r = client.post(f"/api/reports/{rid}/email", headers=demo, json={"to": ["not an email"]})
    assert r.status_code == 422

    client.put("/api/reports-settings/recipients", headers=demo, json={"emails": ["CFO@Example.com", "md@example.com"]})
    r = client.post(f"/api/reports/{rid}/email", headers=demo, json={"use_management": True, "note": "Please look at 13 Nov"})
    assert r.status_code == 200, r.text
    assert r.json()["sent_to"] == ["cfo@example.com", "md@example.com"]
    msg = email_on[-1]
    assert "cfo@example.com" in msg["To"] and "Cash-flow report" in msg["Subject"]
    body = msg.get_body(("plain",)).get_content()
    assert "Please look at 13 Nov" in body and r.json()["link"] in body


def test_email_draft_when_not_set_up(client, demo):
    rid = client.post("/api/reports", headers=demo, json={"kind": "comparison"}).json()["report_id"]
    r = client.post(f"/api/reports/{rid}/email", headers=demo, json={"to": ["a@b.com"]})
    assert r.status_code == 503 and r.json()["code"] == "email_not_configured"
    d = client.post(f"/api/reports/{rid}/email", headers=demo, json={"to": ["a@b.com"], "mode": "draft"}).json()
    assert d["mode"] == "draft" and d["link"] in d["text"] and "vs" in d["subject"]
    assert client.get(d["link"].replace(config.settings.app_url, "").replace("/r/", "/api/public/reports/")).status_code == 200


def test_schedules(client, demo, email_on):
    client.put("/api/reports-settings/recipients", headers=demo, json={"emails": ["md@example.com"]})
    s = client.post("/api/schedules", headers=demo, json={"frequency": "weekly", "weekday": 0, "hour": 9}).json()
    assert s["description"] == "Cash-flow report, every Monday at 09:00" and s["next_run"]
    m = client.post("/api/schedules", headers=demo, json={"frequency": "monthly", "day_of_month": 1,
                                                          "kind": "comparison", "recipients": ["cfo@example.com"]}).json()
    assert m["recipients"] == ["cfo@example.com"]

    # run now: makes the report and emails it
    r = client.post(f"/api/schedules/{m['schedule_id']}/run", headers=demo).json()
    assert "emailed to 1" in r["status"] and r["report"]["kind"] == "comparison"
    assert email_on[-1]["To"] == "cfo@example.com"

    # the background check runs whatever is due, once, and moves it to the next time
    before = len(email_on)
    n = scheduler.run_due(audit.now() + timedelta(days=8))
    assert n >= 1 and len(email_on) > before
    after = {x["schedule_id"]: x for x in client.get("/api/schedules", headers=demo).json()["schedules"]}
    assert after[s["schedule_id"]]["last_run"] and "emailed" in after[s["schedule_id"]]["last_status"]
    hist = client.get("/api/reports", headers=demo).json()["reports"]
    assert any(x["source"] == "scheduled" for x in hist)

    client.put(f"/api/schedules/{s['schedule_id']}", headers=demo,
               json={"frequency": "weekly", "weekday": 4, "hour": 18, "active": False})
    assert client.get("/api/schedules", headers=demo).json()["schedules"][0]["active"] is False
    for x in (s, m):
        assert client.delete(f"/api/schedules/{x['schedule_id']}", headers=demo).status_code == 200


def test_next_run_times():
    from datetime import datetime
    # Thursday 5 Nov 2026, 10:00 IST (04:30 UTC) -> next Monday 9:00 IST = 03:30 UTC on 9 Nov
    at = datetime(2026, 11, 5, 4, 30)
    assert scheduler.next_run("weekly", 0, 1, 9, at) == datetime(2026, 11, 9, 3, 30)
    assert scheduler.next_run("monthly", 0, 1, 9, at) == datetime(2026, 12, 1, 3, 30)
    assert scheduler.next_run("monthly", 0, 5, 11, at) == datetime(2026, 11, 5, 5, 30)    # later today
    assert scheduler.next_run("monthly", 0, 1, 9, datetime(2026, 12, 20)) == datetime(2027, 1, 1, 3, 30)


def test_audit_trail(client, new_account):
    from tests.test_upload import up
    h = new_account
    client.put("/api/business", headers=hdr(h), json={"opening_cash_balance": 100000, "as_of_date": "2026-11-05"})
    up(client, h, "expenses", "date,category,amount\n2026-11-01,Rent,20000\n")
    client.put("/api/business", headers=hdr(h), json={"bank_balance": 90000})
    rid = client.post("/api/reports", headers=hdr(h), json={"kind": "summary"}).json()["report_id"]
    client.post(f"/api/reports/{rid}/printed", headers=hdr(h))
    tok = client.post(f"/api/reports/{rid}/share", headers=hdr(h), json={}).json()["token"]
    client.get(f"/api/public/reports/{tok}")

    e = client.get("/api/audit", headers=hdr(h)).json()["entries"]
    actions = [x["action"] for x in e]
    for a in ("opening.changed", "data.uploaded", "balance.updated", "report.generated", "report.printed",
              "share.created", "share.viewed"):
        assert a in actions, a
    bal = next(x for x in e if x["action"] == "balance.updated")
    assert "90,000" in bal["detail"] and "80,000" in bal["detail"]       # new and old figures
    assert next(x for x in e if x["action"] == "share.viewed")["actor"] == "Someone with the link"
    money = client.get("/api/audit?category=money", headers=hdr(h)).json()["entries"]
    assert {x["category"] for x in money} == {"money"}


def test_reports_survive_demo_reload(client, demo):
    rid = client.post("/api/reports", headers=demo, json={"kind": "summary"}).json()["report_id"]
    client.post("/api/data/demo", headers=demo)
    assert client.get(f"/api/reports/{rid}", headers=demo).status_code == 200
    assert any(x["action"] == "demo.loaded" for x in client.get("/api/audit", headers=demo).json()["entries"])
