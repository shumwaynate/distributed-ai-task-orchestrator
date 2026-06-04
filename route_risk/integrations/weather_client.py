"""
route_risk/integrations/weather_client.py

Weather API integration for the Route Risk Engine.

Purpose:
- Fetch live weather forecast data for a latitude/longitude point.
- Normalize external API data into the weather format already used by
  route_risk.core.scoring.
- Keep external API logic separate from core risk-scoring logic.

Current provider:
- Open-Meteo Forecast API

Why Open-Meteo:
- Accepts latitude and longitude.
- Does not require an API key for basic non-commercial use.
- Provides weather values useful for route-risk scoring.

Normalized output shape:
    {
        "temperature_f": 32.0,
        "wind_mph": 14.0,
        "condition": "snow",
        "visibility_miles": 5.0,
        "source": "open-meteo",
        "raw_weather_code": 71
    }

Notes:
- This file does not change FastAPI or Celery yet.
- First, we prove live weather can be fetched and normalized by itself.
"""

import json
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


# ============================================================
# ROUTE RISK ENGINE WEATHER INTEGRATION
# ============================================================

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_for_coordinate(
    latitude: float,
    longitude: float,
    timeout_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Fetch and normalize live weather data for one coordinate.

    Parameters:
        latitude:
            WGS84 latitude. Must be between -90 and 90.

        longitude:
            WGS84 longitude. Must be between -180 and 180.

        timeout_seconds:
            Request timeout for the API call.

    Returns:
        Dictionary matching the weather shape expected by scoring.py.

    Raises:
        ValueError:
            If coordinates are outside valid ranges.

        RuntimeError:
            If the weather API request fails or returns unusable data.
    """

    validate_coordinate(latitude, longitude)

    api_response = _fetch_open_meteo_response(
        latitude=latitude,
        longitude=longitude,
        timeout_seconds=timeout_seconds,
    )

    return normalize_open_meteo_response(api_response)


def validate_coordinate(latitude: float, longitude: float) -> None:
    """
    Validate latitude and longitude values before calling the API.
    """

    if latitude < -90 or latitude > 90:
        raise ValueError(f"Latitude must be between -90 and 90. Received: {latitude}")

    if longitude < -180 or longitude > 180:
        raise ValueError(
            f"Longitude must be between -180 and 180. Received: {longitude}"
        )


def _fetch_open_meteo_response(
    latitude: float,
    longitude: float,
    timeout_seconds: int,
) -> Dict[str, Any]:
    """
    Call Open-Meteo's forecast API and return parsed JSON.
    """

    query_parameters = {
        "latitude": latitude,
        "longitude": longitude,

        # Use current weather block so we get one simple current-ish snapshot.
        "current": ",".join(
            [
                "temperature_2m",
                "wind_speed_10m",
                "weather_code",
            ]
        ),

        # Use Fahrenheit and mph so the normalized data matches the scoring
        # function's existing temperature_f and wind_mph fields.
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",

        # Ask for the local timezone to keep the response easy to inspect.
        "timezone": "auto",
    }

    url = f"{OPEN_METEO_FORECAST_URL}?{urlencode(query_parameters)}"

    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except HTTPError as error:
        raise RuntimeError(
            f"Open-Meteo request failed with HTTP status {error.code}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"Open-Meteo request failed because the URL could not be reached: {error}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError("Open-Meteo returned invalid JSON.") from error


def normalize_open_meteo_response(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Open-Meteo response JSON into the weather format used by scoring.py.
    """

    current = api_response.get("current")

    if not isinstance(current, dict):
        raise RuntimeError("Open-Meteo response did not include a usable current block.")

    temperature_f = current.get("temperature_2m")
    wind_mph = current.get("wind_speed_10m")
    weather_code = current.get("weather_code")

    condition = weather_code_to_condition(weather_code)

    return {
        "temperature_f": temperature_f,
        "wind_mph": wind_mph,
        "condition": condition,

        # Open-Meteo's simple current block does not provide visibility in this
        # first version. We keep the field as None so scoring can ignore it.
        "visibility_miles": None,

        # Extra trace/debug fields.
        "source": "open-meteo",
        "raw_weather_code": weather_code,
    }


def weather_code_to_condition(weather_code: Optional[int]) -> str:
    """
    Convert Open-Meteo WMO weather codes into simple condition words.

    The scoring engine currently checks simple words like:
    - snow
    - rain
    - fog
    - ice / icy
    - clear / cloudy

    This mapping keeps the external API format separate from scoring.py.
    """

    if weather_code is None:
        return "unknown"

    # Clear / mostly clear / partly cloudy / overcast.
    if weather_code in {0}:
        return "clear"

    if weather_code in {1, 2}:
        return "partly cloudy"

    if weather_code in {3}:
        return "cloudy"

    # Fog and depositing rime fog.
    if weather_code in {45, 48}:
        return "fog"

    # Drizzle and freezing drizzle.
    if weather_code in {51, 53, 55}:
        return "drizzle"

    if weather_code in {56, 57}:
        return "freezing drizzle"

    # Rain and freezing rain.
    if weather_code in {61, 63, 65, 80, 81, 82}:
        return "rain"

    if weather_code in {66, 67}:
        return "freezing rain"

    # Snow, snow grains, snow showers.
    if weather_code in {71, 73, 75, 77, 85, 86}:
        return "snow"

    # Thunderstorm.
    if weather_code in {95, 96, 99}:
        return "thunderstorm"

    return "unknown"


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
    print_section_title("OPEN-METEO WEATHER CLIENT MANUAL TEST")

    # Approximate Rexburg, Idaho coordinate.
    test_latitude = 43.8231
    test_longitude = -111.7924

    print(f"Fetching weather for latitude={test_latitude}, longitude={test_longitude}")

    weather = fetch_weather_for_coordinate(
        latitude=test_latitude,
        longitude=test_longitude,
    )

    print(json.dumps(weather, indent=2))

    print_section_title("END OPEN-METEO WEATHER CLIENT MANUAL TEST")