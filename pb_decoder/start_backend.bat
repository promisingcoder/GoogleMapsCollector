@echo off
echo Starting FastAPI backend on http://localhost:8000
cd /d "%~dp0.."
python -m uvicorn pb_decoder.api:app --host 0.0.0.0 --port 8000 --reload
