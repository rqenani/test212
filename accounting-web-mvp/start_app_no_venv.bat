\
@echo off
setlocal
title Qenani Ledger - NO VENV
echo Using system Python (no virtualenv).
py -V
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
set APP_SECRET_KEY=dev-secret
set PORT=5000
set HOST=127.0.0.1
py app.py
