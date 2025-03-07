import datetime
import json

start_day = "2025-02-16"
times = ['"9:00-12:00"', None, None, None, None, None, None]



import requests
BOARD_ID = 1563336497

url = "https://api.monday.com/v2"

api_key = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"

def try_parse_as_date(value: str):
    try:
        date_parts = value.strip().split('-')
        if len(date_parts) != 2:
            raise ValueError("Invalid date format :: 1")

    except Exception:
        return False, None


def parse_time(value: str):
    # Remove extra quotes -> "9:00-12:00"
    value_temp = value.strip('"')

    # Split into start/end -> ["9:00", "12:00"]
    start_str, end_str = value_temp.split('-')

    # Parse hours, minutes
    start_hour, start_minute = map(int, start_str.split(':'))
    end_hour, end_minute = map(int, end_str.split(':'))

    # Create timedelta objects from midnight
    start_td = datetime.timedelta(hours=start_hour, minutes=start_minute)
    end_td = datetime.timedelta(hours=end_hour, minutes=end_minute)

    return start_td, end_td



#parse_time('"9:00-12:00"')



def _parse_day(big_dict: dict):
    date = None
    date_string = big_dict.get("date__1", None)
    if date_string is not None:
        temp_data = json.loads(date_string)
        date = temp_data.get("date")
    return date

def _parse_status(big_dict: dict):
    status_as_string = big_dict.get("status")
    date_string = json.loads(status_as_string)
    index = date_string.get("index")
    return index

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

def parse_column_dict(big_dict: dict):
    date = _parse_day(big_dict)
    days_list = _get_days(big_dict)
    has_timespan = len([y for y in days_list if y is not None]) > 0

    return date, days_list, has_timespan


def get_timespans_raw():
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    query = f"""
    query GetBoardItems {{
      boards(ids: {BOARD_ID}) {{
        items_page(limit: 20) {{
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

    if "errors" in data:
        print("Errors:", data["errors"])
        exit()

    boards = data.get("data", {}).get("boards", [])
    if not boards:
        print("No boards found.")
        exit()

    save_dictionary = {}
    for board in boards:
        items_page = board.get("items_page", {})
        items = items_page.get("items", [])

        for item in items:
            client_name = item.get("name")
            client_id = item.get("id")
            found_day_flag = False
            start_date = None
            subitems = item.get("subitems", [])
            for subitem in subitems:
                # Convert column_values to a dict of {column_id: value}
                columns_dict = {
                    col["id"]: col["value"]
                    for col in subitem.get("column_values", [])
                }
                status = _parse_status(columns_dict)
                if status == 1:
                    continue

                date, days_list, has_timespan = parse_column_dict(columns_dict)

                if has_timespan:
                    if not client_id in save_dictionary:
                        save_dictionary[client_id] = {"name": client_name, date: days_list }
                    else:
                        save_dictionary[client_id][date] = days_list
    return save_dictionary



x = get_timespans_raw()

def _day_input_converter(day_index, start_day, start_hour, end_hour):
    actual_day = datetime.convert(start_day) + datetime.datetime.day(day_index)

def parse_time_frame(start_date, times_string, day_index):
    if times_string is None:
        return
    time_delata = datetime.timedelta(days=day_index)
    actual_day = datetime.datetime.strptime(start_date, '%Y-%m-%d') + time_delata
    delta_start, delta_finish = parse_time(times_string)

    final_date_start = actual_day + delta_start
    final_date_end = actual_day + delta_finish

    start_formatted = datetime.datetime.strftime(final_date_start, '%Y-%m-%dT%H:%M:%S')
    end_formatted = datetime.datetime.strftime(final_date_end, '%Y-%m-%dT%H:%M:%S')

    return_dict = {"start": start_formatted, "end": end_formatted}
    y =  str(return_dict)
    return return_dict

import os

def save_to_files(data_dict: dict):
    for start_date in data_dict.keys():
        appointments = data_dict[start_date]
        data_to_file = {"start_date": start_date, "appointments": appointments}
        with open(f"input_from_monday/output_{start_date}.json", "w", encoding="utf-8") as f:
            json.dump(data_to_file, f, ensure_ascii=False, indent=2)

def convent_to_input_file_format(monday_dict: dict):
    return_dict = {}
    DAYS_OF_WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for key in monday_dict.keys():
        id = int(key)
        priority = "High"
        type__r = "zoom"
        time = 60
        raw_dict = dict(monday_dict[key])

        name, start_date, days_list = None, None, None

        for key in raw_dict.keys():
            if key == "name":
                name  = raw_dict.get(key)
            else:
                start_date = key
                days_list = raw_dict[key]
        days = [
            {
                "day": day,
                "time_frames": [parse_time_frame(start_date, days_list[index], index)]
            }
            for index, day in enumerate(DAYS_OF_WEEK)
            #if days_list[index] is not None
        ]
        for test in days:
            test_time_frame = test["time_frames"]
            if test_time_frame[0] is None:
                test_time_frame.pop(0)
            else:
                #temp_time_frames = [x for x in test_time_frame]
                #test["time_frames"] = temp_time_frames
                pass

        appointment = {"id": id, "priority": priority, "type": type__r, "time": time, "days": days}
        if start_date in return_dict:
            return_dict[start_date].append(appointment)
        else:
            return_dict[start_date] = [appointment]


        print(return_dict)

    return return_dict


save_to_files(convent_to_input_file_format(x))


