import base64
import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "news_data.json"
OUTPUT_DIR = BASE_DIR / "output"
POSTER_DIR = OUTPUT_DIR / "posters"
VIDEO_FILE = OUTPUT_DIR / "daily_news_short.mp4"
REVIEW_FILE = OUTPUT_DIR / "review_report.md"
WIDTH = 1080
HEIGHT = 1920
MIN_IMAGE_WIDTH = 320
MIN_IMAGE_HEIGHT = 240
MIN_IMAGE_AREA = 120_000


def compact_text(value, limit):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"News data file not found: {DATA_FILE}")
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    news = data.get("news", [])
    if not 1 <= len(news) <= 5:
        raise ValueError("news_data.json must contain between 1 and 5 stories.")

    for index, item in enumerate(news, start=1):
        for key in ("headline", "detail", "image", "image_page_url", "image_author", "image_license", "image_attribution", "image_relevance_evidence"):
            if not str(item.get(key, "")).strip():
                raise ValueError(f"News item {index} is missing '{key}'.")
        image_path = (BASE_DIR / item["image"]).resolve()
        if BASE_DIR not in image_path.parents or not image_path.is_file():
            raise ValueError(f"News item {index} image not found: {image_path}")
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                image.load()
                width, height = image.size
                if (width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT
                        or width * height < MIN_IMAGE_AREA):
                    raise ValueError(f"image is too small: {width}x{height}")
        except (OSError, ValueError) as error:
            raise ValueError(
                f"News item {index} image is not a valid photograph: {image_path}"
            ) from error
        item["image_path"] = image_path

    data["date"] = data.get("updated_at", datetime.now().isoformat())[:10]
    return data


def image_data_uri(image_path):
    return "data:image/jpeg;base64," + base64.b64encode(
        image_path.read_bytes()
    ).decode("ascii")


def build_html(item, index, total, date):
    headline = compact_text(item["headline"], 130)
    detail = compact_text(item["detail"], 300)
    category = item.get("category", "भारत")
    image_uri = image_data_uri(item["image_path"])
    return f"""<!doctype html>
<html lang="hi"><head><meta charset="utf-8"><style>
@page {{ size: 1080px 1920px; margin: 0; }}
* {{ box-sizing: border-box; }} html,body {{ margin:0;width:1080px;height:1920px; }}
body {{ font-family:"Nirmala UI","Noto Sans Devanagari","Mangal",sans-serif;
  color:#fff;background:#16060a;position:relative;overflow:hidden; }}
.top {{ height:184px;padding:40px 56px 24px;background:#c9162b;
  border-bottom:12px solid #ffd33d;position:relative; }}
.brand {{ font-size:28px;letter-spacing:5px;font-weight:900; }}
.edition {{ position:absolute;right:56px;top:44px;font-size:23px;font-weight:800;
  background:#ffd33d;color:#351015;padding:11px 18px;border-radius:8px; }}
.hero {{ height:900px;position:relative;background:#090a0e; }}
.hero img {{ width:100%;height:100%;object-fit:cover; }}
.hero:after {{ content:"";position:absolute;inset:0;
  background:linear-gradient(180deg,transparent 35%,rgba(8,5,8,.9) 100%); }}
.badge {{ position:absolute;z-index:2;left:56px;top:42px;background:#ffd33d;
  color:#351015;padding:14px 22px;border-radius:8px;font-size:26px;font-weight:900; }}
.body {{ padding:52px 56px 40px;background:linear-gradient(145deg,#2a0b12,#12070a); }}
h1 {{ margin:0;color:#fff;font-size:58px;line-height:1.22;font-weight:900; }}
.rule {{ width:150px;height:10px;background:#ffd33d;margin:28px 0; }}
.summary {{ margin:0;font-size:30px;line-height:1.5;color:#fff4e8; }}
.footer {{ position:absolute;left:56px;right:56px;bottom:52px;display:flex;
  justify-content:space-between;align-items:center;border-top:2px solid #ffd33d;
  padding-top:18px;font-size:22px;font-weight:700;color:#ffd33d; }}
.count {{ color:#fff; }}
</style></head><body>
<header class="top"><div class="brand">हिंदी न्यूज़ • BREAKING</div>
<div class="edition">{escape(str(date))}</div></header>
<section class="hero"><img src="{image_uri}" alt="{escape(headline)}">
<div class="badge">{escape(category)}</div></section>
<main class="body"><h1>{escape(headline)}</h1><div class="rule"></div>
<p class="summary">{escape(detail)}</p></main>
<footer class="footer"><span>DAILY NEWS SHORTS</span>
<span class="count">{index:02d} / {total:02d}</span></footer>
</body></html>"""


def write_review_report(data, generated):
    lines = ["# Daily News Shorts review report", "", "This report is for human review before publication.", ""]
    for index, (item, poster) in enumerate(zip(data["news"], generated), 1):
        image = (BASE_DIR / item["image"]).relative_to(OUTPUT_DIR).as_posix()
        poster_rel = poster.relative_to(OUTPUT_DIR).as_posix()
        lines.extend([
            f"## {index}. {item['headline']}",
            f"![Licensed photograph preview]({image})",
            f"![Poster preview]({poster_rel})",
            f"- Publisher story: {item['publisher']} — {item['source_url']}",
            f"- Photograph page: {item['image_page_url']}",
            f"- Author: {item['image_author']}",
            f"- License: {item['image_license']} ({item.get('image_license_url', 'license URL not supplied')})",
            f"- Attribution: {item['image_attribution']}",
            f"- Relevance evidence: {item['image_relevance_evidence']}",
            "",
        ])
    REVIEW_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_FILE.unlink(missing_ok=True)
    if POSTER_DIR.exists():
        shutil.rmtree(POSTER_DIR)
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    data = load_data()
    generated = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        try:
            total = len(data["news"])
            for index, item in enumerate(data["news"], start=1):
                path = POSTER_DIR / f"news_{index:02d}.png"
                page.set_content(build_html(item, index, total, data["date"]),
                                 wait_until="networkidle")
                page.screenshot(path=str(path), full_page=True)
                with Image.open(path) as image:
                    if image.size != (WIDTH, HEIGHT):
                        raise RuntimeError(f"Poster has incorrect size: {path}")
                generated.append(path)
        finally:
            browser.close()

    if len(generated) != len(data["news"]):
        raise RuntimeError("Not all individual news posters were generated.")
    write_review_report(data, generated)
    print(f"SUCCESS: Generated {len(generated)} individual posters.")
    print(f"Review report: {REVIEW_FILE}")
    for path in generated:
        print(path)


if __name__ == "__main__":
    main()
