
import argparse
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POSTER = BASE_DIR / "output" / "daily_news_poster.png"
OUTPUT = BASE_DIR / "output" / "daily_news_short.mp4"
DEFAULT_MUSIC = BASE_DIR / "assets" / "background_music.mp3"


def main():
    parser = argparse.ArgumentParser(
        description="Create a vertical news video with optional background music."
    )
    parser.add_argument("--music", default=str(DEFAULT_MUSIC))
    parser.add_argument("--duration", type=int, default=6)
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg not found. Install FFmpeg and add it to PATH.")

    if not POSTER.exists():
        raise SystemExit(f"Poster not found: {POSTER}")

    if args.duration <= 0:
        raise SystemExit("Duration must be greater than zero.")

    music = Path(args.music)

    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-framerate", "30", "-i", str(POSTER),
    ]

    if music.is_file():
        cmd += [
            "-stream_loop", "-1", "-i", str(music),
            "-t", str(args.duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p",
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-af", "volume=0.20,afade=t=out:st=4.5:d=1.5",
            "-shortest",
            "-movflags", "+faststart",
            str(OUTPUT),
        ]
        print(f"Adding background music: {music}")
    else:
        cmd += [
            "-t", str(args.duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p",
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "22",
            "-an",
            "-movflags", "+faststart",
            str(OUTPUT),
        ]
        print(f"Music not found: {music}. Creating video without audio.")

    subprocess.run(cmd, check=True)
    print(f"Video created: {OUTPUT}")


if __name__ == "__main__":
    main()
