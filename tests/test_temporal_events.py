"""Unit tests for temporal event calendar system."""

import datetime
import pytest
from app.simulation.temporal.events import (
    EventCalendar,
    Event,
    get_temporal_context,
)


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(name="test_event", months=[1, 2], impact=0.5, categories=["test"])
        assert event.name == "test_event"
        assert event.months == [1, 2]
        assert event.impact == 0.5
        assert event.categories == ["test"]
        assert event.days is None

    def test_event_with_days(self):
        """Test event with specific days."""
        event = Event(
            name="specific_day",
            months=[12],
            days=[25],
            impact=0.8,
            categories=["holiday"],
        )
        assert event.days == [25]

    def test_event_is_active_month_only(self):
        """Test event activation with month constraint only."""
        event = Event(
            name="january_event", months=[1], impact=0.3, categories=["winter"]
        )

        assert event.is_active(datetime.date(2024, 1, 15)) is True
        assert event.is_active(datetime.date(2024, 2, 15)) is False
        assert event.is_active(datetime.date(2024, 1, 1)) is True

    def test_event_is_active_with_days(self):
        """Test event activation with both month and day constraints."""
        event = Event(
            name="christmas", months=[12], days=[25], impact=0.5, categories=["holiday"]
        )

        assert event.is_active(datetime.date(2024, 12, 25)) is True
        assert event.is_active(datetime.date(2024, 12, 24)) is False
        assert event.is_active(datetime.date(2024, 11, 25)) is False


class TestEventCalendar:
    """Tests for EventCalendar class."""

    def test_calendar_initialization(self):
        """Test calendar can be initialized."""
        calendar = EventCalendar()
        assert calendar is not None
        assert len(calendar.EVENTS) > 0

    def test_back_to_school_event(self):
        """Test back_to_school event detection."""
        calendar = EventCalendar()

        # August should have back_to_school
        aug_date = datetime.date(2024, 8, 15)
        active_events = calendar.get_active_events(aug_date)
        event_names = [e.name for e in active_events]
        assert "back_to_school" in event_names

        # September should NOT have back_to_school
        sep_date = datetime.date(2024, 9, 15)
        active_events = calendar.get_active_events(sep_date)
        event_names = [e.name for e in active_events]
        assert "back_to_school" not in event_names

    def test_thanksgiving_event(self):
        """Test Thanksgiving event detection."""
        calendar = EventCalendar()

        # November 28, 2024 should be Thanksgiving (4th Thursday)
        tg_date = datetime.date(2024, 11, 28)
        active_events = calendar.get_active_events(tg_date)
        event_names = [e.name for e in active_events]
        assert "thanksgiving" in event_names

        # November 21 should NOT be Thanksgiving
        nov_21 = datetime.date(2024, 11, 21)
        active_events = calendar.get_active_events(nov_21)
        event_names = [e.name for e in active_events]
        assert "thanksgiving" not in event_names

    def test_black_friday_event(self):
        """Test Black Friday event detection."""
        calendar = EventCalendar()

        # November 29 should be Black Friday
        bf_date = datetime.date(2024, 11, 29)
        active_events = calendar.get_active_events(bf_date)
        event_names = [e.name for e in active_events]
        assert "black_friday" in event_names

        # November 28 should NOT be Black Friday
        nov_28 = datetime.date(2024, 11, 28)
        active_events = calendar.get_active_events(nov_28)
        event_names = [e.name for e in active_events]
        assert "black_friday" not in event_names

    def test_holiday_shopping_event(self):
        """Test holiday shopping event detection."""
        calendar = EventCalendar()

        # December 20 should be holiday shopping
        dec_20 = datetime.date(2024, 12, 20)
        active_events = calendar.get_active_events(dec_20)
        event_names = [e.name for e in active_events]
        assert "holiday_shopping" in event_names

        # December 14 should NOT be holiday shopping
        dec_14 = datetime.date(2024, 12, 14)
        active_events = calendar.get_active_events(dec_14)
        event_names = [e.name for e in active_events]
        assert "holiday_shopping" not in event_names

    def test_flu_season_event(self):
        """Test flu season event spans multiple months."""
        calendar = EventCalendar()

        # October through February should have flu_season
        for month in [10, 11, 12, 1, 2]:
            year = 2024 if month != 1 else 2025
            date = datetime.date(year, month, 15)
            active_events = calendar.get_active_events(date)
            event_names = [e.name for e in active_events]
            assert "flu_season" in event_names, (
                f"Flu season should be active in month {month}"
            )

    def test_calculate_total_impact(self):
        """Test total impact calculation."""
        calendar = EventCalendar()

        # Black Friday should have high impact
        bf_date = datetime.date(2024, 11, 29)  # Black Friday 2024
        impact = calendar.calculate_total_impact(bf_date)
        # Black Friday impact: 0.6
        assert impact >= 0.6

        # Regular Wednesday during flu season should have positive impact
        regular_wed = datetime.date(2024, 2, 21)
        impact = calendar.calculate_total_impact(regular_wed)
        # Flu season (0.25) only
        assert 0.2 < impact < 0.3

    def test_get_context_for_date_structure(self):
        """Test context structure returned by get_context_for_date."""
        calendar = EventCalendar()
        context = calendar.get_context_for_date(datetime.date(2024, 8, 15))

        assert "date" in context
        assert "day_of_week" in context
        assert "month_name" in context
        assert "active_events" in context
        assert "event_details" in context
        assert "total_impact" in context
        assert "primary_categories" in context

        assert context["date"] == "2024-08-15"
        assert context["day_of_week"] == "Thursday"
        assert context["month_name"] == "August"
        assert isinstance(context["active_events"], list)
        assert isinstance(context["total_impact"], float)

    def test_is_shopping_event(self):
        """Test shopping event detection with threshold."""
        calendar = EventCalendar()

        # Black Friday should be a shopping event
        bf_date = datetime.date(2024, 11, 29)
        assert calendar.is_shopping_event(bf_date, min_impact=0.2) is True

        # A date in June (summer_bbq only, impact 0.2) should meet threshold
        jun_date = datetime.date(2024, 6, 15)
        result = calendar.is_shopping_event(jun_date, min_impact=0.2)
        # summer_bbq has impact 0.2, so exactly at threshold
        assert result is True

        # A date in March outside tax_refund months with no events
        mar_date = datetime.date(2024, 3, 15)
        # Check if there's actually an event
        active = calendar.get_active_events(mar_date)
        if len(active) == 0:
            # No events, impact should be 0
            result = calendar.is_shopping_event(mar_date, min_impact=0.2)
            assert result is False

    def test_impact_clamping(self):
        """Test that impact is clamped to valid range."""
        calendar = EventCalendar()

        # Test with a date that would have very high impact
        # Christmas + Holiday shopping + Weekend if applicable
        dec_25 = datetime.date(2024, 12, 25)
        impact = calendar.calculate_total_impact(dec_25)
        assert -1.0 <= impact <= 1.0


