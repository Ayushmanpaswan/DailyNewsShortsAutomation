import argparse
import json
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
VIDEO_FILE = BASE_DIR / "output" / "daily_news_short.mp4"
METADATA_FILE = BASE_DIR / "data" / "youtube_metadata.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_metadata():
    if not METADATA_FILE.is_file():
        raise FileNotFoundError(
            f"Metadata not found: {METADATA_FILE}. Run fetch_news.py first."
        )
    metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    for key in ("title", "description", "tags"):
        if not metadata.get(key):
            raise ValueError(f"Generated metadata is missing '{key}'.")
    if len(metadata["description"]) > 5000:
        raise ValueError("Generated description exceeds YouTube's 5,000-character limit; credits were not removed.")
    if not metadata.get("image_credits"):
        raise ValueError("Generated metadata contains no image credits; refusing publication.")
    return metadata


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not CLIENT_SECRET.exists():
            raise FileNotFoundError("Project folder mein client_secret.json file rakho.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def main():
    parser = argparse.ArgumentParser(description="Upload the generated news video.")
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"],
                        default="private")
    args = parser.parse_args()
    metadata = load_metadata()

    if not VIDEO_FILE.exists():
        raise FileNotFoundError(f"Video not found: {VIDEO_FILE}. Run make_video.py first.")

    title = (args.title or metadata["title"])[:100]
    description = args.description or metadata["description"]
    tags = metadata.get("tags", [])
    youtube = build("youtube", "v3", credentials=get_credentials())
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "25",
        },
        "status": {"privacyStatus": args.privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(VIDEO_FILE), mimetype="video/mp4", resumable=True)
    result = youtube.videos().insert(part="snippet,status", body=body,
                                     media_body=media).execute()
    video_id = result.get("id")
    print("Upload completed successfully!")
    print("Video ID:", video_id)
    print("Video URL:", f"https://www.youtube.com/watch?v={video_id}")
    print("Privacy:", args.privacy)


if __name__ == "__main__":
    main()
