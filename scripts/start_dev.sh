#!/bin/bash

WORKERS=${1:-4}

echo "Starting Distributed AI Task Orchestrator development environment..."
echo "Worker concurrency: $WORKERS"

cd "$(dirname "$0")/.."

source .venv/bin/activate

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
celery -A app.worker.celery_app worker --loglevel=info --concurrency=$WORKERS &
WORKER_PID=$!

echo ""
echo "Development environment running."
echo "FastAPI PID: $API_PID"
echo "Worker PID: $WORKER_PID"
echo ""
echo "Press CTRL+C to stop both."

trap "echo 'Stopping services...'; kill $API_PID $WORKER_PID; exit" INT

wait