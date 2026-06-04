"""
route_risk/testing/manual_live_weather_scoring_test.py

Manual test for connecting live weather data to the Route Risk Engine scoring logic.

Purpose:
- Fetch live weather for a coordinate using the weather integration client.
- Pass that normalized weather data into the existing route-risk scoring function.
- Print clean, readable output.
- Prove that external API data can feed the core scoring system before we connect
  live weather to Celery or FastAPI.

This test does NOT require:
- Redis
- Celery worker
- FastAPI
- Docker

It DOES require:
- Internet access
- Open-Meteo API availability
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


# ============================================================
# IMPORT PATH SETUP FOR LOCAL MANUAL TESTING
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from route_risk.core.scoring import score_segment
from route_risk.integrations.weather_client import fetch_weather_for_coordinate


# ============================================================
# ROUTE RISK LIVE WEATHER SCORING TEST
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


def run_live_weather_scoring_test() -> None:
    """
    Fetch live weather and score a route segment using that live data.
    """

    print_section_title("LIVE WEATHER ROUTE RISK SCORING TEST")

    # Approximate Rexburg, Idaho coordinate.
    test_segment = {
        "label": "Rexburg Live Weather Test Segment",
        "latitude": 43.8231,
        "longitude": -111.7924,
        "road_condition": "normal",
        "is_night": False,
    }

    print("Test segment:")
    print_json_result(test_segment)

    print_section_title("FETCHING LIVE WEATHER")

    weather = fetch_weather_for_coordinate(
        latitude=test_segment["latitude"],
        longitude=test_segment["longitude"],
    )

    print("Normalized live weather:")
    print_json_result(weather)

    print_section_title("SCORING SEGMENT WITH LIVE WEATHER")

    risk_result = score_segment(
        weather=weather,
        road_condition=test_segment["road_condition"],
        is_night=test_segment["is_night"],
    )

    final_result = {
        "segment_label": test_segment["label"],
        "latitude": test_segment["latitude"],
        "longitude": test_segment["longitude"],
        "weather": weather,
        "risk_result": risk_result,
    }

    print_json_result(final_result)

    print_section_title("END LIVE WEATHER ROUTE RISK SCORING TEST")


# ============================================================
# LOCAL MANUAL TESTING ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_live_weather_scoring_test()