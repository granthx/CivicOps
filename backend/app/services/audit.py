"""Append-only audit trail helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent, User


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int,
    actor: User | None,
    actor_role: str | None = None,
    actor_name: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else (actor_name or "System"),
        actor_role=actor.role if actor else (actor_role or "system"),
        event_metadata=metadata or {},
    )
    db.add(event)
    return event
