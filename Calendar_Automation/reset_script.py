import json
from get_input_flow import get_timespans_raw
from moday_api_sdk import  MondayApi
from write_to_monday_flow import _update_status_from_client_slim, _reset_column_value

START_STATUS = 11
FINISH_STATUS_FIRST = 8
FINISH_STATUS_OTHERS = 2

def _reset_subitem_status(subitem, is_first_reset):
    board_id = subitem.get('board').get('id')
    item_id = subitem.get('id')

    if is_first_reset:
        status = FINISH_STATUS_FIRST
    else:
        status = FINISH_STATUS_OTHERS

    return_code_status = _update_status_from_client_slim(board_id, item_id, status)
    return_code_time, return_code_date = _reset_column_value(board_id, item_id, time=True, date=True)
    return return_code_status, return_code_time, return_code_date

def _should_reset(status):
    return str(status) == str(START_STATUS)


def _get_status(subitem):
    column_values = subitem.get('column_values')
    for cv in column_values:
        if cv.get('id') == 'status':
            value = cv.get('value')
            x = json.loads(value)
            index = x.get('index')

            return index

def _run_on_subitem(subitem):
    status = _get_status(subitem)
    should_reset = _should_reset(status)
    print(should_reset)
    return should_reset



def _run_on_item(item_dict):
    subitems = item_dict.get('subitems')
    is_first_reset = True
    for subitem in subitems:
        should_reset = _run_on_subitem(subitem)
        if should_reset:
            _reset_subitem_status(subitem, is_first_reset)

            is_first_reset = False




def _extract_items(board: dict) -> list:
    return board.get('items_page').get('items')


def main():
    print("hola")
    url = "https://api.monday.com/v2"
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQzNDY0NDY5OCwiYWFpIjoxMSwidWlkIjo2MzQ0MzI4MCwiaWFkIjoiMjAyNC0xMS0xMFQwOTo0MzoxNi4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MjQ0MTMxODUsInJnbiI6ImV1YzEifQ.EjiCaRi_3RiHpQIH8SXCIiowwuqc1QbVNjyHZMK6who"
    BIG_BOARD_ID = 1563336497
    monday_api = MondayApi(api_key=API_KEY, url=url, main_board_id=BIG_BOARD_ID)
    y = monday_api._get_board()
    x= get_timespans_raw()
    items = _extract_items(y)
    for item in items:
        _run_on_item(item)
    print(y)


if __name__ == "__main__":
    main()
