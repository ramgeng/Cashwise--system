"""
CashFlow Intelligence - demo data generator
Fictional SME: Malabar Electronics Distributors, Kochi (owner: Anil Varghese)
Period: 1 Nov 2025 -> 5 Nov 2026 ("today" in the demo)

Run:  python generate_data.py
Creates a data/ folder with CSV files. Same seed = same data every time.
All amounts are in INR (whole rupees). All names are fictional.
"""
import csv
import os
import random
from datetime import date, timedelta

random.seed(42)

TODAY = date(2026, 11, 5)
START = date(2025, 11, 1)        # cash ledger starts here
SIM_START = date(2025, 9, 1)     # invoices/bills from Sep-Oct 2025 = opening receivables/payables
OUT = "data"
TARGET_TODAY_BALANCE = 1_200_000   # Rs 12 lakh cash on "today"
TARGET_MIN_BALANCE = 90_000        # near-crisis low point (March 2026)

# ---------------------------------------------------------------- helpers
def months(start, end):
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def d(y, m, day):
    while True:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1

def rnd(lo, hi, step=500):
    return int(random.randint(lo // step, hi // step) * step)

def last_working_day(y, m):
    x = d(y, m, 31)
    while x.weekday() == 6:  # skip Sunday
        x -= timedelta(days=1)
    return x

# seasonality on sales (electronics distributor in Kerala)
SEASON = {1: 0.95, 2: 1.0, 3: 1.15, 4: 1.15, 5: 1.0, 6: 0.8, 7: 0.8,
          8: 1.2, 9: 1.15, 10: 1.15, 11: 1.05, 12: 1.05}

# ---------------------------------------------------------------- master data
customers = [
    # id, name, city, contact, terms
    ("C001", "Mehta Traders", "Ernakulam", "Rajesh Mehta", 30),
    ("C002", "Kerala Digital Store", "Kochi", "Priya Nair", 30),
    ("C003", "Sreeram Retail Chain", "Thrissur", "Accounts Team", 45),
    ("C004", "Coastal Mobiles", "Alappuzha", "Joseph Thomas", 30),
    ("C005", "Fortune Appliances", "Kottayam", "Suresh Pillai", 30),
    ("C006", "Trinity Computers", "Kochi", "Anna George", 30),
    ("C007", "Lakshmi Home Needs", "Aluva", "Lakshmi Menon", 30),
    ("C008", "Bluewave Systems", "Kakkanad", "Farhan Ali", 30),
]
suppliers = [
    # id, name, category, terms, early discount %, discount window days, late fee % per month
    ("S001", "Vertex Electronics Pvt Ltd", "Consumer electronics stock", 30, 2.0, 10, 0.0),
    ("S002", "Orion Components", "Accessories & components", 45, 0.0, 0, 0.0),
    ("S003", "PowerCell Batteries", "Batteries & power banks", 30, 0.0, 0, 1.5),
    ("S004", "Southern Logistics", "Freight & delivery", 15, 0.0, 0, 0.0),
    ("S005", "Apex Packaging", "Packaging material", 30, 0.0, 0, 0.0),
]
CUST = {c[0]: c for c in customers}

invoices, receipts, bills, payments, expenses, events = [], [], [], [], [], []
ev_id = 0

def event(dt, etype, eid, kind, text, outcome=""):
    global ev_id
    ev_id += 1
    events.append({"event_id": f"E{ev_id:04d}", "date": dt.isoformat(),
                   "entity_type": etype, "entity_id": eid, "event_type": kind,
                   "description": text, "outcome": outcome})

inv_no = 1000
def add_invoice(cid, issue, amount):
    global inv_no
    inv_no += 1
    terms = CUST[cid][4]
    inv = {"invoice_id": f"INV-{inv_no}", "customer_id": cid,
           "issue_date": issue, "due_date": issue + timedelta(days=terms),
           "amount": amount}
    invoices.append(inv)
    return inv

rcpt_no = 0
FY_HOLD = {"C001", "C003"}  # held payments over Indian fiscal year-end (31 March)
def add_receipt(inv, dt, amount, method="Bank transfer"):
    global rcpt_no
    if inv["customer_id"] in FY_HOLD and date(2026, 3, 10) <= dt <= date(2026, 3, 31):
        dt = date(2026, 4, random.randint(1, 4))
    if dt > TODAY:
        return  # not received yet
    rcpt_no += 1
    receipts.append({"receipt_id": f"RCPT-{rcpt_no:04d}", "invoice_id": inv["invoice_id"],
                     "customer_id": inv["customer_id"], "date": dt, "amount": amount,
                     "method": method})

# ---------------------------------------------------------------- receivables
mehta_calls = []  # (invoice, call_date, paid_date, worked)
for y, m in months(SIM_START, TODAY):
    s = SEASON[m]
    first = date(y, m, 1)

    # C001 Mehta Traders - chronic late payer; worse in festival months;
    # from April 2026 owner starts phoning on due+2 which usually works.
    if (y, m) != (2026, 10):  # Oct 2026 handled in the scenario block
        for day in (6, 20):
            issue = d(y, m, day)
            if issue > TODAY:
                continue
            inv = add_invoice("C001", issue, rnd(int(240000 * s), int(380000 * s)))
            due = inv["due_date"]
            festival = due.month in (9, 10, 11)
            if due >= date(2026, 4, 1):
                call = due + timedelta(days=2)
                worked = not (festival and random.random() < 0.5)
                late = random.randint(4, 7) if worked else random.randint(13, 19)
                paid = due + timedelta(days=late)
                if call <= TODAY:
                    mehta_calls.append((inv, call, paid, worked))
            else:
                late = random.randint(11, 16) + (5 if festival else 0)
                paid = due + timedelta(days=late)
                if due + timedelta(days=3) <= TODAY:
                    event(due + timedelta(days=3), "customer", "C001", "collection_attempt",
                          f"Email reminder sent to Rajesh Mehta for {inv['invoice_id']} (Rs {inv['amount']:,}).",
                          f"No reply. Paid on {paid.isoformat()}, {late} days late." if paid <= TODAY else "No reply yet.")
            add_receipt(inv, paid, inv["amount"])

    # C002 Kerala Digital Store - reliable, pays on time or early
    if (y, m) != (2026, 10):
        for day in (4, 18):
            issue = d(y, m, day)
            if issue > TODAY:
                continue
            inv = add_invoice("C002", issue, rnd(int(160000 * s), int(240000 * s)))
            late = random.randint(-3, 1) if random.random() > 0.08 else 5
            add_receipt(inv, inv["due_date"] + timedelta(days=late), inv["amount"])

    # C003 Sreeram Retail Chain - big account, paying slower every quarter
    for day in (3, 13, 24):
        issue = d(y, m, day)
        if issue > TODAY:
            continue
        inv = add_invoice("C003", issue, rnd(int(170000 * s), int(290000 * s)))
        q = max((issue - START).days // 91, 0)  # quarter index 0..4
        lo, hi = [(2, 5), (4, 8), (7, 12), (10, 16), (12, 18)][min(q, 4)]
        add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(lo, hi)), inv["amount"])

    # C004 Coastal Mobiles - fine normally, very late in monsoon (Jun-Aug)
    for day in (9, 23):
        issue = d(y, m, day)
        if issue > TODAY:
            continue
        inv = add_invoice("C004", issue, rnd(int(110000 * s), int(190000 * s)))
        monsoon = inv["due_date"].month in (6, 7, 8)
        late = random.randint(16, 26) if monsoon else random.randint(0, 4)
        add_receipt(inv, inv["due_date"] + timedelta(days=late), inv["amount"])

    # C005 Fortune Appliances - always pays in two instalments (50% + 50%)
    issue = d(y, m, 11)
    if issue <= TODAY:
        inv = add_invoice("C005", issue, rnd(int(200000 * s), int(300000 * s), 1000))
        half = inv["amount"] // 2
        add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(3, 6)), half)
        add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(18, 24)), inv["amount"] - half)

    # C006 Trinity Computers - small, reliable
    issue = d(y, m, 15)
    if issue <= TODAY:
        inv = add_invoice("C006", issue, rnd(int(60000 * s), int(120000 * s)))
        add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(0, 2)), inv["amount"], "UPI")

    # C007 Lakshmi Home Needs - erratic; one disputed invoice (Feb 2026)
    issue = d(y, m, 17)
    if issue <= TODAY:
        inv = add_invoice("C007", issue, rnd(int(80000 * s), int(150000 * s)))
        if (y, m) == (2026, 2):
            disp = inv
            paid = inv["due_date"] + timedelta(days=62)
            add_receipt(inv, paid, inv["amount"] - 18000, "Cheque")
            event(inv["due_date"] + timedelta(days=4), "customer", "C007", "dispute",
                  f"Lakshmi Menon disputed {inv['invoice_id']}: 3 damaged induction cooktops in the delivery.",
                  "Agreed Rs 18,000 deduction after inspection.")
            event(paid, "customer", "C007", "dispute_resolved",
                  f"{inv['invoice_id']} settled after dispute, paid Rs {inv['amount'] - 18000:,}.",
                  "Paid 62 days late. Lesson: inspect deliveries to Lakshmi Home Needs on arrival.")
        else:
            add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(5, 20)), inv["amount"], "Cheque")

    # C008 Bluewave Systems - new customer from May 2026, on time so far
    if first >= date(2026, 5, 1):
        for day in (7, 21):
            issue = d(y, m, day)
            if issue > TODAY:
                continue
            inv = add_invoice("C008", issue, rnd(int(90000 * s), int(160000 * s)))
            add_receipt(inv, inv["due_date"] + timedelta(days=random.randint(-2, 2)), inv["amount"])

