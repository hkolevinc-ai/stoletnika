@echo off
cd /d "%~dp0"
python scrape_stoletnika.py --refresh
pause
