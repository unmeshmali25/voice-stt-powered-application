"""
Offer Assigner - B-5

Pool-based random offer assignment with separate frontstore and category/brand pools.
"""

import logging
from dataclasses import dataclass
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import OfferEngineConfig
from .time_service import TimeService
from .expiration_handler import ExpirationHandler

logger = logging.getLogger(__name__)


@dataclass
class AssignmentResult:
    """Result of offer assignment."""

    user_id: str
    cycle_id: str
    expired_count: int
    frontstore_assigned: int
    category_brand_assigned: int
    total_assigned: int
    errors: List[str]


class OfferAssigner:
    """Handles pool-based random offer assignment."""

    def __init__(
        self,
        config: OfferEngineConfig,
        time_service: TimeService,
        expiration_handler: ExpirationHandler,
        db: Session,
    ):
        self.config = config
        self.time_service = time_service
        self.expiration_handler = expiration_handler
        self.db = db

    def assign_weekly_offers(self, user_id: str, cycle_id: str) -> AssignmentResult:
        """Full weekly assignment: expire old, assign new."""
        errors = []

        # 1. Expire ALL active offers for user
        expired_count = self.expiration_handler.expire_all_for_user(user_id)

        # 2. Get recently assigned coupon IDs to exclude (exclude expired offers too)
        exclude_ids = self._get_recent_coupon_ids(user_id)

        # 3. Get frontstore offers
        frontstore_ids = self._get_frontstore_offers(exclude_ids)
        if len(frontstore_ids) < self.config.frontstore_per_cycle:
            errors.append(
                f"Pool exhaustion: frontstore has {len(frontstore_ids)}, need {self.config.frontstore_per_cycle}"
            )

        # 4. Get category/brand offers
        category_brand_ids = self._get_category_brand_offers(
            exclude_ids + frontstore_ids
        )
        if len(category_brand_ids) < self.config.category_brand_per_cycle:
            errors.append(
                f"Pool exhaustion: category/brand has {len(category_brand_ids)}, need {self.config.category_brand_per_cycle}"
            )

        # 5. Calculate expiration time
        expiration = self.time_service.get_expiration_time()

        # 6. Insert new assignments
        all_coupon_ids = frontstore_ids + category_brand_ids
        self._insert_assignments(user_id, all_coupon_ids, cycle_id, expiration)

        logger.info(
            f"Assigned {len(all_coupon_ids)} offers to user {user_id} "
            f"(frontstore: {len(frontstore_ids)}, category/brand: {len(category_brand_ids)})"
        )

        return AssignmentResult(
            user_id=user_id,
            cycle_id=cycle_id,
            expired_count=expired_count,
            frontstore_assigned=len(frontstore_ids),
            category_brand_assigned=len(category_brand_ids),
            total_assigned=len(all_coupon_ids),
            errors=errors,
        )

    def _get_recent_coupon_ids(self, user_id: str) -> List[str]:
        """Get coupon IDs assigned in recent cycles (to avoid repetition)."""
        # Get coupons assigned in last 4 weeks
        result = self.db.execute(
            text("""
            SELECT DISTINCT coupon_id
            FROM user_coupons
            WHERE user_id = :uid
              AND is_simulation = true
              AND assigned_at > NOW() - INTERVAL '28 days'
        """),
            {"uid": user_id},
        ).fetchall()

        return [str(row.coupon_id) for row in result]

    def _get_frontstore_offers(self, exclude_ids: List[str]) -> List[str]:
        """Select random offers from frontstore pool."""
        if exclude_ids:
            # Build parameterized NOT IN clause
            placeholders = ", ".join([f":ex_{i}" for i in range(len(exclude_ids))])
            params = {f"ex_{i}": eid for i, eid in enumerate(exclude_ids)}
            params["limit"] = self.config.frontstore_per_cycle

            query = f"""
                SELECT id FROM coupons
                WHERE type = 'frontstore'
                  AND id::text NOT IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT :limit
            """
        else:
            query = """
                SELECT id FROM coupons
                WHERE type = 'frontstore'
                ORDER BY RANDOM()
                LIMIT :limit
            """
            params = {"limit": self.config.frontstore_per_cycle}

        result = self.db.execute(text(query), params).fetchall()
        logger.debug(
            f"Found {len(result)} frontstore offers (excluding {len(exclude_ids)} IDs)"
        )
        return [str(row.id) for row in result]

    def _get_category_brand_offers(self, exclude_ids: List[str]) -> List[str]:
        """Select random offers from category/brand pool."""
        if exclude_ids:
            # Build parameterized NOT IN clause
            placeholders = ", ".join([f":ex_{i}" for i in range(len(exclude_ids))])
            params = {f"ex_{i}": eid for i, eid in enumerate(exclude_ids)}
            params["limit"] = self.config.category_brand_per_cycle

            query = f"""
                SELECT id FROM coupons
                WHERE type IN ('category', 'brand')
                  AND id::text NOT IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT :limit
            """
        else:
            query = """
                SELECT id FROM coupons
                WHERE type IN ('category', 'brand')
                ORDER BY RANDOM()
                LIMIT :limit
            """
            params = {"limit": self.config.category_brand_per_cycle}

        result = self.db.execute(text(query), params).fetchall()
        logger.debug(
            f"Found {len(result)} category/brand offers (excluding {len(exclude_ids)} IDs)"
        )
        return [str(row.id) for row in result]

    def _insert_assignments(
        self, user_id: str, coupon_ids: List[str], cycle_id: str, expiration
    ) -> None:
        """Insert new coupon assignments."""
        for coupon_id in coupon_ids:
            try:
                self.db.execute(text("SAVEPOINT assign_coupon"))
                self.db.execute(
                    text("""
                    INSERT INTO user_coupons
                        (user_id, coupon_id, status, offer_cycle_id, is_simulation, eligible_until, assigned_at)
                    VALUES
                        (:uid, :cid, 'active', :cycle, true, :exp, NOW())
                """),
                    {
                        "uid": user_id,
                        "cid": coupon_id,
                        "cycle": cycle_id,
                        "exp": expiration,
                    },
                )
                self.db.execute(text("RELEASE SAVEPOINT assign_coupon"))
            except Exception as e:
                self.db.execute(text("ROLLBACK TO SAVEPOINT assign_coupon"))
                logger.error(
                    f"Failed to assign coupon {coupon_id} to user {user_id}: {e}"
                )

        self.db.commit()
