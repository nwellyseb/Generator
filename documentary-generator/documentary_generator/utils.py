from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def slugify(value: str, max_length: int = 70) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return (value[:max_length].rstrip("-") or "documentary")


def executable_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required program was not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{detail}") from exc



@lru_cache(maxsize=None)
def ffmpeg_filter_exists(name: str) -> bool:
    """Return whether the active FFmpeg build exposes a named filter."""
    if not executable_exists("ffmpeg"):
        return False
    try:
        result = run_command(["ffmpeg", "-hide_banner", "-filters"])
    except RuntimeError:
        return False
    pattern = re.compile(rf"^\s*[.A-Z]+\s+{re.escape(name)}\s+", re.MULTILINE)
    return bool(pattern.search(result.stdout))


def ffprobe_duration(path: Path) -> float:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return max(0.1, float(result.stdout.strip()))
    except ValueError as exc:
        raise RuntimeError(f"Could not determine media duration: {path}") from exc
