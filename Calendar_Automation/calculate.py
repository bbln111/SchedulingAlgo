from flask import Flask, request, jsonify
import json
import os
from datetime import datetime, timedelta
import random

# =============== ORIGINAL LOGIC START ===============

class CalendarSlot:
    def __init__(self, start_time, client_id=None):
        self.start_time = start_time
        self.client_id = client_id


class Appointment:
    def __init__(self, id, priority, days, app_type, length):
        self.id = id
        self.priority = priority
        self.days = days  # list of {day_index, blocks}
        self.type = app_type  # "zoom" or "field" or other
        self.length = length  # in minutes, multiple of 15


class ScheduleSettings:
    def __init__(self, start_hour, end_hour, min_gap, max_hours_per_day_field, travel_time, start_date):
        self.start_hour = datetime.strptime(start_hour, "%H:%M").time()
        self.end_hour = datetime.strptime(end_hour, "%H:%M").time()
        self.min_gap = min_gap
        self.max_hours_per_day_field = max_hours_per_day_field
        self.travel_time = travel_time
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")


def parse_appointments(data):
    weekday_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    appointments = []
    for item in data["appointments"]:
        app_id = item["id"]
        priority = item["priority"]
        app_type = item["type"]

        # Skip appointments with Exclude priority
        if priority == "Exclude":
            continue

        # Set correct length based on appointment type
        if app_type in ["trial_streets", "trial_zoom"]:
            length = 120  # 2 hours for trial sessions
        else:
            length = item["time"]  # Regular session length

        block_duration = length + 15  # appointment length + 15 min gap

        processed_days = []
        for day_info in item["days"]:
            day_name = day_info["day"]
            if day_name not in weekday_names:
                continue
            day_index = weekday_names.index(day_name)

            blocks = []
            # Handle both list and dict formats for time_frames
            time_frames = day_info["time_frames"]
            if isinstance(time_frames, dict):
                time_frames = [time_frames]

            for tf in time_frames:
                start = datetime.fromisoformat(tf["start"])
                end = datetime.fromisoformat(tf["end"])

                block_start = start
                # generate blocks every 15 min that fit entirely within the time frame
                while block_start + timedelta(minutes=block_duration) <= end:
                    block_end = block_start + timedelta(minutes=block_duration)
                    blocks.append((block_start, block_end))
                    block_start += timedelta(minutes=15)

            processed_days.append({
                "day_index": day_index,
                "blocks": blocks
            })

        appointments.append(Appointment(app_id, priority, processed_days, app_type, length))
    return appointments


def initialize_calendar(settings):
    calendar = {day: [] for day in range(6)}
    for day in range(6):
        current_day = settings.start_date + timedelta(days=day)
        start_time = datetime.combine(current_day, settings.start_hour)
        end_time = datetime.combine(current_day, settings.end_hour)
        current_time = start_time
        while current_time < end_time:
            calendar[day].append(CalendarSlot(current_time))
            current_time += timedelta(minutes=15)
    return calendar


def day_start_time(settings, day_index):
    current_day = settings.start_date + timedelta(days=day_index)
    return datetime.combine(current_day, settings.start_hour)


def check_free_gap(calendar, day_index, start_time, end_time):
    """
    Check if all slots between start_time (inclusive) and end_time (exclusive) are free (client_id=None).
    If start_time >= end_time, trivially return True.
    """
    if start_time >= end_time:
        return True
    day_slots = calendar[day_index]
    for slot in day_slots:
        if slot.start_time >= start_time and slot.start_time < end_time:
            if slot.client_id is not None:
                return False
    return True


