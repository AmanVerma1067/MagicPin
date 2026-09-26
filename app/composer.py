from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.facts import extract_facts, GroundedFacts
from app.llm import GeminiClient
from app.playbooks import get_playbook
from app.suppression import generate_suppression_key
from app.templates import render_fallback_template
from app.validator import validate_grounding_and_format

logger = logging.getLogger("vera.composer")


def _build_composer_prompt(facts: GroundedFacts, retry_reasons: Optional[list[str]] = None) -> Tuple[str, str]:
    playbook = get_playbook(facts.category_slug)

    system_instruction = f"""You are Vera, magicpin's intelligent merchant assistant for local businesses in India.
You compose WhatsApp messages for merchants across 5 verticals (dentists, salons, restaurants, gyms, pharmacies).

NON-NEGOTIABLE GROUNDING RULES:
1. ZERO HALLUCINATION: You may ONLY cite numbers, prices, percentages, counts, or dates explicitly listed in the FACTS SHEET below. Never invent metrics or cohort counts.
2. ADDRESS THE MERCHANT: Always start with the merchant's salutation: '{facts.salutation}'.
3. LENGTH: The message body MUST be between 80 and 280 characters. Be concise and crisp.
4. SPECIFICITY: Include at least one verifiable anchor number (price like ₹299, CTR like 2.1%, search query volume, or trial count) strictly from the facts sheet.
5. SINGLE LOW-FRICTION CTA: End with one clear binary question (e.g., 'Want me to pull the abstract + draft a 90-sec WhatsApp update?', 'Shall I schedule this offer for tomorrow?').
6. CATEGORY TONE ({playbook.slug}): {playbook.tone} — {playbook.role_description}.
7. TABOOS & BANNED PHRASES: Never use any of: {playbook.banned_phrases + facts.banned_taboos}.

Return valid JSON with:
- body: string (80-280 chars)
- cta: string (binary_yes_no)
- rationale: string (1-2 sentences explaining business rationale)
"""

    active_offer_titles = [o.get("title") for o in facts.active_offers if o.get("title")]
    prompt_lines = [
        "=== VERIFIABLE FACTS SHEET ===",
        f"Merchant: {facts.merchant_name} in {facts.locality}, {facts.city}",
        f"Salutation: {facts.salutation}",
        f"Category: {facts.category_slug}",
        f"Trigger: {facts.trigger_kind}",
        f"Trigger Details: {facts.trigger_payload}",
        f"Merchant Performance: views={facts.metrics.get('views', 'N/A')}, calls={facts.metrics.get('calls', 'N/A')}, ctr={facts.metrics.get('ctr', 'N/A')}",
        f"Peer Benchmarks: avg_ctr={facts.peer_stats.get('avg_ctr', 'N/A')}, avg_rating={facts.peer_stats.get('avg_rating', 'N/A')}, avg_views={facts.peer_stats.get('avg_views_30d', 'N/A')}",
        f"Active Catalog Offers: {active_offer_titles}",
    ]
    if facts.digest_item:
        prompt_lines.append(
            f"Digest Item: {facts.digest_item.get('title')} | Source: {facts.digest_item.get('source')} | Trial N: {facts.digest_item.get('trial_n', 'N/A')} | Summary: {facts.digest_item.get('summary')}"
        )
    if facts.customer_name:
        prompt_lines.append(
            f"Customer: {facts.customer_name} (Last Visit: {facts.customer_last_visit})"
        )

    prompt_lines.append(f"ALLOWED TOKENS: {sorted(list(facts.allowed_numbers))[:50]}")

    if retry_reasons:
        prompt_lines.append("\n=== PREVIOUS ATTEMPT FAILED HARD VALIDATION ===")
        for r in retry_reasons:
            prompt_lines.append(f"- FIX THIS ERROR: {r}")
        prompt_lines.append("Rewrite the message to strictly comply with all grounding and format constraints.")

    return system_instruction, "\n".join(prompt_lines)


async def compose(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
    gemini_client: Optional[GeminiClient] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Core engine composition entrypoint:
    compose(category, merchant, trigger, customer) -> OutboundAction dict
    """
    ref_time = now or datetime.now(timezone.utc)
    facts = extract_facts(category, merchant, trigger, customer)

    cat_slug = merchant.get("category_slug", category.get("slug", "retail"))
    trg_kind = trigger.get("kind", "nudge")
    mid = merchant.get("merchant_id", "m_unknown")
    tid = trigger.get("id", "trg_unknown")
    cid = customer.get("customer_id") if customer else trigger.get("customer_id")

    sup_key = trigger.get("suppression_key") or generate_suppression_key(trg_kind, cat_slug, mid, ref_time)

    # 1. Attempt LLM Generation if client available
    if gemini_client:
        system_instr, prompt = _build_composer_prompt(facts)
        comp = await gemini_client.generate_composition(prompt, system_instruction=system_instr)

        if comp:
            # Validate output
            v_res = validate_grounding_and_format(comp.body, comp.cta, facts)
            if v_res.is_valid:
                return {
                    "merchant_id": mid,
                    "customer_id": cid,
                    "trigger_id": tid,
                    "category": cat_slug,
                    "body": v_res.cleaned_body,
                    "cta": v_res.cta,
                    "send_as": "vera",
                    "suppression_key": sup_key,
                    "rationale": comp.rationale,
                }
            else:
                logger.info(f"LLM composition failed validation: {v_res.reasons}; retrying once...")
                # Retry once with validation feedback
                system_instr_retry, prompt_retry = _build_composer_prompt(facts, retry_reasons=v_res.reasons)
                comp_retry = await gemini_client.generate_composition(prompt_retry, system_instruction=system_instr_retry)
                if comp_retry:
                    v_res_retry = validate_grounding_and_format(comp_retry.body, comp_retry.cta, facts)
                    if v_res_retry.is_valid:
                        return {
                            "merchant_id": mid,
                            "customer_id": cid,
                            "trigger_id": tid,
                            "category": cat_slug,
                            "body": v_res_retry.cleaned_body,
                            "cta": v_res_retry.cta,
                            "send_as": "vera",
                            "suppression_key": sup_key,
                            "rationale": comp_retry.rationale,
                        }

    # 2. Fallback to verified deterministic template
    body, cta, rationale = render_fallback_template(facts)
    # Ensure fallback satisfies length and token constraints
    v_fallback = validate_grounding_and_format(body, cta, facts)
    final_body = v_fallback.cleaned_body if v_fallback.is_valid else body

    return {
        "merchant_id": mid,
        "customer_id": cid,
        "trigger_id": tid,
        "category": cat_slug,
        "body": final_body,
        "cta": cta,
        "send_as": "vera",
        "suppression_key": sup_key,
        "rationale": rationale,
    }
