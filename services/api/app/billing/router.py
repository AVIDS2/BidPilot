"""Billing router — checkout session creation and Stripe webhook handler."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.service import require_auth
from app.auth.schemas import CurrentUser
from app.core.settings import get_app_url
from app.entitlements.service import resolve_org_entitlements, upsert_organization_subscription_command
from app.models import OrganizationSubscription, Subscription
from app.adapters.stripe_adapter import (
    create_billing_portal_session,
    create_organization_checkout_session,
    verify_webhook_signature,
    is_stripe_configured,
)
from .service import process_stripe_webhook_event

router = APIRouter(prefix="/billing", tags=["billing"])


def _workspace_subscription_for_billing(
    db: Session,
    *,
    current_user: CurrentUser,
    create_if_missing: bool,
) -> OrganizationSubscription:
    """Return the sole organization subscription a billing owner may manage."""
    entitlement = resolve_org_entitlements(
        db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
    )
    if not entitlement.is_billing_owner:
        raise HTTPException(
            status_code=403,
            detail="Only the workspace billing owner can manage billing",
        )

    subscription = db.scalar(
        select(OrganizationSubscription).where(
            OrganizationSubscription.org_id == current_user.org_id
        )
    )
    if subscription is not None or not create_if_missing:
        if subscription is None:
            raise HTTPException(
                status_code=409,
                detail="No workspace billing subscription is linked to this organization",
            )
        return subscription

    legacy_subscription = db.scalar(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    if legacy_subscription is not None and legacy_subscription.stripe_customer_id:
        raise HTTPException(
            status_code=409,
            detail="This account has legacy billing that requires an operator-reviewed workspace migration",
        )

    # Persist before redirecting to Stripe so a completed Checkout has a local,
    # owner-validated reconciliation target.
    return upsert_organization_subscription_command(
        db,
        org_id=current_user.org_id,
        billing_owner_user_id=current_user.id,
        plan="starter",
        status="active",
        seat_limit=1,
        billable_seat_count=1,
    )


@router.post("/checkout")
def create_checkout(
    plan: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    """Create a Stripe Checkout Session for an organization-owned plan."""
    if not is_stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe is not configured on this deployment")

    if plan not in ("professional", "enterprise"):
        raise HTTPException(status_code=400, detail="Can only checkout professional or enterprise plans")

    try:
        app_url = get_app_url()
        subscription = _workspace_subscription_for_billing(
            db,
            current_user=current_user,
            create_if_missing=True,
        )
        # An existing Stripe customer must manage an upgrade/cancellation in the
        # Billing Portal. Creating another Checkout subscription would bill twice.
        if subscription.stripe_customer_id:
            portal_result = create_billing_portal_session(
                stripe_customer_id=subscription.stripe_customer_id,
                return_url=f"{app_url}/account",
            )
            return {"url": portal_result.url, "session_id": portal_result.session_id, "mode": "portal"}
        entitlement = resolve_org_entitlements(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
        )
        checkout_result = create_organization_checkout_session(
            org_id=current_user.org_id,
            billing_owner_user_id=current_user.id,
            billing_owner_email=current_user.email,
            plan=plan,
            seat_count=max(1, entitlement.active_member_count),
            success_url=f"{app_url}/projects?checkout=success",
            cancel_url=f"{app_url}/pricing?checkout=cancelled",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    return {"url": checkout_result.url, "session_id": checkout_result.session_id, "mode": "checkout"}


@router.post("/portal")
def create_billing_portal(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    """Create a Stripe-hosted portal session for the active workspace owner."""
    if not is_stripe_configured():
        raise HTTPException(status_code=501, detail="Stripe is not configured on this deployment")

    subscription = _workspace_subscription_for_billing(
        db,
        current_user=current_user,
        create_if_missing=False,
    )
    if not subscription.stripe_customer_id:
        raise HTTPException(status_code=409, detail="No Stripe billing customer is linked to this account")

    try:
        result = create_billing_portal_session(
            stripe_customer_id=subscription.stripe_customer_id,
            return_url=f"{get_app_url()}/account",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    return {"url": result.url, "session_id": result.session_id}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Handle Stripe webhook events.

    Processes:
      - checkout.session.completed → set plan/status from checkout metadata
      - customer.subscription.created → sync the initial subscription state
      - customer.subscription.updated → sync plan/status from subscription object
      - customer.subscription.deleted → downgrade to starter/canceled
      - invoice.paid → reconcile a successfully paid subscription invoice
      - invoice.payment_failed → mark subscription as past_due

    Each event is verified, recorded by Stripe event ID, and applied idempotently.
    Stripe may retry or deliver events out of order, so stale state updates are ignored.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Webhook verification failed")

    try:
        result = process_stripe_webhook_event(db, event)
    except ValueError:
        raise HTTPException(status_code=400, detail="Webhook event payload is invalid")

    return {"received": True, "duplicate": result.duplicate}
