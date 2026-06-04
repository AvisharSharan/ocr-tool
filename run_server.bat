@echo off
cd /d "%~dp0"
"C:\Users\avishar\anaconda3\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000
