"""Structural validation for the Google Maps dashboard link."""

from pathlib import Path


DASHBOARD_PATH = (
    Path("app")
    / "dashboard"
    / "index.html"
)


def assert_contains(
    source: str,
    value: str,
    label: str,
) -> None:
    if value not in source:
        raise AssertionError(
            f"{label}: missing {value!r}"
        )

    print(f"PASS: {label}")


def main() -> None:
    print(
        "\nGoogle Maps dashboard-link validation"
    )
    print("=" * 52)

    source = DASHBOARD_PATH.read_text(
        encoding="utf-8-sig"
    )

    assert_contains(
        source,
        "function buildGoogleMapsUrl(",
        "Google Maps URL builder exists",
    )

    assert_contains(
        source,
        '"https://www.google.com/maps/dir/"',
        "official directions URL is used",
    )

    assert_contains(
        source,
        '"waypoints"',
        "route waypoints are included",
    )

    assert_contains(
        source,
        "View in Google Maps",
        "route-card link label exists",
    )

    assert_contains(
        source,
        'target="_blank"',
        "link opens in a new tab",
    )

    assert_contains(
        source,
        'rel="noopener noreferrer"',
        "new-tab security attributes exist",
    )

    assert_contains(
        source,
        "Google Maps may calculate a different route.",
        "route difference warning exists",
    )

    print(
        "\nAll Google Maps dashboard checks passed."
    )


if __name__ == "__main__":
    main()
