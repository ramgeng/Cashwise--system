"""Uploading your own records."""
from tests.conftest import hdr


def up(client, h, kind, text, mode="replace"):
    return client.post(f"/api/data/upload/{kind}", headers=hdr(h), data={"mode": mode},
                       files={"file": (f"{kind}.csv", text.encode(), "text/csv")})


def test_templates_and_types(client):
    types = client.get("/api/data/types").json()
    assert {t["kind"] for t in types} >= {"customers", "invoices", "payments_received", "supplier_bills"}
    t = client.get("/api/data/templates/invoices")
    assert t.status_code == 200
    assert t.text.splitlines()[0].startswith("invoice_id,customer_id,issue_date")


def test_full_upload_flow(client, new_account):
    h = new_account
    r = client.put("/api/business", headers=hdr(h), json={"opening_cash_balance": 500000, "opening_date": "2026-10-01",
                                                         "as_of_date": "2026-11-05"})
    assert r.status_code == 200 and r.json()["cash"] == 500000

    assert up(client, h, "customers", "customer_id,name,payment_terms_days\nC1,Asha Stores,30\nC2,Ravi & Co,15\n").status_code == 200
    # Indian formats: day-first dates, ₹ and commas in amounts; due date worked out from terms
    r = up(client, h, "invoices", "Invoice No,Customer ID,Invoice Date,Amount\n"
                                 "I-1,C1,01/10/2026,\"₹1,00,000\"\nI-2,C1,05/10/2026,50000\nI-3,C2,20-10-2026,Rs 40000\n")
    assert r.status_code == 200, r.json()
    assert r.json()["inserted"] == 3

    r = up(client, h, "payments_received", "invoice_id,date,amount\nI-1,2026-11-03,60000\n")
    assert r.status_code == 200
    assert r.json()["books"]["cash_today"] == 560000

    cust = {c["name"]: c for c in client.get("/api/customers", headers=hdr(h)).json()}
    asha = {o["invoice_id"]: o for o in cust["Asha Stores"]["open_invoices"]}
    assert asha["I-1"]["outstanding"] == 40000 and asha["I-1"]["status"] == "Partially paid"
    assert asha["I-2"]["status"] == "Overdue"            # due 4 Nov, today is 5 Nov
    ravi = {o["invoice_id"]: o for o in cust["Ravi & Co"]["open_invoices"]}
    assert ravi["I-3"]["due"] == "2026-11-04"            # 20 Oct + 15 days

    assert up(client, h, "suppliers", "supplier_id,name\nS1,Big Wholesale\n").status_code == 200
    assert up(client, h, "supplier_bills", "bill_id,supplier_id,bill_date,due_date,amount\nB1,S1,2026-10-20,2026-11-10,700000\n").status_code == 200
    f = client.get("/api/forecast", headers=hdr(h)).json()
    assert f["key_bill"]["bill_id"] == "B1"
    assert f["summary"]["naive"]["on_target"] < 0       # 5.6L + 1.3L due - 7L bill


def test_bad_rows_save_nothing_and_say_where(client, new_account):
    h = new_account
    up(client, h, "customers", "customer_id,name\nC1,Asha\n")
    r = up(client, h, "invoices", "invoice_id,customer_id,issue_date,amount\n"
                                 "I-1,C1,2026-10-01,1000\nI-2,C9,2026-10-01,1000\nI-3,C1,not-a-date,1000\nI-1,C1,2026-10-02,5\n")
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "invalid_rows"
    problems = {(e["row"], e["column"]) for e in body["errors"]}
    assert (3, "customer_id") in problems     # unknown customer
    assert (4, "issue_date") in problems      # bad date
    assert (5, "invoice_id") in problems      # duplicate id
    assert client.get("/api/business", headers=hdr(h)).json()["counts"]["invoices"] == 0


def test_missing_columns(client, new_account):
    r = up(client, new_account, "customers", "id,title\n1,x\n")
    assert r.status_code == 422
    assert r.json()["code"] == "missing_columns"
    assert "customer_id" in r.json()["detail"]


def test_append_updates_existing_rows(client, new_account):
    h = new_account
    up(client, h, "customers", "customer_id,name\nC1,Old name\n")
    up(client, h, "customers", "customer_id,name\nC1,New name\nC2,Second\n", mode="append")
    names = sorted(c["name"] for c in client.get("/api/customers", headers=hdr(h)).json())
    assert names == ["New name", "Second"]


def test_memory_upload_without_hindsight_still_saves(client, new_account):
    r = up(client, new_account, "memory_events",
           "date,entity_type,entity_id,event_type,description,outcome\n"
           "2026-04-07,owner,OWNER,preference,Avoid overdrafts,\n")
    assert r.status_code == 200
    assert "not sent to memory" in r.json()["memory"]
    t = client.get("/api/timeline", headers=hdr(new_account)).json()
    assert t["items"][0]["text"] == "Avoid overdrafts"


def test_only_csv_sized_files(client, new_account):
    big = "customer_id,name\n" + ("C1,x\n" * 1_200_000)
    assert up(client, new_account, "customers", big).status_code == 413


def test_type_in_bank_balance(client, new_account):
    h = new_account
    client.put("/api/business", headers=hdr(h), json={"opening_cash_balance": 500000, "opening_date": "2026-10-01",
                                                     "as_of_date": "2026-11-05"})
    up(client, h, "expenses", "date,category,amount\n2026-10-10,Rent,100000\n2026-11-04,Fuel,5000\n")
    assert client.get("/api/business", headers=hdr(h)).json()["cash"] == 395000

    # the bank actually shows a different figure today: the app matches it with one adjustment
    r = client.put("/api/business", headers=hdr(h), json={"bank_balance": 412000})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["cash"] == 412000 and b["bank_balance_set"] == {"amount": 412000, "date": "2026-11-05"}
    f = client.get("/api/forecast", headers=hdr(h)).json()
    assert f["opening_cash"] == 412000

    # it's the balance at the end of that day, so a record for the same day is already in it
    up(client, h, "expenses", "date,category,amount\n2026-11-05,Snacks,2000\n", mode="append")
    assert client.get("/api/business", headers=hdr(h)).json()["cash"] == 412000

    # a balance for an earlier day: records after that day still move it
    client.put("/api/business", headers=hdr(h), json={"bank_balance": 400000, "bank_balance_date": "2026-11-01"})
    assert client.get("/api/business", headers=hdr(h)).json()["cash"] == 400000 - 5000 - 2000

    assert client.put("/api/business", headers=hdr(h), json={"bank_balance": 1, "bank_balance_date": "2026-12-01"}).status_code == 422
    client.put("/api/business", headers=hdr(h), json={"clear_bank_balance": True})
    b = client.get("/api/business", headers=hdr(h)).json()
    assert b["cash"] == 393000 and b["bank_balance_set"] is None
