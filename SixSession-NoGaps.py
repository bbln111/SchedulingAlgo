import secrets
import sys
from datetime import datetime, timedelta
import json

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
        length = item["time"]  # appointment length in minutes
        block_duration = length + 15  # appointment length + 15 min gap

        processed_days = []
        for day_info in item["days"]:
            day_name = day_info["day"]
            if day_name not in weekday_names:
                continue
            day_index = weekday_names.index(day_name)

            blocks = []
            for tf in day_info["time_frames"]:
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

def need_travel_time(appointment, day_appointments, settings):
    """
    (Unused stub in original code)
    """
    pass

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
    for i, (a_start, a_end, a_type, a_id) in enumerate(day_list):
        if a_start >= start:
            break
        insert_pos = i + 1

    # Get previous and next appointments if they exist
    prev_app_type = None
    prev_app_end = None
    next_app_type = None
    next_app_start = None

    if insert_pos > 0:
        prev_app_start, prev_app_end, prev_app_type, prev_app_id = day_list[insert_pos - 1]

    if insert_pos < len(day_list):
        next_app_start, next_app_end, next_app_type, next_app_id = day_list[insert_pos]

    # Check if this is a zoom-only day
    day_type = {
        0: "mixed",
        1: "mixed",
        2: "mixed",
        3: "mixed",
        4: "mixed",
        5: "mixed",
    }
    if day_type[day_index] == "zoom_only" and appointment.type != "zoom":
        return False

    # Check travel time needed before
    travel_needed_before = False
    if appointment.type != "zoom":
        # Field appointment
        field_placed = any(a_type != "zoom" for (_, _, a_type, a_id) in day_list)
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

    # Check gaps if travel time is needed
    if travel_needed_before:
        gap_start = day_start_time(settings, day_index) if prev_app_end is None else prev_app_end
        gap_end = start
        gap_needed = timedelta(minutes=settings.travel_time)

        if gap_end - gap_start < gap_needed:
            return False
        if not check_free_gap(calendar, day_index, gap_start, gap_end):
            return False

    if travel_needed_after:
        gap_start = end
        gap_end = next_app_start
        gap_needed = timedelta(minutes=settings.travel_time)

        if gap_end:
            if gap_end - gap_start < gap_needed:
                return False
            if not check_free_gap(calendar, day_index, gap_start, gap_end):
                return False

    return True

