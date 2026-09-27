from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.facts import GroundedFacts, parse_offer

MIN_LEN = 80
MAX_LEN = 280

# Offer keywords that best fit a trigger kind (first catalog/active match wins).
_KIND_OFFER_HINTS: Dict[str, List[str]] = {
    "ipl_match_today": ["match", "combo"],
    "festival_upcoming": ["combo", "family", "bridal", "off"],
    "wedding_package_followup": ["bridal", "spa", "keratin"],
    "recall_due": ["cleaning", "checkup", "check"],
    "chronic_refill_due": ["refill", "delivery", "diabetic"],
    "customer_lapsed_hard": ["month", "trial", "personal"],
    "trial_followup": ["month", "trial", "personal"],
    "competitor_opened": ["cleaning", "consultation"],
}


def _human(token: Any) -> str:
    s = str(token).replace("_", " ").strip()
    return re.sub(r"\b(\d+)day\b", r"\1-day", s)


def _window(w: Any) -> str:
    m = re.fullmatch(r"(\d+)d", str(w or ""))
    return f"the last {m.group(1)} days" if m else (str(w) if w else "the last week")


def _pct(frac: Any) -> Optional[str]:
    if not isinstance(frac, (int, float)):
        return None
    return f"{abs(frac) * 100:.0f}%"


def _num(v: Any) -> Optional[str]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return f"{v:,}" if isinstance(v, int) else str(v)


def pick_in_window(variants: Iterable[Optional[str]]) -> str:
    """First variant inside the 80–280 char window; otherwise the closest one."""
    cands = [v.strip() for v in variants if v]
    for v in cands:
        if MIN_LEN <= len(v) <= MAX_LEN:
            return v
    fitting_max = [v for v in cands if len(v) <= MAX_LEN]
    if fitting_max:
        return max(fitting_max, key=len)
    return min(cands, key=len)[: MAX_LEN - 1].rstrip() + "?"


def all_offers(facts: GroundedFacts) -> List[Dict[str, Any]]:
    """Merchant's active offers first, then the category catalog."""
    seen = set()
    out = []
    for o in facts.active_offers:
        p = parse_offer(o)
        p["active"] = True
        if p["title"] and p["title"] not in seen:
            seen.add(p["title"])
            out.append(p)
    for t in facts.catalog_titles:
        if t not in seen:
            seen.add(t)
            p = parse_offer({"title": t})
            p["active"] = False
            out.append(p)
    return out


def _best_offer(facts: GroundedFacts, hints: Iterable[str] = ()) -> Optional[Dict[str, Any]]:
    offers = all_offers(facts)
    if not offers:
        return None
    for h in hints:
        for o in offers:
            if h in o["title"].lower():
                return o
    return offers[0]


def offer_phrase(o: Optional[Dict[str, Any]]) -> str:
    if not o:
        return ""
    if o.get("price"):
        return f"{o['service']} at ₹{o['price']}"
    return o["title"]


def traffic_clause(facts: GroundedFacts) -> Optional[str]:
    views = _num(facts.metrics.get("views"))
    peer = _num(facts.peer_stats.get("avg_views_30d"))
    days = _num(facts.metrics.get("window_days"))
    span = f" in {days} days" if days else " recently"
    if not views:
        return None
    # Peer average is a 30-day figure; only compare like with like.
    if peer and facts.metrics.get("window_days") in (None, 30):
        return f"{views} views{span} vs peer avg {peer}"
    return f"{views} views{span}"


_TRAILING_STOP = {"with", "in", "for", "vs", "of", "and", "at", "to", "on", "the", "a"}


def _outcome_from_summary(summary: str) -> Optional[str]:
    m = re.search(r"(\d+(?:\.\d+)?%\s+(?:[\w-]+\s+){0,3}[\w-]+)", summary or "")
    if not m:
        return None
    words = m.group(1).split()
    while len(words) > 1 and words[-1].lower() in _TRAILING_STOP:
        words.pop()
    return " ".join(words)