def can_place_appointment_with_travel(appointment, day_index, block, day_appointments, calendar, settings):
    """
    Check if we can place this appointment considering travel_time rules both before and after.
    Steps:
    1. Find where this block would fit in day_appointments (sorted by start time)
    2. Check previous appointment for travel time if needed
    3. Check next appointment for travel time if needed
    4. Verify free gaps exist for both cases if travel time is needed
    """
    (start, end) = block
    day_list = day_appointments[day_index]

    # Find insertion point
    insert_pos = 0
    for i, (a_start, a_end, a_type) in enumerate(day_list):
        if a_start >= start:
            break
        insert_pos = i + 1

    # Get previous and next appointments if they exist
    prev_app_type = None
    prev_app_end = None
    next_app_type = None
    next_app_start = None

    if insert_pos > 0:
        prev_app_start, prev_app_end, prev_app_type = day_list[insert_pos - 1]

    if insert_pos < len(day_list):
        next_app_start, next_app_end, next_app_type = day_list[insert_pos]

    # All days here are set as "mixed". If you need zoom-only logic, adjust accordingly.
    day_type = {0: "mixed", 1: "mixed", 2: "mixed", 3: "mixed", 4: "mixed", 5: "mixed"}
    if day_type[day_index] == "zoom_only" and appointment.type != "zoom":
        return False

    # Check travel time needed before
    travel_needed_before = False
    if appointment.type != "zoom":
        # Field appointment
        field_placed = any(a_type != "zoom" for (_, _, a_type) in day_list)
        if not field_placed:
            travel_needed_before = True
        elif prev_app_type == "zoom":
            travel_needed_before = True
    else:
        # Zoom appointment
        if prev_app_type and prev_app_type != "zoom":
            travel_needed_before = True

    # Check travel time needed after
    travel_needed_after = False
    if appointment.type != "zoom":
        # Field appointment
        if next_app_type == "zoom":
            travel_needed_after = True
    else:
        # Zoom appointment
        if next_app_type and next_app_type != "zoom":
            travel_needed_after = True

    # Validate free gap before
    if travel_needed_before:
        gap_start = day_start_time(settings, day_index) if prev_app_end is None else prev_app_end
        gap_end = start
        gap_needed = timedelta(minutes=settings.travel_time)

        if gap_end - gap_start < gap_needed:
            return False
        if not check_free_gap(calendar, day_index, gap_start, gap_end):
            return False

    # Validate free gap after
    if travel_needed_after:
        gap_start = end
        gap_end = next_app_start
        gap_needed = timedelta(minutes=settings.travel_time)

        # next_app_start/next_app_end might be None if there's no next appointment
        if gap_start is not None and gap_end is not None:
            if gap_end - gap_start < gap_needed:
                return False
            if not check_free_gap(calendar, day_index, gap_start, gap_end):
                return False

    return True

def can_place_block(appointment, day_index, block, calendar, used_field_hours, settings, day_appointments):
    (start, end) = block
    slots = [slot for slot in calendar[day_index] if slot.start_time >= start and slot.start_time < end]

    # Check if any slot is already occupied
    if any(slot.client_id is not None for slot in slots):
        return False

    # Calculate hours in this block
    block_slot_count = len(slots)
    block_hours = block_slot_count * 15.0 / 60.0

    # Check daily field hours limit (if not zoom)
    if appointment.type != "zoom":
        if used_field_hours[day_index] + block_hours > settings.max_hours_per_day_field:
            return False

    # Check travel_time constraints
    if not can_place_appointment_with_travel(appointment, day_index, block, day_appointments, calendar, settings):
        return False

    return True

def place_block(appointment, day_index, block, calendar, used_field_hours, final_schedule, day_appointments):
    (start, end) = block
    slots = [slot for slot in calendar[day_index] if slot.start_time >= start and slot.start_time < end]
    for slot in slots:
        slot.client_id = appointment.id

    block_slot_count = len(slots)
    block_hours = block_slot_count * 15.0 / 60.0

    if appointment.type != "zoom":
        used_field_hours[day_index] += block_hours

    final_schedule[appointment.id] = (start, end, appointment.type)

    # Insert into sorted list day_appointments
    day_list = day_appointments[day_index]
    insert_pos = 0
    for i, (a_start, a_end, a_type) in enumerate(day_list):
        if a_start >= start:
            break
        insert_pos = i + 1
    day_list.insert(insert_pos, (start, end, appointment.type))

