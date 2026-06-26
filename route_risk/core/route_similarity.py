"""Geometry-based route similarity and duplicate filtering."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


EARTH_RADIUS_MILES = 3958.7613


def _haversine_distance_miles(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    latitude_1_radians = math.radians(latitude_1)
    longitude_1_radians = math.radians(longitude_1)
    latitude_2_radians = math.radians(latitude_2)
    longitude_2_radians = math.radians(longitude_2)

    latitude_difference = latitude_2_radians - latitude_1_radians
    longitude_difference = longitude_2_radians - longitude_1_radians

    haversine_value = (
        math.sin(latitude_difference / 2.0) ** 2
        + math.cos(latitude_1_radians)
        * math.cos(latitude_2_radians)
        * math.sin(longitude_difference / 2.0) ** 2
    )

    central_angle = 2.0 * math.atan2(
        math.sqrt(haversine_value),
        math.sqrt(1.0 - haversine_value),
    )

    return EARTH_RADIUS_MILES * central_angle


def normalize_route_geometry(
    geometry: Any,
) -> List[Tuple[float, float]]:
    if not isinstance(geometry, list):
        return []

    normalized: List[Tuple[float, float]] = []

    for point in geometry:
        latitude: Optional[float] = None
        longitude: Optional[float] = None

        if isinstance(point, dict):
            raw_latitude = point.get("latitude")
            raw_longitude = point.get("longitude")

            if raw_latitude is None or raw_longitude is None:
                continue

            try:
                latitude = float(raw_latitude)
                longitude = float(raw_longitude)
            except (TypeError, ValueError):
                continue

        elif (
            isinstance(point, (list, tuple))
            and len(point) >= 2
        ):
            try:
                longitude = float(point[0])
                latitude = float(point[1])
            except (TypeError, ValueError):
                continue

        if latitude is None or longitude is None:
            continue

        normalized.append((latitude, longitude))

    return normalized


def _evenly_sample_points(
    points: Sequence[Tuple[float, float]],
    maximum_points: int = 300,
) -> List[Tuple[float, float]]:
    if len(points) <= maximum_points:
        return list(points)

    if maximum_points <= 1:
        return [points[0]]

    last_index = len(points) - 1

    sampled_indexes = {
        round(index * last_index / (maximum_points - 1))
        for index in range(maximum_points)
    }

    return [
        points[index]
        for index in sorted(sampled_indexes)
    ]


def _directional_proximity_coverage(
    source_points: Sequence[Tuple[float, float]],
    comparison_points: Sequence[Tuple[float, float]],
    proximity_tolerance_miles: float,
) -> float:
    if not source_points or not comparison_points:
        return 0.0

    nearby_count = 0

    for source_latitude, source_longitude in source_points:
        is_near_comparison = any(
            _haversine_distance_miles(
                source_latitude,
                source_longitude,
                comparison_latitude,
                comparison_longitude,
            ) <= proximity_tolerance_miles
            for comparison_latitude, comparison_longitude
            in comparison_points
        )

        if is_near_comparison:
            nearby_count += 1

    return nearby_count / len(source_points)


def route_geometry_similarity(
    first_route: Dict[str, Any],
    second_route: Dict[str, Any],
    proximity_tolerance_miles: float = 0.10,
    maximum_sample_points: int = 300,
) -> Dict[str, float]:
    first_geometry = normalize_route_geometry(
        first_route.get("geometry_coordinates", [])
    )

    second_geometry = normalize_route_geometry(
        second_route.get("geometry_coordinates", [])
    )

    if len(first_geometry) < 2 or len(second_geometry) < 2:
        return {
            "similarity": 0.0,
            "first_coverage": 0.0,
            "second_coverage": 0.0,
            "distance_similarity": 0.0,
        }

    first_sample = _evenly_sample_points(
        first_geometry,
        maximum_points=maximum_sample_points,
    )

    second_sample = _evenly_sample_points(
        second_geometry,
        maximum_points=maximum_sample_points,
    )

    first_coverage = _directional_proximity_coverage(
        source_points=first_sample,
        comparison_points=second_sample,
        proximity_tolerance_miles=proximity_tolerance_miles,
    )

    second_coverage = _directional_proximity_coverage(
        source_points=second_sample,
        comparison_points=first_sample,
        proximity_tolerance_miles=proximity_tolerance_miles,
    )

    first_distance = float(
        first_route.get("distance_meters", 0.0) or 0.0
    )

    second_distance = float(
        second_route.get("distance_meters", 0.0) or 0.0
    )

    if first_distance > 0 and second_distance > 0:
        distance_similarity = (
            min(first_distance, second_distance)
            / max(first_distance, second_distance)
        )
    else:
        distance_similarity = 1.0

    geometry_overlap = min(
        first_coverage,
        second_coverage,
    )

    similarity = geometry_overlap * distance_similarity

    return {
        "similarity": round(similarity, 4),
        "first_coverage": round(first_coverage, 4),
        "second_coverage": round(second_coverage, 4),
        "distance_similarity": round(distance_similarity, 4),
    }


def filter_near_duplicate_routes(
    routes: List[Dict[str, Any]],
    similarity_threshold: float = 0.94,
    proximity_tolerance_miles: float = 0.10,
    maximum_sample_points: int = 300,
) -> Dict[str, Any]:
    if not routes:
        return {
            "routes": [],
            "duplicate_routes": [],
            "duplicate_count": 0,
            "generated_count": 0,
            "unique_count": 0,
            "similarity_threshold": similarity_threshold,
            "proximity_tolerance_miles": proximity_tolerance_miles,
        }

    unique_routes: List[Dict[str, Any]] = []
    duplicate_routes: List[Dict[str, Any]] = []

    for route in routes:
        duplicate_match = None

        for kept_route in unique_routes:
            similarity_details = route_geometry_similarity(
                route,
                kept_route,
                proximity_tolerance_miles=(
                    proximity_tolerance_miles
                ),
                maximum_sample_points=maximum_sample_points,
            )

            if (
                similarity_details["similarity"]
                >= similarity_threshold
            ):
                duplicate_match = {
                    "removed_route_id": route.get("route_id"),
                    "removed_route_label": route.get("route_label"),
                    "kept_route_id": kept_route.get("route_id"),
                    "kept_route_label": kept_route.get("route_label"),
                    **similarity_details,
                }
                break

        if duplicate_match is None:
            unique_routes.append(route)
        else:
            duplicate_routes.append(duplicate_match)

    return {
        "routes": unique_routes,
        "duplicate_routes": duplicate_routes,
        "duplicate_count": len(duplicate_routes),
        "generated_count": len(routes),
        "unique_count": len(unique_routes),
        "similarity_threshold": similarity_threshold,
        "proximity_tolerance_miles": proximity_tolerance_miles,
    }
