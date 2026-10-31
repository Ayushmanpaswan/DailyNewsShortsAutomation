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
from urllib.parse import urljoin, urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news_data.json"
HISTORY_FILE = DATA_DIR / "news_history.json"

NEWS_QUERIES = [
    "भारत की ताजा खबरें",
    "उत्तर प्रदेश लखनऊ समाचार",
    "भारत विश्व समाचार",
    "टेक्नोलॉजी AI समाचार",
    "भारत खेल समाचार",
]

MAX_NEWS = 5
MAX_ATTEMPTS = 3
MAX_AGE_HOURS = 48
MAX_HISTORY = 1000


class HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)


class MetaImageParser(HTMLParser):
    """Read article preview images from Open Graph / Twitter metadata."""
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        values = {str(k).lower(): str(v or "").strip() for k, v in attrs}
        key = (values.get("property") or values.get("name") or "").lower()
        content = values.get("content", "")
        if key in ("og:image", "og:image:url", "twitter:image", "twitter:image:src") and content:
            self.images.append(content)


def get_article_image(article_url):
    """Return the article's preview image when the publisher exposes one."""
    if not article_url:
        return ""
    try:
        request = urllib.request.Request(
            article_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return ""
            html_data = response.read(1_500_000).decode("utf-8", errors="replace")
        parser = MetaImageParser()
        parser.feed(html_data)
        for candidate in parser.images:
            image_url = urljoin(final_url, html.unescape(candidate)).strip()
            parsed = urlparse(image_url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                return image_url
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as error:
        print(f"Image unavailable for article: {error}")
    return ""


def clean_text(value):
    """Decode HTML entities and clean text without corrupting Hindi."""
    parser = HTMLTextParser()
    parser.feed(html.unescape(value or ""))
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()

    # Repair common UTF-8 text incorrectly decoded as Latin-1.
    if "à¤" in text or "à¥" in text:
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            if repaired:
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text


def normalize_headline(headline):
    """Normalize headlines for basic duplicate detection."""
    return re.sub(r"[^\w]+", "", headline.casefold())


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

                # RSS providers sometimes include a thumbnail in media/enclosure
                # elements or an image inside the HTML description.
                rss_image = ""
                for child in item.iter():
                    local_name = child.tag.rsplit("}", 1)[-1].lower()
                    if local_name in ("content", "thumbnail", "enclosure"):
                        candidate = child.attrib.get("url", "").strip()
                        if candidate.startswith(("https://", "http://")):
                            rss_image = candidate
                            break
                if not rss_image and description:
                    img_match = re.search(
                        r'<img\\b[^>]*?src=[\\"\\']([^\\"\\']+)[\\"\\']',
                        description,
                        flags=re.IGNORECASE,
                    )
                    if img_match:
                        candidate = html.unescape(img_match.group(1)).strip()
                        if candidate.startswith(("https://", "http://")):
                            rss_image = candidate

                title = clean_text(raw_title)
                detail = clean_text(description)

                if not title:
                    continue

                # Remove the publisher suffix from titles when present.
                if " - " in title:
                    possible_title, publisher = title.rsplit(" - ", 1)

                    if possible_title.strip() and publisher.strip():
                        title = possible_title.strip()

                results.append({
                    "headline": title,
                    "detail": detail or title,
                    "source_url": link,
                    "rss_image": rss_image,
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


def load_history():
    """Load previously used headlines from the history file."""
    if not HISTORY_FILE.exists():
        return []

    try:
        history_data = json.loads(
            HISTORY_FILE.read_text(encoding="utf-8")
        )

        headlines = history_data.get("headlines", [])

        if not isinstance(headlines, list):
            print("Warning: Invalid history format. Starting empty.")
            return []

        return [
            str(headline)
            for headline in headlines
            if isinstance(headline, str) and headline.strip()
        ]

    except (json.JSONDecodeError, OSError) as error:
        print(f"Warning: Could not read news history: {error}")
        raise RuntimeError(
            "News history could not be read safely. "
            "Fix the history file before continuing."
        ) from error


def save_json_atomically(path, data):
    """Write JSON using a temporary file before replacing the target."""
    temp_file = path.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temp_file.replace(path)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    history = load_history()

    seen = {
        normalize_headline(headline)
        for headline in history
    }

    collected = []

    # Fetch news from all configured categories.
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
    max_age = MAX_AGE_HOURS * 60 * 60

    for item in collected:
        headline = item["headline"].strip()
        key = normalize_headline(headline)
        timestamp = item["_timestamp"]

        if not key:
            continue

        # Skip previously used and duplicate headlines.
        if key in seen or key in run_seen:
            continue

        # Skip stories without a valid publication date.
        if timestamp <= 0:
            continue

        # Skip future-dated stories and stories older than 48 hours.
        age = now - timestamp

        if age < 0 or age > max_age:
            continue

        run_seen.add(key)
        selected.append(item)

        if len(selected) >= MAX_NEWS:
            break

    # Preserve existing news data if there are too few fresh stories.
    if len(selected) < MAX_NEWS:
        raise RuntimeError(
            f"Only {len(selected)} unseen news items were found. "
            f"Required: {MAX_NEWS}. "
            "Existing news files have not been replaced. "
            "Try again later."
        )

    news_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "news": [],
    }

    used_image_urls = set()
    for index, item in enumerate(selected, start=1):
        image_url = item.get("rss_image", "") or get_article_image(item["source_url"])
        normalized_image_url = image_url.split("#", 1)[0].split("?", 1)[0].lower()
        if normalized_image_url in used_image_urls:
            print(f"Duplicate article image skipped for story {index}.")
            image_url = ""
        elif normalized_image_url:
            used_image_urls.add(normalized_image_url)

        news_data["news"].append({
            "headline": item["headline"],
            "figure": f"NEWS {index:02d}",
            "detail": item["detail"],
            "image": image_url,
            "source_url": item["source_url"],
            "published": item["published"],
        })

    # Save selected news.
    save_json_atomically(OUTPUT_FILE, news_data)

    # Update history and keep only the most recent 1,000 headlines.
    updated_history = history + [
        item["headline"] for item in selected
    ]

    updated_history = updated_history[-MAX_HISTORY:]

    history_data = {
        "headlines": updated_history
    }

    save_json_atomically(HISTORY_FILE, history_data)

    print("\nSUCCESS: Five unseen news headlines saved.")
    print(f"History contains {len(updated_history)} headlines.")
    print(f"News file: {OUTPUT_FILE}")

    for index, item in enumerate(news_data["news"], start=1):
        print(f"{index}. {item['headline']}")
        print(f"   Published: {item['published']}")
        print(f"   Source: {item['source_url']}")
        print(f"   Image: {item.get('image') or 'NOT FOUND - fallback visual will be used'}")


if __name__ == "__main__":
    main()
