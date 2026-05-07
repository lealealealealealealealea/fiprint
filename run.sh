#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git"
APP_DIR="$HOME/.print-upload-server"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Installing/updating print-upload-server..."

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. Install it first:"
  echo "  sudo apt install git"
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 is required. Install it first:"
  echo "  sudo apt install python3"
  exit 1
fi

if [ -d "$APP_DIR/.git" ]; then
  echo "Updating existing repo in $APP_DIR"
  git -C "$APP_DIR" pull --ff-only
else
  echo "Cloning repo to $APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
fi

echo "Installing Python dependency: qrcode"
"$PYTHON_BIN" -m pip install --user qrcode

echo
echo "Starting server..."
exec "$PYTHON_BIN" main.py
