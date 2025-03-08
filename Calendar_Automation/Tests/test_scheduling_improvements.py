import os
import sys
import logging
import unittest
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import (
    parse_appointments, ScheduleSettings, schedule_appointments,
    enhanced_score_candidate, can_place_block, initialize_calendar
)


class TestSchedulingImprovements(unittest.TestCase):
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
        score1 = enhanced_score_candidate(0, (start2, end2), self.appointments[0], day_appointments)

        # Test scoring for a session with a bigger gap (should score higher/worse)
        start3 = datetime(2025, 3, 2, 18, 0)  # 60 min gap
        end3 = datetime(2025, 3, 2, 19, 0)
        score2 = enhanced_score_candidate(0, (start3, end3), self.appointments[0], day_appointments)

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


if __name__ == "__main__":
    unittest.main()
