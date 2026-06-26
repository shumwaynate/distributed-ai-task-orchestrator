"""
route_risk/integrations/road_conditions_client.py

Road condition and work-zone matching utilities for the Route Risk Engine.

Purpose:
- Match road events such as construction, closures, restrictions, or advisories
  to route checkpoints.
- Normalize external road-event data into simple road_condition values that the
  core scoring engine already understands.
- Prepare the project for future WZDx / 511 / DOT feed integrations.

Current stage:
- Uses provided event dictionaries.
- Does not call a live API yet.
- Proves that route checkpoints can be compared against road events.

Future stage:
- Fetch real work-zone data from WZDx or 511 feeds.
- Normalize those feed events into the event format used here.
"""

import json
import math
from typing import Any, Dict, List, Optional


# ============================================================
# DISTANCE HELPERS
# ============================================================

def haversine_distance_miles(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """
    Calculate the approximate distance in miles between two latitude/longitude points.

    This is good enough for matching route checkpoints to nearby road events.
    """

    earth_radius_miles = 3958.8

    lat_1_rad = math.radians(latitude_1)
    lon_1_rad = math.radians(longitude_1)
    lat_2_rad = math.radians(latitude_2)
    lon_2_rad = math.radians(longitude_2)

    delta_lat = lat_2_rad - lat_1_rad
    delta_lon = lon_2_rad - lon_1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_1_rad)
        * math.cos(lat_2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_miles * c


# ============================================================
# ROAD EVENT NORMALIZATION
# ============================================================

def normalize_event_type_to_road_condition(event_type: str) -> str:
    """
    Convert event type text into a scoring-friendly road_condition value.

    Scoring currently understands:
    - normal
    - construction
    - wet
    - snowy
    - icy
    - closed
    """

    normalized = str(event_type or "").lower()

    if "closed" in normalized or "closure" in normalized:
        return "closed"

    if "work zone" in normalized:
        return "construction"

    if "construction" in normalized:
        return "construction"

    if "maintenance" in normalized:
        return "construction"

    if "restriction" in normalized:
        return "construction"

    if "icy" in normalized or "ice" in normalized:
        return "icy"

    if "snow" in normalized:
        return "snowy"

    if "wet" in normalized or "water" in normalized:
        return "wet"

    return "normal"

def normalize_road_event_to_road_condition(
    event: Dict[str, Any],
) -> str:
    """
    Convert one normalized road-event dictionary into a scoring condition.

    Explicit closure metadata takes priority:

    - is_blocking_closure == True -> closed
    - is_full_closure == True -> closed
    - either explicit flag == False -> construction instead of closed

    Events without either flag retain the legacy event-type behavior. This
    keeps manually supplied ``road closure`` test events blocking.
    """

    normalized_condition = (
        normalize_event_type_to_road_condition(
            str(event.get("event_type", "normal"))
        )
    )

    blocking_flag_present = (
        "is_blocking_closure" in event
    )

    full_closure_flag_present = (
        "is_full_closure" in event
    )

    if blocking_flag_present:
        return (
            "closed"
            if bool(event.get("is_blocking_closure"))
            else (
                "construction"
                if normalized_condition == "closed"
                else normalized_condition
            )
        )

    if full_closure_flag_present:
        return (
            "closed"
            if bool(event.get("is_full_closure"))
            else (
                "construction"
                if normalized_condition == "closed"
                else normalized_condition
            )
        )

    return normalized_condition

def decode_google_polyline(
    encoded_polyline: str,
) -> List[Dict[str, float]]:
    """Decode a standard Google encoded polyline."""

    text = str(encoded_polyline or "").strip()

    if not text:
        return []

    coordinates: List[Dict[str, float]] = []
    index = 0
    latitude_value = 0
    longitude_value = 0

    try:
        while index < len(text):
            latitude_change = 0
            shift = 0

            while True:
                value = ord(text[index]) - 63
                index += 1
                latitude_change |= (
                    value & 0x1F
                ) << shift
                shift += 5

                if value < 0x20:
                    break

            latitude_delta = (
                ~(latitude_change >> 1)
                if latitude_change & 1
                else latitude_change >> 1
            )
            latitude_value += latitude_delta

            longitude_change = 0
            shift = 0

            while True:
                value = ord(text[index]) - 63
                index += 1
                longitude_change |= (
                    value & 0x1F
                ) << shift
                shift += 5

                if value < 0x20:
                    break

            longitude_delta = (
                ~(longitude_change >> 1)
                if longitude_change & 1
                else longitude_change >> 1
            )
            longitude_value += longitude_delta

            coordinates.append(
                {
                    "latitude": latitude_value / 100000.0,
                    "longitude": longitude_value / 100000.0,
                }
            )

    except (IndexError, ValueError, TypeError):
        return []

    return coordinates


def _normalize_geometry_points(
    geometry: Any,
) -> List[Dict[str, float]]:
    """Normalize dictionaries or coordinate pairs into route points."""

    normalized_points: List[Dict[str, float]] = []

    if not isinstance(geometry, list):
        return normalized_points

    for point in geometry:
        latitude = None
        longitude = None

        if isinstance(point, dict):
            latitude = point.get("latitude")
            longitude = point.get("longitude")

        elif (
            isinstance(point, (list, tuple))
            and len(point) >= 2
        ):
            longitude = point[0]
            latitude = point[1]

        if latitude is None or longitude is None:
            continue

        try:
            normalized_points.append(
                {
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                }
            )
        except (TypeError, ValueError):
            continue

    return normalized_points


def event_geometry_points(
    event: Dict[str, Any],
) -> List[Dict[str, float]]:
    """Build the best available geometry for one road event."""

    points = decode_google_polyline(
        str(event.get("encoded_polyline") or "")
    )

    for latitude, longitude in (
        (
            event.get("latitude"),
            event.get("longitude"),
        ),
        (
            event.get("latitude_secondary"),
            event.get("longitude_secondary"),
        ),
    ):
        if latitude is None or longitude is None:
            continue

        try:
            coordinate = {
                "latitude": float(latitude),
                "longitude": float(longitude),
            }
        except (TypeError, ValueError):
            continue

        if coordinate not in points:
            points.append(coordinate)

    return points


def _minimum_distance_between_geometries_miles(
    first_geometry: List[Dict[str, float]],
    second_geometry: List[Dict[str, float]],
) -> Optional[float]:
    """Return the smallest point-to-point geometry distance."""

    if not first_geometry or not second_geometry:
        return None

    def bounded_sample(
        points: List[Dict[str, float]],
        maximum_points: int = 800,
    ) -> List[Dict[str, float]]:
        if len(points) <= maximum_points:
            return points

        step = max(
            1,
            len(points) // maximum_points,
        )

        sampled = points[::step]

        if sampled[-1] != points[-1]:
            sampled.append(points[-1])

        return sampled

    first_points = bounded_sample(first_geometry)
    second_points = bounded_sample(second_geometry)

    minimum_distance: Optional[float] = None

    for first_point in first_points:
        for second_point in second_points:
            distance = haversine_distance_miles(
                latitude_1=first_point["latitude"],
                longitude_1=first_point["longitude"],
                latitude_2=second_point["latitude"],
                longitude_2=second_point["longitude"],
            )

            if (
                minimum_distance is None
                or distance < minimum_distance
            ):
                minimum_distance = distance

                if minimum_distance <= 0.01:
                    return minimum_distance

    return minimum_distance


def _blocking_event_route_threshold_miles(
    event: Dict[str, Any],
    requested_radius_miles: float,
) -> float:
    """
    Use a tighter tolerance for route-blocking closures than construction.
    """

    has_path_geometry = bool(
        str(event.get("encoded_polyline") or "").strip()
    ) or (
        event.get("latitude_secondary") is not None
        and event.get("longitude_secondary") is not None
    )

    maximum_threshold = (
        0.20
        if has_path_geometry
        else 0.12
    )

    return min(
        float(requested_radius_miles),
        maximum_threshold,
    )


def filter_road_events_for_route(
    route_geometry: List[Dict[str, Any]],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Keep road events that plausibly affect the actual selected route.
    """

    normalized_route_geometry = (
        _normalize_geometry_points(
            route_geometry
        )
    )

    if not normalized_route_geometry:
        return list(road_events)

    matched_events: List[Dict[str, Any]] = []

    for event in road_events:
        event_points = event_geometry_points(
            event
        )

        if not event_points:
            continue

        minimum_distance = (
            _minimum_distance_between_geometries_miles(
                normalized_route_geometry,
                event_points,
            )
        )

        if minimum_distance is None:
            continue

        road_condition = (
            normalize_road_event_to_road_condition(
                event
            )
        )

        if road_condition == "closed":
            threshold = (
                _blocking_event_route_threshold_miles(
                    event,
                    radius_miles,
                )
            )
        else:
            threshold = float(radius_miles)

        if minimum_distance > threshold:
            continue

        matched_event = dict(event)
        matched_event["route_match_distance_miles"] = round(
            minimum_distance,
            3,
        )
        matched_event["route_match_threshold_miles"] = round(
            threshold,
            3,
        )
        matched_event["route_match_method"] = (
            "event_geometry"
            if len(event_points) > 1
            else "event_point"
        )

        matched_events.append(
            matched_event
        )

    return matched_events


def distance_from_checkpoint_to_event_miles(
    checkpoint: Dict[str, Any],
    event: Dict[str, Any],
) -> Optional[float]:
    """Measure a checkpoint against the event geometry."""

    event_points = event_geometry_points(
        event
    )

    if not event_points:
        return None

    checkpoint_geometry = [
        {
            "latitude": float(
                checkpoint["latitude"]
            ),
            "longitude": float(
                checkpoint["longitude"]
            ),
        }
    ]

    return _minimum_distance_between_geometries_miles(
        checkpoint_geometry,
        event_points,
    )




def road_condition_priority(road_condition: str) -> int:
    """
    Rank road conditions so the most serious nearby condition wins.
    """

    priorities = {
        "normal": 0,
        "wet": 1,
        "construction": 2,
        "snowy": 3,
        "icy": 4,
        "closed": 5,
    }

    return priorities.get(road_condition, 0)


# ============================================================
# ROAD EVENT MATCHING
# ============================================================

def find_nearby_road_events(
    checkpoint: Dict[str, Any],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Find road events near one checkpoint using event geometry when available.
    """

    nearby_events = []

    retained_fields = (
        "event_id",
        "event_type",
        "description",
        "latitude",
        "longitude",
        "source",
        "source_event_id",
        "roadway_name",
        "direction_of_travel",
        "event_subtype",
        "is_full_closure",
        "is_blocking_closure",
        "closure_scope",
        "severity",
        "lanes_affected",
        "comment",
        "restrictions",
        "timing_status",
        "start_iso_utc",
        "planned_end_iso_utc",
        "latitude_secondary",
        "longitude_secondary",
        "encoded_polyline",
        "detour_polyline",
        "detour_instructions",
        "route_match_distance_miles",
        "route_match_threshold_miles",
        "route_match_method",
    )

    for event in road_events:
        distance_miles = (
            distance_from_checkpoint_to_event_miles(
                checkpoint,
                event,
            )
        )

        if distance_miles is None:
            continue

        if distance_miles > radius_miles:
            continue

        normalized_condition = (
            normalize_road_event_to_road_condition(
                event
            )
        )

        matched_event = {
            field_name: event.get(field_name)
            for field_name in retained_fields
            if field_name in event
        }

        matched_event["distance_miles"] = round(
            distance_miles,
            3,
        )
        matched_event["road_condition"] = (
            normalized_condition
        )

        nearby_events.append(
            matched_event
        )

    nearby_events.sort(
        key=lambda event: (
            -road_condition_priority(
                event["road_condition"]
            ),
            event["distance_miles"],
        )
    )

    return nearby_events




def determine_checkpoint_road_condition(
    checkpoint: Dict[str, Any],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 2.0,
    fallback_road_condition: str = "normal",
) -> Dict[str, Any]:
    """
    Determine the road condition for one checkpoint based on nearby road events.
    """

    nearby_events = find_nearby_road_events(
        checkpoint=checkpoint,
        road_events=road_events,
        radius_miles=radius_miles,
    )

    if not nearby_events:
        return {
            "checkpoint_label": checkpoint.get("label"),
            "latitude": checkpoint.get("latitude"),
            "longitude": checkpoint.get("longitude"),
            "road_condition": fallback_road_condition,
            "matched_event": None,
            "nearby_event_count": 0,
            "source": "fallback",
        }

    highest_priority_event = nearby_events[0]

    return {
        "checkpoint_label": checkpoint.get("label"),
        "latitude": checkpoint.get("latitude"),
        "longitude": checkpoint.get("longitude"),
        "road_condition": highest_priority_event["road_condition"],
        "matched_event": highest_priority_event,
        "nearby_event_count": len(nearby_events),
        "source": highest_priority_event.get("source"),
    }


def determine_route_road_conditions(
    checkpoints: List[Dict[str, Any]],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 2.0,
    fallback_road_condition: str = "normal",
) -> List[Dict[str, Any]]:
    """
    Determine road condition for each route checkpoint.
    """

    results = []

    for checkpoint in checkpoints:
        result = determine_checkpoint_road_condition(
            checkpoint=checkpoint,
            road_events=road_events,
            radius_miles=radius_miles,
            fallback_road_condition=fallback_road_condition,
        )

        results.append(result)

    return results


def apply_road_conditions_to_checkpoints(
    checkpoints: List[Dict[str, Any]],
    road_events: List[Dict[str, Any]],
    radius_miles: float = 2.0,
    fallback_road_condition: str = "normal",
) -> List[Dict[str, Any]]:
    """
    Return checkpoint dictionaries with road_condition and road_event details added.

    This prepares route checkpoints to become route-risk segments.
    """

    road_condition_results = determine_route_road_conditions(
        checkpoints=checkpoints,
        road_events=road_events,
        radius_miles=radius_miles,
        fallback_road_condition=fallback_road_condition,
    )

    enriched_checkpoints = []

    for checkpoint, road_condition_result in zip(checkpoints, road_condition_results):
        enriched_checkpoint = {
            **checkpoint,
            "road_condition": road_condition_result["road_condition"],
            "road_condition_source": road_condition_result["source"],
            "matched_road_event": road_condition_result["matched_event"],
            "nearby_road_event_count": road_condition_result["nearby_event_count"],
        }

        enriched_checkpoints.append(enriched_checkpoint)

    return enriched_checkpoints


# ============================================================
# LOCAL MANUAL TESTING
# ============================================================

def print_section_title(title: str) -> None:
    """
    Print a clear section title for readable terminal output.
    """

    print("\n============================================================")
    print(title)
    print("============================================================\n")


if __name__ == "__main__":
    print_section_title("ROAD CONDITIONS CLIENT MANUAL TEST")

    sample_checkpoints = [
        {
            "label": "Route checkpoint 1",
            "latitude": 43.8231,
            "longitude": -111.792468,
        },
        {
            "label": "Route checkpoint 2",
            "latitude": 43.804545,
            "longitude": -111.811928,
        },
        {
            "label": "Route checkpoint 3",
            "latitude": 43.753344,
            "longitude": -111.850925,
        },
    ]

    sample_road_events = [
        {
            "event_id": "demo-construction-1",
            "event_type": "construction",
            "description": "Demo work zone near checkpoint 2.",
            "latitude": 43.8047,
            "longitude": -111.812,
            "source": "manual-demo-event",
        },
        {
            "event_id": "demo-closure-1",
            "event_type": "road closure",
            "description": "Demo closure near checkpoint 3.",
            "latitude": 43.7534,
            "longitude": -111.851,
            "source": "manual-demo-event",
        },
    ]

    enriched = apply_road_conditions_to_checkpoints(
        checkpoints=sample_checkpoints,
        road_events=sample_road_events,
        radius_miles=1.0,
        fallback_road_condition="normal",
    )

    print(json.dumps(enriched, indent=2))

    print_section_title("END ROAD CONDITIONS CLIENT MANUAL TEST")