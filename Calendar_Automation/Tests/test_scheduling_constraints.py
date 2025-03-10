import os
import sys
import unittest
import logging
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import (
    parse_appointments, ScheduleSettings, schedule_appointments,
    initialize_calendar, can_place_block, place_block, validate_schedule,
    Appointment, TRAVEL_TIME_BETWEEN_TYPES, MAX_GAP_BETWEEN_STREET_SESSIONS
)


class TestSchedulingConstraints(unittest.TestCase):
    """Tests for validating the scheduling constraints in the system."""

    def setUp(self):
        """Setup test data for scheduling constraints."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        print("\n=== Running TestSchedulingConstraints ===")

        # Default settings
        self.settings = ScheduleSettings(
            start_hour="10:00",
            end_hour="23:00",
            min_gap=15,
            max_hours_per_day_field=5,
            travel_time=75,  # 75 minutes travel time
            start_date="2025-03-09"  # A Sunday
        )

        # Initialize empty calendar
        self.calendar = initialize_calendar(self.settings)
        self.used_field_hours = [0] * 6
        self.day_appointments = {d: [] for d in range(6)}
        self.final_schedule = {}

        print("Test setup complete")

    def test_overlapping_appointments(self):
        """Test that overlapping appointments are rejected."""
        print("\n--- Running test_overlapping_appointments ---")

        # Create two overlapping appointments
        app1 = Appointment("1", "High", "streets", 60)
        day_index = 0  # Sunday

        # Create two blocks with overlap
        start1 = datetime(2025, 3, 9, 14, 0)  # 2pm
        end1 = datetime(2025, 3, 9, 15, 15)  # 3:15pm (including 15min gap)
        block1 = (start1, end1)

        start2 = datetime(2025, 3, 9, 15, 0)  # 3pm - overlaps with first block
        end2 = datetime(2025, 3, 9, 16, 15)  # 4:15pm
        block2 = (start2, end2)

        # Add day data to the appointment
        app1.days.append({
            "day_index": day_index,
            "blocks": [block1]
        })

        app2 = Appointment("2", "High", "streets", 60)
        app2.days.append({
            "day_index": day_index,
            "blocks": [block2]
        })

        # Place first appointment
        result1 = place_block(app1, day_index, block1, self.calendar,
                              self.used_field_hours, self.final_schedule,
                              self.day_appointments)

        print(f"Placed first appointment: {result1}")
        self.assertTrue(result1, "Should be able to place first appointment")

        # Try to place second overlapping appointment - should fail
        result2 = can_place_block(app2, day_index, block2, self.calendar,
                                  self.used_field_hours, self.settings,
                                  self.day_appointments)

        print(f"Can place overlapping appointment: {result2}")
        self.assertFalse(result2, "Should not be able to place overlapping appointment")

        # Check validation - should fail with overlapping issue
        if result2:
            place_block(app2, day_index, block2, self.calendar,
                        self.used_field_hours, self.final_schedule,
                        self.day_appointments)

            validation = validate_schedule(self.final_schedule)
            print(f"Validation result: {validation}")
            self.assertFalse(validation["valid"], "Schedule with overlapping appointments should be invalid")

            # Check for the right validation issue
            overlap_issues = [i for i in validation["issues"] if "overlapping" in i]
            self.assertTrue(len(overlap_issues) > 0, "Should identify overlapping appointments issue")

        print("test_overlapping_appointments PASSED")

    def test_travel_time_between_types(self):
        """Test that travel time is respected between different appointment types."""
        print("\n--- Running test_travel_time_between_types ---")

        day_index = 0  # Sunday

        # Create a street and zoom appointment with insufficient travel time
        app1 = Appointment("1", "High", "streets", 60)
        start1 = datetime(2025, 3, 9, 14, 0)  # 2pm
        end1 = datetime(2025, 3, 9, 15, 0)  # 3pm
        block1 = (start1, end1)

        app2 = Appointment("2", "High", "zoom", 60)
        # Only 30 minutes between appointments - less than 75min travel time
        start2 = datetime(2025, 3, 9, 15, 30)  # 3:30pm
        end2 = datetime(2025, 3, 9, 16, 30)  # 4:30pm
        block2 = (start2, end2)

        # Add day data
        app1.days.append({
            "day_index": day_index,
            "blocks": [block1]
        })

        app2.days.append({
            "day_index": day_index,
            "blocks": [block2]
        })

        # Place the street appointment
        result1 = place_block(app1, day_index, block1, self.calendar,
                              self.used_field_hours, self.final_schedule,
                              self.day_appointments)

        print(f"Placed street appointment: {result1}")
        self.assertTrue(result1, "Should be able to place street appointment")

        # Try to place zoom appointment with insufficient travel time
        result2 = can_place_block(app2, day_index, block2, self.calendar,
                                  self.used_field_hours, self.settings,
                                  self.day_appointments)

        print(f"Can place zoom with insufficient travel time: {result2}")
        self.assertFalse(result2, "Should not be able to place zoom with insufficient travel time")

        # Now try with sufficient travel time
        app3 = Appointment("3", "High", "zoom", 60)
        # 75 minutes after first appointment ends
        start3 = datetime(2025, 3, 9, 16, 15)  # 4:15pm
        end3 = datetime(2025, 3, 9, 17, 15)  # 5:15pm
        block3 = (start3, end3)

        app3.days.append({
            "day_index": day_index,
            "blocks": [block3]
        })

        result3 = can_place_block(app3, day_index, block3, self.calendar,
                                  self.used_field_hours, self.settings,
                                  self.day_appointments)

        print(f"Can place zoom with sufficient travel time: {result3}")
        self.assertTrue(result3, "Should be able to place zoom with sufficient travel time")

        print("test_travel_time_between_types PASSED")

    def test_trial_regular_travel_time(self):
        """Test that travel time is respected between trial and regular sessions of same type."""
        print("\n--- Running test_trial_regular_travel_time ---")

        day_index = 0  # Sunday

        # Create a trial_zoom and regular zoom appointment with insufficient travel time
        app1 = Appointment("1", "High", "trial_zoom", 120)
        start1 = datetime(2025, 3, 9, 14, 0)  # 2pm
        end1 = datetime(2025, 3, 9, 16, 0)  # 4pm
        block1 = (start1, end1)

        app2 = Appointment("2", "High", "zoom", 60)
        # Only 30 minutes between appointments - less than 75min travel time
        start2 = datetime(2025, 3, 9, 16, 30)  # 4:30pm
        end2 = datetime(2025, 3, 9, 17, 30)  # 5:30pm
        block2 = (start2, end2)

        # Add day data
        app1.days.append({
            "day_index": day_index,
            "blocks": [block1]
        })

        app2.days.append({
            "day_index": day_index,
            "blocks": [block2]
        })

        # Place the trial zoom appointment
        result1 = place_block(app1, day_index, block1, self.calendar,
                              self.used_field_hours, self.final_schedule,
                              self.day_appointments)

        print(f"Placed trial_zoom appointment: {result1}")
        self.assertTrue(result1, "Should be able to place trial_zoom appointment")

        # Try to place regular zoom appointment with insufficient travel time
        result2 = can_place_block(app2, day_index, block2, self.calendar,
                                  self.used_field_hours, self.settings,
                                  self.day_appointments)

        print(f"Can place zoom with insufficient travel time after trial_zoom: {result2}")
        self.assertFalse(result2, "Should not be able to place zoom with insufficient travel time after trial_zoom")

        # Now try with sufficient travel time
        app3 = Appointment("3", "High", "zoom", 60)
        # 75 minutes after first appointment ends
        start3 = datetime(2025, 3, 9, 17, 15)  # 5:15pm
        end3 = datetime(2025, 3, 9, 18, 15)  # 6:15pm
        block3 = (start3, end3)

        app3.days.append({
            "day_index": day_index,
            "blocks": [block3]
        })

        result3 = can_place_block(app3, day_index, block3, self.calendar,
                                  self.used_field_hours, self.settings,
                                  self.day_appointments)

        print(f"Can place zoom with sufficient travel time after trial_zoom: {result3}")
        self.assertTrue(result3, "Should be able to place zoom with sufficient travel time after trial_zoom")

        print("test_trial_regular_travel_time PASSED")

    def test_isolated_street_session(self):
        """Test that days with only one street session are invalid."""
        print("\n--- Running test_isolated_street_session ---")

        # Create a schedule with just one street session on a day
        day_index = 0  # Sunday

        app = Appointment("1", "High", "streets", 60)
        start = datetime(2025, 3, 9, 14, 0)
        end = datetime(2025, 3, 9, 15, 15)
        block = (start, end)

        app.days.append({
            "day_index": day_index,
            "blocks": [block]
        })

        # Check if can_place_block allows placing a trial street session alone
        result = can_place_block(app, day_index, block, self.calendar,
                                 self.used_field_hours, self.settings,
                                 self.day_appointments)

        print(f"Can place trial_streets session alone: {result}")
        self.assertTrue(result, "Should be able to place trial_streets session alone (counts as 2)")

        # Place the appointment
        place_block(app, day_index, block, self.calendar,
                    self.used_field_hours, self.final_schedule,
                    self.day_appointments)

        # Validate the schedule - should be valid because trial_streets counts as 2
        validation = validate_schedule(self.final_schedule)
        print(f"Validation result for trial_streets session: {validation}")

        # Check for any issues related to isolated sessions
        isolated_issues = [i for i in validation["issues"] if "isolated" in i or "needs at least 2" in i]
        self.assertEqual(len(isolated_issues), 0, "Should not have isolated street session issues with trial_streets")

        print("test_trial_street_counts_as_two PASSED")

    def test_full_scheduling_with_constraints(self):
        """Test the full scheduling algorithm with all constraints."""
        print("\n--- Running test_full_scheduling_with_constraints ---")

        # Create a test dataset with various appointment types and constraints
        test_data = {
            "start_date": "2025-03-09",  # Sunday
            "appointments": [
                # Sunday - two street sessions
                {
                    "id": "1-sunday",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-09T14:00:00", "end": "2025-03-09T18:00:00"}
                    ]}]
                },
                {
                    "id": "2-sunday",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-09T14:00:00", "end": "2025-03-09T18:00:00"}
                    ]}]
                },
                # Monday - trial street session (counts as 2)
                {
                    "id": "3-monday",
                    "priority": "High",
                    "type": "trial_streets",
                    "time": 120,
                    "days": [{"day": "Monday", "time_frames": [
                        {"start": "2025-03-10T14:00:00", "end": "2025-03-10T18:00:00"}
                    ]}]
                },
                # Monday - regular zoom session with enough travel time
                {
                    "id": "4-monday",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Monday", "time_frames": [
                        {"start": "2025-03-10T10:00:00", "end": "2025-03-10T13:00:00"}
                    ]}]
                },
                # Tuesday - trial zoom and regular zoom
                {
                    "id": "5-tuesday",
                    "priority": "High",
                    "type": "trial_zoom",
                    "time": 120,
                    "days": [{"day": "Tuesday", "time_frames": [
                        {"start": "2025-03-11T10:00:00", "end": "2025-03-11T14:00:00"}
                    ]}]
                },
                {
                    "id": "6-tuesday",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Tuesday", "time_frames": [
                        {"start": "2025-03-11T16:00:00", "end": "2025-03-11T20:00:00"}
                    ]}]
                }
            ]
        }

        # Parse appointments
        appointments = parse_appointments(test_data)
        print(f"Parsed {len(appointments)} appointments")

        # Run scheduling
        success, final_schedule, unscheduled = schedule_appointments(appointments, self.settings)

        print(f"Scheduling result: success={success}, scheduled={len(final_schedule)}, unscheduled={len(unscheduled)}")
        self.assertTrue(success, "Scheduling should succeed")
        self.assertEqual(len(final_schedule), len(appointments), "All appointments should be scheduled")

        # Validate the schedule
        validation = validate_schedule(final_schedule)
        print(f"Validation result: {validation}")
        self.assertTrue(validation["valid"], "Schedule should be valid with all constraints satisfied")

        # Check each day's appointments
        days = {}
        for app_id, (start, end, app_type) in final_schedule.items():
            day = start.strftime("%A")
            if day not in days:
                days[day] = []
            days[day].append((app_id, app_type, start, end))

        for day, appointments in days.items():
            print(f"\n{day} appointments:")
            for app_id, app_type, start, end in sorted(appointments, key=lambda x: x[2]):
                gap = ""
                if len(appointments) > 1:
                    for other_id, other_type, other_start, other_end in appointments:
                        if other_start > end:
                            minutes = (other_start - end).total_seconds() / 60
                            if minutes < 120:  # Only show gaps less than 2 hours
                                gap = f" (Gap to next: {minutes} min)"
                                break
                print(f"  {app_id}: {app_type} at {start.strftime('%H:%M')} - {end.strftime('%H:%M')}{gap}")

        print("test_full_scheduling_with_constraints PASSED")


if __name__ == "__main__":
    print("Starting TestSchedulingConstraints tests")
    unittest.main(verbosity=2)
    # Place the appointment
    place_block(app, day_index, block, self.calendar,
                self.used_field_hours, self.final_schedule,
                self.day_appointments)

    # Validate the schedule - should fail with isolated street session
    validation = validate_schedule(self.final_schedule)
    print(f"Validation result for isolated street session: {validation}")
    self.assertFalse(validation["valid"], "Schedule with isolated street session should be invalid")

    # Check for the right validation issue
    isolated_issues = [i for i in validation["issues"] if "isolated" in i or "needs at least 2" in i]
    self.assertTrue(len(isolated_issues) > 0, "Should identify isolated street session issue")

    # Now add a second street session and validate again
    app2 = Appointment("2", "High", "streets", 60)
    start2 = datetime(2025, 3, 9, 16, 0)  # 4pm - with travel time gap
    end2 = datetime(2025, 3, 9, 17, 15)
    block2 = (start2, end2)

    app2.days.append({
        "day_index": day_index,
        "blocks": [block2]
    })

    # Place the second appointment
    place_block(app2, day_index, block2, self.calendar,
                self.used_field_hours, self.final_schedule,
                self.day_appointments)

    # Validate the schedule again - should now be valid
    validation2 = validate_schedule(self.final_schedule)
    print(f"Validation result after adding second street session: {validation2}")

    # Check for any issues related to isolated sessions
    isolated_issues2 = [i for i in validation2["issues"] if "isolated" in i or "needs at least 2" in i]
    self.assertEqual(len(isolated_issues2), 0,
                     "Should not have isolated street session issues after adding second session")

    print("test_isolated_street_session PASSED")


def test_trial_street_counts_as_two(self):
    """Test that a trial_streets session counts as two sessions and is never isolated."""
    print("\n--- Running test_trial_street_counts_as_two ---")

    # Create a schedule with just one trial_streets session
    day_index = 0  # Sunday

    app = Appointment("1", "High", "trial_streets", 120)
    start = datetime(2025, 3, 9, 14, 0)
    end = datetime(2025, 3, 9, 16, 15)
    block = (start, end)

    app.days.append({
        "day_index": day_index,
        "blocks": [block]
    })
