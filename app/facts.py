from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class GroundedFacts:
    merchant_name: str
    owner_name: str
    locality: str
    city: str
    category_slug: str
    salutation: str
    metrics: Dict[str, Any]
    peer_stats: Dict[str, Any]
    active_offers: List[Dict[str, Any]]
    digest_item: Optional[Dict[str, Any]]
    trigger_kind: str
    trigger_payload: Dict[str, Any]
    customer_name: Optional[str]
    customer_last_visit: Optional[str]
    allowed_numbers: Set[str] = field(default_factory=set)
    catalog_titles: List[str] = field(default_factory=list)
    banned_taboos: List[str] = field(default_factory=list)
    summary_text: str = ""


_NUM_RE = re.compile(r"₹?\d[\d,]*(?:\.\d+)?%?")


def _extract_all_numeric_tokens(obj: Any, token_set: Set[str]) -> None:
    """Recursively harvest all numbers, prices, percentages, and dates from context object."""
    if obj is None:
        return
    if isinstance(obj, (int, float)):
        s = str(obj)
        token_set.add(s)
        if isinstance(obj, float):
            token_set.add(f"{obj:.1f}")
            token_set.add(f"{obj:.2f}")
            token_set.add(f"{obj:.3f}")
            # Deltas are stored signed (-0.5); messages cite magnitude ("fell 50%").
            for val in {obj, abs(obj)}:
                pct1 = f"{val * 100:.0f}%"
                pct2 = f"{val * 100:.1f}%"
                token_set.add(pct1)
                token_set.add(pct2)
                token_set.add(pct1.rstrip("%"))
                token_set.add(pct2.rstrip("%"))
        elif isinstance(obj, int):
            token_set.add(f"₹{obj}")
            token_set.add(f"₹{obj:,}")
            token_set.add(f"{obj:,}")
            token_set.add(f"{obj}%")
            token_set.add(str(abs(obj)))
        return

    if isinstance(obj, str):
        matches = _NUM_RE.findall(obj)
        for m in matches:
            token_set.add(m)
            clean = m.replace("₹", "").replace("%", "").replace(",", "")
            if clean:
                token_set.add(clean)
                token_set.add(f"₹{clean}")
                token_set.add(f"{clean}%")
                try:
                    val = float(clean)
                    if val.is_integer():
                        token_set.add(f"{int(val):,}")
                        token_set.add(f"₹{int(val):,}")
                except ValueError:
                    pass

        date_matches = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", obj)
        for d in date_matches:
            token_set.add(d)
        return

    if isinstance(obj, dict):
        for v in obj.values():
            _extract_all_numeric_tokens(v, token_set)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _extract_all_numeric_tokens(v, token_set)


_PRICE_RE = re.compile(r"₹\s?(\d[\d,]*)")


def parse_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Split an offer title like 'Dental Cleaning @ ₹299' into service + price.

    price is the display string ('299', '1,499') or None for free/percentage offers.
    """
    title = (offer.get("title") or "").strip()
    service = title.split("@")[0].strip() if "@" in title else title
    m = _PRICE_RE.search(title)
    price = m.group(1) if m else None
    if price is None:
        raw = str(offer.get("value") or "").replace(",", "")
        if raw.isdigit() and int(raw) > 0 and "%" not in title:
            price = f"{int(raw):,}"
    return {"title": title, "service": service, "price": price}


def extract_facts(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
) -> GroundedFacts:
    """Extract flat, structured, verifiable facts from the 4 contexts."""
    allowed: Set[str] = set()

    _extract_all_numeric_tokens(category, allowed)
    _extract_all_numeric_tokens(merchant, allowed)
    _extract_all_numeric_tokens(trigger, allowed)
    if customer:
        _extract_all_numeric_tokens(customer, allowed)

    identity = merchant.get("identity", {})
    m_name = identity.get("name", "Merchant")
    owner_first = identity.get("owner_first_name", "")
    locality = identity.get("locality", "")
    city = identity.get("city", "")
    c_slug = merchant.get("category_slug", category.get("slug", "retail"))

    if c_slug == "dentists":
        if owner_first.lower().startswith("dr"):
            salutation = owner_first
        elif owner_first:
            salutation = f"Dr. {owner_first}"
        else:
            salutation = "Doctor"
    else:
        salutation = owner_first if owner_first else m_name

    metrics = merchant.get("performance", {})
    peer_stats = category.get("peer_stats", {})

    active_offers = []
    catalog_titles = []
    for off in merchant.get("offers", []):
        if off.get("status") == "active":
            active_offers.append(off)
            catalog_titles.append(off.get("title", ""))
    for off in category.get("offer_catalog", []):
        catalog_titles.append(off.get("title", ""))

    voice = category.get("voice", {})
    taboos = voice.get("vocab_taboo", []) + voice.get("taboos", [])

    trg_kind = trigger.get("kind", "general_nudge")
    trg_payload = trigger.get("payload", {})

    top_item_id = (
        trg_payload.get("top_item_id")
        or trg_payload.get("digest_item_id")
        or trg_payload.get("alert_id")
    )
    digest_item = None
    if top_item_id:
        for d in category.get("digest", []):
            if d.get("id") == top_item_id:
                digest_item = d
                break

    cust_name = None
    cust_last_visit = None
    if customer:
        cust_name = customer.get("identity", {}).get("name")
        cust_last_visit = customer.get("relationship", {}).get("last_visit")

    summary_parts = [
        f"Merchant: {m_name} ({locality}, {city})",
        f"Owner: {salutation}",
        f"Category: {c_slug}",
        f"Trigger: {trg_kind} (urgency {trigger.get('urgency', 1)})",
    ]
    if digest_item:
        summary_parts.append(
            f"Digest Source: {digest_item.get('source', '')} - {digest_item.get('title', '')}"
        )
    if active_offers:
        summary_parts.append(f"Active Offer: {active_offers[0].get('title', '')}")

    return GroundedFacts(
        merchant_name=m_name,
        owner_name=owner_first,
        locality=locality,
        city=city,
        category_slug=c_slug,
        salutation=salutation,
        metrics=metrics,
        peer_stats=peer_stats,
        active_offers=active_offers,
        digest_item=digest_item,
        trigger_kind=trg_kind,
        trigger_payload=trg_payload,
        customer_name=cust_name,
        customer_last_visit=cust_last_visit,
        allowed_numbers=allowed,
        catalog_titles=[t for t in catalog_titles if t],
        banned_taboos=taboos,
        summary_text=" | ".join(summary_parts),
    )
