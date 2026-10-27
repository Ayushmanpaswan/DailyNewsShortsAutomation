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
        description="Create a vertical news video with background music."
    )

    parser.add_argument(
        "--music",
        default=str(DEFAULT_MUSIC),
        help="Path to background music file",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=6,
        help="Video duration in seconds",
    )

    parser.add_argument(
        "--volume",
        type=float,
        default=0.20,
        help="Music volume between 0.0 and 1.0",
    )

    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        raise SystemExit(
            "ERROR: FFmpeg not found. Install FFmpeg first."
        )

    if not POSTER.is_file():
        raise SystemExit(
            f"ERROR: Poster not found: {POSTER}\n"
            "Run poster_generator.py first."
        )

    if args.duration <= 0:
        raise SystemExit("ERROR: Duration must be greater than zero.")

    if not 0.0 <= args.volume <= 1.0:
        raise SystemExit(
            "ERROR: Volume must be between 0.0 and 1.0."
        )

    music = Path(args.music)

    if not music.is_file():
        raise SystemExit(
            f"ERROR: Background music not found: {music}\n"
            "Add a licensed MP3 file at assets/background_music.mp3."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    fade_duration = min(1.5, args.duration / 4)
    fade_start = max(0, args.duration - fade_duration)

    audio_filter = (
        f"volume={args.volume},"
        f"afade=t=in:st=0:d={fade_duration},"
        f"afade=t=out:st={fade_start}:d={fade_duration}"
    )

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",

        # Poster input
        "-loop", "1",
        "-framerate", "30",
        "-i", str(POSTER),

        # Repeat music if it is shorter than the video
        "-stream_loop", "-1",
        "-i", str(music),

        # Video settings
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(args.duration),
        "-vf",
        (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,"
            "format=yuv420p"
        ),
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",

        # Audio settings
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", audio_filter,

        # MP4 compatibility
        "-movflags", "+faststart",
        "-shortest",
        str(OUTPUT),
    ]

    print(f"Poster: {POSTER}")
    print(f"Music: {music}")
    print(f"Duration: {args.duration} seconds")
    print(f"Music volume: {args.volume}")

    subprocess.run(cmd, check=True)

    print("\nSUCCESS: Video created with background music.")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
