@echo off
echo Activating venv and starting app...
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
set APP_SECRET_KEY=dev-secret
python app.py
