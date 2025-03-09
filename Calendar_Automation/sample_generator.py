from datetime import datetime, timedelta
import random
import json
import logging

logger = logging.getLogger(__name__)


def generate_sample_input(output_file, start_date=None, num_clients=5, days_range=5):
    """Generate sample input file for testing the scheduling algorithm"""
    if start_date is None:
        start_date = datetime.now().strftime('%Y-%m-%d')

    # Generate random client IDs
    client_ids = [f"test_client_{i}" for i in range(1, num_clients + 1)]

    # Define appointment types
    types = ["zoom", "streets", "field", "trial_zoom", "trial_streets"]
    priorities = ["High", "Medium", "Low"]

    # Time slots (in 15-minute increments from 9 AM to 5 PM)
    time_slots = []
    for hour in range(9, 17):
        for minute in [0, 15, 30, 45]:
            time_slots.append(f"{hour:02d}:{minute:02d}:00")

    # Generate appointments
    appointments = []
    for client_id in client_ids:
        # Randomly select appointment type and priority
        app_type = random.choice(types)
        priority = random.choice(priorities)

        # Set appointment length based on type
        if "trial" in app_type:
            app_length = 120
        else:
            app_length = 60

        # Generate random available days
        days_data = []
        for day_index in range(days_range):
            # Skip some days randomly
            if random.random() < 0.3:
                continue

            day_name = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][day_index]

            # Generate 1-3 time frames for this day
            num_timeframes = random.randint(1, 3)
            time_frames = []

            for _ in range(num_timeframes):
                # Pick a random start time
                start_idx = random.randint(0, len(time_slots) - 5)  # Leave room for appointment length
                start_time = time_slots[start_idx]

                # Calculate end time (adding some buffer)
                start_dt = datetime.strptime(f"{start_date}T{start_time}", "%Y-%m-%dT%H:%M:%S")

                # Add appointment length + buffer
                buffer = random.randint(1, 4) * 15  # 15-60 minute buffer
                end_dt = start_dt + timedelta(minutes=app_length + buffer)

                # Format as ISO string
                day_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day_index)
                start_iso = day_dt.replace(
                    hour=start_dt.hour,
                    minute=start_dt.minute
                ).isoformat()

                end_iso = day_dt.replace(
                    hour=end_dt.hour,
                    minute=end_dt.minute
                ).isoformat()

                time_frames.append({
                    "start": start_iso,
                    "end": end_iso
                })

            days_data.append({
                "day": day_name,
                "time_frames": time_frames
            })

        # Only add if we have at least one day with time frames
        if days_data:
            appointments.append({
                "id": client_id,
                "priority": priority,
                "type": app_type,
                "time": app_length,
                "days": days_data
            })

    # Create final structure
    data = {
        "start_date": start_date,
        "appointments": appointments
    }

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Generated sample input with {len(appointments)} appointments")
    return output_file
