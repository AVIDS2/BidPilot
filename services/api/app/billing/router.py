"""Billing router — checkout session creation and Stripe webhook handler."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.service import require_auth, update_subscription_command
from app.auth.schemas import CurrentUser
from app.adapters.stripe_adapter import (
    create_checkout_session,
    verify_webhook_signature,
    is_stripe_configured,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
def create_checkout(
    plan: str,
    current_user: CurrentUser = Depends(require_auth),
) -> dict:
    """Create a Stripe Checkout Session for upgrading to the given plan."""
    if not is_stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe is not configured on this deployment")

    if plan not in ("professional", "enterprise"):
        raise HTTPException(status_code=400, detail="Can only checkout professional or enterprise plans")

    try:
        result = create_checkout_session(
            user_id=current_user.id,
            user_email=current_user.email,
            plan=plan,
            success_url="http://localhost:5173/projects?checkout=success",
            cancel_url="http://localhost:5173/pricing?checkout=cancelled",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    return {"url": result.url, "session_id": result.session_id}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Handle Stripe webhook events.

    Processes:
      - checkout.session.completed → upgrade user subscription
      - customer.subscription.deleted → downgrade to starter
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Webhook verification failed")

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        metadata = session_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan", "professional")
        if user_id:
            try:
                update_subscription_command(db, user_id, plan)
            except ValueError:
                pass  # invalid plan, ignore

    elif event_type == "customer.subscription.deleted":
        sub_obj = event["data"]["object"]
        metadata = sub_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        if user_id:
            try:
                update_subscription_command(db, user_id, "starter")
            except ValueError:
                pass

    return {"received": True}
