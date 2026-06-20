import json
import os
from typing import Any, Dict, List
from uuid import uuid4

import redis
from celery.result import AsyncResult
from fastapi import HTTPException

from app.worker.celery_app import celery_app


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def create_job(
    workload: str,
    task_ids: List[str],
    metadata: Dict[str, Any],
) -> str:
    job_id = str(uuid4())

    redis_client.hset(
        _job_key(job_id),
        mapping={
            "job_id": job_id,
            "workload": workload,
            "task_ids": json.dumps(task_ids),
            "total_tasks": len(task_ids),
            "metadata": json.dumps(metadata),
        },
    )

    return job_id


def load_job(job_id: str) -> Dict[str, Any]:
    job_data = redis_client.hgetall(
        _job_key(job_id)
    )

    if not job_data:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job_data


def get_task_results(
    task_ids: List[str],
) -> List[Dict[str, Any]]:
    results = []

    for task_id in task_ids:
        async_result = AsyncResult(
            task_id,
            app=celery_app,
        )

        task_info = {
            "task_id": task_id,
            "status": async_result.status,
            "result": None,
            "error": None,
        }

        if async_result.successful():
            task_info["result"] = async_result.result

        elif async_result.failed():
            task_info["error"] = str(
                async_result.result
            )

        results.append(task_info)

    return results


def build_job_status_response(
    job_id: str,
) -> Dict[str, Any]:
    job_data = load_job(job_id)

    task_ids = json.loads(
        job_data["task_ids"]
    )

    total_tasks = int(
        job_data["total_tasks"]
    )

    completed_tasks = 0
    failed_tasks = 0
    pending_tasks = 0
    running_tasks = 0
    retrying_tasks = 0

    for task_id in task_ids:
        async_result = AsyncResult(
            task_id,
            app=celery_app,
        )

        if async_result.successful():
            completed_tasks += 1

        elif async_result.failed():
            failed_tasks += 1

        elif async_result.status == "RETRY":
            retrying_tasks += 1

        elif async_result.status == "PENDING":
            pending_tasks += 1

        else:
            running_tasks += 1

    unfinished_tasks = (
        pending_tasks
        + running_tasks
        + retrying_tasks
    )

    finished_tasks = (
        completed_tasks
        + failed_tasks
    )

    if total_tasks > 0:
        progress_percent = round(
            (finished_tasks / total_tasks) * 100,
            2,
        )
    else:
        progress_percent = 0.0

    if (
        failed_tasks > 0
        and finished_tasks == total_tasks
    ):
        status = "PARTIAL_FAILURE"

    elif completed_tasks == total_tasks:
        status = "SUCCESS"

    elif (
        unfinished_tasks > 0
        or finished_tasks > 0
    ):
        status = "IN_PROGRESS"

    else:
        status = "PENDING"

    return {
        "job_id": job_id,
        "workload": job_data.get(
            "workload",
            "unknown",
        ),
        "status": status,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "pending_tasks": pending_tasks,
        "running_tasks": running_tasks,
        "retrying_tasks": retrying_tasks,
        "progress_percent": progress_percent,
        "metadata": json.loads(
            job_data.get(
                "metadata",
                "{}",
            )
        ),
    }