from typing import Any, Dict, List

from app.worker.celery_app import celery_app
from route_risk.core.scoring import score_route, score_segment
from route_risk.integrations.weather_client import (
    fetch_weather_for_coordinate,
)


def _build_road_context_result(
    segment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract road-condition context from a route segment.
    """

    return {
        "road_condition": segment.get(
            "road_condition",
            "normal",
        ),
        "road_condition_source": segment.get(
            "road_condition_source",
            "request",
        ),
        "matched_road_event": segment.get(
            "matched_road_event"
        ),
        "nearby_road_event_count": segment.get(
            "nearby_road_event_count",
            0,
        ),
    }


def _build_route_context_result(
    segment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract optional route identity information from a segment.
    """

    return {
        "route_id": segment.get("route_id"),
        "route_label": segment.get("route_label"),
    }


@celery_app.task
def route_segment_risk_task(
    task_id: int,
    segment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score one route segment using weather supplied in the request.
    """

    road_context = _build_road_context_result(segment)
    route_context = _build_route_context_result(segment)

    segment_result = score_segment(
        weather=segment.get("weather", {}),
        road_condition=road_context["road_condition"],
        is_night=segment.get("is_night", False),
    )

    return {
        "task_id": task_id,
        "workload": "route_segment_risk",
        "weather_mode": "manual",
        **route_context,
        "segment_label": segment.get(
            "label",
            "Unnamed segment",
        ),
        "latitude": segment.get("latitude"),
        "longitude": segment.get("longitude"),
        **road_context,
        "risk_score": segment_result["risk_score"],
        "risk_level": segment_result["risk_level"],
        "factors": segment_result["factors"],
    }


@celery_app.task
def live_weather_route_segment_risk_task(
    task_id: int,
    segment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score one route checkpoint using live weather.
    """

    latitude = segment.get("latitude")
    longitude = segment.get("longitude")

    if latitude is None or longitude is None:
        raise ValueError(
            "live_weather_route_segment_risk_task "
            "requires both latitude and longitude."
        )

    road_context = _build_road_context_result(segment)
    route_context = _build_route_context_result(segment)

    live_weather = fetch_weather_for_coordinate(
        latitude=float(latitude),
        longitude=float(longitude),
    )

    segment_result = score_segment(
        weather=live_weather,
        road_condition=road_context["road_condition"],
        is_night=segment.get("is_night", False),
    )

    return {
        "task_id": task_id,
        "workload": "route_segment_risk",
        "weather_mode": "live",
        **route_context,
        "segment_label": segment.get(
            "label",
            "Unnamed segment",
        ),
        "latitude": latitude,
        "longitude": longitude,
        "weather": live_weather,
        **road_context,
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
    Score a complete route inside one Celery task.
    """

    route_result = score_route(segments)

    return {
        "task_id": task_id,
        "workload": "route_risk_summary",
        "route_risk_score": route_result[
            "route_risk_score"
        ],
        "route_risk_level": route_result[
            "route_risk_level"
        ],
        "segment_results": route_result[
            "segment_results"
        ],
        "summary": route_result["summary"],
    }
