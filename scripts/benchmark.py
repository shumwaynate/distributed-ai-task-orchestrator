import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime


API_BASE_URL = "http://127.0.0.1:8000"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = PROJECT_ROOT / "benchmarks" / "results.csv"


def post_json(url, data):
    request_data = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=request_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def save_benchmark_result(result):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "timestamp",
        "task_count",
        "delay_seconds",
        "worker_count",
        "total_runtime_seconds",
        "throughput_tasks_per_second",
        "final_status",
        "completed_tasks",
        "failed_tasks",
    ]

    file_needs_header = (
        not RESULTS_PATH.exists()
        or RESULTS_PATH.stat().st_size == 0
    )

    with RESULTS_PATH.open("a", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        if file_needs_header:
            writer.writeheader()

        writer.writerow(result)


def run_benchmark(task_count=20, delay_seconds=1, worker_count=1):
    numbers = list(range(1, task_count + 1))

    print("Submitting benchmark job...")
    print(f"Worker count recorded: {worker_count}")
    print(f"Task count: {task_count}")
    print(f"Delay seconds per task: {delay_seconds}")

    start_time = time.perf_counter()

    submit_response = post_json(
        f"{API_BASE_URL}/submit_slow_batch",
        {
            "numbers": numbers,
            "delay_seconds": delay_seconds,
        },
    )

    job_id = submit_response["job_id"]
    print(f"Job ID: {job_id}")

    while True:
        status_response = get_json(f"{API_BASE_URL}/job_status/{job_id}")

        completed = status_response["completed_tasks"]
        failed = status_response["failed_tasks"]
        total = status_response["total_tasks"]
        percent = status_response["percent_complete"]
        overall_status = status_response["overall_status"]

        print(
            f"Status: {overall_status} | "
            f"Completed: {completed}/{total} | "
            f"Failed: {failed} | "
            f"Progress: {percent:.1f}%"
        )

        if overall_status in ["SUCCESS", "COMPLETED", "COMPLETED_WITH_FAILURES", "FAILED"]:
            break

        time.sleep(0.5)

    end_time = time.perf_counter()
    total_runtime = end_time - start_time
    throughput = task_count / total_runtime

    print("\nBenchmark complete")
    print(f"Worker count recorded: {worker_count}")
    print(f"Total runtime: {total_runtime:.2f} seconds")
    print(f"Throughput: {throughput:.2f} tasks/second")
    print(f"Final status: {overall_status}")

    benchmark_result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task_count": task_count,
        "delay_seconds": delay_seconds,
        "worker_count": worker_count,
        "total_runtime_seconds": round(total_runtime, 2),
        "throughput_tasks_per_second": round(throughput, 2),
        "final_status": overall_status,
        "completed_tasks": completed,
        "failed_tasks": failed,
    }

    save_benchmark_result(benchmark_result)

    print(f"\nSaved benchmark result to {RESULTS_PATH}")

    return benchmark_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a benchmark against the task orchestrator API."
    )

    parser.add_argument(
        "--tasks",
        type=int,
        default=20,
        help="Number of tasks to submit.",
    )

    parser.add_argument(
        "--delay",
        type=int,
        default=1,
        help="Delay in seconds for each slow task.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of Celery worker processes/concurrency used for this benchmark.",
    )

    args = parser.parse_args()

    run_benchmark(
        task_count=args.tasks,
        delay_seconds=args.delay,
        worker_count=args.workers,
    )