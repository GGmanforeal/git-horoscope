@echo off
rem Double-click: read the stars of a demo repository.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m githoroscope --demo
pause
