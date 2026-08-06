#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .venv/bin/activate ]]; then
  printf 'The virtual environment is missing. Run ./setup.sh first.\n' >&2
  exit 1
fi

# Homebrew's ffmpeg-full is keg-only. Prefer it automatically because the
# regular formula may omit the libass subtitle renderer.
if command -v brew >/dev/null 2>&1; then
  FFMPEG_FULL_PREFIX="$(brew --prefix ffmpeg-full 2>/dev/null || true)"
  if [[ -n "$FFMPEG_FULL_PREFIX" && -x "$FFMPEG_FULL_PREFIX/bin/ffmpeg" ]]; then
    export PATH="$FFMPEG_FULL_PREFIX/bin:$PATH"
  fi
fi

export PYTORCH_ENABLE_MPS_FALLBACK=1
source .venv/bin/activate
streamlit run app.py
