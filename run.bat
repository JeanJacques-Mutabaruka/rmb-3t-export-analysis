@echo off
REM Single-command launcher (Windows).
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ from python.org and tick "Add to PATH".
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo Installing dependencies ^(first run only, ~1 min^)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting RMB 3T Export Intelligence...
echo Open http://localhost:8501 if your browser does not launch automatically.
echo.
streamlit run app/Home.py
pause
