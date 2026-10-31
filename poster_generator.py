import json
from datetime import datetime
from pathlib import Path
from html import escape
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "news_data.json"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "daily_news_poster.png"

def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"News data file not found: {DATA_FILE}")
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    news = data.get("news", [])
    if len(news) != 5:
        raise ValueError("data/news_data.json must contain exactly 5 items in 'news'.")
    for i, item in enumerate(news, 1):
        for key in ("headline", "figure", "detail"):
            if not str(item.get(key, "")).strip():
                raise ValueError(f"News item {i} is missing '{key}'.")
    data.setdefault("date", datetime.now().strftime("%d %b %Y").upper())
    data.setdefault("subtitle", "आज की 5 बड़ी खबरें")
    data.setdefault("source", "Sources listed in the news data")
    return data

def build_html(data):
    cards = []
    for i, item in enumerate(data["news"], 1):
        image_url = str(item.get("image", "") or "").strip()
        # Only use direct HTTP(S) image URLs; Playwright loads them in the poster.
        if not image_url.startswith(("https://", "http://")):
            image_url = ""
        fallback_block = '<div class="image-fallback"><span>NEWS</span><strong>ताज़ा खबर</strong></div>'
        image_block = (
            f'<img class="story-image" src="{escape(image_url, quote=True)}" '
            f'alt="" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'no-image\')">'
            + fallback_block
            if image_url else fallback_block
        )
        cards.append(f"""
        <article class="card">
          <div class="image-wrap">{image_block}<div class="image-shade"></div>
            <div class="num">{i:02}</div>
            <span class="tag">{escape(str(item.get('figure', f'NEWS {i:02}')))}</span>
          </div>
          <div class="content">
            <h2>{escape(str(item['headline']))}</h2>
            <p>{escape(str(item['detail']))}</p>
            <div class="source-label">NEWS AND AWARENESS</div>
          </div>
        </article>""")
    return f"""<!doctype html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
@page {{ size:1080px 1920px; margin:0; }}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; width:1080px; height:1920px; }}
body {{
  font-family:"Nirmala UI","Noto Sans Devanagari","Mangal",sans-serif;
  color:#f8fafc; background:#07111f; padding:38px 48px;
  position:relative; overflow:hidden;
}}
body:before {{ content:""; position:absolute; width:650px; height:650px; right:-260px; top:280px;
  border-radius:50%; background:radial-gradient(circle,rgba(29,78,216,.22),transparent 70%); }}
.header {{
  height:240px; padding:26px 30px; border-radius:28px; position:relative; overflow:hidden;
  background:linear-gradient(120deg,#ef233c 0%,#b5172b 55%,#64152d 100%);
  box-shadow:0 18px 38px rgba(0,0,0,.24);
}}
.header:after {{ content:""; position:absolute; width:330px; height:330px; right:-95px; top:-155px;
  border:36px solid rgba(255,255,255,.12); border-radius:50%; }}
.brand {{font-size:25px;letter-spacing:3px;font-weight:900;}}
.live {{display:inline-block;background:#fff;color:#b5172b;padding:6px 12px;border-radius:8px;
  font-size:17px;letter-spacing:1px;margin-left:12px;vertical-align:4px;}}
.title {{font-size:61px;line-height:1.12;font-weight:950;margin-top:15px;letter-spacing:-1px;}}
.subtitle {{font-size:27px;margin-top:9px;font-weight:600;color:#ffe4e8;}}
.date {{position:absolute;right:26px;bottom:24px;border:1px solid rgba(255,255,255,.45);
  background:rgba(20,20,30,.18);padding:10px 14px;border-radius:12px;font-size:18px;font-weight:800;}}
.cards {{margin-top:23px;display:flex;flex-direction:column;gap:16px;}}
.card {{height:270px;display:flex;overflow:hidden;border-radius:22px;background:#f8fafc;color:#101828;
  border:1px solid rgba(255,255,255,.14);box-shadow:0 12px 26px rgba(0,0,0,.22);}}
.image-wrap {{width:310px;flex:0 0 310px;position:relative;background:linear-gradient(145deg,#173b68,#0a172a);
  overflow:hidden;}}
.story-image {{width:100%;height:100%;object-fit:cover;display:block;}}
.image-shade {{position:absolute;inset:0;background:linear-gradient(0deg,rgba(3,10,20,.58),transparent 58%);pointer-events:none;}}
.image-wrap.no-image .story-image {{display:none;}}
.image-wrap.no-image .image-fallback {{display:flex;}}
.image-fallback {{height:100%;display:none;flex-direction:column;align-items:center;justify-content:center;
  gap:12px;color:#fff;background:radial-gradient(circle at 25% 25%,#385d91,#0a172a 72%);}}
.image-fallback span {{font-size:19px;letter-spacing:4px;font-weight:900;color:#ffcf70;}}
.image-fallback strong {{font-size:29px;}}
.num {{position:absolute;left:15px;top:15px;width:51px;height:51px;border-radius:15px;background:#ef233c;color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:23px;font-weight:950;box-shadow:0 5px 14px #0004;}}
.tag {{position:absolute;left:15px;bottom:14px;background:#ffcf70;color:#3b1d11;padding:7px 10px;
  border-radius:8px;font-size:15px;font-weight:950;}}
.content {{flex:1;min-width:0;padding:20px 22px 15px;display:flex;flex-direction:column;}}
h2 {{font-size:28px;line-height:1.3;margin:0;font-weight:900;color:#111827;}}
p {{font-size:20px;line-height:1.42;color:#475467;margin:13px 0 0;}}
.source-label {{margin-top:auto;padding-top:8px;border-top:1px solid #e4e7ec;font-size:13px;
  font-weight:900;letter-spacing:2px;color:#d61f36;}}
.footer {{margin-top:22px;border:1px solid #29415e;border-radius:18px;padding:16px 22px;height:98px;
  background:linear-gradient(100deg,#122944,#0d1b2e);}}
.footer strong {{font-size:22px;color:#ffcf70;letter-spacing:1px;}}
.footer div {{font-size:17px;margin-top:6px;color:#cbd5e1;}}
.small {{position:absolute;bottom:13px;left:0;width:100%;text-align:center;color:#91a4bd;
  font-size:14px;letter-spacing:2px;}}
</style>
</head>
<body>
  <header class="header">
    <div class="brand">NEWS AND AWARENESS <span class="live">DAILY BRIEF</span></div>
    <div class="title">आज की 5 बड़ी खबरें</div>
    <div class="subtitle">देश • दुनिया • उत्तर प्रदेश • टेक्नोलॉजी</div>
    <div class="date">{escape(str(data["date"]))}</div>
  </header>
  <main class="cards">{''.join(cards)}</main>
  <footer class="footer">
    <strong>खबरों से रहें अपडेट</strong>
    <div>Source: {escape(str(data["source"]))}</div>
  </footer>
  <div class="small">STAY INFORMED • VERIFY BEFORE SHARING</div>
</body>
</html>"""

def main():
    data = load_data()
    html = build_html(data)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width":1080, "height":1920}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(OUTPUT_FILE), full_page=True)
        browser.close()
    print("Poster generated successfully.")
    print(f"File: {OUTPUT_FILE}")
    print("Resolution: 1080 x 1920")

if __name__ == "__main__":
    main()
