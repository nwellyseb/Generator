from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .utils import ffmpeg_filter_exists, ffprobe_duration, run_command


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        proposed = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), proposed, font=font)
        if current and bbox[2] - bbox[0] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def create_placeholder_card(title: str, subtitle: str, destination: Path, size: tuple[int, int]) -> None:
    width, height = size
    image = Image.new("RGB", size, (15, 18, 24))
    draw = ImageDraw.Draw(image)
    title_font = _font(max(34, width // 25))
    subtitle_font = _font(max(20, width // 45))

    # Decorative lines add some visual structure without pretending to be cinema.
    margin = width // 12
    draw.rectangle((margin, height // 4, width - margin, height // 4 + 5), fill=(190, 156, 88))
    title_lines = _wrap(draw, title, title_font, width - 2 * margin)
    line_height = int(getattr(title_font, "size", 50) * 1.25)
    total_height = line_height * len(title_lines)
    y = (height - total_height) // 2
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=title_font, fill=(245, 243, 235))
        y += line_height

    if subtitle:
        subtitle_lines = _wrap(draw, subtitle, subtitle_font, width - 2 * margin)
        y += 24
        for line in subtitle_lines[:2]:
            bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            x = (width - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, font=subtitle_font, fill=(190, 190, 190))
            y += int(getattr(subtitle_font, "size", 26) * 1.3)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=95)


def render_scene(
    *,
    visual_path: Path,
    audio_path: Path,
    output_path: Path,
    width: int,
    height: int,
    fps: int = 30,
) -> float:
    duration = ffprobe_duration(audio_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    common_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )

    if visual_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(visual_path),
            "-i",
            str(audio_path),
            "-vf",
            f"{common_filter},zoompan=z='min(zoom+0.0005,1.06)':d={max(1, math.ceil(duration * fps))}:s={width}x{height}",
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(visual_path),
            "-i",
            str(audio_path),
            "-vf",
            common_filter,
        ]

    command.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    run_command(command)
    return duration


def concatenate_scenes(scene_paths: list[Path], output_path: Path) -> None:
    if not scene_paths:
        raise ValueError("No rendered scenes were provided.")
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.resolve().as_posix().replace(chr(39), "'\\''")}'" for path in scene_paths),
        encoding="utf-8",
    )
    try:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ]
        )
    except RuntimeError:
        # Re-encode fallback for installations that dislike stream-copy concatenation.
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ]
        )


def _escape_subtitle_path(path: Path) -> str:
    value = path.resolve().as_posix()
    value = value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return value


def finish_video(
    *,
    input_video: Path,
    output_video: Path,
    subtitles: Path | None = None,
    music: Path | None = None,
) -> str:
    """Finish the video and return the caption mode used.

    Returns ``burned`` when captions are rendered into the picture, ``embedded``
    when they are added as a selectable MP4 subtitle track, and ``none`` when no
    captions were requested. The embedded fallback keeps ordinary Homebrew
    FFmpeg builds useful even though they omit the libass subtitles filter.
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)
    filters: list[str] = []
    command = ["ffmpeg", "-y", "-i", str(input_video)]

    music_index: int | None = None
    if music:
        music_index = 1
        command.extend(["-stream_loop", "-1", "-i", str(music)])
        filters.append(f"[{music_index}:a]volume=0.08[music]")
        filters.append("[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")

    captions_mode = "none"
    subtitle_input_index: int | None = None
    if subtitles:
        if ffmpeg_filter_exists("subtitles"):
            style = (
                "FontName=Arial,FontSize=19,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00101010,BorderStyle=1,Outline=2,"
                "Shadow=0,MarginV=35,Alignment=2"
            )
            # Use an explicit option name. This is less fragile across FFmpeg
            # parser versions than relying on the unnamed first option.
            subtitle_filter = (
                f"[0:v]subtitles=filename='{_escape_subtitle_path(subtitles)}':"
                f"force_style='{style}'[vout]"
            )
            filters.append(subtitle_filter)
            captions_mode = "burned"
        else:
            subtitle_input_index = 2 if music else 1
            command.extend(["-i", str(subtitles)])
            captions_mode = "embedded"

    if filters:
        command.extend(["-filter_complex", ";".join(filters)])

    command.extend(["-map", "[vout]" if captions_mode == "burned" else "0:v:0"])
    command.extend(["-map", "[aout]" if music else "0:a:0"])
    if subtitle_input_index is not None:
        command.extend(["-map", f"{subtitle_input_index}:0"])

    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ]
    )
    if subtitle_input_index is not None:
        command.extend(
            [
                "-c:s",
                "mov_text",
                "-metadata:s:s:0",
                "language=eng",
                "-metadata:s:s:0",
                "title=English captions",
            ]
        )
    command.extend(["-movflags", "+faststart", "-shortest", str(output_video)])
    run_command(command)
    return captions_mode
