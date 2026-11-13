# Daily News Shorts Automation

Generate a single vertical Hindi news video from individual 1080×1920 news posters. Each story is selected only when the image-discovery pipeline finds a candidate that passes the configured metadata relevance, license, duplicate, and image-quality checks. The metadata checks are not visual confirmation; review the generated posters and attribution report before publishing.

## Current workflow

1. `fetch_news.py` reads the configured RSS feeds, filters recent/nonduplicate stories, discovers Wikimedia Commons candidates, validates license metadata and image quality, and writes a review report plus YouTube metadata.
2. `poster_generator.py` creates one full-screen poster per accepted story.
3. `make_video.py` combines the posters into one vertical MP4.
4. Review `output/review_report.md`, every poster in `output/posters/`, the generated video, and all photo credits before any publication.

If no stories have a suitable image, the pipeline stops safely instead of reusing unrelated or stale output.

## Requirements

- Python 3.12 (recommended)
- FFmpeg installed and available on PATH
- Chromium installed through Playwright
- Internet access for RSS and Wikimedia Commons requests

## Windows setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Run the local pipeline:

```powershell
python fetch_news.py
python poster_generator.py
python make_video.py
```

Expected review outputs include:

- `output/posters/*.png` — individual vertical news posters
- `output/daily_news_short.mp4` — combined video
- `output/review_report.md` — story/image decisions and attribution details
- `data/youtube_metadata.json` — generated title, description, tags, and image credits

The project uses RSS headlines/summaries and Wikimedia Commons image metadata. A metadata match is not proof that the depicted scene is visually correct. Always inspect the actual image and source page.

## Image licensing and attribution

The image adapter accepts only its explicitly configured reuse-license markers and rejects non-commercial/no-derivatives terms. It records the Commons file page, author/license attribution, and source details for review. A license label or metadata match should still be checked against the original file page before publication. CC BY-SA material may impose ShareAlike obligations; do not assume that a short credit line alone satisfies every obligation.

Publisher RSS is used for story discovery. Do not copy publisher article photographs unless you have separate permission or a compatible license.

## YouTube upload (manual and optional)

The upload helper is separate from the build pipeline. It requires local OAuth files:

- `client_secret.json`
- `token.json`

Keep both files private and never commit them. To authorize locally, place your Google Desktop OAuth client JSON at the project root and run:

```powershell
python reauthorize_youtube.py
```

After reviewing the video, report, image licenses, and generated credits, an upload can be initiated manually:

```powershell
python youtube_upload.py --privacy private
```

Choose a different privacy setting only after explicitly reviewing it. The uploader validates that generated metadata contains image credits, but it does not replace human review. No upload is performed by the current GitHub Actions workflow.

## GitHub Actions

`.github/workflows/build-video.yml` is currently **manual-dispatch only**. It has no schedule or push trigger, does not load YouTube credentials, does not upload to YouTube, and uploads generated files only as a short-lived review artifact.

To run it manually, open the repository's **Actions** tab, select **Build Daily News Shorts (manual review)**, and choose **Run workflow**. This starts RSS/Commons discovery and generates review artifacts; it does not publish a video.

## Tests

Run the mocked/unit test suite locally:

```powershell
python -m unittest discover -s tests -v
```

Tests do not establish that a live news image is visually accurate. Inspect each real output before publication.

## Safety

- Never commit OAuth credentials, tokens, virtual environments, caches, generated videos, or private assets.
- Do not weaken relevance, licensing, or image-quality checks to increase the number of selected stories.
- If a story has no suitable licensed image, skip it.
- Review all outputs and attribution before any manual YouTube upload.