# ---- scenario block: the week the demo starts (as of 5 Nov 2026)
# Mehta owes ~Rs 6L due 7-12 Nov, Kerala Digital ~Rs 4L due 10 Nov.
for cid, issue, amt in [("C001", date(2026, 10, 8), 330000), ("C001", date(2026, 10, 13), 270000),
                        ("C002", date(2026, 10, 1), 200000), ("C002", date(2026, 10, 11), 200000)]:
    inv = add_invoice(cid, issue, amt)
    if inv["due_date"] < TODAY:  # KD Oct-1 invoice already paid on time
        add_receipt(inv, inv["due_date"], amt)

for inv, call, paid, worked in mehta_calls:
    event(call, "customer", "C001", "collection_attempt",
          f"Phoned Rajesh Mehta about {inv['invoice_id']} (Rs {inv['amount']:,}), 2 days after due date.",
          (f"Worked. Paid on {paid.isoformat()}, {(paid - inv['due_date']).days} days late." if worked
           else f"Did not work: festival-season stock pressure. Paid on {paid.isoformat()}, "
                f"{(paid - inv['due_date']).days} days late.") if paid <= TODAY else "Promised payment; not received yet.")

# ---------------------------------------------------------------- payables
bill_no = 500
def add_bill(sid, bdate, amount):
    global bill_no
    bill_no += 1
    terms = next(s[3] for s in suppliers if s[0] == sid)
    b = {"bill_id": f"BILL-{bill_no}", "supplier_id": sid, "bill_date": bdate,
         "due_date": bdate + timedelta(days=terms), "amount": amount}
    bills.append(b)
    return b

