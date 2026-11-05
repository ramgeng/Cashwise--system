"""Check that Step 3 worked: numbers in the database, stories in Hindsight.

Run from the project root:   python -m scripts.check_step3
"""
from sqlalchemy import text

from app.db import engine
from app.memory import get_client, recall

SQL_CHECKS = {
    "Cash today": "SELECT balance FROM cash_ledger ORDER BY entry_id DESC LIMIT 1",
    "Open invoices": "SELECT COUNT(*) FROM invoices WHERE status != 'Paid'",
    "Bills due by 13 Nov": "SELECT SUM(amount) FROM supplier_bills "
                           "WHERE status != 'Paid' AND due_date <= '2026-11-13'",
}

QUESTIONS = [
    "How does Mehta Traders respond to collection attempts?",
    "What happened during the March cash crunch?",
    "Which suppliers have given payment extensions?",
]


def main():
    print("DATABASE")
    with engine.connect() as conn:
        for label, sql in SQL_CHECKS.items():
            print(f"  {label}: {conn.execute(text(sql)).scalar():,}")

    print("\nHINDSIGHT MEMORY")
    client = get_client()
    try:
        for q in QUESTIONS:
            print(f"\n  Q: {q}")
            for line in recall(client, q)[:3]:
                print(f"   - {line}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
