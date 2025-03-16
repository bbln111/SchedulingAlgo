"""
Wrapper for appointment_scheduler.py that makes it a drop-in replacement for the scheduling logic in calculate.py.
This provides compatibility with the Flask API endpoints in calculate.py.
"""

import logging
import json
from flask import Flask, request, jsonify

from appointment_scheduler import schedule_appointments as ortools_scheduler

logger = logging.getLogger(__name__)

# Flask Application (same name as in calculate.py to ensure compatibility)
flask_app = Flask(__name__)


@flask_app.route('/schedule', methods=['POST'])
def schedule_endpoint():
    """
    API endpoint to handle scheduling requests.
    Preserves the same interface as calculate.py but uses the new scheduler.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or empty JSON payload."}), 400

    try:
        # Save the input data to a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(data, tmp)
            temp_file_path = tmp.name

        logger.info(f"Saved input data to temporary file: {temp_file_path}")

        # Run the scheduler on the temporary file
        appointments = ortools_scheduler(temp_file_path, max_street_gap=30)

        # Convert the output to the expected format
        output = convert_scheduler_output(appointments, data)

        # Clean up the temporary file
        import os
        try:
            os.unlink(temp_file_path)
        except Exception as e:
            logger.warning(f"Could not delete temporary file {temp_file_path}: {e}")

        return jsonify(output), 200

    except Exception as e:
        logger.error(f"Error processing schedule request: {e}", exc_info=True)
        return jsonify({
            "error": f"Error processing schedule request: {str(e)}",
            "filled_appointments": [],
            "unfilled_appointments": [],
            "validation": {
                "valid": False,
                "issues": [f"Processing error: {str(e)}"]
            }
        }), 500


@flask_app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "Scheduler is running (OR-Tools version)"}), 200


def convert_scheduler_output(scheduled_appointments, input_data):
    """
    Convert the output of the OR-Tools scheduler to the format expected by the system.

    Args:
        scheduled_appointments: List of scheduled appointments from OR-Tools scheduler
        input_data: Original input data

    Returns:
        dict: Output in the format expected by the system
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

        from datetime import datetime
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


# If running directly, start the Flask app
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    flask_app.run(host='0.0.0.0', port=5000, debug=True)
