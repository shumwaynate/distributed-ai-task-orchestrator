#!/usr/bin/env python3
r"""
Unified final validation command for the Distributed Route Risk Engine.

Run from the project root:

    python scripts/validate_final_project.py

The default run performs:
- Required-file and Python compile checks
- Focused local regression tests
- State-provider registry and automatic state-detection checks
- Benchmark evidence validation
- Live API health, distributed single-route closure, route comparison,
  and long-route error checks

Useful options:

    python scripts/validate_final_project.py --skip-api
    python scripts/validate_final_project.py --skip-comparison
    python scripts/validate_final_project.py --skip-long-route-check
    python scripts/validate_final_project.py --api-base-url http://127.0.0.1:8000

The live API checks expect FastAPI, Redis, and at least one Celery worker to
already be running. On Windows, start them first with:

    .\scripts\start_dev.ps1
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

TERMINAL_JOB_STATUSES = {
    "SUCCESS",
    "PARTIAL_FAILURE",
    "FAILURE",
    "FAILED",
    "REVOKED",
}


class ValidationFailure(AssertionError):
    """Raised when a validation condition is not satisfied."""


class ValidationSkip(RuntimeError):
    """Raised when a check is intentionally skipped."""


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    duration_seconds: float


class Validator:
    def __init__(self) -> None:
        self.results: List[CheckResult] = []

    def run(self, name: str, check: Callable[[], str]) -> None:
        started = time.perf_counter()
        try:
            detail = check()
            status = "PASS"
        except ValidationSkip as exc:
            status = "SKIP"
            detail = str(exc)
        except Exception as exc:  # noqa: BLE001 - final validator must record all failures.
            status = "FAIL"
            detail = format_exception(exc)

        elapsed = time.perf_counter() - started
        result = CheckResult(
            name=name,
            status=status,
            detail=detail,
            duration_seconds=round(elapsed, 3),
        )
        self.results.append(result)
        print_result(result)

    @property
    def passed(self) -> int:
        return sum(result.status == "PASS" for result in self.results)

    @property
    def failed(self) -> int:
        return sum(result.status == "FAIL" for result in self.results)

    @property
    def skipped(self) -> int:
        return sum(result.status == "SKIP" for result in self.results)


def format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = exc.__class__.__name__
    return message.replace("\r\n", "\n")


def print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_result(result: CheckResult) -> None:
    print(f"[{result.status}] {result.name} ({result.duration_seconds:.3f}s)")
    if result.detail:
        for line in result.detail.splitlines():
            print(f"       {line}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def require_keys(data: Dict[str, Any], keys: Iterable[str], label: str) -> None:
    missing = [key for key in keys if key not in data]
    require(
        not missing,
        f"{label} is missing required field(s): {', '.join(missing)}",
    )


def compact_json(value: Any, limit: int = 1200) -> str:
    text = json.dumps(value, indent=2, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... output truncated ..."


def run_python_module(module_name: str, timeout_seconds: int = 120) -> str:
    process = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    combined_output = "\n".join(
        part.strip()
        for part in (process.stdout, process.stderr)
        if part and part.strip()
    )

    if process.returncode != 0:
        tail = "\n".join(combined_output.splitlines()[-30:])
        raise ValidationFailure(
            f"{module_name} exited with code {process.returncode}.\n{tail}"
        )

    nonempty_lines = [
        line.strip()
        for line in combined_output.splitlines()
        if line.strip()
    ]
    final_line = nonempty_lines[-1] if nonempty_lines else "completed successfully"
    return f"{module_name}: {final_line}"


def check_required_files() -> str:
    required_paths = [
        "app/api/main.py",
        "app/api/models.py",
        "app/api/routers/jobs.py",
        "app/api/routers/routes.py",
        "app/api/services/route_jobs.py",
        "app/api/services/route_summaries.py",
        "app/worker/celery_app.py",
        "app/worker/tasks.py",
        "route_risk/core/scoring.py",
        "route_risk/core/aggregation.py",
        "route_risk/core/driving_period.py",
        "route_risk/core/route_similarity.py",
        "route_risk/integrations/routing_client.py",
        "route_risk/integrations/ors_client.py",
        "route_risk/integrations/weather_client.py",
        "route_risk/integrations/road_conditions_client.py",
        "route_risk/integrations/state_511_clients/nevada_511_client.py",
        "route_risk/integrations/state_511_clients/arizona_511_client.py",
        "route_risk/integrations/state_511_clients/utah_udot_client.py",
        "route_risk/integrations/state_511_clients/state_event_loader.py",
        "scripts/benchmark.py",
        "scripts/run_scaling_experiment.ps1",
        "scripts/run_scaling_experiment.sh",
        "benchmarks/results.csv",
        "docker-compose.yml",
        "requirements.txt",
    ]

    missing = [
        relative_path
        for relative_path in required_paths
        if not (PROJECT_ROOT / relative_path).is_file()
    ]
    require(
        not missing,
        "Required project files are missing:\n- " + "\n- ".join(missing),
    )
    return f"Found all {len(required_paths)} required project files."


def check_python_compile() -> str:
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "app",
            "route_risk",
            "scripts",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    output = "\n".join(
        part.strip()
        for part in (process.stdout, process.stderr)
        if part and part.strip()
    )
    require(
        process.returncode == 0,
        "Python compile check failed.\n" + output,
    )
    return "Python source compiled without syntax errors."


def check_provider_registry() -> str:
    from route_risk.integrations.state_511_clients.state_event_loader import (
        STATE_EVENT_GROUP_FETCHERS,
        STATE_NAMES,
    )

    required_provider_codes = {"NV", "AZ", "UT"}
    registered = set(STATE_EVENT_GROUP_FETCHERS)
    named = set(STATE_NAMES)

    require(
        required_provider_codes.issubset(registered),
        "Provider registry is missing: "
        + ", ".join(sorted(required_provider_codes - registered)),
    )
    require(
        required_provider_codes.issubset(named),
        "State-name registry is missing: "
        + ", ".join(sorted(required_provider_codes - named)),
    )
    require(
        all(callable(STATE_EVENT_GROUP_FETCHERS[code]) for code in required_provider_codes),
        "One or more registered provider fetchers are not callable.",
    )

    return "Nevada, Arizona, and Utah provider clients are registered."


def check_automatic_state_detection() -> str:
    from app.api.services.route_jobs import _detect_supported_state_codes

    state_points = {
        "NV": {"latitude": 36.1716, "longitude": -115.1391},
        "AZ": {"latitude": 33.4484, "longitude": -112.0740},
        "UT": {"latitude": 40.7608, "longitude": -111.8910},
    }

    observations = []
    for expected_code, point in state_points.items():
        detected = _detect_supported_state_codes(
            [{"geometry_coordinates": [point]}]
        )
        require(
            expected_code in detected,
            f"Expected {expected_code} for {point}, but detected {detected}.",
        )
        observations.append(f"{expected_code} -> {detected}")

    return "Automatic route-geometry detection passed: " + "; ".join(observations)


def parse_float(row: Dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationFailure(
            f"Benchmark row has an invalid {key!r} value: {row.get(key)!r}"
        ) from exc


def parse_int(row: Dict[str, str], key: str) -> int:
    try:
        return int(float(row[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationFailure(
            f"Benchmark row has an invalid {key!r} value: {row.get(key)!r}"
        ) from exc


def check_benchmark_evidence() -> str:
    results_path = PROJECT_ROOT / "benchmarks" / "results.csv"
    with results_path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    successful_rows = [
        row
        for row in rows
        if row.get("workload", "").strip() == "route_risk"
        and row.get("final_status", "").strip().upper() == "SUCCESS"
        and parse_int(row, "failed_tasks") == 0
    ]
    require(successful_rows, "No successful route_risk benchmark rows were found.")

    grouped: Dict[int, List[Dict[str, str]]] = {}
    for row in successful_rows:
        grouped.setdefault(parse_int(row, "task_count"), []).append(row)

    best_evidence: Optional[Tuple[int, int, float, float, float]] = None
    for task_count, group_rows in grouped.items():
        one_worker_rows = [
            row for row in group_rows if parse_int(row, "worker_count") == 1
        ]
        higher_worker_rows = [
            row for row in group_rows if parse_int(row, "worker_count") > 1
        ]
        if not one_worker_rows or not higher_worker_rows:
            continue

        baseline = min(
            one_worker_rows,
            key=lambda row: parse_float(row, "total_runtime_seconds"),
        )
        baseline_runtime = parse_float(baseline, "total_runtime_seconds")

        for candidate in higher_worker_rows:
            candidate_runtime = parse_float(
                candidate,
                "total_runtime_seconds",
            )
            runtime_speedup = baseline_runtime / candidate_runtime
            throughput_ratio = (
                parse_float(candidate, "throughput_tasks_per_second")
                / parse_float(baseline, "throughput_tasks_per_second")
            )
            evidence = (
                task_count,
                parse_int(candidate, "worker_count"),
                runtime_speedup,
                throughput_ratio,
                candidate_runtime,
            )
            if best_evidence is None or runtime_speedup > best_evidence[2]:
                best_evidence = evidence

    require(
        best_evidence is not None,
        "Could not find matching 1-worker and higher-worker benchmark rows.",
    )

    task_count, worker_count, runtime_speedup, throughput_ratio, runtime = best_evidence
    require(
        runtime_speedup >= 2.0 or throughput_ratio >= 2.0,
        (
            "Benchmark evidence did not reach 2x improvement. "
            f"Best runtime speedup={runtime_speedup:.2f}x, "
            f"throughput ratio={throughput_ratio:.2f}x."
        ),
    )

    return (
        f"{task_count} tasks: 1 worker to {worker_count} workers produced "
        f"{runtime_speedup:.2f}x runtime speedup and "
        f"{throughput_ratio:.2f}x throughput; higher-worker runtime "
        f"was {runtime:.3f}s."
    )


class ApiClient:
    def __init__(
        self,
        base_url: str,
        request_timeout_seconds: float,
        job_timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds
        self.job_timeout_seconds = job_timeout_seconds
        self.session = requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: Sequence[int] = (200,),
        **kwargs: Any,
    ) -> requests.Response:
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            timeout=self.request_timeout_seconds,
            **kwargs,
        )
        if response.status_code not in expected_statuses:
            try:
                body = compact_json(response.json())
            except ValueError:
                body = response.text[:1200]
            raise ValidationFailure(
                f"{method} {path} returned HTTP {response.status_code}; "
                f"expected {list(expected_statuses)}.\n{body}"
            )
        return response

    def json(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: Sequence[int] = (200,),
        **kwargs: Any,
    ) -> Dict[str, Any]:
        response = self.request(
            method,
            path,
            expected_statuses=expected_statuses,
            **kwargs,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise ValidationFailure(
                f"{method} {path} did not return valid JSON."
            ) from exc
        require(
            isinstance(data, dict),
            f"{method} {path} returned JSON that was not an object.",
        )
        return data

    def wait_for_job(self, job_id: str) -> Dict[str, Any]:
        deadline = time.monotonic() + self.job_timeout_seconds
        last_status: Optional[Dict[str, Any]] = None

        while time.monotonic() < deadline:
            status = self.json("GET", f"/job_status/{job_id}")
            last_status = status
            status_name = str(status.get("status", "")).upper()

            if status_name in TERMINAL_JOB_STATUSES:
                require(
                    status_name == "SUCCESS",
                    (
                        f"Job {job_id} ended with {status_name}.\n"
                        f"{compact_json(status)}"
                    ),
                )
                return status

            time.sleep(1.0)

        raise ValidationFailure(
            f"Job {job_id} did not finish within "
            f"{self.job_timeout_seconds:.0f} seconds.\n"
            f"Last status: {compact_json(last_status)}"
        )


def check_api_health(api: ApiClient) -> str:
    health = api.json("GET", "/")
    require_keys(health, ["message", "route_risk_status"], "Health response")
    require(
        "running" in str(health["message"]).lower(),
        f"Unexpected API health message: {health['message']!r}",
    )
    return (
        f"API responded at {api.base_url}; "
        f"{health['route_risk_status']}"
    )


def check_single_route_closure(api: ApiClient) -> str:
    payload = {
        "route_name": "Final Validation Rexburg to Idaho Falls",
        "origin_label": "Rexburg, ID",
        "origin_latitude": 43.8231,
        "origin_longitude": -111.7924,
        "destination_label": "Idaho Falls, ID",
        "destination_latitude": 43.4927,
        "destination_longitude": -112.0408,
        "checkpoint_count": 8,
        "road_condition": "normal",
        "road_event_radius_miles": 1.0,
        "road_events": [
            {
                "event_id": "validation-construction-rigby",
                "event_type": "construction",
                "description": "Predictable validation construction event.",
                "latitude": 43.59723,
                "longitude": -111.965417,
                "source": "final-validation",
            },
            {
                "event_id": "validation-closure-idaho-falls",
                "event_type": "road closure",
                "description": "Predictable validation full closure.",
                "latitude": 43.540506,
                "longitude": -112.007668,
                "source": "final-validation",
            },
        ],
        "is_night": False,
    }

    submitted = api.json(
        "POST",
        "/submit_routed_route_risk_job",
        json=payload,
    )
    require_keys(
        submitted,
        ["job_id", "task_count", "checkpoint_count", "summary_endpoint"],
        "Single-route submission",
    )
    job_id = str(submitted["job_id"])
    require(job_id.strip() != "", "Single-route submission returned an empty job ID.")
    require(
        int(submitted["task_count"]) >= 2,
        "Single-route submission created fewer than two worker tasks.",
    )

    status = api.wait_for_job(job_id)
    require(
        int(status.get("completed_tasks", 0))
        == int(status.get("total_tasks", -1)),
        f"Not all distributed tasks completed.\n{compact_json(status)}",
    )
    require(
        int(status.get("failed_tasks", 0)) == 0,
        f"One or more distributed tasks failed.\n{compact_json(status)}",
    )

    summary = api.json("GET", f"/route_risk_summary/{job_id}")
    require_keys(
        summary,
        [
            "route_status",
            "distance_meters",
            "duration_seconds",
            "checkpoint_count",
            "route_risk_score",
            "route_risk_level",
            "route_blocked",
            "average_segment_score",
            "highest_risk_segment",
            "blocking_segment_count",
            "summary",
        ],
        "Single-route summary",
    )
    require(
        str(summary["route_status"]).upper() == "READY",
        f"Route summary was not READY.\n{compact_json(summary)}",
    )
    require(
        bool(summary["route_blocked"]),
        "Predictable full closure did not block the route.",
    )
    require(
        str(summary["route_risk_level"]).lower() == "blocked",
        f"Expected Blocked risk level; got {summary['route_risk_level']!r}.",
    )
    require(
        float(summary["route_risk_score"]) == 100.0,
        f"Expected blocked route score 100; got {summary['route_risk_score']!r}.",
    )
    require(
        int(summary["blocking_segment_count"]) >= 1,
        "Blocked route did not identify a blocking checkpoint.",
    )
    require(
        summary.get("highest_risk_segment") is not None,
        "Summary did not identify a highest-risk checkpoint.",
    )

    return (
        f"Job {job_id}: {status['completed_tasks']}/{status['total_tasks']} "
        f"Celery tasks completed; closure produced "
        f"{summary['route_risk_level']} score {summary['route_risk_score']} "
        f"with {summary['blocking_segment_count']} blocking checkpoint(s)."
    )


def check_route_comparison(api: ApiClient) -> str:
    payload = {
        "route_name": "Final Validation Las Vegas Route Comparison",
        "origin_label": "Downtown Las Vegas",
        "origin_latitude": 36.1716,
        "origin_longitude": -115.1391,
        "destination_label": "Harry Reid International Airport",
        "destination_latitude": 36.0840,
        "destination_longitude": -115.1537,
        "checkpoint_count": 6,
        "target_route_count": 3,
        "share_factor": 0.8,
        "weight_factor": 2.5,
        "road_condition": "normal",
        "road_event_radius_miles": 2.0,
        "road_events": [],
        "is_night": False,
        "use_live_state_events": False,
        "state_codes": [],
    }

    submitted = api.json(
        "POST",
        "/submit_route_comparison_job",
        json=payload,
    )
    require_keys(
        submitted,
        [
            "job_id",
            "route_candidate_count",
            "total_checkpoint_task_count",
            "summary_endpoint",
        ],
        "Route-comparison submission",
    )
    job_id = str(submitted["job_id"])
    require(
        int(submitted["route_candidate_count"]) >= 1,
        "Route comparison did not create a route candidate.",
    )
    require(
        int(submitted["total_checkpoint_task_count"]) >= 2,
        "Route comparison did not create enough distributed tasks.",
    )

    status = api.wait_for_job(job_id)
    summary = api.json("GET", f"/route_comparison_summary/{job_id}")

    routes = summary.get("routes")
    recommended = summary.get("recommended_route")
    require(
        isinstance(routes, list) and routes,
        f"Comparison summary did not contain evaluated routes.\n"
        f"{compact_json(summary)}",
    )
    require(
        isinstance(recommended, dict),
        f"Comparison summary did not contain a recommended route.\n"
        f"{compact_json(summary)}",
    )
    require_keys(
        recommended,
        [
            "route_label",
            "route_risk_score",
            "route_risk_level",
        ],
        "Recommended route",
    )
    require(
        int(status.get("failed_tasks", 0)) == 0,
        f"Route comparison contained failed worker tasks.\n{compact_json(status)}",
    )

    return (
        f"Job {job_id}: evaluated {len(routes)} route(s), completed "
        f"{status.get('completed_tasks')}/{status.get('total_tasks')} tasks, "
        f"and recommended {recommended['route_label']} "
        f"({recommended['route_risk_level']}, "
        f"score {recommended['route_risk_score']})."
    )


def check_long_route_error(api: ApiClient) -> str:
    payload = {
        "route_name": "Final Validation Long Route",
        "origin_label": "Rexburg, ID",
        "origin_latitude": 43.8231,
        "origin_longitude": -111.7924,
        "destination_label": "Phoenix, AZ",
        "destination_latitude": 33.4484,
        "destination_longitude": -112.0740,
        "checkpoint_count": 6,
        "target_route_count": 3,
        "share_factor": 0.8,
        "weight_factor": 2.5,
        "road_condition": "normal",
        "road_event_radius_miles": 2.0,
        "road_events": [],
        "is_night": False,
        "use_live_state_events": False,
        "state_codes": [],
    }

    response = api.request(
        "POST",
        "/submit_route_comparison_job",
        expected_statuses=(422,),
        json=payload,
    )
    data = response.json()
    detail = data.get("detail", {})
    require(
        isinstance(detail, dict),
        f"Expected structured long-route detail; got {compact_json(data)}",
    )
    require(
        detail.get("code") == "ROUTE_TOO_LONG_FOR_ALTERNATIVE_ROUTES",
        f"Unexpected long-route error code.\n{compact_json(data)}",
    )
    require(
        detail.get("maximum_distance_meters") == 100000,
        f"Long-route response did not report the expected limit.\n"
        f"{compact_json(data)}",
    )
    return (
        "Long alternative-route request returned the expected friendly "
        "HTTP 422 limitation response."
    )


def write_report(
    results: List[CheckResult],
    arguments: argparse.Namespace,
) -> Path:
    output_directory = PROJECT_ROOT / "benchmarks" / "validation"
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_directory / f"final_validation_{timestamp}.json"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "python_version": sys.version,
        "arguments": vars(arguments),
        "summary": {
            "passed": sum(item.status == "PASS" for item in results),
            "failed": sum(item.status == "FAIL" for item in results),
            "skipped": sum(item.status == "SKIP" for item in results),
            "overall_status": (
                "PASS"
                if not any(item.status == "FAIL" for item in results)
                else "FAIL"
            ),
        },
        "checks": [asdict(item) for item in results],
    }
    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Distributed Route Risk Engine final validation suite."
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help=f"FastAPI base URL. Default: {DEFAULT_API_BASE_URL}",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=45.0,
        help="Timeout in seconds for each HTTP request. Default: 45",
    )
    parser.add_argument(
        "--job-timeout",
        type=float,
        default=240.0,
        help="Maximum seconds to wait for each distributed job. Default: 240",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Run only local/static checks; skip all live API checks.",
    )
    parser.add_argument(
        "--skip-comparison",
        action="store_true",
        help="Skip the ORS multi-route comparison check.",
    )
    parser.add_argument(
        "--skip-long-route-check",
        action="store_true",
        help="Skip the long-alternative-route limitation check.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write a JSON validation report.",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    validator = Validator()

    print_header("DISTRIBUTED ROUTE RISK ENGINE - FINAL VALIDATION")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Python: {sys.executable}")
    print(f"API: {arguments.api_base_url}")
    print(f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}")

    print_header("1. PROJECT STRUCTURE AND SOURCE")
    validator.run("Required project files", check_required_files)
    validator.run("Python syntax compilation", check_python_compile)
    validator.run("State 511 provider registry", check_provider_registry)
    validator.run("Automatic route-state detection", check_automatic_state_detection)

    print_header("2. FOCUSED LOCAL REGRESSION TESTS")
    regression_modules = [
        (
            "Day/Night schedule precedence",
            "route_risk.testing.manual_driving_period_precedence_test",
        ),
        (
            "Geometry-aware closure matching",
            "route_risk.testing.manual_geometry_aware_closure_test",
        ),
        (
            "Nevada construction versus closure logic",
            "route_risk.testing.manual_nevada_construction_logic_test",
        ),
        (
            "Near-duplicate route filtering",
            "route_risk.testing.manual_route_similarity_test",
        ),
    ]
    for label, module_name in regression_modules:
        validator.run(
            label,
            lambda module_name=module_name: run_python_module(module_name),
        )

    print_header("3. BENCHMARK EVIDENCE")
    validator.run("Route-risk scaling evidence", check_benchmark_evidence)

    print_header("4. LIVE DISTRIBUTED API VALIDATION")
    api = ApiClient(
        base_url=arguments.api_base_url,
        request_timeout_seconds=arguments.request_timeout,
        job_timeout_seconds=arguments.job_timeout,
    )

    if arguments.skip_api:
        validator.run(
            "API health and capability",
            lambda: (_ for _ in ()).throw(
                ValidationSkip("Skipped by --skip-api.")
            ),
        )
        validator.run(
            "Distributed single-route closure workflow",
            lambda: (_ for _ in ()).throw(
                ValidationSkip("Skipped by --skip-api.")
            ),
        )
        validator.run(
            "Distributed route comparison and recommendation",
            lambda: (_ for _ in ()).throw(
                ValidationSkip("Skipped by --skip-api.")
            ),
        )
        validator.run(
            "Friendly long-route limitation response",
            lambda: (_ for _ in ()).throw(
                ValidationSkip("Skipped by --skip-api.")
            ),
        )
    else:
        validator.run(
            "API health and capability",
            lambda: check_api_health(api),
        )
        validator.run(
            "Distributed single-route closure workflow",
            lambda: check_single_route_closure(api),
        )

        if arguments.skip_comparison:
            validator.run(
                "Distributed route comparison and recommendation",
                lambda: (_ for _ in ()).throw(
                    ValidationSkip("Skipped by --skip-comparison.")
                ),
            )
        else:
            validator.run(
                "Distributed route comparison and recommendation",
                lambda: check_route_comparison(api),
            )

        if arguments.skip_long_route_check:
            validator.run(
                "Friendly long-route limitation response",
                lambda: (_ for _ in ()).throw(
                    ValidationSkip("Skipped by --skip-long-route-check.")
                ),
            )
        elif arguments.skip_comparison:
            validator.run(
                "Friendly long-route limitation response",
                lambda: (_ for _ in ()).throw(
                    ValidationSkip(
                        "Skipped because --skip-comparison was supplied."
                    )
                ),
            )
        else:
            validator.run(
                "Friendly long-route limitation response",
                lambda: check_long_route_error(api),
            )

    print_header("FINAL RESULT")
    total = len(validator.results)
    print(f"PASS: {validator.passed}")
    print(f"FAIL: {validator.failed}")
    print(f"SKIP: {validator.skipped}")
    print(f"TOTAL: {total}")

    report_path: Optional[Path] = None
    if not arguments.no_report:
        report_path = write_report(validator.results, arguments)
        print(f"Report: {report_path}")

    if validator.failed:
        print()
        print("OVERALL STATUS: FAIL")
        print("Fix the failed checks and rerun the same command.")
        return 1

    print()
    print("OVERALL STATUS: PASS")
    print("The validated project areas are ready for final demonstration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
