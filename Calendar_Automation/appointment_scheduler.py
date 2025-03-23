from ortools.sat.python import cp_model
import json
from datetime import datetime, timedelta
import argparse


def parse_time(time_str):
    """Convert time string to minutes from midnight.

    Handles both 'HH:MM' format and ISO format like '2025-03-02T16:00'
    """
    # Check if time_str is in ISO format (contains 'T')
    if 'T' in time_str:
        # Extract the time part after 'T'
        time_part = time_str.split('T')[1]
        # Handle both with and without seconds
        if ':' in time_part:
            if time_part.count(':') == 1:
                hours, minutes = map(int, time_part.split(':'))
                return hours * 60 + minutes
            else:
                hours_minutes = time_part.split(':')[:2]  # Take only hours and minutes
                hours, minutes = map(int, hours_minutes)
                return hours * 60 + minutes
        else:
            # Handle format like T16
            return int(time_part) * 60
    else:
        # Standard HH:MM format
        if ':' in time_str:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        else:
            # Handle just hours
            return int(time_str) * 60


def format_time(minutes):
    """Convert minutes from midnight to time string (HH:MM)."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def day_name_to_number(day_name):
    """Convert day name to number (0=Sunday, 1=Monday, ..., 6=Saturday)."""
    days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    return days.index(day_name.lower())


def day_number_to_name(day_number):
    """Convert day number to name."""
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    return days[day_number]


def get_working_hours(day_number):
    """Return working hours for the given day as (start_minute, end_minute)."""
    if 0 <= day_number <= 4:  # Sunday to Thursday
        return 10 * 60, 23 * 60  # 10:00 to 23:00
    elif day_number == 5:  # Friday
        return 12 * 60 + 30, 17 * 60  # 12:30 to 17:00
    else:  # Saturday
        return None  # No working hours on Saturday


def python_weekday_to_our_weekday(python_weekday):
    """
    Convert Python's weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
    to our weekday system (0=Sunday, 1=Monday, ..., 6=Saturday)
    """
    return (python_weekday + 1) % 7


def our_weekday_to_python_weekday(our_weekday):
    """
    Convert our weekday system (0=Sunday, 1=Monday, ..., 6=Saturday)
    to Python's weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
    """
    return (our_weekday - 1) % 7


def schedule_appointments(json_file, max_street_gap=30, max_street_minutes_per_day=270):
    """Schedule appointments based on constraints and client availability.

    Args:
        json_file (str): Path to the input JSON file
        max_street_gap (int): Maximum gap in minutes allowed between consecutive street sessions
        max_street_minutes_per_day (int): Maximum total minutes of street sessions allowed per day
    """
    # Load data from JSON file
    with open(json_file, 'r') as constraints_file:
        json_data = json.load(constraints_file)

    constraint_start_date = datetime.strptime(json_data['start_date'], '%Y-%m-%d')
    python_weekday = constraint_start_date.weekday()
    our_weekday = python_weekday_to_our_weekday(python_weekday)

    print(f"DEBUG: Input start date: {json_data['start_date']}")
    print(f"DEBUG: Parsed date: {constraint_start_date}")
    print(f"DEBUG: Python weekday: {python_weekday} (0=Monday, 6=Sunday)")
    print(f"DEBUG: Our weekday system: {our_weekday} (0=Sunday, 6=Saturday)")
    print(f"DEBUG: Day name according to our system: {day_number_to_name(our_weekday)}")

    clients = json_data['appointments']

    # Print summary of input data
    print(f"\n=== Input Data Summary ===")
    print(f"Start date: {constraint_start_date.strftime('%Y-%m-%d')} "
          f"({day_number_to_name(python_weekday_to_our_weekday(constraint_start_date.weekday()))})")
    print(f"Total clients: {len(clients)}")
    print(f"Maximum gap between street sessions: {max_street_gap} minutes")
    print(f"Maximum street session minutes per day: {max_street_minutes_per_day} minutes")

    # Count session types
    session_counts = {
        'streets': 0,
        'trial_streets': 0,
        'zoom': 0,
        'trial_zoom': 0
    }
    priority_counts = {
        'High': 0,
        'Medium': 0,
        'Low': 0,
        'Exclude': 0
    }

    for client in clients:
        session_type = client['type']
        priority = client['priority']

        if session_type in session_counts:
            session_counts[session_type] += 1

        if priority in priority_counts:
            priority_counts[priority] += 1

    print("\nSession types:")
    for session_type, count in session_counts.items():
        print(f"  - {session_type}: {count}")

    print("\nPriority levels:")
    for priority, count in priority_counts.items():
        print(f"  - {priority}: {count}")

    # Print client details
    print("\nClient details:")
    for client in clients:
        client_id = client['id']
        session_type = client['type']
        priority = client['priority']
        # Add session time if available
        session_time = client.get('time', None)
        time_info = f"({session_time} min)" if session_time else ""

        # Skip excluded clients in the detailed list
        if priority == "Exclude":
            continue

        # Count available days with time slots
        available_days = []
        for day_info in client.get('days', []):
            day_name = day_info['day']
            time_frames = day_info.get('time_frames', [])

            # Check if there are any time frames for this day
            has_time_frames = False
            if isinstance(time_frames, list) and time_frames:
                has_time_frames = True
            elif isinstance(time_frames, dict) and 'start' in time_frames and 'end' in time_frames:
                has_time_frames = True
            elif isinstance(time_frames, str) and '-' in time_frames:
                has_time_frames = True

            if has_time_frames:
                available_days.append(day_name)

        if available_days:
            available_days_str = ", ".join(available_days)
            print(f"  - Client {client_id}: {session_type} {time_info} (Priority: {priority}) - "
                  f"Available on {available_days_str}")
        else:
            print(f"  - Client {client_id}: {session_type} {time_info} (Priority: {priority}) - No availability")

    print("\n=== Starting Scheduler ===")

    # Default session type durations (used if not specified in client data)
    default_session_durations = {
        'trial_streets': 120,
        'streets': 60,
        'trial_zoom': 90,
        'zoom': 60
    }

    # Prepare the model
    model = cp_model.CpModel()

    # Define the scheduling horizon (7 days)
    num_days = 7
    horizon_minutes = num_days * 24 * 60  # Total minutes in the scheduling horizon

    # Collect all client availabilities
    client_availabilities = []
    for client in clients:
        client_id = client['id']
        client_priority = client['priority']
        session_type = client['type']

        # Use 'time' field if provided, otherwise use default durations
        if 'time' in client and client['time'] is not None:
            session_duration = client['time']
        else:
            session_duration = default_session_durations[session_type]

        # Skip clients with "Exclude" priority
        if client_priority == "Exclude":
            continue

        # Calculate priority value (for optimization)
        if client_priority == "High":
            priority_value = 3
        elif client_priority == "Medium":
            priority_value = 2
        else:  # "Low"
            priority_value = 1

        daily_availabilities = []

        for availability in client.get('days', []):
            day_name = availability['day']
            day_number = day_name_to_number(day_name)
            python_weekday = constraint_start_date.weekday()  # 0-6 (Monday-Sunday)
            our_start_weekday = python_weekday_to_our_weekday(python_weekday)  # 0-6 (Sunday-Saturday)
            day_offset = (day_number - our_start_weekday + 7) % 7

            print(f"DEBUG: Day offset calculation")
            print(f"  Input day name: {day_name}")
            print(f"  Day number: {day_number}")
            print(f"  Start date: {constraint_start_date}")
            print(f"  Python weekday: {python_weekday}")
            print(f"  Our start weekday: {our_start_weekday}")
            print(f"  Day offset: {day_offset}")

            # Skip Saturdays as they are not working days
            if day_number == 6:
                continue

            # Get working hours for this day
            working_hours = get_working_hours(day_number)
            if not working_hours:
                continue

            work_start, work_end = working_hours

            time_frames = availability.get('time_frames', [])

            # Skip if time_frames is empty
            if not time_frames:
                continue

            # Handle different time_frames formats
            if isinstance(time_frames, list):
                # Skip if empty list
                if not time_frames:
                    continue

                for time_frame in time_frames:
                    # Check if time_frame is a dictionary with start/end keys
                    if isinstance(time_frame, dict) and 'start' in time_frame and 'end' in time_frame:
                        start_time = parse_time(time_frame['start'])
                        end_time = parse_time(time_frame['end'])

                        # Adjust start and end times to be within working hours
                        start_time = max(start_time, work_start)
                        end_time = min(end_time, work_end)

                        if end_time - start_time >= session_duration:
                            # Calculate start and end times in minutes from the beginning of the scheduling horizon
                            horizon_start = day_offset * 24 * 60 + start_time
                            horizon_end = day_offset * 24 * 60 + end_time - session_duration

                            daily_availabilities.append((horizon_start, horizon_end, day_number))

                    # Check if time_frame is a string with format "start-end"
                    elif isinstance(time_frame, str) and '-' in time_frame:
                        start_str, end_str = time_frame.split('-')
                        start_time = parse_time(start_str)
                        end_time = parse_time(end_str)

                        # Adjust start and end times to be within working hours
                        start_time = max(start_time, work_start)
                        end_time = min(end_time, work_end)

                        if end_time - start_time >= session_duration:
                            # Calculate start and end times in minutes from the beginning of the scheduling horizon
                            horizon_start = day_offset * 24 * 60 + start_time
                            horizon_end = day_offset * 24 * 60 + end_time - session_duration

                            daily_availabilities.append((horizon_start, horizon_end, day_number))

                    print(f"DEBUG: Processing time_frame for client {client_id} on {day_name}")
                    print(f"  Original time_frame: {time_frame}")
                    print(f"  Parsed start_time: {start_time} ({format_time(start_time)})")
                    print(f"  Parsed end_time: {end_time} ({format_time(end_time)})")
                    print(f"  Working hours: {work_start} - {work_end}")
                    print(
                        f"  Adjusted start_time: {max(start_time, work_start)} ({format_time(max(start_time, work_start))})")
                    print(f"  Adjusted end_time: {min(end_time, work_end)} ({format_time(min(end_time, work_end))})")
                    print(f"  Session duration: {session_duration}")
                    print(f"  Valid time window: {end_time - start_time >= session_duration}")
                    print(f"  Resulting horizon_start: {horizon_start}")
                    print(f"  Resulting horizon_end: {horizon_end}")

            # Handle case where time_frames is a dictionary with start/end keys (not in an array)
            elif isinstance(time_frames, dict) and 'start' in time_frames and 'end' in time_frames:
                start_time = parse_time(time_frames['start'])
                end_time = parse_time(time_frames['end'])

                # Adjust start and end times to be within working hours
                start_time = max(start_time, work_start)
                end_time = min(end_time, work_end)

                if end_time - start_time >= session_duration:
                    # Calculate start and end times in minutes from the beginning of the scheduling horizon
                    horizon_start = day_offset * 24 * 60 + start_time
                    horizon_end = day_offset * 24 * 60 + end_time - session_duration

                    daily_availabilities.append((horizon_start, horizon_end, day_number))

            # Handle case where time_frames is a single string with format "start-end"
            elif isinstance(time_frames, str) and '-' in time_frames:
                start_str, end_str = time_frames.split('-')
                start_time = parse_time(start_str)
                end_time = parse_time(end_str)

                # Adjust start and end times to be within working hours
                start_time = max(start_time, work_start)
                end_time = min(end_time, work_end)

                if end_time - start_time >= session_duration:
                    # Calculate start and end times in minutes from the beginning of the scheduling horizon
                    horizon_start = day_offset * 24 * 60 + start_time
                    horizon_end = day_offset * 24 * 60 + end_time - session_duration

                    daily_availabilities.append((horizon_start, horizon_end, day_number))

        if daily_availabilities:
            client_availabilities.append({
                'id': client_id,
                'type': session_type,
                'duration': session_duration,
                'priority': priority_value,
                'availabilities': daily_availabilities
            })

    print(f"\n=== Debug: Client Availabilities ===")

    # Create variables for each client's appointment
    appointment_vars = {}
    appointment_day_vars = {}
    appointment_scheduled_vars = {}

    for client in client_availabilities:
        client_id = client['id']
        print(f"DEBUG: Processing client {client_id} with {len(client['availabilities'])} availability slots")
        for start, end, day_number in client['availabilities']:
            print(f"DEBUG: Availability slot: day {day_number}, start {start}, end {end}")

        # Create a variable for the start time of the appointment
        appointment_vars[client_id] = model.NewIntVar(0, horizon_minutes, f'start_{client_id}')

        # Create a variable to track which day the appointment is scheduled on
        appointment_day_vars[client_id] = model.NewIntVar(0, 6, f'day_{client_id}')

        # Create a boolean variable to indicate if the client is scheduled
        appointment_scheduled_vars[client_id] = model.NewBoolVar(f'scheduled_{client_id}')

        # Add constraints to ensure appointment is within client availability
        availability_literals = []

        for start, end, day_number in client['availabilities']:
            # Create a boolean variable for this availability slot
            slot_var = model.NewBoolVar(f'slot_{client_id}_{start}_{end}')

            # If this slot is chosen, constrain the appointment time
            model.Add(appointment_vars[client_id] >= start).OnlyEnforceIf(slot_var)
            model.Add(appointment_vars[client_id] <= end).OnlyEnforceIf(slot_var)

            # Set the day if this slot is chosen
            model.Add(appointment_day_vars[client_id] == day_number).OnlyEnforceIf(slot_var)

            availability_literals.append(slot_var)

        # The client is scheduled if and only if one of their availability slots is chosen
        model.AddBoolOr(availability_literals).OnlyEnforceIf(appointment_scheduled_vars[client_id])
        model.AddBoolAnd([lit.Not() for lit in availability_literals]).OnlyEnforceIf(
            appointment_scheduled_vars[client_id].Not())

    # Create arrays to track street sessions per day
    days_with_streets = {}
    street_sessions_per_day = {}
    street_minutes_per_day = {}  # Track total minutes of street sessions per day
    street_sessions_by_day = {}  # Keep track of street sessions for each day

    for day in range(7):
        if day in street_sessions_by_day and street_sessions_by_day[day]:
            print(f"DEBUG: Day {day} ({day_number_to_name(day)}) "
                  f"has {len(street_sessions_by_day[day])} potential street sessions")
        # Skip Saturday
        if day == 6:
            continue

        street_sessions_for_day = []
        street_session_durations = []  # List to store the durations of street sessions for this day
        street_sessions_by_day[day] = []  # Initialize array to store street session clients for this day

        for client_id, client in [(c['id'], c) for c in client_availabilities]:
            session_type = client['type']
            session_duration = client['duration']

            # Check if this is a streets-type session
            if session_type in ['streets', 'trial_streets']:
                # Create a boolean variable to indicate if this streets session is scheduled on this day
                is_scheduled_this_day = model.NewBoolVar(f'street_{client_id}_on_day_{day}')

                # This client's street session is on this day if the client is scheduled and the day matches
                model.Add(appointment_day_vars[client_id] == day).OnlyEnforceIf(is_scheduled_this_day)
                model.Add(appointment_day_vars[client_id] != day).OnlyEnforceIf(is_scheduled_this_day.Not())

                # This is only valid if the client is actually scheduled
                model.AddImplication(is_scheduled_this_day, appointment_scheduled_vars[client_id])

                street_sessions_for_day.append(is_scheduled_this_day)
                street_sessions_by_day[day].append((client_id, session_duration, is_scheduled_this_day))

                # Add this session's duration to our tracking list, multiplied by whether it's scheduled
                street_session_durations.append(session_duration * is_scheduled_this_day)

        if street_sessions_for_day:
            # Create a variable to count streets sessions on this day
            street_sessions_per_day[day] = model.NewIntVar(0, len(street_sessions_for_day), f'streets_on_day_{day}')
            model.Add(street_sessions_per_day[day] == sum(street_sessions_for_day))

            # Create a variable to track total minutes of street sessions on this day
            street_minutes_per_day[day] = model.NewIntVar(0, 1000, f'street_minutes_on_day_{day}')
            model.Add(street_minutes_per_day[day] == sum(street_session_durations))

            # Add constraint to limit total minutes of street sessions per day
            model.Add(street_minutes_per_day[day] <= max_street_minutes_per_day)

            # Variable to indicate if this day has at least 2 street sessions
            days_with_streets[day] = model.NewBoolVar(f'day_{day}_has_streets')
            model.Add(street_sessions_per_day[day] >= 2).OnlyEnforceIf(days_with_streets[day])
            model.Add(street_sessions_per_day[day] <= 1).OnlyEnforceIf(days_with_streets[day].Not())

            # Enforce the rule: either 0 or at least 2 streets sessions per day
            model.Add(street_sessions_per_day[day] == 0).OnlyEnforceIf(days_with_streets[day].Not())

            if len(street_sessions_by_day[day]) >= 2:
                # Create a variable for each session to represent its position in the sequence
                session_positions = {}
                for i, (client_id, _, is_scheduled) in enumerate(street_sessions_by_day[day]):
                    # For each potential session, create a variable for its position (0 = not scheduled)
                    max_position = len(street_sessions_by_day[day])
                    session_positions[client_id] = model.NewIntVar(0, max_position, f'position_{client_id}_day_{day}')

                    # If the session is not scheduled, its position is 0
                    model.Add(session_positions[client_id] == 0).OnlyEnforceIf(is_scheduled.Not())
                    # If the session is scheduled, its position is > 0
                    model.Add(session_positions[client_id] > 0).OnlyEnforceIf(is_scheduled)

                # Ensure positions are different for scheduled sessions
                for i, (client1_id, _, is_scheduled1) in enumerate(street_sessions_by_day[day]):
                    for j, (client2_id, _, is_scheduled2) in enumerate(street_sessions_by_day[day]):
                        if i < j:
                            both_scheduled = model.NewBoolVar(f'both_{client1_id}_{client2_id}_on_day_{day}_scheduled')
                            model.AddBoolAnd([is_scheduled1, is_scheduled2]).OnlyEnforceIf(both_scheduled)
                            model.AddBoolOr([is_scheduled1.Not(), is_scheduled2.Not()]).OnlyEnforceIf(
                                both_scheduled.Not())

                            # If both are scheduled, they must have different positions
                            model.Add(session_positions[client1_id] != session_positions[client2_id]).OnlyEnforceIf(
                                both_scheduled)

                # Now, for each session, if it's in position p, find the session in position p+1
                # and enforce the max_street_gap constraint between them
                for position in range(1, len(street_sessions_by_day[day])):
                    # For each client that might be at position 'position'
                    for i, (client1_id, client1_duration, is_scheduled1) in enumerate(street_sessions_by_day[day]):
                        client1_at_position = model.NewBoolVar(f'client_{client1_id}_at_position_{position}_day_{day}')
                        model.Add(session_positions[client1_id] == position).OnlyEnforceIf(client1_at_position)
                        model.Add(session_positions[client1_id] != position).OnlyEnforceIf(client1_at_position.Not())

                        # For each client that might be at position 'position+1'
                        for j, (client2_id, client2_duration, is_scheduled2) in enumerate(street_sessions_by_day[day]):
                            if i != j:
                                client2_at_next_position = model.NewBoolVar(
                                    f'client_{client2_id}_at_position_{position + 1}_day_{day}')
                                model.Add(session_positions[client2_id] == position + 1).OnlyEnforceIf(
                                    client2_at_next_position)
                                model.Add(session_positions[client2_id] != position + 1).OnlyEnforceIf(
                                    client2_at_next_position.Not())

                                # If client1 is at position and client2 is at next position, enforce gap constraint
                                consecutive = model.NewBoolVar(f'consecutive_{client1_id}_{client2_id}_day_{day}')
                                model.AddBoolAnd([client1_at_position, client2_at_next_position]).OnlyEnforceIf(
                                    consecutive)
                                model.AddBoolOr(
                                    [client1_at_position.Not(), client2_at_next_position.Not()]).OnlyEnforceIf(
                                    consecutive.Not())

                                # When consecutive, client2 must come after client1
                                model.Add(appointment_vars[client2_id] > appointment_vars[client1_id]).OnlyEnforceIf(
                                    consecutive)

                                # Enforce max gap constraint only between consecutive sessions
                                model.Add(appointment_vars[client2_id] - (
                                        appointment_vars[client1_id] + client1_duration) <= max_street_gap) \
                                    .OnlyEnforceIf(consecutive)

    # For each day, add constraints to ensure all street sessions are scheduled before or after all zoom sessions
    # (not interleaved) and have the required gap between them
    for day in range(7):
        if day in street_sessions_by_day and street_sessions_by_day[day]:
            print(f"DEBUG: Day {day} ({day_number_to_name(day)}) "
                  f"has {len(street_sessions_by_day[day])} potential street sessions")

        # Skip Saturday
        if day == 6:
            continue

        # Create variables to track if clients are scheduled on this day
        day_clients = {}
        for client in client_availabilities:
            client_id = client['id']
            is_scheduled_on_day = model.NewBoolVar(f'client_{client_id}_on_day_{day}')
            model.Add(appointment_day_vars[client_id] == day).OnlyEnforceIf(is_scheduled_on_day)
            model.Add(appointment_day_vars[client_id] != day).OnlyEnforceIf(is_scheduled_on_day.Not())
            model.AddImplication(is_scheduled_on_day, appointment_scheduled_vars[client_id])
            day_clients[client_id] = is_scheduled_on_day

        # Get all street and zoom clients for this day
        streets_on_day = [(client['id'], client['type']) for client in client_availabilities
                          if client['type'] in ['streets', 'trial_streets']]
        zooms_on_day = [(client['id'], client['type']) for client in client_availabilities
                        if client['type'] in ['zoom', 'trial_zoom']]

        # If there are both street and zoom sessions on this day, enforce consecutive scheduling
        if streets_on_day and zooms_on_day:
            # Create a variable to represent whether all street sessions come before zoom sessions on this day
            streets_before_zooms = model.NewBoolVar(f'streets_before_zooms_day_{day}')
            streets_after_zooms = model.NewBoolVar(f'streets_after_zooms_day_{day}')

            # Either all streets come before all zooms, or all streets come after all zooms
            model.AddBoolOr([streets_before_zooms, streets_after_zooms])

            # For each street and zoom pair, enforce the appropriate ordering
            for street_id, _ in streets_on_day:
                for zoom_id, _ in zooms_on_day:
                    # Only if both are scheduled on this day
                    both_on_day = model.NewBoolVar(f'both_{street_id}_{zoom_id}_on_day_{day}')
                    model.AddBoolAnd([day_clients[street_id], day_clients[zoom_id]]).OnlyEnforceIf(both_on_day)
                    model.AddBoolOr([day_clients[street_id].Not(), day_clients[zoom_id].Not()]).OnlyEnforceIf(
                        both_on_day.Not())

                    # If streets before zooms, this street must be before this zoom
                    street_before_zoom = model.NewBoolVar(f'{street_id}_before_{zoom_id}')
                    model.Add(appointment_vars[street_id] +
                              client_availabilities[next(i for i, c in enumerate(client_availabilities)
                                                         if c['id'] == street_id)]['duration'] + 75 <=
                              appointment_vars[zoom_id]).OnlyEnforceIf(
                        [both_on_day, streets_before_zooms, street_before_zoom])

                    # If streets after zooms, this street must be after this zoom
                    zoom_before_street = model.NewBoolVar(f'{zoom_id}_before_{street_id}')
                    model.Add(appointment_vars[zoom_id] +
                              client_availabilities[next(i for i, c in enumerate(client_availabilities)
                                                         if c['id'] == zoom_id)]['duration'] + 75 <=
                              appointment_vars[street_id]).OnlyEnforceIf(
                        [both_on_day, streets_after_zooms, zoom_before_street])

                    # Ensure exactly one ordering if both are scheduled on this day
                    model.AddBoolOr([street_before_zoom, zoom_before_street]).OnlyEnforceIf(both_on_day)

    # Add constraints to prevent scheduling appointments at the same time (no overlaps)
    for i, client1 in enumerate(client_availabilities):
        client1_id = client1['id']
        client1_duration = client1['duration']
        client1_type = client1['type']

        for j, client2 in enumerate(client_availabilities):
            if i >= j:
                continue

            client2_id = client2['id']
            client2_duration = client2['duration']
            client2_type = client2['type']

            # Create boolean variables to represent the two cases of non-overlap
            client1_before_client2 = model.NewBoolVar(f'{client1_id}_before_{client2_id}')
            client2_before_client1 = model.NewBoolVar(f'{client2_id}_before_{client1_id}')

            # Calculate required break time between sessions
            required_break = 15  # Minimum 15-minute break between all sessions

            # Apply 75-minute break rule for streets-zoom transitions
            if (client1_type in ['streets', 'trial_streets'] and client2_type in ['zoom', 'trial_zoom']) or \
                    (client2_type in ['streets', 'trial_streets'] and client1_type in ['zoom', 'trial_zoom']):
                required_break = 75

            # If both clients are scheduled, ensure they don't overlap
            both_scheduled = model.NewBoolVar(f'both_{client1_id}_{client2_id}_scheduled')
            model.AddBoolAnd([appointment_scheduled_vars[client1_id],
                              appointment_scheduled_vars[client2_id]]).OnlyEnforceIf(both_scheduled)
            model.AddBoolOr([appointment_scheduled_vars[client1_id].Not(),
                             appointment_scheduled_vars[client2_id].Not()]).OnlyEnforceIf(both_scheduled.Not())

            # If both are scheduled, ensure they don't overlap
            model.Add(
                appointment_vars[client1_id] + client1_duration + required_break <= appointment_vars[client2_id]
            ).OnlyEnforceIf([both_scheduled, client1_before_client2])
            model.Add(
                appointment_vars[client2_id] + client2_duration + required_break <= appointment_vars[client1_id]
            ).OnlyEnforceIf([both_scheduled, client2_before_client1])

            # Ensure that exactly one of the non-overlap constraints is true if both are scheduled
            model.AddBoolOr([client1_before_client2, client2_before_client1]).OnlyEnforceIf(both_scheduled)

    # Set up the optimization objective
    objective_terms = []

    # Maximize the number of scheduled appointments based on priority
    for client in client_availabilities:
        client_id = client['id']
        priority = client['priority']
        # Prioritize client by priority value and add a small weight for lower client IDs
        # This ensures deterministic behavior when clients have identical constraints

        client_index = next((i for i, c in enumerate(client_availabilities) if c['id'] == client_id), 0)
        objective_terms.append(appointment_scheduled_vars[client_id] * priority * 100)  # Weight by priority
        # Small preference based on index
        objective_terms.append(appointment_scheduled_vars[client_id] * (-client_index * 0.1))
        print(f"DEBUG: Client ID processing")
        print(f"  Original client_id: {client_id}")
        print(f"  Converted to int: {client_index}")
        print(f"  Weight in objective: {(-client_index * 0.1)}")

    # Maximize the number of days with at least 2 street sessions
    for day in days_with_streets:
        objective_terms.append(days_with_streets[day] * 1000)  # High weight to prioritize days with streets

    # Maximize the number of street sessions per day (up to 4)
    for day in street_sessions_per_day:
        sessions_count = street_sessions_per_day[day]
        # Add bonus for each street session (diminishing returns after 4)
        for i in range(1, 5):
            has_at_least_i = model.NewBoolVar(f'day_{day}_has_at_least_{i}')
            model.Add(sessions_count >= i).OnlyEnforceIf(has_at_least_i)
            model.Add(sessions_count < i).OnlyEnforceIf(has_at_least_i.Not())

            # Weight decreases as we get more sessions
            weight = 500 if i <= 2 else 300 if i <= 3 else 200
            objective_terms.append(has_at_least_i * weight)

    print(f"\n=== Debug: Objective Function ===")
    print(f"Number of terms in objective: {len(objective_terms)}")
    for i, term in enumerate(objective_terms):
        print(f"Term {i}: {term}")

    model.Maximize(sum(objective_terms))

    # Add this after all constraints have been added but before solving:
    print(f"Model has been created with the following stats:")
    print(f"Variables dictionary size: {len(model.__dict__.get('_CpModel__variables', {}))}")
    print(f"Constraints dictionary size: {len(model.__dict__.get('_CpModel__constraints', {}))}")
    print(f"Client availabilities: {len(client_availabilities)}")
    print(f"Appointment variables: {len(appointment_vars)}")
    print(f"Day variables: {len(appointment_day_vars)}")
    print(f"Scheduled variables: {len(appointment_scheduled_vars)}")

    # Check appointments that can potentially be scheduled
    print(f"\n=== Debug: Potential Appointments ===")
    for client_id, var in appointment_scheduled_vars.items():
        client_type = next(c['type'] for c in client_availabilities if c['id'] == client_id)
        client_day_var = appointment_day_vars[client_id]
        print(f"Client {client_id} ({client_type}): scheduled_var={var.Index()}, day_var={client_day_var.Index()}")

    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True  # Algo Verbosity
    status = solver.Solve(model)

    print(f"\n=== Debug: Solver Stats ===")
    print(f"Solution status: {solver.StatusName(status)}")
    print(f"Objective value: {solver.ObjectiveValue()}")
    print(f"Wall time: {solver.WallTime()} seconds")
    print(f"Branches: {solver.NumBranches()}")
    print(f"Conflicts: {solver.NumConflicts()}")

    # Check individual variable values
    print(f"\n=== Debug: Appointment Variables ===")
    for client_id, var in appointment_scheduled_vars.items():
        scheduled = solver.Value(var)
        if scheduled:
            start_time = solver.Value(appointment_vars[client_id])
            day = solver.Value(appointment_day_vars[client_id])
            print(f"Client {client_id}: scheduled=True, day={day}, start_time={start_time}")
        else:
            print(f"Client {client_id}: scheduled=False")

    # Process the results
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Get scheduled appointments
        scheduled_appointments = []

        for client in client_availabilities:
            client_id = client['id']

            if solver.Value(appointment_scheduled_vars[client_id]):
                start_time_minutes = solver.Value(appointment_vars[client_id])
                day_number = solver.Value(appointment_day_vars[client_id])

                # Calculate the date and time
                appointment_date = constraint_start_date + timedelta(days=(day_number - our_start_weekday + 7) % 7)
                start_hour = (start_time_minutes % (24 * 60)) // 60
                start_minute = (start_time_minutes % (24 * 60)) % 60

                end_time_minutes = start_time_minutes + client['duration']
                end_hour = (end_time_minutes % (24 * 60)) // 60
                end_minute = (end_time_minutes % (24 * 60)) % 60

                scheduled_appointments.append({
                    'client_id': client_id,
                    'type': client['type'],
                    'day': day_number_to_name(day_number),
                    'date': appointment_date.strftime('%Y-%m-%d'),
                    'start_time': f"{start_hour:02d}:{start_minute:02d}",
                    'end_time': f"{end_hour:02d}:{end_minute:02d}",
                    'duration': client['duration']
                })

        print(f"\n=== Debug: Client Availabilities ===")

        scheduled_appointments = minimize_gaps_post_processing(scheduled_appointments)

        # Sort appointments by date and time
        scheduled_appointments.sort(key=lambda x: (x['date'], x['start_time']))

        # Print summary statistics
        total_scheduled = len(scheduled_appointments)
        street_sessions = sum(1 for appt in scheduled_appointments if appt['type'] in ['streets', 'trial_streets'])
        zoom_sessions = sum(1 for appt in scheduled_appointments if appt['type'] in ['zoom', 'trial_zoom'])

        print(f"Schedule optimization complete. Status: {solver.StatusName(status)}")
        print(f"Total appointments scheduled: {total_scheduled}")
        print(f"Street sessions: {street_sessions}")
        print(f"Zoom sessions: {zoom_sessions}")

        # Check for unscheduled clients
        scheduled_client_ids = set(appt['client_id'] for appt in scheduled_appointments)
        all_client_ids = set(client['id'] for client in client_availabilities)
        unscheduled_client_ids = all_client_ids - scheduled_client_ids

        if unscheduled_client_ids:
            print(f"\nUnscheduled clients: {len(unscheduled_client_ids)}")
            for client_id in sorted(unscheduled_client_ids):
                # Find the client data
                client_data = next((c for c in client_availabilities if c['id'] == client_id), None)
                if client_data:
                    priority_value_to_name = {3: "High", 2: "Medium", 1: "Low"}
                    priority_name = priority_value_to_name.get(client_data['priority'], str(client_data['priority']))
                    print(f"  - Client ID {client_id}: {client_data['type']} session (Priority: {priority_name})")

                    # Try to determine why this client wasn't scheduled
                    availability_count = sum(1 for avail in client_data['availabilities'] if avail[1] >= avail[0])
                    if availability_count == 0:
                        print(f"    Reason: No valid availability slots")
                    else:
                        # Check for conflicts with scheduled appointments
                        conflicts = []
                        for appt in scheduled_appointments:
                            # If both are on the same day
                            client_days = set(day for _, _, day in client_data['availabilities'])
                            appt_day = day_name_to_number(appt['day'])

                            if appt_day in client_days:
                                if (client_data['type'] in ['streets', 'trial_streets'] and appt['type'] in
                                        ['streets', 'trial_streets']):
                                    conflicts.append(f"Potential street session conflict with Client "
                                                     f"{appt['client_id']} ({appt['day']} {appt['start_time']})")
                                elif (client_data['type'] in ['streets', 'trial_streets'] and appt['type'] in
                                      ['zoom', 'trial_zoom']) or \
                                        (client_data['type'] in ['zoom', 'trial_zoom'] and appt['type'] in
                                         ['streets', 'trial_streets']):
                                    conflicts.append(
                                        f"Potential streets-zoom transition with Client {appt['client_id']} "
                                        f"({appt['day']} {appt['start_time']})"
                                    )

                        if conflicts:
                            print(f"    Possible conflicts:")
                            for conflict in conflicts[:3]:  # Limit to first 3 conflicts
                                print(f"    - {conflict}")
                            if len(conflicts) > 3:
                                print(f"    - ...and {len(conflicts) - 3} more potential conflicts")
                        else:
                            print(f"    Reason: Likely couldn't fit into schedule while maintaining all constraints")
                else:
                    print(f"  - Client ID {client_id}: Unknown details")

        # Print daily schedule header
        print(f"\n=== Schedule Results ===")

        # Print daily schedule
        days_with_appointments = {}
        for appt in scheduled_appointments:
            day = appt['date']
            if day not in days_with_appointments:
                days_with_appointments[day] = []
            days_with_appointments[day].append(appt)

        for day, appointments in sorted(days_with_appointments.items()):
            print(f"\n=== {appointments[0]['day']} ({day}) ===")
            for appt in sorted(appointments, key=lambda x: x['start_time']):
                print(f"{appt['start_time']} - {appt['end_time']} : {appt['type']} (Client ID: {appt['client_id']})")

        # Return the scheduled appointments for potential export to JSON
        return scheduled_appointments, client_availabilities
    else:
        print(f"No solution found. Status: {solver.StatusName(status)}")
        return [], client_availabilities


def enforce_street_zoom_gaps(appointments, streets_zoom_break=75):
    """Enforces the 75-minute gap constraint between street and zoom sessions.

    Args:
        appointments: List of appointments for a single day, sorted by start time
        streets_zoom_break: Minimum break required between street and zoom sessions

    Returns:
        Updated list of appointments with correct gaps
    """
    if len(appointments) <= 1:
        return appointments

    # Create a copy to avoid modifying the original
    appointments = [appointment.copy() for appointment in appointments]

    # Sort by start time to ensure proper order
    appointments.sort(key=lambda x: x['start_time'])

    # Check for violations of the constraint (street followed by zoom with gap < 75 minutes)
    for i in range(len(appointments) - 1):
        current = appointments[i]
        next_appt = appointments[i + 1]

        # Check if this is a street-to-zoom transition
        if current['type'] in ['streets', 'trial_streets'] and next_appt['type'] in ['zoom', 'trial_zoom']:
            current_end_minutes = time_to_minutes(current['end_time'])
            next_start_minutes = time_to_minutes(next_appt['start_time'])

            # Calculate the gap
            gap = next_start_minutes - current_end_minutes

            # If gap is less than required, adjust the next appointment
            if gap < streets_zoom_break:
                # Move the zoom session to start 75 minutes after the street session ends
                new_start_minutes = current_end_minutes + streets_zoom_break
                new_end_minutes = new_start_minutes + next_appt['duration']

                next_appt['start_time'] = minutes_to_time(new_start_minutes)
                next_appt['end_time'] = minutes_to_time(new_end_minutes)

                # Now we need to check and fix any overlaps created by this adjustment
                for j in range(i + 1, len(appointments) - 1):
                    current_j = appointments[j]
                    next_j = appointments[j + 1]

                    current_j_end = time_to_minutes(current_j['end_time'])
                    next_j_start = time_to_minutes(next_j['start_time'])

                    required_gap = streets_zoom_break if (current_j['type'] in ['streets', 'trial_streets'] and
                                                          next_j['type'] in ['zoom', 'trial_zoom']) else required_break

                    # If there's an overlap or insufficient gap
                    if next_j_start < current_j_end + required_gap:
                        # Adjust the next appointment
                        new_next_start = current_j_end + required_gap
                        new_next_end = new_next_start + next_j['duration']

                        next_j['start_time'] = minutes_to_time(new_next_start)
                        next_j['end_time'] = minutes_to_time(new_next_end)

    # Re-sort by start time in case any adjustments changed the order
    appointments.sort(key=lambda x: x['start_time'])

    return appointments


def minimize_gaps_post_processing(scheduled_appointments, required_break=15, streets_zoom_break=75):
    """Post-processes the schedule to minimize gaps between street sessions while maintaining constraints.

    Args:
        scheduled_appointments: List of scheduled appointment dictionaries
        required_break: Minimum break between any two sessions (default: 15 minutes)
        streets_zoom_break: Minimum break between street and zoom sessions (default: 75 minutes)

    Returns:
        List of appointments with minimized gaps between street sessions
    """
    # Group appointments by day
    appointments_by_day = {}
    for appt in scheduled_appointments:
        day = appt['date']
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appt)

    # Process each day
    for day, appointments in appointments_by_day.items():
        # Sort by start time
        appointments.sort(key=lambda x: x['start_time'])

        # First, verify and fix gaps between street-to-zoom transitions
        # This needs to be done before compacting street sessions to ensure the 75-minute gap is maintained
        appointments = enforce_street_zoom_gaps(appointments, required_break, streets_zoom_break)

        # After fixing gaps, identify street and non-street sessions
        street_sessions = [appt for appt in appointments if appt['type'] in ['streets', 'trial_streets']]
        non_street_sessions = [appt for appt in appointments if appt['type'] not in ['streets', 'trial_streets']]

        # Only proceed with compacting if there are at least 2 street sessions
        if len(street_sessions) >= 2:
            # Sort street sessions by start time
            street_sessions.sort(key=lambda x: x['start_time'])

            # Create a timeline of fixed points from non-street sessions
            fixed_points = []
            for appt in non_street_sessions:
                start_minutes = time_to_minutes(appt['start_time'])
                end_minutes = time_to_minutes(appt['end_time'])
                session_type = appt['type']

                # Add constraints for zoom sessions
                if session_type in ['zoom', 'trial_zoom']:
                    # Streets must end at least 75 minutes before zoom starts
                    fixed_points.append({
                        'time': start_minutes - streets_zoom_break,
                        'type': 'before_zoom'
                    })
                    # Streets can start at least 75 minutes after zoom ends
                    fixed_points.append({
                        'time': end_minutes + streets_zoom_break,
                        'type': 'after_zoom'
                    })

            # Sort fixed points by time
            fixed_points.sort(key=lambda x: x['time'])

            # Compact the street sessions while respecting fixed points
            compact_street_sessions(street_sessions, fixed_points, required_break)

            # Update the appointments list
            all_sessions = non_street_sessions + street_sessions
            all_sessions.sort(key=lambda x: x['start_time'])

            # Verify once more that all constraints are maintained
            all_sessions = enforce_street_zoom_gaps(all_sessions, required_break, streets_zoom_break)

            # Replace the day's appointments with the updated list
            appointments_by_day[day] = all_sessions

    # Reconstruct the full schedule
    updated_appointments = []
    for day_appointments in appointments_by_day.values():
        updated_appointments.extend(day_appointments)

    # Sort by date and time
    updated_appointments.sort(key=lambda x: (x['date'], x['start_time']))

    return updated_appointments


def enforce_street_zoom_gaps(appointments, required_break=15, streets_zoom_break=75):
    """Enforces the 75-minute gap constraint between street and zoom sessions.

    Args:
        appointments: List of appointments for a single day, sorted by start time
        required_break: Minimum break between any two sessions (default: 15 minutes)
        streets_zoom_break: Minimum break required between street and zoom sessions

    Returns:
        Updated list of appointments with correct gaps
    """
    if len(appointments) <= 1:
        return appointments

    # Create a copy to avoid modifying the original
    appointments = [appointment.copy() for appointment in appointments]

    # Sort by start time to ensure proper order
    appointments.sort(key=lambda x: x['start_time'])

    # Check for violations of the constraint (street followed by zoom with gap < 75 minutes)
    for i in range(len(appointments) - 1):
        current = appointments[i]
        next_appt = appointments[i + 1]

        # Check if this is a street-to-zoom transition
        if current['type'] in ['streets', 'trial_streets'] and next_appt['type'] in ['zoom', 'trial_zoom']:
            current_end_minutes = time_to_minutes(current['end_time'])
            next_start_minutes = time_to_minutes(next_appt['start_time'])

            # Calculate the gap
            gap = next_start_minutes - current_end_minutes

            # If gap is less than required, adjust the next appointment
            if gap < streets_zoom_break:
                # Move the zoom session to start 75 minutes after the street session ends
                new_start_minutes = current_end_minutes + streets_zoom_break
                new_end_minutes = new_start_minutes + next_appt['duration']

                next_appt['start_time'] = minutes_to_time(new_start_minutes)
                next_appt['end_time'] = minutes_to_time(new_end_minutes)

                # Now we need to check and fix any overlaps created by this adjustment
                for j in range(i + 1, len(appointments) - 1):
                    current_j = appointments[j]
                    next_j = appointments[j + 1]

                    current_j_end = time_to_minutes(current_j['end_time'])
                    next_j_start = time_to_minutes(next_j['start_time'])

                    required_gap = streets_zoom_break if (current_j['type'] in ['streets', 'trial_streets'] and
                                                          next_j['type'] in ['zoom', 'trial_zoom']) else required_break

                    # If there's an overlap or insufficient gap
                    if next_j_start < current_j_end + required_gap:
                        # Adjust the next appointment
                        new_next_start = current_j_end + required_gap
                        new_next_end = new_next_start + next_j['duration']

                        next_j['start_time'] = minutes_to_time(new_next_start)
                        next_j['end_time'] = minutes_to_time(new_next_end)

    # Re-sort by start time in case any adjustments changed the order
    appointments.sort(key=lambda x: x['start_time'])

    return appointments


def time_to_minutes(time_str):
    """Convert time string (HH:MM) to minutes from midnight."""
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes


def minutes_to_time(minutes):
    """Convert minutes from midnight to time string (HH:MM)."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def compact_street_sessions(street_sessions, fixed_points, required_break):
    """Compact street sessions to minimize gaps while respecting fixed points."""
    # If no street sessions, nothing to do
    if not street_sessions:
        return

    # Get the earliest possible start time (considering first fixed point)
    # By default, start at the original start time of the first session
    current_time = time_to_minutes(street_sessions[0]['start_time'])

    # Check if there are fixed points before the first session
    relevant_fixed_points = [fp for fp in fixed_points if fp['time'] < current_time]
    if relevant_fixed_points:
        # Start after the last fixed point before the original start time
        current_time = max(current_time, relevant_fixed_points[-1]['time'])

    # Process each street session
    for i, session in enumerate(street_sessions):
        session_duration = session['duration']

        # Check if we need to delay this session due to a fixed point
        for fixed_point in fixed_points:
            if current_time < fixed_point['time'] < current_time + session_duration:
                # Need to start after this fixed point
                current_time = fixed_point['time']

        # Update the session's start and end times
        new_start = current_time
        new_end = new_start + session_duration

        # Update the session times
        session['start_time'] = minutes_to_time(new_start)
        session['end_time'] = minutes_to_time(new_end)

        # Update current time for the next session
        current_time = new_end + required_break


