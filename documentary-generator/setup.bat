@echo off
setlocal
py -3.12 -m venv .venv
if errorlevel 1 (
  echo Python 3.12 is required for Kokoro. Install it, then run setup.bat again.
  exit /b 1
)
call .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if not exist .env copy .env.example .env
where espeak-ng >nul 2>nul
if errorlevel 1 echo Install espeak-ng from the official espeak-ng releases before using Kokoro.
echo Setup complete. Run run.bat.
