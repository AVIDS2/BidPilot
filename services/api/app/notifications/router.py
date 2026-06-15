from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications() -> list[dict]:
    return []


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(notification_id: str) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
