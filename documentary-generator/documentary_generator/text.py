from __future__ import annotations

import re
from pathlib import Path

from .models import DocumentaryPlan, Scene


def split_manual_script(script: str, topic: str) -> DocumentaryPlan:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]
    if not paragraphs:
        paragraphs = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if not paragraphs:
        raise ValueError("The manual script is empty.")

    scenes = [
        Scene(
            narration=paragraph,
            visual_query=f"{topic} documentary cinematic",
            on_screen_text=topic if index == 0 else "",
        )
        for index, paragraph in enumerate(paragraphs)
    ]
    return DocumentaryPlan(
        title=topic.strip() or "Untitled Documentary",
        youtube_description=f"A short documentary about {topic.strip()}.",
        scenes=scenes,
    )


def _timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _caption_chunks(text: str, target_words: int = 9) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        sentence_end = bool(re.search(r"[.!?][\"')\]]?$", word))
        if len(current) >= target_words or (sentence_end and len(current) >= 5):
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def write_srt(plan: DocumentaryPlan, durations: list[float], output_path: Path) -> None:
    if len(plan.scenes) != len(durations):
        raise ValueError("Scene and duration counts do not match.")

    lines: list[str] = []
    cursor = 0.0
    caption_index = 1
    for scene, duration in zip(plan.scenes, durations, strict=True):
        chunks = _caption_chunks(scene.narration)
        word_total = max(1, sum(len(chunk.split()) for chunk in chunks))
        scene_cursor = cursor
        for chunk in chunks:
            share = len(chunk.split()) / word_total
            chunk_duration = max(0.8, duration * share)
            end = min(cursor + duration, scene_cursor + chunk_duration)
            lines.extend(
                [
                    str(caption_index),
                    f"{_timestamp(scene_cursor)} --> {_timestamp(end)}",
                    chunk,
                    "",
                ]
            )
            caption_index += 1
            scene_cursor = end
        cursor += duration

    output_path.write_text("\n".join(lines), encoding="utf-8")
