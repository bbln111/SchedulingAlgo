"""
test_scheduler.py - Test the scheduling system without Monday.com integration
"""

import argparse
import os
import sys
import json
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from david_sdk import run_on_file
from etc_functions import should_rerun, unite_output_from_script

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_sample_input(output_file, start_date=None, num_clients=5, days_range=5):
    """Generate sample input file for testing the scheduling algorithm"""
    # [Implementation as shown above]
    pass


def main():
    parser = argparse.ArgumentParser(description='Test the scheduling system')
    parser.add_argument('--generate', '-g', action='store_true', help='Generate sample input data')
    parser.add_argument('--input', '-i', type=str, help='Input file (if not generating sample data)')
    parser.add_argument('--output', '-o', type=str, default='test_results.json', help='Output file for results')
    parser.add_argument('--html', action='store_true', help='Generate HTML visualization')
    parser.add_argument('--clients', type=int, default=5, help='Number of clients for sample data')
    parser.add_argument('--days', type=int, default=5, help='Number of days to schedule for sample data')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format (defaults to today)')
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

    # Run the scheduler
    logger.info(f"Running scheduler with input file: {input_file}")
    output_from_script = run_on_file(input_file)

    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_from_script, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved results to {args.output}")

    # Generate HTML if requested
    if args.html:
        html_file = args.output.rsplit('.', 1)[0] + '.html'
        generate_html_visualization(output_from_script, html_file)
        logger.info(f"Generated HTML visualization: {html_file}")

    # Print summary
    filled = len(output_from_script.get('filled_appointments', []))
    unfilled = len(output_from_script.get('unfilled_appointments', []))
    valid = output_from_script.get('validation', {}).get('valid', False)

    logger.info(f"Scheduling complete: {filled} appointments scheduled, {unfilled} unfilled")
    logger.info(f"Schedule validation: {'Valid' if valid else 'Invalid'}")

    if not valid:
        issues = output_from_script.get('validation', {}).get('issues', [])
        for issue in issues:
            logger.info(f"  - {issue}")


if __name__ == '__main__':
    main()
