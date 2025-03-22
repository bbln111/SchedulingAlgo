import sys
import os

# Add parent directory to path to import from Calendar_Automation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now you can import from the main package
from appointment_scheduler import schedule_appointments  # Adjust based on your actual function name


def test_with_existing_input_files(self):
    """Test with the existing input files in input_for_testing directory."""

    # Find all input files
    input_dir = Path("../input_for_testing")
    input_files = list(input_dir.glob("*.json"))

    self.assertGreater(len(input_files), 0, "No input files found in input_for_testing directory")

    for input_file in input_files:
        print(f"\nTesting with input file: {input_file.name}")

        # Run the scheduler with this input
        try:
            subprocess.run(
                ["python", "../appointment_scheduler.py", str(input_file)],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            self.fail(f"Scheduler failed with error: {e.stderr}")

        # Load the output
        with open("../schedule.json", "r") as f:
            output_data = json.load(f)

        # Validate the schedule
        validation = self.verify_schedule_validity(output_data["filled_appointments"])

        self.assertTrue(
            validation["valid"],
            f"Schedule validation failed for {input_file.name} with issues: {validation['issues']}"
        )

        print(f"✓ Successfully validated schedule for {input_file.name}")

