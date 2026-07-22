"""Commercial plan constants shared by entitlement consumers."""

from __future__ import annotations


VALID_PLANS = frozenset({"starter", "professional", "enterprise"})
VALID_SUBSCRIPTION_STATUSES = frozenset(
    {
        "active",
        "trialing",
        "past_due",
        "canceled",
        "unpaid",
        "incomplete",
        "incomplete_expired",
        "paused",
    }
)
PREMIUM_ENTITLED_STATUSES = frozenset({"active", "trialing", "past_due"})
UNLIMITED_PLANS = frozenset({"professional", "enterprise"})

STARTER_PROJECT_LIMIT = 3
STARTER_OFFICIAL_WORKFLOW_LIMIT = 3
STARTER_OFFICIAL_ASSISTANT_LIMIT = 100
STARTER_OFFICIAL_INDEXING_LIMIT = 5

PLAN_PROJECT_LIMITS: dict[str, int] = {
    "starter": STARTER_PROJECT_LIMIT,
    "professional": -1,
    "enterprise": -1,
}


def normalized_effective_plan(plan: str, status: str) -> str:
    """Return the safely entitled plan, never trusting an inactive paid state."""
    if plan not in VALID_PLANS:
        return "starter"
    if plan in UNLIMITED_PLANS and status not in PREMIUM_ENTITLED_STATUSES:
        return "starter"
    return plan


def plan_limit(plan: str, starter_limit: int) -> int:
    return -1 if plan in UNLIMITED_PLANS else starter_limit
