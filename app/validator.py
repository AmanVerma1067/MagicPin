from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.facts import GroundedFacts
from app.playbooks import get_playbook

NUM_TOKEN_RE = re.compile(r"₹?\d[\d,]*(?:\.\d+)?%?")


@dataclass
class ValidationResult:
    is_valid: bool
    reasons: List[str] = field(default_factory=list)
    cleaned_body: str = ""
    cta: str = ""


def _normalize_num_token(token: str) -> str:
    return token.replace("₹", "").replace("%", "").replace(",", "").strip()


def validate_grounding_and_format(
    body: str,
    cta: str,
    facts: GroundedFacts,
) -> ValidationResult:
    reasons: List[str] = []
    body_clean = body.strip()

    # 1. Length constraint: 80 to 280 characters
    char_len = len(body_clean)
    if char_len < 80:
        reasons.append(f"Length violation: message length {char_len} is under minimum 80 characters.")
    elif char_len > 280:
        reasons.append(f"Length violation: message length {char_len} exceeds maximum 280 characters.")

    # 2. Extract and check numeric tokens
    tokens = NUM_TOKEN_RE.findall(body_clean)
    if not tokens:
        reasons.append("Missing anchor number: message must cite at least one verifiable metric, price, %, or date.")
    else:
        for t in tokens:
            norm = _normalize_num_token(t)
            # Accept if token or its normalized value, currency, or % matches allowed numbers
            is_allowed = (
                t in facts.allowed_numbers
                or norm in facts.allowed_numbers
                or f"₹{norm}" in facts.allowed_numbers
                or f"{norm}%" in facts.allowed_numbers
            )
            if not is_allowed:
                reasons.append(f"Unverified number: token '{t}' is not present in injected context facts.")

    # 3. Merchant personalization check
    lower_body = body_clean.lower()
    has_merchant_identity = False

    names_to_check = [
        facts.merchant_name.lower(),
        facts.owner_name.lower(),
        facts.salutation.lower(),
    ]
    # For Dr. Meera, also check "dr. meera" or "meera"
    if facts.salutation:
        names_to_check.append(facts.salutation.replace("Dr. ", "").lower())

    for n in names_to_check:
        if n and n in lower_body:
            has_merchant_identity = True
            break

    if not has_merchant_identity:
        reasons.append(
            f"Personalization missing: message must address merchant by name or salutation ('{facts.salutation}' or '{facts.merchant_name}')."
        )

    # 4. Taboos and banned phrases
    playbook = get_playbook(facts.category_slug)
    all_banned = set(playbook.banned_phrases + facts.banned_taboos)
    for banned in all_banned:
        b_clean = banned.lower().strip()
        if b_clean and b_clean in lower_body:
            reasons.append(f"Taboo violation: found banned phrase '{banned}'.")

    # 5. Catalog offer title consistency
    # If the message mentions a price with rupee symbol, verify it matches an active catalog offer
    rupee_prices = [t for t in tokens if "₹" in t or (t.isdigit() and int(t) > 50)]
    if rupee_prices and facts.catalog_titles:
        # Check if the text matches any known catalog title with acceptable similarity
        matched_any = False
        for title in facts.catalog_titles:
            # Check direct inclusion or high similarity
            title_clean = title.lower()
            if any(word in lower_body for word in title_clean.split() if len(word) > 4):
                matched_any = True
                break
            # Fuzzy match on title
            ratio = difflib.SequenceMatcher(None, title_clean, lower_body).quick_ratio()
            if ratio > 0.4:
                matched_any = True
                break
        if not matched_any and len(facts.catalog_titles) > 0:
            reasons.append("Catalog mismatch: mentioned price/offer does not align with active catalog items.")

    # 6. CTA check: must have a clear closing ask (ends with ? or provides binary choice)
    if "?" not in body_clean and "?" not in cta and not any(k in lower_body for k in ["reply", "yes", "confirm", "want me to", "should i"]):
        reasons.append("CTA missing: message must end with a clear low-friction question or action prompt.")

    return ValidationResult(
        is_valid=len(reasons) == 0,
        reasons=reasons,
        cleaned_body=body_clean,
        cta=cta.strip() if cta else "binary_yes_no",
    )