def export_schedule_to_json(scheduled_appointments, output_file):
    """Export the scheduled appointments to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(scheduled_appointments, f, indent=2)
    print(f"Schedule exported to {output_file}")


def validate_schedule(appointments, min_break=15, zoom_streets_break=75,
                      max_street_gap=30, max_street_minutes=270):
    """
    Validates a schedule against all constraints.

    Args:
        appointments: List of appointment dictionaries with:
            - client_id: Client ID
            - type: Session type (streets, trial_streets, zoom, trial_zoom)
            - day: Day name
            - date: Date as string YYYY-MM-DD
            - start_time: Start time as string HH:MM
            - end_time: End time as string HH:MM
            - duration: Duration in minutes
        min_break: Minimum break between any two appointments (minutes)
        zoom_streets_break: Minimum break between zoom and streets sessions (minutes)
        max_street_gap: Maximum gap between consecutive street sessions (minutes)
        max_street_minutes: Maximum street session minutes per day (minutes)

    Returns:
        dict: Validation result with:
            - valid: Boolean indicating if all constraints are met
            - violations: List of constraint violations
    """
    # Initialize result
    result = {
        "valid": True,
        "violations": []
    }

    # Group appointments by day
    appointments_by_day = {}
    for appt in appointments:
        day = appt['date']
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appt)

    # Helper functions
    def time_to_minutes(time_str):
        """Convert time string (HH:MM) to minutes from midnight."""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes

    # Check each day's schedule
    for day, day_appointments in appointments_by_day.items():
        # Sort by start time
        day_appointments.sort(key=lambda x: x['start_time'])

        # Check 1: Minimum breaks between appointments
        for i in range(len(day_appointments) - 1):
            current = day_appointments[i]
            next_appt = day_appointments[i + 1]

            current_end = time_to_minutes(current['end_time'])
            next_start = time_to_minutes(next_appt['start_time'])
            gap = next_start - current_end

            # Check minimum break
            if gap < min_break:
                result["valid"] = False
                result["violations"].append({
                    "constraint": "minimum_break",
                    "description": f"Insufficient break ({gap} minutes) between {current['type']} "
                                   f"(Client {current['client_id']}) and {next_appt['type']} "
                                   f"(Client {next_appt['client_id']}) on {day}",
                    "expected": min_break,
                    "actual": gap
                })

            # Check zoom/streets break
            streets_types = ['streets', 'trial_streets']
            zoom_types = ['zoom', 'trial_zoom']

            if ((current['type'] in streets_types and next_appt['type'] in zoom_types) or
                    (current['type'] in zoom_types and next_appt['type'] in streets_types)):
                if gap < zoom_streets_break:
                    result["valid"] = False
                    result["violations"].append({
                        "constraint": "zoom_streets_break",
                        "description": f"Insufficient break ({gap} minutes) between {current['type']} "
                                       f"(Client {current['client_id']}) and {next_appt['type']} "
                                       f"(Client {next_appt['client_id']}) on {day}",
                        "expected": zoom_streets_break,
                        "actual": gap
                    })

        # Check 2: Minimum of two street sessions per day or none
        street_sessions = [appt for appt in day_appointments
                           if appt['type'] in ['streets', 'trial_streets']]

        if 1 == len(street_sessions):
            result["valid"] = False
            result["violations"].append({
                "constraint": "minimum_street_sessions",
                "description": f"Only 1 street session on {day}, must be at least 2 or none",
                "expected": "0 or ≥2",
                "actual": len(street_sessions)
            })

        # Check 3: Maximum street minutes per day
        if street_sessions:
            total_street_minutes = sum(s['duration'] for s in street_sessions)
            if total_street_minutes > max_street_minutes:
                result["valid"] = False
                result["violations"].append({
                    "constraint": "max_street_minutes",
                    "description": f"Too many street session minutes ({total_street_minutes}) on {day}",
                    "expected": f"≤{max_street_minutes}",
                    "actual": total_street_minutes
                })

        # Check 4: Maximum gap between consecutive street sessions
        if len(street_sessions) >= 2:
            for i in range(len(street_sessions) - 1):
                current = street_sessions[i]
                next_street = street_sessions[i + 1]

                current_end = time_to_minutes(current['end_time'])
                next_start = time_to_minutes(next_street['start_time'])
                gap = next_start - current_end

                if gap > max_street_gap:
                    result["valid"] = False
                    result["violations"].append({
                        "constraint": "max_street_gap",
                        "description": f"Gap between street sessions ({gap} minutes) exceeds maximum on {day} "
                                       f"between Client {current['client_id']} and Client {next_street['client_id']}",
                        "expected": f"≤{max_street_gap}",
                        "actual": gap
                    })

    # Check 5: One appointment per client per day (across all days)
    client_days = {}
    for appt in appointments:
        client_id = appt['client_id']
        day = appt['date']
        key = f"{client_id}_{day}"

        if key in client_days:
            result["valid"] = False
            result["violations"].append({
                "constraint": "one_appointment_per_client_per_day",
                "description": f"Client {client_id} has multiple appointments on {day}",
                "expected": "1",
                "actual": "≥2"
            })
        else:
            client_days[key] = True

    # Check 6: No overlapping appointments
    for day, day_appointments in appointments_by_day.items():
        for i in range(len(day_appointments)):
            for j in range(i + 1, len(day_appointments)):
                appt1 = day_appointments[i]
                appt2 = day_appointments[j]

                start1 = time_to_minutes(appt1['start_time'])
                end1 = time_to_minutes(appt1['end_time'])
                start2 = time_to_minutes(appt2['start_time'])
                end2 = time_to_minutes(appt2['end_time'])

                if (start1 <= start2 < end1) or (start1 < end2 <= end1) or (start2 <= start1 < end2):
                    result["valid"] = False
                    result["violations"].append({
                        "constraint": "no_overlapping_appointments",
                        "description": f"Appointments for Client {appt1['client_id']} and Client {appt2['client_id']} "
                                       f"overlap on {day}",
                        "details": f"{appt1['start_time']}-{appt1['end_time']} overlaps with "
                                   f"{appt2['start_time']}-{appt2['end_time']}"
                    })

    return result


def integrate_with_scheduler(scheduled_appointments, client_availabilities, output_file):
    """
    Validates the schedule and modifies the output if needed.

    Args:
        scheduled_appointments: List of appointment dictionaries
        client_availabilities: List of client availability dictionaries
        output_file: Path to the output JSON file

    Returns:
        dict: The validated and potentially fixed schedule
    """
    import json
    from datetime import datetime, timedelta

    # First, validate the schedule
    validation_result = validate_schedule(scheduled_appointments)

    if not validation_result["valid"]:
        print("\n=== Schedule Validation Failed ===")
        print(f"Found {len(validation_result['violations'])} constraint violations:")

        for i, violation in enumerate(validation_result["violations"], 1):
            print(f"\nViolation {i}: {violation['constraint']}")
            print(f"  {violation['description']}")
            if "expected" in violation and "actual" in violation:
                print(f"  Expected: {violation['expected']}, Actual: {violation['actual']}")
            if "details" in violation:
                print(f"  Details: {violation['details']}")

        # Here you could attempt to fix the schedule or reject it entirely
        # For simplicity, we'll just flag it as invalid in the output

    # Build the filled appointments list
    filled_appointments = []
    for appt in scheduled_appointments:
        client_id = appt['client_id']
        appt_date = appt['date']
        start_time = appt['start_time']
        end_time = appt['end_time']

        # Convert to ISO format for output
        iso_start_time = f"{appt_date}T{start_time}:00"
        iso_end_time = f"{appt_date}T{end_time}:00"

        filled_appointments.append({
            "id": client_id,
            "type": appt['type'],
            "start_time": iso_start_time,
            "end_time": iso_end_time
        })

    # Get set of scheduled client IDs
    scheduled_client_ids = set(appt['client_id'] for appt in scheduled_appointments)

    # Get all client IDs
    all_client_ids = set(client['id'] for client in client_availabilities)

    # Get unscheduled client IDs
    unscheduled_client_ids = all_client_ids - scheduled_client_ids

    # Build unfilled appointments list
    unfilled_appointments = []
    for client_id in unscheduled_client_ids:
        client_data = next((c for c in client_availabilities if c['id'] == client_id), None)
        if client_data:
            unfilled_appointments.append({
                "id": client_id,
                "type": client_data['type']
            })

    # Count sessions by type
    session_types = ['streets', 'trial_streets', 'zoom', 'trial_zoom', 'field']
    type_counts = {
        session_type: {
            'scheduled': 0,
            'total': 0,
            'rate': 0.0
        } for session_type in session_types
    }

    # Count total for each type
    for client in client_availabilities:
        session_type = client['type']
        if session_type in type_counts:
            type_counts[session_type]['total'] += 1
    print(f"\n=== Debug: Client Availabilities ===")

    # Count scheduled for each type
    for appt in scheduled_appointments:
        session_type = appt['type']
        if session_type in type_counts:
            type_counts[session_type]['scheduled'] += 1

    # Calculate rates
    for session_type in type_counts:
        total = type_counts[session_type]['total']
        if total > 0:
            scheduled = type_counts[session_type]['scheduled']
            type_counts[session_type]['rate'] = round(scheduled / total, 2)
        else:
            type_counts[session_type]['rate'] = 1.0  # If total is 0, set rate to 1.0

    # Assemble the final output structure
    output_data = {
        "filled_appointments": filled_appointments,
        "unfilled_appointments": unfilled_appointments,
        "validation": {
            "valid": validation_result["valid"],
            "issues": validation_result["violations"] if not validation_result["valid"] else []
        },
        "type_balance": type_counts
    }

    # Write to file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nEnhanced schedule exported to {output_file}")
    if not validation_result["valid"]:
        print(f"WARNING: Schedule has constraint violations - see {output_file} for details")

    return output_data


def export_enhanced_schedule_to_json(scheduled_appointments, client_availabilities, output_file):
    """Export the scheduled appointments to a JSON file with enhanced format.

    Args:
        scheduled_appointments: List of scheduled appointment dictionaries
        client_availabilities: List of client availability dictionaries
        output_file: Path to the output JSON file
    """
    # Build the filled appointments list
    filled_appointments = []
    for appt in scheduled_appointments:
        client_id = appt['client_id']
        appt_date = appt['date']
        start_time = appt['start_time']
        end_time = appt['end_time']

        # Convert to ISO format for output
        iso_start_time = f"{appt_date}T{start_time}:00"
        iso_end_time = f"{appt_date}T{end_time}:00"

        filled_appointments.append({
            "id": client_id,
            "type": appt['type'],
            "start_time": iso_start_time,
            "end_time": iso_end_time
        })

    # Get set of scheduled client IDs
    scheduled_client_ids = set(appt['client_id'] for appt in scheduled_appointments)

    # Build unfilled appointments list (currently empty as per example)
    unfilled_appointments = []

    # Get all client IDs
    all_client_ids = set(client['id'] for client in client_availabilities)

    # Get unscheduled client IDs
    unscheduled_client_ids = all_client_ids - scheduled_client_ids

    # Optionally, you could populate unfilled_appointments with info about unscheduled clients
    # Uncomment the following code if you want to include unscheduled clients
    """
    for client_id in unscheduled_client_ids:
        client_data = next((c for c in client_availabilities if c['id'] == client_id), None)
        if client_data:
            unfilled_appointments.append({
                "id": client_id,
                "type": client_data['type']
            })
    """

    # Count sessions by type
    session_types = ['streets', 'trial_streets', 'zoom', 'trial_zoom', 'field']
    type_counts = {
        session_type: {
            'scheduled': 0,
            'total': 0,
            'rate': 0.0
        } for session_type in session_types
    }

    # Count total for each type
    for client in client_availabilities:
        session_type = client['type']
        if session_type in type_counts:
            type_counts[session_type]['total'] += 1
    print(f"\n=== Debug: Client Availabilities ===")

    # Count scheduled for each type
    for appt in scheduled_appointments:
        session_type = appt['type']
        if session_type in type_counts:
            type_counts[session_type]['scheduled'] += 1

    # Calculate rates
    for session_type in type_counts:
        total = type_counts[session_type]['total']
        if total > 0:
            scheduled = type_counts[session_type]['scheduled']
            type_counts[session_type]['rate'] = round(scheduled / total, 2)
        else:
            type_counts[session_type]['rate'] = 1.0  # If total is 0, set rate to 1.0

    # Build the validation section (simplified for now)
    validation = {
        "valid": True,
        "issues": []
    }

    # Assemble the final output structure
    output_data = {
        "filled_appointments": filled_appointments,
        "unfilled_appointments": unfilled_appointments,
        "validation": validation,
        "type_balance": type_counts
    }

    # Write to file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"Enhanced schedule exported to {output_file}")


def export_schedule_to_html(scheduled_appointments, client_availabilities, output_file, start_date):
    """Export the scheduled appointments to an HTML file with a neat design.

    Args:
        scheduled_appointments: List of scheduled appointment dictionaries
        client_availabilities: List of client availability dictionaries
        output_file: Path to the output HTML file
        start_date: The start date of the scheduling period (datetime object)
    """
    # Get set of scheduled client IDs
    scheduled_client_ids = set(appt['client_id'] for appt in scheduled_appointments)

    # Get all client IDs
    all_client_ids = set(client['id'] for client in client_availabilities)

    # Get unscheduled client IDs
    unscheduled_client_ids = all_client_ids - scheduled_client_ids

    # Group appointments by day
    appointments_by_day = {}
    for appt in scheduled_appointments:
        day = appt['date']
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appt)

    # Get unscheduled clients info
    unscheduled_clients = []
    for client_id in unscheduled_client_ids:
        client_data = next((c for c in client_availabilities if c['id'] == client_id), None)
        if client_data:
            session_type = client_data['type']
            priority_value = client_data['priority']

            # Convert priority value back to name
            priority_value_to_name = {3: "High", 2: "Medium", 1: "Low"}
            priority_name = priority_value_to_name.get(priority_value, str(priority_value))

            unscheduled_clients.append({
                'id': client_id,
                'type': session_type,
                'priority': priority_name
            })

    # Count sessions by type
    session_types = ['streets', 'trial_streets', 'zoom', 'trial_zoom', 'field']
    type_counts = {
        session_type: {
            'scheduled': 0,
            'total': 0,
            'rate': 0.0
        } for session_type in session_types
    }

    # Count total for each type
    for client in client_availabilities:
        session_type = client['type']
        if session_type in type_counts:
            type_counts[session_type]['total'] += 1
    print(f"\n=== Debug: Client Availabilities ===")

    # Count scheduled for each type
    for appt in scheduled_appointments:
        session_type = appt['type']
        if session_type in type_counts:
            type_counts[session_type]['scheduled'] += 1

    # Calculate rates
    for session_type in type_counts:
        total = type_counts[session_type]['total']
        if total > 0:
            scheduled = type_counts[session_type]['scheduled']
            type_counts[session_type]['rate'] = round(scheduled / total * 100)  # Percentage

    # Create the HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Schedule Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            .header {{
                border-bottom: 2px solid #3498db;
                margin-bottom: 20px;
                padding-bottom: 10px;
            }}
            .summary {{
                background-color: #f8f9fa;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
            }}
            .summary-box {{
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                margin: 5px;
                flex: 1;
                min-width: 200px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .day-schedule {{
                margin-bottom: 30px;
            }}
            .day-header {{
                background-color: #3498db;
                color: white;
                padding: 10px;
                border-radius: 5px 5px 0 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .streets {{
                background-color: #d4edda;
            }}
            .trial_streets {{
                background-color: #c3e6cb;
            }}
            .zoom {{
                background-color: #d1ecf1;
            }}
            .trial_zoom {{
                background-color: #bee5eb;
            }}
            .unscheduled {{
                background-color: #f8d7da;
                margin-top: 30px;
                border-radius: 5px;
                padding: 15px;
            }}
            .progress {{
                height: 20px;
                width: 100%;
                background-color: #e9ecef;
                border-radius: 20px;
                position: relative;
                margin-top: 5px;
            }}
            .progress-bar {{
                height: 100%;
                border-radius: 20px;
                background-color: #3498db;
                text-align: center;
                color: white;
                line-height: 20px;
                font-size: 12px;
            }}
            .good {{
                background-color: #28a745;
            }}
            .medium {{
                background-color: #ffc107;
            }}
            .poor {{
                background-color: #dc3545;
            }}
            .badge {{
                display: inline-block;
                padding: 3px 7px;
                font-size: 12px;
                font-weight: bold;
                line-height: 1;
                text-align: center;
                white-space: nowrap;
                vertical-align: baseline;
                border-radius: 10px;
                color: white;
            }}
            .badge-streets {{
                background-color: #28a745;
            }}
            .badge-trial_streets {{
                background-color: #20c997;
            }}
            .badge-zoom {{
                background-color: #17a2b8;
            }}
            .badge-trial_zoom {{
                background-color: #0dcaf0;
            }}
            .empty-message {{
                text-align: center;
                padding: 20px;
                color: #6c757d;
            }}
            footer {{
                margin-top: 50px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                text-align: center;
                font-size: 14px;
                color: #6c757d;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Appointment Schedule Report</h1>
            <p>Scheduling period starting: {start_date.strftime('%Y-%m-%d')}</p>
            <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>

        <div class="summary">
            <div class="summary-box">
                <h3>Schedule Overview</h3>
                <p>Total appointments: {len(client_availabilities)}</p>
                <p>Scheduled: {len(scheduled_appointments)} 
                ({round(len(scheduled_appointments) / len(client_availabilities) * 100 if len(client_availabilities) > 0 else 0)}%)</p>
                <p>Unscheduled: {len(unscheduled_clients)}</p>
            </div>
    """

    # Add session type statistics
    for session_type in ['streets', 'trial_streets', 'zoom', 'trial_zoom']:
        if type_counts[session_type]['total'] > 0:
            scheduled = type_counts[session_type]['scheduled']
            total = type_counts[session_type]['total']
            rate = type_counts[session_type]['rate']

            # Determine color class based on rate
            color_class = "good" if rate >= 75 else "medium" if rate >= 50 else "poor"

            # Format the session type for display
            display_type = " ".join(word.capitalize() for word in session_type.split("_"))

            html_content += f"""
            <div class="summary-box">
                <h3>{display_type}</h3>
                <p>Scheduled: {scheduled} / {total}</p>
                <div class="progress">
                    <div class="progress-bar {color_class}" style="width: {rate}%">{rate}%</div>
                </div>
            </div>
            """

    html_content += """
        </div>
    """

    # Daily schedule
    if appointments_by_day:
        html_content += """
        <h2>Daily Schedule</h2>
        """

        # Sort days
        for day, appointments in sorted(appointments_by_day.items()):
            day_name = appointments[0]['day']
            html_content += f"""
            <div class="day-schedule">
                <div class="day-header">
                    <h3>{day_name} ({day})</h3>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Client ID</th>
                            <th>Session Type</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            # Sort appointments by start time
            for appt in sorted(appointments, key=lambda x: x['start_time']):
                session_type = appt['type']
                html_content += f"""
                        <tr class="{session_type}">
                            <td>{appt['start_time']}</td>
                            <td>{appt['end_time']}</td>
                            <td>{appt['client_id']}</td>
                            <td><span class="badge badge-{session_type}">{session_type}</span></td>
                            <td>{appt['duration']} min</td>
                        </tr>
                """

            html_content += """
                    </tbody>
                </table>
            </div>
            """
    else:
        html_content += """
        <div class="empty-message">
            <h2>No appointments scheduled</h2>
            <p>The scheduler was unable to find a valid solution for the given constraints.</p>
        </div>
        """

    # Unscheduled clients
    if unscheduled_clients:
        html_content += """
        <div class="unscheduled">
            <h2>Unscheduled Appointments</h2>
            <p>The following appointments could not be scheduled:</p>
            <table>
                <thead>
                    <tr>
                        <th>Client ID</th>
                        <th>Session Type</th>
                        <th>Priority</th>
                    </tr>
                </thead>
                <tbody>
        """

        for client in sorted(unscheduled_clients, key=lambda x: x['id']):
            html_content += f"""
                    <tr>
                        <td>{client['id']}</td>
                        <td><span class="badge badge-{client['type']}">{client['type']}</span></td>
                        <td>{client['priority']}</td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        </div>
        """

    # Footer
    html_content += """
        <footer>
            <p>Generated by Appointment Scheduler</p>
        </footer>
    </body>
    </html>
    """

    # Write to file
    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"HTML schedule report exported to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Schedule appointments based on constraints and client availability.')
    parser.add_argument('input_file', type=str, help='Path to the input JSON file')
    parser.add_argument('--output', type=str, default='schedule.json', help='Path to the output JSON file')
    parser.add_argument('--html', type=str, default='schedule_report.html', help='Path to the output HTML report file')
    parser.add_argument('--max-street-gap', type=int, default=30,
                        help='Maximum gap in minutes allowed between consecutive street sessions (default: 30)')
    parser.add_argument('--validate-only', action='store_true',
                        help='Validate an existing schedule without generating a new one')
    parser.add_argument('--retries', type=int, default=10,
                        help='Number of retries if validation fails (default: 10)')

    args = parser.parse_args()

    # Get the start date from the input file
    with open(args.input_file, 'r') as f:
        data = json.load(f)
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')

    if args.validate_only:
        # Load existing schedule
        try:
            with open(args.output, 'r') as f:
                existing_schedule = json.load(f)

            # Convert the filled_appointments to our internal format for validation
            appointments = []
            for appt in existing_schedule.get('filled_appointments', []):
                start_time = datetime.fromisoformat(appt['start_time'])
                end_time = datetime.fromisoformat(appt['end_time'])

                appointments.append({
                    'client_id': appt['id'],
                    'type': appt['type'],
                    'day': start_time.strftime('%A'),
                    'date': start_time.strftime('%Y-%m-%d'),
                    'start_time': start_time.strftime('%H:%M'),
                    'end_time': end_time.strftime('%H:%M'),
                    'duration': (end_time - start_time).seconds // 60
                })

            # Load client availabilities from the input file
            client_availabilities = []
            for client in data['appointments']:
                if client['priority'] != "Exclude":
                    client_availabilities.append({
                        'id': client['id'],
                        'type': client['type']
                    })

            # Validate the schedule
            validation_result = validate_schedule(appointments)
            if validation_result["valid"]:
                print("Existing schedule is valid - all constraints are satisfied.")
            else:
                print("\n=== Schedule Validation Failed ===")
                print(f"Found {len(validation_result['violations'])} constraint violations:")

                for i, violation in enumerate(validation_result["violations"], 1):
                    print(f"\nViolation {i}: {violation['constraint']}")
                    print(f"  {violation['description']}")
                    if "expected" in violation and "actual" in violation:
                        print(f"  Expected: {violation['expected']}, Actual: {violation['actual']}")
                    if "details" in violation:
                        print(f"  Details: {violation['details']}")

            return
        except FileNotFoundError:
            print(f"Error: Schedule file '{args.output}' not found. Cannot validate.")
            return
        except json.JSONDecodeError:
            print(f"Error: Schedule file '{args.output}' is not valid JSON. Cannot validate.")
            return

    appointments = None
    validation_result = None
    client_availabilities = None
    # Schedule the appointments with retry logic
    for attempt in range(args.retries):
        appointments, client_availabilities = schedule_appointments(args.input_file, max_street_gap=args.max_street_gap)

        if not appointments:
            print(f"Attempt {attempt + 1}/{args.retries}: Scheduler failed to find a solution")
            continue

        # Validate the schedule
        validation_result = validate_schedule(appointments)

        if validation_result["valid"]:
            print(f"Attempt {attempt + 1}/{args.retries}: Found valid schedule!")
            break
        else:
            print(f"\nAttempt {attempt + 1}/{args.retries}: Schedule validation failed")
            print(f"Found {len(validation_result['violations'])} constraint violations:")

            for i, violation in enumerate(validation_result["violations"], 1):
                print(f"\nViolation {i}: {violation['constraint']}")
                print(f"  {violation['description']}")
                if "expected" in violation and "actual" in violation:
                    print(f"  Expected: {violation['expected']}, Actual: {violation['actual']}")
                if "details" in violation:
                    print(f"  Details: {violation['details']}")

            if attempt < args.retries - 1:
                print(f"\nRetrying... ({attempt + 1}/{args.retries})")

    # Export the schedule (even if invalid after all retries)
    if appointments:
        # Use the new validation-aware export function
        integrate_with_scheduler(appointments, client_availabilities, args.output)
        export_schedule_to_html(appointments, client_availabilities, args.html, start_date)

        # Print a message with links to both files
        print(f"\nExports completed:")
        print(f"- JSON: {args.output}")
        print(f"- HTML Report: {args.html}")

        # Print final validation status
        if not validation_result.get("valid", True):
            print(f"\nWARNING: Final schedule still has {len(validation_result['violations'])} constraint violations")
            print("Review the JSON output for details and consider manual adjustments")
    else:
        print("Failed to generate a valid schedule after all retry attempts")


if __name__ == "__main__":
    main()
