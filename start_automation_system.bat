@echo off
REM Start BOTH Celery Worker and Beat in separate windows
REM This is the easiest way to start the complete automation system!

echo ====================================
echo Starting Automation System
echo ====================================
echo.
echo This will open 2 windows:
echo   1. Celery Worker (processes tasks)
echo   2. Celery Beat (checks schedules)
echo.
echo Keep BOTH windows open for automation to work!
echo.

cd /d "%~dp0"

REM Start Celery Worker in new window
start "Celery Worker" cmd /k "call venv\Scripts\activate.bat && celery -A config worker --loglevel=info --pool=solo"

REM Wait 3 seconds for worker to start
timeout /t 3 /nobreak

REM Start Celery Beat in new window
start "Celery Beat" cmd /k "call venv\Scripts\activate.bat && celery -A config beat --loglevel=info"

echo.
echo ✓ Started Celery Worker and Beat!
echo.
echo Check the 2 new windows to see if they started correctly.
echo To stop: Close both windows or press Ctrl+C in each.
echo.

pause