pay_no = 0
def add_payment(b, dt, amount, note=""):
    global pay_no
    if dt > TODAY:
        return
    pay_no += 1
    payments.append({"payment_id": f"PAY-{pay_no:04d}", "bill_id": b["bill_id"],
                     "supplier_id": b["supplier_id"], "date": dt, "amount": amount, "note": note})

early_pay_months = {(2025, 12), (2026, 1)}
for y, m in months(SIM_START, TODAY):
    nm = 1 if m == 12 else m + 1
    s_next = SEASON[nm] * (1.6 if m == 2 else 1.0)  # Feb: big pre-summer stock-up
    # S001 Vertex - main stock, two bills a month
    for day in (2, 16):
        bdate = d(y, m, day)
        if bdate > TODAY or (y, m, day) == (2026, 10, 16):
            continue
        b = add_bill("S001", bdate, rnd(int(560000 * s_next), int(700000 * s_next), 1000))
        if (y, m) in early_pay_months and day == 2:
            disc = round(b["amount"] * 0.02)
            pdate = bdate + timedelta(days=8)
            add_payment(b, pdate, b["amount"] - disc, "Paid early, 2% discount taken")
            event(pdate, "supplier", "S001", "early_payment_discount",
                  f"Paid Vertex {b['bill_id']} 8 days after billing to take the 2% early-payment discount.",
                  f"Saved Rs {disc:,}.")
        else:
            add_payment(b, b["due_date"], b["amount"])
    # S002 Orion - net 45
    bdate = d(y, m, 5)
    if bdate <= TODAY:
        b = add_bill("S002", bdate, rnd(int(330000 * s_next), int(430000 * s_next), 1000))
        if b["due_date"].year == 2026 and b["due_date"].month == 3:
            pd = b["due_date"] + timedelta(days=5)
            event(b["due_date"] - timedelta(days=2), "supplier", "S002", "extension_request",
                  f"Asked Orion Components for a 5-day extension on {b['bill_id']} (Rs {b['amount']:,}) during cash crunch.",
                  "Granted by phone, no penalty. Orion is flexible if asked before the due date.")
            add_payment(b, pd, b["amount"], "Paid with agreed 5-day extension")
        else:
            add_payment(b, b["due_date"], b["amount"])
    # S003 PowerCell - late fee 1.5%
    bdate = d(y, m, 8)
    if bdate <= TODAY:
        b = add_bill("S003", bdate, rnd(int(150000 * s_next), int(220000 * s_next), 1000))
        if b["due_date"].year == 2026 and b["due_date"].month == 3:
            pd = date(2026, 4, 3)
            late = (pd - b["due_date"]).days
            fee = round(b["amount"] * 0.015)
            add_payment(b, pd, b["amount"] + fee, f"Paid {late} days late incl. 1.5% late fee Rs {fee}")
            event(pd, "supplier", "S003", "late_payment_penalty",
                  f"Held PowerCell {b['bill_id']} to protect March salaries; paid {late} days late once collections came in.",
                  f"Charged 1.5% late fee (Rs {fee:,}). PowerCell does not give extensions.")
        else:
            add_payment(b, b["due_date"], b["amount"])
    # S004 Southern Logistics - net 15
    bdate = d(y, m, 28)
    if bdate <= TODAY:
        b = add_bill("S004", bdate, rnd(int(60000 * SEASON[m]), int(90000 * SEASON[m])))
        add_payment(b, b["due_date"], b["amount"])
    # S005 Apex Packaging
    bdate = d(y, m, 12)
    if bdate <= TODAY:
        b = add_bill("S005", bdate, rnd(30000, 50000))
        add_payment(b, b["due_date"], b["amount"])

