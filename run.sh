#!/usr/bin/env bash
# Single-command launcher (macOS / Linux).
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "Python 3 not found. Install Python 3.10+ and try again."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies (first run only, ~1 min)..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo ""
echo "Starting RMB 3T Export Intelligence..."
echo "Open http://localhost:8501 if your browser does not launch automatically."
echo ""
exec streamlit run app/Home.py
