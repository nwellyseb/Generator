"""Run manually: python tests/caption_finish_smoke_test.py"""
from pathlib import Path

import documentary_generator.media as media
from documentary_generator.utils import run_command

root = Path(__file__).resolve().parents[1] / "outputs" / "caption-finish-smoke-test"
root.mkdir(parents=True, exist_ok=True)
joined = root / "joined.mp4"
music = root / "music.wav"
subtitles = root / "captions.srt"

run_command(
    [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=640x360:d=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(joined),
    ]
)
run_command(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1", str(music)])
subtitles.write_text(
    "1\n00:00:00,000 --> 00:00:01,400\nCaption test\n",
    encoding="utf-8",
)

if media.ffmpeg_filter_exists("subtitles"):
    mode = media.finish_video(
        input_video=joined,
        output_video=root / "burned.mp4",
        subtitles=subtitles,
    )
    assert mode == "burned"

original = media.ffmpeg_filter_exists
media.ffmpeg_filter_exists = lambda name: False
try:
    mode = media.finish_video(
        input_video=joined,
        output_video=root / "embedded.mp4",
        subtitles=subtitles,
        music=music,
    )
    assert mode == "embedded"
finally:
    media.ffmpeg_filter_exists = original

print("Caption finishing smoke test passed.")
