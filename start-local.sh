#!/usr/bin/env bash

set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="$root/.venv/bin/python"

cd "$root"

if [[ ! -x "$python" ]]; then
    echo "Creating Python environment..."
    python3 -m venv "$root/.venv"
fi

if ! "$python" -c "import agentprobe" 2>/dev/null; then
    echo "Installing backend dependencies..."
    "$python" -m pip install -e ".[dev]"
fi

if [[ ! -d "$root/apps/web/node_modules" ]]; then
    echo "Installing dashboard dependencies..."
    npm install --prefix "$root/apps/web"
fi

export AGENTPROBE_STORAGE_BACKEND=memory
export AGENTPROBE_TEMPLATE_BACKEND=local
export AGENTPROBE_DATASET_ENABLED=false
export NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

api_pid=""
dashboard_pid=""

cleanup() {
    trap - EXIT INT TERM
    [[ -n "$api_pid" ]] && kill -- "-$api_pid" 2>/dev/null || true
    [[ -n "$dashboard_pid" ]] && kill -- "-$dashboard_pid" 2>/dev/null || true
    wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting AgentProbe without Docker..."
setsid "$python" -m uvicorn agentprobe.main:app \
    --app-dir "$root/apps/api" --host 127.0.0.1 --port 8000 &
api_pid=$!

setsid npm run dev --prefix "$root/apps/web" &
dashboard_pid=$!

echo
echo "Dashboard:       http://localhost:3000"
echo "Test chatbot:    http://localhost:8000/demo"
echo "API docs:        http://localhost:8000/docs"
echo "Storage:         in memory (resets when stopped)"
echo "Press Ctrl+C to stop both services."

wait -n "$api_pid" "$dashboard_pid"
