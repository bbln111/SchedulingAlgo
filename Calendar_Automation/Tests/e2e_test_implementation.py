import unittest
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the main package
from appointment_scheduler import (
    schedule_appointments,
    time_to_minutes,
    minutes_to_time,
    day_name_to_number
)


class SchedulerE2ETests(unittest.TestCase):
    """End-to-end tests for appointment_scheduler.py"""

    def setUp(self):
        """Set up the test environment."""
        # Use input_for_testing directory for test files
        self.input_dir = Path("../input_for_testing")
        self.output_dir = Path("./test_outputs")

        # Create output directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir()

    def verify_minimum_break_between_appointments(self, scheduled_appointments):
        """
        Verify constraint 1: Minimum 15-minute break between any appointments.
        """
        issues = []

        # Group appointments by date
        appointments_by_day = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in appointments_by_day:
                appointments_by_day[day] = []
            appointments_by_day[day].append(appt)

        # Check each day's appointments
        for day, appointments in appointments_by_day.items():
            # Sort by start time
            appointments.sort(key=lambda x: x['start_time'])

            for i in range(len(appointments) - 1):
                current_appt = appointments[i]
                next_appt = appointments[i + 1]

                current_end = time_to_minutes(current_appt['end_time'])
                next_start = time_to_minutes(next_appt['start_time'])

                # Calculate break duration in minutes
                break_duration = next_start - current_end

                if break_duration < 15:
                    issues.append(
                        f"Insufficient break between appointments on {day}: "
                        f"ID {current_appt['client_id']} ({current_appt['type']}) and "
                        f"ID {next_appt['client_id']} ({next_appt['type']}). "
                        f"Break is {break_duration} minutes (minimum: 15 minutes)."
                    )

        return issues

    def verify_zoom_streets_break(self, scheduled_appointments):
        """
        Verify constraint 2: Minimum 75-minute break between zoom and streets appointments.
        """
        issues = []

        # Group appointments by date
        appointments_by_day = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in appointments_by_day:
                appointments_by_day[day] = []
            appointments_by_day[day].append(appt)

        # Check each day's appointments
        for day, appointments in appointments_by_day.items():
            # Sort by start time
            appointments.sort(key=lambda x: x['start_time'])

            for i in range(len(appointments) - 1):
                current_appt = appointments[i]
                next_appt = appointments[i + 1]

                current_type = current_appt['type']
                next_type = next_appt['type']

                # Check if one is zoom-related and the other is streets-related
                current_is_zoom = "zoom" in current_type
                current_is_streets = "streets" in current_type
                next_is_zoom = "zoom" in next_type
                next_is_streets = "streets" in next_type

                if (current_is_zoom and next_is_streets) or (current_is_streets and next_is_zoom):
                    current_end = time_to_minutes(current_appt['end_time'])
                    next_start = time_to_minutes(next_appt['start_time'])

                    # Calculate break duration in minutes
                    break_duration = next_start - current_end

                    if break_duration < 75:
                        issues.append(
                            f"Insufficient break between zoom and streets appointments on {day}: "
                            f"ID {current_appt['client_id']} ({current_appt['type']}) and "
                            f"ID {next_appt['client_id']} ({next_appt['type']}). "
                            f"Break is {break_duration} minutes (minimum: 75 minutes)."
                        )

        return issues

    def verify_consecutive_streets_sessions(self, scheduled_appointments, max_street_gap=30):
        """
        Verify constraint 3: Minimum of two consecutive streets sessions in one calendar day, or none at all.
        Also verify that breaks between consecutive streets sessions are 15-30 minutes.
        """
        issues = []

        # Group appointments by date
        appointments_by_day = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in appointments_by_day:
                appointments_by_day[day] = []
            appointments_by_day[day].append(appt)

        # Check each day
        for day, appointments in appointments_by_day.items():
            # Count streets sessions
            streets_appointments = [
                appt for appt in appointments
                if "streets" in appt['type']
            ]

            num_streets = len(streets_appointments)

            # Verify either 0 or at least 2 streets sessions
            if 0 < num_streets < 2:
                issues.append(
                    f"Invalid number of streets sessions on {day}: {num_streets}. "
                    f"Must be either 0 or at least 2."
                )

            # If there are streets sessions, verify they are consecutive with 15-30 minute gaps
            if num_streets >= 2:
                # Sort by start time
                streets_appointments.sort(key=lambda x: x['start_time'])

                # Check breaks between consecutive streets sessions
                for i in range(len(streets_appointments) - 1):
                    current_end = time_to_minutes(streets_appointments[i]['end_time'])
                    next_start = time_to_minutes(streets_appointments[i + 1]['start_time'])

                    # Calculate break duration in minutes
                    break_duration = next_start - current_end

                    # Verify minimum break (15 minutes)
                    if break_duration < 15:
                        issues.append(
                            f"Break between streets sessions on {day} is too short: "
                            f"{break_duration} minutes (minimum: 15 minutes). "
                            f"ID {streets_appointments[i]['client_id']} and ID {streets_appointments[i + 1]['client_id']}."
                        )

                    # Verify maximum break (30 minutes)
                    if break_duration > max_street_gap:
                        issues.append(
                            f"Break between streets sessions on {day} is too long: "
                            f"{break_duration} minutes (maximum: {max_street_gap} minutes). "
                            f"ID {streets_appointments[i]['client_id']} and ID {streets_appointments[i + 1]['client_id']}."
                        )

        return issues

    def verify_max_streets_duration(self, scheduled_appointments, max_street_minutes=270):
        """
        Verify constraint 4: Maximum 270 minutes of streets sessions per day.
        """
        issues = []

        # Group appointments by date
        appointments_by_day = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in appointments_by_day:
                appointments_by_day[day] = []
            appointments_by_day[day].append(appt)

        # Check each day
        for day, appointments in appointments_by_day.items():
            # Calculate total streets duration
            total_streets_minutes = 0
            for appt in appointments:
                if "streets" in appt['type']:
                    total_streets_minutes += appt['duration']

            if total_streets_minutes > max_street_minutes:
                issues.append(
                    f"Total streets duration on {day} exceeds maximum: "
                    f"{total_streets_minutes} minutes (max: {max_street_minutes} minutes)."
                )

        return issues

    def verify_one_appointment_per_client_per_day(self, scheduled_appointments):
        """
        Verify constraint 5: One appointment per client per calendar day.
        """
        issues = []

        # Group appointments by date and client
        appointments_by_day_client = {}
        for appt in scheduled_appointments:
            day = appt['date']
            client_id = appt['client_id']

            if day not in appointments_by_day_client:
                appointments_by_day_client[day] = {}

            if client_id not in appointments_by_day_client[day]:
                appointments_by_day_client[day][client_id] = []

            appointments_by_day_client[day][client_id].append(appt)

        # Check each day and client
        for day, clients in appointments_by_day_client.items():
            for client_id, client_appointments in clients.items():
                if len(client_appointments) > 1:
                    issues.append(
                        f"Client {client_id} has multiple appointments on {day}: "
                        f"{len(client_appointments)} appointments."
                    )

        return issues

    def verify_all_constraints(self, scheduled_appointments, max_street_gap=30, max_street_minutes=270):
        """
        Verify all constraints and build a validation report.
        """
        all_issues = []

        # Verify each constraint
        all_issues.extend(self.verify_minimum_break_between_appointments(scheduled_appointments))
        all_issues.extend(self.verify_zoom_streets_break(scheduled_appointments))
        all_issues.extend(self.verify_consecutive_streets_sessions(scheduled_appointments, max_street_gap))
        all_issues.extend(self.verify_max_streets_duration(scheduled_appointments, max_street_minutes))
        all_issues.extend(self.verify_one_appointment_per_client_per_day(scheduled_appointments))

        # Build validation report
        return {
            "valid": len(all_issues) == 0,
            "issues": all_issues
        }

    def test_scheduling_with_existing_inputs(self):
        """
        Test scheduling with all available input files in the input_for_testing directory.
        This directly calls the schedule_appointments function rather than executing the script.
        """
        input_files = list(self.input_dir.glob("*.json"))

        self.assertGreater(len(input_files), 0, "No input files found in input_for_testing directory")

        for input_file in input_files:
            with self.subTest(input_file=input_file.name):
                print(f"\nTesting with input file: {input_file.name}")

                # Call the schedule_appointments function directly
                scheduled_appointments, client_availabilities = schedule_appointments(str(input_file))

                # Verify the schedule meets all constraints
                validation = self.verify_all_constraints(scheduled_appointments)

                # Save the validation results for debugging
                validation_file = self.output_dir / f"validation_{input_file.name}"
                with open(validation_file, "w") as f:
                    json.dump(validation, f, indent=2)

                # Check if scheduling was successful
                self.assertGreater(len(scheduled_appointments), 0, f"No appointments scheduled for {input_file.name}")

                # Verify all constraints are satisfied
                self.assertTrue(
                    validation["valid"],
                    f"Schedule validation failed for {input_file.name} with issues: {validation['issues']}"
                )

                print(
                    f"✓ Successfully validated schedule for {input_file.name} with {len(scheduled_appointments)} appointments")

    def test_schedule_constraints_with_subprocess(self):
        """
        Test scheduling by executing the appointment_scheduler.py script as a subprocess.
        This verifies the script works correctly when called from command line.
        """
        input_files = list(self.input_dir.glob("*.json"))

        self.assertGreater(len(input_files), 0, "No input files found in input_for_testing directory")

        # Choose one file for subprocess testing
        input_file = input_files[0]

        print(f"\nTesting subprocess execution with: {input_file.name}")

        # Custom output paths for this test
        test_output_json = self.output_dir / f"subprocess_test_{input_file.name}"
        test_output_html = self.output_dir / f"subprocess_test_{input_file.stem}.html"

        # Run the scheduler as a subprocess
        try:
            result = subprocess.run(
                ["python", "../appointment_scheduler.py",
                 str(input_file),
                 "--output", str(test_output_json),
                 "--html", str(test_output_html)],
                check=True,
                capture_output=True,
                text=True
            )

            # Print captured output for debugging
            print(f"Subprocess output:\n{result.stdout}")

            # Check if output files were created
            self.assertTrue(test_output_json.exists(), f"Output JSON file not created: {test_output_json}")
            self.assertTrue(test_output_html.exists(), f"Output HTML file not created: {test_output_html}")

            # Load the output JSON
            with open(test_output_json, "r") as f:
                output_data = json.load(f)

            # Verify output format
            self.assertIn("filled_appointments", output_data, "Output JSON missing filled_appointments field")
            self.assertIn("unfilled_appointments", output_data, "Output JSON missing unfilled_appointments field")
            self.assertIn("validation", output_data, "Output JSON missing validation field")
            self.assertIn("type_balance", output_data, "Output JSON missing type_balance field")

            # Extract scheduled appointments for validation
            scheduled_appointments = []
            for appt in output_data["filled_appointments"]:
                # Convert ISO format to the format used in our validation functions
                client_id = appt["id"]
                session_type = appt["type"]

                # Parse ISO format datetime
                start_time_dt = datetime.fromisoformat(appt["start_time"])
                end_time_dt = datetime.fromisoformat(appt["end_time"])

                # Calculate duration
                duration_minutes = int((end_time_dt - start_time_dt).total_seconds() / 60)

                scheduled_appointments.append({
                    "client_id": client_id,
                    "type": session_type,
                    "date": start_time_dt.date().isoformat(),
                    "start_time": start_time_dt.strftime("%H:%M"),
                    "end_time": end_time_dt.strftime("%H:%M"),
                    "duration": duration_minutes
                })

            # Verify the schedule meets all constraints
            validation = self.verify_all_constraints(scheduled_appointments)

            self.assertTrue(
                validation["valid"],
                f"Schedule validation failed for subprocess test with issues: {validation['issues']}"
            )

            print(f"✓ Successfully validated subprocess execution with {len(scheduled_appointments)} appointments")

        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess execution failed: {e.stderr}")

    def test_specific_day_scheduling(self):
        """
        Test scheduling for a specific day to verify constraints are met across days.
        """
        # Choose the second test file (if available) or the first one
        input_files = list(self.input_dir.glob("*.json"))

        self.assertGreater(len(input_files), 0, "No input files found in input_for_testing directory")

        input_file = input_files[1] if len(input_files) > 1 else input_files[0]

        print(f"\nTesting specific day scheduling with: {input_file.name}")

        # Schedule appointments
        scheduled_appointments, client_availabilities = schedule_appointments(str(input_file))

        # Group appointments by date
        appointments_by_day = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in appointments_by_day:
                appointments_by_day[day] = []
            appointments_by_day[day].append(appt)

        # Check if there are any days with streets sessions
        streets_days = []
        for day, appointments in appointments_by_day.items():
            streets_count = sum(1 for appt in appointments if "streets" in appt['type'])
            if streets_count > 0:
                streets_days.append((day, streets_count))

        self.assertGreater(len(streets_days), 0, "No days with streets sessions found")

        # Find a day with the most streets sessions
        test_day, streets_count = max(streets_days, key=lambda x: x[1])

        print(f"Testing day {test_day} with {streets_count} streets sessions")

        # Get appointments for this day
        day_appointments = appointments_by_day[test_day]

        # Filter streets appointments
        streets_appointments = [appt for appt in day_appointments if "streets" in appt['type']]

        # Verify there are 0 or at least 2 streets sessions
        self.assertNotEqual(len(streets_appointments), 1,
                            f"Invalid number of streets sessions on {test_day}: 1. Must be either 0 or at least 2.")

        if len(streets_appointments) >= 2:
            # Sort by start time
            streets_appointments.sort(key=lambda x: x['start_time'])

            # Check breaks between consecutive streets sessions
            for i in range(len(streets_appointments) - 1):
                current_end = time_to_minutes(streets_appointments[i]['end_time'])
                next_start = time_to_minutes(streets_appointments[i + 1]['start_time'])

                # Calculate break duration in minutes
                break_duration = next_start - current_end

                # Verify minimum break (15 minutes)
                self.assertGreaterEqual(
                    break_duration,
                    15,
                    f"Break between streets sessions on {test_day} is too short: {break_duration} minutes"
                )

                # Verify maximum break (30 minutes)
                self.assertLessEqual(
                    break_duration,
                    30,
                    f"Break between streets sessions on {test_day} is too long: {break_duration} minutes"
                )

    def test_example_from_documentation(self):
        """
        Test the specific example shown in your documentation to ensure
        the scheduler produces expected results.
        """
        # Define the expected output based on your example
        expected_output = [
            {"id": "7", "type": "trial_streets", "start_time": "2025-03-02T17:00:00",
             "end_time": "2025-03-02T19:00:00"},
            {"id": "8", "type": "trial_streets", "start_time": "2025-03-02T19:15:00",
             "end_time": "2025-03-02T21:15:00"},
            {"id": "1", "type": "streets", "start_time": "2025-03-04T17:00:00", "end_time": "2025-03-04T18:00:00"},
            {"id": "3", "type": "streets", "start_time": "2025-03-04T18:15:00", "end_time": "2025-03-04T19:15:00"},
            {"id": "2", "type": "streets", "start_time": "2025-03-04T19:30:00", "end_time": "2025-03-04T20:30:00"},
            {"id": "4", "type": "zoom", "start_time": "2025-03-05T16:00:00", "end_time": "2025-03-05T17:00:00"},
            {"id": "6", "type": "zoom", "start_time": "2025-03-05T17:15:00", "end_time": "2025-03-05T18:15:00"},
            {"id": "5", "type": "zoom", "start_time": "2025-03-05T18:30:00", "end_time": "2025-03-05T19:30:00"},
            {"id": "13", "type": "streets", "start_time": "2025-03-06T14:30:00", "end_time": "2025-03-06T15:30:00"},
            {"id": "10", "type": "streets", "start_time": "2025-03-06T15:45:00", "end_time": "2025-03-06T16:45:00"},
            {"id": "12", "type": "zoom", "start_time": "2025-03-06T18:15:00", "end_time": "2025-03-06T19:15:00"},
            {"id": "11", "type": "trial_zoom", "start_time": "2025-03-06T19:30:00", "end_time": "2025-03-06T21:00:00"},
            {"id": "14", "type": "streets", "start_time": "2025-03-07T12:45:00", "end_time": "2025-03-07T13:45:00"},
            {"id": "9", "type": "streets", "start_time": "2025-03-07T14:00:00", "end_time": "2025-03-07T15:00:00"},
            {"id": "15", "type": "streets", "start_time": "2025-03-07T15:15:00", "end_time": "2025-03-07T16:15:00"}
        ]

        # Find the specific input file that corresponds to this example
        # Usually it's input_for_testing_2.json based on your example
        test_file = self.input_dir / "input_for_testing_2.json"

        if test_file.exists():
            print(f"\nTesting with documented example: {test_file.name}")

            # Schedule appointments
            scheduled_appointments, client_availabilities = schedule_appointments(str(test_file))

            # Convert to output format for comparison
            actual_output = []
            for appt in scheduled_appointments:
                client_id = appt["client_id"]
                session_type = appt["type"]
                date = appt["date"]
                start_time = appt["start_time"]
                end_time = appt["end_time"]

                # Convert to ISO format for comparison
                start_time_iso = f"{date}T{start_time}:00"
                end_time_iso = f"{date}T{end_time}:00"

                actual_output.append({
                    "id": client_id,
                    "type": session_type,
                    "start_time": start_time_iso,
                    "end_time": end_time_iso
                })

            # We'll do a "fuzzy" comparison since exact times might vary slightly
            # Check that all expected clients are scheduled
            expected_clients = {appt["id"] for appt in expected_output}
            actual_clients = {appt["id"] for appt in actual_output}

            self.assertEqual(
                expected_clients,
                actual_clients,
                f"Scheduled clients don't match expected. Missing: {expected_clients - actual_clients}, "
                f"Extra: {actual_clients - expected_clients}"
            )

            # Check that all constraints are maintained
            validation = self.verify_all_constraints(scheduled_appointments)

            self.assertTrue(
                validation["valid"],
                f"Schedule validation failed for example with issues: {validation['issues']}"
            )

            # Check specific day patterns
            # Sunday should have 2 trial_streets sessions
            sunday_appts = [appt for appt in scheduled_appointments if appt["date"] == "2025-03-02"]
            sunday_trial_streets = [appt for appt in sunday_appts if appt["type"] == "trial_streets"]
            self.assertEqual(len(sunday_trial_streets), 2, "Sunday should have exactly 2 trial_streets sessions")

            # Tuesday should have 3 streets sessions
            tuesday_appts = [appt for appt in scheduled_appointments if appt["date"] == "2025-03-04"]
            tuesday_streets = [appt for appt in tuesday_appts if appt["type"] == "streets"]
            self.assertEqual(len(tuesday_streets), 3, "Tuesday should have exactly 3 streets sessions")

            print(f"✓ Successfully validated example schedule with {len(scheduled_appointments)} appointments")
        else:
            self.skipTest(f"Example input file {test_file} not found")


if __name__ == "__main__":
    unittest.main()
