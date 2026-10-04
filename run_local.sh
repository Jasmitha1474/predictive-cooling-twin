#!/usr/bin/env bash
# Start backend (port 8000) and frontend (port 5173) locally. Ctrl+C stops both.
# Uses the first Python that has the backend packages installed (Anaconda's on this Mac).
set -e
cd "$(dirname "$0")"
PY=""
for c in /opt/anaconda3/bin/python3 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import uvicorn, fastapi, lightgbm, pandas, pyarrow" 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "No Python with the backend packages found. Run:  python3 -m pip install -r backend/requirements.txt"; exit 1
fi
for port in 8000 5173; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use (the site may already be running: open http://localhost:5173)."; exit 1
  fi
done
MODEL="${PCOOL_MODEL:-lstm:models_subset/SUBSET104_L0_lstm/model.pt}"
echo "Python: $PY   model: $MODEL"
(cd backend && OMP_NUM_THREADS=1 PCOOL_MODEL="$MODEL" "$PY" -m uvicorn app.main:app --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM
cd frontend && npx vite --port 5173 --open
