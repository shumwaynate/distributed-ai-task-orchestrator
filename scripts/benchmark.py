import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_FILE = PROJECT_ROOT / "benchmarks" / "results.csv"
API_BASE_URL = "http://127.0.0.1:8000"

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


def submit_slow_batch(task_count: int, delay_seconds: float) -> Dict[str, Any]:
    payload = {
        "numbers": list(range(1, task_count + 1)),
        "delay_seconds": delay_seconds,
    }

    response = requests.post(
        f"{API_BASE_URL}/submit_slow_batch",
        json=payload,
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def submit_matrix_batch(task_count: int, workload_size: int) -> Dict[str, Any]:
    payload = {
        "task_count": task_count,
        "matrix_size": workload_size,
    }

    response = requests.post(
        f"{API_BASE_URL}/submit_matrix_batch",
        json=payload,
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def submit_vector_batch(task_count: int, workload_size: int) -> Dict[str, Any]:
    payload = {
        "task_count": task_count,
        "vector_size": workload_size,
    }

    response = requests.post(
        f"{API_BASE_URL}/submit_vector_batch",
        json=payload,
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def submit_route_risk_job(task_count: int) -> Dict[str, Any]:
    payload = {
        "route_name": "Benchmark Rexburg to Idaho Falls Route",
        "origin_label": "Rexburg, ID",
        "origin_latitude": 43.8231,
        "origin_longitude": -111.7924,
        "destination_label": "Idaho Falls, ID",
        "destination_latitude": 43.4927,
        "destination_longitude": -112.0408,
        "checkpoint_count": task_count,
        "road_condition": "normal",
        "road_event_radius_miles": 1.0,
        "road_events": [],
        "is_night": False,
    }

    response = requests.post(
        f"{API_BASE_URL}/submit_routed_route_risk_job",
        json=payload,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_job_status(job_id: str) -> Dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/job_status/{job_id}",
        timeout=15,
    )

    response.raise_for_status()
    return response.json()


def wait_for_job(job_id: str, poll_interval: float) -> Dict[str, Any]:
    while True:
        status = get_job_status(job_id)

        print(
            "Status: "
            f"{status['status']} | "
            f"Completed: {status['completed_tasks']}/{status['total_tasks']} | "
            f"Failed: {status['failed_tasks']} | "
            f"Progress: {status['progress_percent']}%"
        )

        if status["status"] in ["SUCCESS", "PARTIAL_FAILURE"]:
            return status

        time.sleep(poll_interval)


def read_existing_fieldnames(results_file: Path) -> List[str]:
    if not results_file.exists() or results_file.stat().st_size == 0:
        return DEFAULT_FIELDNAMES

    with results_file.open("r", newline="") as file:
        reader = csv.reader(file)
        header = next(reader, None)

    if not header:
        return DEFAULT_FIELDNAMES

    return header


def save_result(results_file: Path, result: Dict[str, Any]) -> None:
    results_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = read_existing_fieldnames(results_file)
    file_exists = results_file.exists() and results_file.stat().st_size > 0

    row = {}

    for field in fieldnames:
        row[field] = result.get(field, "")

    with results_file.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def submit_benchmark_job(args: argparse.Namespace) -> Dict[str, Any]:
    if args.workload == "slow":
        print(f"Delay seconds per task: {args.delay}")
        return submit_slow_batch(args.tasks, args.delay)

    if args.workload == "matrix":
        print(f"Matrix size: {args.size}")
        return submit_matrix_batch(args.tasks, args.size)

    if args.workload == "vector":
        print(f"Vector size: {args.size}")
        return submit_vector_batch(args.tasks, args.size)

    if args.workload == "route_risk":
        print(f"Route-risk checkpoint count: {args.tasks}")
        return submit_route_risk_job(args.tasks)

    raise ValueError(f"Unsupported workload: {args.workload}")


def get_workload_size(args: argparse.Namespace) -> Any:
    if args.workload == "slow":
        return args.delay

    if args.workload == "route_risk":
        return args.tasks

    return args.size


def run_benchmark(args: argparse.Namespace) -> None:
    print("Submitting benchmark job...")
    print(f"Workload: {args.workload}")
    print(f"Worker count recorded: {args.workers}")
    print(f"Task count: {args.tasks}")

    submitted_job = submit_benchmark_job(args)

    job_id = submitted_job["job_id"]
    print(f"Job ID: {job_id}")

    start_time = time.perf_counter()
    final_status = wait_for_job(job_id, args.poll_interval)
    end_time = time.perf_counter()

    total_runtime = end_time - start_time
    throughput = args.tasks / total_runtime if total_runtime > 0 else 0

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "workload": args.workload,
        "task_count": args.tasks,
        "delay_seconds": args.delay if args.workload == "slow" else "",
        "workload_size": get_workload_size(args),
        "worker_count": args.workers,
        "total_runtime_seconds": round(total_runtime, 4),
        "throughput_tasks_per_second": round(throughput, 4),
        "final_status": final_status["status"],
        "completed_tasks": final_status["completed_tasks"],
        "failed_tasks": final_status["failed_tasks"],
    }

    save_result(args.results_file, result)

    print()
    print("Benchmark complete")
    print(f"Workload: {args.workload}")
    print(f"Worker count recorded: {args.workers}")
    print(f"Total runtime: {total_runtime:.2f} seconds")
    print(f"Throughput: {throughput:.2f} tasks/second")
    print(f"Final status: {final_status['status']}")
    print(f"Saved benchmark result to {args.results_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a benchmark against the Distributed Route Risk Engine."
    )

    parser.add_argument(
        "--tasks",
        type=int,
        default=20,
        help="Number of tasks/checkpoints to submit.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay seconds per task for the slow workload.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        required=True,
        help="Worker count to record for this benchmark run.",
    )

    parser.add_argument(
        "--workload",
        choices=["slow", "matrix", "vector", "route_risk"],
        default="slow",
        help="Workload type to benchmark.",
    )

    parser.add_argument(
        "--size",
        type=int,
        default=75,
        help="Workload size for matrix or vector workloads.",
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between job status checks.",
    )

    parser.add_argument(
        "--results-file",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help="CSV file where benchmark results are saved.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    benchmark_args = parse_args()
    run_benchmark(benchmark_args)