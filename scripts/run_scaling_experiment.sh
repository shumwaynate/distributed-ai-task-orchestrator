#!/usr/bin/env bash

set -Eeuo pipefail

TASKS="${TASKS:-20}"
POLL_INTERVAL="${POLL_INTERVAL:-0.5}"

RESULT_SUMMARY=()
START_DEV_PID=""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Python was not found."
    exit 1
fi

show_usage() {
    echo "Usage:"
    echo "  ./scripts/run_scaling_experiment.sh 1 2 4 8"
    echo ""
    echo "Optional environment variables:"
    echo "  TASKS=20"
    echo "  POLL_INTERVAL=0.5"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_scaling_experiment.sh 1 2 4"
    echo "  TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4 8"
}

validate_inputs() {
    if [ "$#" -lt 1 ]; then
        show_usage
        exit 1
    fi

    if ! [[ "$TASKS" =~ ^[0-9]+$ ]]; then
        echo "TASKS must be a whole number."
        exit 1
    fi

    if [ "$TASKS" -lt 2 ] || [ "$TASKS" -gt 50 ]; then
        echo "TASKS must be between 2 and 50."
        echo "The value is used as the route checkpoint count."
        exit 1
    fi

    for worker_count in "$@"; do
        if ! [[ "$worker_count" =~ ^[0-9]+$ ]]; then
            echo "Worker counts must be whole numbers."
            exit 1
        fi

        if [ "$worker_count" -lt 1 ]; then
            echo "Every worker count must be at least 1."
            exit 1
        fi
    done
}

cleanup() {
    if [ -n "${START_DEV_PID:-}" ]; then
        echo "Stopping development environment..."

        kill "$START_DEV_PID" 2>/dev/null || true
        wait "$START_DEV_PID" 2>/dev/null || true

        START_DEV_PID=""
    fi
}

wait_for_api() {
    echo "Waiting for API to become available..."

    local attempt

    for attempt in $(seq 1 60); do
        if curl \
            --silent \
            --fail \
            --max-time 2 \
            "http://127.0.0.1:8000/" \
            >/dev/null; then

            echo "API is ready."
            return 0
        fi

        sleep 1
    done

    echo "API did not become ready in time."
    return 1
}

run_single_experiment() {
    local workers="$1"
    local log_file
    local benchmark_exit_code
    local runtime
    local throughput
    local final_status

    log_file="$(mktemp)"

    echo ""
    echo "========================================"
    echo "Starting Route Risk scaling experiment"
    echo "Workers: $workers"
    echo "Route-risk tasks/checkpoints: $TASKS"
    echo "Poll interval: $POLL_INTERVAL seconds"
    echo "========================================"
    echo ""

    ./scripts/start_dev.sh "$workers" &
    START_DEV_PID=$!

    if ! wait_for_api; then
        cleanup
        rm -f "$log_file"
        return 1
    fi

    echo "Submitting the real routed Route Risk workload..."
    echo ""

    set +e

    "$PYTHON_BIN" ./scripts/benchmark.py \
        --tasks "$TASKS" \
        --workers "$workers" \
        --poll-interval "$POLL_INTERVAL" \
        2>&1 |
        tee "$log_file"

    benchmark_exit_code="${PIPESTATUS[0]}"

    set -e

    runtime="$(
        grep "Total runtime:" "$log_file" |
            tail -n 1 |
            awk '{print $3}'
    )"

    throughput="$(
        grep "Throughput:" "$log_file" |
            tail -n 1 |
            awk '{print $2}'
    )"

    final_status="$(
        grep "Final status:" "$log_file" |
            tail -n 1 |
            awk '{print $3}'
    )"

    if [ -z "$runtime" ]; then
        runtime="FAILED"
    fi

    if [ -z "$throughput" ]; then
        throughput="FAILED"
    fi

    if [ -z "$final_status" ]; then
        final_status="FAILED"
    fi

    RESULT_SUMMARY+=(
        "$workers|$TASKS|$runtime|$throughput|$final_status"
    )

    if [ "$benchmark_exit_code" -ne 0 ]; then
        echo ""
        echo "Benchmark failed for $workers worker(s)."
        echo "Exit code: $benchmark_exit_code"
    fi

    rm -f "$log_file"

    cleanup

    echo "Finished run for $workers worker(s)."

    sleep 2
}

print_summary() {
    echo ""
    echo "========================================"
    echo "Route Risk scaling experiment complete"
    echo "========================================"
    echo ""
    echo "Route-risk tasks/checkpoints: $TASKS"
    echo ""

    printf \
        "%-10s %-10s %-18s %-28s %-15s\n" \
        "Workers" \
        "Tasks" \
        "Runtime Seconds" \
        "Throughput Tasks Per Second" \
        "Final Status"

    printf \
        "%-10s %-10s %-18s %-28s %-15s\n" \
        "-------" \
        "-----" \
        "---------------" \
        "---------------------------" \
        "------------"

    local row
    local workers
    local tasks
    local runtime
    local throughput
    local final_status

    for row in "${RESULT_SUMMARY[@]}"; do
        IFS="|" read -r \
            workers \
            tasks \
            runtime \
            throughput \
            final_status \
            <<< "$row"

        printf \
            "%-10s %-10s %-18s %-28s %-15s\n" \
            "$workers" \
            "$tasks" \
            "$runtime" \
            "$throughput" \
            "$final_status"
    done

    echo ""
    echo "Results were appended to:"
    echo "benchmarks/results.csv"
}

validate_inputs "$@"

trap cleanup EXIT INT TERM

for workers in "$@"; do
    run_single_experiment "$workers"
done

print_summary