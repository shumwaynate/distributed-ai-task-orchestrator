"""Focused validation for Nevada recurring nightly closures."""

import datetime as datetime_module

from route_risk.integrations.state_511_clients.nevada_511_client import (
    apply_nevada_recurrence_timing,
)


def timestamp_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
) -> float:
    return datetime_module.datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=datetime_module.timezone.utc,
    ).timestamp()


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )

    print(f"PASS: {label} -> {actual!r}")


def sample_event() -> dict:
    return {
        "event_id": "nightly-ramp-closure",
        "event_type": "road closure",
        "description": (
            "Ramp closed nightly from 8:00PM-5:00AM. "
            "Use other routes."
        ),
        "comment": "",
        "timing_status": "active",
        "recurrence_schedules": [
            {
                "Times": [
                    {
                        "StartTime": "00:00:00-07:00:00",
                        "EndTime": "23:59:59-07:00:00",
                    }
                ],
                "DaysOfWeek": [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
            }
        ],
    }


def main() -> None:
    print("\nNevada recurrence timing validation")
    print("=" * 48)

    midday = apply_nevada_recurrence_timing(
        sample_event(),
        reference_timestamp=timestamp_utc(
            2026,
            6,
            26,
            19,
            0,
        ),
    )

    assert_equal(
        midday["recurrence_active_now"],
        False,
        "12 PM Nevada time is outside nightly closure",
    )

    assert_equal(
        midday["timing_status"],
        "upcoming",
        "daytime closure becomes upcoming",
    )

    nighttime = apply_nevada_recurrence_timing(
        sample_event(),
        reference_timestamp=timestamp_utc(
            2026,
            6,
            27,
            4,
            0,
        ),
    )

    assert_equal(
        nighttime["recurrence_active_now"],
        True,
        "9 PM Nevada time is inside nightly closure",
    )

    assert_equal(
        nighttime["timing_status"],
        "active",
        "nighttime closure stays active",
    )

    early_morning = apply_nevada_recurrence_timing(
        sample_event(),
        reference_timestamp=timestamp_utc(
            2026,
            6,
            27,
            11,
            30,
        ),
    )

    assert_equal(
        early_morning["recurrence_active_now"],
        True,
        "4:30 AM belongs to prior night's window",
    )

    after_window = apply_nevada_recurrence_timing(
        sample_event(),
        reference_timestamp=timestamp_utc(
            2026,
            6,
            27,
            13,
            0,
        ),
    )

    assert_equal(
        after_window["recurrence_active_now"],
        False,
        "6 AM Nevada time is outside nightly closure",
    )

    assert_equal(
        after_window["recurrence_window_source"],
        "description",
        "description overrides incorrect all-day schedule",
    )

    print("\nAll recurrence timing checks passed.")


if __name__ == "__main__":
    main()
