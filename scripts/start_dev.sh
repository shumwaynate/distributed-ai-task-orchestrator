#!/usr/bin/env bash

set -e

WORKERS=${1:-4}

cd "$(dirname "$0")/.."

cleanup_existing_processes() {
    echo "Cleaning up old FastAPI and Celery processes..."

    pkill -f "uvicorn app.api.main:app" 2>/dev/null || true
    pkill -f "celery -A app.worker.celery_app worker" 2>/dev/null || true

    sleep 2
}

cleanup_started_processes() {
    echo "Stopping services..."

    if [ -n "${API_PID:-}" ]; then
        kill "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
    fi

    if [ -n "${WORKER_PID:-}" ]; then
        kill "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi
}

echo "Starting Distributed AI Task Orchestrator development environment..."
echo "Worker concurrency: $WORKERS"

source .venv/bin/activate

cleanup_existing_processes

echo "Checking Redis..."
redis-cli ping

if [ $? -ne 0 ]; then
    echo "Redis is not responding. Start Redis first with:"
    echo "brew services start redis"
    exit 1
fi

echo "Starting FastAPI..."
uvicorn app.api.main:app --reload &
API_PID=$!

sleep 2

echo "Starting Celery worker..."
celery -A app.worker.celery_app worker \
    --loglevel=info \
    --concurrency="$WORKERS" \
    --hostname="worker_${WORKERS}_$(date +%s)@%h" &
WORKER_PID=$!

echo ""
echo "Development environment running."
echo "FastAPI PID: $API_PID"
echo "Worker PID: $WORKER_PID"
echo ""
echo "Press CTRL+C to stop both."

trap cleanup_started_processes INT TERM EXIT

wait