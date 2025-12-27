"""
Expiration Handler - B-3

Soft-delete expiration logic for offers.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import OfferEngineConfig
from .time_service import TimeService

logger = logging.getLogger(__name__)


@dataclass
class ExpirationResult:
    """Result of expiration processing."""

    expired_count: int
    user_id: Optional[str] = None


class ExpirationHandler:
    """Handles soft-delete expiration of offers."""

    def __init__(
        self, config: OfferEngineConfig, time_service: TimeService, db: Session
    ):
        self.config = config
        self.time_service = time_service
        self.db = db

    def process_expirations(self, user_id: str = None) -> ExpirationResult:
        """Mark expired offers with status='expired'."""
        current_time = self.time_service.now()

        if user_id:
            # Process for specific user
            result = self.db.execute(
                text("""
                UPDATE user_coupons
                SET status = 'expired'
                WHERE user_id = :uid
                  AND status = 'active'
                  AND is_simulation = true
                  AND eligible_until <= :now
            """),
                {"uid": user_id, "now": current_time},
            )
        else:
            # Process all simulation users
            result = self.db.execute(
                text("""
                UPDATE user_coupons
                SET status = 'expired'
                WHERE status = 'active'
                  AND is_simulation = true
                  AND eligible_until <= :now
            """),
                {"now": current_time},
            )

        self.db.commit()
        count = result.rowcount

        if count > 0:
            logger.info(
                f"Expired {count} offers" + (f" for user {user_id}" if user_id else "")
            )

        return ExpirationResult(expired_count=count, user_id=user_id)

    def expire_all_for_user(self, user_id: str) -> int:
        """Expire ALL active offers for a user (used in weekly refresh)."""
        result = self.db.execute(
            text("""
            UPDATE user_coupons
            SET status = 'expired'
            WHERE user_id = :uid
              AND status = 'active'
              AND is_simulation = true
        """),
            {"uid": user_id},
        )

        self.db.commit()
        count = result.rowcount
        logger.info(f"Expired all {count} active offers for user {user_id}")
        return count

    def get_expiration_stats(self, user_id: str) -> dict:
        """Get expiration statistics for a user."""
        result = self.db.execute(
            text("""
            SELECT
                status,
                COUNT(*) as count
            FROM user_coupons
            WHERE user_id = :uid AND is_simulation = true
            GROUP BY status
        """),
            {"uid": user_id},
        ).fetchall()

        stats = {row.status: row.count for row in result}
        return {
            "active": stats.get("active", 0),
            "expired": stats.get("expired", 0),
            "used": stats.get("used", 0),
            "removed": stats.get("removed", 0),
        }
