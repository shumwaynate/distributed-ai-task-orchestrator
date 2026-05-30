import math
import os
import random
import time
from typing import Any, Dict, List, Union

# Keep NumPy from using multiple internal threads per Celery worker process.
# This makes worker-count scaling tests cleaner and easier to interpret.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np

from app.worker.celery_app import celery_app
from route_risk.scoring import score_route, score_segment


# ============================================================
# ORIGINAL ORCHESTRATOR LOGIC
# ============================================================
#
# These tasks belong to the original Distributed AI Task Orchestrator.
#
# They are being preserved because they demonstrate:
# - FastAPI / Redis / Celery distributed execution
# - deterministic task processing
# - retry behavior
# - failure handling
# - benchmarkable CPU workloads
# - scaling experiments
#
# The Route Risk Engine pivot should build on this infrastructure instead
# of deleting it.


@celery_app.task
def square_number(x: int) -> int:
    """
    Basic deterministic task used for simple API testing.
    """
    return x * x


@celery_app.task
def slow_square_number(x: int, delay_seconds: float = 1.0) -> int:
    """
    Controlled delay workload used for baseline scaling tests.

    This is useful because each task takes a predictable amount of time,
    making worker scaling easy to measure.
    """
    time.sleep(delay_seconds)
    return x * x


@celery_app.task(bind=True, max_retries=3)
def unreliable_square(self, x: int, fail_on_even: bool = True) -> int:
    """
    Permanent failure test task.

    If fail_on_even is true, even numbers intentionally fail. Celery retries the
    task up to max_retries, but because the failure condition never changes,
    even-numbered tasks eventually end in FAILURE.

    This is useful for proving that the system can detect failed tasks and
    report PARTIAL_FAILURE at the job level.
    """
    try:
        if fail_on_even and x % 2 == 0:
            raise ValueError(f"Intentional failure for even number: {x}")

        return x * x

    except Exception as exc:
        raise self.retry(exc=exc, countdown=1)


@celery_app.task(bind=True, max_retries=3)
def transient_unreliable_square(
    self,
    x: int,
    fail_attempts: int = 2,
) -> Dict[str, Union[int, str]]:
    """
    Transient failure test task.

    This task intentionally fails for the first fail_attempts attempts, then
    succeeds on a later retry.

    Celery's self.request.retries value starts at 0 on the first attempt.
    For example, if fail_attempts is 2:

    attempt 1: retries = 0, fail and retry
    attempt 2: retries = 1, fail and retry
    attempt 3: retries = 2, succeed

    This is useful for proving that retry behavior works, not just failure
    reporting.
    """
    current_retry_count = self.request.retries
    current_attempt_number = current_retry_count + 1

    try:
        if current_retry_count < fail_attempts:
            raise ValueError(
                f"Transient failure for {x} on attempt {current_attempt_number}"
            )

        return {
            "input": x,
            "output": x * x,
            "workload": "transient_unreliable",
            "attempts": current_attempt_number,
            "retries_used": current_retry_count,
            "status": "succeeded_after_retry",
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=1)


def _deterministic_vector(seed: int, size: int) -> List[float]:
    """
    Creates a deterministic pseudo-random vector.

    The seed makes the workload repeatable for the same input values.
    """
    rng = random.Random(seed)
    return [rng.random() for _ in range(size)]


def _dot_product(a: List[float], b: List[float]) -> float:
    """
    Computes the dot product of two vectors.
    """
    return sum(x * y for x, y in zip(a, b))


@celery_app.task
def vector_similarity_task(task_id: int, vector_size: int = 1000) -> Dict[str, float]:
    """
    AI-style deterministic vector similarity workload.

    This simulates the kind of vector math used in embedding comparison,
    recommendation systems, retrieval systems, and other AI-adjacent systems.

    The output is a small summary rather than a huge vector.
    """
    vector_a = _deterministic_vector(task_id, vector_size)
    vector_b = _deterministic_vector(task_id + 10_000, vector_size)

    dot = _dot_product(vector_a, vector_b)
    magnitude_a = math.sqrt(_dot_product(vector_a, vector_a))
    magnitude_b = math.sqrt(_dot_product(vector_b, vector_b))

    if magnitude_a == 0 or magnitude_b == 0:
        cosine_similarity = 0.0
    else:
        cosine_similarity = dot / (magnitude_a * magnitude_b)

    return {
        "task_id": task_id,
        "workload": "vector",
        "vector_size": vector_size,
        "cosine_similarity": round(cosine_similarity, 8),
        "checksum": round(dot, 8),
    }


