import unittest

from ..get_input_flow import collect_input_from_monday, get_board_data, get_timespans_raw
from ..david_sdk import run_on_file
from ..write_to_monday_flow import write_to_monday
from ..etc_functions import should_rerun, unite_output_from_script
import moday_api_sdk
from ..moday_api_sdk import Client, MondayApi

TESTS_DIR = r'./Calendar_Automation/Tests/'

class IntegrationTests(unittest.TestCase):

    def test_get_board_data(self):
        data = get_timespans_raw()

        names = [d.get('name') for d in data.values()]
        print(names)

        assert data is not None
        assert len(data) > 0

    def test_run_on_file(self):
        """this is a unit test"""
        input_file_name = f"{TESTS_DIR}/Data/input_2025-03-02.json"  # TODO FIX
        data = run_on_file(input_file_name)
        desired_id = '1680614077-1'
        desired_start_time = '2025-03-05T20:45:00'
        desired_end_time = '2025-03-05T22:00:00'

        #print(data)
        assert data is not None
        filled_appointment_data = data['filled_appointments']
        selected_appointment = filled_appointment_data[1]

        assert len(filled_appointment_data) == 5
        assert selected_appointment is not None
        assert selected_appointment['id'] == desired_id
        assert selected_appointment['start_time'] == desired_start_time
        assert selected_appointment['end_time'] == desired_end_time
        assert len(data) > 0


    def test_get_clients(self):
        url = "https://api.monday.com/v2"
        API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"
        BIG_BOARD_ID = 1563336497
        monday_api = moday_api_sdk.MondayApi(api_key=API_KEY, url=url, main_board_id=str(BIG_BOARD_ID))

        clients = monday_api.get_clients()

        yossi: Client = clients[0]
        assert yossi.client_name == 'יוסי איש בדיקות'
        assert yossi.client_id == '1854218826'
        assert yossi.board_id == '1563336497'
        assert yossi.meeting == []

        print(clients)