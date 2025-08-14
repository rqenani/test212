\
@echo off
setlocal
title Qenani Ledger - DEBUG
if not exist logs mkdir logs
echo === Starting (with console log) ===
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip > logs\pip.log 2>&1
pip install -r requirements.txt >> logs\pip.log 2>&1
set APP_SECRET_KEY=dev-secret
set PORT=5000
set HOST=127.0.0.1
echo Launching app... (see logs\run.log)
python app.py > logs\run.log 2>&1
type logs\run.log
echo.
echo [INFO] If window closed, open logs\run.log for details.
pause
