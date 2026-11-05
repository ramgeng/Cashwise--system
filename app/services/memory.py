"""Hindsight memory for one business. Every business has its own memory bank.

Everything the agent should *remember* (behaviour, decisions, outcomes, preferences)
goes through MemoryService, so the rest of the app never talks to Hindsight directly.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime
from threading import Lock

from hindsight_client import Hindsight

from app.core.config import settings
from app.core.errors import AppError

log = logging.getLogger("cashwise.memory")
_client: Hindsight | None = None
_client_lock = Lock()
_ready_banks: set[str] = set()


def client() -> Hindsight:
    global _client
    if not settings.hindsight_configured:
        raise AppError(503, "Memory isn't set up. Add HINDSIGHT_API_KEY to the .env file and restart the backend.",
                       "memory_not_configured")
    with _client_lock:
        if _client is None:
            _client = Hindsight(base_url=settings.hindsight_url, api_key=settings.hindsight_api_key, timeout=120.0)
        return _client


def _retry(fn, *args, attempts: int = 3, **kwargs):
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # rate limits, network blips
            if i == attempts - 1:
                raise
            log.warning("Hindsight call failed (%s), retrying", str(e)[:80])
            time.sleep(2 * (i + 1))


class MemoryService:
    def __init__(self, bank_id: str, business_name: str, industry: str = "", city: str = ""):
        self.bank_id = bank_id
        self.business_name = business_name
        self.mission = (
            f"Financial memory for {business_name}"
            + (f", a {industry.lower()} business" if industry else "")
            + (f" in {city}" if city else "") + ". "
            "Remember how each customer pays (delays, part-payments, seasonal patterns), which collection "
            "approaches worked, supplier terms, extensions and penalties, past cash crunches, and the "
            "owner's decisions and preferences, with their outcomes.")

    def ensure_bank(self) -> None:
        if self.bank_id in _ready_banks:
            return
        try:
            client().create_bank(bank_id=self.bank_id, name=self.business_name, mission=self.mission)
        except AppError:
            raise
        except Exception as e:  # already exists
            if "exist" not in str(e).lower() and "409" not in str(e):
                log.info("create_bank: %s", str(e)[:120])
        _ready_banks.add(self.bank_id)

    def recall(self, query: str, budget: str = "mid") -> list[str]:
        res = _retry(client().recall, bank_id=self.bank_id, query=query, budget=budget)
        return [r.text for r in res.results]

    def retain(self, content: str, tags: list[str], context: str, when: date | None = None) -> None:
        """Save one memory in the background (does not block the request)."""
        self.ensure_bank()
        ts = datetime.combine(when or date.today(), datetime.now().time()).isoformat() + "Z"
        client().retain(bank_id=self.bank_id, content=content, context=context, tags=tags, timestamp=ts,
                        document_id=f"{tags[0]}-{uuid.uuid4().hex[:10]}", retain_async=True)

    def retain_events(self, events: list[dict], names: dict[str, str], wait: bool = False, batch: int = 10) -> int:
        """Send business history (memory_events rows) to Hindsight. Re-sending updates, not duplicates."""
        self.ensure_bank()
        items = []
        for e in events:
            who = names.get(e["entity_id"], e["entity_id"])
            d = str(e["date"])[:10]
            text = f"On {d} ({e['entity_type']} {who}): {e['description']}"
            if e.get("outcome"):
                text += f" Outcome: {e['outcome']}"
            items.append({"content": text, "timestamp": f"{d}T10:00:00Z",
                          "context": f"{e['event_type'].replace('_', ' ')} for {who}",
                          "document_id": f"event-{e['event_id']}",
                          "tags": [f"{e['entity_type']}:{e['entity_id']}", e["event_type"]],
                          "metadata": {"event_id": str(e["event_id"]), "entity_id": str(e["entity_id"]),
                                       "event_type": e["event_type"]}})
        for i in range(0, len(items), batch):
            _retry(client().retain_batch, bank_id=self.bank_id, items=items[i:i + batch], retain_async=not wait)
        return len(items)

    def delete_bank(self) -> None:
        try:
            client().delete_bank(self.bank_id)
        except Exception as e:
            log.info("delete_bank: %s", str(e)[:120])
        _ready_banks.discard(self.bank_id)
