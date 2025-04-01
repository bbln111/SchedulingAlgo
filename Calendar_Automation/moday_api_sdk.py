import json
import datetime
import requests
from constants import MONDAY_URL, MONDAY_API_KEY
BOARD_ID = 1563336497

url = MONDAY_URL
API_KEY = MONDAY_API_KEY


class ParserFriend:
    def __init__(self):
        pass
    @staticmethod
    def try_parse_as_date(value: str):
        try:
            date_parts = value.strip().split('-')
            if len(date_parts) != 2:
                raise ValueError("Invalid date format :: 1")

        except Exception:
            return False, None

    @staticmethod
    def parse_time(value: str):
        value_temp = value.strip('"')
        start_str, end_str = value_temp.split('-')

        start_hour, start_minute = map(int, start_str.split(':'))
        end_hour, end_minute = map(int, end_str.split(':'))

        start_td = datetime.timedelta(hours=start_hour, minutes=start_minute)
        end_td = datetime.timedelta(hours=end_hour, minutes=end_minute)

        return start_td, end_td

    @staticmethod
    def _parse_day(big_dict: dict):
        date = None
        date_string = big_dict.get("date__1", None)
        if date_string is not None:
            temp_data = json.loads(date_string)
            date = temp_data.get("date")
        return date

    @staticmethod
    def _parse_status(big_dict: dict):
        status_as_string = big_dict.get("status")
        date_string = json.loads(status_as_string)
        index = date_string.get("index")
        return index

    @staticmethod
    def _parse_status_as_text(big_dict: dict):
        status_as_string = big_dict.get("status")
        #date_string = json.loads(status_as_string)
        #text = date_string.get("text")
        #return text
        return  status_as_string

    @staticmethod
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

    @staticmethod
    def parse_column_dict(big_dict: dict):
        date = ParserFriend._parse_day(big_dict)
        days_list = ParserFriend._get_days(big_dict)
        has_timespan = len([y for y in days_list if y is not None]) > 0

        return date, days_list, has_timespan

    @staticmethod
    def get_timespans_raw():
        headers = {
            "Authorization": API_KEY,
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
                    status = ParserFriend._parse_status(columns_dict)
                    if status == 1:
                        continue

                    date, days_list, has_timespan = ParserFriend.parse_column_dict(columns_dict)

                    if has_timespan:
                        if not client_id in save_dictionary:
                            save_dictionary[client_id] = {"name": client_name, date: days_list }
                        else:
                            save_dictionary[client_id][date] = days_list
        return save_dictionary




class MondayUtils:
    def __init__(self):
        pass
    @staticmethod
    def get_headers(api_key):
        return {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    @staticmethod
    def get_items_from_board(board):
        items_page = board.get("items_page", {})
        items = items_page.get("items", [])
        clients = []
        for item in items:
            client_name = item.get("name")
            client_id = item.get("id")
            client_board_id = item.get("board").get("id")
            client_meetings = []

            subitems = item.get("subitems", [])
            for subitem in subitems:
                # Convert column_values to a dict of {column_id: value}
                columns_dict = {
                    col["id"]: col["value"]
                    for col in subitem.get("column_values", [])
                }
                status = ParserFriend._parse_status(columns_dict)
                if status == 1:
                    continue
                meeting_id = subitem.get("id")
                meeting_board_id = subitem.get("board").get("id")
                meeting_column_values = subitem.get("column_values", {})

                date, days_list, has_timespan = ParserFriend.parse_column_dict(columns_dict)
                shortened_days_list = days_list[:6]
                if has_timespan:
                    for index, time in enumerate(shortened_days_list):
                        if time is None:
                            continue
                        clean_time = time.strip('\'').strip('\"').split("-")[0]
                        real_date = datetime.datetime.strptime(date, "%Y-%m-%d") + datetime.timedelta(days=index)
                        real_real_date = str(real_date.date())
                        meeting = Meeting(meeting_id, meeting_board_id, real_real_date, clean_time, meeting_column_values)
                        client_meetings.append(meeting)

            client = Client(client_id, client_name, client_meetings, client_board_id)
            clients.append(client)

        return clients

    @staticmethod
    def get_next_meetings_for_client(board, client_id_):
        items_page = board.get("items_page", {})
        items = items_page.get("items", [])
        for item in items:
            client_name = item.get("name")
            client_id = item.get("id")
            if client_id != client_id_:
                continue

            next_meetings = []
            subitems = item.get("subitems", [])
            for subitem in subitems:
                FILLED_APPOITEMENT_VALUE = 'תואם'
                DONE_APPOITEMENT_VALUE = 'בוצע'
                ALGORITHM_FILLED = 'אלגוריתם שיבץ'
                # Convert column_values to a dict of {column_id: value}
                columns_dict = {
                    col["id"]: col["text"]
                    for col in subitem.get("column_values", [])
                }
                status = ParserFriend._parse_status_as_text(columns_dict)
                if status == DONE_APPOITEMENT_VALUE:
                    continue
                if status == FILLED_APPOITEMENT_VALUE:
                    continue
                if status == ALGORITHM_FILLED:
                    continue

                meeting_id = subitem.get("id")
                meeting_board_id = subitem.get("board").get("id")
                meeting_column_values = subitem.get("column_values", {})
                next_meeting = Meeting(meeting_id, meeting_board_id, None, None, meeting_column_values)
                next_meetings.append(next_meeting)

            return next_meetings

class Meeting:
    def __init__(self, id: str, board_id: str, date: str, time:str,  column_values: dict):
        self.id = id
        self.board_id = board_id
        self.date = date
        self.time = time
        self.column_values = column_values

    def is_done(self):
        is_done = self.column_values.get("status")

class Client:
    def __init__(self, client_id: str, client_name: str, meeting: list[Meeting], board_id: str):
        self.client_id = client_id
        self.client_name = client_name
        self.meeting = meeting
        self.board_id = board_id

class MondayApi:
    def __init__(self, api_key:str, url: str, main_board_id:str):
        self.api_key = api_key
        self.url = url
        self.main_board_id = main_board_id
        self._headers = {
            "Authorization": API_KEY,
            "Content-Type": "application/json"
        }
        self.cache = None


    def _get_board(self):
        headers = {
            "Authorization": API_KEY,
            "Content-Type": "application/json"
        }

        query = f"""
                query GetBoardItems {{
                  boards(ids: {BOARD_ID}) {{
                    items_page {{
                      items {{
                        id
                        name
                        board {{
                            id
                        }}
                        subitems {{
                          id
                          name
                          board {{
                            id
                          }}
                          column_values {{
                            id
                            text
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
        if not len(boards) != 1:
            print("More than one board found.")
        board = boards[0]
        return board

    def _get_board_cached(self):
        if self.cache is None:
            self.cache = self._get_board()
        return self.cache

    def get_clients(self):
        board = self._get_board_cached()
        return MondayUtils.get_items_from_board(board)

    def get_meetings(self, client_id):
        board = self._get_board_cached()
        return MondayUtils.get_next_meetings_for_client(board, client_id)

    def _get_headers(self):
        return {
            "Authorization": API_KEY,
            "Content-Type": "application/json"
        }

    def send_query_post(self, query):
        headers = self._get_headers()
        response = requests.post(url, json={"query": query}, headers=headers)
        return response
