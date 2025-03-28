import datetime
import json
import requests
import logging

logger = logging.getLogger(__name__)

BOARD_ID = 1563336497
url = "https://api.monday.com/v2"
api_key = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"

KEY_DAYS_REQUESTED = 'numeric_mknnxrbp'
DEFAULT_REQUESTED_DAYS = 1
GOT_AVAIlABILITIES_INDEX = 8


#def try_parse_as_date(value: str):
#    try:
#        date_parts = value.strip().split('-')
#        if len(date_parts) != 2:
#            raise ValueError("Invalid date format :: 1")
#
#    except Exception:
#        return False, None

def split_time(time):
    hour, minute = None, None
    time_map = [i for i in map(int, time.split(':'))]
    return time_map[0], time_map[1]



def parse_time(value: str):
    logger.info(value)
    # Remove extra quotes -> "9:00-12:00"
    value_temp = value.strip('"')

    # Split into start/end -> ["9:00", "12:00"]
    start_str, end_str = value_temp.split('-')
    # Parse hours, minutes
    start_hour, start_minute = split_time(start_str)
    end_hour, end_minute = split_time(end_str)

    # Create timedelta objects from midnight
    start_td = datetime.timedelta(hours=start_hour, minutes=start_minute)
    end_td = datetime.timedelta(hours=end_hour, minutes=end_minute)

    return start_td, end_td

def _parse_day(big_dict: dict):
    date = None
    date_string = big_dict.get("date__1", None)
    if date_string is not None:
        temp_data = json.loads(date_string)
        date = temp_data.get("date")
    return date

def _parse_status(big_dict: dict):
    status_as_string = big_dict.get("status")
    if status_as_string is None:
        return None
    date_string = json.loads(status_as_string)
    index = date_string.get("index")
    return index

def _parse_location(big_dict: dict):
    location_as_string = big_dict.get("label_mkn677r1")
    if location_as_string is None:
        return None
    date_string = json.loads(location_as_string)
    index = date_string.get("index")

    locations_by_index = {
        0: "streets",
        3: "zoom",
    }
    if index not in locations_by_index:
        return None
    return locations_by_index[index]

def _get_days(big_dict: dict):
    days = []
    day_counter = None
    for key in big_dict.keys():
        if key == "date__1":
            day_counter = 0

        if day_counter is None:
            continue
        if day_counter == 0:
            day_counter += 1
            continue

        if day_counter > 6:
            continue
        days.append(big_dict[key])

    return days

def _get_requested_days(big_dict: dict):
    request_string = big_dict.get(KEY_DAYS_REQUESTED, None)
    if request_string is None:
        '''if someone forgot to fill requested days'''
        return DEFAULT_REQUESTED_DAYS
    clean_string = request_string.strip("\"").strip("\'")
    if not clean_string.isnumeric():
        return DEFAULT_REQUESTED_DAYS
    request_as_int = int(clean_string)
    return request_as_int

def parse_column_dict(big_dict: dict):
    date = _parse_day(big_dict)
    days_list = _get_days(big_dict)
    has_timespan = len([y for y in days_list if y is not None]) > 0
    requested_amount = _get_requested_days(big_dict)
    location = _parse_location(big_dict)

    return date, days_list, has_timespan, requested_amount, location

def duplicate_client(big_dict: dict, client_id, factor):
    value = big_dict.get(client_id)
    if value is None:
        return
    for i in range(1, factor):
        new_client_id = f'{client_id}-{i}'
        big_dict[new_client_id] = value

def get_board_data():
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    query = f"""
    query GetBoardItems {{
      boards(ids: {BOARD_ID}) {{
        items_page(limit: 40) {{
          items {{
            id
            name
            subitems {{
              id
              name
              column_values {{
                id
                value
              }}
            }}
          }}
        }}
      }}
    }}
    """

    response = requests.post(url, json={"query": query}, headers=headers)
    data = response.json()
    return data

def get_timespans_raw():
    data = get_board_data()
    if "errors" in data:
        logger.error("Errors:", data["errors"])
        exit()

    boards = data.get("data", {}).get("boards", [])
    if not boards:
        logger.error("No boards found.")
        exit()

    save_dictionary = {}
    for board in boards:
        items_page = board.get("items_page", {})
        items = items_page.get("items", [])

        for item in items:
            client_name = item.get("name")
            client_id = item.get("id")
            subitems = item.get("subitems", [])
            for subitem in subitems:
                # Convert column_values to a dict of {column_id: value}
                columns_dict = {
                    col["id"]: col["value"]
                    for col in subitem.get("column_values", [])
                }
                status = _parse_status(columns_dict)
                if status != GOT_AVAIlABILITIES_INDEX:
                    continue

                date, days_list, has_timespan, requested_amount, location = parse_column_dict(columns_dict)
                if location is None:
                    logger.warning(f"No location found for {client_name} : {client_id}. defauling to zoom")
                    location = "zoom"

                from datetime import timedelta
                today_minus_a_week = datetime.datetime.today().date() - timedelta(weeks=1)
                if datetime.datetime.strptime(date, '%Y-%m-%d').date() <= today_minus_a_week:
                    print(client_name, date)
                    continue
                if has_timespan:
                    if not client_id in save_dictionary:
                        save_dictionary[client_id] = {"name": client_name, date: days_list, "requested_amount": requested_amount, "location": location }
                    else:
                        save_dictionary[client_id][date] = days_list
                #duplicate_client(save_dictionary, client_id, requested_amount)
    return save_dictionary

