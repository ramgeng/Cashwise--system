"""Send a business's history (memory_events) to its Hindsight memory bank and test a recall.

    python -m scripts.load_memory              # the demo business
    python -m scripts.load_memory --business 2
    python -m scripts.load_memory --reset      # delete the bank first, then send
"""
from scripts._pick import context, parser, pick


def main():
    p = parser(__doc__)
    p.add_argument("--reset", action="store_true", help="delete the memory bank before loading")
    a = p.parse_args()
    b = pick(a.business)
    books, _, mem = context(b)
    rows = books.rows("SELECT * FROM memory_events ORDER BY date")
    print(f"{b['name']}: {len(rows)} history events -> Hindsight bank '{b['bank_id']}'")
    if not rows:
        raise SystemExit("No history events yet. Upload 'History for memory' in the dashboard first.")
    if a.reset:
        mem.delete_bank()
        print("  old bank deleted")
    names = {**{k: v["name"] for k, v in books.customers().items()},
             **{k: v["name"] for k, v in books.suppliers().items()}, "OWNER": "the owner"}
    n = mem.retain_events(rows, names, wait=True)
    print(f"  sent {n} events")
    print("\nTest recall: 'How does our slowest customer respond to collection calls?'")
    for line in mem.recall("How does our slowest customer respond to collection calls?")[:5]:
        print("  -", line)


if __name__ == "__main__":
    main()
