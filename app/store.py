from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Set, Tuple

import orjson

from app.schemas import ContextAck, ContextPush, Scope


@dataclass(frozen=True)
class ContextRecord:
    scope: Scope
    context_id: str
    version: int
    payload: MappingProxyType
    stored_at: datetime


@dataclass(frozen=True)
class StoreSnapshot:
    categories: MappingProxyType[str, ContextRecord]
    merchants: MappingProxyType[str, ContextRecord]
    customers: MappingProxyType[str, ContextRecord]
    triggers: MappingProxyType[str, ContextRecord]
    customers_by_merchant: MappingProxyType[str, Tuple[str, ...]]
    triggers_by_merchant: MappingProxyType[str, Tuple[str, ...]]
    merchants_by_category: MappingProxyType[str, Tuple[str, ...]]
    counts: MappingProxyType[str, int]


def _empty_snapshot() -> StoreSnapshot:
    return StoreSnapshot(
        categories=MappingProxyType({}),
        merchants=MappingProxyType({}),
        customers=MappingProxyType({}),
        triggers=MappingProxyType({}),
        customers_by_merchant=MappingProxyType({}),
        triggers_by_merchant=MappingProxyType({}),
        merchants_by_category=MappingProxyType({}),
        counts=MappingProxyType({"category": 0, "merchant": 0, "customer": 0, "trigger": 0}),
    )


