"""
route_risk/testing/manual_live_weather_celery_task_test.py

Manual test runner for the live-weather Route Risk Celery task.

Purpose:
- Confirm the live_weather_route_segment_risk_task can be imported.
- Confirm the task can fetch live weather using latitude/longitude.
- Confirm live weather can be scored through the route-risk scoring engine.
- Print clean, readable terminal output.
- Test the task logic before connecting it to FastAPI.

Important:
This file calls the Celery task logic directly using .run(...).

That means:
- It does not queue work in Redis yet.
- It does not require a running Celery worker.
- It does not prove distributed execution yet.
- It only proves the task code itself works.

This test does require:
- Internet access.
- Open-Meteo API availability.
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


from app.worker.tasks import live_weather_route_segment_risk_task


# ============================================================
# ROUTE RISK LIVE-WEATHER CELERY TASK MANUAL TEST
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


def run_live_weather_celery_task_test() -> None:
    """
    Run the live-weather route segment task directly.
    """

    print_section_title("LIVE WEATHER ROUTE SEGMENT CELERY TASK DIRECT TEST")

    test_segment = {
        "label": "Rexburg Live Weather Celery Task Test Segment",
        "latitude": 43.8231,
        "longitude": -111.7924,
        "road_condition": "normal",
        "is_night": False,
    }

    print("Test segment:")
    print_json_result(test_segment)

    print_section_title("RUNNING LIVE WEATHER TASK LOGIC DIRECTLY")

    result = live_weather_route_segment_risk_task.run(
        task_id=1,
        segment=test_segment,
    )

    print_json_result(result)

    print_section_title("END LIVE WEATHER ROUTE SEGMENT CELERY TASK DIRECT TEST")


# ============================================================
# LOCAL MANUAL TESTING ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_live_weather_celery_task_test()