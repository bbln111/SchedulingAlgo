import logging
import json
import os.path
from datetime import datetime, timedelta
from pathlib import Path
from appointment_scheduler import export_schedule_to_html
# Import the new scheduler instead of the old one
from appointment_scheduler import schedule_appointments as ortools_scheduler
from constants import HTML_REPORT_PATH
logger = logging.getLogger(__name__)
#HTML_REPORT_PATH = f"../logs/scheduling_report.html"

def run_on_file(input_file_path):
    """
    Run scheduling algorithm on the input file.
    Adapts between the old calculate.py interface and the new appointment_scheduler.py

    Args:
        input_file_path (str): Path to the input JSON file

    Returns:
        dict: Scheduling results formatted to match the expected output structure
    """
    try:
        logger.info(f"Starting scheduling on file: {input_file_path}")

        # Ensure file exists
        input_path = Path(input_file_path)
        if not input_path.exists():
            logger.error(f"Input file not found: {input_file_path}")
            return {
                "filled_appointments": [],
                "unfilled_appointments": [],
                "validation": {
                    "valid": False,
                    "issues": [f"Input file not found: {input_file_path}"]
                }
            }

        # Run the appointment scheduler (OR-Tools version)
        appointments, availabilities = ortools_scheduler(input_file_path, max_street_gap=30)
        with open(input_file_path, 'r') as f:
            data = json.load(f)
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        export_schedule_to_html(appointments, availabilities, HTML_REPORT_PATH, start_date)
        # Create HTML report


        # Convert scheduler output format to the format expected by the existing system
        result = convert_scheduler_output(appointments, input_file_path)

        logger.info(f"Scheduling completed with {len(result['filled_appointments'])} filled appointments")
        return result

    except Exception as e:
        logger.exception(f"Error in run_on_file: {str(e)}")
        return {
            "filled_appointments": [],
            "unfilled_appointments": [],
            "validation": {
                "valid": False,
                "issues": [f"Scheduling error: {str(e)}"]
            }
        }


def convert_scheduler_output(scheduled_appointments, input_file_path):
    """
    Convert appointment_scheduler.py output format to the format expected by the existing system

    Args:
        scheduled_appointments (list): List of appointments scheduled by appointment_scheduler.py
        input_file_path (str): Path to the input file for retrieving unscheduled appointments

    Returns:
        dict: Output in the format expected by the existing system
    """
    filled_appointments = []
    unfilled_appointments = []
    validation_issues = []

    # Process filled appointments
    for appointment in scheduled_appointments:
        client_id = appointment['client_id']
        session_type = appointment['type']

        # Parse start and end times to ISO format
        date_str = appointment['date']
        start_time_str = appointment['start_time']
        end_time_str = appointment['end_time']

        start_datetime = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")

        filled_appointments.append({
            "id": client_id,
            "type": session_type,
            "start_time": start_datetime.isoformat(),
            "end_time": end_datetime.isoformat()
        })

    # Find unscheduled appointments
    try:
        with open(input_file_path, 'r') as f:
            input_data = json.load(f)

        all_appointments = input_data.get('appointments', [])
        scheduled_ids = {appointment['client_id'] for appointment in scheduled_appointments}

        for appointment in all_appointments:
            # Skip appointments with exclude priority
            if appointment.get('priority') == "Exclude":
                continue

            if appointment['id'] not in scheduled_ids:
                unfilled_appointments.append({
                    "id": appointment['id'],
                    "type": appointment['type']
                })
    except Exception as e:
        logger.error(f"Error processing unscheduled appointments: {str(e)}")
        validation_issues.append(f"Error identifying unscheduled appointments: {str(e)}")

    # Check validation: Check if we have isolated street sessions
    days_with_streets = {}
    for appointment in filled_appointments:
        if appointment['type'] in ['streets', 'trial_streets', 'field']:
            start_time = datetime.fromisoformat(appointment['start_time'])
            day = start_time.date().isoformat()

            if day not in days_with_streets:
                days_with_streets[day] = []
            days_with_streets[day].append(appointment)

    # Check for days with isolated street sessions
    for day, appointments in days_with_streets.items():
        if len(appointments) == 1 and appointments[0]['type'] != 'trial_streets':
            # If there's only one street session and it's not a trial (which counts as 2)
            validation_issues.append(f"Day {day} has an isolated street session")

    # Construct final result
    result = {
        "filled_appointments": filled_appointments,
        "unfilled_appointments": unfilled_appointments,
        "validation": {
            "valid": len(validation_issues) == 0,
            "issues": validation_issues
        }
    }

    return result
