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
    filled_appointments = big_dict['filled_appointments']
    clients = {}
    for appointment in filled_appointments:
        id = appointment['id']
        start = appointment['start_time']
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

def unite_output_from_script(appointments):
    for appointment in appointments:
        id = appointment['id']
        real_id = None
        if '-' in id:
            real_id = id.split('-')[0]
        else:
            real_id = id
        appointment['id'] = real_id

    return appointments