"""Publish the generated news short as a video on the configured Facebook Page."""
import json
import os
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
VIDEO_FILE = BASE_DIR / "output" / "daily_news_short.mp4"
METADATA_FILE = BASE_DIR / "data" / "youtube_metadata.json"
GRAPH_API_VERSION = "v27.0"
GRAPH_VIDEO_BASE = "https://graph-video.facebook.com"


def load_metadata():
    if not METADATA_FILE.is_file():
        raise FileNotFoundError(f"Metadata not found: {METADATA_FILE}")
    metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    title = str(metadata.get("title", "")).strip()
    description = str(metadata.get("description", "")).strip()
    if not title or not description:
        raise ValueError("News metadata must include a title and description.")
    hashtags = metadata.get("hashtags", [])
    if isinstance(hashtags, list):
        suffix = " ".join(str(tag).strip() for tag in hashtags if str(tag).strip())
        if suffix and suffix not in description:
            description = f"{description}\n\n{suffix}"
    return title[:255], description


def main():
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    page_token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not page_token:
        raise SystemExit(
            "Missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN GitHub Actions secret."
        )
    if not page_id.isdigit():
        raise SystemExit("FB_PAGE_ID must contain only the numeric Page ID.")
    if not VIDEO_FILE.is_file():
        raise FileNotFoundError(f"Video not found: {VIDEO_FILE}. Run make_video.py first.")

    title, description = load_metadata()
    endpoint = f"{GRAPH_VIDEO_BASE}/{GRAPH_API_VERSION}/{page_id}/videos"
    form_data = {
        "access_token": page_token,
        "title": title,
        "description": description,
        "published": "true",
    }

    print(f"Uploading {VIDEO_FILE.name} to Facebook Page {page_id}...")
    try:
        with VIDEO_FILE.open("rb") as video:
            response = requests.post(
                endpoint,
                data=form_data,
                files={"source": (VIDEO_FILE.name, video, "video/mp4")},
                timeout=(30, 600),
            )
        try:
            result = response.json()
        except ValueError:
            result = {}

        if not response.ok or not result.get("id"):
            error = result.get("error", {})
            message = error.get("message") or f"HTTP {response.status_code}"
            error_code = error.get("code")
            error_subcode = error.get("error_subcode")
            details = f"Facebook API upload failed: {message}"
            if error_code is not None:
                details += f" (code {error_code}"
                if error_subcode is not None:
                    details += f", subcode {error_subcode}"
                details += ")"
            raise RuntimeError(details)

        print("Facebook Page video upload completed successfully.")
        print("Facebook video ID:", result["id"])
    except requests.RequestException as error:
        # Do not print request URLs or request bodies, which may contain credentials.
        raise RuntimeError(
            f"Facebook upload network error: {type(error).__name__}"
        ) from None


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
