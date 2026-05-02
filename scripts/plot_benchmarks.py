import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_RESULTS_FILE = Path("benchmarks/results.csv")
DEFAULT_OUTPUT_DIR = Path("benchmarks/graphs")


def load_results(csv_path: Path) -> list[dict]:
    """
    Load benchmark results from a CSV file.

    Expected columns:
    timestamp,
    task_count,
    delay_seconds,
    worker_count,
    total_runtime_seconds,
    throughput_tasks_per_second,
    final_status,
    completed_tasks,
    failed_tasks

    Some older benchmark files may not include worker_count.
    This script handles that gracefully.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Benchmark results file not found: {csv_path}")

    rows = []

    with csv_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            cleaned = {
                "timestamp": row.get("timestamp", ""),
                "task_count": int(float(row.get("task_count", 0) or 0)),
                "delay_seconds": float(row.get("delay_seconds", 0) or 0),
                "worker_count": int(float(row.get("worker_count", 0) or 0)),
                "total_runtime_seconds": float(row.get("total_runtime_seconds", 0) or 0),
                "throughput_tasks_per_second": float(row.get("throughput_tasks_per_second", 0) or 0),
                "final_status": row.get("final_status", ""),
                "completed_tasks": int(float(row.get("completed_tasks", 0) or 0)),
                "failed_tasks": int(float(row.get("failed_tasks", 0) or 0)),
            }

            rows.append(cleaned)

    return rows


def filter_successful_results(rows: list[dict]) -> list[dict]:
    """
    Keep benchmark rows that completed successfully.

    The API/Celery status may report successful jobs as either
    COMPLETED or SUCCESS depending on which part of the system
    produced the final status.
    """
    successful_statuses = {"COMPLETED", "SUCCESS"}

    return [
        row for row in rows
        if row["final_status"].upper() in successful_statuses
    ]


def group_by_worker_count(rows: list[dict]) -> dict[int, list[dict]]:
    """
    Group benchmark rows by number of workers.
    """
    grouped = {}

    for row in rows:
        worker_count = row["worker_count"]

        if worker_count not in grouped:
            grouped[worker_count] = []

        grouped[worker_count].append(row)

    return grouped


def plot_runtime_by_workers(rows: list[dict], output_dir: Path) -> Path:
    """
    Create a graph showing how total runtime changes as worker count changes.
    """
    grouped = group_by_worker_count(rows)

    worker_counts = []
    average_runtimes = []

    for worker_count in sorted(grouped.keys()):
        worker_rows = grouped[worker_count]
        avg_runtime = sum(row["total_runtime_seconds"] for row in worker_rows) / len(worker_rows)

        worker_counts.append(worker_count)
        average_runtimes.append(avg_runtime)

    output_path = output_dir / "runtime_by_workers.png"

    plt.figure()
    plt.plot(worker_counts, average_runtimes, marker="o")
    plt.title("Average Runtime by Worker Count")
    plt.xlabel("Worker Count")
    plt.ylabel("Average Runtime (seconds)")
    plt.grid(True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()

    return output_path


def plot_throughput_by_workers(rows: list[dict], output_dir: Path) -> Path:
    """
    Create a graph showing how throughput changes as worker count changes.
    """
    grouped = group_by_worker_count(rows)

    worker_counts = []
    average_throughputs = []

    for worker_count in sorted(grouped.keys()):
        worker_rows = grouped[worker_count]
        avg_throughput = (
            sum(row["throughput_tasks_per_second"] for row in worker_rows)
            / len(worker_rows)
        )

        worker_counts.append(worker_count)
        average_throughputs.append(avg_throughput)

    output_path = output_dir / "throughput_by_workers.png"

    plt.figure()
    plt.plot(worker_counts, average_throughputs, marker="o")
    plt.title("Average Throughput by Worker Count")
    plt.xlabel("Worker Count")
    plt.ylabel("Average Throughput (tasks/second)")
    plt.grid(True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()

    return output_path


def plot_speedup_by_workers(rows: list[dict], output_dir: Path) -> Path:
    """
    Create a speedup graph using the average 1-worker runtime as the baseline.

    Speedup = baseline_runtime / runtime_with_n_workers
    """
    grouped = group_by_worker_count(rows)

    if 1 not in grouped:
        raise ValueError(
            "Cannot calculate speedup because no benchmark rows exist for worker_count=1."
        )

    one_worker_rows = grouped[1]
    baseline_runtime = (
        sum(row["total_runtime_seconds"] for row in one_worker_rows)
        / len(one_worker_rows)
    )

    worker_counts = []
    speedups = []

    for worker_count in sorted(grouped.keys()):
        worker_rows = grouped[worker_count]
        avg_runtime = sum(row["total_runtime_seconds"] for row in worker_rows) / len(worker_rows)

        speedup = baseline_runtime / avg_runtime if avg_runtime > 0 else 0

        worker_counts.append(worker_count)
        speedups.append(speedup)

    output_path = output_dir / "speedup_by_workers.png"

    plt.figure()
    plt.plot(worker_counts, speedups, marker="o")
    plt.title("Speedup by Worker Count")
    plt.xlabel("Worker Count")
    plt.ylabel("Speedup Compared to 1 Worker")
    plt.grid(True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()

    return output_path


def print_summary(rows: list[dict]) -> None:
    """
    Print a readable summary of benchmark results.
    """
    grouped = group_by_worker_count(rows)

    print("\nBenchmark Summary")
    print("-----------------")

    for worker_count in sorted(grouped.keys()):
        worker_rows = grouped[worker_count]

        avg_runtime = (
            sum(row["total_runtime_seconds"] for row in worker_rows)
            / len(worker_rows)
        )

        avg_throughput = (
            sum(row["throughput_tasks_per_second"] for row in worker_rows)
            / len(worker_rows)
        )

        print(f"Workers: {worker_count}")
        print(f"  Runs: {len(worker_rows)}")
        print(f"  Average runtime: {avg_runtime:.2f} seconds")
        print(f"  Average throughput: {avg_throughput:.2f} tasks/second")


def main():
    parser = argparse.ArgumentParser(
        description="Generate benchmark graphs from distributed task orchestrator results."
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_RESULTS_FILE),
        help="Path to benchmark CSV file."
    )

    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where graphs should be saved."
    )

    args = parser.parse_args()

    csv_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_results(csv_path)
    successful_rows = filter_successful_results(rows)

    if not successful_rows:
        print("No completed benchmark rows found. Run benchmarks first.")
        return

    print_summary(successful_rows)

    generated_files = []

    generated_files.append(plot_runtime_by_workers(successful_rows, output_dir))
    generated_files.append(plot_throughput_by_workers(successful_rows, output_dir))

    try:
        generated_files.append(plot_speedup_by_workers(successful_rows, output_dir))
    except ValueError as error:
        print(f"\nSpeedup graph skipped: {error}")

    print("\nGenerated graph files:")
    for file_path in generated_files:
        print(f"  {file_path}")


if __name__ == "__main__":
    main()