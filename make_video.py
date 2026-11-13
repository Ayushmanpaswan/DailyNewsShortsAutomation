import argparse
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
POSTER_DIR = BASE_DIR / "output" / "posters"
OUTPUT = BASE_DIR / "output" / "daily_news_short.mp4"
DEFAULT_MUSIC = BASE_DIR / "assets" / "background_music.mp3"
SLIDE_SECONDS = 5
TRANSITION_SECONDS = 0.5


def main():
    parser = argparse.ArgumentParser(description="Create one vertical news slideshow.")
    parser.add_argument("--music", default=str(DEFAULT_MUSIC))
    parser.add_argument("--slide-seconds", type=int, default=SLIDE_SECONDS)
    parser.add_argument("--volume", type=float, default=0.20)
    args = parser.parse_args()

    OUTPUT.unlink(missing_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    posters = sorted(POSTER_DIR.glob("news_*.png"))
    music = Path(args.music)

    if not ffmpeg:
        raise SystemExit("ERROR: FFmpeg not found. Install FFmpeg first.")
    if not posters:
        raise SystemExit(f"ERROR: No individual posters found in {POSTER_DIR}")
    if args.slide_seconds <= 0:
        raise SystemExit("ERROR: --slide-seconds must be greater than zero.")
    if not 0.0 <= args.volume <= 1.0:
        raise SystemExit("ERROR: Volume must be between 0.0 and 1.0.")
    if not music.is_file():
        raise SystemExit(f"ERROR: Background music not found: {music}")

    total_duration = len(posters) * args.slide_seconds
    inputs = []
    for poster in posters:
        inputs.extend(["-loop", "1", "-framerate", "30", "-i", str(poster)])
    inputs.extend(["-stream_loop", "-1", "-i", str(music)])

    filters = []
    for index in range(len(posters)):
        filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,format=yuv420p,"
            f"trim=duration={args.slide_seconds},setpts=PTS-STARTPTS[v{index}]"
        )

    if len(posters) == 1:
        video_label = "[v0]"
    else:
        current = "[v0]"
        for index in range(1, len(posters)):
            output = f"xf{index}"
            offset = index * args.slide_seconds - TRANSITION_SECONDS
            filters.append(
                f"{current}[v{index}]xfade=transition=fade:duration="
                f"{TRANSITION_SECONDS}:offset={offset}[{output}]"
            )
            current = f"[{output}]"
        video_label = current

    fade_duration = min(1.5, total_duration / 4)
    fade_start = max(0, total_duration - fade_duration)
    filters.append(
        f"[{len(posters)}:a]volume={args.volume},"
        f"afade=t=in:st=0:d={fade_duration},"
        f"afade=t=out:st={fade_start}:d={fade_duration}[aout]"
    )

    command = [ffmpeg, "-hide_banner", "-y", *inputs, "-filter_complex",
               ";".join(filters), "-map", video_label, "-map",
               "[aout]", "-t", str(total_duration),
               "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(OUTPUT)]

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        OUTPUT.unlink(missing_ok=True)
        raise

    if not OUTPUT.is_file():
        raise SystemExit("ERROR: FFmpeg completed without creating the video.")
    print(f"SUCCESS: Created one {len(posters)}-slide video: {OUTPUT}")
    print(f"Resolution: 1080x1920; duration: {total_duration} seconds")


if __name__ == "__main__":
    main()
