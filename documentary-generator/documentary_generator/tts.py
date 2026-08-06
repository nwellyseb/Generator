from __future__ import annotations

import importlib.util
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import wave
from array import array
from functools import lru_cache
from pathlib import Path

from .utils import run_command


KOKORO_VOICES: dict[str, str] = {
    "Warm American female — Heart": "af_heart",
    "Expressive American female — Bella": "af_bella",
    "Calm American female — Nicole": "af_nicole",
    "Measured American male — Fenrir": "am_fenrir",
    "Conversational American male — Michael": "am_michael",
    "Warm British female — Emma": "bf_emma",
    "British male — Fable": "bm_fable",
}


def kokoro_is_installed() -> bool:
    return importlib.util.find_spec("kokoro") is not None and importlib.util.find_spec("soundfile") is not None


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


def piper_is_installed() -> bool:
    return importlib.util.find_spec("piper") is not None


def download_voice(voice: str, data_dir: Path) -> None:
    if not piper_is_installed():
        raise RuntimeError("Piper is not installed. Kokoro is the recommended narrator in version 4.")
    data_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            sys.executable,
            "-m",
            "piper.download_voices",
            "--data-dir",
            str(data_dir),
            voice,
        ]
    )


def voice_is_downloaded(voice: str, data_dir: Path) -> bool:
    return (data_dir / f"{voice}.onnx").exists() and (data_dir / f"{voice}.onnx.json").exists()


def macos_say_available() -> bool:
    return platform.system() == "Darwin" and shutil.which("say") is not None


def list_macos_voices() -> list[str]:
    if not macos_say_available():
        return []
    result = run_command(["say", "-v", "?"])
    voices: list[str] = []
    for line in result.stdout.splitlines():
        match = re.match(r"^(.*?)\s+[a-z]{2}_[A-Z]{2}\s+#", line.strip())
        name = (match.group(1) if match else line.split(maxsplit=1)[0]).strip()
        if name and name not in voices:
            voices.append(name)
    return voices


def _normalise_audio(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            "-af",
            "highpass=f=65,lowpass=f=15000,loudnorm=I=-16:TP=-1.5:LRA=8",
            str(destination),
        ]
    )


