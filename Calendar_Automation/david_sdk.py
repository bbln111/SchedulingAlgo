import subprocess
import json
import time
import logging

logger = logging.getLogger(__name__)


PYTHON_PATH = r"C:\Users\amirf\PyCharmMiscProject\.venv\Scripts\python.exe"
FLASK_SERVER_LOCATION = r"C:\Users\amirf\PyCharmMiscProject\Calendar_Automation\calculate.py"


def run_flask_server():
    logger.info(f"Running flask server on {FLASK_SERVER_LOCATION}")
    command = f'{PYTHON_PATH} {FLASK_SERVER_LOCATION}'
    running_server_process = _run_command(command, False)
    return running_server_process


def _create_command(filename):
    command = f'curl.exe -X POST -H "Content-Type: application/json" -d "@{filename}" http://127.0.0.1:5000/schedule'
    return command


def _run_command(command, wait=True):
    """
    Runs a shell command and captures its output and errors.

    :param command: The command to execute as a string.
    :param wait: If True, waits for the command to complete; otherwise, runs in the background.
    :return: A tuple (stdout, stderr) if wait=True, otherwise None.
    """
    try:
        if wait:
            result = subprocess.run(command, shell=True, text=True, capture_output=True)
            logger.info(f"Command result - stdout: '{result.stdout}', stderr: '{result.stderr}'")
            if not result.stdout.strip():
                logger.error("Empty response from server")
                return None, "Empty response"
            return result.stdout, result.stderr
        else:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return process
    except Exception as e:
        logger.error(f"Error running command: {command}\nException: {str(e)}")
        return None, str(e)


def _close_server(server_process):
    server_process.terminate()
    server_process.wait()


def run_on_file(filename):
    logger.info(f"Running on file {filename}")
    logger.info("Starting server")
    server = run_flask_server()
    logger.info("Sleeping")
    time.sleep(2)  # let the server to wake up chill
    logger.info("Creating command")
    command = _create_command(filename)
    logger.info(f"Running command {command}")
    stdout, stderr = _run_command(command)
    logger.info(f"stdout: {stdout}, stderr: {stderr}")

    # Handle potential empty response
    if not stdout or not stdout.strip():
        logger.error("No data returned from server")
        _close_server(server)
        return {"filled_appointments": [], "unfilled_appointments": [],
                "validation": {"valid": False, "issues": ["Server returned empty response"]}}

    # Handle JSON decode errors
    try:
        data_as_json = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Raw response: '{stdout}'")
        _close_server(server)
        return {"filled_appointments": [], "unfilled_appointments": [],
                "validation": {"valid": False, "issues": [f"JSON decode error: {e}"]}}

    logger.info(f"data_as_json: {data_as_json}")
    logger.info(f"Closing server")
    _close_server(server)
    logger.info("Server closed")
    return data_as_json


if __name__ == '__main__':
    x = f"input_from_monday/output_2025-03-02.json"
    a = run_on_file(x)
    print(a)
