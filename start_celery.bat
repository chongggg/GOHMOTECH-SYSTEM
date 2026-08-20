@echo off
REM Start Celery Worker and Beat for Automation System
REM Run this in a separate terminal window

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo ====================================
echo Starting Celery Worker
echo ====================================
echo.
echo This starts the Celery worker to process tasks
echo Keep this window open!
echo.
echo To stop: Press Ctrl+C
echo.

REM Start Celery worker only (on Windows, beat must run separately)
celery -A config worker --loglevel=info --pool=solo

pause
