
import json
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news_data.json"

# Google News RSS searches in Hindi.
# Multiple categories help avoid collecting five similar headlines.
NEWS_QUERIES = [
    "भारत की खबरें",
    "उत्तर प्रदेश लखनऊ",
    "विश्व समाचार",
    "टेक्नोलॉजी AI",
    "खेल समाचार",
]

MAX_NEWS = 5


class HTMLTextParser(HTMLParser):
    """Convert HTML descriptions into readable plain text."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)


def clean_text(value):
    """Remove HTML tags and extra whitespace."""
    parser = HTMLTextParser()
    parser.feed(html.unescape(value or ""))

    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date(value):
    """Convert RSS publication date into a sortable timestamp."""
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0


def fetch_feed(query):
    """Fetch one Google News RSS feed."""
    params = urllib.parse.urlencode({
        "q": query,
        "hl": "hi",
        "gl": "IN",
        "ceid": "IN:hi",
    })

    url = "https://news.google.com/rss/search?" + params

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DailyNewsShortsAutomation/1.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    results = []

    for item in root.findall(".//item"):
        raw_title = item.findtext("title", default="")
        description = item.findtext("description", default="")
        link = item.findtext("link", default="")
        pub_date = item.findtext("pubDate", default="")

        title = clean_text(raw_title)
        detail = clean_text(description)

        if not title:
            continue

        # Google News titles commonly end with " - Publisher".
        # Remove the publisher suffix only when it is clearly present.
        if " - " in title:
            possible_title, publisher = title.rsplit(" - ", 1)
            if possible_title and publisher:
                title = possible_title.strip()

        results.append({
            "headline": title,
            "detail": detail or title,
            "source_url": link,
            "published": pub_date,
            "_timestamp": parse_date(pub_date),
        })

    return results


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    collected = []
    failed_queries = []

    for query in NEWS_QUERIES:
        try:
            items = fetch_feed(query)
            collected.extend(items)
            print(f"Fetched {len(items)} items: {query}")

        except Exception as error:
            failed_queries.append(query)
            print(f"Could not fetch '{query}': {error}")

    # Sort newest first and remove duplicate headlines.
    collected.sort(
        key=lambda item: item["_timestamp"],
        reverse=True
    )

    selected = []
    seen = set()

    for item in collected:
        key = re.sub(
            r"\W+", "", item["headline"].lower()
        )

        if not key or key in seen:
            continue

        seen.add(key)
        selected.append(item)

        if len(selected) == MAX_NEWS:
            break

    if len(selected) < MAX_NEWS:
        raise RuntimeError(
            f"Only {len(selected)} unique news items were fetched. "
            "The existing news_data.json has not been replaced. "
            "Check your internet connection and try again."
        )

    # Keep the fields expected by the existing poster generator.
    news_data = {
        "updated_at": datetime.now().astimezone().isoformat(),
        "news": []
    }

    for index, item in enumerate(selected, start=1):
        news_data["news"].append({
            "headline": item["headline"],
            "figure": f"NEWS {index:02d}",
            "detail": item["detail"],
            "image": "",
            "source_url": item["source_url"],
            "published": item["published"],
        })

    # Write first to a temporary file so incomplete downloads
    # do not overwrite the previous JSON file.
    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(news_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    temp_file.replace(OUTPUT_FILE)

    print("\nSUCCESS: Five news items saved.")
    print(f"File: {OUTPUT_FILE}")

    for index, item in enumerate(news_data["news"], start=1):
        print(f"{index}. {item['headline']}")


if __name__ == "__main__":
    main()
