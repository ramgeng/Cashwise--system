"""Hindsight memory layer: the story behind the numbers.

Everything the agent should *remember* (behaviour, decisions, outcomes, preferences)
goes through this module, so the rest of the app never talks to Hindsight directly.
"""
import time

from hindsight_client import Hindsight

from app.config import BANK_ID, BUSINESS_NAME, HINDSIGHT_API_KEY, HINDSIGHT_URL

BANK_MISSION = (
    f"Financial memory for {BUSINESS_NAME}, an electronics distributor in Kochi. "
    "Remember how each customer pays (delays, part-payments, seasonal patterns), which "
    "collection approaches worked, supplier terms, extensions and penalties, past cash "
    "crunches, and the owner's decisions and preferences, with their outcomes."
)


def get_client() -> Hindsight:
    if not HINDSIGHT_API_KEY and "localhost" not in HINDSIGHT_URL:
        raise SystemExit("HINDSIGHT_API_KEY is missing from .env")
    return Hindsight(base_url=HINDSIGHT_URL, api_key=HINDSIGHT_API_KEY, timeout=120.0)


def ensure_bank(client: Hindsight, bank_id: str = BANK_ID) -> None:
    """Create the bank if it doesn't exist yet (safe to call every time)."""
    try:
        client.create_bank(bank_id=bank_id, name=BUSINESS_NAME, mission=BANK_MISSION)
    except Exception as e:  # already exists, or plan doesn't allow updates
        if "exist" not in str(e).lower() and "409" not in str(e):
            print(f"  note: create_bank said: {str(e)[:120]}")


def with_retry(fn, *args, attempts: int = 3, **kwargs):
    """Retry on rate limits / network blips with a short backoff."""
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if i == attempts - 1:
                raise
            wait = 2 * (i + 1)
            print(f"  retrying in {wait}s ({str(e)[:80]})")
            time.sleep(wait)


def retain_items(client: Hindsight, items: list[dict], bank_id: str = BANK_ID, batch_size: int = 10) -> int:
    done = 0
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        with_retry(client.retain_batch, bank_id=bank_id, items=chunk)
        done += len(chunk)
        print(f"  retained {done}/{len(items)}")
    return done


def recall(client: Hindsight, query: str, bank_id: str = BANK_ID, budget: str = "mid") -> list[str]:
    res = with_retry(client.recall, bank_id=bank_id, query=query, budget=budget)
    return [r.text for r in res.results]
