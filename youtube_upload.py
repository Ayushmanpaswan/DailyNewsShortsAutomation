
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
    """Build upload metadata from the five stories used in this video."""
    try:
        data = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        stories = data.get("news", [])
    except (OSError, json.JSONDecodeError):
        stories = []

    headlines = [
        str(story.get("headline", "")).strip()
        for story in stories
        if str(story.get("headline", "")).strip()
    ]
    if not headlines:
        return (
            "आज की 5 बड़ी खबरें | Hindi News #Shorts",
            "आज की प्रमुख खबरें एक ही वीडियो में।\n\n#HindiNews #LatestNews #Shorts",
        )

    first = headlines[0]
    title = first if len(first) <= 78 else first[:75].rsplit(" ", 1)[0] + "..."
    title = title + " | #Shorts"

    # Choose topic hashtags only when the corresponding words occur in today's stories.
    all_text = " ".join(headlines).casefold()
    topic_rules = [
        (("क्रिकेट", "टी20", "बैटर", "बल्लेबाज", "छक्के", "cricket"), "#CricketNews"),
        (("लखनऊ", "उत्तर प्रदेश", "यूपी", "up news", "योगी"), "#UPNews"),
        (("चुनाव", "सरकार", "मंत्री", "संसद", "राजनीति", "politics"), "#Politics"),
        (("टेक्नोलॉजी", "एआई", "आर्टिफिशियल इंटेलिजेंस", "technology", "ai "), "#TechNews"),
        (("मौसम", "बारिश", "बाढ़", "weather", "flood"), "#WeatherUpdate"),
        (("खेल", "खिलाड़ी", "स्पोर्ट्स", "sports"), "#SportsNews"),
        (("शेयर बाजार", "बाजार", "अर्थव्यवस्था", "business", "market"), "#BusinessNews"),
        (("अदालत", "कोर्ट", "पुलिस", "मर्डर", "हादसा", "crime"), "#CrimeNews"),
    ]
    topic_tags = []
    for keywords, tag in topic_rules:
        if any(keyword in all_text for keyword in keywords) and tag not in topic_tags:
            topic_tags.append(tag)
    hashtags = ["#HindiNews", "#LatestNews"] + topic_tags + ["#Shorts", "#NewsAndAwareness"]
    hashtags = list(dict.fromkeys(hashtags))[:10]

    lines = ["आज की खबरें — इस शॉर्ट में:", ""]
    lines.extend("• " + headline for headline in headlines)
    lines += [
        "",
        "यह संक्षिप्त न्यूज़ अपडेट है। पूरी जानकारी के लिए मूल रिपोर्ट देखें और तथ्यों की पुष्टि करें.",
        "",
        " ".join(hashtags),
    ]
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
            "tags": [tag.lstrip("#") for tag in description.split() if tag.startswith("#")][:15] + ["Hindi News", "Shorts"],
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
