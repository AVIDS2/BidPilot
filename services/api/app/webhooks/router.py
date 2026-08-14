from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    WebhookDeliveryActionRead,
    WebhookEndpointCreate,
    WebhookEndpointCreateRead,
    WebhookEndpointRead,
    WebhookEndpointUpdate,
    WebhookOverviewRead,
)
from .service import (
    create_webhook_endpoint_command,
    delete_webhook_endpoint_command,
    list_webhook_overview_query,
    retry_webhook_delivery_command,
    rotate_webhook_secret_command,
    test_webhook_endpoint_command,
    update_webhook_endpoint_command,
)


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/overview", response_model=WebhookOverviewRead)
def get_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookOverviewRead:
    return list_webhook_overview_query(db, current_user=current_user)


@router.post("/endpoints", response_model=WebhookEndpointCreateRead, status_code=status.HTTP_201_CREATED)
def create_endpoint(
    payload: WebhookEndpointCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookEndpointCreateRead:
    return create_webhook_endpoint_command(db, payload=payload, current_user=current_user)


@router.patch("/endpoints/{endpoint_id}", response_model=WebhookEndpointRead)
def update_endpoint(
    endpoint_id: str,
    payload: WebhookEndpointUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookEndpointRead:
    return update_webhook_endpoint_command(
        db, endpoint_id=endpoint_id, payload=payload, current_user=current_user
    )


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    delete_webhook_endpoint_command(db, endpoint_id=endpoint_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/endpoints/{endpoint_id}/rotate-secret", response_model=WebhookEndpointCreateRead)
def rotate_secret(
    endpoint_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookEndpointCreateRead:
    return rotate_webhook_secret_command(db, endpoint_id=endpoint_id, current_user=current_user)


@router.post("/endpoints/{endpoint_id}/test", response_model=WebhookDeliveryActionRead)
def test_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookDeliveryActionRead:
    return test_webhook_endpoint_command(db, endpoint_id=endpoint_id, current_user=current_user)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryActionRead)
def retry_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> WebhookDeliveryActionRead:
    return retry_webhook_delivery_command(db, delivery_id=delivery_id, current_user=current_user)