# scenario: big Diwali stock bill from Vertex, Rs 15L due Friday 13 Nov 2026
add_bill("S001", date(2026, 10, 14), 1500000)

# ---------------------------------------------------------------- expenses
for y, m in months(START, TODAY):
    rent_date = d(y, m, 1)
    if (y, m) == (2026, 4):
        rent_date = date(2026, 4, 8)
        event(rent_date, "expense", "RENT", "late_payment_penalty",
              "April rent (Rs 1,20,000) paid 7 days late because cash hit Rs 90k on 1 April.",
              "Landlord charged Rs 6,000 late fee and was unhappy. Owner: never delay rent again.")
        expenses.append({"date": rent_date, "category": "Rent late fee", "amount": 6000,
                         "vendor": "Kochi Commercial Properties", "recurring": "No"})
    expenses.append({"date": rent_date, "category": "Rent", "amount": 120000,
                     "vendor": "Kochi Commercial Properties", "recurring": "Monthly"})
    if (y, m) != (2026, 4):  # owner skipped April drawings during the crunch
        expenses.append({"date": d(y, m, 1), "category": "Owner drawings", "amount": 200000,
                         "vendor": "Anil Varghese (owner)", "recurring": "Monthly"})
    expenses.append({"date": last_working_day(y, m), "category": "Salaries", "amount": 280000,
                     "vendor": "Staff payroll (9 employees)", "recurring": "Monthly"})
    expenses.append({"date": d(y, m, 10), "category": "Electricity", "amount": rnd(28000, 41000),
                     "vendor": "KSEB", "recurring": "Monthly"})
    expenses.append({"date": d(y, m, 3), "category": "Internet & phone", "amount": 8200,
                     "vendor": "Telecom provider", "recurring": "Monthly"})
    for day in (8, 22):
        expenses.append({"date": d(y, m, day), "category": "Fuel & local transport",
                         "amount": rnd(16000, 26000), "vendor": "Various", "recurring": "Variable"})
    expenses.append({"date": d(y, m, 19), "category": "Office & miscellaneous",
                     "amount": rnd(12000, 24000), "vendor": "Various", "recurring": "Variable"})
expenses.append({"date": date(2026, 10, 30), "category": "Festival bonus", "amount": 280000,
                 "vendor": "Staff payroll (9 employees)", "recurring": "Yearly"})
expenses.append({"date": date(2026, 10, 27), "category": "Insurance renewal", "amount": 118000,
                 "vendor": "Warehouse & stock insurance", "recurring": "Yearly"})
expenses = [e for e in expenses if e["date"] <= TODAY]

# ---------------------------------------------------------------- owner / preference memories
event(date(2025, 11, 3), "owner", "OWNER", "preference",
      "Anil Varghese (owner) does a cash check every Monday morning and wants a 1-page summary.")