def _validate_audio(path: Path) -> None:
    """Reject empty, clipped, or broadband-noise narration before video rendering."""
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except (wave.Error, OSError) as exc:
        raise RuntimeError(f"Narration audio could not be read: {path}") from exc

    if sample_width != 2:
        raise RuntimeError("Narration validation expects 16-bit PCM audio.")

    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    if channels > 1:
        samples = array("h", samples[::channels])

    if len(samples) < sample_rate // 2:
        raise RuntimeError("Narration audio is unexpectedly short.")

    peak = max(abs(value) for value in samples)
    if peak < 300:
        raise RuntimeError("Narration audio is silent or nearly silent.")

    clipping = sum(1 for value in samples if abs(value) >= 32760) / len(samples)
    if clipping > 0.01:
        raise RuntimeError("Narration audio is heavily clipped.")

    window = max(1, sample_rate // 2)
    active_windows = 0
    noise_windows = 0
    for start in range(0, len(samples) - window + 1, window):
        block = samples[start : start + window]
        rms = math.sqrt(sum(float(value) * float(value) for value in block) / len(block)) / 32768.0
        if rms < 0.02:
            continue
        active_windows += 1
        crossings = 0
        previous_positive = block[0] >= 0
        for value in block[1:]:
            positive = value >= 0
            if positive != previous_positive:
                crossings += 1
            previous_positive = positive
        zcr = crossings / max(1, len(block) - 1)
        if zcr > 0.16 and rms > 0.08:
            noise_windows += 1

    if active_windows and noise_windows / active_windows > 0.20:
        raise RuntimeError(
            "Narration contains broadband digital noise. Try Kokoro or macOS Say, "
            "and regenerate this scene before rendering."
        )


def _prepare_text(text: str) -> str:
    text = text.replace("&", " and ")
    text = re.sub(r"(?<=\d)%(?=\s|$|[.,;:!?])", " percent", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentence_groups(paragraph: str, *, min_words: int = 28, max_words: int = 105) -> list[str]:
    """Bundle sentences into natural breath groups.

    Kokoro is less reliable on tiny utterances and may rush extremely long ones, so
    the generator avoids both extremes rather than mechanically synthesising every
    sentence in isolation.
    """
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", paragraph.strip()) if item.strip()]
    if not sentences:
        return []

    groups: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words >= min_words and current_words + sentence_words > max_words:
            groups.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        groups.append(" ".join(current))

    # A tiny trailing group usually sounds worse than one slightly longer group.
    if len(groups) >= 2 and len(groups[-1].split()) < min_words // 2:
        groups[-2] = f"{groups[-2]} {groups[-1]}"
        groups.pop()
    return groups


def narration_groups(text: str) -> list[tuple[str, bool]]:
    """Return (text, paragraph_end) groups for Kokoro synthesis."""
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", text.strip()) if item.strip()]
    result: list[tuple[str, bool]] = []
    for paragraph in paragraphs:
        groups = _sentence_groups(_prepare_text(paragraph))
        for index, group in enumerate(groups):
            result.append((group, index == len(groups) - 1))
    return result


def _kokoro_language_code(voice: str) -> str:
    if voice.startswith(("bf_", "bm_")):
        return "b"
    return "a"


@lru_cache(maxsize=2)
def _load_kokoro_pipeline(language_code: str):
    if not kokoro_is_installed():
        raise RuntimeError(
            "Kokoro is not installed. Run ./setup.sh with Python 3.10, 3.11, or 3.12."
        )
    # Apple Silicon can use MPS where supported while safely falling back for
    # operations that PyTorch has not implemented on MPS.
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    from kokoro import KPipeline

    return KPipeline(lang_code=language_code)


def _synthesize_kokoro(
    text: str,
    output_wav: Path,
    *,
    voice: str,
    speed: float,
    group_pause: float,
    paragraph_pause: float,
) -> None:
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Kokoro requires numpy and soundfile. Run ./setup.sh again.") from exc

    pipeline = _load_kokoro_pipeline(_kokoro_language_code(voice))
    groups = narration_groups(text)
    if not groups:
        raise RuntimeError("There is no narration text to synthesize.")

    sample_rate = 24000
    pieces = []
    for group_text, paragraph_end in groups:
        generated_any = False
        generator = pipeline(group_text, voice=voice, speed=float(speed), split_pattern=r"\n+")
        for _, _, audio in generator:
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            values = np.asarray(audio, dtype=np.float32).reshape(-1)
            if values.size:
                pieces.append(values)
                generated_any = True
        if not generated_any:
            raise RuntimeError(f"Kokoro returned no audio for: {group_text[:80]}")
        pause = paragraph_pause if paragraph_end else group_pause
        if pause > 0:
            pieces.append(np.zeros(int(sample_rate * pause), dtype=np.float32))

    combined = np.concatenate(pieces)
    peak = float(np.max(np.abs(combined))) if combined.size else 0.0
    if peak > 1.0:
        combined = combined / peak
    sf.write(str(output_wav), combined, sample_rate, subtype="PCM_16")


def synthesize(
    text: str,
    output_wav: Path,
    *,
    engine: str,
    voice: str,
    data_dir: Path,
    rate: int = 175,
    speed: float = 0.92,
    group_pause: float = 0.36,
    paragraph_pause: float = 0.72,
) -> None:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="documentary-tts-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        raw_output = temp_dir / ("speech.aiff" if engine == "macos" else "speech.wav")

        if engine == "kokoro":
            _synthesize_kokoro(
                text,
                raw_output,
                voice=voice,
                speed=speed,
                group_pause=group_pause,
                paragraph_pause=paragraph_pause,
            )
        elif engine == "macos":
            if not macos_say_available():
                raise RuntimeError("The macOS Say narrator is not available on this computer.")
            command = ["say", "-r", str(rate), "-o", str(raw_output)]
            if voice.strip():
                command.extend(["-v", voice.strip()])
            command.append(_prepare_text(text))
            run_command(command)
        elif engine == "piper":
            if not piper_is_installed():
                raise RuntimeError("Piper is not installed. Use Kokoro or macOS Say instead.")
            if not voice_is_downloaded(voice, data_dir):
                raise RuntimeError(f"Piper voice is not downloaded: {voice}")
            input_file = temp_dir / "narration.txt"
            input_file.write_text(_prepare_text(text) + "\n", encoding="utf-8")
            run_command(
                [
                    sys.executable,
                    "-m",
                    "piper",
                    "--data-dir",
                    str(data_dir),
                    "-m",
                    voice,
                    "-f",
                    str(raw_output),
                    "--sentence-silence",
                    str(group_pause),
                    "--input-file",
                    str(input_file),
                ]
            )
        else:
            raise ValueError(f"Unknown narrator engine: {engine}")

        _normalise_audio(raw_output, output_wav)
        _validate_audio(output_wav)
