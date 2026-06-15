from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.service import get_current_user_from_token
from app.models import Subscription
from app.usage.service import get_usage_quota

from .schemas import BillingSummaryRead


def get_billing_summary(db: Session, user_id: str) -> BillingSummaryRead:
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    quota = get_usage_quota(db, user_id)
    if sub is None:
        return BillingSummaryRead(
            plan=quota.plan,
            status="active",
            stripe_customer_id=None,
            monthly_workflow_limit=quota.monthly_workflow_limit,
            monthly_workflow_used=quota.monthly_workflow_used,
            monthly_workflow_remaining=quota.monthly_workflow_remaining,
            trial_window_start=quota.trial_window_start,
        )
    return BillingSummaryRead(
        plan=sub.plan,
        status=sub.status,
        stripe_customer_id=sub.stripe_customer_id,
        monthly_workflow_limit=quota.monthly_workflow_limit,
        monthly_workflow_used=quota.monthly_workflow_used,
        monthly_workflow_remaining=quota.monthly_workflow_remaining,
        trial_window_start=quota.trial_window_start,
    )
