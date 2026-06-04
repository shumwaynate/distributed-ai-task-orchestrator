"""
route_risk/core/scoring.py

Core route-risk scoring logic for the Route Risk Engine.

Purpose:
- Keep the original distributed orchestrator infrastructure intact.
- Provide pure, testable scoring functions for route-risk analysis.
- Score route segments using weather, road condition, visibility, wind,
  temperature, and time-of-day risk.

This file does NOT depend on:
- FastAPI
- Redis
- Celery
- Docker
- External APIs

That is intentional. External integrations should normalize data first, then
pass simple weather dictionaries into these core scoring functions.
"""

import json
from typing import Any, Dict, List, Optional


# ============================================================
# ROUTE RISK ENGINE LOGIC
# ============================================================

def classify_risk(score: int) -> str:
    """
    Convert a numeric risk score into a human-readable risk level.

    Risk levels:
    - 0-34: Low
    - 35-69: Moderate
    - 70-100: High
    """

    if score >= 70:
        return "High"

    if score >= 35:
        return "Moderate"

    return "Low"


def score_segment(
    weather: Dict[str, Any],
    road_condition: Optional[str] = None,
    is_night: bool = False,
) -> Dict[str, Any]:
    """
    Score one route segment based on weather, road condition, and time-of-day risk.

    This function is intentionally pure:
    - It receives input data.
    - It calculates a score.
    - It returns a result.
    - It does not call APIs.
    - It does not modify outside state.

    Parameters:
        weather:
            Dictionary containing weather details.

            Expected keys:
            - temperature_f: int or float
            - wind_mph: int or float
            - condition: str
            - visibility_miles: int or float, optional

        road_condition:
            Optional road condition label.

            Example values:
            - "normal"
            - "construction"
            - "icy"
            - "closed"

        is_night:
            Boolean indicating whether the segment is being driven at night.

    Returns:
        Dictionary with:
        - risk_score
        - risk_level
        - factors
    """

    score = 0
    factors: List[str] = []

    temperature_f = weather.get("temperature_f")
    wind_mph = weather.get("wind_mph")
    condition = str(weather.get("condition", "")).lower()
    visibility_miles = weather.get("visibility_miles")

    # ------------------------------------------------------------
    # Temperature-based risk factors
    # ------------------------------------------------------------

    is_freezing = temperature_f is not None and temperature_f <= 32

    if is_freezing:
        score += 25
        factors.append("freezing temperature")

    if temperature_f is not None and temperature_f <= 15:
        score += 15
        factors.append("extreme cold")

    # ------------------------------------------------------------
    # Precipitation and condition-based risk factors
    # ------------------------------------------------------------

    if "thunderstorm" in condition:
        score += 45
        factors.append("thunderstorm")

    if "severe thunderstorm" in condition:
        score += 60
        factors.append("severe thunderstorm")

    if "hail" in condition:
        score += 45
        factors.append("hail")

    if "snow" in condition:
        score += 35
        factors.append("snow")

    if "ice" in condition or "icy" in condition:
        score += 40
        factors.append("icy conditions")

    if "freezing rain" in condition:
        score += 55
        factors.append("freezing rain")

    if "freezing drizzle" in condition:
        score += 45
        factors.append("freezing drizzle")

    if "rain" in condition and "freezing rain" not in condition:
        score += 15
        factors.append("rain")

    if "drizzle" in condition and "freezing drizzle" not in condition:
        score += 10
        factors.append("drizzle")

    if "fog" in condition:
        score += 25
        factors.append("fog")

    if "snow" in condition and "rain" in condition:
        score += 15
        factors.append("mixed rain and snow")

    # ------------------------------------------------------------
    # Wind-based risk factors
    # ------------------------------------------------------------

    if wind_mph is not None and wind_mph >= 25:
        score += 15
        factors.append("high wind")

    if wind_mph is not None and wind_mph >= 40:
        score += 20
        factors.append("very high wind")

    if wind_mph is not None and wind_mph >= 55:
        score += 30
        factors.append("extreme wind")

    # ------------------------------------------------------------
    # Visibility-based risk factors
    # ------------------------------------------------------------

    if visibility_miles is not None and visibility_miles <= 2:
        score += 25
        factors.append("low visibility")

    if visibility_miles is not None and visibility_miles <= 0.5:
        score += 25
        factors.append("very low visibility")

    # ------------------------------------------------------------
    # Compound weather risk factors
    # ------------------------------------------------------------
    #
    # These are added when multiple risky conditions happen together.

    if is_freezing and ("rain" in condition or "drizzle" in condition):
        score += 25
        factors.append("freezing precipitation risk")

    if is_freezing and "fog" in condition:
        score += 15
        factors.append("freezing fog risk")

    if is_freezing and wind_mph is not None and wind_mph >= 25:
        score += 10
        factors.append("cold wind risk")

    if "snow" in condition and wind_mph is not None and wind_mph >= 25:
        score += 15
        factors.append("blowing snow risk")

    # ------------------------------------------------------------
    # Time-of-day risk factors
    # ------------------------------------------------------------

    if is_night:
        score += 10
        factors.append("nighttime travel")

    # ------------------------------------------------------------
    # Road-condition risk factors
    # ------------------------------------------------------------

    normalized_road_condition = str(road_condition or "normal").lower()

    if normalized_road_condition == "construction":
        score += 15
        factors.append("construction")

    if normalized_road_condition == "icy":
        score += 35
        factors.append("reported icy road")

    if normalized_road_condition == "wet":
        score += 10
        factors.append("reported wet road")

    if normalized_road_condition == "snowy":
        score += 25
        factors.append("reported snowy road")

    if normalized_road_condition == "closed":
        score += 100
        factors.append("road closure")

    # ------------------------------------------------------------
    # Final score normalization
    # ------------------------------------------------------------

    final_score = min(score, 100)

    return {
        "risk_score": final_score,
        "risk_level": classify_risk(final_score),
        "factors": factors,
    }


