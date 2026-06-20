import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RESULTS_FILE = (
    PROJECT_ROOT
    / "benchmarks"
    / "results.csv"
)

DEFAULT_API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
)

DEFAULT_FIELDNAMES = [
    "timestamp",
    "workload",
    "task_count",
    "delay_seconds",
    "workload_size",
    "worker_count",
    "total_runtime_seconds",
    "throughput_tasks_per_second",
    "final_status",
    "completed_tasks",
    "failed_tasks",
]


def submit_routed_route_risk_job(
    checkpoint_count: int,
    api_base_url: str,
) -> Dict[str, Any]:
    """
    Submit a real routed Route Risk Engine workload.

    Each sampled checkpoint becomes one distributed Celery task.
    """

    payload = {
        "route_name": (
            "Benchmark Rexburg to Idaho Falls Route"
        ),
        "origin_label": "Rexburg, ID",
        "origin_latitude": 43.8231,
        "origin_longitude": -111.7924,
        "destination_label": "Idaho Falls, ID",
        "destination_latitude": 43.4927,
        "destination_longitude": -112.0408,
        "checkpoint_count": checkpoint_count,
        "road_condition": "normal",
        "road_event_radius_miles": 1.0,
        "road_events": [],
        "is_night": False,
    }

    response = requests.post(
        (
            f"{api_base_url}"
            "/submit_routed_route_risk_job"
        ),
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    response_data = response.json()

    if "job_id" not in response_data:
        raise RuntimeError(
            "The API response did not contain a job_id."
        )

    return response_data


def get_job_status(
    job_id: str,
    api_base_url: str,
) -> Dict[str, Any]:
    """
    Retrieve the current distributed job status.
    """

    response = requests.get(
        f"{api_base_url}/job_status/{job_id}",
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


def wait_for_job(
    job_id: str,
    api_base_url: str,
    poll_interval: float,
) -> Dict[str, Any]:
    """
    Poll Redis-backed job status until every task finishes.
    """

    while True:
        status = get_job_status(
            job_id=job_id,
            api_base_url=api_base_url,
        )

        print(
            "Status: "
            f"{status['status']} | "
            f"Completed: "
            f"{status['completed_tasks']}/"
            f"{status['total_tasks']} | "
            f"Failed: {status['failed_tasks']} | "
            f"Progress: "
            f"{status['progress_percent']}%"
        )

        if status["status"] in {
            "SUCCESS",
            "PARTIAL_FAILURE",
        }:
            return status

        time.sleep(poll_interval)


def read_existing_fieldnames(
    results_file: Path,
) -> List[str]:
    """
    Preserve the existing CSV header when appending results.

    This allows historical matrix, vector, and slow-workload rows to
    remain in the same results file.
    """

    if (
        not results_file.exists()
        or results_file.stat().st_size == 0
    ):
        return DEFAULT_FIELDNAMES

    with results_file.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.reader(file)
        header = next(reader, None)

    if not header:
        return DEFAULT_FIELDNAMES

    return header


def save_result(
    results_file: Path,
    result: Dict[str, Any],
) -> None:
    """
    Append one benchmark result to the CSV file.
    """

    results_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = read_existing_fieldnames(
        results_file
    )

    file_exists = (
        results_file.exists()
        and results_file.stat().st_size > 0
    )

    row = {
        field: result.get(field, "")
        for field in fieldnames
    }

    with results_file.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def validate_args(
    args: argparse.Namespace,
) -> None:
    """
    Validate values before submitting a benchmark.
    """

    if args.tasks < 2 or args.tasks > 50:
        raise ValueError(
            "--tasks must be between 2 and 50 because "
            "the routed API uses the value as its "
            "checkpoint count."
        )

    if args.workers < 1:
        raise ValueError(
            "--workers must be at least 1."
        )

    if args.poll_interval <= 0:
        raise ValueError(
            "--poll-interval must be greater than 0."
        )


def run_benchmark(
    args: argparse.Namespace,
) -> None:
    """
    Submit, time, track, and save one route-risk benchmark run.
    """

    validate_args(args)

    api_base_url = args.api_base_url.rstrip("/")

    print("Submitting Route Risk Engine benchmark...")
    print("Workload: route_risk")
    print(f"Worker count recorded: {args.workers}")
    print(f"Requested checkpoints: {args.tasks}")
    print(f"API: {api_base_url}")

    submitted_job = submit_routed_route_risk_job(
        checkpoint_count=args.tasks,
        api_base_url=api_base_url,
    )

    job_id = submitted_job["job_id"]

    print(f"Job ID: {job_id}")

    start_time = time.perf_counter()

    final_status = wait_for_job(
        job_id=job_id,
        api_base_url=api_base_url,
        poll_interval=args.poll_interval,
    )

    end_time = time.perf_counter()

    total_runtime = end_time - start_time

    actual_task_count = int(
        final_status.get(
            "total_tasks",
            args.tasks,
        )
    )

    throughput = (
        actual_task_count / total_runtime
        if total_runtime > 0
        else 0
    )

    result = {
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "workload": "route_risk",
        "task_count": actual_task_count,

        # Kept blank for compatibility with the historical CSV schema.
        "delay_seconds": "",

        # For route-risk runs, workload size is the checkpoint count.
        "workload_size": actual_task_count,

        "worker_count": args.workers,
        "total_runtime_seconds": round(
            total_runtime,
            4,
        ),
        "throughput_tasks_per_second": round(
            throughput,
            4,
        ),
        "final_status": final_status["status"],
        "completed_tasks": final_status[
            "completed_tasks"
        ],
        "failed_tasks": final_status[
            "failed_tasks"
        ],
    }

    save_result(
        results_file=args.results_file,
        result=result,
    )

    print()
    print("Benchmark complete")
    print("Workload: route_risk")
    print(f"Worker count recorded: {args.workers}")
    print(f"Tasks completed: {actual_task_count}")
    print(
        f"Total runtime: "
        f"{total_runtime:.2f} seconds"
    )
    print(
        f"Throughput: "
        f"{throughput:.2f} tasks/second"
    )
    print(
        f"Final status: "
        f"{final_status['status']}"
    )
    print(
        f"Saved benchmark result to "
        f"{args.results_file}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the real Distributed Route Risk Engine "
            "with a selected worker count."
        )
    )

    parser.add_argument(
        "--tasks",
        type=int,
        default=20,
        help=(
            "Number of route checkpoints and distributed "
            "Celery tasks to submit. Allowed range: 2-50."
        ),
    )

    parser.add_argument(
        "--workers",
        type=int,
        required=True,
        help=(
            "Worker count used for this run. The scaling "
            "script starts the workers; this value is stored "
            "with the benchmark result."
        ),
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help=(
            "Seconds between job-status checks."
        ),
    )

    parser.add_argument(
        "--results-file",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help=(
            "CSV file where benchmark results are appended."
        ),
    )

    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help=(
            "Base URL of the running FastAPI application."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    benchmark_args = parse_args()
    run_benchmark(benchmark_args)