def remove_block(appointment, day_index, block, calendar, used_field_hours, final_schedule, day_appointments):
    (start, end) = block
    slots = [slot for slot in calendar[day_index] if slot.start_time >= start and slot.start_time < end]
    for slot in slots:
        if slot.client_id == appointment.id:
            slot.client_id = None

    block_slot_count = len(slots)
    block_hours = block_slot_count * 15.0 / 60.0

    if appointment.type != "zoom":
        used_field_hours[day_index] -= block_hours

    if appointment.id in final_schedule:
        del final_schedule[appointment.id]

    # Remove from day_appointments
    day_list = day_appointments[day_index]
    for i, (a_start, a_end, a_type) in enumerate(day_list):
        if a_start == start and a_end == end and a_type == appointment.type:
            day_list.pop(i)
            break

def backtrack_schedule(appointments, calendar, used_field_hours, settings,
                       index=0, unscheduled_tasks=None, final_schedule=None, day_appointments=None, recursion_depth=0):
    if unscheduled_tasks is None:
        unscheduled_tasks = []
    if final_schedule is None:
        final_schedule = {}
    if day_appointments is None:
        day_appointments = {d: [] for d in range(6)}

    if index == len(appointments):
        return True, unscheduled_tasks, final_schedule

    appointment = appointments[index]

    # Gather all day/block possibilities for current appointment
    candidates = []
    for day_data in appointment.days:
        day_index = day_data["day_index"]
        for block in day_data["blocks"]:
            if can_place_block(appointment, day_index, block, calendar, used_field_hours, settings, day_appointments):
                candidates.append((day_index, block))

    if not candidates:
        # If no placement found:
        if appointment.priority == "High":
            return False, unscheduled_tasks, final_schedule
        elif appointment.priority == "Medium":
            if recursion_depth == 0:
                return False, unscheduled_tasks, final_schedule
            else:
                unscheduled_tasks.append(appointment)
                return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                          index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)
        else:
            # Low priority -> just skip
            unscheduled_tasks.append(appointment)
            return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                      index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)

    #randomization
    random.seed(datetime.now().microsecond)
    random.shuffle(candidates)

    # Try each candidate block
    for (day_index, block) in candidates:
        old_field_hours = used_field_hours[day_index]
        saved_day_appointments = [list(day_appointments[d]) for d in range(6)]

        place_block(appointment, day_index, block, calendar, used_field_hours,
                    final_schedule, day_appointments)

        next_recursion_depth = recursion_depth + 1 if appointment.priority == "Medium" else 0

        success, unsched_after, final_after = backtrack_schedule(
            appointments, calendar, used_field_hours, settings,
            index + 1, unscheduled_tasks, final_schedule, day_appointments, next_recursion_depth
        )

        if success:
            return True, unsched_after, final_after
        else:
            # restore
            remove_block(appointment, day_index, block, calendar, used_field_hours,
                         final_schedule, day_appointments)
            used_field_hours[day_index] = old_field_hours
            for d in range(6):
                day_appointments[d] = saved_day_appointments[d]

    # If no candidate block works
    if appointment.priority == "High":
        return False, unscheduled_tasks, final_schedule
    elif appointment.priority == "Medium":
        if recursion_depth == 0:
            return False, unscheduled_tasks, final_schedule
        else:
            unscheduled_tasks.append(appointment)
            return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                      index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)
    else:
        unscheduled_tasks.append(appointment)
        return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                  index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)


def schedule_appointments(appointments, settings):
    high_priority = [a for a in appointments if a.priority == "High"]
    medium_priority = [a for a in appointments if a.priority == "Medium"]
    low_priority = [a for a in appointments if a.priority == "Low"]

    def count_blocks(a):
        return sum(len(day_data["blocks"]) for day_data in a.days)

    # Sort by ascending number of possible blocks
    high_priority.sort(key=count_blocks)
    medium_priority.sort(key=count_blocks)
    low_priority.sort(key=count_blocks)

    # Merge all
    sorted_appointments = high_priority + medium_priority + low_priority

    # Initialize
    calendar = initialize_calendar(settings)
    used_field_hours = [0] * 6

    success, unscheduled_tasks, final_schedule = backtrack_schedule(
        sorted_appointments, calendar, used_field_hours, settings
    )
    return success, final_schedule, unscheduled_tasks


def format_output(final_schedule, unscheduled_tasks, appointments):
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

    validation_results = validate_schedule(final_schedule, appointments)

    output = {
        "filled_appointments": filled_appointments,
        "unfilled_appointments": unfilled_appointments,
        "validation": validation_results
    }
    return output


