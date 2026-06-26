"""Focused validation for near-duplicate route filtering."""

from route_risk.core.route_similarity import (
    filter_near_duplicate_routes,
    route_geometry_similarity,
)


def make_route(
    route_id: str,
    longitude_offset: float,
    distance_meters: float,
) -> dict:
    geometry = []

    for index in range(101):
        geometry.append(
            {
                "latitude": 36.0 + (index * 0.001),
                "longitude": -115.0 + longitude_offset,
            }
        )

    return {
        "route_id": route_id,
        "route_label": route_id,
        "distance_meters": distance_meters,
        "duration_seconds": 1800,
        "geometry_coordinates": geometry,
    }


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )

    print(f"PASS: {label} -> {actual!r}")


def main() -> None:
    print("\nNear-duplicate route filtering validation")
    print("=" * 56)

    route_1 = make_route(
        "route-1",
        longitude_offset=0.0,
        distance_meters=18000,
    )

    route_2_near_duplicate = make_route(
        "route-2",
        longitude_offset=0.0002,
        distance_meters=18100,
    )

    route_3_distinct = make_route(
        "route-3",
        longitude_offset=0.02,
        distance_meters=19000,
    )

    duplicate_similarity = route_geometry_similarity(
        route_1,
        route_2_near_duplicate,
    )

    distinct_similarity = route_geometry_similarity(
        route_1,
        route_3_distinct,
    )

    assert_equal(
        duplicate_similarity["similarity"] >= 0.94,
        True,
        "near-identical corridor exceeds threshold",
    )

    assert_equal(
        distinct_similarity["similarity"] < 0.94,
        True,
        "distinct corridor stays below threshold",
    )

    filtered = filter_near_duplicate_routes(
        [
            route_1,
            route_2_near_duplicate,
            route_3_distinct,
        ]
    )

    assert_equal(
        filtered["generated_count"],
        3,
        "three routes were generated",
    )

    assert_equal(
        filtered["unique_count"],
        2,
        "two unique routes remain",
    )

    assert_equal(
        filtered["duplicate_count"],
        1,
        "one near-duplicate was removed",
    )

    assert_equal(
        [
            route["route_id"]
            for route in filtered["routes"]
        ],
        ["route-1", "route-3"],
        "original route order is preserved",
    )

    print("\nAll route duplicate filtering checks passed.")


if __name__ == "__main__":
    main()
