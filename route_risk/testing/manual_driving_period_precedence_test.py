"""Regression test for conflicting nightly and all-day feed timing."""

from route_risk.core.driving_period import (
    apply_driving_period_to_events,
    classify_event_driving_period,
)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )

    print(f"PASS: {label} -> {actual!r}")


def main() -> None:
    print(
        "\nDriving-period precedence regression test"
    )
    print("=" * 58)

    conflicting_event = {
        "event_id": "nv-night-conflict",
        "source": "nevada-511",
        "description": (
            "Road work on ramp from I-80 Westbound to "
            "US-395 Southbound. All lanes blocked - use "
            "other routes. Ramp closed nightly from "
            "8:00PM-5:00AM."
        ),
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

    classification = (
        classify_event_driving_period(
            conflicting_event
        )
    )

    assert_equal(
        classification["driving_period"],
        "night_only",
        "nightly description overrides all-day recurrence",
    )

    assert_equal(
        classification["driving_period_source"],
        "narrative_night_keyword",
        "classification reports narrative precedence",
    )

    day_events = apply_driving_period_to_events(
        [conflicting_event],
        is_night=False,
    )

    assert_equal(
        len(day_events),
        0,
        "Day mode ignores conflicting nightly closure",
    )

    night_events = apply_driving_period_to_events(
        [conflicting_event],
        is_night=True,
    )

    assert_equal(
        len(night_events),
        1,
        "Night mode includes conflicting nightly closure",
    )

    print(
        "\nAll precedence regression checks passed."
    )


if __name__ == "__main__":
    main()
