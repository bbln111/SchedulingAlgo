#!/usr/bin/env python3
"""
test_scheduler.py - Test the scheduling system without Monday.com integration
"""

import argparse
import os
import sys
import json
import logging
from datetime import datetime, timedelta
import random
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
sys.path.append(str(parent_dir))

# Import necessary modules
from david_sdk import run_on_file

# Optional imports - don't fail if these aren't available
try:
    from etc_functions import should_rerun, unite_output_from_script
except ImportError:
    logger.warning("etc_functions module not found. Some functionality may be limited.")


    # Provide stub implementations
    def should_rerun(output):
        return False


    def unite_output_from_script(output):
        return output

try:
    from visualization import generate_html_visualization
except ImportError:
    logger.warning("visualization module not found. HTML visualization will be disabled.")


    # Provide stub implementation
    def generate_html_visualization(data, output_file):
        logger.warning(f"HTML visualization not available. Skipping generation of {output_file}")
        return False


def find_flask_script():
    """Find the Flask server script based on the project structure"""
    # Start with the parent directory and look for calculate.py
    potential_paths = [
        parent_dir / "calculate.py",
        parent_dir / "Calendar_Automation" / "calculate.py",
        script_dir.parent / "Calendar_Automation" / "calculate.py",
    ]

    for path in potential_paths:
        if path.exists():
            logger.info(f"Found Flask script at: {path}")
            return str(path)

    logger.warning("Flask script not found automatically")
    return None


def generate_sample_input(output_file, start_date=None, num_clients=5, days_range=5):
    """
    Generate sample input file for testing the scheduling algorithm

    Args:
        output_file (str): Path to save the generated file
        start_date (str, optional): Start date in YYYY-MM-DD format. Defaults to today.
        num_clients (int, optional): Number of clients to generate. Defaults to 5.
        days_range (int, optional): Number of days to include. Defaults to 5.

    Returns:
        str: Path to the generated file
    """
    # Parse start date or use today
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now()

    # Create sample data structure
    sample_data = {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "appointments": []
    }

    # Generate appointments
    client_types = ["zoom", "streets", "trial_zoom", "trial_streets"]
    priorities = ["High", "Medium", "Low"]

    for i in range(1, num_clients + 1):
        # Pick random type and priority
        app_type = random.choice(client_types)
        priority = random.choice(priorities)

        # Set appointment time based on type
        if "trial" in app_type:
            app_time = 120  # Trial sessions are 2 hours
        else:
            app_time = random.choice([45, 60, 90])  # Regular sessions

        # Generate the appointment
        appointment = {
            "id": f"client_{i}",
            "type": app_type,
            "priority": priority,
            "time": app_time,
            "days": []
        }

        # Generate availability for multiple days
        weekday_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        # Pick a random subset of days
        available_days = random.sample(weekday_names, min(random.randint(1, 5), days_range))

        for day_name in available_days:
            day_index = weekday_names.index(day_name)
            current_date = start_date + timedelta(days=day_index)

            # Generate 1-3 time frames per day
            time_frames = []
            for _ in range(random.randint(1, 3)):
                # Random start hour between 9 and 16
                start_hour = random.randint(9, 16)
                # End 2-4 hours later
                end_hour = min(start_hour + random.randint(2, 4), 20)

                time_frames.append({
                    "start": f"{current_date.strftime('%Y-%m-%d')}T{start_hour:02d}:00:00",
                    "end": f"{current_date.strftime('%Y-%m-%d')}T{end_hour:02d}:00:00"
                })

            # Add the day's availability
            appointment["days"].append({
                "day": day_name,
                "time_frames": time_frames
            })

        # Add this appointment to the list
        sample_data["appointments"].append(appointment)

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2)

    logger.info(f"Generated sample input file with {num_clients} clients over {days_range} days")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description='Test the scheduling system')
    parser.add_argument('--generate', '-g', action='store_true', help='Generate sample input data')
    parser.add_argument('--input', '-i', type=str, help='Input file (if not generating sample data)')
    parser.add_argument('--output', '-o', type=str, default='test_results.json', help='Output file for results')
    parser.add_argument('--html', action='store_true', help='Generate HTML visualization')
    parser.add_argument('--clients', type=int, default=5, help='Number of clients for sample data')
    parser.add_argument('--days', type=int, default=5, help='Number of days to schedule for sample data')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--flask-script', type=str, help='Path to Flask server script')
    parser.add_argument('--endpoint', type=str, default='/schedule', help='API endpoint to call')
    args = parser.parse_args()

    # Set input file
    input_file = None
    if args.generate:
        start_date = args.start_date or datetime.now().strftime('%Y-%m-%d')
        sample_file = f'sample_input_{start_date}.json'
        input_file = generate_sample_input(sample_file, start_date, args.clients, args.days)
        logger.info(f"Generated sample input file: {input_file}")
    elif args.input:
        input_file = args.input
    else:
        logger.error("Either --generate or --input must be specified")
        return

    # Get the Flask script path if not specified
    flask_script = args.flask_script
    if not flask_script:
        flask_script = find_flask_script()

    # Run the scheduler
    logger.info(f"Running scheduler with input file: {input_file}")
    output_from_script = run_on_file(input_file, flask_script, args.endpoint)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_from_script, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved results to {args.output}")

    # Generate HTML if requested
    if args.html:
        html_file = str(output_path).rsplit('.', 1)[0] + '.html'
        generate_html_visualization(output_from_script, html_file)
        logger.info(f"Generated HTML visualization: {html_file}")

    # Check if we should rerun based on the output
    try:
        if should_rerun(output_from_script):
            logger.info("Rerunning based on output")
            united_output = unite_output_from_script(output_from_script)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(united_output, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved united results to {args.output}")
    except Exception as e:
        logger.error(f"Error in rerun processing: {e}")
        logger.info("Continuing with original output")

    # Print summary
    filled = len(output_from_script.get('filled_appointments', []))
    unfilled = len(output_from_script.get('unfilled_appointments', []))
    valid = output_from_script.get('validation', {}).get('valid', False)

    logger.info(f"Scheduling complete: {filled} appointments scheduled, {unfilled} unfilled")

    # Show unfilled appointments if any
    if unfilled > 0:
        unfilled_ids = [app.get('id', 'unknown') for app in output_from_script.get('unfilled_appointments', [])]
        unfilled_types = [app.get('type', 'unknown') for app in output_from_script.get('unfilled_appointments', [])]
        logger.info(
            f"Unfilled appointments: {', '.join(f'{id}({type})' for id, type in zip(unfilled_ids, unfilled_types))}")

    logger.info(f"Schedule validation: {'Valid' if valid else 'Invalid'}")

    if not valid:
        issues = output_from_script.get('validation', {}).get('issues', [])
        for issue in issues:
            logger.info(f"  - {issue}")


if __name__ == '__main__':
    main()