def can_place_block(appointment, day_index, block, calendar, used_field_hours, settings, day_appointments):
    (start, end) = block
    slots = [slot for slot in calendar[day_index] if slot.start_time >= start and slot.start_time < end]

    # Check if any slot is occupied
    if any(slot.client_id is not None for slot in slots):
        return False

    # Calculate hours in this block
    block_slot_count = len(slots)
    block_hours = block_slot_count * 15.0 / 60.0

    # field appointment check
    if appointment.type != "zoom":
        if used_field_hours[day_index] + block_hours > settings.max_hours_per_day_field:
            return False

    # Check travel_time conditions and zoom-only/mixed conditions
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

    # MINIMAL CHANGE: now store the appointment id in day_appointments
    day_list = day_appointments[day_index]
    insert_pos = 0
    for i, (a_start, a_end, a_type, a_id) in enumerate(day_list):
        if a_start >= start:
            break
        insert_pos = i+1
    day_list.insert(insert_pos, (start, end, appointment.type, appointment.id))

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

    # MINIMAL CHANGE: remove the 4-tuple (start, end, type, id)
    day_list = day_appointments[day_index]
    for i, (a_start, a_end, a_type, a_id) in enumerate(day_list):
        if a_start == start and a_end == end and a_type == appointment.type and a_id == appointment.id:
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
        return True, unscheduled_tasks, final_schedule, day_appointments

    appointment = appointments[index]

    candidates = []
    for day_data in appointment.days:
        day_index = day_data["day_index"]
        for block in day_data["blocks"]:
            if can_place_block(appointment, day_index, block, calendar, used_field_hours, settings, day_appointments):
                candidates.append((day_index, block))

    if not candidates:
        if appointment.priority == "High":
            return False, unscheduled_tasks, final_schedule, day_appointments
        elif appointment.priority == "Medium":
            # For medium priority, only if we haven't gone back once already
            if recursion_depth == 0:
                return False, unscheduled_tasks, final_schedule, day_appointments
            else:
                # Skip it if we've already tried backtracking once
                unscheduled_tasks.append(appointment)
                return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                          index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)
        else:
            # Low priority: just add to unscheduled
            unscheduled_tasks.append(appointment)
            return backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                      index + 1, unscheduled_tasks, final_schedule, day_appointments, 0)

    for (day_index, block) in candidates:
        old_field_hours = used_field_hours[day_index]
        saved_day_appointments = [list(day_appointments[d]) for d in range(6)]  # copy current state
        place_block(appointment, day_index, block, calendar, used_field_hours, final_schedule, day_appointments)

        # Increment recursion_depth for medium priority appointments when backtracking
        next_recursion_depth = recursion_depth + 1 if appointment.priority == "Medium" else 0

        success, unsched_after, final_after, day_apps_after = backtrack_schedule(appointments, calendar, used_field_hours, settings,
                                                                                 index + 1, unscheduled_tasks, final_schedule,
                                                                                 day_appointments,
                                                                                 next_recursion_depth)
        if success:
            return True, unsched_after, final_after, day_apps_after
        else:
            # restore state
            remove_block(appointment, day_index, block, calendar, used_field_hours, final_schedule, day_appointments)
            used_field_hours[day_index] = old_field_hours
            # restore day_appointments
            for d in range(6):
                day_appointments[d] = saved_day_appointments[d]

    # If no candidate worked
    if appointment.priority == "High":
        return False, unscheduled_tasks, final_schedule, day_appointments
    elif appointment.priority == "Medium":
        # For medium priority, only backtrack if we haven't gone back once already
        if recursion_depth == 0:
            return False, unscheduled_tasks, final_schedule, day_appointments
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

    high_priority.sort(key=count_blocks)
    medium_priority.sort(key=count_blocks)
    low_priority.sort(key=count_blocks)

    sorted_appointments = high_priority + medium_priority + low_priority

    calendar = initialize_calendar(settings)
    used_field_hours = [0]*6

    success, unscheduled_tasks, final_schedule, day_appointments = backtrack_schedule(sorted_appointments, calendar, used_field_hours, settings)
    return success, final_schedule, unscheduled_tasks, day_appointments, used_field_hours, calendar

def format_output(final_schedule, unscheduled_tasks):
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

    output = {
        "filled_appointments": filled_appointments,
        "unfilled_appointments": unfilled_appointments
    }
    return output

