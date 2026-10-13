# Daily News Shorts Automation (Starter)

This project generates a 1080×1920 Hindi news poster, turns it into a 6-second MP4 with optional background music, and includes an optional YouTube upload helper.

## What works out of the box
- `poster_generator.py`: renders the 5-news layout with HTML/CSS + Playwright/Chromium. This avoids Pillow's missing RAQM support.
- `make_video.py`: creates a 6-second vertical MP4 with FFmpeg. If the music file is absent, it creates a silent video.
- `youtube_upload.py`: optional upload using YouTube Data API v3 and Google OAuth.

**Important:** `data/news_data.json` contains sample placeholders. This starter does not fetch real news automatically yet. Replace the five sample items with verified news, or connect a news provider before enabling daily publishing. YouTube uploads are private by default unless you explicitly choose another privacy setting.

## Windows setup (PowerShell)

1. Extract the ZIP.
2. Open the extracted `DailyNewsShortsAutomation` folder in VS Code.
3. Install Python 3.11 or 3.12 (recommended for package compatibility) and make sure `python` works in Terminal.
4. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements.txt
```

5. Generate the poster:

```powershell
python poster_generator.py
```

Output: `output/daily_news_poster.png`

If Hindi font rendering is incorrect, install a Devanagari font such as Nirmala UI or Noto Sans Devanagari on Windows. The Chromium browser uses installed fonts and supports Hindi shaping.

6. Create a video:
   - Install FFmpeg and add its `bin` folder to PATH: https://ffmpeg.org/download.html
   - Put music you have rights to use at `assets/background_music.mp3`.
   - Then run:

```powershell
python make_video.py
```

Output: `output/daily_news_short.mp4`

You can supply another audio path:

```powershell
python make_video.py --music "C:\path\to\licensed-music.mp3" --duration 6
```

## YouTube upload setup (optional)

1. In Google Cloud Console, create/select a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen, then create an **OAuth Client ID → Desktop app**.
3. Download the OAuth JSON and place it at the project root named `client_secret.json`.
4. Run this once in a desktop terminal:

```powershell
python youtube_upload.py --privacy private
```

5. Complete the browser consent. A `token.json` file will be created locally. Keep both `client_secret.json` and `token.json` private. Never commit them to GitHub.
6. Review the uploaded private video in YouTube Studio. Only use `--privacy public` after validating the content and upload behavior.

YouTube API projects may be subject to quota and audit restrictions; public upload behavior can depend on Google's current API project status. Do not assume public publishing is enabled until tested.

## GitHub Actions

The workflow in `.github/workflows/build-video.yml` builds the poster and video on a schedule and uploads them as a downloadable workflow artifact. It does **not** upload to YouTube automatically yet. That is intentional: first verify the output and add news-source automation and securely configured OAuth secrets.

To enable the scheduled build:
1. Push this project to a GitHub repository.
2. In the repository, go to **Actions** and enable workflows.
3. The workflow runs daily at 03:30 UTC (09:00 India Standard Time) and can also be started manually.
4. Add a music file only if you have the rights to use it; GitHub workflow can use a committed, properly licensed audio file or a securely stored asset.

GitHub-hosted runners are temporary, so generated files are attached as workflow artifacts.

## Suggested next stages
1. Replace sample headlines with real, verified news.
2. Add a trusted news API/RSS source and robust error handling.
3. Run the scheduled build and inspect artifacts.
4. Configure and test YouTube upload privately.
5. Only then automate public uploads.

## Safety and reliability notes
- News should be checked for accuracy and dated.
- Use music you own or have a license to use.
- Do not put OAuth credentials in source control.
- A six-second video is very short for five stories; use concise headlines and consider a longer duration if readability suffers.
