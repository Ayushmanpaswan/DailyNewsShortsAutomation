"""
Optional YouTube upload helper.
Requires client_secret.json downloaded from a Google Cloud OAuth Desktop app.
First run opens a browser for OAuth consent and creates token.json.
Never commit client_secret.json or token.json to GitHub.
"""
from pathlib import Path
import argparse
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
VIDEO_FILE = BASE_DIR / "output" / "daily_news_short.mp4"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_credentials():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES) if TOKEN_FILE.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not CLIENT_SECRET.exists():
            raise FileNotFoundError("Put Google OAuth Desktop client file at project root as client_secret.json.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="आज की 5 बड़ी खबरें | Daily News #Shorts")
    parser.add_argument("--description", default="आज की पाँच प्रमुख खबरें। कृपया जानकारी को विश्वसनीय स्रोतों से सत्यापित करें।")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    args = parser.parse_args()

    if not VIDEO_FILE.exists():
        raise FileNotFoundError(f"Video not found: {VIDEO_FILE}. Run make_video.py first.")
    youtube = build("youtube", "v3", credentials=get_credentials())
    body = {
        "snippet": {
            "title": args.title[:100],
            "description": args.description,
            "tags": ["news", "HindiNews", "Shorts"],
            "categoryId": "25"
        },
        "status": {"privacyStatus": args.privacy, "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(str(VIDEO_FILE), mimetype="video/mp4", resumable=True)
    result = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    print("Upload completed.")
    print("Video ID:", result.get("id"))
    print("URL:", "https://www.youtube.com/watch?v=" + result.get("id", ""))

if __name__ == "__main__":
    main()
