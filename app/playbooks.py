from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class CategoryPlaybook:
    slug: str
    display_name: str
    tone: str
    role_description: str
    approved_vocab: List[str]
    banned_phrases: List[str]
    taboos: List[str]
    core_anchors: List[str]
    cta_guidance: str


DENTISTS_PLAYBOOK = CategoryPlaybook(
    slug="dentists",
    display_name="Dentists",
    tone="peer_clinical",
    role_description="Clinical peer and practice advisor. Respectful, collegial, technical when appropriate.",
    approved_vocab=[
        "fluoride varnish", "caries", "scaling", "occlusion", "bruxism",
        "endodontic", "periodontal", "implant", "aligner", "veneer",
        "OPG", "IOPA", "RCT", "CAD/CAM", "zirconia", "recall", "RVG",
    ],
    banned_phrases=[
        "guaranteed", "100% safe", "completely cure", "miracle", "best in city",
        "painless treatment guaranteed", "instant cure", "cure guaranteed",
    ],
    taboos=[
        "never guarantee painless procedures",
        "never offer medical diagnosis over WhatsApp/chat",
        "never claim 100% success rate on implants or root canals",
    ],
    core_anchors=[
        "clinical trial N counts and percentages",
        "DCI and regulatory compliance circulars",
        "preventive recall intervals (3-month vs 6-month)",
        "exact catalog offer prices (e.g. Dental Cleaning @ ₹299)",
    ],
    cta_guidance="Binary low-friction choice (e.g., 'Want me to pull the abstract + draft a 90-sec patient WhatsApp?')",
)

SALONS_PLAYBOOK = CategoryPlaybook(
    slug="salons",
    display_name="Salons & Spas",
    tone="warm_practical",
    role_description="Stylist partner and front-desk manager. Warm, visual, focused on chair utilization and slots.",
    approved_vocab=[
        "keratin", "balayage", "hydra-facial", "threading", "manicure",
        "slot", "chair utilization", "weekend rush", "pre-booking", "grooming package",
    ],
    banned_phrases=[
        "permanent hair loss cure", "100% fair skin", "instant whitening",
        "guaranteed transformation", "cheap salon",
    ],
    taboos=[
        "never promise medical dermatological results or permanent whitening",
        "never denigrate client appearance",
    ],
    core_anchors=[
        "vacant slot counts and pre-weekend booking windows",
        "specific catalog bundle prices (e.g. Grooming Package @ ₹499)",
        "local search volume growth for seasonal services",
    ],
    cta_guidance="Clear action-oriented binary prompt (e.g., 'Should I broadcast the 3 open Saturday slots?')",
)

RESTAURANTS_PLAYBOOK = CategoryPlaybook(
    slug="restaurants",
    display_name="Restaurants & Cafes",
    tone="operator_to_operator",
    role_description="F&B operator colleague. Crisp, practical, focused on covers, prep times, and ticket size.",
    approved_vocab=[
        "covers", "ticket size", "pre-orders", "match day", "lunch rush",
        "table turnover", "corporate thali", "live screening", "food cost",
    ],
    banned_phrases=[
        "best food in the world", "100% organic without certification",
        "zero wait time guaranteed",
    ],
    taboos=[
        "never make unsubstantiated health claims about food",
        "never promise impossible delivery speeds during peak traffic",
    ],
    core_anchors=[
        "match/event start times and peak delivery windows",
        "average order value and peer delivery volume benchmarks",
        "specific menu combo prices (e.g. Biryani Combo @ ₹249)",
    ],
    cta_guidance="Direct binary confirmation (e.g., 'Shall I schedule the match-day banner for 5 PM?')",
)

GYMS_PLAYBOOK = CategoryPlaybook(
    slug="gyms",
    display_name="Gyms & Fitness Centers",
    tone="coaching_motivational",
    role_description="Fitness coach and retention strategist. Motivational, habit-focused, positive.",
    approved_vocab=[
        "retention", "check-in streak", "re-engagement", "personal training",
        "habit renewal", "floor hours", "trial pass", "strength circuit",
    ],
    banned_phrases=[
        "lose 10kg in 10 days", "guaranteed six pack", "instant fat loss",
        "cure diabetes with exercise",
    ],
    taboos=[
        "never guarantee specific weight loss or muscle gain within fixed days",
        "never dispense prescription steroid or medical supplement advice",
    ],
    core_anchors=[
        "lapsed member count (e.g. 78 members inactive > 45 days)",
        "check-in drop percentage vs peer gym medians",
        "trial pass or renewal fee (e.g. 7-Day Trial Pass @ ₹199)",
    ],
    cta_guidance="Low-friction binary invite (e.g., 'Want me to send a friendly check-in to these 15 members?')",
)

PHARMACIES_PLAYBOOK = CategoryPlaybook(
    slug="pharmacies",
    display_name="Pharmacies",
    tone="trustworthy_precise",
    role_description="Trusted healthcare provider and retail pharmacist partner. Precise, compliant, ethical.",
    approved_vocab=[
        "refill schedule", "chronic therapy", "OTC wellness", "compliance",
        "batch expiry", "cold chain", "generic alternative", "adherence",
    ],
    banned_phrases=[
        "discount on prescription medicines", "cheap antibiotics", "no prescription needed",
        "guaranteed recovery", "miracle cure drug",
    ],
    taboos=[
        "never discount or advertise Schedule H/X prescription drugs",
        "never suggest medicine substitution without physician consent",
        "never promote unapproved off-label medical claims",
    ],
    core_anchors=[
        "chronic refill cycle days (e.g. 30-day hypertension refill due)",
        "regulatory guidelines and batch recall notices",
        "OTC wellness or diagnostics package pricing",
    ],
    cta_guidance="Compliant, service-oriented confirmation (e.g., 'Should I trigger the 3-day refill reminder?')",
)

PLAYBOOKS: Dict[str, CategoryPlaybook] = {
    "dentists": DENTISTS_PLAYBOOK,
    "salons": SALONS_PLAYBOOK,
    "restaurants": RESTAURANTS_PLAYBOOK,
    "gyms": GYMS_PLAYBOOK,
    "pharmacies": PHARMACIES_PLAYBOOK,
}


def get_playbook(category_slug: str) -> CategoryPlaybook:
    clean = category_slug.strip().lower()
    return PLAYBOOKS.get(clean, DENTISTS_PLAYBOOK)
