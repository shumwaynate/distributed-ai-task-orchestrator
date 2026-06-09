"""
route_risk/integrations/ors_client.py

HeiGIT / OpenRouteService integration for alternative route candidates.

Purpose:
- Request multiple route alternatives from HeiGIT OpenRouteService.
- Normalize ORS GeoJSON route features into the same route shape used by OSRM.
- Reuse the existing checkpoint sampling helper from routing_client.py.

Important:
- Requires ORS_API_KEY environment variable.
- Do not hardcode your API key in this file.
"""

import json
import os
from typing import Any, Dict, List

import requests

from route_risk.integrations.routing_client import sample_route_checkpoints


ORS_DIRECTIONS_URL = (
    "https://api.heigit.org/openrouteservice/v2/directions/"
    "driving-car/geojson"
)


def fetch_ors_alternative_routes(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    checkpoint_count: int = 8,
    target_route_count: int = 3,
    share_factor: float = 0.6,
    weight_factor: float = 2.0,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Fetch alternative route candidates from HeiGIT OpenRouteService.

    ORS expects coordinates in longitude, latitude order.

    Returns:
        {
            "source": "ors",
            "provider": "heigit-openrouteservice",
            "candidate_count": 3,
            "routes": [...]
        }
    """

    api_key = os.getenv("ORS_API_KEY")

    if not api_key:
        raise RuntimeError("Missing ORS_API_KEY environment variable.")

    payload = {
        "coordinates": [
            [origin_longitude, origin_latitude],
            [destination_longitude, destination_latitude],
        ],
        "alternative_routes": {
            "target_count": target_route_count,
            "share_factor": share_factor,
            "weight_factor": weight_factor,
        },
        "instructions": False,
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }

    response = requests.post(
        ORS_DIRECTIONS_URL,
        json=payload,
        headers=headers,
        timeout=timeout_seconds,
    )

    response.raise_for_status()
    api_response = response.json()

    return normalize_ors_alternative_routes_response(
        api_response=api_response,
        checkpoint_count=checkpoint_count,
    )


def normalize_ors_alternative_routes_response(
    api_response: Dict[str, Any],
    checkpoint_count: int,
) -> Dict[str, Any]:
    """
    Normalize an ORS GeoJSON response containing route features.
    """

    features = api_response.get("features")

    if not isinstance(features, list) or not features:
        raise RuntimeError("ORS response did not include any route features.")

    normalized_routes = []

    for index, feature in enumerate(features, start=1):
        normalized_route = normalize_ors_route_feature(
            feature=feature,
            route_number=index,
            checkpoint_count=checkpoint_count,
        )
        normalized_routes.append(normalized_route)

    return {
        "source": "ors",
        "provider": "heigit-openrouteservice",
        "candidate_count": len(normalized_routes),
        "routes": normalized_routes,
    }


def normalize_ors_route_feature(
    feature: Dict[str, Any],
    route_number: int,
    checkpoint_count: int,
) -> Dict[str, Any]:
    """
    Normalize one ORS GeoJSON route feature into the internal route format.
    """

    properties = feature.get("properties", {})
    summary = properties.get("summary", {})

    distance_meters = summary.get("distance")
    duration_seconds = summary.get("duration")

    geometry = feature.get("geometry", {})

    if not isinstance(geometry, dict):
        raise RuntimeError(f"ORS route {route_number} did not include usable geometry.")

    raw_coordinates = geometry.get("coordinates")

    if not isinstance(raw_coordinates, list) or not raw_coordinates:
        raise RuntimeError(
            f"ORS route {route_number} geometry did not include coordinates."
        )

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
        raise RuntimeError(
            f"ORS route {route_number} geometry coordinates could not be normalized."
        )

    checkpoints = sample_route_checkpoints(
        coordinates=geometry_coordinates,
        checkpoint_count=checkpoint_count,
    )

    return {
        "source": "ors",
        "provider": "heigit-openrouteservice",
        "route_id": f"ors-route-{route_number}",
        "route_label": f"ORS Alternative Route {route_number}",
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "geometry_point_count": len(geometry_coordinates),
        "geometry_coordinates": geometry_coordinates,
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoints,
    }


def print_section_title(title: str) -> None:
    """
    Print a clear section title for readable terminal output.
    """

    print("\n============================================================")
    print(title)
    print("============================================================\n")


if __name__ == "__main__":
    print_section_title("ORS / HEIGIT NORMALIZED ALTERNATIVE ROUTES TEST")

    # Approximate Rexburg, Idaho.
    origin_latitude = 43.8231
    origin_longitude = -111.7924

    # Approximate Idaho Falls, Idaho.
    destination_latitude = 43.4927
    destination_longitude = -112.0408

    result = fetch_ors_alternative_routes(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        destination_latitude=destination_latitude,
        destination_longitude=destination_longitude,
        checkpoint_count=8,
        target_route_count=3,
    )

    print(f"ORS returned {result['candidate_count']} normalized route(s).")

    compact_routes = []

    for route in result["routes"]:
        compact_routes.append(
            {
                "route_id": route["route_id"],
                "route_label": route["route_label"],
                "source": route["source"],
                "provider": route["provider"],
                "distance_meters": route["distance_meters"],
                "duration_seconds": route["duration_seconds"],
                "geometry_point_count": route["geometry_point_count"],
                "checkpoint_count": route["checkpoint_count"],
                "checkpoints": route["checkpoints"],
            }
        )

    print(json.dumps(compact_routes, indent=2))

    print_section_title("END ORS / HEIGIT NORMALIZED ALTERNATIVE ROUTES TEST")