def render_fallback_template(facts: GroundedFacts) -> Tuple[str, str, str]:
    """
    Generate guaranteed grounded, valid fallback message for any (category, trigger_type).
    Every number is read from the pushed context. Returns (body, cta, rationale).
    """
    kind = facts.trigger_kind or ""
    p = facts.trigger_payload or {}
    if p.get("placeholder"):
        # Synthetic trigger with no real signal: use the merchant's own numbers instead.
        kind = "_default"
    sal = facts.salutation
    m_name = facts.merchant_name
    loc = facts.locality or facts.city or "your area"
    cust = facts.customer_name
    offer = _best_offer(facts, _KIND_OFFER_HINTS.get(kind, ()))
    off = offer_phrase(offer)
    traffic = traffic_clause(facts)
    cta = "binary_yes_no"

    def done(variants: List[Optional[str]], why: str) -> Tuple[str, str, str]:
        return pick_in_window(variants), cta, why

    # 1. Research digest / CDE
    if kind in ("research_digest", "cde_opportunity") and facts.digest_item:
        d = facts.digest_item
        src = d.get("source", "")
        title = d.get("title", "")
        n = _num(d.get("trial_n"))
        n_str = f" (N={n})" if n else ""
        if kind == "cde_opportunity":
            credits = _num(p.get("credits"))
            fee = _human(p.get("fee", "")) if p.get("fee") else ""
            extra = ", ".join(x for x in [f"{credits} CDE credits" if credits else "", fee] if x)
            return done([
                f"{sal}, {title} ({src}){' — ' + extra if extra else ''}. Shall I block a seat for you?",
                f"{sal}, {title}{' — ' + extra if extra else ''}. Shall I block a seat for you?",
            ], f"CDE opportunity from {src}.")
        outcome = _outcome_from_summary(d.get("summary", ""))
        out_str = f": {outcome}" if outcome else ""
        return done([
            f"{sal}, {src} — {title}{n_str}{out_str}. Want me to pull the abstract + draft a patient WhatsApp note?",
            f"{sal}, new {src} trial{n_str}{out_str}. Want me to pull the abstract + draft a patient WhatsApp note?",
            f"{sal}, {src}{n_str}{out_str}. Want the abstract?",
        ], f"Research digest from {src}{n_str} relevant to {m_name}'s patient base.")

    # 2. Regulation / compliance
    if "regulation" in kind or "compliance" in kind:
        d = facts.digest_item or {}
        src = d.get("source", "")
        title = d.get("title", _human(kind))
        deadline = p.get("deadline_iso", "")
        dl = f" Deadline: {deadline}." if deadline and deadline not in title else ""
        return done([
            f"{sal}, {src} update: {title}.{dl} Want me to send {m_name} the 1-page compliance checklist?",
            f"{sal}, {title}.{dl} Want me to send the 1-page compliance checklist?",
            f"{sal}, new compliance rule from {src}.{dl} Want me to send the 1-page checklist?",
        ], f"Regulatory change{(' due ' + deadline) if deadline else ''}.")

    # 3. Supply / batch recall
    if kind == "supply_alert":
        mol = p.get("molecule", "")
        batches = ", ".join(p.get("affected_batches", [])[:3])
        mfr = p.get("manufacturer", "")
        return done([
            f"{sal}, {mfr} recall: {mol} batches {batches}. Please quarantine this stock at {m_name}. Shall I draft the WhatsApp alert for customers who bought it?",
            f"{sal}, {mol} recall on batches {batches}. Shall I draft the customer WhatsApp alert?",
        ], f"Batch safety alert for {mol} ({batches}).")

    # 4. Chronic refill
    if kind == "chronic_refill_due" and p.get("molecule_list"):
        mols = ", ".join(p.get("molecule_list", [])[:3])
        runs_out = str(p.get("stock_runs_out_iso", ""))[:10]
        last = p.get("last_refill", "")
        who = cust or "a chronic patient"
        deliv = " to the saved address" if p.get("delivery_address_saved") else ""
        return done([
            f"{sal}, {who}'s {mols} refill runs out on {runs_out} (last refill {last}). Shall I send the refill reminder with home delivery{deliv}?",
            f"{sal}, {who}'s {mols} stock runs out on {runs_out}. Shall I send the refill reminder?",
        ], f"Chronic refill continuity before {runs_out}.")

    # 5. Google profile unverified
    if kind == "gbp_unverified":
        up = _pct(p.get("estimated_uplift_pct"))
        path = _human(p.get("verification_path", "postcard or phone call"))
        up_str = f" — verifying is estimated to lift visibility by {up}" if up else ""
        return done([
            f"{sal}, {m_name}'s Google profile is still unverified{up_str}. It only needs a {path}. Shall I start verification today?",
            f"{sal}, {m_name}'s Google profile is unverified{up_str}. Shall I start verification today?",
        ], "Unverified Google profile suppresses discovery.")

    # 6. Performance dip / spike
    if "perf_dip" in kind or "drop" in kind:
        metric = p.get("metric", "views")
        delta = _pct(p.get("delta_pct"))
        window = _window(p.get("window"))
        base = _num(p.get("vs_baseline"))
        base_str = f" (baseline {base})" if base else ""
        push = f"push your {off}" if off else "run a promotional push"
        views, peer = facts.metrics.get("views"), facts.peer_stats.get("avg_views_30d")
        below_peer = isinstance(views, (int, float)) and isinstance(peer, (int, float)) and views < peer
        goal = "restore traffic" if below_peer or not p.get("is_expected_seasonal") else "hold your lead"
        head = f"{sal}, {metric} at {m_name} fell {delta} over {window}{base_str}." if delta else f"{sal}, {metric} at {m_name} dipped over {window}."
        if p.get("is_expected_seasonal"):
            head += " It's the expected seasonal dip."
        tr = f" You're at {traffic}." if traffic else ""
        return done([
            f"{head}{tr} Shall we {push} to {goal} in {loc}?",
            f"{head} Shall we {push} to {goal} in {loc}?",
            f"{head} Shall we {push}?",
        ], f"Performance dip on {metric} ({delta or 'n/a'}) with a concrete recovery offer.")

    if kind == "perf_spike":
        metric = p.get("metric", "views")
        delta = _pct(p.get("delta_pct"))
        window = _window(p.get("window"))
        driver = _human(p.get("likely_driver", "")) if p.get("likely_driver") else ""
        drv = f", likely from your {driver}" if driver else ""
        dbl = f" with {off}" if off else ""
        return done([
            f"{sal}, {metric} at {m_name} jumped {delta} over {window}{drv}. Shall we double down{dbl} while {loc} demand is hot?",
            f"{sal}, {metric} jumped {delta} over {window}{drv}. Shall we double down{dbl}?",
        ], f"Momentum on {metric} (+{delta}); amplify the driver.")

    # 7. Customer recall / lapse / winback / trial follow-up
    if kind == "recall_due":
        who = cust or "a patient"
        svc = _human(p.get("service_due", "checkup"))
        due = p.get("due_date", "")
        last = p.get("last_service_date") or facts.customer_last_visit or ""
        slots = p.get("available_slots") or []
        slot = f" Open slot: {slots[0].get('label')}." if slots and slots[0].get("label") else ""
        with_off = f" with your {off}" if off else ""
        return done([
            f"{sal}, {who} is due for a {svc} on {due} (last visit {last}).{slot} Shall I send the recall reminder{with_off}?",
            f"{sal}, {who} is due for a {svc} on {due}.{slot} Shall I send the recall reminder?",
        ], f"Recall due {due} for {who}.")

    if kind == "customer_lapsed_hard" or "lapsed" in kind:
        who = cust or "a regular member"
        days = _num(p.get("days_since_last_visit"))
        focus = _human(p.get("previous_focus", "")) if p.get("previous_focus") else ""
        months = _num(p.get("previous_membership_months"))
        hist = f" after {months} months of {focus}" if months and focus else ""
        gap = f"hasn't visited in {days} days" if days else f"hasn't visited since {facts.customer_last_visit}"
        with_off = f" with {off}" if off else ""
        return done([
            f"{sal}, {who} {gap}{hist}. Shall I send a personal winback note{with_off}?",
            f"{sal}, {who} {gap}. Shall I send a winback note{with_off}?",
        ], f"Hard-lapsed customer winback for {who}.")

    if kind == "winback_eligible":
        days = _num(p.get("days_since_expiry"))
        dip = _pct(p.get("perf_dip_pct"))
        lapsed = _num(p.get("lapsed_customers_added_since_expiry"))
        bits = []
        if lapsed:
            bits.append(f"{lapsed} customers have lapsed")
        if dip:
            bits.append(f"traffic is down {dip}")
        tail = f" Since then {' and '.join(bits)}." if bits else ""
        return done([
            f"{sal}, it's been {days} days since {m_name}'s magicpin plan expired.{tail} Shall I reactivate it with {off or 'your top offer'}?",
            f"{sal}, {m_name}'s plan expired {days} days ago.{tail} Shall I reactivate it?",
        ], "Winback: expired subscription with measurable decay.")

    if kind == "trial_followup":
        who = cust or "your trial customer"
        tdate = p.get("trial_date", "")
        opts = p.get("next_session_options") or []
        nxt = f" Next open session: {opts[0].get('label')}." if opts and opts[0].get("label") else ""
        with_off = f" with {off}" if off else ""
        return done([
            f"{sal}, {who} took a trial on {tdate}.{nxt} Shall I send them the booking nudge{with_off}?",
            f"{sal}, {who} took a trial on {tdate}.{nxt} Shall I send the booking nudge?",
        ], f"Trial follow-up for {who}.")

    if kind == "wedding_package_followup":
        who = cust or "your bridal client"
        wdate = p.get("wedding_date", "")
        days = _num(p.get("days_to_wedding"))
        step = _human(p.get("next_step_window_open", "")) if p.get("next_step_window_open") else "next prep step"
        dstr = f" ({days} days away)" if days else ""
        with_off = f" alongside {off}" if off else ""
        return done([
            f"{sal}, {who}'s wedding is on {wdate}{dstr} and the trial is done. Shall I send them the {step} plan{with_off}?",
            f"{sal}, {who}'s wedding is on {wdate}{dstr}. Shall I send the {step} plan?",
        ], f"Bridal pipeline follow-up before {wdate}.")

    # 8. Renewal
    if kind == "renewal_due":
        days = _num(p.get("days_remaining"))
        plan = p.get("plan", "")
        amt = _num(p.get("renewal_amount"))
        amt_str = f" (₹{amt})" if amt else ""
        tr = f" This month: {traffic}." if traffic else ""
        return done([
            f"{sal}, {m_name}'s {plan} plan renews in {days} days{amt_str}.{tr} Shall I renew it now so your listing stays live?",
            f"{sal}, your {plan} plan renews in {days} days{amt_str}. Shall I renew it now?",
        ], f"Renewal due in {days} days.")

    # 9. Seasonal / festival / match
    if kind == "ipl_match_today" or "match" in kind:
        match = p.get("match", "tonight's match")
        venue = p.get("venue", "")
        t = str(p.get("match_time_iso", ""))
        hhmm = t[11:16] if len(t) >= 16 else ""
        at = f" at {venue}" if venue else ""
        when = f", {hhmm}" if hhmm else ""
        push = off or "a match-night combo"
        return done([
            f"{sal}, {match}{at} tonight{when}. Shall I push your {push} to diners in {loc} before the first ball?",
            f"{sal}, {match} tonight{when}. Shall I push your {push} to {loc} diners?",
        ], f"Same-day IPL demand spike ({match}).")

    if kind == "festival_upcoming" or "festival" in kind:
        fest = p.get("festival", "the festival")
        date = p.get("date", "")
        days = _num(p.get("days_until"))
        dstr = f" ({days} days out)" if days else ""
        push = off or "a festive offer"
        return done([
            f"{sal}, {fest} is on {date}{dstr}. Shall I line up your {push} for {fest} bookings in {loc}?",
            f"{sal}, {fest} is on {date}. Shall I line up your {push}?",
        ], f"Festival window: {fest} {date}.")

    if kind == "category_seasonal" or "seasonal" in kind:
        trends = []
        for tr in p.get("trends", [])[:3]:
            m = re.match(r"(.+?)_demand_([+-]\d+)", str(tr))
            if m:
                trends.append(f"{_human(m.group(1))} {m.group(2)}%")
        season = _human(p.get("season", "this season"))
        tstr = ", ".join(trends)
        return done([
            f"{sal}, {season} demand shift near {loc}: {tstr}. Shall I update {m_name}'s shelf spotlight to match?",
            f"{sal}, {season} demand: {tstr}. Shall I update your shelf spotlight?",
        ], f"Seasonal demand shift ({season}).")

    # 10. Reviews / milestones / competition
    if kind == "review_theme_emerged":
        theme = _human(p.get("theme", "service"))
        occ = _num(p.get("occurrences_30d"))
        quote = str(p.get("common_quote", "")).replace('"', "'")
        q = f" — '{quote}'" if quote else ""
        return done([
            f"{sal}, {occ} reviews in 30 days mention {theme}{q}. Shall I draft a public reply and a fix note for your team?",
            f"{sal}, {occ} recent reviews mention {theme}. Shall I draft a public reply?",
        ], f"Emerging negative review theme: {theme}.")

    if kind == "milestone_reached" and p.get("value_now") is not None:
        now_v = _num(p.get("value_now"))
        goal = _num(p.get("milestone_value"))
        metric = _human(p.get("metric", "review count"))
        at = f"{now_v} reviews" if metric == "review count" else f"{now_v} on {metric}"
        return done([
            f"{sal}, {m_name} is at {at}, just short of the {goal} mark. Shall I send a review request to your last few happy customers?",
            f"{sal}, {m_name} is at {now_v} {metric}, close to {goal}. Shall I send review requests?",
        ], f"Milestone within reach ({now_v}→{goal}).")

    if kind == "competitor_opened":
        comp = p.get("competitor_name", "A competitor")
        dist = _num(p.get("distance_km"))
        theirs = p.get("their_offer", "")
        opened = p.get("opened_date", "")
        d = f" {dist} km away" if dist else " nearby"
        t = f" with {theirs}" if theirs else ""
        counter = f"your {off}" if off else "a counter-offer"
        return done([
            f"{sal}, {comp} opened{d} on {opened}{t}. Shall we spotlight {counter} to hold searches in {loc}?",
            f"{sal}, {comp} opened{d}{t}. Shall we spotlight {counter}?",
        ], f"Competitive entry: {comp}.")

    # 11. Planning intent / curiosity / dormancy
    if kind == "active_planning_intent":
        topic = _human(p.get("intent_topic", "your plan"))
        words = [w for w in topic.lower().split() if len(w) > 3]
        o = _best_offer(facts, words) or offer
        anchor = f" anchored on {offer_phrase(o)}" if o else ""
        tr = f" You have {traffic} to seed it." if traffic else ""
        return done([
            f"{sal}, here's a first cut of the {topic}{anchor}.{tr} Shall I draft the full package for your review?",
            f"{sal}, first cut of the {topic}{anchor}. Shall I draft the full package?",
        ], f"Merchant is actively planning: {topic}.")

    if kind == "dormant_with_vera":
        days = _num(p.get("days_since_last_merchant_message"))
        topic = _human(p.get("last_topic", "")) if p.get("last_topic") else "your listing"
        tr = f" Meanwhile {m_name} had {traffic}." if traffic else ""
        return done([
            f"{sal}, it's been {days} days since we discussed {topic}.{tr} Shall I send a short plan to lift calls this week?",
            f"{sal}, it's been {days} days since we discussed {topic}. Shall I send a short plan?",
        ], "Re-engage dormant merchant with their own numbers.")

    # 12. Default: own traffic vs peers + best offer
    push = f"spotlight your {off}" if off else "refresh your listing"
    tr = traffic or f"peer rating avg {_num(facts.peer_stats.get('avg_rating')) or ''}".strip()
    return done([
        f"{sal}, {m_name} in {loc}: {tr}. Shall I {push} this week to grow inquiries?",
        f"{sal}, {tr}. Shall I {push} this week?",
        f"{sal}, {m_name} in {loc} has {tr}. Want me to {push} for the coming week so more nearby customers find you?",
    ], f"Grounded default nudge for {m_name} using own metrics vs peers.")