def parse_time_frame(start_date, times_string, day_index):
    if times_string is None:
        return
    logger.info(f"start date: {start_date}, times string: {times_string}, day_index: {day_index}")

    time_delata = datetime.timedelta(days=day_index)
    actual_day = datetime.datetime.strptime(start_date, '%Y-%m-%d') + time_delata
    delta_start, delta_finish = parse_time(times_string)

    final_date_start = actual_day + delta_start
    final_date_end = actual_day + delta_finish

    start_formatted = datetime.datetime.strftime(final_date_start, '%Y-%m-%dT%H:%M:%S')
    end_formatted = datetime.datetime.strftime(final_date_end, '%Y-%m-%dT%H:%M:%S')

    return_dict = {"start": start_formatted, "end": end_formatted}
    return return_dict

def save_to_files(data_dict: dict, file_path: str):
    for start_date in data_dict.keys():
        appointments = data_dict[start_date]
        data_to_file = {"start_date": start_date, "appointments": appointments}
        output_file_name = f"{file_path}_{start_date}.json"
        with open(output_file_name, "w", encoding="utf-8") as f:
            json.dump(data_to_file, f, ensure_ascii=False, indent=2)
        return output_file_name

def try_parse_time(time_as_string):
    formats = ["%H:%M:%S", "%H:%M"]
    for format in formats:
        try:
            ret_date = datetime.datetime.strptime(time_as_string, format)
            return ret_date
        except Exception:
            logger.error(f"Failed to parse {time_as_string}.")
    return None

def authistic_day_list_fix(days_list: list):
    """add here bandages for the bot giving wrong format timespan"""
    ret_list = []
    def shitty_sign(day):
        for _shitty_sign in ["", "-", "\"-\"", "\"\"","\'\'"]:
            if day == _shitty_sign:
                return True
        return False

    for day in days_list[:6]:
        if day is None:
            ret_list.append(None)
            continue
        d = day.strip("\"").strip("\'")
        if shitty_sign(d) :
            ret_list.append(None)
            continue
        elif '-' not in day:
            d = day.strip("\"").strip("\'")
            time_a = try_parse_time(d)
            if time_a is None:
                continue
            #time_a = datetime.datetime.strptime(d, "%H:%M:%S")
            time_b = time_a + datetime.timedelta(hours=2)
            span_as_string = f"{time_a.strftime('%H:%M:%S')}-{time_b.strftime('%H:%M:%S')}"
            ret_list.append(span_as_string)
            continue
        else:
            d = day.strip("\"").strip("\'")
            ret_list.append(d)
            continue
    logger.info(ret_list)
    return ret_list

def convent_to_input_file_format(monday_dict: dict):
    return_dict = {}
    DAYS_OF_WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for key in monday_dict.keys():
        id = key #int(key)
        priority = "High"
        type__r = "zoom"
        time = 60
        raw_dict = dict(monday_dict[key])

        name, start_date, days_list = None, None, None



        for key in raw_dict.keys():
            if key is None:
                continue
            elif key == "name":
                name  = raw_dict.get(key)
            elif key == "requested_amount":
                requested_amount = raw_dict.get(key)
            elif key == "location":
                location = raw_dict.get(key)
            else:
                start_date = key
                days_list = raw_dict[key]

        if days_list is None: # כפיר מוכתרי
            continue
        logger.info(f"name: {name} \t start_date: {start_date} \t days_list: {days_list} \t requested_amount: {requested_amount}, location: {location}")
        fixed_days_list = authistic_day_list_fix(days_list)
        logger.info(f"fixed_days_list: {fixed_days_list}")

        days = [
            {
                "day": day,
                "time_frames": [parse_time_frame(start_date, fixed_days_list[index], index)]
            }
            for index, day in enumerate(DAYS_OF_WEEK)
        ]
        for test in days:
            test_time_frame = test["time_frames"]
            if test_time_frame[0] is None:
                test_time_frame.pop(0)

        appointment = {"id": id, "priority": priority, "type": location, "time": time, "requested_amount": requested_amount, "days": days}
        if start_date in return_dict:
            return_dict[start_date].append(appointment)
        else:
            return_dict[start_date] = [appointment]


        logger.info(return_dict)


    return return_dict

def filter_out_empty_entries(data_dict: dict):
    for date in data_dict.keys():
        data_for_date: list = data_dict[date]
        values_to_keep = []
        for obj in data_for_date:
            days = obj["days"]
            flag_keep = False
            for day_data in days:
                day_time_frame = day_data["time_frames"]
                if len(day_time_frame) > 0:
                    flag_keep = True
            if flag_keep:
                values_to_keep.append(obj)

        data_dict[date] = values_to_keep
    return data_dict

def collect_input_from_monday(input_file):
    logger.info("starting to collect input from monday")
    raw_dict = get_timespans_raw()
    logger.info("formatting timespans")
    formatted_dict = convent_to_input_file_format(raw_dict)
    logger.info("formatting filtering")
    filtered_dict = filter_out_empty_entries(formatted_dict)
    logger.info("formatting finished")
    output_file = save_to_files(filtered_dict, input_file)
    logger.info(f"saved to file {output_file}")
    return output_file


if __name__ == "__main__":
    collect_input_from_monday(f"input_from_monday/input")
