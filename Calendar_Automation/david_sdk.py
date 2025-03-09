import json
import logging
import sys
import importlib.util
from pathlib import Path
from contextlib import contextmanager
from flask import Flask, request
import threading
import time
import requests
from datetime import datetime


def find_flask_script():
    """Find the Flask server script based on the project structure"""
    # Try to find calculate.py in common locations
    script_dir = Path.cwd()
    potential_paths = [
        script_dir / "calculate.py",
        script_dir / "Calendar_Automation" / "calculate.py",
        script_dir.parent / "Calendar_Automation" / "calculate.py",
    ]

    for path in potential_paths:
        if path.exists():
            return str(path)

    return None


def run_flask_server(flask_script_path, input_data, host='127.0.0.1', port=5000):
    """
    Run a Flask server as a subprocess with the input data directly passed to the scheduling function

    Args:
        flask_script_path (str): Path to the Flask script
        input_data (dict): The input data to schedule
        host (str): Host to bind the server to
        port (int): Port to bind the server to

    Returns:
        dict: The scheduling result
    """
    import logging
    logger = logging.getLogger(__name__)

    # Log input data details for debugging
    appointment_count = len(input_data.get("appointments", []))
    logger.info(f"Direct scheduling mode: Processing {appointment_count} appointments")

    try:
        # Import the module directly
        module = import_module_from_path(str(flask_script_path), "schedule_module")

        # Create settings
        if "start_date" in input_data:
            start_date = input_data["start_date"]
        else:
            start_date = datetime.now().strftime('%Y-%m-%d')

        if hasattr(module, "ScheduleSettings"):
            settings = module.ScheduleSettings(
                start_hour="10:00",
                end_hour="23:00",
                min_gap=15,
                max_hours_per_day_field=5,
                travel_time=75,
                start_date=start_date
            )

            # Parse the appointment data
            if hasattr(module, "parse_appointments"):
                appointments = module.parse_appointments(input_data)
                logger.info(f"Parsed {len(appointments)} appointments")

                # Log appointment types for debugging
                street_count = sum(1 for a in appointments if a.type in ["streets", "field", "trial_streets"])
                zoom_count = sum(1 for a in appointments if a.type in ["zoom", "trial_zoom"])
                logger.info(f"Appointment breakdown: {street_count} street/field, {zoom_count} zoom")

                # Call schedule_appointments directly - no special handling for test cases
                if hasattr(module, "schedule_appointments"):
                    success, final_schedule, unscheduled_tasks = module.schedule_appointments(appointments, settings)
                    logger.info(
                        f"Direct scheduling result: {len(final_schedule)} scheduled, {len(unscheduled_tasks)} unscheduled")
                else:
                    logger.error("Module does not have schedule_appointments function")
                    raise ValueError("Required schedule_appointments function not found in the module")

                # Format the output
                if hasattr(module, "format_output"):
                    logger.info("Formatting output")
                    output = module.format_output(final_schedule, unscheduled_tasks, appointments)
                    return output

                # If no format_output function, create a basic output
                filled_appointments = []
                for app_id, (start, end, app_type) in final_schedule.items():
                    filled_appointments.append({
                        "id": app_id,
                        "type": app_type,
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat()
                    })

                unfilled_appointments = []
                for app in unscheduled_tasks:
                    unfilled_appointments.append({
                        "id": app.id,
                        "type": app.type
                    })

                return {
                    "filled_appointments": filled_appointments,
                    "unfilled_appointments": unfilled_appointments,
                    "validation": {
                        "valid": success,
                        "issues": []
                    }
                }

        raise ValueError("Required functions or classes not found in the module")

    except Exception as e:
        logger.error(f"Error in direct scheduling: {e}", exc_info=True)
        raise


# Configure logging
logger = logging.getLogger(__name__)


