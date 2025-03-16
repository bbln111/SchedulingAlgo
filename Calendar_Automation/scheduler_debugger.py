#!/usr/bin/env python
"""
Scheduler Debugging Tool

This script provides detailed analysis of why certain appointment types
might not be getting scheduled properly.

Usage:
  python scheduler_debugger.py input_file.json [--output output.json] [--html]

Options:
  --output FILE    Output results to FILE (default: debug_results.json)
  --html           Generate HTML visualization of the results
  --no-console     Disable console output (log to file only)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Add the parent directory to path so we can import the calculate module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import (
    parse_appointments, ScheduleSettings, schedule_appointments,
    format_output, validate_schedule
)


def setup_enhanced_logging(log_file=None, level=logging.DEBUG):
    """Set up enhanced logging with detailed formatting"""
    log_format = '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    return logger


def log_appointment_details(logger, appointments):
    """Log detailed information about appointments"""
    # Group appointments by type
    by_type = {}
    for app in appointments:
        if app.type not in by_type:
            by_type[app.type] = []
        by_type[app.type].append(app)

    # Log summary
    logger.info("===== APPOINTMENT DETAILS =====")
    for app_type, apps in by_type.items():
        logger.info(f"{app_type}: {len(apps)} appointments")

        # Log details of each appointment
        for app in apps:
            available_days = []
            for day_data in app.days:
                if day_data["blocks"]:
                    day_index = day_data["day_index"]
                    block_count = len(day_data["blocks"])
                    available_days.append(f"Day {day_index} ({block_count} blocks)")

            logger.info(f"  ID={app.id}, Priority={app.priority}, Length={app.length}min, " +
                        f"Available days: {', '.join(available_days) if available_days else 'None'}")


def log_scheduling_results(logger, final_schedule, unscheduled_tasks, appointments):
    """Log detailed information about scheduling results"""
    # Create lookup to easily find original appointments
    app_lookup = {app.id: app for app in appointments}

    # Get statistics by type
    type_stats = {}
    for app in appointments:
        if app.type not in type_stats:
            type_stats[app.type] = {"total": 0, "scheduled": 0, "unscheduled": 0}

        type_stats[app.type]["total"] += 1
        if app.id in final_schedule:
            type_stats[app.type]["scheduled"] += 1
        else:
            type_stats[app.type]["unscheduled"] += 1

    # Log the stats
    logger.info("===== SCHEDULING RESULTS =====")
    logger.info(f"Total appointments: {len(appointments)}")
    logger.info(f"Scheduled: {len(final_schedule)}")
    logger.info(f"Unscheduled: {len(unscheduled_tasks)}")

    for app_type, stats in type_stats.items():
        pct = stats['scheduled'] / stats['total'] * 100 if stats['total'] > 0 else 0
        logger.info(f"{app_type}: {stats['scheduled']}/{stats['total']} scheduled ({pct:.1f}%)")

    # Log details of scheduled appointments
    logger.info("===== SCHEDULED APPOINTMENTS =====")
    for app_id, (start, end, app_type) in final_schedule.items():
        day_of_week = start.strftime("%A")
        logger.info(f"ID={app_id}, Type={app_type}, Day={day_of_week}, " +
                    f"Time={start.strftime('%H:%M')}-{end.strftime('%H:%M')}")

    # Log details of unscheduled appointments
    if unscheduled_tasks:
        logger.info("===== UNSCHEDULED APPOINTMENTS =====")
        for app in unscheduled_tasks:
            days_with_blocks = sum(1 for day in app.days if day["blocks"])
            logger.info(f"ID={app.id}, Type={app.type}, Priority={app.priority}, " +
                        f"Length={app.length}min, Available days: {days_with_blocks}")


def main():
    parser = argparse.ArgumentParser(description='Scheduler Debugging Tool')
    parser.add_argument('input_file', help='Input JSON file with appointments')
    parser.add_argument('--output', default='debug_results.json', help='Output results file')
    parser.add_argument('--html', action='store_true', help='Generate HTML visualization')
    parser.add_argument('--no-console', action='store_true', help='Disable console output')

    args = parser.parse_args()

    # Set up logging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'scheduler_debug_{timestamp}.log'

    logger = setup_enhanced_logging(log_file=log_file)

    if not args.no_console:
        # Add console handler
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    logger.info(f"Debugging scheduler with input file: {args.input_file}")

    try:
        # Load input file
        with open(args.input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)

        # Parse appointments
        appointments = parse_appointments(input_data)

        # Log appointment details
        log_appointment_details(logger, appointments)

        # Create settings
        settings = ScheduleSettings(
            start_hour="10:00",
            end_hour="23:00",
            min_gap=15,
            max_hours_per_day_field=5,
            travel_time=75,
            start_date=input_data["start_date"]
        )

        # Run scheduling with detailed logging
        logger.info("Running scheduling algorithm...")
        success, final_schedule, unscheduled_tasks = schedule_appointments(
            appointments, settings
        )

        # Log scheduling results
        log_scheduling_results(logger, final_schedule, unscheduled_tasks, appointments)

        # Format output
        output = format_output(final_schedule, unscheduled_tasks, appointments)

        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {args.output}")

        # Generate HTML if requested
        if args.html:
            try:
                from visualization import generate_html_visualization
                html_file = args.output.rsplit('.', 1)[0] + '.html'
                generate_html_visualization(output, html_file)
                logger.info(f"HTML visualization saved to {html_file}")
            except ImportError:
                logger.error("Could not import visualization module")

        # Print summary
        print("\n===== SCHEDULING SUMMARY =====")
        print(f"Total appointments: {len(appointments)}")
        print(f"Scheduled: {len(final_schedule)}")
        print(f"Unscheduled: {len(unscheduled_tasks)}")

        # Print by type
        print("\nScheduled by type:")
        for app_type, stats in {t: s for t, s in type_stats.items() if s['scheduled'] > 0}.items():
            print(
                f"  {app_type}: {stats['scheduled']}/{stats['total']} ({stats['scheduled'] / stats['total'] * 100:.1f}%)")

        print("\nUnscheduled by type:")
        for app_type, stats in {t: s for t, s in type_stats.items() if s['unscheduled'] > 0}.items():
            print(
                f"  {app_type}: {stats['unscheduled']}/{stats['total']} ({stats['unscheduled'] / stats['total'] * 100:.1f}%)")

        print(f"\nValidation: {'Valid' if output['validation']['valid'] else 'Invalid'}")
        if not output['validation']['valid']:
            for issue in output['validation']['issues']:
                print(f"  - {issue}")

        print(f"\nDetailed log saved to: {log_file}")

    except Exception as e:
        logger.exception(f"Error debugging scheduler: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
