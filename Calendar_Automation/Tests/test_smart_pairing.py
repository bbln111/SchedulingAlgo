import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import (
    parse_appointments, ScheduleSettings, schedule_appointments, find_optimal_pairings,
    # Replace pre_assign_appointments with pre_assign_street_pairs
    pre_assign_street_pairs, score_candidate,
    can_place_block, initialize_calendar
)


class TestSmartPairing(unittest.TestCase):
    def setUp(self):
        """Set up test data and scheduler instance."""
        self.test_data = {
            "start_date": "2025-03-02",
            "appointments": [
                # Two street sessions on the same day with overlapping time frames
                {
                    "id": "1",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T16:00:00", "end": "2025-03-02T20:00:00"}
                    ]}]
                },
                {
                    "id": "2",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T16:00:00", "end": "2025-03-02T20:00:00"}
                    ]}]
                },
                # Two street sessions on Monday
                {
                    "id": "3",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Monday", "time_frames": [
                        {"start": "2025-03-03T16:00:00", "end": "2025-03-03T20:00:00"}
                    ]}]
                },
                {
                    "id": "4",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Monday", "time_frames": [
                        {"start": "2025-03-03T16:00:00", "end": "2025-03-03T20:00:00"}
                    ]}]
                },
                # A single street session on Tuesday (should be avoided)
                {
                    "id": "5",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Tuesday", "time_frames": [
                        {"start": "2025-03-04T16:00:00", "end": "2025-03-04T17:00:00"}
                    ]}]
                },
                # Two zoom sessions (shouldn't affect street pairing)
                {
                    "id": "6",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Tuesday", "time_frames": [
                        {"start": "2025-03-04T18:00:00", "end": "2025-03-04T20:00:00"}
                    ]}]
                },
                {
                    "id": "7",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Wednesday", "time_frames": [
                        {"start": "2025-03-05T16:00:00", "end": "2025-03-05T20:00:00"}
                    ]}]
                }
            ]
        }

        self.settings = ScheduleSettings(
            start_hour="10:00",
            end_hour="23:00",
            min_gap=15,
            max_hours_per_day_field=5,
            travel_time=75,
            start_date="2025-03-02"
        )

        self.appointments = parse_appointments(self.test_data)

    def identify_pairing_opportunities(self, appointments):
        """Helper function to identify days with multiple street sessions.

        This function replaces the original identify_pairing_opportunities function.
        """
        opportunities = {}
        for app in appointments:
            if app.is_street_session:
                for day_data in app.days:
                    day_index = day_data["day_index"]
                    if day_index not in opportunities:
                        opportunities[day_index] = []
                    opportunities[day_index].append(app)

        # Filter out days with only one street session
        return {day: apps for day, apps in opportunities.items() if len(apps) >= 2}

    def test_identify_pairing_opportunities(self):
        """Test that the function correctly identifies days with multiple potential street sessions."""
        opportunities = self.identify_pairing_opportunities(self.appointments)

        # Should identify Sunday (day 0) and Monday (day 1) as having multiple street sessions
        self.assertIn(0, opportunities)
        self.assertIn(1, opportunities)

        # Should have 2 street sessions on each of those days
        self.assertEqual(len(opportunities[0]), 2)
        self.assertEqual(len(opportunities[1]), 2)

        # Tuesday should not be included as it only has one street session
        self.assertNotIn(2, opportunities)

    def test_find_optimal_pairings(self):
        """Test that optimal pairings are found with minimal gaps."""
        calendar = initialize_calendar(self.settings)
        used_field_hours = [0] * 6

        # Get the pairing opportunities
        opportunities = self.identify_pairing_opportunities(self.appointments)

        # Create day_appointments for the pairings function
        day_appointments = {d: [] for d in range(6)}

        # Create street_appointments list
        street_appointments = [a for a in self.appointments if a.is_street_session]

        # Use the refactored find_optimal_pairings function
        optimal_pairings = find_optimal_pairings(street_appointments, calendar, used_field_hours, self.settings)

        # Should find pairings for days 0 and 1
        self.assertIn(0, optimal_pairings)
        self.assertIn(1, optimal_pairings)

        # Each day should have at least one pairing
        self.assertGreaterEqual(len(optimal_pairings[0]), 1)
        self.assertGreaterEqual(len(optimal_pairings[1]), 1)

        # Check that pairs include the expected session IDs
        day0_pair = optimal_pairings[0][0]
        self.assertIn(day0_pair["app1"].id, ["1", "2"])
        self.assertIn(day0_pair["app2"].id, ["1", "2"])

        day1_pair = optimal_pairings[1][0]
        self.assertIn(day1_pair["app1"].id, ["3", "4"])
        self.assertIn(day1_pair["app2"].id, ["3", "4"])

    def test_pre_assign_appointments(self):
        """Test that street session pairs are correctly pre-assigned in the calendar."""
        calendar = initialize_calendar(self.settings)
        used_field_hours = [0] * 6
        final_schedule = {}
        day_appointments = {d: [] for d in range(6)}

        # Get street appointments
        street_appointments = [a for a in self.appointments if a.is_street_session]

        # Find optimal pairings
        optimal_pairings = find_optimal_pairings(street_appointments, calendar, used_field_hours, self.settings)

        # Use the refactored pre_assign_street_pairs function
        pre_assigned = pre_assign_street_pairs(optimal_pairings, calendar, used_field_hours,
                                               final_schedule, day_appointments, self.settings)

        # Should pre-assign 4 appointments (2 pairs)
        self.assertEqual(len(pre_assigned), 4)

        # IDs 1, 2, 3, 4 should be pre-assigned
        self.assertIn("1", pre_assigned)
        self.assertIn("2", pre_assigned)
        self.assertIn("3", pre_assigned)
        self.assertIn("4", pre_assigned)

        # Check that the appointments were actually placed in the calendar and final_schedule
        self.assertEqual(len(final_schedule), 4)

        # Day 0 and 1 should each have 2 appointments
        day0_count = sum(1 for app_id, (start, end, app_type) in final_schedule.items()
                         if start.weekday() == 6)  # Use 6 for Sunday (day 0 in your system)
        day1_count = sum(1 for app_id, (start, end, app_type) in final_schedule.items()
                         if start.weekday() == 0)  # Use 0 for Monday (day 1 in your system)

        self.assertEqual(day0_count, 2)
        self.assertEqual(day1_count, 2)

    def test_full_scheduling_with_smart_pairing(self):
        """Test the entire scheduling process with smart pairing."""
        success, final_schedule, unscheduled_tasks = schedule_appointments(
            self.appointments, self.settings, is_test=True
        )

        # Should successfully schedule all high priority appointments
        self.assertTrue(success)

        # Analyze the schedule
        day_sessions = {}
        for app_id, (start, end, app_type) in final_schedule.items():
            day_index = start.weekday()  # This uses Python's weekday() where Monday=0
            if day_index not in day_sessions:
                day_sessions[day_index] = []
            day_sessions[day_index].append(app_type)

        # Check that there are no isolated street sessions
        for day, sessions in day_sessions.items():
            street_count = sum(1 for t in sessions if t in ["streets", "field"])
            trial_count = sum(1 for t in sessions if t == "trial_streets")

            # If there are street sessions, there should be at least 2
            if street_count > 0 or trial_count > 0:
                self.assertGreaterEqual(street_count + (2 * trial_count), 2)

        # Specifically check days 0 and 1 (Sunday and Monday) - UPDATE THESE VALUES
        if 6 in day_sessions:  # Sunday is day 6 in Python's weekday()
            street_count_day0 = sum(1 for t in day_sessions[6] if t in ["streets", "field"])
            self.assertGreaterEqual(street_count_day0, 2)

        if 0 in day_sessions:  # Monday is day 0 in Python's weekday()
            street_count_day1 = sum(1 for t in day_sessions[0] if t in ["streets", "field"])
            self.assertGreaterEqual(street_count_day1, 2)

        # Check that day 2 (Tuesday) doesn't have just one street session
        if 1 in day_sessions:  # Tuesday is day 1 in Python's weekday()
            street_count_day2 = sum(1 for t in day_sessions[1] if t in ["streets", "field"])
            if street_count_day2 > 0:
                self.assertGreaterEqual(street_count_day2, 2)


if __name__ == "__main__":
    unittest.main()
