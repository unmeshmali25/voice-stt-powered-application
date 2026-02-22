"""Temporal event calendar for shopping simulation.

Provides static seasonal and weekly patterns that influence shopping behavior.
"""

import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Event:
    """Represents a temporal event that influences shopping behavior."""

    name: str
    months: List[int]
    impact: float  # -1.0 to 1.0
    categories: List[str]
    days: Optional[List[int]] = None  # Specific days of month if applicable
    description: str = ""  # Human-readable description

    def is_active(self, date: datetime.date) -> bool:
        """Check if event is active on given date."""
        if date.month not in self.months:
            return False

        if self.days is not None and date.day not in self.days:
            return False

        return True


@dataclass
class WeeklyPattern:
    """Represents a weekly shopping pattern."""

    name: str
    days: List[int]  # 0=Monday, 6=Sunday
    impact: float  # -1.0 to 1.0

    def is_active(self, date: datetime.date) -> bool:
        """Check if pattern is active on given date."""
        return date.weekday() in self.days


class EventCalendar:
    """Calendar system for temporal shopping events and patterns.

    Provides context about seasonal events (e.g., Black Friday, Back to School)
    and weekly patterns (e.g., weekend boost) that influence shopping behavior.
    """

    # Static seasonal events
    EVENTS: Dict[str, Event] = {
        "back_to_school": Event(
            name="back_to_school",
            months=[8],  # August
            impact=0.3,
            categories=["school", "office", "health"],
            description="School supplies, health checkups",
        ),
        "black_friday": Event(
            name="black_friday",
            months=[11],  # November
            days=[29],  # Black Friday (4th Thursday + 1)
            impact=0.6,
            categories=["all"],
            description="Major shopping holiday",
        ),
        "cyber_monday": Event(
            name="cyber_monday",
            months=[11],
            days=[25],  # Cyber Monday (adjust as needed)
            impact=0.4,
            categories=["all"],
            description="Online shopping deals",
        ),
        "holiday_shopping": Event(
            name="holiday_shopping",
            months=[12],  # December
            days=list(range(15, 26)),  # Dec 15-25
            impact=0.5,
            categories=["gifts", "food", "decor"],
            description="Christmas and holiday shopping",
        ),
        "summer_bbq": Event(
            name="summer_bbq",
            months=[6, 7],  # June-July
            impact=0.2,
            categories=["food", "outdoor"],
            description="Summer gatherings and outdoor cooking",
        ),
        "flu_season": Event(
            name="flu_season",
            months=[10, 11, 12, 1, 2],  # Oct-Feb
            impact=0.25,
            categories=["health", "pharmacy"],
            description="Cold and flu remedies, vitamins",
        ),
        "new_year_health": Event(
            name="new_year_health",
            months=[1],  # January
            days=list(range(1, 16)),  # Jan 1-15
            impact=0.35,
            categories=["health", "fitness", "pharmacy"],
            description="New Year resolutions, health kick",
        ),
        "valentines_day": Event(
            name="valentines_day",
            months=[2],
            days=[14],
            impact=0.3,
            categories=["gifts", "candy", "beauty"],
            description="Valentine's Day gifts and treats",
        ),
        "mothers_day": Event(
            name="mothers_day",
            months=[5],
            days=list(range(8, 15)),  # 2nd Sunday in May approximation
            impact=0.25,
            categories=["gifts", "beauty", "health"],
            description="Mother's Day gifts",
        ),
        "halloween": Event(
            name="halloween",
            months=[10],
            days=list(range(25, 32)),  # Oct 25-31
            impact=0.2,
            categories=["candy", "decor"],
            description="Halloween candy and decorations",
        ),
        "tax_refund": Event(
            name="tax_refund",
            months=[3, 4],  # March-April
            impact=0.15,
            categories=["all"],
            description="Tax refund spending",
        ),
        "allergy_season": Event(
            name="allergy_season",
            months=[3, 4, 5, 9],  # Spring and Fall
            impact=0.2,
            categories=["health", "pharmacy"],
            description="Allergy medications and remedies",
        ),
    }

    # Weekly shopping patterns
    WEEKLY_PATTERNS: Dict[str, WeeklyPattern] = {
        "weekend_boost": WeeklyPattern(
            name="weekend_boost",
            days=[5, 6],  # Saturday (5), Sunday (6)
            impact=0.15,
        ),
        "midweek_dip": WeeklyPattern(
            name="midweek_dip",
            days=[2],  # Wednesday
            impact=-0.1,
        ),
        "friday_prep": WeeklyPattern(
            name="friday_prep",
            days=[4],  # Friday
            impact=0.1,
        ),
    }

    def __init__(self):
        """Initialize the event calendar."""
        pass

    def get_active_events(self, date: datetime.date) -> List[Event]:
        """Get all active events for a given date.

        Args:
            date: The date to check

        Returns:
            List of active Event objects
        """
        return [event for event in self.EVENTS.values() if event.is_active(date)]

    def get_active_patterns(self, date: datetime.date) -> List[WeeklyPattern]:
        """Get all active weekly patterns for a given date.

        Args:
            date: The date to check

        Returns:
            List of active WeeklyPattern objects
        """
        return [
            pattern
            for pattern in self.WEEKLY_PATTERNS.values()
            if pattern.is_active(date)
        ]

    def calculate_total_impact(self, date: datetime.date) -> float:
        """Calculate total shopping impact for a date.

        Sums impacts from active events and weekly patterns.

        Args:
            date: The date to check

        Returns:
            Total impact score (can be positive or negative)
        """
        events = self.get_active_events(date)
        patterns = self.get_active_patterns(date)

        total_impact = sum(e.impact for e in events) + sum(p.impact for p in patterns)

        # Clamp to reasonable range
        return max(-1.0, min(1.0, total_impact))

    def get_context_for_date(self, date: datetime.date) -> Dict[str, Any]:
        """Get complete temporal context for a date.

        Returns full context including active events, patterns, and impact scores.
        This is used when making LLM-based decisions to provide temporal context.

        Args:
            date: The date to get context for

        Returns:
            Dictionary with:
                - date: ISO format date string
                - day_of_week: Day name (Monday-Sunday)
                - month_name: Month name
                - active_events: List of event names
                - active_patterns: List of pattern names
                - event_details: List of event objects (as dicts)
                - total_impact: Combined impact score (-1.0 to 1.0)
                - primary_categories: Union of all category influences
        """
        events = self.get_active_events(date)
        patterns = self.get_active_patterns(date)

        # Collect all categories
        categories = set()
        for event in events:
            categories.update(event.categories)

        return {
            "date": date.isoformat(),
            "day_of_week": date.strftime("%A"),
            "month_name": date.strftime("%B"),
            "active_events": [e.name for e in events],
            "active_patterns": [p.name for p in patterns],
            "event_details": [
                {
                    "name": e.name,
                    "impact": e.impact,
                    "categories": e.categories,
                    "description": e.description if hasattr(e, "description") else "",
                }
                for e in events
            ],
            "total_impact": self.calculate_total_impact(date),
            "primary_categories": sorted(list(categories)),
        }

    def is_shopping_event(self, date: datetime.date, min_impact: float = 0.2) -> bool:
        """Check if date represents a significant shopping event.

        Args:
            date: The date to check
            min_impact: Minimum impact threshold to be considered significant

        Returns:
            True if total impact >= min_impact
        """
        return self.calculate_total_impact(date) >= min_impact

    def get_event_description(self, event_name: str) -> str:
        """Get human-readable description of an event.

        Args:
            event_name: Name of the event

        Returns:
            Description string or empty string if not found
        """
        if event_name in self.EVENTS:
            event = self.EVENTS[event_name]
            return getattr(event, "description", f"Shopping event: {event_name}")
        return ""


# Global calendar instance
calendar = EventCalendar()


def get_temporal_context(date: datetime.date) -> Dict[str, Any]:
    """Convenience function to get temporal context for a date.

    Args:
        date: The date to get context for

    Returns:
        Temporal context dictionary
    """
    return calendar.get_context_for_date(date)
