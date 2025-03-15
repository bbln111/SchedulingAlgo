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
        return (10 * 60, 23 * 60)  # 10:00 to 23:00
    elif day_number == 5:  # Friday
        return (12 * 60 + 30, 17 * 60)  # 12:30 to 17:00
    else:  # Saturday
        return None  # No working hours on Saturday


def schedule_appointments(json_file, max_street_gap=30):
    """Schedule appointments based on constraints and client availability.

    Args:
        json_file (str): Path to the input JSON file
        max_street_gap (int): Maximum gap in minutes allowed between consecutive street sessions
    """
    # Load data from JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)

    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    clients = data['appointments']

    # Print summary of input data
    print(f"\n=== Input Data Summary ===")
    print(f"Start date: {start_date.strftime('%Y-%m-%d')} ({day_number_to_name(start_date.weekday())})")
    print(f"Total clients: {len(clients)}")
    print(f"Maximum gap between street sessions: {max_street_gap} minutes")

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
            print(f"  - Client {client_id}: {session_type} (Priority: {priority}) - Available on {available_days_str}")
        else:
            print(f"  - Client {client_id}: {session_type} (Priority: {priority}) - No availability")

    print("\n=== Starting Scheduler ===")

    # Session type durations
    session_durations = {
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
        session_duration = session_durations[session_type]

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
            day_offset = (day_number - start_date.weekday() + 7) % 7

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

    # Create variables for each client's appointment
    appointment_vars = {}
    appointment_day_vars = {}
    appointment_scheduled_vars = {}

    for client in client_availabilities:
        client_id = client['id']
        session_type = client['type']

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
    street_sessions_by_day = {}  # Keep track of street sessions for each day

    for day in range(7):
        # Skip Saturday
        if day == 6:
            continue

        street_sessions_for_day = []
        street_sessions_by_day[day] = []  # Initialize array to store street session clients for this day

        for client_id, client in [(c['id'], c) for c in client_availabilities]:
            session_type = client['type']

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
                street_sessions_by_day[day].append((client_id, client['duration'], is_scheduled_this_day))

        if street_sessions_for_day:
            # Create a variable to count streets sessions on this day
            street_sessions_per_day[day] = model.NewIntVar(0, len(street_sessions_for_day), f'streets_on_day_{day}')
            model.Add(street_sessions_per_day[day] == sum(street_sessions_for_day))

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
            model.Add(appointment_vars[client1_id] + client1_duration + required_break <= appointment_vars[client2_id]) \
                .OnlyEnforceIf([both_scheduled, client1_before_client2])
            model.Add(appointment_vars[client2_id] + client2_duration + required_break <= appointment_vars[client1_id]) \
                .OnlyEnforceIf([both_scheduled, client2_before_client1])

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
        client_id_int = int(client_id) if client_id.isdigit() else 0
        objective_terms.append(appointment_scheduled_vars[client_id] * priority * 100)  # Weight by priority
        objective_terms.append(
            appointment_scheduled_vars[client_id] * (-client_id_int * 0.1))  # Small preference for lower client IDs

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

    model.Maximize(sum(objective_terms))

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

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
                appointment_date = start_date + timedelta(days=(day_number - start_date.weekday() + 7) % 7)
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
                                if client_data['type'] in ['streets', 'trial_streets'] and appt['type'] in ['streets',
                                                                                                            'trial_streets']:
                                    conflicts.append(
                                        f"Potential street session conflict with Client {appt['client_id']} ({appt['day']} {appt['start_time']})")
                                elif (client_data['type'] in ['streets', 'trial_streets'] and appt['type'] in ['zoom',
                                                                                                               'trial_zoom']) or \
                                        (client_data['type'] in ['zoom', 'trial_zoom'] and appt['type'] in ['streets',
                                                                                                            'trial_streets']):
                                    conflicts.append(
                                        f"Potential streets-zoom transition with Client {appt['client_id']} ({appt['day']} {appt['start_time']})")

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
        return scheduled_appointments
    else:
        print(f"No solution found. Status: {solver.StatusName(status)}")
        return []


def export_schedule_to_json(scheduled_appointments, output_file):
    """Export the scheduled appointments to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(scheduled_appointments, f, indent=2)
    print(f"Schedule exported to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Schedule appointments based on constraints and client availability.')
    parser.add_argument('input_file', type=str, help='Path to the input JSON file')
    parser.add_argument('--output', type=str, default='schedule.json', help='Path to the output JSON file')
    parser.add_argument('--max-street-gap', type=int, default=30,
                        help='Maximum gap in minutes allowed between consecutive street sessions (default: 30)')

    args = parser.parse_args()

    appointments = schedule_appointments(args.input_file, max_street_gap=args.max_street_gap)

    if appointments:
        export_schedule_to_json(appointments, args.output)
