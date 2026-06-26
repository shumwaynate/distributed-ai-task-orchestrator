"""
Focused validation for geometry-aware closure matching.

Run:
    python -m route_risk.testing.manual_geometry_aware_closure_test
"""

from route_risk.integrations.road_conditions_client import (
    filter_road_events_for_route,
    find_nearby_road_events,
)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )

    print(f"PASS: {label} -> {actual!r}")


def main() -> None:
    print("\nGeometry-aware closure validation")
    print("=" * 52)

    route_geometry = [
        {"latitude": 36.0000, "longitude": -115.0000},
        {"latitude": 36.0100, "longitude": -115.0000},
        {"latitude": 36.0200, "longitude": -115.0000},
    ]

    overlapping_full_closure = {
        "event_id": "overlap",
        "event_type": "road closure",
        "is_full_closure": True,
        "is_blocking_closure": True,
        "closure_scope": "full",
        "latitude": 36.0100,
        "longitude": -115.0002,
        "latitude_secondary": 36.0150,
        "longitude_secondary": -115.0002,
        "roadway_name": "Route Road",
        "direction_of_travel": "North",
        "detour_instructions": "Use Route B.",
        "source": "test",
    }

    parallel_full_closure = {
        "event_id": "parallel",
        "event_type": "road closure",
        "is_full_closure": True,
        "is_blocking_closure": True,
        "closure_scope": "full",
        "latitude": 36.0100,
        "longitude": -114.9900,
        "latitude_secondary": 36.0150,
        "longitude_secondary": -114.9900,
        "roadway_name": "Parallel Road",
        "source": "test",
    }

    nearby_construction = {
        "event_id": "construction",
        "event_type": "construction",
        "is_full_closure": False,
        "is_blocking_closure": False,
        "closure_scope": "partial_lane",
        "latitude": 36.0100,
        "longitude": -114.9930,
        "roadway_name": "Nearby Work",
        "source": "test",
    }

    matched = filter_road_events_for_route(
        route_geometry=route_geometry,
        road_events=[
            overlapping_full_closure,
            parallel_full_closure,
            nearby_construction,
        ],
        radius_miles=1.0,
    )

    matched_ids = {
        event["event_id"]
        for event in matched
    }

    assert_equal(
        "overlap" in matched_ids,
        True,
        "overlapping full closure is kept",
    )
    assert_equal(
        "parallel" in matched_ids,
        False,
        "parallel full closure is rejected",
    )
    assert_equal(
        "construction" in matched_ids,
        True,
        "nearby construction uses selected radius",
    )

    checkpoint_matches = find_nearby_road_events(
        checkpoint={
            "label": "Checkpoint",
            "latitude": 36.0100,
            "longitude": -115.0000,
        },
        road_events=[
            event
            for event in matched
            if event["event_id"] == "overlap"
        ],
        radius_miles=1.0,
    )

    assert_equal(
        len(checkpoint_matches),
        1,
        "overlapping closure reaches checkpoint matching",
    )
    assert_equal(
        checkpoint_matches[0]["detour_instructions"],
        "Use Route B.",
        "detour instructions are preserved",
    )
    assert_equal(
        checkpoint_matches[0]["route_match_method"],
        "event_geometry",
        "route match method is preserved",
    )

    print("\nAll geometry-aware closure checks passed.")


if __name__ == "__main__":
    main()