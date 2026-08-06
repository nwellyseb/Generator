from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from documentary_generator.commons import WikimediaCommonsClient
from documentary_generator.ollama_client import generate_plan, ollama_is_running
from documentary_generator.pexels import PexelsClient
from documentary_generator.pipeline import build_documentary
from documentary_generator.text import split_manual_script
from documentary_generator.tts import (
    KOKORO_VOICES,
    download_voice,
    espeak_available,
    kokoro_is_installed,
    list_macos_voices,
    macos_say_available,
    piper_is_installed,
    synthesize,
    voice_is_downloaded,
)
from documentary_generator.utils import executable_exists, ffmpeg_filter_exists, slugify


load_dotenv()
ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
PREVIEWS = ROOT / ".previews"

st.set_page_config(page_title="Free Documentary Generator 4", page_icon="🎬", layout="wide")
st.title("Free Local Documentary Generator 4")
st.caption("Natural Kokoro narration, real stock and archive visuals, captions, and FFmpeg rendering.")

with st.sidebar:
    st.header("Setup")
    ollama_host = st.text_input("Ollama host", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    model = st.text_input("Ollama model", os.getenv("OLLAMA_MODEL", "gemma3:4b"))

    st.subheader("Visual sources")
    pexels_key = st.text_input("Pexels API key", os.getenv("PEXELS_API_KEY", ""), type="password")
    use_wikimedia = st.checkbox(
        "Use Wikimedia Commons images",
        value=True,
        help="Adds archival and reference images without requiring an API key. Credits and licenses are saved.",
    )
    if st.button("Test Pexels media", use_container_width=True, disabled=not pexels_key.strip()):
        try:
            PREVIEWS.mkdir(exist_ok=True)
            client = PexelsClient(pexels_key)
            client.validate_key()
            asset = client.search_photo("computer history") or client.search_video("computer programming")
            if asset is None:
                st.error("Pexels accepted the key but returned no test media.")
            else:
                suffix = ".mp4" if asset.kind == "video" else ".jpg"
                preview_path = PREVIEWS / f"pexels_test{suffix}"
                client.download(asset, preview_path)
                if asset.kind == "video":
                    st.video(str(preview_path))
                else:
                    st.image(str(preview_path), caption=f"Pexels test: {asset.creator_name}")
                st.success("Pexels search and download work.")
        except Exception as exc:
            st.error(str(exc))

    if st.button("Test Wikimedia media", use_container_width=True, disabled=not use_wikimedia):
        try:
            PREVIEWS.mkdir(exist_ok=True)
            client = WikimediaCommonsClient()
            asset = client.search_image("computer history")
            if asset is None:
                st.error("Wikimedia was reachable but returned no usable test image.")
            else:
                preview_path = PREVIEWS / f"wikimedia_test{asset.file_extension}"
                client.download(asset, preview_path)
                st.image(str(preview_path), caption=f"Wikimedia test: {asset.title}")
                st.success("Wikimedia search and download work.")
        except Exception as exc:
            st.error(str(exc))

    st.subheader("Narrator")
    engine_options = ["Kokoro Local (recommended)"]
    if macos_say_available():
        engine_options.append("macOS Say (fallback)")
    if piper_is_installed():
        engine_options.append("Piper (legacy)")
    engine_label = st.selectbox("Narrator engine", engine_options, index=0)
    narrator_engine = {
        "Kokoro Local (recommended)": "kokoro",
        "macOS Say (fallback)": "macos",
        "Piper (legacy)": "piper",
    }[engine_label]

    piper_data_dir = Path(st.text_input("Legacy Piper voice folder", os.getenv("PIPER_DATA_DIR", "voices")))
    if not piper_data_dir.is_absolute():
        piper_data_dir = ROOT / piper_data_dir

    narrator_rate = 170
    narrator_speed = 0.92
    narrator_group_pause = 0.36
    narrator_paragraph_pause = 0.72

    if narrator_engine == "kokoro":
        voice_labels = list(KOKORO_VOICES)
        selected_voice_label = st.selectbox("Kokoro voice", voice_labels, index=0)
        narrator_voice = KOKORO_VOICES[selected_voice_label]
        narrator_speed = st.slider(
            "Delivery speed",
            min_value=0.80,
            max_value=1.12,
            value=0.92,
            step=0.01,
            help="Below 1.0 is slower. Around 0.90–0.96 usually suits documentary narration.",
        )
        narrator_group_pause = st.slider(
            "Pause between thought groups (seconds)", 0.15, 0.70, 0.36, step=0.01
        )
        narrator_paragraph_pause = st.slider(
            "Pause between paragraphs (seconds)", 0.40, 1.20, 0.72, step=0.02
        )
        if not kokoro_is_installed():
            st.error("Kokoro is not installed in this environment. Run ./setup.sh using Python 3.10–3.12.")
        elif not espeak_available():
            st.warning("espeak-ng was not found. Install it with: brew install espeak-ng")
        else:
            st.success("Kokoro is ready. The first preview downloads and caches the model files.")
    elif narrator_engine == "macos":
        available_voices = list_macos_voices()
        default_voice = "Samantha" if "Samantha" in available_voices else (available_voices[0] if available_voices else "")
        narrator_voice = st.selectbox("macOS voice", available_voices or [default_voice], index=0)
        narrator_rate = st.slider("Narration speed", 130, 220, 165, step=5)
    else:
        narrator_voice = st.text_input("Piper voice", os.getenv("PIPER_VOICE", "en_US-lessac-medium"))
        st.write("Piper voice:", "✅" if voice_is_downloaded(narrator_voice, piper_data_dir) else "⬇️ not downloaded")
        if st.button("Download Piper voice", use_container_width=True):
            with st.spinner("Downloading voice files..."):
                try:
                    download_voice(narrator_voice, piper_data_dir)
                    st.success("Voice downloaded.")
                except Exception as exc:
                    st.error(str(exc))

    if st.button("Preview narrator", use_container_width=True):
        PREVIEWS.mkdir(exist_ok=True)
        preview_path = PREVIEWS / "narrator_test.wav"
        preview_text = (
            "For decades, computers followed instructions written entirely by people. "
            "Then, quietly, the relationship began to change. Programs started helping humans write programs, "
            "and an old tool became something closer to a collaborator."
        )
        try:
            with st.spinner("Generating voice preview. The first Kokoro run may download its model..."):
                synthesize(
                    preview_text,
                    preview_path,
                    engine=narrator_engine,
                    voice=narrator_voice,
                    data_dir=piper_data_dir,
                    rate=narrator_rate,
                    speed=narrator_speed,
                    group_pause=narrator_group_pause,
                    paragraph_pause=narrator_paragraph_pause,
                )
            st.audio(str(preview_path))
            st.success("Narration passed the audio check. Listen before building the full documentary.")
        except Exception as exc:
            st.error(str(exc))

    ffmpeg_ready = executable_exists("ffmpeg") and executable_exists("ffprobe")
    st.subheader("Status")
    st.write("FFmpeg:", "✅" if ffmpeg_ready else "❌")
    if ffmpeg_ready:
        st.write("Caption burn-in:", "✅" if ffmpeg_filter_exists("subtitles") else "⚠️ selectable captions only")
    st.write("Kokoro:", "✅" if kokoro_is_installed() else "❌")
    st.write("espeak-ng:", "✅" if espeak_available() else "❌")
    st.write("Ollama:", "✅" if ollama_is_running(ollama_host) else "❌")

st.subheader("Documentary")
topic = st.text_input("Topic", placeholder="Example: How AI learned to code")
left, right = st.columns(2)
with left:
    target_minutes = st.slider("Target length", 1, 12, 3)
with right:
    resolution_label = st.selectbox("Resolution", ["1280×720", "1920×1080"], index=0)
resolution = (1920, 1080) if resolution_label.startswith("1920") else (1280, 720)

source_notes = st.text_area(
    "Verified source notes",
    height=180,
    placeholder="Paste checked notes, dates, quotations, and source summaries here.",
)

with st.expander("Use a manually written script instead of Ollama"):
    manual_script = st.text_area(
        "Manual script",
        height=180,
        help="Separate scenes with blank lines. When filled, Ollama is skipped.",
    )

st.subheader("Media and finishing")
user_media_uploads = st.file_uploader(
    "Optional photos or video clips",
    type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v"],
    accept_multiple_files=True,
    help="Files are assigned to scenes in upload order, then online free sources fill the remaining scenes.",
)
burn_captions = st.checkbox("Burn captions into the video", value=True)
allow_placeholders = st.checkbox(
    "Allow designed bridge cards when media is unavailable",
    value=False,
    help=(
        "When off, at least half the scenes must have real photos or video. "
        "A few bridge cards are permitted after that threshold; an all-card video is rejected."
    ),
)
music_upload = st.file_uploader("Optional background music", type=["mp3", "wav", "m4a", "aac", "ogg"])

if st.button("Build documentary", type="primary", use_container_width=True):
    if not topic.strip():
        st.error("Enter a documentary topic.")
        st.stop()
    if not executable_exists("ffmpeg") or not executable_exists("ffprobe"):
        st.error("FFmpeg and ffprobe must be installed and available in PATH.")
        st.stop()
    if narrator_engine == "kokoro" and not kokoro_is_installed():
        st.error("Kokoro is not installed. Run ./setup.sh, then restart the app.")
        st.stop()
    if narrator_engine == "kokoro" and not espeak_available():
        st.error("Install espeak-ng first: brew install espeak-ng")
        st.stop()
    if narrator_engine == "piper" and not voice_is_downloaded(narrator_voice, piper_data_dir):
        st.error("Download the selected Piper voice first, or choose Kokoro.")
        st.stop()
    if not pexels_key.strip() and not use_wikimedia and not user_media_uploads and not allow_placeholders:
        st.error("Enable Wikimedia, add a Pexels key, or upload media. Otherwise there is nothing to show besides typography.")
        st.stop()

    output_dir: Path | None = None
    try:
        if manual_script.strip():
            plan = split_manual_script(manual_script, topic)
        else:
            if not ollama_is_running(ollama_host):
                st.error("Ollama is not running. Start Ollama or provide a manual script.")
                st.stop()
            with st.spinner("Writing the documentary plan locally..."):
                plan = generate_plan(
                    topic=topic,
                    source_notes=source_notes,
                    target_minutes=target_minutes,
                    model=model,
                    host=ollama_host,
                )

        output_dir = OUTPUTS / f"{slugify(plan.title)}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)

        music_path = None
        if music_upload:
            music_path = output_dir / f"music{Path(music_upload.name).suffix.lower()}"
            music_path.write_bytes(music_upload.getbuffer())

        user_media_paths: list[Path] = []
        if user_media_uploads:
            uploaded_dir = output_dir / "uploaded_media"
            uploaded_dir.mkdir(exist_ok=True)
            for index, upload in enumerate(user_media_uploads, start=1):
                suffix = Path(upload.name).suffix.lower()
                path = uploaded_dir / f"upload_{index:03}{suffix}"
                path.write_bytes(upload.getbuffer())
                user_media_paths.append(path)

        progress_bar = st.progress(0.0)
        status = st.empty()

        def report(fraction: float, message: str) -> None:
            progress_bar.progress(fraction)
            status.write(message)

        result = build_documentary(
            plan=plan,
            output_dir=output_dir,
            pexels_api_key=pexels_key,
            narrator_voice=narrator_voice,
            piper_data_dir=piper_data_dir,
            resolution=resolution,
            burn_captions=burn_captions,
            music_path=music_path,
            progress=report,
            narrator_engine=narrator_engine,
            narrator_rate=narrator_rate,
            narrator_speed=narrator_speed,
            narrator_group_pause=narrator_group_pause,
            narrator_paragraph_pause=narrator_paragraph_pause,
            use_wikimedia=use_wikimedia,
            allow_placeholders=allow_placeholders,
            user_media=user_media_paths,
        )
        status.success("Documentary complete.")
        st.success(f"Real visuals: {result.real_visuals} · Placeholders: {result.placeholders}")
        if result.captions_mode == "embedded":
            st.warning(
                "This FFmpeg build lacks the libass subtitle filter, so captions were added as a selectable track. "
                "The captions.srt file is included for YouTube."
            )
        st.video(str(result.final_video))

        archive_base = output_dir.parent / output_dir.name
        archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=output_dir))
        with result.final_video.open("rb") as video_handle:
            st.download_button(
                "Download MP4",
                data=video_handle.read(),
                file_name=result.final_video.name,
                mime="video/mp4",
                use_container_width=True,
            )
        with archive_path.open("rb") as archive_handle:
            st.download_button(
                "Download full project ZIP",
                data=archive_handle.read(),
                file_name=archive_path.name,
                mime="application/zip",
                use_container_width=True,
            )
        st.info(f"Saved locally to: {output_dir}")
    except Exception as exc:
        st.error(str(exc))
        if output_dir is not None:
            report_path = output_dir / "media_search_report.txt"
            if report_path.exists():
                report_text = report_path.read_text(encoding="utf-8", errors="replace")
                with st.expander("Media search report", expanded=True):
                    st.code(report_text, language="text")
                    st.download_button(
                        "Download media search report",
                        data=report_text.encode("utf-8"),
                        file_name="media_search_report.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )
        with st.expander("Technical details"):
            st.exception(exc)
