import datetime
import os.path
import pickle
from pprint import pprint

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def upload(data, sheet_id):
    """Uploads data to a google sheet.  The only public method."""
    arr = [[None, None, None, 'Last updated:', str(datetime.datetime.utcnow())],
           ['id', 'username', 'nicknames', 'xp roll', 'warnings', 'joined', 'first message', 'messages this month',
            'total messages', 'off-topic messages', 'xp roll position', 'earliest']]
    for uid in data:
        row = data[uid]
        # we have to stringify the user id, because otherwise it goes into big E notation cuz it's a big number
        arr.append(("'" + str(uid),) + row)
    print('built array')

    range_ = 'Raw!A1:M'
    service = build('sheets', 'v4', credentials=_get_creds())

    # clear the current sheet contents and upload our new data over it
    sheet = service.spreadsheets()
    sheet.values().clear(spreadsheetId=sheet_id, range=range_).execute()
    response = sheet.values().update(spreadsheetId=sheet_id,
                                     range=range_,
                                     valueInputOption='USER_ENTERED',
                                     body={'values': arr}).execute()
    pprint(response)


def _get_creds():
    """Get the google login credentials to do stuff.  This may take you to a login page or something."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('config/sheets_token.pickle'):
        with open('config/sheets_token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # If modifying these scopes, delete the file token.pickle.
            flow = InstalledAppFlow.from_client_secrets_file(
                'config/sheets_credentials.json', ['https://www.googleapis.com/auth/spreadsheets'])
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('config/sheets_token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


"""
def _make_data():
    ""Create dummy data to upload""
    from commandcogs import gsheets
    dummy = gsheets.Sheet()
    guy = gsheets.Member()
    guy.nickname = 'nicky'
    guy.username = 'Guy#2134'
    guy.joined = datetime.datetime.now()
    guy.messages_month = 123
    guy.messages_total = 3456
    guy.warnings = 0
    guy.xp_roll = 'Rocky Planet'

    gal = gsheets.Member()
    gal.nickname = 'nickyyyy!'
    gal.username = 'gal#2134'
    gal.joined = datetime.datetime.now()
    gal.messages_month = 3455
    gal.messages_total = 345677
    gal.warnings = 1
    gal.xp_roll = 'Universe'

    dummy.members[234556] = guy
    dummy.members[786543] = gal
    return dummy


if __name__ == '__main__':
    upload(_make_data(), '1-mIvOjygL86oalj2AE8le5wGNb0WvPXazKiu3rTL16U')
"""
