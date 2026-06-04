"""
route_risk/integrations/routing_client.py

Routing API integration for the Route Risk Engine.

Purpose:
- Fetch a route between an origin coordinate and destination coordinate.
- Normalize routing API data into a simple internal format.
- Sample route geometry into a smaller set of analysis checkpoints.
- Keep routing API logic separate from core scoring logic and weather logic.

Current provider:
- OSRM public route API

Why OSRM:
- Accepts longitude/latitude coordinate pairs.
- Can return route distance, duration, and GeoJSON geometry.
- Works well for a first routing prototype.

Normalized output shape:
    {
        "source": "osrm",
        "profile": "driving",
        "distance_meters": 37000.0,
        "duration_seconds": 1800.0,
        "geometry_coordinates": [
            {"latitude": 43.8231, "longitude": -111.7924},
            ...
        ],
        "checkpoints": [
            {
                "label": "Route checkpoint 1",
                "latitude": 43.8231,
                "longitude": -111.7924
            },
            ...
        ]
    }

Notes:
- This file does not change FastAPI or Celery yet.
- First, we prove route generation and checkpoint sampling works by itself.
"""

import json
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


# ============================================================
# ROUTE RISK ENGINE ROUTING INTEGRATION
# ============================================================

OSRM_BASE_URL = "https://router.project-osrm.org"
OSRM_ROUTE_PATH = "/route/v1"


def fetch_route_between_coordinates(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    profile: str = "driving",
    checkpoint_count: int = 8,
    timeout_seconds: int = 15,
) -> Dict[str, Any]:
    """
    Fetch and normalize a route between two coordinates.

    Parameters:
        origin_latitude:
            Origin WGS84 latitude.

        origin_longitude:
            Origin WGS84 longitude.

        destination_latitude:
            Destination WGS84 latitude.

        destination_longitude:
            Destination WGS84 longitude.

        profile:
            OSRM routing profile. Public OSRM commonly supports "driving".

        checkpoint_count:
            Number of sampled route checkpoints to produce.

        timeout_seconds:
            Request timeout for the API call.

    Returns:
        Normalized route dictionary.

    Raises:
        ValueError:
            If coordinates or checkpoint_count are invalid.

        RuntimeError:
            If OSRM request fails or returns unusable data.
    """

    validate_coordinate(origin_latitude, origin_longitude, "origin")
    validate_coordinate(destination_latitude, destination_longitude, "destination")

    if checkpoint_count < 2:
        raise ValueError("checkpoint_count must be at least 2.")

    api_response = _fetch_osrm_route_response(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        profile=profile,
        timeout_seconds=timeout_seconds,
    )

    return normalize_osrm_route_response(
        api_response=api_response,
        profile=profile,
        checkpoint_count=checkpoint_count,
    )


def validate_coordinate(latitude: float, longitude: float, label: str = "coordinate") -> None:
    """
    Validate latitude and longitude values before calling the routing API.
    """

    if latitude < -90 or latitude > 90:
        raise ValueError(
            f"{label} latitude must be between -90 and 90. Received: {latitude}"
        )

    if longitude < -180 or longitude > 180:
        raise ValueError(
            f"{label} longitude must be between -180 and 180. Received: {longitude}"
        )


