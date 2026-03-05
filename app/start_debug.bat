@echo off
pip install -r requirements.txt -q
playwright install chromium
python app.py
pause
