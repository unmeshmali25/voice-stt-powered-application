"""
Offer Scheduler - B-6

Orchestrates offer refresh operations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import OfferEngineConfig
from .time_service import TimeService
from .expiration_handler import ExpirationHandler
from .cycle_manager import OfferCycleManager
from .offer_assigner import OfferAssigner

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    """Result of user refresh check."""

    user_id: str
    refreshed: bool
    reason: str
    assigned_count: int = 0
    expired_count: int = 0


@dataclass
class AdvanceResult:
    """Result of time advance operation."""

    previous_date: Optional[str]
    new_date: Optional[str]
    cycles_completed: int
    users_refreshed: int
    offers_assigned: int
    real_hours_advanced: float


class OfferScheduler:
    """Orchestrates offer refresh and time advance operations."""

    def __init__(
        self, config: OfferEngineConfig, time_service: TimeService, db: Session
    ):
        self.config = config
        self.time_service = time_service
        self.db = db

        # Create component instances
        self.expiration_handler = ExpirationHandler(config, time_service, db)
        self.cycle_manager = OfferCycleManager(config, time_service, db)
        self.offer_assigner = OfferAssigner(
            config, time_service, self.expiration_handler, db
        )

    def check_and_refresh_user(self, user_id: str) -> RefreshResult:
        """Main entry point: check if refresh needed, perform if so."""
        if not self.config.simulation_mode:
            return RefreshResult(
                user_id=user_id, refreshed=False, reason="simulation_mode_disabled"
            )

        # Check cooldown
        if self._should_skip_cooldown(user_id):
            return RefreshResult(user_id=user_id, refreshed=False, reason="cooldown")

        # Check if refresh is needed
        if not self.cycle_manager.should_refresh_user_offers(user_id):
            return RefreshResult(user_id=user_id, refreshed=False, reason="not_due")

        # Perform refresh
        return self._perform_refresh(user_id)

    def force_refresh_user(self, user_id: str) -> RefreshResult:
        """Force refresh for a user (bypasses checks)."""
        if not self.config.simulation_mode:
            return RefreshResult(
                user_id=user_id, refreshed=False, reason="simulation_mode_disabled"
            )

        return self._perform_refresh(user_id)

    def _perform_refresh(self, user_id: str) -> RefreshResult:
        """Perform the actual refresh operation."""
        try:
            # Get or create current cycle
            cycle = self.cycle_manager.get_or_create_current_cycle()

            # Assign offers
            result = self.offer_assigner.assign_weekly_offers(user_id, cycle.id)

            # Update user's refresh time
            self.cycle_manager.update_user_refresh_time(user_id, cycle.id)

            return RefreshResult(
                user_id=user_id,
                refreshed=True,
                reason="success",
                assigned_count=result.total_assigned,
                expired_count=result.expired_count,
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to refresh user {user_id}: {e}")
            return RefreshResult(
                user_id=user_id, refreshed=False, reason=f"error: {str(e)}"
            )

    def _should_skip_cooldown(self, user_id: str) -> bool:
        """Check if user was refreshed within cooldown period."""
        state = self.cycle_manager.get_user_cycle_state(user_id)
        if not state or not state.last_refresh_at:
            return False

        cooldown = timedelta(seconds=self.config.refresh_cooldown_seconds)
        return datetime.utcnow() - state.last_refresh_at < cooldown

    def advance_simulation_time(
        self,
        hours: float,
        agent_ids: Optional[List[str]] = None,
        process_all_agents: bool = True,
    ) -> AdvanceResult:
        """Advance simulation time and refresh all affected users.

        Args:
            hours: Hours to advance simulation
            agent_ids: Optional list of agent IDs to filter (e.g., ['agent_001', 'agent_002'])
            process_all_agents: If True, process all agents. If False, only process agents in agent_ids list

        Returns:
            AdvanceResult with statistics
        """
        if not self.config.simulation_mode:
            raise ValueError("Simulation mode is not enabled")

        if not self.time_service.is_simulation_active():
            raise ValueError("Simulation is not currently active")

        # Advance time
        time_result = self.time_service.advance_time(hours)

        # Check for cycle transitions and create new cycles if needed
        cycles_completed = 0
        current_cycle = self.cycle_manager.get_or_create_current_cycle()
        while self.time_service.now() > current_cycle.ends_at:
            current_cycle = self.cycle_manager.create_new_cycle()
            cycles_completed += 1

        # Get all simulation users needing refresh
        users = self._get_users_needing_refresh(
            agent_ids=agent_ids, process_all=process_all_agents
        )
        logger.info(f"Found {len(users)} users needing refresh")

        # Refresh each user
        refreshed_count = 0
        total_offers_assigned = 0
        for user_id in users:
            result = self._perform_refresh(user_id)
            if result.refreshed:
                refreshed_count += 1
                total_offers_assigned += result.assigned_count
                logger.info(
                    f"  Refreshed user {user_id[:8]}...: {result.assigned_count} offers assigned"
                )
            else:
                logger.warning(
                    f"  Failed to refresh user {user_id[:8]}...: {result.reason}"
                )

        logger.info(
            f"Advanced {hours}h: {cycles_completed} cycles, {refreshed_count} users refreshed, {total_offers_assigned} offers assigned"
        )

        return AdvanceResult(
            previous_date=str(time_result.previous_date)
            if time_result.previous_date
            else None,
            new_date=str(time_result.new_date) if time_result.new_date else None,
            cycles_completed=cycles_completed,
            users_refreshed=refreshed_count,
            offers_assigned=total_offers_assigned,
            real_hours_advanced=hours,
        )

    def _get_users_needing_refresh(
        self, agent_ids: Optional[List[str]] = None, process_all: bool = True
    ) -> List[str]:
        """Get all simulation users who need offer refresh.

        This includes:
        1. Users past their next_refresh_at time
        2. NEW users (agents) who have never been enrolled in a cycle

        Args:
            agent_ids: Optional list of agent IDs to filter (e.g., ['agent_001', 'agent_002'])
            process_all: If True, process all agents. If False, only process agents in agent_ids list

        Returns:
            List of user IDs needing refresh
        """
        current_time = self.time_service.now()

        # Build WHERE clause for agent filtering
        agent_filter = ""
        agent_params = {}
        if not process_all and agent_ids:
            placeholders = ", ".join([f":aid_{i}" for i in range(len(agent_ids))])
            agent_filter = f"AND a.agent_id IN ({placeholders})"
            agent_params = {f"aid_{i}": aid for i, aid in enumerate(agent_ids)}
            logger.info(f"Filtering to {len(agent_ids)} specific agents: {agent_ids}")

        # Get users past their refresh time
        existing_users_query = f"""
            SELECT DISTINCT u.id
            FROM user_offer_cycles uoc
            JOIN users u ON u.id = uoc.user_id
            JOIN agents a ON a.user_id = u.id
            WHERE uoc.is_simulation = true
              AND uoc.next_refresh_at <= :now
              {agent_filter}
        """
        existing_users = self.db.execute(
            text(existing_users_query),
            {"now": current_time, **agent_params},
        ).fetchall()

        logger.debug(f"Existing users past refresh time: {len(existing_users)}")

        existing_ids = {str(row.id) for row in existing_users}

        # Get all agent users who may not be enrolled yet
        all_agent_users_query = f"""
            SELECT DISTINCT u.id
            FROM users u
            JOIN agents a ON a.user_id = u.id
            WHERE a.is_active = true
              {agent_filter}
        """
        all_agent_users = self.db.execute(
            text(all_agent_users_query),
            agent_params,
        ).fetchall()

        all_agent_ids = {str(row.id) for row in all_agent_users}

        # Find new users (in agents but not in user_offer_cycles)
        enrolled_users_query = f"""
            SELECT DISTINCT u.id
            FROM user_offer_cycles uoc
            JOIN users u ON u.id = uoc.user_id
            JOIN agents a ON a.user_id = u.id
            WHERE uoc.is_simulation = true
              {agent_filter}
        """
        enrolled_users = self.db.execute(
            text(enrolled_users_query),
            agent_params,
        ).fetchall()

        enrolled_ids = {str(row.id) for row in enrolled_users}

        new_user_ids = all_agent_ids - enrolled_ids

        logger.debug(
            f"All active agents: {len(all_agent_ids)}, Enrolled agents: {len(enrolled_ids)}, New agents: {len(new_user_ids)}"
        )

        # Combine: users needing refresh + new users needing initial enrollment
        all_needing_refresh = existing_ids | new_user_ids

        logger.info(
            f"Users needing refresh: {len(existing_ids)} existing (past due), {len(new_user_ids)} new (never enrolled)"
        )

        return list(all_needing_refresh)

    def get_all_simulation_user_ids(self) -> List[str]:
        """Get all users in simulation mode."""
        result = self.db.execute(
            text("""
            SELECT DISTINCT u.id
            FROM users u
            JOIN agents a ON a.user_id = u.id
            WHERE a.is_active = true
        """)
        ).fetchall()

        return [str(row.id) for row in result]
