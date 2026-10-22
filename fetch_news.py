
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news_data.json"
HISTORY_FILE = DATA_DIR / "news_history.json"

NEWS_QUERIES = [
    "भारत की खबरें",
    "उत्तर प्रदेश लखनऊ",
    "विश्व समाचार",
    "टेक्नोलॉजी AI",
    "खेल समाचार",
]

MAX_NEWS = 5
MAX_ATTEMPTS = 3


class HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)



def clean_text(value):
    """Decode HTML entities and clean text without corrupting Hindi."""
    parser = HTMLTextParser()
    parser.feed(html.unescape(value or ""))
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()

    # Repair common UTF-8 text incorrectly decoded as Latin-1/Windows-1252.
    if "à¤" in text or "à¥" in text:
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            if repaired:
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text


def parse_date(value):
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0


def fetch_feed(query):
    params = urllib.parse.urlencode({
        "q": query,
        "hl": "hi",
        "gl": "IN",
        "ceid": "IN:hi",
    })

    url = "https://news.google.com/rss/search?" + params
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8",
        },
    )

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
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

                if " - " in title:
                    possible_title, publisher = title.rsplit(" - ", 1)
                    if possible_title.strip() and publisher.strip():
                        title = possible_title.strip()

                results.append({
                    "headline": title,
                    "detail": detail or title,
                    "source_url": link,
                    "published": pub_date,
                    "_timestamp": parse_date(pub_date),
                })

            return results

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ET.ParseError,
            OSError,
        ) as error:
            last_error = error
            print(
                f"Attempt {attempt}/{MAX_ATTEMPTS} failed "
                f"for '{query}': {error}"
            )

            if attempt < MAX_ATTEMPTS:
                delay = 2 ** attempt
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)

    raise RuntimeError(
        f"RSS request failed after {MAX_ATTEMPTS} attempts: {last_error}"
    )



def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load previously used headlines.
    seen = set()

    if HISTORY_FILE.exists():
        try:
            history_data = json.loads(
                HISTORY_FILE.read_text(encoding="utf-8")
            )
            seen = set(history_data.get("headlines", []))
        except (json.JSONDecodeError, OSError):
            print("Warning: Could not read news history.")

    collected = []

    # Fetch news from every configured category.
    for query in NEWS_QUERIES:
        try:
            items = fetch_feed(query)
            collected.extend(items)
            print(f"Fetched {len(items)} items: {query}")
        except Exception as error:
            print(f"Could not fetch '{query}': {error}")

    # Sort newest stories first.
    collected.sort(
        key=lambda item: item["_timestamp"],
        reverse=True,
    )

    selected = []
    run_seen = set()
    now = datetime.now(timezone.utc).timestamp()
    max_age = 48 * 60 * 60

    for item in collected:
        headline = item["headline"].strip()
        key = re.sub(r"\W+", "", headline.casefold())

        if not key or key in seen or key in run_seen:
            continue

        # Skip stories without a valid publication date.
        if item["_timestamp"] <= 0:
            continue

        # Skip stories older than 48 hours.
        age = now - item["_timestamp"]
        if age < 0 or age > max_age:
            continue

        run_seen.add(key)
        selected.append(item)

        if len(selected) >= MAX_NEWS:
            break

    # Do not replace existing news if there are not enough new stories.
    if len(selected) < MAX_NEWS:
        raise RuntimeError(
            f"Only {len(selected)} unseen news items were found. "
            "Existing news files have not been replaced. Try again later."
        )

    news_data = {
        "updated_at": datetime.now().astimezone().isoformat(),
        "news": [],
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

    # Save the new news data.
    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(news_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(OUTPUT_FILE)

    # Save history so these headlines are skipped in future runs.
    all_seen = seen | run_seen
    history_temp = HISTORY_FILE.with_suffix(".tmp")
    history_temp.write_text(
        json.dumps(
            {"headlines": sorted(all_seen)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    history_temp.replace(HISTORY_FILE)

    print("\nSUCCESS: Five unseen news headlines saved.")
    print(f"History contains {len(all_seen)} headlines.")
    print(f"News file: {OUTPUT_FILE}")

    for index, item in enumerate(news_data["news"], start=1):
        print(f"{index}. {item['headline']}")


if __name__ == "__main__":
    main()
