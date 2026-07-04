@echo off
setlocal

set "ROOT=%~dp0"
set "PGBIN=C:\Program Files\PostgreSQL\18\bin"
set "PGDATA=%ROOT%.devdata\pgdata"
set "SYS=%SystemRoot%\System32"

echo === Karavay: starting ===

echo Checking Postgres (port 5433)...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" status >nul 2>&1
if errorlevel 1 (
    echo Starting Postgres...
    "%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%ROOT%.devdata\pg.log" -o "-p 5433" start
) else (
    echo Postgres already running.
)

echo Checking backend (port 8000)...
"%SYS%\netstat.exe" -ano | "%SYS%\findstr.exe" ":8000 " | "%SYS%\findstr.exe" "LISTENING" >nul
if errorlevel 1 (
    echo Starting backend...
    start "Karavay Backend" cmd /k "cd /d "%ROOT%backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
) else (
    echo Backend already running.
)

echo Checking frontend (port 5173)...
"%SYS%\netstat.exe" -ano | "%SYS%\findstr.exe" ":5173 " | "%SYS%\findstr.exe" "LISTENING" >nul
if errorlevel 1 (
    echo Starting frontend...
    start "Karavay Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
) else (
    echo Frontend already running.
)

echo Waiting for servers to come up...
"%SYS%\timeout.exe" /t 6 /nobreak >nul

echo Opening the app in your browser...
start "" "http://localhost:5173"

endlocal
