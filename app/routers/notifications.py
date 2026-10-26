from fastapi import APIRouter, Response
from sqlalchemy import func, select, update

from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import Notification, utcnow
from app.schemas.account import NotificationOut, NotificationPage

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationPage, summary="My notifications, newest first",
            responses=error_responses(401, 422))
def list_notifications(user: CurrentUser, db: DbSession, pagination: Pagination,
                       unread_only: bool = False) -> NotificationPage:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    items, total = paginate(db, stmt, pagination)
    unread = db.scalar(select(func.count()).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    return NotificationPage(items=[NotificationOut.model_validate(n) for n in items], total=total,
                            page=pagination.page, size=pagination.size, unread=unread or 0)


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark one as read",
             responses=error_responses(401, 404))
def mark_read(notification_id: int, user: CurrentUser, db: DbSession) -> Notification:
    note = db.scalar(select(Notification).where(Notification.id == notification_id,
                                                Notification.user_id == user.id))
    if note is None:
        raise AppError(404, "NOTIFICATION_NOT_FOUND", "Notification not found.")
    note.read_at = note.read_at or utcnow()
    db.commit()
    return note


@router.post("/read-all", status_code=204, summary="Mark all as read", responses=error_responses(401))
def mark_all_read(user: CurrentUser, db: DbSession) -> Response:
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
               .values(read_at=utcnow()))
    db.commit()
    return Response(status_code=204)
