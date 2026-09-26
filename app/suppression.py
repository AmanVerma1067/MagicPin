from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, Set


def generate_suppression_key(
    trigger_type: str,
    category: str,
    merchant_id: str,
    now: datetime,
) -> str:
    """
    Deterministic key pattern derived from request now:
    f"{trigger_type}:{category}:{merchant_id}:{iso_year}-W{iso_week:02d}"
    """
    iso_year, iso_week, _ = now.isocalendar()
    clean_cat = category.strip().lower()
    clean_type = trigger_type.strip().lower()
    clean_mid = merchant_id.strip()
    return f"{clean_type}:{clean_cat}:{clean_mid}:{iso_year}-W{iso_week:02d}"


class SentLedger:
    """Thread-safe ledger tracking proactive outreach suppression keys."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sent_keys: Set[str] = set()
        self._sent_timestamps: Dict[str, datetime] = {}

    def is_suppressed(self, key: str) -> bool:
        with self._lock:
            return key in self._sent_keys

    def record_sent(self, key: str, sent_at: datetime | None = None) -> None:
        with self._lock:
            self._sent_keys.add(key)
            self._sent_timestamps[key] = sent_at or datetime.now(timezone.utc)

    def get_sent_count(self) -> int:
        with self._lock:
            return len(self._sent_keys)

    def clear(self) -> None:
        with self._lock:
            self._sent_keys.clear()
            self._sent_timestamps.clear()
