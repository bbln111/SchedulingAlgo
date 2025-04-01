import json
import sys
import moday_api_sdk
import logging
from datetime import datetime as datetime_
from moday_api_sdk import Client, MondayApi
from constants import  MONDAY_URL, MONDAY_API_KEY ,MONDAY_BOARD_ID, DATE_KEY, TIME_KEY, STATUS_KEY, STATUS_VALUE_SCHEDULED

logger = logging.getLogger(__name__)

BIG_BOARD_ID = MONDAY_BOARD_ID
url = MONDAY_URL
API_KEY = MONDAY_API_KEY
MondayApi = (
    MondayApi(api_key=API_KEY, url=url, main_board_id=BIG_BOARD_ID))
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

    sorted_appointments = sort_appointment_by_client(appointments)

    for client_id in sorted_appointments.keys():
        client_appointment = sorted_appointments[client_id]
        update_client_appointments(client_id, client_appointment, monday_api)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_input_file>")
        sys.exit(1)
    input_file = sys.argv[1]

    with open(input_file, "r") as file:
        input_data = json.load(file)

    write_to_monday(input_data)
