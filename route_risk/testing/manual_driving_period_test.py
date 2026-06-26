"""Validation for the shared four-state Day/Night event filter."""

from route_risk.core.driving_period import (
    apply_driving_period_to_events,
    classify_event_driving_period,
)


def assert_equal(
    actual,
    expected,
    label: str,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected "
            f"{expected!r}, got {actual!r}"
        )

    print(
        f"PASS: {label} -> {actual!r}"
    )


def event_ids(events):
    return [
        event["event_id"]
        for event in events
    ]


def main() -> None:
    print(
        "\nShared driving-period validation"
    )
    print("=" * 56)

    events = [
        {
            "event_id": "nv-night",
            "source": "nevada-511",
            "description": (
                "Ramp closed nightly from "
                "8:00PM-5:00AM."
            ),
        },
        {
            "event_id": "id-night",
            "source": "idaho-511",
            "description": (
                "Overnight lane closure "
                "10:00 PM to 6:00 AM."
            ),
        },
        {
            "event_id": "ut-day",
            "source": "utah-udot",
            "description": (
                "Daytime work from "
                "7:00 AM-4:00 PM."
            ),
        },
        {
            "event_id": "az-all-day",
            "source": "arizona-511",
            "description": (
                "Road closed 24 hours."
            ),
        },
        {
            "event_id": "unknown",
            "source": "test",
            "description": (
                "Road closure near interchange."
            ),
        },
    ]

    assert_equal(
        classify_event_driving_period(
            events[0]
        )["driving_period"],
        "night_only",
        "Nevada nightly description",
    )

    assert_equal(
        classify_event_driving_period(
            events[1]
        )["driving_period"],
        "night_only",
        "Idaho overnight description",
    )

    assert_equal(
        classify_event_driving_period(
            events[2]
        )["driving_period"],
        "day_only",
        "Utah daytime description",
    )

    assert_equal(
        classify_event_driving_period(
            events[3]
        )["driving_period"],
        "all_day",
        "Arizona all-day description",
    )

    day_events = apply_driving_period_to_events(
        events,
        is_night=False,
    )

    assert_equal(
        event_ids(day_events),
        [
            "ut-day",
            "az-all-day",
            "unknown",
        ],
        "Day mode filters night-only events",
    )

    night_events = (
        apply_driving_period_to_events(
            events,
            is_night=True,
        )
    )

    assert_equal(
        event_ids(night_events),
        [
            "nv-night",
            "id-night",
            "az-all-day",
            "unknown",
        ],
        "Night mode filters day-only events",
    )

    assert_equal(
        day_events[-1][
            "driving_period_applies"
        ],
        True,
        "Unknown schedule stays active for safety",
    )

    print(
        "\nAll shared driving-period checks passed."
    )


if __name__ == "__main__":
    main()
