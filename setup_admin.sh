#!/usr/bin/env bash
# Sets up a Python virtual environment and installs all admin UI dependencies.
# Run from the project root:  bash setup_admin.sh

set -e

VENV_DIR=".venv"

echo "==> Creating virtual environment in $VENV_DIR …"
python3 -m venv "$VENV_DIR"

echo "==> Activating virtual environment…"
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip…"
pip install --upgrade pip

echo "==> Installing admin UI dependencies…"
pip install -r admin/requirements.txt

echo "==> Installing backend dependencies…"
pip install -r backend/requirements.txt

echo ""
echo "✓ Setup complete."
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in your API keys:"
echo "       cp .env.example .env"
echo ""
echo "  2. Activate the venv (in every new terminal session):"
echo "       source .venv/bin/activate"
echo ""
echo "  3. Launch the Admin UI:"
echo "       streamlit run admin/app.py"
echo ""
echo "  4. Launch the FastAPI backend (separate terminal):"
echo "       uvicorn backend.main:app --reload"
