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
        cards.append(f"""
        <article class="card">
          <div class="num">{i:02}</div>
          <div class="content">
            <div class="row">
              <h2>{escape(str(item['headline']))}</h2>
              <span class="tag">{escape(str(item['figure']))}</span>
            </div>
            <p>{escape(str(item['detail']))}</p>
          </div>
        </article>""")
    return f"""<!doctype html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
@page {{ size: 1080px 1920px; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; width:1080px; height:1920px; }}
body {{
  font-family: "Nirmala UI", "Noto Sans Devanagari", "Mangal", sans-serif;
  color:#101828;
  background: linear-gradient(145deg,#061226 0%,#10284b 100%);
  padding:42px 54px;
}}
.header {{
  height:245px; border-radius:30px; padding:26px 34px;
  color:white; background:linear-gradient(115deg,#e51d35,#b5122a);
  position:relative; overflow:hidden;
}}
.brand {{font-size:28px; letter-spacing:4px; font-weight:800;}}
.title {{font-size:62px; line-height:1.16; font-weight:900; margin-top:10px;}}
.subtitle {{font-size:29px; margin-top:8px; font-weight:600;}}
.date {{
 position:absolute; right:26px; top:25px; border-radius:14px;
 background:#fff; color:#101828; padding:13px 18px;
 font-size:22px; font-weight:800;
}}
.cards {{ margin-top:25px; display:flex; flex-direction:column; gap:18px; }}
.card {{
 height:260px; display:flex; gap:20px; padding:22px;
 border-radius:24px; background:#f8fafc;
 border:2px solid rgba(255,255,255,.55);
 box-shadow:0 10px 0 rgba(0,0,0,.16);
}}
.num {{
 flex:0 0 68px; height:68px; border-radius:20px; background:#e51d35;
 color:white; display:flex; align-items:center; justify-content:center;
 font-size:27px; font-weight:900;
}}
.content {{flex:1; min-width:0;}}
.row {{display:flex; align-items:flex-start; gap:12px;}}
h2 {{font-size:31px; line-height:1.25; margin:0; flex:1; font-weight:800;}}
.tag {{
 flex:0 0 auto; background:#ffe08a; color:#78220e; padding:9px 12px;
 border-radius:12px; font-size:18px; font-weight:900; max-width:180px;
}}
p {{font-size:23px; line-height:1.45; color:#475467; margin:18px 0 0;}}
.footer {{
 margin-top:24px; border-radius:20px; padding:18px 24px;
 background:#132b4d; color:#fff; height:105px;
}}
.footer strong {{font-size:24px; color:#ffd66b;}}
.footer div {{font-size:19px; margin-top:7px;}}
.small {{position:absolute; bottom:20px; left:0; width:100%; text-align:center;
 color:#b9c8dc; font-size:16px; letter-spacing:2px;}}
</style>
</head>
<body>
  <header class="header">
    <div class="brand">DAILY UPDATE</div>
    <div class="date">{escape(str(data["date"]))}</div>
    <div class="title">TOP 5 NEWS</div>
    <div class="subtitle">{escape(str(data["subtitle"]))}</div>
  </header>
  <main class="cards">{''.join(cards)}</main>
  <footer class="footer">
    <strong>NEWS UPDATE</strong>
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
