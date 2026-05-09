#!/usr/bin/env bash

set -e

TASKS="${TASKS:-20}"
DELAY="${DELAY:-1}"
WORKLOAD="${WORKLOAD:-slow}"
SIZE="${SIZE:-75}"
POLL_INTERVAL="${POLL_INTERVAL:-0.5}"

RESULT_SUMMARY=()

if [ "$#" -lt 1 ]; then
    echo "Usage: ./scripts/run_scaling_experiment.sh 1 2 4 8"
    echo ""
    echo "Optional environment variables:"
    echo "  TASKS=20"
    echo "  DELAY=1"
    echo "  WORKLOAD=slow"
    echo "  WORKLOAD=matrix"
    echo "  WORKLOAD=vector"
    echo "  SIZE=75"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_scaling_experiment.sh 1 2 4"
    echo "  WORKLOAD=matrix SIZE=250 TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4"
    echo "  WORKLOAD=vector SIZE=1000 TASKS=20 ./scripts/run_scaling_experiment.sh 1 2 4"
    exit 1
fi

cleanup() {
    if [ -n "${START_DEV_PID:-}" ]; then
        echo "Stopping development environment..."
        kill "$START_DEV_PID" 2>/dev/null || true
        wait "$START_DEV_PID" 2>/dev/null || true
    fi
}

wait_for_api() {
    echo "Waiting for API to become available..."

    for attempt in {1..30}; do
        if curl -s "http://127.0.0.1:8000/" >/dev/null; then
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

    log_file="$(mktemp)"

    echo ""
    echo "Starting scaling experiment run"
    echo "Workers: $workers"
    echo "Tasks: $TASKS"
    echo "Workload: $WORKLOAD"

    if [ "$WORKLOAD" = "slow" ]; then
        echo "Delay: $DELAY"
    else
        echo "Size: $SIZE"
    fi

    ./scripts/start_dev.sh "$workers" &
    START_DEV_PID=$!

    wait_for_api

    python3 scripts/benchmark.py \
        --tasks "$TASKS" \
        --delay "$DELAY" \
        --workers "$workers" \
        --workload "$WORKLOAD" \
        --size "$SIZE" \
        --poll-interval "$POLL_INTERVAL" | tee "$log_file"

    local runtime
    local throughput
    local final_status

    runtime="$(grep "Total runtime:" "$log_file" | tail -n 1 | awk '{print $3}')"
    throughput="$(grep "Throughput:" "$log_file" | tail -n 1 | awk '{print $2}')"
    final_status="$(grep "Final status:" "$log_file" | tail -n 1 | awk '{print $3}')"

    RESULT_SUMMARY+=("$workers|$runtime|$throughput|$final_status")

    rm -f "$log_file"

    cleanup
    START_DEV_PID=""

    echo "Finished run for $workers workers."
    sleep 2
}

print_summary() {
    echo ""
    echo "Scaling experiment complete."
    echo ""
    echo "Summary"
    echo "Workload: $WORKLOAD"
    echo "Tasks: $TASKS"

    if [ "$WORKLOAD" = "slow" ]; then
        echo "Delay: $DELAY"
    else
        echo "Size: $SIZE"
    fi

    echo ""
    printf "%-10s %-18s %-28s %-15s\n" "Workers" "Runtime Seconds" "Throughput Tasks Per Second" "Final Status"
    printf "%-10s %-18s %-28s %-15s\n" "-------" "---------------" "---------------------------" "------------"

    for row in "${RESULT_SUMMARY[@]}"; do
        IFS="|" read -r workers runtime throughput final_status <<< "$row"
        printf "%-10s %-18s %-28s %-15s\n" "$workers" "$runtime" "$throughput" "$final_status"
    done
}

trap cleanup EXIT

for workers in "$@"; do
    run_single_experiment "$workers"
done

print_summary