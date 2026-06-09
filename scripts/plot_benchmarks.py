import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_FILE = PROJECT_ROOT / "benchmarks" / "results.csv"
GRAPHS_DIR = PROJECT_ROOT / "benchmarks" / "graphs"


def load_results() -> List[Dict[str, str]]:
    """
    Loads benchmark results from benchmarks/results.csv.
    """
    if not RESULTS_FILE.exists():
        raise FileNotFoundError(f"Could not find results file: {RESULTS_FILE}")

    with RESULTS_FILE.open("r", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def parse_float(value: str, default: float = 0.0) -> float:
    """
    Safely parses a float from CSV text.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: str, default: int = 0) -> int:
    """
    Safely parses an integer from CSV text.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def filter_successful_results(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Keeps only successful benchmark rows.
    """
    return [
        row
        for row in rows
        if row.get("final_status", "").upper() == "SUCCESS"
    ]


def group_results(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """
    Groups results by workload, task count, and workload size.

    This prevents slow, matrix, vector, and route-risk tests from being mixed together.
    """
    grouped_results = defaultdict(list)

    for row in rows:
        workload = row.get("workload", "unknown")
        task_count = row.get("task_count", "unknown")
        workload_size = row.get("workload_size", "")

        if workload == "slow":
            workload_size = row.get("delay_seconds", workload_size)

        group_key = f"{workload}_tasks_{task_count}_size_{workload_size}"
        grouped_results[group_key].append(row)

    return grouped_results


def clean_group_name(group_key: str) -> str:
    """
    Converts a group key into a safe filename piece.
    """
    return (
        group_key
        .replace(" ", "_")
        .replace(".", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def sort_rows_by_worker_count(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Sorts rows by worker count.
    """
    return sorted(rows, key=lambda row: parse_int(row.get("worker_count", "0")))


def get_group_title(rows: List[Dict[str, str]]) -> str:
    """
    Builds a readable graph title from the first row in a result group.
    """
    first_row = rows[0]

    workload = first_row.get("workload", "unknown")
    task_count = first_row.get("task_count", "unknown")

    if workload == "slow":
        delay = first_row.get("delay_seconds", "unknown")
        return f"{workload.title()} Workload, {task_count} Tasks, {delay}s Delay"

    if workload == "route_risk":
        return f"Route Risk Workload, {task_count} Checkpoints"

    workload_size = first_row.get("workload_size", "unknown")
    return f"{workload.title()} Workload, {task_count} Tasks, Size {workload_size}"


def plot_runtime(rows: List[Dict[str, str]], group_key: str) -> Path:
    """
    Creates a runtime versus worker count graph.
    """
    sorted_rows = sort_rows_by_worker_count(rows)

    worker_counts = [
        parse_int(row.get("worker_count", "0"))
        for row in sorted_rows
    ]

    runtimes = [
        parse_float(row.get("total_runtime_seconds", "0"))
        for row in sorted_rows
    ]

    title = get_group_title(sorted_rows)
    output_path = GRAPHS_DIR / f"runtime_by_workers_{clean_group_name(group_key)}.png"

    plt.figure(figsize=(10, 6))
    plt.plot(worker_counts, runtimes, marker="o")
    plt.xlabel("Worker Count")
    plt.ylabel("Runtime Seconds")
    plt.title(f"Runtime vs Worker Count\n{title}")
    plt.grid(True)
    plt.xticks(worker_counts)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def plot_throughput(rows: List[Dict[str, str]], group_key: str) -> Path:
    """
    Creates a throughput versus worker count graph.
    """
    sorted_rows = sort_rows_by_worker_count(rows)

    worker_counts = [
        parse_int(row.get("worker_count", "0"))
        for row in sorted_rows
    ]

    throughputs = [
        parse_float(row.get("throughput_tasks_per_second", "0"))
        for row in sorted_rows
    ]

    title = get_group_title(sorted_rows)
    output_path = GRAPHS_DIR / f"throughput_by_workers_{clean_group_name(group_key)}.png"

    plt.figure(figsize=(10, 6))
    plt.plot(worker_counts, throughputs, marker="o")
    plt.xlabel("Worker Count")
    plt.ylabel("Throughput, Tasks Per Second")
    plt.title(f"Throughput vs Worker Count\n{title}")
    plt.grid(True)
    plt.xticks(worker_counts)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def calculate_speedup(rows: List[Dict[str, str]]) -> None:
    """
    Prints speedup information for each group.
    """
    sorted_rows = sort_rows_by_worker_count(rows)

    if not sorted_rows:
        return

    baseline = sorted_rows[0]
    baseline_workers = parse_int(baseline.get("worker_count", "0"))
    baseline_throughput = parse_float(
        baseline.get("throughput_tasks_per_second", "0")
    )

    print()
    print(get_group_title(sorted_rows))
    print("-" * 60)

    for row in sorted_rows:
        workers = parse_int(row.get("worker_count", "0"))
        runtime = parse_float(row.get("total_runtime_seconds", "0"))
        throughput = parse_float(row.get("throughput_tasks_per_second", "0"))

        if baseline_throughput > 0:
            speedup = throughput / baseline_throughput
        else:
            speedup = 0.0

        print(
            f"{workers} workers: "
            f"{runtime:.2f}s runtime, "
            f"{throughput:.2f} tasks/sec, "
            f"{speedup:.2f}x throughput vs {baseline_workers} worker"
        )


def main() -> None:
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_results()
    successful_rows = filter_successful_results(rows)

    if not successful_rows:
        print("No successful benchmark rows found.")
        return

    grouped_results = group_results(successful_rows)

    print(f"Loaded {len(rows)} total benchmark rows.")
    print(f"Using {len(successful_rows)} successful benchmark rows.")
    print(f"Found {len(grouped_results)} result group(s).")

    generated_graphs = []

    for group_key, group_rows in grouped_results.items():
        if len(group_rows) < 2:
            print()
            print(f"Skipping graph for {group_key} because it has fewer than 2 rows.")
            continue

        runtime_graph = plot_runtime(group_rows, group_key)
        throughput_graph = plot_throughput(group_rows, group_key)

        generated_graphs.append(runtime_graph)
        generated_graphs.append(throughput_graph)

        calculate_speedup(group_rows)

    print()
    print("Generated graph files:")

    for graph_path in generated_graphs:
        print(graph_path)


if __name__ == "__main__":
    main()