class TestGetTemporalContext:
    """Tests for the convenience function."""

    def test_get_temporal_context(self):
        """Test the convenience function works."""
        date = datetime.date(2024, 8, 15)
        context = get_temporal_context(date)

        assert context["date"] == "2024-08-15"
        assert "active_events" in context
        assert "total_impact" in context


class TestEventCategories:
    """Tests for event category assignments."""

    def test_back_to_school_categories(self):
        """Test back_to_school has correct categories."""
        calendar = EventCalendar()
        event = calendar.EVENTS["back_to_school"]

        assert "school" in event.categories
        assert "office" in event.categories
        assert "health" in event.categories

    def test_black_friday_categories(self):
        """Test Black Friday affects all categories."""
        calendar = EventCalendar()
        event = calendar.EVENTS["black_friday"]

        assert "all" in event.categories

    def test_flu_season_categories(self):
        """Test flu_season has health-related categories."""
        calendar = EventCalendar()
        event = calendar.EVENTS["flu_season"]

        assert "health" in event.categories
        assert "pharmacy" in event.categories

    def test_context_categories_union(self):
        """Test that context contains union of all categories."""
        calendar = EventCalendar()

        # August should have back_to_school with school/office/health
        context = calendar.get_context_for_date(datetime.date(2024, 8, 15))
        categories = context["primary_categories"]

        assert "school" in categories
        assert "office" in categories
        assert "health" in categories


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_leap_year(self):
        """Test calendar works correctly on leap day."""
        calendar = EventCalendar()

        # Feb 29, 2024 (leap year)
        leap_day = datetime.date(2024, 2, 29)
        context = calendar.get_context_for_date(leap_day)

        # Flu season should be active
        assert "flu_season" in context["active_events"]

    def test_year_boundary(self):
        """Test calendar works across year boundaries."""
        calendar = EventCalendar()

        # Dec 31 and Jan 1
        dec_31 = datetime.date(2024, 12, 31)
        jan_1 = datetime.date(2025, 1, 1)

        # Dec 31 should have flu_season and holiday_shopping
        dec_context = calendar.get_context_for_date(dec_31)
        assert "flu_season" in dec_context["active_events"]

        # Jan 1 should have flu_season and new_year_health
        jan_context = calendar.get_context_for_date(jan_1)
        assert "flu_season" in jan_context["active_events"]
        assert "new_year_health" in jan_context["active_events"]

    def test_multiple_events_same_date(self):
        """Test handling of multiple events on same date."""
        calendar = EventCalendar()

        # A date in December during flu season and holiday shopping
        dec_20 = datetime.date(2024, 12, 20)
        events = calendar.get_active_events(dec_20)
        event_names = [e.name for e in events]

        # Should have both flu_season and holiday_shopping
        assert "flu_season" in event_names
        assert "holiday_shopping" in event_names

        # Impact should be cumulative
        impact = calendar.calculate_total_impact(dec_20)
        assert impact > calendar.EVENTS["flu_season"].impact


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
