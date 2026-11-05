# Demo data: Malabar Electronics Distributors

Fictional consumer-electronics wholesaler in Kochi, Kerala. Owner: Anil Varghese, 9 staff.
All names and numbers are invented. Amounts are in INR (whole rupees).

- **Cash ledger period:** 1 Nov 2025 to 5 Nov 2026
- **"Today" in the demo:** Thursday 5 Nov 2026
- Invoices and bills from Sep to Oct 2025 are included as opening receivables and payables.
- Regenerate any time with `python generate_data.py` (fixed seed, same output every run).

## Files

| File | What it holds | Goes to |
|---|---|---|
| `business_profile.csv` | Name, owner, opening balance, cash on "today" | PostgreSQL |
| `customers.csv` | 8 customers with payment terms | PostgreSQL |
| `suppliers.csv` | 5 suppliers with terms, early-pay discount, late fee | PostgreSQL |
| `invoices.csv` | Sales invoices with amount received, outstanding and status | PostgreSQL |
| `payments_received.csv` | Every customer payment, including part-payments | PostgreSQL |
| `supplier_bills.csv` | Bills from suppliers with status | PostgreSQL |
| `payments_made.csv` | Every supplier payment, with notes on discounts and late fees | PostgreSQL |
| `expenses.csv` | Rent, salaries, utilities, owner drawings, one-offs | PostgreSQL |
| `cash_ledger.csv` | All cash movements in date order, with running balance | PostgreSQL (checking) |
| `memory_events.csv` | Collection attempts, disputes, negotiations, owner decisions and their outcomes | **Hindsight (retain)** |

Numbers go to the database for the maths. `memory_events.csv` is the "story" behind the
numbers, which is what Hindsight should remember.

## Built-in patterns (answer key)

Use these to check that your forecasts and the agent's memory find the right things.

| Customer | Behaviour hidden in the data |
|---|---|
| Mehta Traders | Chronic late payer (~14 days late with email reminders). From April, a phone call 2 days after the due date cut it to ~5 days late. In festival season (Sep to Nov) calls stopped working (13 to 15 days late). |
| Kerala Digital Store | Reliable. Pays on time or a few days early. |
| Sreeram Retail Chain | Biggest account (45-day terms). Gets slower every quarter: ~3 days late, rising to ~12 days. Held payments over the 31 March year-end. |
| Coastal Mobiles | On time normally, 2 to 4 weeks late in monsoon (Jun to Aug). |
| Fortune Appliances | Always pays in two halves: ~5 days late, then ~3 weeks late. |
| Trinity Computers | Small and reliable. |
| Lakshmi Home Needs | Erratic, 5 to 20 days late. One Feb 2026 invoice disputed (damaged goods) and paid 62 days late with a Rs 18,000 deduction. |
| Bluewave Systems | New customer since May 2026, on time so far. |

| Supplier | Behaviour |
|---|---|
| Vertex Electronics | Main stock supplier. 2% discount if paid within 10 days (taken in Dec 2025 and Jan 2026). |
| Orion Components | Gave a 5-day extension with no penalty when asked before the due date. |
| PowerCell Batteries | No extensions. Charges 1.5% late fee (charged once, April 2026). |
| Southern Logistics, Apex Packaging | Paid on time, small amounts. |

**The March 2026 crunch:** a big pre-summer stock-up in February created large supplier
bills due in March, while Mehta and Sreeram held payments until after 31 March. Cash fell to
about Rs 90,000 on 1 April. Anil declined an overdraft, skipped his own April drawings,
asked Orion for an extension, paid PowerCell late (fee) and paid April rent late (fee).
He then added Rs 3.68 lakh of savings as a buffer and started phoning slow payers.
Cash never went below about Rs 3.6 lakh after that.

## Demo scenario as of 5 Nov 2026

- **Cash:** about Rs 12 lakh
- **Big bill:** Vertex Rs 15 lakh (Diwali stock) due **Friday 13 Nov**
- **Other bills due by 13 Nov:** PowerCell Rs 1.73L (7 Nov), Apex Rs 0.43L, Southern Logistics Rs 0.81L
- **Expected collections by 13 Nov:** Mehta Rs 6L (due 7 and 12 Nov), Kerala Digital Rs 2L (10 Nov),
  Coastal Rs 1.3L (8 Nov), Fortune Rs 2.47L (10 Nov, in halves), Sreeram Rs 2.59L overdue + Rs 2.08L due 8 Nov

A plain dashboard adds these up and says "fine". A memory-powered agent should notice:
Mehta usually pays two weeks late in festival season and calls have not been working lately,
Sreeram keeps getting slower, Fortune pays only half on time. So cash on 13 Nov is likely
**short**, and the agent should recommend actions that fit Anil's history: chase Sreeram and
Mehta now, ask Vertex for a part-payment or short extension (as Orion granted before),
never delay rent, avoid overdrafts.

## Loading memory into Hindsight (sketch)

```python
import csv
for e in csv.DictReader(open("data/memory_events.csv", encoding="utf-8")):
    client.retain(
        bank_id="malabar-electronics",
        content=f"{e['description']} Outcome: {e['outcome']}",
        context=f"{e['entity_type']}:{e['entity_id']} {e['event_type']}",
        timestamp=f"{e['date']}T10:00:00Z",
    )
```
