from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .commons import CommonsAsset, WikimediaCommonsClient
from .media import concatenate_scenes, create_placeholder_card, finish_video, render_scene
from .models import DocumentaryPlan
from .pexels import PexelsAsset, PexelsClient
from .text import write_srt
from .tts import synthesize


@dataclass(frozen=True)
class BuildResult:
    final_video: Path
    script_file: Path
    plan_file: Path
    subtitles_file: Path
    credits_file: Path
    description_file: Path
    captions_mode: str
    real_visuals: int
    placeholders: int


@dataclass(frozen=True)
class SelectedVisual:
    path: Path
    source: str
    credit_lines: tuple[str, ...]
    search_query: str = ""


ProgressCallback = Callable[[float, str], None]


_NOISE_WORDS = {
    "abstract",
    "animation",
    "archival",
    "cinematic",
    "close",
    "concept",
    "conceptual",
    "diagram",
    "dramatic",
    "early",
    "documentary",
    "illustrating",
    "illustration",
    "historical",
    "history",
    "image",
    "interface",
    "modern",
    "photo",
    "photograph",
    "representation",
    "screenshot",
    "shot",
    "simplified",
    "stock",
    "vintage",
    "footage",
    "visualization",
}

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "became", "become", "by",
    "for", "from", "how", "in", "into", "is", "it", "its", "learned", "of",
    "on", "or", "our", "that", "the", "their", "this", "through", "to", "was",
    "were", "what", "when", "where", "which", "while", "who", "why", "with",
}


def _progress(callback: ProgressCallback | None, fraction: float, message: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), message)


def _query_candidates(query: str, topic: str, narration: str = "", on_screen_text: str = "") -> list[str]:
    """Create literal, progressively broader media-library search phrases."""

    def clean(value: str) -> list[str]:
        value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", value)
        return [
            word
            for word in words
            if word.lower() not in _NOISE_WORDS
            and word.lower() not in _STOP_WORDS
            and len(word) > 1
        ]

    query_words = clean(query)
    text_words = clean(on_screen_text)
    topic_words = clean(topic)
    narration_words = clean(narration)

    # Preserve order while adding increasingly broad searches. Proper names and
    # acronyms become useful one- or two-word fallbacks instead of being trapped
    # inside a poetic stock-footage prompt.
    raw_candidates: list[str] = []
    original = re.sub(r"\s+", " ", query).strip(" ,.-")
    if original:
        raw_candidates.append(original)
    for words, limits in (
        (query_words, (7, 5, 3, 2, 1)),
        (text_words, (5, 3, 2, 1)),
        (topic_words, (6, 4, 3, 2)),
        (narration_words, (5, 3)),
    ):
        for limit in limits:
            if words:
                raw_candidates.append(" ".join(words[:limit]))

    # Topic-aware generic b-roll is still better than a blank scene when a
    # specific historical interface has no reusable image.
    combined = (query + " " + topic).lower()
    if any(term in combined for term in ("computer", "software", "code", "programming", "ai", "algorithm", "neural", "artificial intelligence", "machine learning")):
        raw_candidates.extend([
            "computer history",
            "computer programming",
            "software developer",
            "computer laboratory",
        ])

    result: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip(" ,.-")
        key = candidate.casefold()
        if candidate and key not in seen:
            result.append(candidate)
            seen.add(key)
        if len(result) >= 10:
            break
    return result


def _download_pexels(
    client: PexelsClient,
    query_candidates: list[str],
    destination_stem: Path,
    diagnostics: list[str],
) -> SelectedVisual | None:
    # Limit API consumption while still allowing broad recovery queries.
    for query in query_candidates[:5]:
        try:
            asset = client.search_video(query)
        except Exception as exc:
            diagnostics.append(f"  Pexels video [{query}]: ERROR - {exc}")
            break
        if asset:
            destination = destination_stem.with_suffix(".mp4")
            try:
                client.download(asset, destination)
            except Exception as exc:
                diagnostics.append(f"  Pexels video [{query}]: download failed - {exc}")
                continue
            diagnostics.append(f"  Pexels video [{query}]: selected {asset.page_url}")
            return SelectedVisual(
                path=destination,
                source="Pexels video",
                credit_lines=(
                    f"Pexels video by {asset.creator_name}",
                    f"Asset: {asset.page_url}",
                    f"Creator: {asset.creator_url}",
                ),
                search_query=query,
            )
        diagnostics.append(f"  Pexels video [{query}]: no result")

    for query in query_candidates[:5]:
        try:
            asset = client.search_photo(query)
        except Exception as exc:
            diagnostics.append(f"  Pexels photo [{query}]: ERROR - {exc}")
            break
        if asset:
            destination = destination_stem.with_suffix(".jpg")
            try:
                client.download(asset, destination)
            except Exception as exc:
                diagnostics.append(f"  Pexels photo [{query}]: download failed - {exc}")
                continue
            diagnostics.append(f"  Pexels photo [{query}]: selected {asset.page_url}")
            return SelectedVisual(
                path=destination,
                source="Pexels photo",
                credit_lines=(
                    f"Pexels photo by {asset.creator_name}",
                    f"Asset: {asset.page_url}",
                    f"Creator: {asset.creator_url}",
                ),
                search_query=query,
            )
        diagnostics.append(f"  Pexels photo [{query}]: no result")
    return None


