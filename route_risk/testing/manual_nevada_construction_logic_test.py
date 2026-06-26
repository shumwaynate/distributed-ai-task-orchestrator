"""
Focused local validation for Nevada construction and closure classification.

Run:
    python -m route_risk.testing.manual_nevada_construction_logic_test
"""

from route_risk.integrations.road_conditions_client import (
    find_nearby_road_events,
    normalize_road_event_to_road_condition,
)
from route_risk.integrations.state_511_clients.nevada_511_client import (
    normalize_nevada_511_event,
)


def make_raw_event(
    *,
    event_id: int,
    event_type: str,
    event_subtype: str,
    is_full_closure: bool,
    description: str,
    lanes_affected: str,
) -> dict:
    return {
        "ID": event_id,
        "EventType": event_type,
        "EventSubType": event_subtype,
        "IsFullClosure": is_full_closure,
        "Description": description,
        "Comment": "",
        "Latitude": 36.1000,
        "Longitude": -115.1000,
        "LatitudeSecondary": None,
        "LongitudeSecondary": None,
        "LanesAffected": lanes_affected,
        "StartDate": None,
        "PlannedEndDate": None,
        "RoadwayName": "Demo Road",
        "DirectionOfTravel": "Both",
        "Severity": "Minor",
    }


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )

    print(f"PASS: {label} -> {actual!r}")


def main() -> None:
    print("\nNevada construction and closure logic validation")
    print("=" * 58)

    one_lane = normalize_nevada_511_event(
        make_raw_event(
            event_id=1,
            event_type="Roadwork",
            event_subtype="singleLineTraffic",
            is_full_closure=False,
            description=(
                "Flagging operation. 1 Lane Closed. "
                "Reduced lanes with flaggers."
            ),
            lanes_affected="1 Lane Closed",
        )
    )

    assert_equal(
        one_lane["event_type"],
        "construction",
        "one lane closure stays construction",
    )
    assert_equal(
        one_lane["closure_scope"],
        "partial_lane",
        "one lane closure scope",
    )
    assert_equal(
        one_lane["is_blocking_closure"],
        False,
        "one lane closure is non-blocking",
    )

    shoulder = normalize_nevada_511_event(
        make_raw_event(
            event_id=2,
            event_type="Closures",
            event_subtype="shoulderClosure",
            is_full_closure=False,
            description="Shoulder closed for utility work.",
            lanes_affected="Shoulder Affected",
        )
    )

    assert_equal(
        shoulder["event_type"],
        "construction",
        "shoulder closure stays construction",
    )
    assert_equal(
        shoulder["closure_scope"],
        "shoulder",
        "shoulder closure scope",
    )

    ramp = normalize_nevada_511_event(
        make_raw_event(
            event_id=3,
            event_type="Closures",
            event_subtype="rampClosure",
            is_full_closure=False,
            description=(
                "ON-RAMP CLOSED. Follow detours and use caution."
            ),
            lanes_affected="No Data",
        )
    )

    assert_equal(
        ramp["event_type"],
        "construction",
        "ramp closure does not automatically block nearby routes",
    )
    assert_equal(
        ramp["closure_scope"],
        "ramp",
        "ramp closure scope",
    )

    full_closure = normalize_nevada_511_event(
        make_raw_event(
            event_id=4,
            event_type="Closures",
            event_subtype="roadClosure",
            is_full_closure=True,
            description="Road closed in both directions.",
            lanes_affected="All Lanes Closed",
        )
    )

    assert_equal(
        full_closure["event_type"],
        "road closure",
        "full closure normalizes to road closure",
    )
    assert_equal(
        full_closure["closure_scope"],
        "full",
        "full closure scope",
    )
    assert_equal(
        full_closure["is_blocking_closure"],
        True,
        "full closure is blocking",
    )
    assert_equal(
        normalize_road_event_to_road_condition(
            full_closure
        ),
        "closed",
        "full closure scores as closed",
    )

    manual_closure = {
        "event_type": "road closure",
    }

    assert_equal(
        normalize_road_event_to_road_condition(
            manual_closure
        ),
        "closed",
        "legacy manual road closure remains blocking",
    )

    explicit_nonblocking_closure = {
        "event_type": "road closure",
        "is_full_closure": False,
    }

    assert_equal(
        normalize_road_event_to_road_condition(
            explicit_nonblocking_closure
        ),
        "construction",
        "explicit non-full closure is downgraded",
    )

    checkpoint = {
        "label": "Demo checkpoint",
        "latitude": 36.1001,
        "longitude": -115.1001,
    }

    matched = find_nearby_road_events(
        checkpoint=checkpoint,
        road_events=[one_lane],
        radius_miles=1.0,
    )

    assert_equal(
        len(matched),
        1,
        "nearby partial closure is matched",
    )
    assert_equal(
        matched[0]["road_condition"],
        "construction",
        "nearby partial closure remains construction",
    )
    assert_equal(
        matched[0]["roadway_name"],
        "Demo Road",
        "matched event preserves roadway name",
    )
    assert_equal(
        matched[0]["lanes_affected"],
        "1 Lane Closed",
        "matched event preserves lane information",
    )
    assert_equal(
        matched[0]["closure_scope"],
        "partial_lane",
        "matched event preserves closure scope",
    )

    print("\nAll Nevada construction logic checks passed.")


if __name__ == "__main__":
    main()
