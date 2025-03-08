import logging
import uuid
import json
import os
from get_input_flow import collect_input_from_monday
from david_sdk import run_on_file
from etc_functions import should_rerun, unite_output_from_script

RERUN_HARD_LIMIT = 1
RUN_ID = str(uuid.uuid4())
LOG_FILE_PATH = fr'..\logs\Calendar_Automation\log_file_{RUN_ID}.log'
OUTPUT_DIR = "output_for_testing"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "output_for_testing.json")

logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=LOG_FILE_PATH,
        filemode='w+'
    )


def main():
    # Configure logging
    print("Working directory:", os.getcwd())
    print("started")

    logger.info("Starting the main function")

    # השתמש בקובץ הבדיקות המלאכותי במקום למשוך נתונים מ-Monday
    input_file_name = "input_for_testing.json"

    logger.info(f"Using input file: {input_file_name}")
    output_from_script = run_on_file(input_file_name)

    # ודא שהמשתנה לא ריק
    if not output_from_script:
        logger.error("Error: output_from_script is None or empty")
        print("Error: output_from_script is None or empty")
        return

    logger.info(f"Initial script run result: {output_from_script}")

    # Retry mechanism
    for i in range(RERUN_HARD_LIMIT):
        logger.info(f"Rerun attempt {i + 1}/{RERUN_HARD_LIMIT}")
        rerun_script = run_on_file(input_file_name)
        logger.debug(f"Rerun script result: {rerun_script}")
        if not should_rerun(rerun_script):
            logger.info("No rerun required based on the script output.")
            break

    # ודא שהתיקייה לקובץ הפלט קיימת
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # שמירת הפלט בקובץ JSON
    if "filled_appointments" in output_from_script:
        united_dictionary = unite_output_from_script(output_from_script['filled_appointments'])
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(united_dictionary, f, indent=4, ensure_ascii=False)

        logger.info(f"Results saved to {OUTPUT_FILE}")
        print(f"Results saved to {OUTPUT_FILE}")

    else:
        logger.error("Error: 'filled_appointments' key missing in output")
        print("Error: 'filled_appointments' key missing in output")


if __name__ == '__main__':
    configure_logging()
    try:
        main()
    except Exception as e:
        logger.error("Error in main function")
        logger.error(e)