def _fetch_osrm_route_response(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    profile: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    """
    Call OSRM's route API and return parsed JSON.

    OSRM expects coordinates in longitude,latitude order.
    """

    coordinate_text = (
        f"{origin_longitude},{origin_latitude};"
        f"{destination_longitude},{destination_latitude}"
    )

    query_parameters = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    }

    url = (
        f"{OSRM_BASE_URL}{OSRM_ROUTE_PATH}/{profile}/"
        f"{coordinate_text}?{urlencode(query_parameters)}"
    )

    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except HTTPError as error:
        raise RuntimeError(
            f"OSRM route request failed with HTTP status {error.code}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"OSRM route request failed because the URL could not be reached: {error}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError("OSRM returned invalid JSON.") from error


def normalize_osrm_route_response(
    api_response: Dict[str, Any],
    profile: str,
    checkpoint_count: int,
) -> Dict[str, Any]:
    """
    Convert OSRM response JSON into a route format used by the Route Risk Engine.
    """

    if api_response.get("code") != "Ok":
        raise RuntimeError(
            f"OSRM did not return a successful route. Response code: {api_response.get('code')}"
        )

    routes = api_response.get("routes")

    if not isinstance(routes, list) or not routes:
        raise RuntimeError("OSRM response did not include any routes.")

    first_route = routes[0]

    distance_meters = first_route.get("distance")
    duration_seconds = first_route.get("duration")

    geometry = first_route.get("geometry")

    if not isinstance(geometry, dict):
        raise RuntimeError("OSRM response route did not include usable geometry.")

    raw_coordinates = geometry.get("coordinates")

    if not isinstance(raw_coordinates, list) or not raw_coordinates:
        raise RuntimeError("OSRM response geometry did not include coordinates.")

    geometry_coordinates = [
        {
            "latitude": coordinate_pair[1],
            "longitude": coordinate_pair[0],
        }
        for coordinate_pair in raw_coordinates
        if (
            isinstance(coordinate_pair, list)
            and len(coordinate_pair) >= 2
        )
    ]

    if not geometry_coordinates:
        raise RuntimeError("OSRM geometry coordinates could not be normalized.")

    checkpoints = sample_route_checkpoints(
        coordinates=geometry_coordinates,
        checkpoint_count=checkpoint_count,
    )

    return {
        "source": "osrm",
        "profile": profile,
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "geometry_point_count": len(geometry_coordinates),
        "geometry_coordinates": geometry_coordinates,
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoints,
    }


def sample_route_checkpoints(
    coordinates: List[Dict[str, float]],
    checkpoint_count: int,
) -> List[Dict[str, float]]:
    """
    Sample route geometry into a smaller number of checkpoints.

    This keeps the route-risk engine from calling weather/road APIs for every
    geometry point returned by the routing API.

    Current simple strategy:
    - Always include the first point.
    - Always include the last point.
    - Evenly sample points between them by index.

    Future improvement:
    - Sample by distance along route instead of raw geometry index.
    """

    if not coordinates:
        return []

    if checkpoint_count >= len(coordinates):
        return [
            {
                "label": f"Route checkpoint {index}",
                "latitude": coordinate["latitude"],
                "longitude": coordinate["longitude"],
            }
            for index, coordinate in enumerate(coordinates, start=1)
        ]

    last_index = len(coordinates) - 1

    selected_indexes = []

    for sample_number in range(checkpoint_count):
        ratio = sample_number / (checkpoint_count - 1)
        selected_index = round(ratio * last_index)

        if selected_index not in selected_indexes:
            selected_indexes.append(selected_index)

    checkpoints = []

    for checkpoint_number, coordinate_index in enumerate(selected_indexes, start=1):
        coordinate = coordinates[coordinate_index]

        checkpoints.append(
            {
                "label": f"Route checkpoint {checkpoint_number}",
                "latitude": coordinate["latitude"],
                "longitude": coordinate["longitude"],
            }
        )

    return checkpoints


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
    print_section_title("OSRM ROUTING CLIENT MANUAL TEST")

    # Approximate Rexburg, Idaho.
    origin_latitude = 43.8231
    origin_longitude = -111.7924

    # Approximate Idaho Falls, Idaho.
    destination_latitude = 43.4927
    destination_longitude = -112.0408

    print(
        "Fetching route from "
        f"({origin_latitude}, {origin_longitude}) to "
        f"({destination_latitude}, {destination_longitude})"
    )

    route = fetch_route_between_coordinates(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        checkpoint_count=8,
    )

    # Print a compact summary first.
    route_summary = {
        "source": route["source"],
        "profile": route["profile"],
        "distance_meters": route["distance_meters"],
        "duration_seconds": route["duration_seconds"],
        "geometry_point_count": route["geometry_point_count"],
        "checkpoint_count": route["checkpoint_count"],
        "checkpoints": route["checkpoints"],
    }

    print(json.dumps(route_summary, indent=2))

    print_section_title("END OSRM ROUTING CLIENT MANUAL TEST")