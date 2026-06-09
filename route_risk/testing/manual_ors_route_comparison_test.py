"""
route_risk/testing/manual_ors_route_comparison_test.py

Manual local test for comparing multiple ORS route candidates.

Run:
    python -m route_risk.testing.manual_ors_route_comparison_test
"""

from typing import Any, Dict, List

from route_risk.core.aggregation import aggregate_segment_results
from route_risk.core.scoring import score_segment
from route_risk.integrations.ors_client import fetch_ors_alternative_routes
from route_risk.integrations.road_conditions_client import (
    apply_road_conditions_to_checkpoints,
)
from route_risk.integrations.weather_client import fetch_weather_for_coordinate


def build_demo_road_events() -> List[Dict[str, Any]]:
    return [
        {
            "event_id": "demo-closure-route-1",
            "event_type": "road closure",
            "description": "Demo road closure placed near ORS Route 1.",
            "latitude": 43.531797,
            "longitude": -112.015832,
            "source": "manual-ors-comparison-test",
        },
        {
            "event_id": "demo-construction-route-area",
            "event_type": "construction",
            "description": "Demo construction near the Rexburg to Idaho Falls corridor.",
            "latitude": 43.583786,
            "longitude": -111.973613,
            "source": "manual-ors-comparison-test",
        },
    ]


def score_route_candidate(
    route: Dict[str, Any],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 1.0,
    fallback_road_condition: str = "normal",
    is_night: bool = False,
) -> Dict[str, Any]:
    enriched_checkpoints = apply_road_conditions_to_checkpoints(
        checkpoints=route["checkpoints"],
        road_events=road_events,
        radius_miles=radius_miles,
        fallback_road_condition=fallback_road_condition,
    )

    segment_results = []

    for index, checkpoint in enumerate(enriched_checkpoints, start=1):
        weather = fetch_weather_for_coordinate(
            latitude=checkpoint["latitude"],
            longitude=checkpoint["longitude"],
        )

        segment_score = score_segment(
            weather=weather,
            road_condition=checkpoint.get("road_condition", fallback_road_condition),
            is_night=is_night,
        )

        segment_results.append(
            {
                "task_id": f"{route['route_id']}-checkpoint-{index}",
                "workload": "route_segment_risk",
                "weather_mode": "live",
                "segment_label": checkpoint.get("label", f"Route checkpoint {index}"),
                "latitude": checkpoint["latitude"],
                "longitude": checkpoint["longitude"],
                "weather": weather,
                "road_condition": checkpoint.get(
                    "road_condition",
                    fallback_road_condition,
                ),
                "road_condition_source": checkpoint.get(
                    "road_condition_source",
                    "fallback",
                ),
                "matched_road_event": checkpoint.get("matched_road_event"),
                "nearby_road_event_count": checkpoint.get(
                    "nearby_road_event_count",
                    0,
                ),
                "risk_score": segment_score["risk_score"],
                "risk_level": segment_score["risk_level"],
                "factors": segment_score["factors"],
            }
        )

    aggregated = aggregate_segment_results(segment_results)

    return {
        "route_id": route["route_id"],
        "route_label": route["route_label"],
        "source": route["source"],
        "provider": route["provider"],
        "distance_meters": route["distance_meters"],
        "duration_seconds": route["duration_seconds"],
        "checkpoint_count": route["checkpoint_count"],
        "route_risk_score": aggregated["route_risk_score"],
        "route_risk_level": aggregated["route_risk_level"],
        "route_blocked": aggregated.get("route_blocked", False),
        "route_warning": aggregated.get("route_warning"),
        "average_segment_score": aggregated.get("average_segment_score"),
        "highest_risk_segment": aggregated.get("highest_risk_segment"),
        "blocking_segment_count": len(aggregated.get("blocking_segments", [])),
        "summary": aggregated["summary"],
        "aggregated_route_risk": aggregated,
    }


def choose_recommended_route(scored_routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable_routes = [
        route for route in scored_routes if not route.get("route_blocked", False)
    ]

    candidate_routes = usable_routes if usable_routes else scored_routes

    return sorted(
        candidate_routes,
        key=lambda route: (
            route.get("route_risk_score", 999),
            route.get("duration_seconds", 999999),
        ),
    )[0]


def print_section_title(title: str) -> None:
    print("\n============================================================")
    print(title)
    print("============================================================\n")


def main() -> None:
    print_section_title("ORS ROUTE COMPARISON TEST")

    route_candidates = fetch_ors_alternative_routes(
        origin_latitude=43.8231,
        origin_longitude=-111.7924,
        destination_latitude=43.4927,
        destination_longitude=-112.0408,
        checkpoint_count=8,
        target_route_count=3,
    )

    routes = route_candidates["routes"]
    road_events = build_demo_road_events()

    print(f"Fetched {len(routes)} route candidate(s).")
    print(f"Applying {len(road_events)} demo road event(s).")
    print("Scoring route candidates...")

    scored_routes = [
        score_route_candidate(
            route=route,
            road_events=road_events,
            radius_miles=1.0,
            fallback_road_condition="normal",
            is_night=False,
        )
        for route in routes
    ]

    recommended_route = choose_recommended_route(scored_routes)

    print_section_title("ROUTE COMPARISON RESULTS")

    for route in scored_routes:
        print(route["route_label"])
        print(f"  Route ID: {route['route_id']}")
        print(f"  Distance meters: {route['distance_meters']}")
        print(f"  Duration seconds: {route['duration_seconds']}")
        print(f"  Risk score: {route['route_risk_score']}")
        print(f"  Risk level: {route['route_risk_level']}")
        print(f"  Blocked: {route['route_blocked']}")
        print(f"  Blocking segments: {route['blocking_segment_count']}")

        highest = route.get("highest_risk_segment")

        if highest:
            print(f"  Highest-risk segment: {highest.get('segment_label')}")
            print(f"  Highest-risk road condition: {highest.get('road_condition')}")

        print()

    print_section_title("RECOMMENDED ROUTE")

    print(f"Recommended route: {recommended_route['route_label']}")
    print(f"Route ID: {recommended_route['route_id']}")
    print(f"Risk score: {recommended_route['route_risk_score']}")
    print(f"Risk level: {recommended_route['route_risk_level']}")
    print(f"Blocked: {recommended_route['route_blocked']}")
    print(f"Duration seconds: {recommended_route['duration_seconds']}")
    print()
    print("Summary:")
    print(recommended_route["summary"])

    print_section_title("END ORS ROUTE COMPARISON TEST")


if __name__ == "__main__":
    main()