def _download_commons(
    client: WikimediaCommonsClient,
    query_candidates: list[str],
    destination_stem: Path,
    diagnostics: list[str],
) -> SelectedVisual | None:
    for query in query_candidates:
        try:
            asset = client.search_image(query)
        except Exception as exc:
            diagnostics.append(f"  Wikimedia [{query}]: ERROR - {exc}")
            break
        if asset:
            destination = destination_stem.with_suffix(asset.file_extension)
            try:
                client.download(asset, destination)
            except Exception as exc:
                diagnostics.append(f"  Wikimedia [{query}]: download failed - {exc}")
                continue
            license_text = asset.license_name
            if asset.license_url:
                license_text += f" ({asset.license_url})"
            diagnostics.append(f"  Wikimedia [{query}]: selected {asset.title} - {asset.page_url}")
            return SelectedVisual(
                path=destination,
                source="Wikimedia Commons",
                credit_lines=(
                    f"Wikimedia Commons image: {asset.title}",
                    f"Creator: {asset.creator_name}",
                    f"License: {license_text}",
                    f"Source: {asset.page_url}",
                ),
                search_query=query,
            )
        diagnostics.append(f"  Wikimedia [{query}]: no result")
    return None


def _copy_user_media(path: Path, destination_stem: Path) -> SelectedVisual:
    suffix = path.suffix.lower() or ".bin"
    destination = destination_stem.with_suffix(suffix)
    shutil.copy2(path, destination)
    return SelectedVisual(
        path=destination,
        source="Creator upload",
        credit_lines=(f"Creator-provided media: {path.name}",),
    )


