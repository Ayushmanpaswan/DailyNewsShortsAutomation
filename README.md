# Daily News Shorts Automation

Generate one 1080×1920 Hindi news poster from the newest eligible, unseen RSS story. The system skips stories without a candidate that passes the configured metadata relevance, license, duplicate, and image-quality checks. It creates a single 4-second vertical MP4 with the configured background music. Metadata checks are not visual confirmation; review the poster and attribution report before publishing.

## Current workflow

1. `fetch_news.py` reads the configured RSS feeds, sorts stories newest-first, skips previously published stories, and selects only the first story with a verified relevant, licensed, nonduplicate, sufficiently large Wikimedia Commons image.
2. `poster_generator.py` creates exactly one full-screen poster.
3. `make_video.py` creates a 4-second vertical MP4 from that single poster.
4. Review `output/review_report.md`, the single poster in `output/posters/`, the 4-second video, and the photo credit before publication.

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

- `output/posters/news_01.png` — the single vertical news poster
- `output/daily_news_short.mp4` — combined video
- `output/review_report.md` — story/image decisions and attribution details
- `data/youtube_metadata.json` — generated title, description, tags, and image credits

The project uses RSS headlines/summaries and Wikimedia Commons image metadata. A metadata match is not proof that the depicted scene is visually correct. Always inspect the actual image and source page.

## Image licensing and attribution

The image adapter accepts only its explicitly configured reuse-license markers and rejects non-commercial/no-derivatives terms. It records the Commons file page, author/license attribution, and source details for review. A license label or metadata match should still be checked against the original file page before publication. CC BY-SA material may impose ShareAlike obligations; do not assume that a short credit line alone satisfies every obligation.

Publisher RSS is used for story discovery. Do not copy publisher article photographs unless you have separate permission or a compatible license.

## YouTube upload (manual and optional)

The uploader uses a Google OAuth `token.json` containing a valid refresh token. Keep it private and never commit it. To authorize locally, place your Google Desktop OAuth client JSON at the project root and run:

```powershell
python reauthorize_youtube.py
```

After reviewing the video, report, image licenses, and generated credits, a local upload can be initiated manually:

```powershell
python youtube_upload.py --privacy private
```

Choose a different privacy setting only after explicitly reviewing it. The uploader validates that generated metadata contains image credits, but it does not replace human review. No upload is performed by the current GitHub Actions workflow.

## GitHub Actions

`.github/workflows/build-video.yml` can be run manually and also has the configured weekly schedule. Each run fetches the newest eligible unseen story, applies the configured image relevance/license/quality checks, creates one poster and a 4-second vertical video, and uploads that single video to YouTube as **Public**. If no valid stories/images are found, the pipeline stops before upload. The workflow requires a GitHub Actions secret named `YOUTUBE_TOKEN_JSON` containing the complete OAuth `token.json` JSON with a refresh token. Add it under **Settings → Secrets and variables → Actions**; never paste the token into chat or commit it.

To publish, open the repository's **Actions** tab, select **Build and publish Daily News Shorts**, and choose **Run workflow**. Each run may publish one new public video, containing one news poster displayed for 4 seconds. Review the run logs and saved artifact afterward. The metadata relevance checks are not visual confirmation, so public publishing without human visual review can still publish a mismatched scene if metadata matching is misleading.

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
