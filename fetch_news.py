import html
import http.client
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from licensed_images import (
    ImageSelectionError,
    get_commons_metrics,
    prefetch_queries,
    search_queries,
    select_image,
    story_mapping,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news_data.json"
HISTORY_FILE = DATA_DIR / "news_history.json"
SEO_FILE = DATA_DIR / "youtube_metadata.json"
OUTPUT_DIR = BASE_DIR / "output"
IMAGE_DIR = OUTPUT_DIR / "news_images"
POSTER_DIR = OUTPUT_DIR / "posters"
VIDEO_FILE = OUTPUT_DIR / "daily_news_short.mp4"
REVIEW_FILE = OUTPUT_DIR / "review_report.md"
REJECTION_LOG_FILE = DATA_DIR / "image_rejection_log.json"
LEGACY_POSTER_FILE = OUTPUT_DIR / "daily_news_poster.png"
MAX_NEWS = 5
MAX_IMAGE_CHECKS = 100
MAX_ATTEMPTS = 2
RSS_CONNECT_TIMEOUT = 5
RSS_READ_TIMEOUT = 10
FEED_COOLDOWN_FILE = DATA_DIR / "publisher_feed_cache.json"
EMPTY_FEED_COOLDOWN = 24 * 60 * 60
PERMANENT_FEED_COOLDOWN = 7 * 24 * 60 * 60
TEMPORARY_FEED_COOLDOWN = 30 * 60
MAX_AGE_HOURS = 48
MAX_HISTORY = 1000
MAX_YOUTUBE_DESCRIPTION_CHARS = 5000
USED_IMAGE_HASHES = set()
USER_AGENT = "DailyNewsShortsAutomation/1.0"
FETCH_METRICS = {
    "rss_requests": 0,
    "rss_successes": 0,
    "rss_cache_hits": 0,
    "rss_skipped_feeds": 0,
    "publisher_timings": {},
}

RSS_FEEDS = [
    ("Live Hindustan", "भारत", "https://api.livehindustan.com/feeds/rss/national/rssfeed.xml"),
    ("Live Hindustan", "उत्तर प्रदेश", "https://api.livehindustan.com/feeds/rss/uttar-pradesh/rssfeed.xml"),
    ("NDTV Hindi", "भारत", "https://feeds.feedburner.com/ndtvkhabar-latest"),
    ("NDTV Hindi", "विश्व", "https://feeds.feedburner.com/ndtvkhabar-india"),
    ("Dainik Jagran", "भारत", "http://rss.jagran.com/rss/news/national.xml"),
    ("Dainik Jagran", "उत्तर प्रदेश", "http://rss.jagran.com/local/uttar-pradesh/lucknow-city.xml"),
]


class HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value):
    parser = HTMLTextParser()
    parser.feed(html.unescape(value or ""))
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    if "Ã Â¤" in text or "Ã Â¥" in text:
        try:
            text = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def normalize_headline(value):
    return re.sub(r"[^\w\u0900-\u097f]+", "", value.casefold())


def parse_date(value):
    try:
        date = parsedate_to_datetime(value)
        return date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0


def _empty_feed_cache():
    return {"version": 1, "feeds": {}}


def load_feed_cache():
    if not FEED_COOLDOWN_FILE.is_file():
        return _empty_feed_cache()
    try:
        value = json.loads(FEED_COOLDOWN_FILE.read_text(encoding="utf-8"))
        if value.get("version") != 1 or not isinstance(value.get("feeds"), dict):
            return _empty_feed_cache()
        return value
    except (OSError, json.JSONDecodeError):
        print("Warning: publisher feed cache is missing or corrupted; rebuilding it.")
        return _empty_feed_cache()


FEED_CACHE = load_feed_cache()


