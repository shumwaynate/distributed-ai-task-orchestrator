import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RESULTS_FILE = (
    PROJECT_ROOT
    / "benchmarks"
    / "results.csv"
)

DEFAULT_GRAPHS_DIR = (
    PROJECT_ROOT
    / "benchmarks"
    / "graphs"
)

BenchmarkRow = Dict[str, str]
GroupedResults = Dict[str, List[BenchmarkRow]]


def parse_float(
    value: str,
    default: float = 0.0,
) -> float:
    """
    Safely convert CSV text into a float.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(
    value: str,
    default: int = 0,
) -> int:
    """
    Safely convert CSV text into an integer.
    """

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_results(
    results_file: Path,
) -> List[BenchmarkRow]:
    """
    Load benchmark rows from the selected CSV file.
    """

    if not results_file.exists():
        raise FileNotFoundError(
            f"Could not find results file: {results_file}"
        )

    with results_file.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)
        return list(reader)


def filter_successful_results(
    rows: List[BenchmarkRow],
) -> List[BenchmarkRow]:
    """
    Keep only successful benchmark runs.
    """

    return [
        row
        for row in rows
        if row.get(
            "final_status",
            "",
        ).strip().upper() == "SUCCESS"
    ]


def filter_workloads(
    rows: List[BenchmarkRow],
    include_historical: bool,
) -> List[BenchmarkRow]:
    """
    By default, graph only the final Route Risk Engine workload.

    Historical slow, matrix, and vector rows remain available through
    the --include-historical command-line option.
    """

    if include_historical:
        return rows

    return [
        row
        for row in rows
        if row.get(
            "workload",
            "",
        ).strip().lower() == "route_risk"
    ]


def build_group_key(
    row: BenchmarkRow,
) -> str:
    """
    Build a group key for comparable experiment runs.

    Rows are comparable when they use the same workload, task count,
    and workload size.
    """

    workload = row.get(
        "workload",
        "unknown",
    ).strip().lower()

    task_count = row.get(
        "task_count",
        "unknown",
    ).strip()

    workload_size = row.get(
        "workload_size",
        "",
    ).strip()

    if workload == "slow":
        workload_size = row.get(
            "delay_seconds",
            workload_size,
        ).strip()

    return (
        f"{workload}"
        f"_tasks_{task_count}"
        f"_size_{workload_size}"
    )


def group_results(
    rows: List[BenchmarkRow],
) -> GroupedResults:
    """
    Group rows into comparable experiment configurations.
    """

    grouped_results: GroupedResults = defaultdict(list)

    for row in rows:
        group_key = build_group_key(row)
        grouped_results[group_key].append(row)

    return dict(grouped_results)


def select_latest_result_per_worker(
    rows: List[BenchmarkRow],
) -> List[BenchmarkRow]:
    """
    Keep only the newest CSV row for each worker count.

    The CSV is appended chronologically, so a later row replaces an
    earlier row with the same worker count.
    """

    latest_by_worker: Dict[int, BenchmarkRow] = {}

    for row in rows:
        worker_count = parse_int(
            row.get(
                "worker_count",
                "0",
            )
        )

        if worker_count < 1:
            continue

        latest_by_worker[worker_count] = row

    return [
        latest_by_worker[worker_count]
        for worker_count in sorted(latest_by_worker)
    ]


def clean_group_name(
    group_key: str,
) -> str:
    """
    Convert a result-group name into a safe filename.
    """

    cleaned_name = group_key

    for character in [
        " ",
        ".",
        "/",
        "\\",
        ":",
    ]:
        cleaned_name = cleaned_name.replace(
            character,
            "_",
        )

    return cleaned_name


def get_group_title(
    rows: List[BenchmarkRow],
) -> str:
    """
    Build a readable graph title.
    """

    first_row = rows[0]

    workload = first_row.get(
        "workload",
        "unknown",
    ).strip().lower()

    task_count = first_row.get(
        "task_count",
        "unknown",
    ).strip()

    if workload == "route_risk":
        return (
            "Distributed Route Risk Engine"
            f", {task_count} Checkpoint Tasks"
        )

    if workload == "slow":
        delay = first_row.get(
            "delay_seconds",
            "unknown",
        ).strip()

        return (
            "Historical Slow Workload"
            f", {task_count} Tasks"
            f", {delay}s Delay"
        )

    workload_size = first_row.get(
        "workload_size",
        "unknown",
    ).strip()

    return (
        f"Historical {workload.title()} Workload"
        f", {task_count} Tasks"
        f", Size {workload_size}"
    )


def extract_graph_values(
    rows: List[BenchmarkRow],
) -> Tuple[
    List[int],
    List[float],
    List[float],
]:
    """
    Extract worker, runtime, and throughput values.
    """

    worker_counts = [
        parse_int(
            row.get(
                "worker_count",
                "0",
            )
        )
        for row in rows
    ]

    runtimes = [
        parse_float(
            row.get(
                "total_runtime_seconds",
                "0",
            )
        )
        for row in rows
    ]

    throughputs = [
        parse_float(
            row.get(
                "throughput_tasks_per_second",
                "0",
            )
        )
        for row in rows
    ]

    return (
        worker_counts,
        runtimes,
        throughputs,
    )


def plot_runtime(
    rows: List[BenchmarkRow],
    group_key: str,
    graphs_dir: Path,
) -> Path:
    """
    Generate runtime versus worker count.
    """

    worker_counts, runtimes, _ = (
        extract_graph_values(rows)
    )

    title = get_group_title(rows)

    output_path = (
        graphs_dir
        / (
            "runtime_by_workers_"
            f"{clean_group_name(group_key)}.png"
        )
    )

    plt.figure(figsize=(10, 6))

    plt.plot(
        worker_counts,
        runtimes,
        marker="o",
    )

    plt.xlabel("Worker Count")
    plt.ylabel("Total Runtime in Seconds")

    plt.title(
        "Runtime vs Worker Count\n"
        f"{title}"
    )

    plt.grid(True)
    plt.xticks(worker_counts)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def plot_throughput(
    rows: List[BenchmarkRow],
    group_key: str,
    graphs_dir: Path,
) -> Path:
    """
    Generate throughput versus worker count.
    """

    worker_counts, _, throughputs = (
        extract_graph_values(rows)
    )

    title = get_group_title(rows)

    output_path = (
        graphs_dir
        / (
            "throughput_by_workers_"
            f"{clean_group_name(group_key)}.png"
        )
    )

    plt.figure(figsize=(10, 6))

    plt.plot(
        worker_counts,
        throughputs,
        marker="o",
    )

    plt.xlabel("Worker Count")
    plt.ylabel("Completed Tasks Per Second")

    plt.title(
        "Throughput vs Worker Count\n"
        f"{title}"
    )

    plt.grid(True)
    plt.xticks(worker_counts)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def calculate_runtime_speedups(
    rows: List[BenchmarkRow],
) -> List[float]:
    """
    Calculate runtime speedup relative to the smallest worker count.

    Speedup is:

        baseline runtime / current runtime
    """

    _, runtimes, _ = extract_graph_values(rows)

    if not runtimes:
        return []

    baseline_runtime = runtimes[0]

    if baseline_runtime <= 0:
        return [
            0.0
            for _ in runtimes
        ]

    return [
        (
            baseline_runtime / runtime
            if runtime > 0
            else 0.0
        )
        for runtime in runtimes
    ]


def plot_speedup(
    rows: List[BenchmarkRow],
    group_key: str,
    graphs_dir: Path,
) -> Path:
    """
    Generate measured speedup versus worker count.

    An ideal linear scaling reference is included for comparison.
    """

    worker_counts, _, _ = extract_graph_values(rows)
    measured_speedups = calculate_runtime_speedups(rows)

    baseline_workers = worker_counts[0]

    ideal_speedups = [
        worker_count / baseline_workers
        for worker_count in worker_counts
    ]

    title = get_group_title(rows)

    output_path = (
        graphs_dir
        / (
            "speedup_by_workers_"
            f"{clean_group_name(group_key)}.png"
        )
    )

    plt.figure(figsize=(10, 6))

    plt.plot(
        worker_counts,
        measured_speedups,
        marker="o",
        label="Measured Speedup",
    )

    plt.plot(
        worker_counts,
        ideal_speedups,
        marker="o",
        linestyle="--",
        label="Ideal Linear Speedup",
    )

    plt.xlabel("Worker Count")
    plt.ylabel("Speedup Compared with Baseline")

    plt.title(
        "Measured Scaling Speedup\n"
        f"{title}"
    )

    plt.grid(True)
    plt.xticks(worker_counts)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


def print_scaling_summary(
    rows: List[BenchmarkRow],
) -> None:
    """
    Print runtime, throughput, and speedup measurements.
    """

    worker_counts, runtimes, throughputs = (
        extract_graph_values(rows)
    )

    runtime_speedups = calculate_runtime_speedups(rows)

    baseline_workers = worker_counts[0]
    baseline_throughput = throughputs[0]

    print()
    print(get_group_title(rows))
    print("-" * 75)

    for (
        worker_count,
        runtime,
        throughput,
        runtime_speedup,
    ) in zip(
        worker_counts,
        runtimes,
        throughputs,
        runtime_speedups,
    ):
        throughput_speedup = (
            throughput / baseline_throughput
            if baseline_throughput > 0
            else 0.0
        )

        print(
            f"{worker_count} worker(s): "
            f"{runtime:.2f}s runtime, "
            f"{throughput:.2f} tasks/sec, "
            f"{runtime_speedup:.2f}x runtime speedup, "
            f"{throughput_speedup:.2f}x throughput "
            f"vs {baseline_workers} worker(s)"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate scaling graphs for the Distributed "
            "Route Risk Engine."
        )
    )

    parser.add_argument(
        "--results-file",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help=(
            "Benchmark CSV file to read."
        ),
    )

    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=DEFAULT_GRAPHS_DIR,
        help=(
            "Directory where generated graphs are saved."
        ),
    )

    parser.add_argument(
        "--include-historical",
        action="store_true",
        help=(
            "Also graph historical slow, matrix, and vector "
            "workloads. By default, only route_risk rows are used."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    args.graphs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_rows = load_results(
        args.results_file
    )

    successful_rows = filter_successful_results(
        all_rows
    )

    selected_rows = filter_workloads(
        successful_rows,
        include_historical=args.include_historical,
    )

    if not selected_rows:
        print(
            "No successful Route Risk Engine "
            "benchmark rows were found."
        )
        return

    grouped_results = group_results(
        selected_rows
    )

    print(
        f"Loaded {len(all_rows)} total benchmark row(s)."
    )

    print(
        f"Found {len(successful_rows)} "
        "successful benchmark row(s)."
    )

    print(
        f"Using {len(selected_rows)} selected row(s)."
    )

    if args.include_historical:
        print(
            "Historical workload graphing is enabled."
        )
    else:
        print(
            "Graphing only the final route_risk workload."
        )

    generated_graphs: List[Path] = []

    for group_key, group_rows in grouped_results.items():
        latest_rows = select_latest_result_per_worker(
            group_rows
        )

        if len(latest_rows) < 2:
            print()
            print(
                f"Skipping {group_key}: "
                "at least two different worker counts "
                "are required."
            )
            continue

        generated_graphs.append(
            plot_runtime(
                rows=latest_rows,
                group_key=group_key,
                graphs_dir=args.graphs_dir,
            )
        )

        generated_graphs.append(
            plot_throughput(
                rows=latest_rows,
                group_key=group_key,
                graphs_dir=args.graphs_dir,
            )
        )

        generated_graphs.append(
            plot_speedup(
                rows=latest_rows,
                group_key=group_key,
                graphs_dir=args.graphs_dir,
            )
        )

        print_scaling_summary(
            latest_rows
        )

    print()

    if not generated_graphs:
        print(
            "No graphs were generated because no group had "
            "at least two different worker counts."
        )
        return

    print("Generated graph files:")

    for graph_path in generated_graphs:
        print(graph_path)


if __name__ == "__main__":
    main()