import datetime


def _is_faulty_client(dates):
    counter = {}
    for date in dates:
        real_date = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
        counter[real_date] = counter.get(real_date, 0) + 1

    for x in counter.values():
        if x > 1:
            return False
    return True


def should_rerun(big_dict):
    filled_appointments = big_dict.get('filled_appointments', [])
    clients = {}
    for appointment in filled_appointments:
        id = appointment.get('id', '')
        start = appointment.get('start_time', '')
        real_id = None
        if '-' in id:
            real_id = id.split('-')[0]
        else:
            real_id = id

        if real_id not in clients:
            clients[real_id] = []
        clients[real_id].append(start)

    dates_list_of_lists = clients.values()
    for date_list in dates_list_of_lists:
        if _is_faulty_client(date_list):
            return True

    return False


def unite_output_from_script(output_dict):
    """
    Fix appointment IDs in the output dictionary
    """
    result = output_dict.copy()  # Create a copy to avoid modifying the original

    # Process filled appointments
    filled_appointments = result.get('filled_appointments', [])
    for appointment in filled_appointments:
        appointment_id = appointment.get('id', '')
        if '-' in appointment_id:
            real_id = appointment_id.split('-')[0]
            appointment['id'] = real_id

    # Also process unfilled appointments
    unfilled_appointments = result.get('unfilled_appointments', [])
    for appointment in unfilled_appointments:
        appointment_id = appointment.get('id', '')
        if '-' in appointment_id:
            real_id = appointment_id.split('-')[0]
            appointment['id'] = real_id

    return result
