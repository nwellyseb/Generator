@echo off
set PYTORCH_ENABLE_MPS_FALLBACK=1
call .venv\Scripts\activate
streamlit run app.py