def import_module_from_path(module_path, module_name=None):
    """
    Dynamically import a Python module from a file path

    Args:
        module_path (str): Path to the Python file
        module_name (str, optional): Name to give the module. Defaults to filename.

    Returns:
        The imported module
    """
    if module_name is None:
        module_name = Path(module_path).stem

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None:
        raise ImportError(f"Could not load spec for module {module_name} from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def in_memory_flask_server(flask_script_path, host='127.0.0.1', port=5000):
    """
    Context manager to run a Flask application in a separate thread

    Args:
        flask_script_path (str): Path to the Flask script
        host (str): Host to bind the server to
        port (int): Port to bind the server to

    Yields:
        The base URL of the server (e.g., 'http://127.0.0.1:5000')
    """
    from multiprocessing import Process
    import socket

    # Create a process to run the Flask app
    def run_flask():
        import sys
        from importlib.machinery import SourceFileLoader

        # Direct import of the module to execute it in the process context
        try:
            # Add the script's directory to the Python path
            script_dir = str(Path(flask_script_path).parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            # Load the module directly
            module_name = Path(flask_script_path).stem
            module = SourceFileLoader(module_name, str(flask_script_path)).load_module()

            # Find the Flask app
            app = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, Flask):
                    app = attr
                    break

            if app is None:
                # Try common names
                if hasattr(module, 'flask_app'):
                    app = module.flask_app
                elif hasattr(module, 'app'):
                    app = module.app
                else:
                    print(f"Could not find Flask application in {flask_script_path}")
                    return

            # Run the app directly
            app.run(host=host, port=port, debug=False, use_reloader=False)

        except Exception as e:
            print(f"Error in Flask process: {e}")
            sys.exit(1)

    logger.info(f"Loading Flask application from {flask_script_path}")
    try:
        # Make sure the port is free
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
        except socket.error as e:
            if e.errno == 98:  # Address already in use
                logger.warning(f"Port {port} is already in use, assuming server is running")
                yield f"http://{host}:{port}"
                return
            else:
                raise
        finally:
            s.close()

        # Start the Flask app in a separate process
        server_process = Process(target=run_flask)
        server_process.daemon = True
        server_process.start()

        # Wait for the server to start
        base_url = f"http://{host}:{port}"
        max_retries = 30
        for _ in range(max_retries):
            try:
                response = requests.get(f"{base_url}/", timeout=0.5)
                # Even a 404 means the server is running
                logger.info(f"Server is running at {base_url}")
                break
            except requests.exceptions.RequestException:
                time.sleep(0.1)
        else:
            # Try one more time with a longer timeout
            try:
                response = requests.get(f"{base_url}/", timeout=2)
                logger.info(f"Server is running at {base_url} (verified with longer timeout)")
            except requests.exceptions.RequestException:
                logger.warning(f"Server may not be running properly at {base_url}")

        # Yield the base URL to the user
        yield base_url

    except Exception as e:
        logger.error(f"Error starting Flask server: {e}")
        raise
    finally:
        # Try to shut down gracefully
        logger.info("Shutting down Flask server")


def run_on_file(input_file, flask_script=None, endpoint="/schedule"):
    """
    Process a schedule using the Flask server

    Args:
        input_file (str): Path to the input JSON file
        flask_script (str, optional): Path to the Flask script. Required if not already running.
        endpoint (str, optional): API endpoint to call. Defaults to "/schedule".

    Returns:
        The processed schedule data or an error response
    """
    try:
        # Load input data
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"Input file not found: {input_file}")
            return {
                "filled_appointments": [],
                "unfilled_appointments": [],
                "validation": {
                    "valid": False,
                    "issues": [f"Input file not found: {input_file}"]
                }
            }

        with open(input_path, 'r', encoding='utf-8') as f:
            try:
                input_data = json.load(f)
                appointment_count = len(input_data.get("appointments", []))
                logger.info(f"Direct scheduling mode: Processing {appointment_count} appointments")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in input file: {e}")
                return {
                    "filled_appointments": [],
                    "unfilled_appointments": [],
                    "validation": {
                        "valid": False,
                        "issues": [f"Invalid JSON in input file: {e}"]
                    }
                }

        # If no Flask script provided, try to find it
        if flask_script is None:
            flask_script = find_flask_script()
            if flask_script:
                logger.info(f"Found Flask script at: {flask_script}")

        # If we have a Flask script, try direct scheduling first
        if flask_script:
            flask_path = Path(flask_script)
            if not flask_path.exists():
                logger.error(f"Flask script not found: {flask_script}")
                return {
                    "filled_appointments": [],
                    "unfilled_appointments": [],
                    "validation": {
                        "valid": False,
                        "issues": [f"Flask script not found: {flask_script}"]
                    }
                }

            # Try direct scheduling
            try:
                return run_flask_server(flask_path, input_data)
            except Exception as e:
                logger.error(f"Direct scheduling failed: {e}")
                # Fall back to HTTP approach below
                pass

            # If direct scheduling failed, start the Flask server
            try:
                with in_memory_flask_server(flask_path) as base_url:
                    # Send the request to our server
                    try:
                        logger.info(f"Sending request to {base_url}{endpoint}")
                        response = requests.post(
                            f"{base_url}{endpoint}",
                            json=input_data,
                            headers={"Content-Type": "application/json"},
                            timeout=30
                        )
                        response.raise_for_status()
                        return response.json()
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error processing request: {e}")
                        return {
                            "filled_appointments": [],
                            "unfilled_appointments": [],
                            "validation": {
                                "valid": False,
                                "issues": [f"Request processing error: {e}"]
                            }
                        }
            except Exception as e:
                logger.error(f"Error starting Flask server: {e}")
                return {
                    "filled_appointments": [],
                    "unfilled_appointments": [],
                    "validation": {
                        "valid": False,
                        "issues": [f"Server error: {e}"]
                    }
                }

        # If no Flask script or previous attempts failed, try connecting to an existing server
        try:
            logger.info("Attempting to connect to existing server")
            response = requests.post(
                f"http://127.0.0.1:5000{endpoint}",
                json=input_data,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to existing server: {e}")
            return {
                "filled_appointments": [],
                "unfilled_appointments": [],
                "validation": {
                    "valid": False,
                    "issues": [f"Server connection error: {e}"]
                }
            }

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "filled_appointments": [],
            "unfilled_appointments": [],
            "validation": {
                "valid": False,
                "issues": [f"Unexpected error: {e}"]
            }
        }


if __name__ == "__main__":
    # Configure logging for standalone usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example usage when run directly
    import argparse

    parser = argparse.ArgumentParser(description='Run scheduling on an input file')
    parser.add_argument('input_file', help='Path to the input JSON file')
    parser.add_argument('--flask-script', '-f', help='Path to the Flask script')
    parser.add_argument('--endpoint', '-e', default='/schedule', help='API endpoint to call')

    args = parser.parse_args()

    result = run_on_file(args.input_file, args.flask_script, args.endpoint)
    print(json.dumps(result, indent=2))
