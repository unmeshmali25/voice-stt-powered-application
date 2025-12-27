"""
Offer Cycle Manager - B-4

Manages offer cycle lifecycle.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import OfferEngineConfig
from .time_service import TimeService

logger = logging.getLogger(__name__)


@dataclass
class OfferCycle:
    """Represents an offer cycle."""
    id: str
    cycle_number: int
    started_at: datetime
    ends_at: datetime
    simulated_start_date: Optional[str]
    simulated_end_date: Optional[str]


@dataclass
class UserCycleState:
    """User's cycle state."""
    user_id: str
    current_cycle_id: Optional[str]
    last_refresh_at: Optional[datetime]
    next_refresh_at: Optional[datetime]


class OfferCycleManager:
    """Manages offer cycle lifecycle."""

    def __init__(self, config: OfferEngineConfig, time_service: TimeService, db: Session):
        self.config = config
        self.time_service = time_service
        self.db = db

    def get_or_create_current_cycle(self) -> OfferCycle:
        """Get active cycle or create new one."""
        current_time = self.time_service.now()

        # Find active cycle
        result = self.db.execute(text("""
            SELECT id, cycle_number, started_at, ends_at,
                   simulated_start_date, simulated_end_date
            FROM offer_cycles
            WHERE is_simulation = true
              AND started_at <= :now
              AND ends_at > :now
            ORDER BY cycle_number DESC
            LIMIT 1
        """), {"now": current_time}).fetchone()

        if result:
            return OfferCycle(
                id=str(result.id),
                cycle_number=result.cycle_number,
                started_at=result.started_at,
                ends_at=result.ends_at,
                simulated_start_date=str(result.simulated_start_date) if result.simulated_start_date else None,
                simulated_end_date=str(result.simulated_end_date) if result.simulated_end_date else None,
            )

        # Create new cycle
        return self.create_new_cycle()

    def create_new_cycle(self) -> OfferCycle:
        """Create a new offer cycle."""
        current_time = self.time_service.now()

        # Get next cycle number
        result = self.db.execute(text("""
            SELECT COALESCE(MAX(cycle_number), 0) + 1 as next_num
            FROM offer_cycles
            WHERE is_simulation = true
        """)).fetchone()
        next_number = result.next_num

        cycle_id = str(uuid4())
        ends_at = self.time_service.get_cycle_end_time(current_time)

        # Get simulated dates
        sim_start = self.time_service.get_simulated_date()
        sim_end = None
        if sim_start:
            from datetime import timedelta
            sim_end = sim_start + timedelta(days=self.config.cycle_duration_days)

        self.db.execute(text("""
            INSERT INTO offer_cycles
                (id, cycle_number, started_at, ends_at, simulated_start_date, simulated_end_date, is_simulation)
            VALUES
                (:id, :num, :start, :end, :sim_start, :sim_end, true)
        """), {
            "id": cycle_id,
            "num": next_number,
            "start": current_time,
            "end": ends_at,
            "sim_start": sim_start,
            "sim_end": sim_end,
        })
        self.db.commit()

        logger.info(f"Created cycle {next_number}: {current_time} to {ends_at}")

        return OfferCycle(
            id=cycle_id,
            cycle_number=next_number,
            started_at=current_time,
            ends_at=ends_at,
            simulated_start_date=str(sim_start) if sim_start else None,
            simulated_end_date=str(sim_end) if sim_end else None,
        )

    def get_user_cycle_state(self, user_id: str) -> Optional[UserCycleState]:
        """Get user's current refresh state."""
        result = self.db.execute(text("""
            SELECT user_id, current_cycle_id, last_refresh_at, next_refresh_at
            FROM user_offer_cycles
            WHERE user_id = :uid AND is_simulation = true
        """), {"uid": user_id}).fetchone()

        if not result:
            return None

        return UserCycleState(
            user_id=str(result.user_id),
            current_cycle_id=str(result.current_cycle_id) if result.current_cycle_id else None,
            last_refresh_at=result.last_refresh_at,
            next_refresh_at=result.next_refresh_at,
        )

    def should_refresh_user_offers(self, user_id: str) -> bool:
        """Check if user needs offer refresh."""
        state = self.get_user_cycle_state(user_id)

        if not state:
            # New user, needs initial assignment
            return True

        if not state.next_refresh_at:
            return True

        return self.time_service.now() >= state.next_refresh_at

    def update_user_refresh_time(self, user_id: str, cycle_id: str) -> None:
        """Update user's refresh state."""
        current_time = self.time_service.now()
        next_refresh = self.time_service.get_cycle_end_time(current_time)

        # Upsert user_offer_cycles
        self.db.execute(text("""
            INSERT INTO user_offer_cycles
                (user_id, current_cycle_id, last_refresh_at, next_refresh_at, is_simulation)
            VALUES
                (:uid, :cid, :now, :next, true)
            ON CONFLICT (user_id) DO UPDATE SET
                current_cycle_id = :cid,
                last_refresh_at = :now,
                next_refresh_at = :next,
                updated_at = NOW()
        """), {
            "uid": user_id,
            "cid": cycle_id,
            "now": current_time,
            "next": next_refresh,
        })
        self.db.commit()
