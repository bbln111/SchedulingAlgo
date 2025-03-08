import sys
import os
import unittest
from datetime import datetime, timedelta

# Add parent directory to path, so we can import the calculate module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import parse_appointments, Appointment, validate_schedule


class TestCalculations(unittest.TestCase):
    def test_parse_appointments(self):
        """Test the parse_appointments function with various input scenarios."""
        test_data = {
            "start_date": "2025-03-02",
            "appointments": [
                {
                    "id": "1",
                    "priority": "High",
                    "type": "streets",
                    "time": 60,
                    "days": [
                        {
                            "day": "Sunday",
                            "time_frames": [
                                {
                                    "start": "2025-03-02T16:00:00",
                                    "end": "2025-03-02T20:00:00"
                                }
                            ]
                        }
                    ]
                },
                {
                    "id": "2",
                    "priority": "High",
                    "type": "trial_streets",
                    # No time specified - should use default 120 minutes
                    "days": [
                        {
                            "day": "Monday",
                            "time_frames": {  # Dict format
                                "start": "2025-03-03T19:00:00",
                                "end": "2025-03-03T22:00:00"
                            }
                        }
                    ]
                },
                {
                    "id": "3",
                    "priority": "High",
                    "type": "trial_streets",
                    "time": 90,  # Explicitly specify 90 minutes
                    "days": [
                        {
                            "day": "Tuesday",
                            "time_frames": [
                                {
                                    "start": "2025-03-04T19:00:00",
                                    "end": "2025-03-04T22:00:00"
                                }
                            ]
                        }
                    ]
                },
                {
                    "id": "4",
                    "priority": "Exclude",  # Should be skipped
                    "type": "zoom",
                    "time": 60,
                    "days": [
                        {
                            "day": "Tuesday",
                            "time_frames": [
                                {
                                    "start": "2025-03-04T19:00:00",
                                    "end": "2025-03-04T22:00:00"
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        appointments = parse_appointments(test_data)

        # Assert we have only 3 appointments (Exclude was skipped)
        self.assertEqual(len(appointments), 3)

        # Test regular appointment
        self.assertEqual(appointments[0].id, "1")
        self.assertEqual(appointments[0].type, "streets")
        self.assertEqual(appointments[0].length, 60)

        # Test trial appointment with default duration
        self.assertEqual(appointments[1].id, "2")
        self.assertEqual(appointments[1].type, "trial_streets")
        self.assertEqual(appointments[1].length, 120)  # Default 120 minutes

        # Test trial appointment with specified duration
        self.assertEqual(appointments[2].id, "3")
        self.assertEqual(appointments[2].type, "trial_streets")
        self.assertEqual(appointments[2].length, 90)  # Custom 90 minutes

        # Verify blocks were created properly for all formats
        self.assertTrue(len(appointments[0].days[0]["blocks"]) > 0)
        self.assertTrue(len(appointments[1].days[0]["blocks"]) > 0)
        self.assertTrue(len(appointments[2].days[0]["blocks"]) > 0)


class TestValidateSchedule(unittest.TestCase):
    def setUp(self):
        """Setup common test data."""
        # Base time for tests
        self.base_time = datetime(2025, 3, 2, 12, 0)  # Sunday at noon

        # Empty initial schedule
        self.schedule = {}

    def test_valid_schedule(self):
        """Test a valid schedule with proper street session distribution."""
        # Add 2 street sessions to Sunday (day 0)
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Add 2 street sessions to Monday (day 1)
        monday = self.base_time + timedelta(days=1)
        self.schedule["3"] = (
            monday,
            monday + timedelta(hours=1),
            "streets"
        )
        self.schedule["4"] = (
            monday + timedelta(hours=1, minutes=15),
            monday + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid with no issues
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_isolated_street_session(self):
        """Test schedule with isolated street session on a day."""
        # Add 2 street sessions to Sunday (day 0)
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Add only 1 street session to Monday (day 1) - should be invalid
        monday = self.base_time + timedelta(days=1)
        self.schedule["3"] = (
            monday,
            monday + timedelta(hours=1),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be invalid due to isolated session
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["issues"]), 1)
        self.assertTrue(any("has only one street session" in issue for issue in result["issues"]))

    def test_trial_streets_not_isolated(self):
        """Test that a single trial_streets session is not considered isolated."""
        # Add 2 street sessions to Sunday (day 0)
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Add only 1 trial_streets session to Monday (day 1) - should be valid
        monday = self.base_time + timedelta(days=1)
        self.schedule["3"] = (
            monday,
            monday + timedelta(hours=1),
            "trial_streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid as trial_streets is not considered isolated
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_trial_streets_with_regular_street(self):
        """Test trial_streets session with regular street session on same day."""
        # Add a trial_streets session and a regular streets session to the same day
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "trial_streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_large_gap_between_sessions(self):
        """Test schedule with a large gap between street sessions."""
        # Add 2 street sessions to Sunday with a large gap between them
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=2),  # 1-hour gap (> 30 minutes)
            self.base_time + timedelta(hours=3),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be invalid due to large gap
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["issues"]), 1)
        self.assertTrue(any("gap" in issue for issue in result["issues"]))

    def test_acceptable_gap_between_sessions(self):
        """Test schedule with an acceptable gap between street sessions."""
        # Add 2 street sessions to Sunday with an acceptable gap
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=30),  # 30-minute gap (boundary case)
            self.base_time + timedelta(hours=2, minutes=30),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_multiple_appointments_same_client(self):
        """Test schedule with multiple appointments for the same client on one day."""
        # Add 2 appointments for client ID 1 on the same day
        self.schedule["1-1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["1-2"] = (
            self.base_time + timedelta(hours=2),
            self.base_time + timedelta(hours=3),
            "zoom"
        )

        # Add valid appointments on another day
        monday = self.base_time + timedelta(days=1)
        self.schedule["2-1"] = (
            monday,
            monday + timedelta(hours=1),
            "streets"
        )
        self.schedule["3-1"] = (
            monday + timedelta(hours=1, minutes=15),
            monday + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be invalid due to multiple appointments for same client
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["issues"]), 1)
        self.assertTrue(any("multiple appointments" in issue for issue in result["issues"]))

    def test_different_clients_same_day(self):
        """Test schedule with different clients on the same day."""
        # Add appointments for different clients on the same day
        self.schedule["1-1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "streets"
        )
        self.schedule["2-1"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_field_type_equivalent_to_streets(self):
        """Test that 'field' type is treated the same as 'streets'."""
        # Add a 'field' session and a 'streets' session
        self.schedule["1"] = (
            self.base_time,
            self.base_time + timedelta(hours=1),
            "field"
        )
        self.schedule["2"] = (
            self.base_time + timedelta(hours=1, minutes=15),
            self.base_time + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Should be valid
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)

    def test_weekday_conversion(self):
        """Test correct handling of weekday conversion between Python and the system."""
        # Add street sessions across different days to verify correct day indexing
        # We need to account for Python's weekday() where Monday=0, Sunday=6

        # Map of Python weekday to your system's day index
        # Python:   0   1   2   3   4   5   6
        # System:   1   2   3   4   5   0
        # (Monday=1, Tuesday=2, ..., Sunday=0)

        # Sunday (Python weekday 6 → system day 0)
        sunday = self.base_time  # Base time is Sunday
        self.schedule["Sunday-1"] = (
            sunday,
            sunday + timedelta(hours=1),
            "streets"
        )
        self.schedule["Sunday-2"] = (
            sunday + timedelta(hours=1, minutes=15),
            sunday + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Monday (Python weekday 0 → system day 1)
        monday = self.base_time + timedelta(days=1)
        self.schedule["Monday-1"] = (
            monday,
            monday + timedelta(hours=1),
            "streets"
        )
        self.schedule["Monday-2"] = (
            monday + timedelta(hours=1, minutes=15),
            monday + timedelta(hours=2, minutes=15),
            "streets"
        )

        # Add pairs for other days
        days = [
            (2, "Tuesday", 2),  # Tuesday (Python weekday 1 → system day 2)
            (3, "Wednesday", 3),  # Wednesday (Python weekday 2 → system day 3)
            (4, "Thursday", 4),  # Thursday (Python weekday 3 → system day 4)
            (5, "Friday", 5)  # Friday (Python weekday 4 → system day 5)
        ]

        for day_offset, day_name, _ in days:
            day_date = self.base_time + timedelta(days=day_offset)
            self.schedule[f"{day_name}-1"] = (
                day_date,
                day_date + timedelta(hours=1),
                "streets"
            )
            self.schedule[f"{day_name}-2"] = (
                day_date + timedelta(hours=1, minutes=15),
                day_date + timedelta(hours=2, minutes=15),
                "streets"
            )

        # Validate the schedule
        result = validate_schedule(self.schedule)

        # Print debug info for failures
        if not result["valid"]:
            print("Validation issues:", result["issues"])

        # Should be valid - all days have at least 2 street sessions
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)


if __name__ == "__main__":
    unittest.main()
