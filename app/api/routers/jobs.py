import json
from typing import Any, Dict

from fastapi import APIRouter

from app.api.job_store import (
    build_job_status_response,
    get_task_results,
    load_job,
)
from app.api.services.route_summaries import (
    build_route_comparison_summary_response,
)
from route_risk.core.aggregation import (
    aggregate_job_results,
)


router = APIRouter(
    tags=["Jobs"],
)


@router.get("/job_status/{job_id}")
def job_status(
    job_id: str,
) -> Dict[str, Any]:
    """
    Return distributed task progress for a stored job.
    """

    return build_job_status_response(
        job_id
    )


@router.get("/results/{job_id}")
def results(
    job_id: str,
) -> Dict[str, Any]:
    """
    Return raw task results and workload-specific aggregation.
    """

    job_data = load_job(
        job_id
    )

    task_ids = json.loads(
        job_data["task_ids"]
    )

    task_results = get_task_results(
        task_ids
    )

    workload = job_data.get(
        "workload",
        "unknown",
    )

    response: Dict[str, Any] = {
        "job_id": job_id,
        "workload": workload,
        "metadata": json.loads(
            job_data.get(
                "metadata",
                "{}",
            )
        ),
        "results": task_results,
    }

    if workload == "route_risk_segments":
        response["aggregated_route_risk"] = (
            aggregate_job_results(
                task_results
            )
        )

    if workload == "route_comparison":
        response["route_comparison"] = (
            build_route_comparison_summary_response(
                job_id
            )
        )

    return response