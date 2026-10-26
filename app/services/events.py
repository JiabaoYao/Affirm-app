"""Side effects of business actions: in-app notifications and the audit log. Both add to the session only."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Notification, User, utcnow


def notify(db: Session, user_id: int, kind: str, title: str, body: str, *, link: str | None = None,
           dedupe_key: str | None = None) -> Notification | None:
    """Queue a notification. With a dedupe_key, a notification that was already sent is skipped (returns None)."""
    if dedupe_key is not None:
        exists = db.scalar(
            select(Notification.id).where(Notification.user_id == user_id, Notification.dedupe_key == dedupe_key)
        )
        if exists is not None:
            return None
    note = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link, dedupe_key=dedupe_key,
                        created_at=utcnow())
    db.add(note)
    return note


def audit(db: Session, actor: User, action: str, entity: str, entity_id: int, **details: Any) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, entity=entity, entity_id=entity_id,
                    details={k: str(v) for k, v in details.items()}, created_at=utcnow()))
