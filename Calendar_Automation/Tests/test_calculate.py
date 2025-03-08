import sys
import os
import unittest
from datetime import datetime

# Add parent directory to path, so we can import the calculate module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import parse_appointments, Appointment


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
                    "time": 60,  # This should be overridden to 120
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

        # Assert we have only 2 appointments (Exclude was skipped)
        self.assertEqual(len(appointments), 2)

        # Test regular appointment
        self.assertEqual(appointments[0].id, "1")
        self.assertEqual(appointments[0].type, "streets")
        self.assertEqual(appointments[0].length, 60)

        # Test trial appointment with dict format time_frames
        self.assertEqual(appointments[1].id, "2")
        self.assertEqual(appointments[1].type, "trial_streets")
        self.assertEqual(appointments[1].length, 120)  # Should be 120 not 60

        # Verify blocks were created properly for both formats
        self.assertTrue(len(appointments[0].days[0]["blocks"]) > 0)
        self.assertTrue(len(appointments[1].days[0]["blocks"]) > 0)


if __name__ == "__main__":
    unittest.main()
