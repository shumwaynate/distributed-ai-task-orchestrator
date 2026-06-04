"""
route_risk/testing/manual_routed_live_weather_test.py

Manual test for combining routing, live weather, scoring, and aggregation.

Purpose:
- Fetch a real route using OSRM.
- Sample checkpoints along the route geometry.
- Fetch live weather for each checkpoint using Open-Meteo.
- Score each checkpoint using the Route Risk Engine scoring logic.
- Aggregate checkpoint results into a route-level risk summary.

This test proves the Route Risk Engine concept before connecting generated
routes to FastAPI and Celery.

This test does NOT require:
- Redis
- Celery worker
- FastAPI
- Docker

It DOES require:
- Internet access
- OSRM API availability
- Open-Meteo API availability
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


# ============================================================
# IMPORT PATH SETUP FOR LOCAL MANUAL TESTING
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from route_risk.core.aggregation import aggregate_segment_results
from route_risk.core.scoring import score_segment
from route_risk.integrations.routing_client import fetch_route_between_coordinates
from route_risk.integrations.weather_client import fetch_weather_for_coordinate


# ============================================================
# ROUTED LIVE WEATHER TEST
# ============================================================

def print_section_title(title: str) -> None:
    """
    Print a clear section title for readable terminal output.
    """

    print("\n============================================================")
    print(title)
    print("============================================================\n")


def print_json_result(result: Dict[str, Any]) -> None:
    """
    Print a dictionary in readable JSON format.
    """

    print(json.dumps(result, indent=2))


def build_segment_result_from_checkpoint(
    checkpoint_number: int,
    checkpoint: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fetch live weather and score one routed checkpoint.
    """

    latitude = checkpoint["latitude"]
    longitude = checkpoint["longitude"]

    weather = fetch_weather_for_coordinate(
        latitude=latitude,
        longitude=longitude,
    )

    risk_result = score_segment(
        weather=weather,
        road_condition="normal",
        is_night=False,
    )

    return {
        "task_id": checkpoint_number,
        "workload": "route_segment_risk",
        "weather_mode": "live",
        "segment_label": checkpoint.get(
            "label",
            f"Route checkpoint {checkpoint_number}",
        ),
        "latitude": latitude,
        "longitude": longitude,
        "weather": weather,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
        "factors": risk_result["factors"],
    }


def run_routed_live_weather_test() -> None:
    """
    Run a complete local route-risk flow using routing + live weather.
    """

    print_section_title("ROUTED LIVE WEATHER ROUTE RISK TEST")

    # Approximate Rexburg, Idaho.
    origin_latitude = 43.8231
    origin_longitude = -111.7924

    # Approximate Idaho Falls, Idaho.
    destination_latitude = 43.4927
    destination_longitude = -112.0408

    print("Fetching route from OSRM...")

    route = fetch_route_between_coordinates(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        checkpoint_count=8,
    )

    route_summary = {
        "source": route["source"],
        "profile": route["profile"],
        "distance_meters": route["distance_meters"],
        "duration_seconds": route["duration_seconds"],
        "geometry_point_count": route["geometry_point_count"],
        "checkpoint_count": route["checkpoint_count"],
        "checkpoints": route["checkpoints"],
    }

    print_section_title("ROUTE SUMMARY")
    print_json_result(route_summary)

    print_section_title("FETCHING LIVE WEATHER AND SCORING CHECKPOINTS")

    segment_results: List[Dict[str, Any]] = []

    for checkpoint_number, checkpoint in enumerate(route["checkpoints"], start=1):
        print(
            f"Scoring checkpoint {checkpoint_number}/{route['checkpoint_count']}: "
            f"{checkpoint['latitude']}, {checkpoint['longitude']}"
        )

        segment_result = build_segment_result_from_checkpoint(
            checkpoint_number=checkpoint_number,
            checkpoint=checkpoint,
        )

        segment_results.append(segment_result)

    print_section_title("CHECKPOINT RISK RESULTS")
    print(json.dumps(segment_results, indent=2))

    print_section_title("AGGREGATED ROUTE RISK RESULT")

    aggregate_result = aggregate_segment_results(segment_results)

    final_result = {
        "route_source": route["source"],
        "distance_meters": route["distance_meters"],
        "duration_seconds": route["duration_seconds"],
        "checkpoint_count": route["checkpoint_count"],
        "aggregated_route_risk": aggregate_result,
    }

    print_json_result(final_result)

    print_section_title("END ROUTED LIVE WEATHER ROUTE RISK TEST")


# ============================================================
# LOCAL MANUAL TESTING ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_routed_live_weather_test()