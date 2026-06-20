from typing import Any, Dict

from fastapi import APIRouter

from app.api.models import (
    RouteComparisonJobRequest,
    RoutedRouteRiskJobRequest,
)
from app.api.services.route_jobs import (
    submit_comparison_job,
    submit_single_route_job,
)
from app.api.services.route_summaries import (
    build_route_comparison_summary_response,
    build_route_risk_summary_response,
)


router = APIRouter(
    tags=["Route Risk"],
)


@router.post("/submit_routed_route_risk_job")
def submit_routed_route_risk_job(
    request: RoutedRouteRiskJobRequest,
) -> Dict[str, Any]:
    """
    Submit one routed live-weather risk-analysis job.
    """

    return submit_single_route_job(
        request
    )


@router.post("/submit_route_comparison_job")
def submit_route_comparison_job(
    request: RouteComparisonJobRequest,
) -> Dict[str, Any]:
    """
    Submit a distributed multi-route comparison job.
    """

    return submit_comparison_job(
        request
    )


@router.get("/route_risk_summary/{job_id}")
def route_risk_summary(
    job_id: str,
) -> Dict[str, Any]:
    """
    Return a summarized single-route result.
    """

    return build_route_risk_summary_response(
        job_id
    )


@router.get("/route_comparison_summary/{job_id}")
def route_comparison_summary(
    job_id: str,
) -> Dict[str, Any]:
    """
    Return a summarized multi-route comparison.
    """

    return build_route_comparison_summary_response(
        job_id
    )