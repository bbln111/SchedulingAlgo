import logging
import uuid
from get_input_flow import collect_input_from_monday
from david_sdk import run_on_file
from write_to_monday_flow import write_to_monday
from etc_functions import should_rerun, unite_output_from_script

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


def main():
    # Configure logging
    import os
    print("Working directory:", os.getcwd())
    print("started")

    logger.info("Starting the main function")
    # If you want to collect input dynamically, uncomment the line below
    input_file_name = _collect_input()

    logger.info(f"Using input file: {input_file_name}")
    output_from_script = run_on_file(input_file_name)
    logger.info(f"Initial script run result: {output_from_script}")

    # Retry mechanism
    for i in range(RERUN_HARD_LIMIT):
        logger.info(f"Rerun attempt {i+1}/{RERUN_HARD_LIMIT}")
        rerun_script = run_on_file(input_file_name)
        logger.debug(f"Rerun script result: {rerun_script}")
        if not should_rerun(rerun_script):
            logger.info("No rerun required based on the script output.")
            break
    # end for
    # Inspect or log details about 'output_from_script' if needed
    logger.info("Uniting script output...")
    united_dictionary = unite_output_from_script(output_from_script['filled_appointments'])
    logger.info(f"Writing results to Monday with data: {united_dictionary}")

    # Call your final function
    write_to_monday(united_dictionary)
    logger.info("Done writing to Monday. Main function complete.")


if __name__ == '__main__':
    configure_logging()
    try:
        main()
    except Exception as e:
        logger.error("Error in main function")
        logger.error(e)