# =============== ORIGINAL LOGIC END ===============


def validate_schedule(final_schedule, appointments):
    """
    Validates if the schedule meets all requirements.
    Returns a dict with validation results.
    """
    validation_results = {
        "valid": True,
        "issues": []
    }

    # Extract appointments by day and type
    days_schedule = {}
    client_days = {}

    for app_id, (start, end, app_type) in final_schedule.items():
        day_index = start.weekday()

        # Initialize day if not exists
        if day_index not in days_schedule:
            days_schedule[day_index] = {"streets": [], "zoom": [], "trial_streets": [], "trial_zoom": []}

        # Add to appropriate type list
        if app_type in ["streets", "zoom", "trial_streets", "trial_zoom"]:
            days_schedule[day_index][app_type].append((start, end, app_id))
        else:
            # Handle legacy types like "field"
            if app_type == "field":
                days_schedule[day_index]["streets"].append((start, end, app_id))
            else:
                days_schedule[day_index]["zoom"].append((start, end, app_id))

        # Track client appointments by day
        client_id = app_id.split('-')[0] if '-' in app_id else app_id
        if client_id not in client_days:
            client_days[client_id] = {}
        if day_index not in client_days[client_id]:
            client_days[client_id][day_index] = []
        client_days[client_id][day_index].append((start, end))

    # Check for isolated street sessions
    for day, types in days_schedule.items():
        street_count = len(types["streets"]) + 2 * len(types["trial_streets"])
        if street_count == 1:
            validation_results["valid"] = False
            validation_results["issues"].append(f"Day {day} has only one street session")

    # Check for large gaps between street sessions
    for day, types in days_schedule.items():
        all_street_sessions = sorted(types["streets"] + types["trial_streets"], key=lambda x: x[0])
        if len(all_street_sessions) >= 2:
            for i in range(len(all_street_sessions) - 1):
                current_end = all_street_sessions[i][1]
                next_start = all_street_sessions[i + 1][0]
                gap = (next_start - current_end).total_seconds() / 60
                if gap > 30:  # 30 minutes max gap (15 min break + 15 min acceptable gap)
                    validation_results["valid"] = False
                    validation_results["issues"].append(f"Day {day} has a gap of {gap} minutes between street sessions")

    # Check for multiple appointments for same client in one day
    for client, days in client_days.items():
        for day, appointments in days.items():
            if len(appointments) > 1:
                validation_results["valid"] = False
                validation_results["issues"].append(f"Client {client} has multiple appointments on day {day}")

    return validation_results


app = Flask(__name__)


@app.route('/schedule', methods=['POST'])
def schedule_endpoint():
    """
    Expects a JSON payload with at least these keys:
    {
        "start_date": "2025-01-01",
        "appointments": [
            {
                "id": "A1",
                "priority": "High",
                "type": "zoom",
                "time": 60,
                "days": [
                    {
                        "day": "Sunday",
                        "time_frames": [
                            {
                                "start": "2025-01-05T09:30:00",
                                "end": "2025-01-05T12:00:00"
                            }
                        ]
                    }
                ]
            },
            ...
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or empty JSON payload."}), 400

    # Example: these settings can be customized or also come dynamically from data
    settings = ScheduleSettings(
        start_hour="10:00",  # earliest start
        end_hour="23:00",  # latest end
        min_gap=15,  # 15 min gap
        max_hours_per_day_field=5,  # max 5 hours of field visits per day
        travel_time=75,  # 75 min travel time
        start_date=data["start_date"]  # must be format YYYY-MM-DD
    )

    # Parse the appointment data
    appointments = parse_appointments(data)

    # Perform scheduling
    success, final_schedule, unscheduled_tasks = schedule_appointments(appointments, settings)

    # Format the scheduling results
    output = format_output(final_schedule, unscheduled_tasks, appointments)

    # ---- Write results to a JSON file in the same folder as this script ----
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_file_path = os.path.join(current_dir, "output.json")
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    # Return results in HTTP response as well
    return jsonify(output), 200


if __name__ == "__main__":
    # Run the Flask app (debug=True is optional and not recommended in production)
    app.run(debug=True)
