import uuid
import logging
import argparse

from get_input_flow import collect_input_from_monday
from david_sdk import run_on_file  # This will now use the appointment_scheduler.py
from write_to_monday_flow import write_to_monday
from etc_functions import should_rerun, unite_output_from_script
#from visualization import generate_html_visualization
#from sample_generator import generate_sample_input


RERUN_HARD_LIMIT = 1
RUN_ID = str(uuid.uuid4())
LOG_FILE_PATH = fr'..\logs\Calendar_Automation\log_file_{RUN_ID}.log'
logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=LOG_FILE_PATH,
        filemode='w+'
    )


def _collect_input():
    input_file = f"input_from_monday/input"
    try:
        logger.info("Attempting to collect input from Monday...")
        output_file_name = collect_input_from_monday(input_file)
        logger.info(f"Successfully collected input and wrote to {input_file}")
    except Exception:
        logger.exception("Error in collect_input_from_monday")
        raise  # Re-raise to ensure the exception is not suppressed
    return output_file_name


def configure_argument_parser():
    parser = argparse.ArgumentParser(description='Schedule appointments from Monday.com data')
    parser.add_argument('--test', '-t', action='store_true', help='Run in test mode without writing to Monday')
    parser.add_argument('--input-file', '-i', type=str,
                        help='Specify input file for test mode (bypasses Monday data collection)')
    parser.add_argument('--output-file', '-o', type=str, default='scheduling_results.json',
                        help='Output file for test results')
    parser.add_argument('--no-html', action='store_true', help='Disable HTML visualization in test mode')
    parser.add_argument('--use-legacy', action='store_true',
                        help='Use the legacy scheduler in calculate.py instead of the OR-Tools scheduler')
    return parser.parse_args()


def save_results_to_file(results, filename):
    """Save scheduling results to a JSON file"""
    import json
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved results to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}")
        return False


def main():
    # Configure logging
    configure_logging()

    # Parse command-line arguments
    args = configure_argument_parser()

    logger.info("Starting the main function")
    logger.info(f"Using OR-Tools scheduler: {not args.use_legacy}")

    # Handle input based on mode
    if args.input_file:
        input_file_name = args.input_file
        logger.info(f"Using provided input file: {input_file_name}")
    else:
        input_file_name = _collect_input()
        logger.info(f"Using collected input file: {input_file_name}")

    # Run the scheduling algorithm
    output_from_script = run_on_file(input_file_name)
    logger.info(f"Initial script run result: {len(output_from_script.get('filled_appointments', []))} appointments filled")

    # Retry mechanism (only if needed - may not be necessary with OR-Tools)
    for i in range(RERUN_HARD_LIMIT):
        logger.info(f"Rerun attempt {i + 1}/{RERUN_HARD_LIMIT}")
        rerun_script = run_on_file(input_file_name)
        logger.debug(f"Rerun script result: {len(rerun_script.get('filled_appointments', []))} appointments filled")
        if not should_rerun(rerun_script):
            logger.info("No rerun required based on the script output.")
            break

    # Process output
    united_dictionary = unite_output_from_script(output_from_script['filled_appointments'])

    # Save results to file in test mode or specified output file
    if args.test or args.output_file:
        output_file = args.output_file or 'test_results.json'
        save_results_to_file(output_from_script, output_file)
        logger.info(f"Results saved to {output_file}")

        if not args.no_html:
            html_file = output_file.rsplit('.', 1)[0] + '.html'
            #generate_html_visualization(output_from_script, html_file)
            logger.info(f"HTML visualization saved to {html_file}")

    # Only write to Monday if not in test mode
    if not args.test:
        logger.info(f"Writing results to Monday with data: {united_dictionary}")
        write_to_monday(united_dictionary)
        logger.info("Done writing to Monday. Main function complete.")
    else:
        logger.info("Test mode: Skipping write to Monday")


if __name__ == '__main__':
    try:
        print("started")
        main()
        print("finished")
    except Exception as e:
        logger.error(f"Error in main function: {e}")