event(date(2026, 3, 28), "owner", "OWNER", "decision",
      "Accountant suggested a Rs 5 lakh bank overdraft to cover the end-of-March gap. Anil declined.",
      "Preference: avoid loans/overdrafts; chase receivables and negotiate supplier timing first.")
event(date(2026, 4, 1), "owner", "OWNER", "decision",
      "Cash fell to about Rs 90,000 on 1 April. Anil skipped his own April drawings and protected salaries.",
      "Root cause: Feb stock-up bills due in March while big customers held payments over year-end.")
event(date(2026, 4, 9), "owner", "OWNER", "decision",
      "After the March crunch, Anil decided to phone slow payers 2 days after due date instead of emailing.",
      "Applied to Mehta Traders from April 2026.")
event(date(2026, 5, 7), "customer", "C008", "new_customer",
      "Onboarded Bluewave Systems (IT reseller, Kakkanad) on 30-day terms.", "Paid on time so far.")
event(date(2026, 6, 26), "customer", "C004", "customer_note",
      "Joseph Thomas (Coastal Mobiles) said monsoon footfall is low and asked for patience on June-August invoices.",
      "Pattern: Coastal pays 2-4 weeks late in monsoon, on time otherwise.")
event(date(2025, 12, 15), "customer", "C005", "customer_note",
      "Fortune Appliances informally pays every invoice in two instalments (about 50% + 50%).",
      "Plan for half the cash around due date and the rest about 3 weeks later.")
event(date(2026, 3, 27), "customer", "C003", "customer_note",
      "Sreeram Retail and Mehta Traders both held March payments until after their 31 March year-end closing.",
      "Pattern: expect big customers to delay payments due in the second half of March.")
event(date(2026, 7, 10), "customer", "C003", "customer_note",
      "Sreeram Retail accounts team blamed delays on their new billing software.",
      "Delays have kept increasing every quarter since.")

# ---------------------------------------------------------------- cash ledger & calibration
def build_ledger(opening):
    rows = []
    for r in receipts:
        if r["date"] < START:
            continue
        rows.append((r["date"], 0, "Receipt", r["receipt_id"], f"{CUST[r['customer_id']][1]} - {r['invoice_id']}", r["amount"]))
    for p in payments:
        if p["date"] < START:
            continue
        sname = next(s[1] for s in suppliers if s[0] == p["supplier_id"])
        rows.append((p["date"], 1, "Supplier payment", p["payment_id"], f"{sname} - {p['bill_id']}", -p["amount"]))
    for i, e in enumerate(expenses):
        rows.append((e["date"], 2, "Expense", f"EXP-{i+1:04d}", e["category"], -e["amount"]))
    rows.sort(key=lambda x: (x[0], x[1]))
    bal, out = opening, []
    for dt, _, typ, ref, desc, amt in rows:
        bal += amt
        out.append({"date": dt, "type": typ, "reference": ref, "description": desc,
                    "amount": amt, "balance": bal})
    return out

# Calibration: opening balance makes the March 2026 low ~Rs 90k (the near-crisis),
# then one documented owner action after March brings "today" to ~Rs 12 lakh.
def crunch_min(led):  # crunch window: 1 March - 10 April 2026
    return min(r["balance"] for r in led if date(2026, 3, 1) <= r["date"] <= date(2026, 4, 10))

led = build_ledger(0)
opening = round(TARGET_MIN_BALANCE - crunch_min(led), -3)
led = build_ledger(opening)
gap = round(TARGET_TODAY_BALANCE - led[-1]["balance"], -3)
if gap > 150000:
    adj_date = date(2026, 4, 24)
    receipts.append({"receipt_id": "RCPT-OWNER", "invoice_id": "", "customer_id": "OWNER",
                     "date": adj_date, "amount": gap, "method": "Owner capital"})
    CUST["OWNER"] = ("OWNER", "Owner capital infusion", "", "", 0)
    event(adj_date, "owner", "OWNER", "capital_infusion",
          f"After the March crunch, Anil added Rs {gap:,} of personal savings as a cash buffer (not a loan).",
          "Goal: never go below Rs 3 lakh again.")
elif gap < -150000:
    adj_date = date(2026, 6, 12)
    expenses.append({"date": adj_date, "category": "Equipment purchase", "amount": -gap,
                     "vendor": "Second delivery van (one-time)", "recurring": "No"})
    event(adj_date, "owner", "OWNER", "decision",
          f"Bought a second delivery van for Rs {-gap:,} from cash (no loan).")
