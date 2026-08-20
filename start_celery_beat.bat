@echo off
REM Start Celery Beat (Scheduler) for Automation System
REM Run this in a separate terminal window AFTER starting the worker

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo ====================================
echo Starting Celery Beat (Scheduler)
echo ====================================
echo.
echo This checks schedules every minute
echo Keep this window open!
echo.
echo To stop: Press Ctrl+C
echo.

REM Start Celery beat scheduler
celery -A config beat --loglevel=info

pause