def score_route(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Score an entire route by combining multiple segment scores.

    Each segment should include:
    - label
    - weather
    - road_condition
    - is_night

    Returns:
        Dictionary with:
        - route_risk_score
        - route_risk_level
        - segment_results
        - summary
    """

    if not segments:
        return {
            "route_risk_score": 0,
            "route_risk_level": "Low",
            "segment_results": [],
            "summary": "No route segments were provided.",
        }

    segment_results = []

    for segment in segments:
        segment_score = score_segment(
            weather=segment.get("weather", {}),
            road_condition=segment.get("road_condition", "normal"),
            is_night=segment.get("is_night", False),
        )

        segment_results.append(
            {
                "label": segment.get("label", "Unnamed segment"),
                "risk_score": segment_score["risk_score"],
                "risk_level": segment_score["risk_level"],
                "factors": segment_score["factors"],
            }
        )

    total_score = sum(result["risk_score"] for result in segment_results)
    average_score = round(total_score / len(segment_results))

    summary = build_route_summary(segment_results, average_score)

    return {
        "route_risk_score": average_score,
        "route_risk_level": classify_risk(average_score),
        "segment_results": segment_results,
        "summary": summary,
    }


def build_route_summary(segment_results: List[Dict[str, Any]], route_score: int) -> str:
    """
    Build a simple human-readable explanation for the route score.
    """

    if not segment_results:
        return "No segment data was available to summarize."

    all_factors: List[str] = []

    for segment in segment_results:
        all_factors.extend(segment.get("factors", []))

    unique_factors = sorted(set(all_factors))

    if not unique_factors:
        return "This route currently appears low risk based on the available data."

    factor_text = ", ".join(unique_factors)

    return (
        f"This route has a risk score of {route_score}. "
        f"The main risk factors are: {factor_text}."
    )


# ============================================================
# LOCAL MANUAL TESTING
# ============================================================

def print_manual_test_result(result: Dict[str, Any]) -> None:
    """
    Print manual test output in a readable JSON-style format.
    """

    print("\n============================================================")
    print("ROUTE RISK SCORING MANUAL TEST")
    print("============================================================\n")

    print(json.dumps(result, indent=2))

    print("\n============================================================")
    print("END TEST")
    print("============================================================\n")


if __name__ == "__main__":
    sample_segments = [
        {
            "label": "Rexburg to Rigby",
            "weather": {
                "temperature_f": 28,
                "wind_mph": 18,
                "condition": "snow",
                "visibility_miles": 3,
            },
            "road_condition": "normal",
            "is_night": True,
        },
        {
            "label": "Rigby to Idaho Falls",
            "weather": {
                "temperature_f": 34,
                "wind_mph": 30,
                "condition": "cloudy",
                "visibility_miles": 5,
            },
            "road_condition": "construction",
            "is_night": True,
        },
        {
            "label": "Severe weather example",
            "weather": {
                "temperature_f": 29,
                "wind_mph": 42,
                "condition": "freezing rain",
                "visibility_miles": 0.4,
            },
            "road_condition": "icy",
            "is_night": True,
        },
    ]

    manual_test_result = score_route(sample_segments)

    print_manual_test_result(manual_test_result)