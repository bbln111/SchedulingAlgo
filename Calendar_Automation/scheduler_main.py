"""
Appointment Scheduler - Main Application

This is the main entry point for the appointment scheduler application.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import List

from scheduler_core import (
    parse_input_json,
    Scheduler,
    Appointment,
    ScheduledAppointment
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler_main")


def generate_html_output(scheduled_appointments: List[ScheduledAppointment], output_path: str) -> None:
    """Generate an HTML visualization of the scheduled appointments."""
    logger.info(f"Generating HTML visualization at {output_path}")

    # Group appointments by day
    appointments_by_day = {}
    for appointment in scheduled_appointments:
        day = appointment.start_time.date().isoformat()
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appointment)

    # Sort days
    days = sorted(appointments_by_day.keys())

    # Generate HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Appointment Schedule Visualization</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .day-container {
                margin-bottom: 30px;
            }
            .day-header {
                background-color: #f0f0f0;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            .timeline {
                position: relative;
                margin-top: 20px;
                border-left: 2px solid #ccc;
                padding-left: 20px;
                margin-left: 10px;
            }
            .appointment {
                position: relative;
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .streets, .trial_streets {
                background-color: #d4edda;
                border-left: 4px solid #28a745;
            }
            .zoom, .trial_zoom {
                background-color: #cce5ff;
                border-left: 4px solid #007bff;
            }
            .appointment-time {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .appointment-details {
                font-size: 14px;
            }
            .legend {
                display: flex;
                justify-content: center;
                margin-bottom: 20px;
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin: 0 10px;
            }
            .legend-color {
                width: 20px;
                height: 20px;
                margin-right: 5px;
                border-radius: 3px;
            }
            .streets-color {
                background-color: #d4edda;
                border-left: 4px solid #28a745;
            }
            .zoom-color {
                background-color: #cce5ff;
                border-left: 4px solid #007bff;
            }
        </style>
    </head>
    <body>
        <h1>Appointment Schedule Visualization</h1>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color streets-color"></div>
                <span>Streets Sessions</span>
            </div>
            <div class="legend-item">
                <div class="legend-color zoom-color"></div>
                <span>Zoom Sessions</span>
            </div>
        </div>
    """

    # Add each day's appointments
    for day in days:
        day_appointments = appointments_by_day[day]
        day_date = datetime.fromisoformat(day).strftime("%A, %B %d, %Y")

        html_content += f"""
        <div class="day-container">
            <div class="day-header">{day_date}</div>
            <div class="timeline">
        """

        # Sort appointments by start time
        day_appointments.sort(key=lambda x: x.start_time)

        for appointment in day_appointments:
            app_type = appointment.appointment_type.value
            start_time = appointment.start_time.strftime("%H:%M")
            end_time = appointment.end_time.strftime("%H:%M")
            duration = appointment.duration_minutes

            html_content += f"""
                <div class="appointment {app_type}">
                    <div class="appointment-time">{start_time} - {end_time}</div>
                    <div class="appointment-details">
                        <strong>ID:</strong> {appointment.appointment_id}<br>
                        <strong>Type:</strong> {app_type}<br>
                        <strong>Duration:</strong> {duration} minutes
                    </div>
                </div>
            """

        html_content += """
            </div>
        </div>
        """

    html_content += """
    </body>
    </html>
    """

    # Write to file
    with open(output_path, 'w') as f:
        f.write(html_content)

    logger.info(f"HTML visualization generated at {output_path}")


def print_schedule_summary(scheduled_appointments: List[ScheduledAppointment]) -> None:
    """Print a summary of the schedule to stdout."""
    print("\n=== APPOINTMENT SCHEDULE SUMMARY ===")
    print(f"Total scheduled appointments: {len(scheduled_appointments)}")

    # Group by day for better readability
    appointments_by_day = {}
    for appointment in scheduled_appointments:
        day = appointment.start_time.strftime("%Y-%m-%d")
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appointment)

    # Print by day
    for day, day_appointments in sorted(appointments_by_day.items()):
        print(f"\n--- {day} ({len(day_appointments)} appointments) ---")

        # Sort by start time
        day_appointments.sort(key=lambda x: x.start_time)

        for app in day_appointments:
            start_time = app.start_time.strftime("%H:%M")
            end_time = app.end_time.strftime("%H:%M")
            print(
                f"  {start_time} - {end_time}: Client {app.appointment_id} ({app.appointment_type.value}, {app.duration_minutes} min)")


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Appointment Scheduler using Google's CP-SAT solver")
    parser.add_argument('input_file', help='Path to the input JSON file')
    parser.add_argument('--output-json', default='scheduled_appointments.json', help='Path for the output JSON file')
    parser.add_argument('--output-html', default='schedule_visualization.html',
                        help='Path for the output HTML visualization')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Set the logging level')

    args = parser.parse_args()

    # Set logging level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)

    try:
        # Parse the input file
        start_date, appointments = parse_input_json(args.input_file)

        # Create the scheduler
        scheduler = Scheduler(start_date)

        # Add appointments to be scheduled
        for appointment in appointments:
            scheduler.add_appointment(appointment)

        # Schedule the appointments
        scheduled_appointments = scheduler.schedule()

        # Print schedule summary to stdout
        print_schedule_summary(scheduled_appointments)

        # Export to JSON
        scheduler.export_to_json(args.output_json)

        # Generate HTML visualization
        generate_html_output(scheduled_appointments, args.output_html)

        logger.info("Scheduling process completed successfully")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
