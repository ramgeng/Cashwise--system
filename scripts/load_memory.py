"""Seed Hindsight with a year of business history from data/memory_events.csv.

Run from the project root:
    python -m scripts.load_memory --dry-run   # preview, sends nothing
    python -m scripts.load_memory             # send to Hindsight
    python -m scripts.load_memory --reset     # delete the bank first, then send

Each event becomes one memory with its real date, so the agent can recall
"what happened last March" and see how patterns changed over time.
"""
import argparse
import csv

from app.config import BANK_ID, DATA_DIR
from app.memory import ensure_bank, get_client, recall, retain_items


def load_names():
    names = {"OWNER": "Anil Varghese", "RENT": "Kochi Commercial Properties (landlord)"}
    for f, key in (("customers.csv", "customer_id"), ("suppliers.csv", "supplier_id")):
        with open(DATA_DIR / f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                names[r[key]] = r["name"]
    return names


def build_items():
    names = load_names()
    items = []
    with open(DATA_DIR / "memory_events.csv", encoding="utf-8") as fh:
        for e in csv.DictReader(fh):
            who = names.get(e["entity_id"], e["entity_id"])
            text = f"On {e['date']} ({e['entity_type']} {who}): {e['description']}"
            if e["outcome"]:
                text += f" Outcome: {e['outcome']}"
            items.append({
                "content": text,
                "timestamp": f"{e['date']}T10:00:00Z",
                "context": f"{e['event_type'].replace('_', ' ')} for {who}",
                "document_id": f"event-{e['event_id']}",  # re-running updates, not duplicates
                "tags": [f"{e['entity_type']}:{e['entity_id']}", e["event_type"]],
                "metadata": {"event_id": e["event_id"], "entity_id": e["entity_id"],
                             "event_type": e["event_type"]},
            })
    return items


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="show what would be sent")
    p.add_argument("--reset", action="store_true", help="delete the bank before loading")
    args = p.parse_args()

    items = build_items()
    print(f"{len(items)} memory events prepared for bank '{BANK_ID}'")
    if args.dry_run:
        for it in items[:3]:
            print("\n", it["content"], "\n  tags:", it["tags"])
        print("\nDry run only: nothing was sent.")
        return

    client = get_client()
    try:
        if args.reset:
            try:
                client.delete_bank(BANK_ID)
                print("  old bank deleted")
            except Exception:
                pass
        ensure_bank(client)
        retain_items(client, items)

        print("\nTest recall: 'How does Mehta Traders respond to collection attempts?'")
        for line in recall(client, "How does Mehta Traders respond to collection attempts?")[:5]:
            print("  -", line)
        print("\nMemory loaded.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
