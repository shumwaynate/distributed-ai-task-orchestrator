import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.api.job_store import get_task_results, load_job
from route_risk.core.aggregation import aggregate_job_results


def choose_recommended_route(
    scored_routes: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Choose the recommended route.

    Current ranking behavior is preserved during the refactor:

    1. Prefer usable routes over blocked routes.
    2. Prefer the lower risk score.
    3. Prefer the shorter duration.
    4. Prefer the shorter distance.

    The all-routes-blocked behavior will be improved after the refactor.
    """

    if not scored_routes:
        return None

    usable_routes = [
        route
        for route in scored_routes
        if not route.get(
            "route_blocked",
            False,
        )
    ]

    candidate_routes = (
        usable_routes
        if usable_routes
        else scored_routes
    )

    return sorted(
        candidate_routes,
        key=lambda route: (
            route.get(
                "route_risk_score",
                999,
            ),
            route.get(
                "duration_seconds",
                999999999,
            ),
            route.get(
                "distance_meters",
                999999999,
            ),
        ),
    )[0]


def _combine_upcoming_route_disclosures(
    scored_routes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Combine duplicate upcoming-event disclosures across route candidates.
    """

    combined_by_key: Dict[
        Tuple[str, str],
        Dict[str, Any],
    ] = {}

    for route in scored_routes:
        route_id = route.get("route_id")
        route_label = route.get("route_label")

        for disclosure in route.get(
            "upcoming_road_events",
            [],
        ):
            event_key = (
                str(
                    disclosure.get(
                        "source",
                        "",
                    )
                ),
                str(
                    disclosure.get(
                        "event_id",
                        "",
                    )
                ),
            )

            if event_key not in combined_by_key:
                combined_disclosure = dict(
                    disclosure
                )

                combined_disclosure.pop(
                    "checkpoint_labels",
                    None,
                )

                combined_disclosure.pop(
                    "matched_checkpoint_count",
                    None,
                )

                combined_disclosure["affected_routes"] = []
                combined_disclosure["route_matches"] = []

                combined_by_key[event_key] = (
                    combined_disclosure
                )

            combined_disclosure = combined_by_key[
                event_key
            ]

            if route_label not in combined_disclosure[
                "affected_routes"
            ]:
                combined_disclosure[
                    "affected_routes"
                ].append(
                    route_label
                )

            combined_disclosure[
                "route_matches"
            ].append(
                {
                    "route_id": route_id,
                    "route_label": route_label,
                    "checkpoint_labels": disclosure.get(
                        "checkpoint_labels",
                        [],
                    ),
                    "matched_checkpoint_count": disclosure.get(
                        "matched_checkpoint_count",
                        0,
                    ),
                }
            )

    return list(
        combined_by_key.values()
    )


def build_route_risk_summary_response(
    job_id: str,
) -> Dict[str, Any]:
    """
    Build a clean user-facing single-route summary.
    """

    job_data = load_job(job_id)

    workload = job_data.get(
        "workload",
        "unknown",
    )

    if workload != "route_risk_segments":
        raise HTTPException(
            status_code=400,
            detail=(
                "This endpoint only supports route_risk_segments jobs. "
                f"Job workload was: {workload}"
            ),
        )

    task_ids = json.loads(
        job_data["task_ids"]
    )

    task_results = get_task_results(
        task_ids
    )

    metadata = json.loads(
        job_data.get(
            "metadata",
            "{}",
        )
    )

    aggregated_route_risk = aggregate_job_results(
        task_results
    )

    incomplete_tasks = [
        task_result
        for task_result in task_results
        if task_result.get("status") != "SUCCESS"
    ]

    route_status = (
        "INCOMPLETE"
        if incomplete_tasks
        else "READY"
    )

    blocking_segments = aggregated_route_risk.get(
        "blocking_segments",
        [],
    )

    return {
        "job_id": job_id,
        "route_status": route_status,
        "route_name": metadata.get(
            "route_name"
        ),
        "origin": metadata.get(
            "origin"
        ),
        "destination": metadata.get(
            "destination"
        ),
        "segment_count": metadata.get(
            "segment_count"
        ),
        "coordinate_segment_count": metadata.get(
            "coordinate_segment_count"
        ),
        "weather_mode": metadata.get(
            "weather_mode"
        ),
        "route_source": metadata.get(
            "route_source"
        ),
        "distance_meters": metadata.get(
            "distance_meters"
        ),
        "duration_seconds": metadata.get(
            "duration_seconds"
        ),
        "geometry_point_count": metadata.get(
            "geometry_point_count"
        ),
        "checkpoint_count": metadata.get(
            "checkpoint_count"
        ),
        "road_event_count": metadata.get(
            "road_event_count"
        ),
        "matched_road_event_checkpoint_count": metadata.get(
            "matched_road_event_checkpoint_count"
        ),
        "route_risk_score": aggregated_route_risk[
            "route_risk_score"
        ],
        "route_risk_level": aggregated_route_risk[
            "route_risk_level"
        ],
        "route_blocked": aggregated_route_risk.get(
            "route_blocked",
            False,
        ),
        "route_warning": aggregated_route_risk.get(
            "route_warning"
        ),
        "average_segment_score": aggregated_route_risk.get(
            "average_segment_score"
        ),
        "highest_risk_segment": aggregated_route_risk.get(
            "highest_risk_segment"
        ),
        "blocking_segments": blocking_segments,
        "blocking_segment_count": len(
            blocking_segments
        ),
        "incomplete_task_count": aggregated_route_risk.get(
            "incomplete_task_count",
            0,
        ),
        "summary": aggregated_route_risk[
            "summary"
        ],
    }


def build_route_comparison_summary_response(
    job_id: str,
) -> Dict[str, Any]:
    """
    Build the distributed multi-route comparison result.
    """

    job_data = load_job(job_id)

    workload = job_data.get(
        "workload",
        "unknown",
    )

    if workload != "route_comparison":
        raise HTTPException(
            status_code=400,
            detail=(
                "This endpoint only supports route_comparison jobs. "
                f"Job workload was: {workload}"
            ),
        )

    task_ids = json.loads(
        job_data["task_ids"]
    )

    task_results = get_task_results(
        task_ids
    )

    task_result_map = {
        task_result["task_id"]: task_result
        for task_result in task_results
    }

    metadata = json.loads(
        job_data.get(
            "metadata",
            "{}",
        )
    )

    scored_routes = []

    for route_metadata in metadata.get(
        "routes",
        [],
    ):
        route_task_results = [
            task_result_map[task_id]
            for task_id in route_metadata.get(
                "task_ids",
                [],
            )
            if task_id in task_result_map
        ]

        aggregated_route_risk = aggregate_job_results(
            route_task_results
        )

        blocking_segments = aggregated_route_risk.get(
            "blocking_segments",
            [],
        )

        incomplete_task_count = aggregated_route_risk.get(
            "incomplete_task_count",
            0,
        )

        route_status = (
            "INCOMPLETE"
            if incomplete_task_count > 0
            else "READY"
        )

        scored_routes.append(
            {
                "route_id": route_metadata[
                    "route_id"
                ],
                "route_label": route_metadata.get(
                    "route_label"
                ),
                "route_status": route_status,
                "source": route_metadata.get(
                    "source"
                ),
                "provider": route_metadata.get(
                    "provider"
                ),
                "distance_meters": route_metadata.get(
                    "distance_meters"
                ),
                "duration_seconds": route_metadata.get(
                    "duration_seconds"
                ),
                "geometry_point_count": route_metadata.get(
                    "geometry_point_count"
                ),
                "geometry_coordinates": route_metadata.get(
                    "geometry_coordinates",
                    [],
                ),
                "checkpoint_count": route_metadata.get(
                    "checkpoint_count"
                ),
                "matched_road_event_checkpoint_count": (
                    route_metadata.get(
                        "matched_road_event_checkpoint_count",
                        0,
                    )
                ),
                "matched_upcoming_road_event_checkpoint_count": (
                    route_metadata.get(
                        "matched_upcoming_road_event_checkpoint_count",
                        0,
                    )
                ),
                "upcoming_road_event_count": len(
                    route_metadata.get(
                        "upcoming_road_events",
                        [],
                    )
                ),
                "upcoming_road_events": route_metadata.get(
                    "upcoming_road_events",
                    [],
                ),
                "route_risk_score": aggregated_route_risk.get(
                    "route_risk_score"
                ),
                "route_risk_level": aggregated_route_risk.get(
                    "route_risk_level"
                ),
                "route_blocked": aggregated_route_risk.get(
                    "route_blocked",
                    False,
                ),
                "route_warning": aggregated_route_risk.get(
                    "route_warning"
                ),
                "average_segment_score": aggregated_route_risk.get(
                    "average_segment_score"
                ),
                "highest_risk_segment": aggregated_route_risk.get(
                    "highest_risk_segment"
                ),
                "blocking_segments": blocking_segments,
                "blocking_segment_count": len(
                    blocking_segments
                ),
                "incomplete_task_count": incomplete_task_count,
                "summary": aggregated_route_risk.get(
                    "summary"
                ),
                "aggregated_route_risk": aggregated_route_risk,
            }
        )

    recommended_route = choose_recommended_route(
        scored_routes
    )

    incomplete_routes = [
        route
        for route in scored_routes
        if route.get(
            "route_status"
        ) != "READY"
    ]

    comparison_status = (
        "INCOMPLETE"
        if incomplete_routes
        else "READY"
    )

    upcoming_disclosures = (
        _combine_upcoming_route_disclosures(
            scored_routes
        )
    )

    return {
        "job_id": job_id,
        "comparison_status": comparison_status,
        "route_name": metadata.get(
            "route_name"
        ),
        "origin": metadata.get(
            "origin"
        ),
        "destination": metadata.get(
            "destination"
        ),
        "route_source": metadata.get(
            "route_source"
        ),
        "route_candidate_count": len(
            scored_routes
        ),
        "checkpoint_count_per_route": metadata.get(
            "checkpoint_count_per_route"
        ),
        "total_checkpoint_task_count": len(
            task_ids
        ),
        "weather_mode": metadata.get(
            "weather_mode"
        ),
        "use_live_state_events": metadata.get(
            "use_live_state_events",
            False,
        ),
        "state_codes": metadata.get(
            "state_codes",
            [],
        ),
        "manual_road_event_count": metadata.get(
            "manual_road_event_count",
            0,
        ),
        "live_state_event_count": metadata.get(
            "live_state_event_count",
            0,
        ),
        "active_state_event_count": metadata.get(
            "active_state_event_count",
            metadata.get(
                "live_state_event_count",
                0,
            ),
        ),
        "upcoming_state_event_count": metadata.get(
            "upcoming_state_event_count",
            0,
        ),
        "road_event_count": metadata.get(
            "road_event_count",
            0,
        ),
        "upcoming_road_event_disclosure_count": len(
            upcoming_disclosures
        ),
        "upcoming_road_event_disclosures": (
            upcoming_disclosures
        ),
        "road_event_radius_miles": metadata.get(
            "road_event_radius_miles"
        ),
        "routes": scored_routes,
        "recommended_route": recommended_route,
    }