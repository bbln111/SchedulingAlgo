# Appointment Scheduler

An appointment scheduling solution using Google's CP-SAT solver that optimizes appointment schedules based on various constraints.

## Overview

This scheduler application handles four types of appointments:
- Trial_streets
- Streets
- Trial_zoom
- Zoom

The scheduler respects multiple constraints:
1. Minimum 15-minute breaks between any two appointments
2. Minimum 75-minute break between zoom and streets type appointments
3. Minimum two consecutive streets sessions per day, or none at all
4. Maximum 270 minutes of streets sessions per day
5. One appointment per client per calendar day
6. Maximum 30-minute gap between consecutive streets sessions

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/appointment-scheduler.git
   cd appointment-scheduler
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

The main dependency is Google's OR-Tools, which provides the CP-SAT solver.

## Usage

### Basic Usage

Run the scheduler with an input JSON file:

```bash
python scheduler_main.py input_file.json
```

### Command Line Options

```bash
python scheduler_main.py input_file.json [--output-json OUTPUT_JSON] [--output-html OUTPUT_HTML] [--log-level {DEBUG,INFO,WARNING,ERROR}]
```

- `input_file.json`: Path to the input JSON file with appointment data
- `--output-json`: Path for the output JSON file (default: scheduled_appointments.json)
- `--output-html`: Path for the output HTML visualization (default: schedule_visualization.html)
- `--log-level`: Set the logging level (default: INFO)

### Input File Format

The input file should be a JSON file with the following structure:

```json
{
  "start_date": "YYYY-MM-DD",
  "appointments": [
    {
      "id": "client_id",
      "priority": "High|Medium|Low|Exclude",
      "type": "streets|trial_streets|zoom|trial_zoom",
      "time": duration_in_minutes,
      "days": [
        {
          "day": "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday",
          "time_frames": [
            {
              "start": "YYYY-MM-DDThh:mm:ss",
              "end": "YYYY-MM-DDThh:mm:ss"
            }
          ]
        }
      ]
    }
  ]
}
```

### Output

The scheduler produces:

1. A summary of scheduled appointments on the console
2. A JSON file with the scheduled appointments
3. An HTML visualization file showing the appointments on a timeline

## Project Structure

- `scheduler_core.py`: Core scheduling functionality and data structures
- `scheduler_main.py`: Main application entry point
- `scheduler_tests.py`: Unit tests
- `scheduler_e2e_tests.py`: End-to-end tests

## Running Tests

Run unit tests:

```bash
python -m unittest scheduler_tests.py
```

Run end-to-end tests:

```bash
python -m unittest scheduler_e2e_tests.py
```

## Working Hours

The scheduler respects the following working hours:
- Sunday through Thursday: 10:00 AM - 11:15 PM
- Friday: 12:30 PM - 5:00 PM
- Saturday: Not a working day

## License

[MIT License](LICENSE)