#!/usr/bin/env bash
set -euo pipefail

valid_python() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 13) else 1)
PY
}

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && valid_python "$candidate"; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]] && command -v brew >/dev/null 2>&1; then
  printf 'Kokoro requires Python 3.10–3.12. Installing Python 3.12 with Homebrew...\n'
  brew install python@3.12
  PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12"
fi

if [[ -z "$PYTHON_BIN" ]] || ! valid_python "$PYTHON_BIN"; then
  printf 'No compatible Python was found. Install Python 3.12, then run this script again.\n' >&2
  exit 1
fi

printf 'Using %s\n' "$($PYTHON_BIN --version)"

if [[ -d .venv ]]; then
  if ! .venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 13) else 1)
PY
  then
    printf 'Replacing the old virtual environment because its Python version cannot run Kokoro.\n'
    rm -rf .venv
  fi
fi

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
cp -n .env.example .env || true

if command -v brew >/dev/null 2>&1 && ! command -v espeak-ng >/dev/null 2>&1; then
  printf '\nInstalling espeak-ng, which Kokoro uses for pronunciation fallback...\n'
  brew install espeak-ng
fi

if ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1; then
  printf '\nWARNING: espeak-ng is missing. On macOS run: brew install espeak-ng\n'
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  printf '\nWARNING: FFmpeg is missing. On macOS run: brew install ffmpeg-full\n'
fi

if command -v ffmpeg >/dev/null 2>&1; then
  if ! ffmpeg -hide_banner -filters 2>/dev/null | grep -Eq '^[[:space:]]*[.A-Z]+[[:space:]]+subtitles[[:space:]]+'; then
    printf '\nNote: this FFmpeg build cannot burn captions. On macOS install ffmpeg-full:\n'
    printf '  brew install ffmpeg-full\n'
    printf 'The app will otherwise embed selectable captions and still create the MP4.\n'
  fi
fi

printf '\nSetup complete. Start with: ./run.sh\n'
printf 'The first Kokoro preview downloads and caches the model files.\n'