def save_feed_cache():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = FEED_COOLDOWN_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(FEED_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(FEED_COOLDOWN_FILE)


def feed_cache_record(source, category, url):
    record = FEED_CACHE["feeds"].setdefault(url, {
        "source": source,
        "category": category,
        "last_success": None,
        "last_failure": None,
        "failure_type": None,
        "cooldown_until": 0,
        "consecutive_failures": 0,
    })
    record["source"] = source
    record["category"] = category
    return record


def _retry_after_seconds(error, attempt):
    value = getattr(error, "headers", {}).get("Retry-After") if error else None
    if value:
        try:
            return min(30, max(0, int(value)))
        except (TypeError, ValueError):
            try:
                retry_date = parsedate_to_datetime(value)
                return min(30, max(0, int(retry_date.timestamp() - time.time())))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(10, 2 ** attempt)


def _feed_http_request(url):
    """Fetch RSS bytes with separate connect and read socket timeouts."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid RSS URL: {url}")
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=RSS_CONNECT_TIMEOUT)
    try:
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection.request("GET", path, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml,*/*",
            "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8",
        })
        response = connection.getresponse()
        sock = getattr(getattr(response, "fp", None), "raw", None)
        sock = getattr(sock, "_sock", None)
        if sock is not None:
            sock.settimeout(RSS_READ_TIMEOUT)
        body = response.read(4 * 1024 * 1024)
        headers = response.headers
        status = response.status
        if status < 200 or status >= 300:
            raise urllib.error.HTTPError(url, status, response.reason, headers, None)
        return body
    finally:
        connection.close()


def _record_feed_failure(source, category, url, failure_type, cooldown):
    record = feed_cache_record(source, category, url)
    now = time.time()
    record["last_failure"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
    record["failure_type"] = failure_type
    record["consecutive_failures"] = int(record.get("consecutive_failures", 0)) + 1
    record["cooldown_until"] = now + cooldown
    save_feed_cache()


def _record_feed_success(source, category, url):
    record = feed_cache_record(source, category, url)
    record["last_success"] = datetime.now(timezone.utc).isoformat()
    record["cooldown_until"] = 0
    record["failure_type"] = None
    record["consecutive_failures"] = 0
    save_feed_cache()


def _add_publisher_timing(source, elapsed):
    FETCH_METRICS["publisher_timings"][source] = FETCH_METRICS["publisher_timings"].get(source, 0.0) + elapsed


def fetch_feed(source, category, url):
    started = time.perf_counter()
    record = feed_cache_record(source, category, url)
    if record.get("cooldown_until", 0) > time.time():
        FETCH_METRICS["rss_skipped_feeds"] += 1
        FETCH_METRICS["rss_cache_hits"] += 1
        _add_publisher_timing(source, time.perf_counter() - started)
        print(f"Skipped {source} feed during cooldown: {url}")
        return []
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            FETCH_METRICS["rss_requests"] += 1
            root = ET.fromstring(_feed_http_request(url))
            results = []
            for node in root.findall(".//item"):
                title = clean_text(node.findtext("title", ""))
                detail = clean_text(node.findtext("description", ""))
                link = (node.findtext("link", "") or "").strip()
                pub_date = (node.findtext("pubDate", "") or "").strip()
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0].strip()
                if not title or not link:
                    continue
                results.append({"headline": title, "detail": detail or title, "source_url": link, "published": pub_date, "_timestamp": parse_date(pub_date), "publisher": source, "category": category})
            if not results:
                _record_feed_failure(source, category, url, "empty_xml_or_no_items", EMPTY_FEED_COOLDOWN)
                _add_publisher_timing(source, time.perf_counter() - started)
                print(f"Skipped empty RSS feed without retry: {source} {url}")
                return []
            _record_feed_success(source, category, url)
            FETCH_METRICS["rss_successes"] += 1
            _add_publisher_timing(source, time.perf_counter() - started)
            return results
        except ET.ParseError as error:
            _record_feed_failure(source, category, url, "invalid_xml", EMPTY_FEED_COOLDOWN)
            _add_publisher_timing(source, time.perf_counter() - started)
            print(f"Skipped invalid RSS XML without retry: {source} {url}: {error}")
            return []
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed for {source} {url}: {error}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(_retry_after_seconds(error, attempt))
    failure_type = "permanent_http_error" if isinstance(last_error, urllib.error.HTTPError) and last_error.code in {400, 401, 403, 404, 410} else "temporary_feed_error"
    cooldown = PERMANENT_FEED_COOLDOWN if failure_type == "permanent_http_error" else TEMPORARY_FEED_COOLDOWN
    _record_feed_failure(source, category, url, failure_type, cooldown)
    _add_publisher_timing(source, time.perf_counter() - started)
    return []


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        values = json.loads(HISTORY_FILE.read_text(encoding="utf-8")).get("headlines", [])
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"News history could not be read safely: {error}") from error
    return [str(value) for value in values if isinstance(value, str) and value.strip()]


def save_json_atomically(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def clear_previous_outputs():
    USED_IMAGE_HASHES.clear()
    for path in (OUTPUT_FILE, SEO_FILE, VIDEO_FILE, REVIEW_FILE, LEGACY_POSTER_FILE, REJECTION_LOG_FILE):
        path.unlink(missing_ok=True)
    for directory in (IMAGE_DIR, POSTER_DIR):
        if directory.exists():
            shutil.rmtree(directory)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def build_youtube_metadata(news):
    headlines = [item["headline"] for item in news]
    categories = list(dict.fromkeys(item.get("category", "भारत") for item in news))
    title = f"आज की बड़ी खबरें | {' • '.join(headlines[:2])} #Shorts"[:100]
    lines = ["आज के Hindi News Shorts में शामिल खबरें:", ""]
    for index, item in enumerate(news, 1):
        summary = re.sub(r"\s+", " ", item["detail"]).strip()[:240]
        lines += [f"{index}. {item['headline']}", f"   {summary}", f"   स्रोत: {item['publisher']} — {item['source_url']}", ""]
    lines += ["फोटो क्रेडिट और लाइसेंस:"]
    for index, item in enumerate(news, 1):
        lines.append(f"{index}. {item['image_attribution']}")
        if item.get("image_sharealike"):
            lines.append("   यह फोटो CC BY-SA के तहत है; फोटो का क्रेडिट और मूल लाइसेंस लागू रहेगा।")
    lines += ["", "यह वीडियो केवल उन्हीं समाचारों और लाइसेंस-प्रमाणित तस्वीरों पर आधारित है जो ऊपर सूचीबद्ध हैं।"]
    description = "\n".join(lines)
    if len(description) > MAX_YOUTUBE_DESCRIPTION_CHARS:
        raise RuntimeError(f"Required story and image credits exceed YouTube description limit ({len(description)} > {MAX_YOUTUBE_DESCRIPTION_CHARS}).")
    tags = ["Hindi news", "Hindi breaking news", "daily news", "news shorts"]
    for headline in headlines:
        for word in re.findall(r"[\w\u0900-\u097f]{4,}", headline.casefold()):
            if word not in tags and len(tags) < 30:
                tags.append(word)
    return {"title": title, "description": description, "hashtags": ["#HindiNews", "#BreakingNews", "#DailyNews", "#Shorts"] + [f"#{category.replace(' ', '')}" for category in categories], "tags": tags, "image_credits": [item["image_attribution"] for item in news], "description_character_count": len(description)}


def report_metrics(total_elapsed):
    commons = get_commons_metrics()
    print("\nFETCH METRICS")
    for publisher, elapsed in sorted(FETCH_METRICS["publisher_timings"].items()):
        print(f"{publisher}: {elapsed:.2f}s")
    print(f"RSS requests: {FETCH_METRICS['rss_requests']}")
    print(f"RSS successful requests: {FETCH_METRICS['rss_successes']}")
    print(f"RSS skipped feeds: {FETCH_METRICS['rss_skipped_feeds']}")
    print(f"RSS feed-cache hits: {FETCH_METRICS['rss_cache_hits']}")
    print(f"Commons API requests: {commons['api_requests']}")
    print(f"Commons cache hits: {commons['cache_hits']}")
    print(f"Total execution time: {total_elapsed:.2f}s")


def _run():
    configure_console_encoding()
    clear_previous_outputs()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    history = load_history()
    seen = {normalize_headline(value) for value in history}
    collected = []
    for source, category, url in RSS_FEEDS:
        try:
            items = fetch_feed(source, category, url)
            collected.extend(items)
            print(f"Fetched {len(items)} items from {source} ({category})")
        except Exception as error:
            print(f"Could not fetch {source} {url}: {error}")
    collected.sort(key=lambda item: item["_timestamp"], reverse=True)
    prefetch_queries([
        query
        for item in collected[:MAX_IMAGE_CHECKS]
        for query in search_queries(item)
    ])
    selected = []
    rejection_log = []
    attempted = set()
    now = datetime.now(timezone.utc).timestamp()
    image_attempts = 0
    for item in collected:
        key = normalize_headline(item["headline"])
        age = now - item["_timestamp"]
        if not key or key in seen or key in attempted or item["_timestamp"] <= 0 or age < 0 or age > MAX_AGE_HOURS * 3600:
            continue
        attempted.add(key)
        image_attempts += 1
        if image_attempts > MAX_IMAGE_CHECKS:
            print(f"Stopping after {MAX_IMAGE_CHECKS} strict image checks; uncertain stories remain excluded.")
            break
        image_path = IMAGE_DIR / f"news_{len(selected) + 1:02d}.jpg"
        story_rejection = {
            "headline": item["headline"],
            "publisher": item.get("publisher"),
            "story_url": item.get("source_url"),
            "mapping": story_mapping(item),
            "queries_attempted": search_queries(item),
            "candidates": [],
            "final_status": "rejected",
        }
        rejection_log.append(story_rejection)
        try:
            selected_image = select_image(item, image_path, USED_IMAGE_HASHES, story_rejection)
        except Exception as error:
            print(f"Skipping story without a verified relevant licensed photograph: {item['headline']} — {error}")
            continue
        story_rejection["final_status"] = "accepted"
        item.update(selected_image)
        item["image"] = str(image_path.relative_to(BASE_DIR)).replace("\\", "/")
        selected.append(item)
        if len(selected) >= MAX_NEWS:
            break
    if not selected:
        save_json_atomically(REJECTION_LOG_FILE, {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stories": rejection_log,
        })
        raise RuntimeError("No verified, relevant, licensed news photographs were found. No new news data was written and stale output was removed.")
    stories = []
    for index, item in enumerate(selected, 1):
        story = {key: item[key] for key in ("headline", "category", "detail", "image", "source_url", "published", "publisher", "image_source_url", "image_page_url", "image_author", "image_license", "image_license_url", "image_attribution", "image_relevance_evidence", "image_title", "image_sharealike")}
        story["figure"] = f"NEWS {index:02d}"
        stories.append(story)
    news_data = {"updated_at": datetime.now(timezone.utc).isoformat(), "news": stories}
    metadata = build_youtube_metadata(stories)
    save_json_atomically(OUTPUT_FILE, news_data)
    save_json_atomically(SEO_FILE, metadata)
    save_json_atomically(REJECTION_LOG_FILE, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stories": rejection_log,
    })
    save_json_atomically(HISTORY_FILE, {"headlines": (history + [item["headline"] for item in selected])[-MAX_HISTORY:]})
    print(f"SUCCESS: {len(stories)} licensed image-backed stories saved.")
    print(f"News file: {OUTPUT_FILE}")
    print(f"Metadata file: {SEO_FILE}")
    for item in stories:
        print(f"- {item['headline']} | {item['image_license']} | {item['image_page_url']}")


def main():
    started = time.perf_counter()
    try:
        _run()
    finally:
        report_metrics(time.perf_counter() - started)


if __name__ == "__main__":
    main()
