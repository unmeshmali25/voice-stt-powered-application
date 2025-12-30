"""
Time Service - B-2

Time abstraction layer with calendar alignment for simulation mode.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import OfferEngineConfig

logger = logging.getLogger(__name__)


@dataclass
class SimulatedTimeResult:
    """Result of time advance operation."""

    previous_date: date
    new_date: date
    real_hours_advanced: float
    simulated_days_advanced: int


class TimeService:
    """Time abstraction for real vs simulation mode."""

    def __init__(self, config: OfferEngineConfig, db: Session = None):
        self.config = config
        self.db = db
        self._simulation_start_time: Optional[datetime] = None
        self._real_start_time: Optional[datetime] = None
        self._calendar_start: Optional[date] = None
        self._is_active: bool = False

    def now(self) -> datetime:
        """Returns current time (real or simulated)."""
        if not self.config.simulation_mode or not self._is_active:
            return datetime.utcnow()

        # Calculate elapsed real time
        real_elapsed = datetime.utcnow() - self._real_start_time
        real_hours = real_elapsed.total_seconds() / 3600

        # Scale to simulated hours
        simulated_hours = real_hours * self.config.time_scale

        # Return simulated time
        return self._simulation_start_time + timedelta(hours=simulated_hours)

    def get_simulated_date(self) -> Optional[date]:
        """Get current simulated calendar date."""
        if not self._is_active or not self._calendar_start:
            return None

        # Calculate simulated days from start (including fractional days)
        simulated_now = self.now()
        exact_days = (
            simulated_now - self._simulation_start_time
        ).total_seconds() / 86400

        return self._calendar_start + timedelta(days=exact_days)

    def start_simulation(self, calendar_start: date) -> None:
        """Begin simulation from specified calendar date."""
        self._simulation_start_time = datetime.utcnow()
        self._real_start_time = datetime.utcnow()
        self._calendar_start = calendar_start
        self._is_active = True
        self.save_state()
        logger.info(f"Simulation started at calendar date: {calendar_start}")

    def stop_simulation(self) -> dict:
        """End simulation, preserve state."""
        result = {
            "final_simulated_date": self.get_simulated_date(),
            "total_real_hours_elapsed": self._get_real_hours_elapsed(),
        }
        self._is_active = False
        self.save_state()
        logger.info(f"Simulation stopped. Final date: {result['final_simulated_date']}")
        return result

    def advance_time(self, hours: float) -> SimulatedTimeResult:
        """Advance simulation clock by N real hours."""
        if not self._is_active:
            raise ValueError("Simulation is not active")

        previous_date = self.get_simulated_date()

        # Move real start time back to simulate time passage
        self._real_start_time -= timedelta(hours=hours)

        new_date = self.get_simulated_date()
        simulated_days = (
            (new_date - previous_date).days if previous_date and new_date else 0
        )

        self.save_state()
        logger.info(f"Advanced {hours} hours: {previous_date} -> {new_date}")

        return SimulatedTimeResult(
            previous_date=previous_date,
            new_date=new_date,
            real_hours_advanced=hours,
            simulated_days_advanced=simulated_days,
        )

    def get_expiration_time(self, from_time: datetime = None) -> datetime:
        """
        Calculate offer expiration (2 weeks from now).

        In simulation mode: 14 simulated days
        In real mode: 14 real days
        """
        if from_time is None:
            from_time = self.now()

        # Always add days based on config (14 days)
        # The time context (simulated vs real) is already in from_time
        return from_time + timedelta(days=self.config.offer_expiration_days)

    def get_cycle_end_time(self, from_time: datetime = None) -> datetime:
        """Calculate cycle end (1 week simulated from now)."""
        if from_time is None:
            from_time = self.now()

        return from_time + timedelta(days=self.config.cycle_duration_days)

    def is_simulation_active(self) -> bool:
        """Check if simulation is currently active."""
        return self.config.simulation_mode and self._is_active

    def _get_real_hours_elapsed(self) -> float:
        """Get real hours elapsed since simulation start."""
        if not self._real_start_time:
            return 0.0
        elapsed = datetime.utcnow() - self._real_start_time
        return elapsed.total_seconds() / 3600

    def load_state(self) -> None:
        """Load simulation state from database."""
        if not self.db:
            return

        try:
            result = self.db.execute(
                text("""
                SELECT simulation_start_time, real_start_time,
                       simulation_calendar_start, is_active, time_scale
                FROM simulation_state WHERE id = 1
            """)
            ).fetchone()

            if result and result.is_active:
                self._simulation_start_time = result.simulation_start_time
                self._real_start_time = result.real_start_time
                self._calendar_start = result.simulation_calendar_start
                self._is_active = result.is_active
                self.config.time_scale = float(result.time_scale)
                logger.info(
                    f"Loaded simulation state: active={self._is_active}, date={self._calendar_start}"
                )
        except Exception as e:
            logger.error(f"Failed to load simulation state: {e}")

    def save_state(self) -> None:
        """Persist simulation state to database."""
        if not self.db:
            return

        try:
            self.db.execute(
                text("""
                UPDATE simulation_state SET
                    simulation_start_time = :sim_start,
                    real_start_time = :real_start,
                    simulation_calendar_start = :cal_start,
                    current_simulated_date = :current_date,
                    is_active = :is_active,
                    time_scale = :time_scale,
                    updated_at = NOW()
                WHERE id = 1
            """),
                {
                    "sim_start": self._simulation_start_time,
                    "real_start": self._real_start_time,
                    "cal_start": self._calendar_start,
                    "current_date": self.get_simulated_date(),
                    "is_active": self._is_active,
                    "time_scale": self.config.time_scale,
                },
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save simulation state: {e}")
            self.db.rollback()

    def get_status(self) -> dict:
        """Get current simulation status."""
        return {
            "is_active": self._is_active,
            "simulation_mode": self.config.simulation_mode,
            "calendar_start": self._calendar_start.isoformat()
            if self._calendar_start
            else None,
            "current_simulated_date": self.get_simulated_date().isoformat()
            if self.get_simulated_date()
            else None,
            "real_elapsed_hours": round(self._get_real_hours_elapsed(), 2),
            "time_scale": self.config.time_scale,
        }