# MINIMAL CHANGE: New function to optimize same-type consecutive appointments
def optimize_same_type_gaps(calendar, final_schedule, day_appointments, used_field_hours, settings):
    """
    After the schedule is built, check each day for consecutive appointments of the same type.
    If the gap > 15 minutes, attempt to "push" the second appointment closer.

    This is a local/greedy approach. If it can legally move the second appointment
    (using can_place_block), it will do so and then re-check.
    """

    mandatory_gap = timedelta(minutes=15)

    def remove_by_id(day_index, block, app_id, app_type):
        (st, et) = block
        slots = [slot for slot in calendar[day_index] if slot.start_time >= st and slot.start_time < et]
        for slot in slots:
            if slot.client_id == app_id:
                slot.client_id = None

        block_slot_count = len(slots)
        block_hours = block_slot_count * 15.0 / 60.0
        if app_type != "zoom":
            used_field_hours[day_index] -= block_hours

        if app_id in final_schedule:
            del final_schedule[app_id]

        # remove from day_appointments
        day_list = day_appointments[day_index]
        for i, (s0, e0, t0, id0) in enumerate(day_list):
            if s0 == st and e0 == et and t0 == app_type and id0 == app_id:
                day_list.pop(i)
                break

    def place_by_id(day_index, block, app_id, app_type):
        (st, et) = block
        slots = [slot for slot in calendar[day_index] if slot.start_time >= st and slot.start_time < et]
        for slot in slots:
            slot.client_id = app_id

        block_slot_count = len(slots)
        block_hours = block_slot_count * 15.0 / 60.0
        if app_type != "zoom":
            used_field_hours[day_index] += block_hours

        final_schedule[app_id] = (st, et, app_type)

        # insert sorted
        day_list = day_appointments[day_index]
        insert_pos = 0
        for i, (s0, e0, t0, id0) in enumerate(day_list):
            if s0 >= st:
                break
            insert_pos = i+1
        day_list.insert(insert_pos, (st, et, app_type, app_id))

    # Iterate each day
    for day_index in range(6):
        day_appointments[day_index].sort(key=lambda x: x[0])  # sort by start
        i = 0
        while i < len(day_appointments[day_index]) - 1:
            (start1, end1, type1, id1) = day_appointments[day_index][i]
            (start2, end2, type2, id2) = day_appointments[day_index][i+1]

            # If consecutive appointments have the same type and gap > 15 min
            if type1 == type2:
                gap = start2 - end1
                if gap > mandatory_gap:
                    # Attempt to move the second appointment closer
                    length = end2 - start2
                    earliest_new_start = end1 + mandatory_gap
                    latest_new_start = start2

                    # We'll step in 15-min increments
                    step_time = earliest_new_start
                    moved = False
                    while step_time <= latest_new_start and not moved:
                        new_start = step_time
                        new_end = new_start + length
                        new_block = (new_start, new_end)

                        # remove the second appointment from current block
                        remove_by_id(day_index, (start2, end2), id2, type2)

                        # create a minimal "Appointment" object
                        from types import SimpleNamespace
                        mock_appointment = SimpleNamespace(
                            id=id2,
                            type=type2,
                            priority="Low",
                            days=[]
                        )

                        # Check if we can place
                        if can_place_block(mock_appointment, day_index, new_block,
                                           calendar, used_field_hours, settings,
                                           day_appointments):
                            # place it
                            place_by_id(day_index, new_block, id2, type2)
                            moved = True
                        else:
                            # revert if we failed
                            place_by_id(day_index, (start2, end2), id2, type2)

                        step_time += timedelta(minutes=15)

                    if moved:
                        # re-sort day_appointments and re-check from same index
                        day_appointments[day_index].sort(key=lambda x: x[0])
                        continue
            i += 1

def main(input_file):
    with open(input_file, "r") as file:  # Open the file in read mode
        data = json.load(file)

    input_data = data
    settings = ScheduleSettings(
        start_hour="09:30",
        end_hour="22:45",
        min_gap=15,
        max_hours_per_day_field=5,
        travel_time=75,
        start_date=input_data["start_date"]
    )

    appointments = parse_appointments(input_data)
    success, final_schedule, unscheduled_tasks, day_appointments, used_field_hours, calendar = schedule_appointments(appointments, settings)
    if success:
        # MINIMAL CHANGE: call the new function
        optimize_same_type_gaps(calendar, final_schedule, day_appointments, used_field_hours, settings)

    output = format_output(final_schedule, unscheduled_tasks)
    print(json.dumps(output, indent=4))

def write_to_json(input, output_file):
    with open(output_file, "w") as json_file:
        json.dump(input, json_file, indent=4)
    print(f"save to {output_file}")


if __name__ == "__main__":
    import os
    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()

    print(os.path.abspath(os.curdir))
    input_file = "input_data/input_file_3.json"
    with redirect_stdout(buffer):
        main(input_file)
    captured_output = buffer.getvalue()
    print(captured_output)
    x = captured_output
    write_to_json(captured_output, output_file=f"output_data/avs.json")
    print("עם ישראל חי")
# problem: when trying to group together consecutive appointments of the same type it ignores the original availability of the person. for example in input file 3 - id 1 and 4, in order to close the gap it puts 4 in 11:30 altough 4 is available only after 14:30.