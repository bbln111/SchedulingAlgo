import uuid
import os



MONDAY_URL = "https://api.monday.com/v2"
MONDAY_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"
MONDAY_BOARD_ID = 1563336497

RERUN_HARD_LIMIT = 1
RUN_ID = str(uuid.uuid4())
'''LOG FILE PATHS'''
LOGS_DIR_PATH = fr'..\logs\Calendar_Automation'
RUN_LOGS_DIR_PATH = os.path.join(LOGS_DIR_PATH, RUN_ID)
LOG_FILE_PATH = os.path.join(RUN_LOGS_DIR_PATH, 'log_file.log')
HTML_REPORT_PATH = os.path.join(RUN_LOGS_DIR_PATH, 'scheduling_report.html')
INPUT_DUMP = os.path.join(RUN_LOGS_DIR_PATH, 'input_dump')
OUTPUT_DUMP = os.path.join(RUN_LOGS_DIR_PATH, 'output_dump')

DATE_KEY = 'date0'
TIME_KEY = 'hour__1'
STATUS_KEY = 'status'
STATUS_VALUE_SCHEDULED = 'אלגוריתם שיבץ'
KEY_DAYS_REQUESTED = 'numeric_mknnxrbp'
DEFAULT_REQUESTED_DAYS = 1
GOT_AVAIlABILITIES_INDEX = 8


