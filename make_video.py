import argparse
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POSTER = BASE_DIR / "output" / "daily_news_poster.png"
OUTPUT = BASE_DIR / "output" / "daily_news_short.mp4"
DEFAULT_MUSIC = BASE_DIR / "assets" / "background_music.mp3"

def main():
    parser = argparse.ArgumentParser(description="Create a 6-second vertical YouTube Shorts video.")
    parser.add_argument("--music", default=str(DEFAULT_MUSIC), help="Path to licensed music MP3/WAV file.")
    parser.add_argument("--duration", type=int, default=6, help="Video duration in seconds (default: 6).")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg not found. Install FFmpeg and add it to PATH.")
    if not POSTER.exists():
        raise SystemExit(f"Poster not found: {POSTER}. Run poster_generator.py first.")

    music = Path(args.music)
    if music.exists():
        cmd = [
            ffmpeg, "-y", "-loop", "1", "-i", str(POSTER), "-i", str(music),
            "-t", str(args.duration), "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(OUTPUT)
        ]
    else:
        print(f"Music file not found ({music}). Creating video without audio.")
        cmd = [
            ffmpeg, "-y", "-loop", "1", "-i", str(POSTER),
            "-t", str(args.duration), "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-an", "-movflags", "+faststart", str(OUTPUT)
        ]
    subprocess.run(cmd, check=True)
    print(f"Video created: {OUTPUT}")

if __name__ == "__main__":
    main()