def build_documentary(
    *,
    plan: DocumentaryPlan,
    output_dir: Path,
    pexels_api_key: str,
    narrator_voice: str,
    piper_data_dir: Path,
    resolution: tuple[int, int] = (1280, 720),
    burn_captions: bool = True,
    music_path: Path | None = None,
    progress: ProgressCallback | None = None,
    narrator_engine: str = "kokoro",
    narrator_rate: int = 175,
    narrator_speed: float = 0.92,
    narrator_group_pause: float = 0.36,
    narrator_paragraph_pause: float = 0.72,
    use_wikimedia: bool = True,
    allow_placeholders: bool = False,
    user_media: list[Path] | None = None,
) -> BuildResult:
    width, height = resolution
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = output_dir / "audio"
    visual_dir = output_dir / "visuals"
    rendered_dir = output_dir / "rendered_scenes"
    for path in (audio_dir, visual_dir, rendered_dir):
        path.mkdir(exist_ok=True)

    plan_file = output_dir / "plan.json"
    plan_file.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    script_file = output_dir / "script.txt"
    script_file.write_text(
        "\n\n".join(f"SCENE {i + 1}\n{scene.narration}" for i, scene in enumerate(plan.scenes)),
        encoding="utf-8",
    )
    description_file = output_dir / "youtube_description.txt"
    description_file.write_text(plan.youtube_description, encoding="utf-8")
    media_report_file = output_dir / "media_search_report.txt"

    pexels = PexelsClient(pexels_api_key) if pexels_api_key.strip() else None
    commons = WikimediaCommonsClient() if use_wikimedia else None
    if pexels:
        _progress(progress, 0.01, "Checking Pexels access")
        pexels.validate_key()

    supplied_media = [Path(item) for item in (user_media or []) if Path(item).exists()]
    selected_visuals: list[SelectedVisual | None] = []
    missing_scenes: list[int] = []
    credits: list[str] = []
    diagnostics: list[str] = [
        f"Documentary: {plan.title}",
        f"Pexels enabled: {bool(pexels)}",
        f"Wikimedia enabled: {bool(commons)}",
        "",
    ]

    total = len(plan.scenes)
    for index, scene in enumerate(plan.scenes):
        scene_number = index + 1
        _progress(progress, 0.02 + 0.28 * (index / max(1, total)), f"Finding real media for scene {scene_number}/{total}")
        destination_stem = visual_dir / f"scene_{scene_number:03}"
        selected: SelectedVisual | None = None

        if index < len(supplied_media):
            selected = _copy_user_media(supplied_media[index], destination_stem)
            diagnostics.extend(
                [
                    f"Scene {scene_number}",
                    f"  Creator upload: {supplied_media[index].name}",
                    "  Result: Creator upload",
                    "",
                ]
            )
        else:
            candidates = _query_candidates(
                scene.visual_query,
                plan.title,
                narration=scene.narration,
                on_screen_text=scene.on_screen_text,
            )
            diagnostics.extend(
                [
                    f"Scene {scene_number}",
                    f"  Requested visual: {scene.visual_query}",
                    f"  Search candidates: {' | '.join(candidates)}",
                ]
            )
            # Stock footage first, archival/reference imagery second. Each source
            # logs every attempt so a blocked API no longer masquerades as "no image".
            if pexels:
                selected = _download_pexels(pexels, candidates, destination_stem, diagnostics)
            if selected is None and commons:
                selected = _download_commons(commons, candidates, destination_stem, diagnostics)
            diagnostics.append(f"  Result: {selected.source if selected else 'MISSING'}")
            diagnostics.append("")

        if selected is None:
            missing_scenes.append(scene_number)
        selected_visuals.append(selected)

    media_report_file.write_text("\n".join(diagnostics).strip() + "\n", encoding="utf-8")

    real_count_before_fallback = total - len(missing_scenes)
    real_ratio = real_count_before_fallback / max(1, total)
    # Do not abort merely because one obscure scene lacks a perfect archive image.
    # A few designed bridge cards are acceptable; an entire video made of them is not.
    if missing_scenes and not allow_placeholders and real_ratio < 0.50:
        scenes = ", ".join(str(number) for number in missing_scenes[:12])
        more = "…" if len(missing_scenes) > 12 else ""
        first_error = next((line.strip() for line in diagnostics if "ERROR -" in line), "")
        reason = f" First source error: {first_error}" if first_error else ""
        raise RuntimeError(
            "Too few real photos or videos were found. Missing scene(s): "
            f"{scenes}{more}. Found {real_count_before_fallback}/{total} real visual(s)."
            f"{reason} Full details were saved to: {media_report_file}. "
            "Use the Visual source tests in the sidebar before rebuilding."
        )

    placeholder_count = 0
    for index, selected in enumerate(selected_visuals):
        if selected is not None:
            credits.extend(
                [
                    f"Scene {index + 1}: {selected.source}",
                    f"Search query: {selected.search_query}" if selected.search_query else "",
                    *selected.credit_lines,
                    "",
                ]
            )
            continue
        placeholder_count += 1
        scene = plan.scenes[index]
        destination = visual_dir / f"scene_{index + 1:03}.png"
        create_placeholder_card(
            scene.on_screen_text or f"Scene {index + 1}",
            scene.visual_query,
            destination,
            resolution,
        )
        selected_visuals[index] = SelectedVisual(
            path=destination,
            source="Placeholder",
            credit_lines=("No external media available",),
        )

    rendered_paths: list[Path] = []
    durations: list[float] = []
    for index, (scene, selected) in enumerate(zip(plan.scenes, selected_visuals, strict=True)):
        assert selected is not None
        scene_number = index + 1
        base = 0.32 + 0.55 * (index / max(1, total))
        _progress(progress, base, f"Creating checked narration for scene {scene_number}/{total}")
        audio_path = audio_dir / f"scene_{scene_number:03}.wav"
        synthesize(
            scene.narration,
            audio_path,
            engine=narrator_engine,
            voice=narrator_voice,
            data_dir=piper_data_dir,
            rate=narrator_rate,
            speed=narrator_speed,
            group_pause=narrator_group_pause,
            paragraph_pause=narrator_paragraph_pause,
        )

        _progress(progress, base + 0.25 / max(1, total), f"Rendering scene {scene_number}/{total}")
        rendered_path = rendered_dir / f"scene_{scene_number:03}.mp4"
        duration = render_scene(
            visual_path=selected.path,
            audio_path=audio_path,
            output_path=rendered_path,
            width=width,
            height=height,
        )
        rendered_paths.append(rendered_path)
        durations.append(duration)

    _progress(progress, 0.89, "Joining scenes")
    joined_video = output_dir / "joined.mp4"
    concatenate_scenes(rendered_paths, joined_video)

    subtitles_file = output_dir / "captions.srt"
    write_srt(plan, durations, subtitles_file)
    credits_file = output_dir / "credits.txt"
    credits_file.write_text("\n".join(credits).strip() + "\n", encoding="utf-8")

    _progress(progress, 0.95, "Adding captions and final audio")
    final_video = output_dir / "final_documentary.mp4"
    captions_mode = finish_video(
        input_video=joined_video,
        output_video=final_video,
        subtitles=subtitles_file if burn_captions else None,
        music=music_path,
    )
    _progress(progress, 1.0, "Documentary complete")

    manifest = {
        "title": plan.title,
        "resolution": [width, height],
        "scenes": total,
        "captions_requested": burn_captions,
        "captions_mode": captions_mode,
        "burned_captions": captions_mode == "burned",
        "used_pexels": bool(pexels),
        "used_wikimedia": bool(commons),
        "narrator_engine": narrator_engine,
        "narrator_voice": narrator_voice,
        "narrator_speed": narrator_speed,
        "narrator_group_pause": narrator_group_pause,
        "narrator_paragraph_pause": narrator_paragraph_pause,
        "real_visuals": total - placeholder_count,
        "placeholders": placeholder_count,
        "media_search_report": str(media_report_file),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return BuildResult(
        final_video=final_video,
        script_file=script_file,
        plan_file=plan_file,
        subtitles_file=subtitles_file,
        credits_file=credits_file,
        description_file=description_file,
        captions_mode=captions_mode,
        real_visuals=total - placeholder_count,
        placeholders=placeholder_count,
    )