class ContextStore:
    """Thread-safe, copy-on-write, lock-free read in-memory context store."""

    def __init__(self, max_context_bytes: int = 512000):
        self._max_context_bytes = max_context_bytes
        self._write_lock = threading.Lock()
        self._snapshot: StoreSnapshot = _empty_snapshot()

    @property
    def snapshot(self) -> StoreSnapshot:
        return self._snapshot

    def upsert(self, push: ContextPush) -> ContextAck:
        # 1. Payload size check
        try:
            payload_bytes = orjson.dumps(push.payload)
            if len(payload_bytes) > self._max_context_bytes:
                return ContextAck(
                    accepted=False,
                    status="rejected",
                    scope=push.scope,
                    context_id=push.context_id,
                    stored_version=0,
                    reason=f"payload_exceeds_max_bytes_{self._max_context_bytes}",
                )
        except Exception as e:
            return ContextAck(
                accepted=False,
                status="rejected",
                scope=push.scope,
                context_id=push.context_id,
                stored_version=0,
                reason=f"serialization_error_{str(e)}",
            )

        with self._write_lock:
            cur = self._snapshot

            container_map = {
                "category": cur.categories,
                "merchant": cur.merchants,
                "customer": cur.customers,
                "trigger": cur.triggers,
            }
            container = container_map[push.scope]
            existing = container.get(push.context_id)

            if existing is not None and push.version <= existing.version:
                return ContextAck(
                    accepted=True,
                    status="noop",
                    scope=push.scope,
                    context_id=push.context_id,
                    stored_version=existing.version,
                    ack_id=f"ack_{push.context_id}_v{existing.version}",
                    stored_at=existing.stored_at.isoformat(),
                    reason="version_already_present",
                )

            # Copy on write
            new_cats = dict(cur.categories)
            new_merchants = dict(cur.merchants)
            new_customers = dict(cur.customers)
            new_triggers = dict(cur.triggers)

            stored_at = datetime.now(timezone.utc)
            record = ContextRecord(
                scope=push.scope,
                context_id=push.context_id,
                version=push.version,
                payload=MappingProxyType(push.payload),
                stored_at=stored_at,
            )

            if push.scope == "category":
                new_cats[push.context_id] = record
            elif push.scope == "merchant":
                new_merchants[push.context_id] = record
            elif push.scope == "customer":
                new_customers[push.context_id] = record
            elif push.scope == "trigger":
                new_triggers[push.context_id] = record

            # Secondary indexes
            cust_by_m: Dict[str, Set[str]] = {k: set(v) for k, v in cur.customers_by_merchant.items()}
            trig_by_m: Dict[str, Set[str]] = {k: set(v) for k, v in cur.triggers_by_merchant.items()}
            merch_by_c: Dict[str, Set[str]] = {k: set(v) for k, v in cur.merchants_by_category.items()}

            if push.scope == "merchant":
                cslug = push.payload.get("category_slug")
                if cslug:
                    merch_by_c.setdefault(cslug, set()).add(push.context_id)
            elif push.scope == "customer":
                mid = push.payload.get("merchant_id")
                if mid:
                    cust_by_m.setdefault(mid, set()).add(push.context_id)
            elif push.scope == "trigger":
                mid = push.payload.get("merchant_id")
                if mid:
                    trig_by_m.setdefault(mid, set()).add(push.context_id)

            new_counts = {
                "category": len(new_cats),
                "merchant": len(new_merchants),
                "customer": len(new_customers),
                "trigger": len(new_triggers),
            }

            self._snapshot = StoreSnapshot(
                categories=MappingProxyType(new_cats),
                merchants=MappingProxyType(new_merchants),
                customers=MappingProxyType(new_customers),
                triggers=MappingProxyType(new_triggers),
                customers_by_merchant=MappingProxyType({k: tuple(sorted(v)) for k, v in cust_by_m.items()}),
                triggers_by_merchant=MappingProxyType({k: tuple(sorted(v)) for k, v in trig_by_m.items()}),
                merchants_by_category=MappingProxyType({k: tuple(sorted(v)) for k, v in merch_by_c.items()}),
                counts=MappingProxyType(new_counts),
            )

            return ContextAck(
                accepted=True,
                status="stored",
                scope=push.scope,
                context_id=push.context_id,
                stored_version=push.version,
                ack_id=f"ack_{push.context_id}_v{push.version}",
                stored_at=stored_at.isoformat(),
            )

    def get(self, scope: Scope, context_id: str) -> Optional[dict[str, Any]]:
        record = self.get_record(scope, context_id)
        return dict(record.payload) if record else None

    def get_record(self, scope: Scope, context_id: str) -> Optional[ContextRecord]:
        cur = self._snapshot
        if scope == "category":
            return cur.categories.get(context_id)
        elif scope == "merchant":
            return cur.merchants.get(context_id)
        elif scope == "customer":
            return cur.customers.get(context_id)
        elif scope == "trigger":
            return cur.triggers.get(context_id)
        return None

    def get_version(self, scope: Scope, context_id: str) -> int:
        record = self.get_record(scope, context_id)
        return record.version if record else 0

    def get_category(self, slug: str) -> Optional[dict[str, Any]]:
        return self.get("category", slug)

    def get_merchant(self, merchant_id: str) -> Optional[dict[str, Any]]:
        return self.get("merchant", merchant_id)

    def get_customer(self, customer_id: str) -> Optional[dict[str, Any]]:
        return self.get("customer", customer_id)

    def get_trigger(self, trigger_id: str) -> Optional[dict[str, Any]]:
        return self.get("trigger", trigger_id)

    def get_counts(self) -> dict[str, int]:
        return dict(self._snapshot.counts)

    def get_customers_for_merchant(self, merchant_id: str) -> List[dict[str, Any]]:
        cur = self._snapshot
        cids = cur.customers_by_merchant.get(merchant_id, ())
        return [dict(cur.customers[cid].payload) for cid in cids if cid in cur.customers]

    def get_triggers_for_merchant(self, merchant_id: str) -> List[dict[str, Any]]:
        cur = self._snapshot
        tids = cur.triggers_by_merchant.get(merchant_id, ())
        return [dict(cur.triggers[tid].payload) for tid in tids if tid in cur.triggers]

    def get_merchants_for_category(self, category_slug: str) -> List[dict[str, Any]]:
        cur = self._snapshot
        mids = cur.merchants_by_category.get(category_slug, ())
        return [dict(cur.merchants[mid].payload) for mid in mids if mid in cur.merchants]

    def get_all_merchants(self) -> Dict[str, dict[str, Any]]:
        cur = self._snapshot
        return {k: dict(v.payload) for k, v in cur.merchants.items()}

    def get_all_triggers(self) -> Dict[str, dict[str, Any]]:
        cur = self._snapshot
        return {k: dict(v.payload) for k, v in cur.triggers.items()}

    def clear(self) -> None:
        with self._write_lock:
            self._snapshot = _empty_snapshot()
