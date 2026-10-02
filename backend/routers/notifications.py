from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.dependencies.auth import CurrentUser, CurrentUserCsrf
from backend.schemas.notifications import (
    NotificationReadAllResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from services.notification_service import (
    MAX_NOTIFICATION_OFFSET,
    MAX_NOTIFICATION_PAGE_SIZE,
    NotificationNotFoundError,
    notification_service,
)
from services.notification_types import NotificationType


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=MAX_NOTIFICATION_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0, le=MAX_NOTIFICATION_OFFSET)] = 0,
    unread_only: bool = False,
    tipo: NotificationType | None = None,
) -> list[NotificationResponse]:
    return [
        NotificationResponse(**item)
        for item in notification_service.list(
            current_user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
            notification_type=tipo,
        )
    ]


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(current_user: CurrentUser) -> NotificationUnreadCountResponse:
    return NotificationUnreadCountResponse(
        unread_count=notification_service.unread_count(current_user.id)
    )


@router.post("/read-all", response_model=NotificationReadAllResponse)
def read_all_notifications(current_user: CurrentUserCsrf) -> NotificationReadAllResponse:
    return NotificationReadAllResponse(
        updated_count=notification_service.mark_all_read(current_user.id)
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: int,
    current_user: CurrentUserCsrf,
) -> NotificationResponse:
    try:
        return NotificationResponse(
            **notification_service.mark_read(current_user.id, notification_id)
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_notification(
    notification_id: int,
    current_user: CurrentUserCsrf,
) -> Response:
    notification_service.delete(current_user.id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