def _matrix_iterations_for_size(matrix_size: int) -> int:
    """
    Chooses a repeat count for the matrix workload.

    NumPy matrix multiplication can be very fast after initial warmup.
    Repeating the multiplication inside each task makes the workload more
    consistent and gives the scaling experiment enough work to measure.

    Smaller matrices need more iterations.
    Larger matrices need fewer iterations.
    """
    if matrix_size <= 250:
        return 160

    if matrix_size <= 300:
        return 120

    if matrix_size <= 400:
        return 80

    if matrix_size <= 500:
        return 60

    if matrix_size <= 700:
        return 40

    return 25


@celery_app.task
def matrix_compute_task(task_id: int, matrix_size: int = 700) -> Dict[str, float]:
    """
    AI-style deterministic NumPy matrix compute workload.

    This simulates CPU-based numerical work similar to what appears in
    machine learning pipelines, vector processing, and scientific computing.

    The workload is deterministic because each task uses a seeded NumPy random
    generator. The task returns a checksum instead of the full matrix so results
    stay small and easy to store.

    To make timing more stable, each task performs repeated matrix
    multiplications. This reduces the impact of one-time NumPy warmup and makes
    worker scaling easier to measure.
    """
    rng = np.random.default_rng(seed=task_id)

    matrix_a = rng.random((matrix_size, matrix_size), dtype=np.float64)
    matrix_b = rng.random((matrix_size, matrix_size), dtype=np.float64)

    iterations = _matrix_iterations_for_size(matrix_size)
    checksum = 0.0

    for _ in range(iterations):
        result_matrix = matrix_a @ matrix_b
        checksum += float(np.sum(result_matrix))

    return {
        "task_id": task_id,
        "workload": "matrix",
        "matrix_size": matrix_size,
        "iterations": iterations,
        "checksum": round(checksum, 8),
    }


# ============================================================
# ROUTE RISK ENGINE LOGIC
# ============================================================
#
# These tasks belong to the new Route Risk / Driving Recommendation Engine
# direction.
#
# Important design goal:
# The Route Risk Engine should reuse the existing distributed orchestrator
# infrastructure instead of replacing it.
#
# Current stage:
# - Uses local/sample route data only.
# - Does not call live APIs yet.
# - Proves that route-risk workloads can run inside Celery workers.
#
# Future stages:
# - Add live weather data.
# - Add road-condition data.
# - Add routing/geocoding data.
# - Benchmark route-risk workloads across multiple worker containers.


@celery_app.task
def route_segment_risk_task(
    task_id: int,
    segment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score a single route segment inside a Celery worker.

    This is the first Route Risk Engine workload added to the original
    Distributed AI Task Orchestrator.

    Parameters:
        task_id:
            Numeric ID used for tracking and benchmark consistency.

        segment:
            Dictionary containing:
            - label
            - weather
            - road_condition
            - is_night

    Returns:
        Dictionary containing:
        - task_id
        - workload
        - segment_label
        - risk_score
        - risk_level
        - factors

    Why this matters:
    Each route segment can be processed independently, which makes it a good
    fit for distributed Celery workers.
    """

    segment_result = score_segment(
        weather=segment.get("weather", {}),
        road_condition=segment.get("road_condition", "normal"),
        is_night=segment.get("is_night", False),
    )

    return {
        "task_id": task_id,
        "workload": "route_segment_risk",
        "segment_label": segment.get("label", "Unnamed segment"),
        "risk_score": segment_result["risk_score"],
        "risk_level": segment_result["risk_level"],
        "factors": segment_result["factors"],
    }


@celery_app.task
def route_risk_summary_task(
    task_id: int,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Score a full route inside a Celery worker.

    This task is useful for early testing because it allows one worker task to
    process a complete sample route and return a readable risk summary.

    Later, we can split the route into separate segment tasks and combine the
    results using the existing job/status/result infrastructure.

    Parameters:
        task_id:
            Numeric ID used for tracking and benchmark consistency.

        segments:
            List of route segment dictionaries.

    Returns:
        Dictionary containing full route-risk results.
    """

    route_result = score_route(segments)

    return {
        "task_id": task_id,
        "workload": "route_risk_summary",
        "route_risk_score": route_result["route_risk_score"],
        "route_risk_level": route_result["route_risk_level"],
        "segment_results": route_result["segment_results"],
        "summary": route_result["summary"],
    }