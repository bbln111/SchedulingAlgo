

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Define the scopes your application will use
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def connect_to_google_calendar():
    creds = None

    # Token file stores the user's access and refresh tokens
    token_file = 'config/credentials.json'

    # Load credentials from the token file, if it exists
    try:
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    except Exception:
        pass

    # If there are no valid credentials, start the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'config/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    # Connect to the Google Calendar API
    try:
        service = build('calendar', 'v3', credentials=creds)
        print("Successfully connected to Google Calendar!")

        # Fetch the next 5 events from the primary calendar
        events_result = service.events().list(
            calendarId='primary',
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        # Print the upcoming events
        if not events:
            print('No upcoming events found.')
        else:
            print('Upcoming events:')
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"{start} - {event['summary']}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    flow = InstalledAppFlow.from_client_secrets_file(
        'config/credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    print(">_<")
    connect_to_google_calendar()

"""258843329048-6h6gkvvfco5poidslgm99jirh0nqsq81.apps.googleusercontent.com"""
#flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)