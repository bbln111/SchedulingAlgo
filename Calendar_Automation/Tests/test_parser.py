#!/usr/bin/env python3
"""
test_parser.py - Test the appointment parsing functionality
"""

import os
import sys
import json
import logging
from datetime import datetime
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

# Import the parsing function
from calculate import parse_appointments, ScheduleSettings, schedule_appointments


def test_file_parser(file_path):
    """Test parsing appointments from a file"""
    try:
        # Load the file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Loaded file: {file_path}")
        logger.info(f"File contains {len(data.get('appointments', []))} appointments")

        # Parse appointments
        appointments = parse_appointments(data)

        logger.info(f"Successfully parsed {len(appointments)} appointments")

        # Count by type
        type_counts = {}
        for app in appointments:
            app_type = app.type
            if app_type not in type_counts:
                type_counts[app_type] = 0
            type_counts[app_type] += 1

        logger.info(f"Appointment types: {type_counts}")

        # Print details of each appointment
        for app in appointments:
            logger.info(f"ID={app.id}, Type={app.type}, Priority={app.priority}")
            for day_data in app.days:
                day_index = day_data["day_index"]
                block_count = len(day_data["blocks"])
                logger.info(f"  Day {day_index}: {block_count} blocks")

        # Create settings and run scheduling
        settings = ScheduleSettings(
            start_hour="10:00",
            end_hour="23:00",
            min_gap=15,
            max_hours_per_day_field=5,
            travel_time=75,
            start_date=data["start_date"]
        )

        # Run scheduling algorithm
        logger.info("Running scheduling algorithm...")
        success, final_schedule, unscheduled = schedule_appointments(appointments, settings)

        logger.info(f"Scheduling result: {len(final_schedule)} scheduled, {len(unscheduled)} unscheduled")

        # Print scheduled appointments
        logger.info("Scheduled appointments:")
        for app_id, (start, end, app_type) in final_schedule.items():
            day_index = start.weekday()
            logger.info(f"  ID={app_id}, Type={app_type}, Day={day_index}, Start={start.time()}, End={end.time()}")

        # Print unscheduled appointments
        if unscheduled:
            logger.info("Unscheduled appointments:")
            for app in unscheduled:
                logger.info(f"  ID={app.id}, Type={app.type}, Priority={app.priority}")

        return True

    except Exception as e:
        logger.error(f"Error parsing file: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test the appointment parser')
    parser.add_argument('file', help='Path to the JSON file to parse')

    args = parser.parse_args()

    test_file_parser(args.file)
