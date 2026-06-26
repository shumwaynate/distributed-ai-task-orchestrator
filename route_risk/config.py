"""Configuration and secret-loading helpers.

API keys are loaded from environment variables first. When an environment
variable is unavailable, the project falls back to an external key file.

Secret values must never be stored in the repository or copied into a Docker
image.
"""

import os
from pathlib import Path
from typing import List


def _resolve_default_key_directory() -> Path:
    """Return a portable default directory for external API-key files."""

    candidates = [
        # Read-only directory mounted by Docker Compose.
        Path("/run/secrets/route-risk-keys"),

        # Windows development locations.
        Path.home() / "OneDrive" / "Desktop" / "ORS Key",
        Path.home() / "Desktop" / "ORS Key",

        # General cross-platform fallback.
        Path.home() / ".route-risk-keys",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return candidates[-1]


KEY_DIRECTORY = Path(
    os.getenv(
        "ROUTE_RISK_KEY_DIRECTORY",
        str(_resolve_default_key_directory()),
    )
).expanduser()


ORS_KEY_FILE_PATH = KEY_DIRECTORY / "ORSKey.txt"
IDAHO_511_KEY_FILE_PATH = KEY_DIRECTORY / "Idaho511Key.txt"
NEVADA_511_KEY_FILE_PATH = KEY_DIRECTORY / "Nevada511Key.txt"
UTAH_UDOT_KEY_FILE_PATH = KEY_DIRECTORY / "UtahUDOTKey.txt"
ARIZONA_511_KEY_FILE_PATH = KEY_DIRECTORY / "Arizona511Key.txt"


def _read_api_key_from_file(
    file_path: Path,
    service_name: str,
    accepted_labels: List[str],
) -> str:
    """Read one API key from an external text file."""

    if not file_path.exists():
        raise RuntimeError(
            f"The {service_name} key file could not be found at: "
            f"{file_path}"
        )

    if not file_path.is_file():
        raise RuntimeError(
            f"The configured {service_name} key location is not a file: "
            f"{file_path}"
        )

    file_contents = file_path.read_text(
        encoding="utf-8",
    )

    nonempty_lines = [
        line.strip()
        for line in file_contents.splitlines()
        if line.strip()
    ]

    if not nonempty_lines:
        raise RuntimeError(
            f"The {service_name} key file is empty: {file_path}"
        )

    first_line = nonempty_lines[0].lower().rstrip(":")

    normalized_labels = [
        label.lower().rstrip(":")
        for label in accepted_labels
    ]

    if first_line in normalized_labels:
        nonempty_lines = nonempty_lines[1:]

    if not nonempty_lines:
        raise RuntimeError(
            f"The {service_name} key file contains a label but does not "
            "contain an API key."
        )

    api_key = nonempty_lines[0].strip()

    if not api_key:
        raise RuntimeError(
            f"No {service_name} API key could be read from the configured "
            "file."
        )

    return api_key


def _get_api_key(
    environment_variable: str,
    file_path: Path,
    service_name: str,
    accepted_labels: List[str],
) -> str:
    """Load a key from its environment variable, then fall back to a file."""

    environment_value = os.getenv(
        environment_variable,
        "",
    ).strip()

    if environment_value:
        return environment_value

    try:
        return _read_api_key_from_file(
            file_path=file_path,
            service_name=service_name,
            accepted_labels=accepted_labels,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"No {service_name} API key was available. Set the "
            f"{environment_variable} environment variable or provide the "
            f"external key file. {exc}"
        ) from exc


def get_ors_api_key() -> str:
    """Return the OpenRouteService API key."""

    return _get_api_key(
        environment_variable="ORS_API_KEY",
        file_path=ORS_KEY_FILE_PATH,
        service_name="OpenRouteService",
        accepted_labels=[
            "ORS Key",
            "OpenRouteService Key",
            "API Key",
        ],
    )


def get_idaho_511_api_key() -> str:
    """Return the Idaho 511 API key."""

    return _get_api_key(
        environment_variable="IDAHO_511_API_KEY",
        file_path=IDAHO_511_KEY_FILE_PATH,
        service_name="Idaho 511",
        accepted_labels=[
            "Idaho 511 Key",
            "Idaho511 Key",
            "Idaho API Key",
            "API Key",
        ],
    )


def get_nevada_511_api_key() -> str:
    """Return the Nevada 511 API key."""

    return _get_api_key(
        environment_variable="NEVADA_511_API_KEY",
        file_path=NEVADA_511_KEY_FILE_PATH,
        service_name="Nevada 511",
        accepted_labels=[
            "Nevada 511 Key",
            "Nevada511 Key",
            "NV Roads Key",
            "Nevada API Key",
            "API Key",
        ],
    )


def get_utah_udot_api_key() -> str:
    """Return the Utah UDOT API key."""

    return _get_api_key(
        environment_variable="UTAH_UDOT_API_KEY",
        file_path=UTAH_UDOT_KEY_FILE_PATH,
        service_name="Utah UDOT",
        accepted_labels=[
            "Utah UDOT Key",
            "UtahUDOT Key",
            "Utah 511 Key",
            "Utah API Key",
            "API Key",
        ],
    )


def get_arizona_511_api_key() -> str:
    """Return the Arizona 511 API key."""

    return _get_api_key(
        environment_variable="ARIZONA_511_API_KEY",
        file_path=ARIZONA_511_KEY_FILE_PATH,
        service_name="Arizona 511",
        accepted_labels=[
            "Arizona 511 Key",
            "Arizona511 Key",
            "AZ 511 Key",
            "Arizona API Key",
            "API Key",
        ],
    )