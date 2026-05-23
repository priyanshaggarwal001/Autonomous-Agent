import os
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from sqlalchemy.orm import Session
from ..models.token import GoogleToken

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

class GoogleService:
    def __init__(self, db: Session = None):
        self.db = db
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("REDIRECT_URI")
        
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_auth_url(self):
        import urllib.parse
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent"
        }
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def fetch_token(self, code: str):
        import requests
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        response = requests.post(token_url, data=data)
        token_data = response.json()
        
        if "error" in token_data:
            raise Exception(f"Token exchange failed: {token_data.get('error_description', token_data['error'])}")

        # Add client info needed by the library for refreshing/validation
        token_data['client_id'] = self.client_id
        token_data['client_secret'] = self.client_secret

        # Create credentials for user info
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info['email']
        
        # Save to DB
        token_entry = self.db.query(GoogleToken).filter(GoogleToken.user_email == user_email).first()
        if not token_entry:
            token_entry = GoogleToken(user_email=user_email)
            self.db.add(token_entry)
        
        token_entry.token_data = token_data
        self.db.commit()
        return user_email

    def login_cli(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        # Adjust config for desktop apps
        cli_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        
        flow = InstalledAppFlow.from_client_config(cli_config, SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Get user info
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        user_email = user_info['email']
        
        # Save to DB
        token_entry = self.db.query(GoogleToken).filter(GoogleToken.user_email == user_email).first()
        if not token_entry:
            token_entry = GoogleToken(user_email=user_email)
            self.db.add(token_entry)
        
        token_entry.token_data = self._credentials_to_dict(creds)
        self.db.commit()
        return user_email

    def _credentials_to_dict(self, credentials):
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

    def get_service(self, user_email: str, service_name: str, version: str):
        token_entry = self.db.query(GoogleToken).filter(GoogleToken.user_email == user_email).first()
        if not token_entry:
            raise Exception("No token found for user")
        
        creds = Credentials.from_authorized_user_info(token_entry.token_data, SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_entry.token_data = self._credentials_to_dict(creds)
            self.db.commit()
            
        return build(service_name, version, credentials=creds)

    def list_messages(self, user_email: str, query: str = None, max_results: int = 100):
        service = self.get_service(user_email, 'gmail', 'v1')
        messages = []
        page_token = None
        while len(messages) < max_results:
            results = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token,
                maxResults=min(100, max_results - len(messages)) # Fetch in chunks
            ).execute()
            messages.extend(results.get('messages', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return messages[:max_results] # Ensure not to exceed max_results

    def get_unread_emails(self, user_email: str):
        # Refactored to use list_messages for consistency and future flexibility
        return self.list_messages(user_email, query='is:unread newer_than:2d', max_results=50) # Reduced default max_results to 50


    def get_email_details(self, user_email: str, msg_id: str):
        service = self.get_service(user_email, 'gmail', 'v1')
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        return message

    def extract_body(self, payload):
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    import base64
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                elif 'parts' in part:
                    body = self.extract_body(part)
                    if body: return body
        else:
            import base64
            data = payload['body'].get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
        return ""

    def get_attachment(self, user_email: str, msg_id: str, attachment_id: str):
        service = self.get_service(user_email, 'gmail', 'v1')
        attachment = service.users().messages().attachments().get(
            userId='me', messageId=msg_id, id=attachment_id
        ).execute()
        import base64
        return base64.urlsafe_b64decode(attachment['data'])

    def create_calendar_event(self, user_email: str, event_data: dict):
        service = self.get_service(user_email, 'calendar', 'v3')
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        return event
