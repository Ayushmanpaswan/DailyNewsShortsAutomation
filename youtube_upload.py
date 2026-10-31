
from pathlib import Path
import argparse
import json

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
VIDEO_FILE = BASE_DIR / "output" / "daily_news_short.mp4"
NEWS_FILE = BASE_DIR / "data" / "news_data.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def build_metadata():
    """Create YouTube metadata from the actual stories in this video."""
    try:
        data = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        stories = data.get("news", [])
    except (OSError, json.JSONDecodeError):
        stories = []
    if not stories:
        return ("आज की 5 बड़ी खबरें | Hindi News #Shorts", "आज की प्रमुख खबरें एक ही वीडियो में।\n\n#HindiNews #LatestNews #Shorts #IndiaNews")
    headline = str(stories[0].get("headline", "आज की बड़ी खबर")).strip()
    title = headline if len(headline) <= 82 else headline[:79].rsplit(" ", 1)[0] + "..."
    title = title + " | #Shorts"
    lines = ["आज की बड़ी खबरें — इस 6 सेकंड के न्यूज़ अपडेट में:", ""]
    for story in stories:
        story_title = str(story.get("headline", "")).strip()
        if story_title:
            lines.append("• " + story_title)
    lines += ["", "ताज़ा अपडेट के लिए जुड़े रहें। जानकारी शेयर करने से पहले तथ्यों की पुष्टि करें.", "", "#HindiNews #LatestNews #BreakingNews #IndiaNews #UPNews #Shorts #NewsAndAwareness"]
    return title[:100], "\n".join(lines)

def get_credentials():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not CLIENT_SECRET.exists():
            raise FileNotFoundError(
                "Project folder mein client_secret.json file rakho."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET), SCOPES
        )

        creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(
            creds.to_json(), encoding="utf-8"
        )

    return creds


def main():
    parser = argparse.ArgumentParser(
        description="Upload a news video to YouTube."
    )

    parser.add_argument("--title", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private"
    )

    args = parser.parse_args()
    generated_title, generated_description = build_metadata()
    title = args.title or generated_title
    description = args.description or generated_description

    if not VIDEO_FILE.exists():
        raise FileNotFoundError(
            f"Video not found: {VIDEO_FILE}. "
            "Run make_video.py first."
        )

    youtube = build(
        "youtube",
        "v3",
        credentials=get_credentials()
    )

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["news", "HindiNews", "Shorts"],
            "categoryId": "25"
        },
        "status": {
            "privacyStatus": args.privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        str(VIDEO_FILE),
        mimetype="video/mp4",
        resumable=True
    )

    result = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    ).execute()

    video_id = result.get("id")

    print("Upload completed successfully!")
    print("Title:", title[:100])
    print("Video ID:", video_id)
    print("Video URL:", f"https://www.youtube.com/watch?v={video_id}")
    print("Privacy:", args.privacy)


if __name__ == "__main__":
    main()