led = build_ledger(opening)
post = [r["balance"] for r in led if r["date"] > date(2026, 4, 10)]
print(f"[check] Crunch low: Rs {crunch_min(led):,} | lowest after March: Rs {min(post):,}")

# ---------------------------------------------------------------- statuses
paid_by_inv = {}
for r in receipts:
    if r["invoice_id"]:
        paid_by_inv[r["invoice_id"]] = paid_by_inv.get(r["invoice_id"], 0) + r["amount"]
for inv in invoices:
    p = paid_by_inv.get(inv["invoice_id"], 0)
    disputed_cut = 18000 if p and p == inv["amount"] - 18000 else 0
    inv["amount_received"] = p
    inv["outstanding"] = max(inv["amount"] - p - disputed_cut, 0)
    inv["status"] = "Paid" if inv["outstanding"] == 0 else ("Partially paid" if p else
                    ("Overdue" if inv["due_date"] < TODAY else "Open"))
paid_by_bill = {}
for p in payments:
    paid_by_bill[p["bill_id"]] = paid_by_bill.get(p["bill_id"], 0) + p["amount"]
for b in bills:
    p = paid_by_bill.get(b["bill_id"], 0)
    b["amount_paid"] = p
    b["status"] = "Paid" if p else ("Overdue" if b["due_date"] < TODAY else "Open")

# ---------------------------------------------------------------- write files
os.makedirs(OUT, exist_ok=True)

def write(name, rows, fields):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (v.isoformat() if isinstance(v, date) else v) for k, v in r.items() if k in fields})

with open(os.path.join(OUT, "business_profile.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["field", "value"])
    for row in [("business_name", "Malabar Electronics Distributors"), ("city", "Kochi, Kerala"),
                ("owner", "Anil Varghese"), ("industry", "Consumer electronics wholesale distribution"),
                ("employees", 9), ("currency", "INR"), ("data_start", START.isoformat()),
                ("as_of_date", TODAY.isoformat()), ("opening_cash_balance", opening),
                ("cash_balance_as_of_date", led[-1]["balance"])]:
        w.writerow(row)

write("customers.csv", [dict(zip(["customer_id", "name", "city", "contact_person", "payment_terms_days"], c)) for c in customers],
      ["customer_id", "name", "city", "contact_person", "payment_terms_days"])
write("suppliers.csv", [dict(zip(["supplier_id", "name", "category", "payment_terms_days",
                                  "early_payment_discount_pct", "discount_window_days", "late_fee_pct_per_month"], s)) for s in suppliers],
      ["supplier_id", "name", "category", "payment_terms_days", "early_payment_discount_pct",
       "discount_window_days", "late_fee_pct_per_month"])
invoices.sort(key=lambda x: x["issue_date"])
write("invoices.csv", invoices, ["invoice_id", "customer_id", "issue_date", "due_date", "amount",
                                 "amount_received", "outstanding", "status"])
receipts.sort(key=lambda x: x["date"])
write("payments_received.csv", receipts, ["receipt_id", "invoice_id", "customer_id", "date", "amount", "method"])
bills.sort(key=lambda x: x["bill_date"])
write("supplier_bills.csv", bills, ["bill_id", "supplier_id", "bill_date", "due_date", "amount", "amount_paid", "status"])
payments.sort(key=lambda x: x["date"])
write("payments_made.csv", payments, ["payment_id", "bill_id", "supplier_id", "date", "amount", "note"])
expenses.sort(key=lambda x: x["date"])
write("expenses.csv", expenses, ["date", "category", "amount", "vendor", "recurring"])
write("cash_ledger.csv", led, ["date", "type", "reference", "description", "amount", "balance"])
events.sort(key=lambda x: x["date"])
for i, e in enumerate(events):
    e["event_id"] = f"E{i+1:04d}"
write("memory_events.csv", events, ["event_id", "date", "entity_type", "entity_id", "event_type", "description", "outcome"])

print(f"Done. Files written to ./{OUT}/")
print(f"Opening balance: Rs {opening:,}  |  Cash on {TODAY}: Rs {led[-1]['balance']:,}")
print(f"Lowest balance: Rs {min(r['balance'] for r in led):,} on "
      f"{min(led, key=lambda r: r['balance'])['date']}")
print(f"Invoices: {len(invoices)}  Receipts: {len(receipts)}  Bills: {len(bills)}  "
      f"Payments: {len(payments)}  Expenses: {len(expenses)}  Memory events: {len(events)}")
