#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

case "${1:-run}" in
  install)
    python3 -m venv backend/venv
    backend/venv/bin/pip install -r backend/requirements.txt
    echo "OK: installed"
    ;;
  run)
    exec backend/venv/bin/uvicorn main:app --reload --port 8000 --app-dir backend
    ;;
  stop)
    pkill -f "uvicorn main:app" || true
    echo "OK: stopped"
    ;;
  *)
    echo "Ishlatish: ./run.sh [install|run|stop]"
    ;;
esac
