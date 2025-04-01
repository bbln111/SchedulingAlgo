from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
from datetime import datetime, timedelta, date

# If modifying these SCOPES, delete token.json
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def parse_time(time):
    pass

def is_in_next_sunday(dt: datetime) -> bool:
    today = date.today()
    # Find next Sunday
    days_ahead = (6 - today.weekday()) % 7
    days_ahead = 7 if days_ahead == 0 else days_ahead
    next_sunday = today + timedelta(days=days_ahead)
    next_next_sunday = next_sunday + timedelta(days=7)
    subject_date = datetime.fromisoformat(dt).date()

    a = next_sunday <= subject_date
    b = subject_date <= next_next_sunday
    return next_sunday <= subject_date <= next_next_sunday

def _get_meetings_from_google_calendar():
    creds = None
    # Load saved token
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid token, go through OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Calendar API service
    service = build('calendar', 'v3', credentials=creds)

    # Get upcoming 10 events
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=100, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        print("No upcoming events.")
    ret_list = []
    for event in events:

        start = event['start'].get('dateTime', event['start'].get('date'))
        if not is_in_next_sunday(start):
            continue
        end = event['end'].get('dateTime', event['end'].get('date'))
        x = start.split('+')
        ret_list.append({'start':start.split('+')[0], 'end':end.split('+')[0]})

    return ret_list


def _filter_duplicated(start_list):
     ret_list = []
     for item1 in start_list:
         if item1 in ret_list:
             continue
         ret_list.append(item1)
     return ret_list



def get_meetings_from_google_calendar():
    raw_list = _get_meetings_from_google_calendar()
    filtered_list = _filter_duplicated(raw_list)
    return filtered_list

def main():
    ret_list = get_meetings_from_google_calendar()

if __name__ == '__main__':
    main()
