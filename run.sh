#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/lealealealealealealealea/fiprint.git"
APP_DIR="$HOME/.print-upload-server"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCREEN_NAME="${SCREEN_NAME:-print-upload-server}"

cmd="${1:-start}"

if ! command -v screen >/dev/null 2>&1; then
  echo "screen is required. Install it first:"
  echo "  sudo apt install screen"
  exit 1
fi

if [ "$cmd" = "stop" ]; then
  echo "Stopping screen session: $SCREEN_NAME"

  if screen -list | grep -q "[.]${SCREEN_NAME}[[:space:]]"; then
    screen -S "$SCREEN_NAME" -X quit
    echo "Stopped."
  else
    echo "No running screen session named $SCREEN_NAME."
  fi

  exit 0
fi

if [ "$cmd" != "start" ] && [ "$cmd" != "restart" ]; then
  echo "Usage:"
  echo "  bash run.sh"
  echo "  bash run.sh start"
  echo "  bash run.sh restart"
  echo "  bash run.sh stop"
  exit 1
fi

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

if screen -list | grep -q "[.]${SCREEN_NAME}[[:space:]]"; then
  if [ "$cmd" = "restart" ]; then
    echo "Stopping existing screen session: $SCREEN_NAME"
    screen -S "$SCREEN_NAME" -X quit
    sleep 1
  else
    echo "Already running in screen session: $SCREEN_NAME"
    echo
    echo "Attach:"
    echo "  screen -r $SCREEN_NAME"
    echo
    echo "Stop:"
    echo "  bash $APP_DIR/run.sh stop"
    exit 0
  fi
fi

echo "Starting server in background screen session: $SCREEN_NAME"

screen -dmS "$SCREEN_NAME" bash -lc "
  cd '$APP_DIR'
  exec '$PYTHON_BIN' main.py
"

echo "Started."
echo
echo "Attach to logs / QR setup:"
echo "  screen -r $SCREEN_NAME"
echo
echo "Detach from screen:"
echo "  Ctrl-a then d"
echo
echo "Stop:"
echo "  bash $APP_DIR/run.sh stop"
