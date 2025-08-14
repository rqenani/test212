\
@echo off
setlocal
title Qenani Ledger - PORT 5001
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
set APP_SECRET_KEY=dev-secret
set PORT=5001
set HOST=127.0.0.1
python app.py
