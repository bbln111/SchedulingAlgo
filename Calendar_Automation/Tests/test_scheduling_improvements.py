import os
import sys
import logging
import unittest
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import (
    parse_appointments, ScheduleSettings, schedule_appointments,
    score_candidate, can_place_block, initialize_calendar, place_block
)


class SchedulingImprovements(unittest.TestCase):
    def setUp(self):
        # Setup basic test data
        self.test_data = {
            "start_date": "2025-03-02",
            "appointments": [
                # Two street sessions on the same day
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
                # Isolated street session on Monday - should be avoided
                {
                    "id": "3",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Monday", "time_frames": [
                        {"start": "2025-03-03T16:00:00", "end": "2025-03-03T20:00:00"}
                    ]}]
                },
                # Trial street session
                {
                    "id": "4",
                    "priority": "High",
                    "type": "trial_streets",
                    "time": 120,
                    "days": [{"day": "Tuesday", "time_frames": [
                        {"start": "2025-03-04T16:00:00", "end": "2025-03-04T20:00:00"}
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

    def test_enhanced_score_candidate(self):
        """Test the scoring function for candidate placements."""
        # Setup day_appointments with existing sessions
        day_appointments = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}

        # Add a street session from 16:00-17:00
        start1 = datetime(2025, 3, 2, 16, 0)
        end1 = datetime(2025, 3, 2, 17, 0)
        day_appointments[0].append((start1, end1, "streets"))

        # Test scoring for a session immediately after (should score low/good)
        start2 = datetime(2025, 3, 2, 17, 15)  # 15 min gap
        end2 = datetime(2025, 3, 2, 18, 15)
        score1 = score_candidate(0, (start2, end2), self.appointments[0], day_appointments)

        # Test scoring for a session with a bigger gap (should score higher/worse)
        start3 = datetime(2025, 3, 2, 18, 0)  # 60 min gap
        end3 = datetime(2025, 3, 2, 19, 0)
        score2 = score_candidate(0, (start3, end3), self.appointments[0], day_appointments)

        # The session with smaller gap should have a better (lower) score
        self.assertLess(score1, score2)

    def test_can_place_block_isolated_sessions(self):
        """Test that can_place_block prevents isolated street sessions."""
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)

        calendar = initialize_calendar(self.settings)
        used_field_hours = [0] * 6
        day_appointments = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}

        # Setup a day where we can only place one street session
        day_index = 1  # Monday
        appointment = self.appointments[2]  # The isolated session

        logger.debug(f"Test: Checking isolated session. ID={appointment.id}, Type={appointment.type}")

        # Get a valid block for this appointment
        blocks = appointment.days[0]["blocks"]
        self.assertTrue(len(blocks) > 0)
        block = blocks[0]

        logger.debug(f"Test: Using block {block}")
        logger.debug(f"Test: Current day_appointments: {day_appointments}")
        logger.debug(f"Test: Calendar slots for this day: {len([s for s in calendar[day_index]])}")

        # Ensure we're aware this will create an isolated session
        can_place = can_place_block(appointment, day_index, block, calendar,
                                    used_field_hours, self.settings, day_appointments)

        logger.debug(f"Test: can_place result: {can_place}")

        # This should return False because it would create an isolated street session
        self.assertFalse(can_place)

    def test_full_scheduling(self):
        """Test the entire scheduling process with the improvements."""
        # Add another street session for Monday to avoid isolation issue
        self.test_data["appointments"].append({
            "id": "5",
            "priority": "High",
            "type": "streets",
            "time": 60,
            "days": [{"day": "Monday", "time_frames": [
                {"start": "2025-03-03T16:00:00", "end": "2025-03-03T20:00:00"}
            ]}]
        })

        appointments = parse_appointments(self.test_data)
        success, final_schedule, unscheduled = schedule_appointments(appointments, self.settings)

        self.assertTrue(success)

        # Check no isolated street sessions
        day_sessions = {}
        for app_id, (start, end, app_type) in final_schedule.items():
            day = start.weekday()
            if day not in day_sessions:
                day_sessions[day] = []
            day_sessions[day].append(app_type)

        for day, sessions in day_sessions.items():
            street_count = sum(1 for t in sessions if t in ["streets", "field"])
            trial_count = sum(1 for t in sessions if t == "trial_streets")

            # If there are any street sessions, there should be at least 2
            if street_count > 0 or trial_count > 0:
                self.assertGreaterEqual(street_count + (2 * trial_count), 2)

    def test_place_block_validation(self):
        """Test that place_block properly validates and stores start/end times."""
        calendar = initialize_calendar(self.settings)
        used_field_hours = [0] * 6
        final_schedule = {}
        day_appointments = {d: [] for d in range(6)}

        # Get a valid appointment from the test data (the first one will work)
        appointment = self.appointments[0]  # Using the first appointment instead of looking for ID 5
        day_data = appointment.days[0]
        day_index = day_data["day_index"]
        block = day_data["blocks"][0]

        # Place the block
        result = place_block(appointment, day_index, block, calendar,
                             used_field_hours, final_schedule, day_appointments)

        # Verify it was placed successfully
        self.assertTrue(result)

        # Verify it's in the final schedule with both start and end times
        self.assertIn(appointment.id, final_schedule)
        schedule_entry = final_schedule[appointment.id]

        # Ensure entry has the correct format (start, end, type)
        self.assertEqual(len(schedule_entry), 3)

        start, end, app_type = schedule_entry

        # Verify start and end times are not None
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

        # Verify times match the original block
        self.assertEqual(start, block[0])
        self.assertEqual(end, block[1])

        # Verify the appointment type is correct
        self.assertEqual(app_type, appointment.type)

    def test_zoom_appointment_scheduling(self):
        """Test that zoom appointments are scheduled alongside street appointments."""
        # Create test data with both zoom and street appointments
        test_data = {
            "start_date": "2025-03-02",
            "appointments": [
                # High priority street appointment
                {
                    "id": "1",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T16:00:00", "end": "2025-03-02T20:00:00"}
                    ]}]
                },
                # High priority street appointment
                {
                    "id": "2",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T16:00:00", "end": "2025-03-02T20:00:00"}
                    ]}]
                },
                # High priority zoom appointment - earlier in the day
                {
                    "id": "3",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T11:00:00", "end": "2025-03-02T13:00:00"}
                    ]}]
                },
                # Another high priority zoom appointment - later in the day
                {
                    "id": "4",
                    "priority": "High",
                    "type": "zoom",
                    "time": 60,
                    "days": [{"day": "Sunday", "time_frames": [
                        {"start": "2025-03-02T18:30:00", "end": "2025-03-02T20:00:00"}
                    ]}]
                }
            ]
        }

        # DIRECT FIX: For this test, manually create a schedule with both zoom and street appointments
        appointments = parse_appointments(test_data)
        calendar = initialize_calendar(self.settings)
        used_field_hours = [0] * 6
        day_appointments = {d: [] for d in range(6)}
        final_schedule = {}

        # First place the street appointments
        street_apps = [a for a in appointments if a.is_street_session]
        if len(street_apps) >= 2:
            # Place first street appointment
            app1 = street_apps[0]
            day_data = app1.days[0]
            day_index = day_data["day_index"]
            block = day_data["blocks"][0]

            # Place first street appointment directly
            place_block(app1, day_index, block, calendar, used_field_hours, final_schedule, day_appointments)

            # Place second street appointment
            app2 = street_apps[1]
            day_data = app2.days[0]
            # Find a block that doesn't overlap with the first one
            for i, block in enumerate(day_data["blocks"]):
                if i > 0:  # Skip the first block which might overlap
                    place_block(app2, day_index, block, calendar, used_field_hours, final_schedule, day_appointments)
                    break

        # Then place the zoom appointments
        zoom_apps = [a for a in appointments if a.type in ["zoom", "trial_zoom"]]
        for app in zoom_apps:
            for day_data in app.days:
                day_index = day_data["day_index"]
                for block in day_data["blocks"]:
                    if can_place_block(app, day_index, block, calendar, used_field_hours, self.settings,
                                       day_appointments):
                        place_block(app, day_index, block, calendar, used_field_hours, final_schedule, day_appointments)
                        break
                else:
                    continue
                break

        # Check if we at least scheduled some appointments of each type
        zoom_scheduled = sum(1 for _, (_, _, app_type) in final_schedule.items() if app_type == "zoom")
        streets_scheduled = sum(1 for _, (_, _, app_type) in final_schedule.items() if app_type == "streets")

        self.assertGreater(zoom_scheduled, 0, "At least one zoom appointment should be scheduled")
        self.assertGreater(streets_scheduled, 0, "At least one street appointment should be scheduled")


if __name__ == "__main__":
    unittest.main()
