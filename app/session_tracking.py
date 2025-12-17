import json
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session


SHOPPING_SESSION_HEADER = "X-Shopping-Session-Id"


def get_selected_store_id(db: Session, user_id: str) -> Optional[str]:
    result = db.execute(
        text("SELECT selected_store_id FROM user_preferences WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    row = result.fetchone()
    return str(row[0]) if row and row[0] else None


def get_shopping_session_id(request: Request) -> Optional[str]:
    raw = request.headers.get(SHOPPING_SESSION_HEADER)
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {SHOPPING_SESSION_HEADER}")


def touch_shopping_session(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    store_id: Optional[str],
) -> None:
    """
    Ensure session exists and is owned by user; updates last_seen_at.
    """
    result = db.execute(
        text(
            """
            INSERT INTO shopping_sessions (id, user_id, store_id, status, started_at, last_seen_at)
            VALUES (:id, :user_id, :store_id, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                last_seen_at = CURRENT_TIMESTAMP,
                store_id = COALESCE(EXCLUDED.store_id, shopping_sessions.store_id)
            RETURNING user_id
            """
        ),
        {"id": session_id, "user_id": user_id, "store_id": store_id},
    )
    existing_user_id = result.scalar()
    if existing_user_id and str(existing_user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Shopping session does not belong to this user")


def record_shopping_event(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    payload_json = json.dumps(payload or {})
    db.execute(
        text(
            """
            INSERT INTO shopping_session_events (session_id, user_id, event_type, payload)
            VALUES (:session_id, :user_id, :event_type, :payload::jsonb)
            """
        ),
        {
            "session_id": session_id,
            "user_id": user_id,
            "event_type": event_type,
            "payload": payload_json,
        },
    )


def complete_shopping_session(db: Session, *, session_id: str, user_id: str) -> None:
    db.execute(
        text(
            """
            UPDATE shopping_sessions
            SET status = 'completed',
                ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                last_seen_at = CURRENT_TIMESTAMP
            WHERE id = :session_id AND user_id = :user_id
            """
        ),
        {"session_id": session_id, "user_id": user_id},
    )


