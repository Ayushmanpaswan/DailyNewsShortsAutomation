
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def run_step(description, script):
    print(f"\n{'=' * 45}")
    print(description)
    print("=" * 45)

    script_path = BASE_DIR / script

    if not script_path.exists():
        raise FileNotFoundError(f"File not found: {script_path}")

    subprocess.run(
        [PYTHON, str(script_path)],
        cwd=BASE_DIR,
        check=True
    )


def main():
    try:
        run_step("Step 1: Fetching news", "fetch_news.py")
        run_step("Step 2: Generating poster", "poster_generator.py")
        run_step("Step 3: Creating video", "make_video.py")

        print("\nSUCCESS! Video creation completed.")
        print(BASE_DIR / "output" / "daily_news_short.mp4")

    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
