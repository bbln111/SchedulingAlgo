import json
import sys
import moday_api_sdk
import logging
from datetime import datetime as datetime_
from moday_api_sdk import Client, MondayApi

logger = logging.getLogger(__name__)

DATE_KEY = 'date0'
TIME_KEY = 'hour__1'
STATUS_KEY = 'status'
STATUS_VALUE_SCHEDULED = 'אלגוריתם שיבץ'
BIG_BOARD_ID = 1563336497
url = "https://api.monday.com/v2"
API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"
MondayApi = MondayApi(api_key=API_KEY, url=url, main_board_id=BIG_BOARD_ID)
headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}


def get_query_for_client(board_id, item_id, column_id, value):
    query = f"""
    mutation {{
      change_column_value (
        board_id: {board_id},
        item_id: {item_id},
        column_id: "{column_id}",
        value: "{value}"
      ) {{
        id
      }}
    }}
    """
    return query




'''
def _update_date_from_client2(board_id, client_id, value):
    # Validate the input date format
    try:
        date_value = datetime_.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {value}. Expected format: YYYY-MM-DD")

    # Create the JSON object for GraphQL `value`
    formatted_value = {
        "date": str(date_value),  # "YYYY-MM-DD"
        "time": "00:00:00"
    }

    # Convert to a properly escaped string for GraphQL
    json_payload = json.dumps(formatted_value)  # Correctly formats and escapes JSON

    # Call the function with properly formatted JSON
    return _update_meeting_for_client(board_id, client_id, DATE_KEY, json_payload)
'''

def _update_date_from_client(board_id, client_id, value):
    return_code = _update_meeting_for_client(board_id, client_id, DATE_KEY, f"{{\\\"date\\\": \\\"{value}\\\"}}")
    #return_code = _update_meeting_for_client(board_id, client_id, DATE_KEY, f"{{\\\"date\\\": \\\"{value}\\\", \\\"time\\\": \\\"00:00:00\\\"}}")
    return return_code

def _update_time_from_client(board_id, client_id, value):
    dt = datetime_.strptime(value, "%H:%M:%S")
    value_transformed = f"{{\\\"hour\\\":{dt.hour},\\\"minute\\\":{dt.minute}}}"
    return_code = _update_meeting_for_client(board_id, client_id, TIME_KEY, value_transformed)
    return return_code

def _reset_column_value(board_id, client_id, time: bool, date:bool):
    value = "{}"
    if time:
        return_code_time = _update_meeting_for_client(board_id, client_id, TIME_KEY, value)
    if date:
        return_code_date = _update_meeting_for_client(board_id, client_id, DATE_KEY, value)
    return return_code_time, return_code_date

def _update_status_from_client(board_id, client_id, value):
    enum_value = -1
    if value == STATUS_VALUE_SCHEDULED:
        enum_value = 11

    value_transformed = f"{{\\\"index\\\":\\\"{enum_value}\\\"}}"
    return_code = _update_meeting_for_client(board_id, client_id, STATUS_KEY, value_transformed)
    return return_code

def _update_status_from_client_slim(board_id, client_id, value):
    value_transformed = f"{{\\\"index\\\":\\\"{value}\\\"}}"
    return_code = _update_meeting_for_client(board_id, client_id, STATUS_KEY, value_transformed)
    return return_code

def update_client_meeting(board_id, client_id, date, time):
    pass
    res_date, res_time = None, None
    try:
        res_date = _update_date_from_client(board_id, client_id, date)
        res_time = _update_time_from_client(board_id, client_id, time)
        res_status = _update_status_from_client(board_id, client_id, STATUS_VALUE_SCHEDULED)
    except Exception as error:
        logger.error("failed updating clinet {client_id}, date_query_result:{res_date} time_query_result:{res_time}, status_query_result:{res_status}" ,error)


def _parse_filled_appointment(appointment):
    #end_time = appointment.get("end_time")
    #type_ = appointment.get("type")

    client_id = appointment.get("id")
    start_time = appointment.get("start_time")
    start_time_parsed = datetime_.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    date = str(start_time_parsed.date())
    time = str(start_time_parsed.time())

    return date, time, client_id

def _get_appointments(data):
    appointments = []
    for d in data:#['filled_appointments']:
        appointments.append(_parse_filled_appointment(d))
    return appointments



def _update_meeting_for_client(board_id, item_id, column_id, value):
    q = get_query_for_client(board_id, item_id, column_id, value)
    logger.info(f"query: {q}")

    response = MondayApi.send_query_post(q)
    return response.status_code

def find_client_with_id(client_id, clients):
    logger.info(client_id)
    for client in clients:
        if client.client_id == client_id:
            return client
    raise ValueError("Client not found")

def find_meeting_with_date(client: Client, date):
    for meeting in client.meeting:
        if meeting.date == date:
            return meeting
    raise ValueError("Meeting not found")

def update_client_appointments(client_id, appointments: list, monday_api):
    client_meetings = monday_api.get_meetings(client_id)

    for appointment in appointments:
        if client_meetings == []:
            return
        meeting = client_meetings.pop(0)

        date, time = appointment[0], appointment[1]
        update_client_meeting(meeting.board_id, meeting.id, date, time)


def sort_appointment_by_client(appointments):
    ret_dict = {client_id : [] for _, _, client_id in appointments}
    for date, time, client_id in appointments:
        ret_dict[client_id].append((date, time))

    return ret_dict


def write_to_monday(data):
    appointments = _get_appointments(data)

    monday_api = moday_api_sdk.MondayApi(api_key=API_KEY, url=url, main_board_id=str(BIG_BOARD_ID))
    clients = monday_api.get_clients()

    sorted_appointments = sort_appointment_by_client(appointments)

    for client_id in sorted_appointments.keys():
        client_appointment = sorted_appointments[client_id]
        update_client_appointments(client_id, client_appointment, monday_api)


    #for date, time, client_id in appointments:
    #    client = find_client_with_id(str(client_id), clients) # TODO change client_id to string
    #    meeting = find_meeting_with_date(client, date)
    #    meeting_board_id = meeting.board_id
    #    client_meetings = monday_api.get_meetings(client_id)
#
    #    update_client_meeting(meeting_board_id, meeting.id, date, time)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_input_file>")
        sys.exit(1)
    input_file = sys.argv[1]

    with open(input_file, "r") as file:
        input_data = json.load(file)

    write_to_monday(input_data)
