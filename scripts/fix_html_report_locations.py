#!/usr/bin/env python3
r"""
Fix origin/destination handling in the dashboard HTML report exporter.

Run from the project root:

    python .\scripts\fix_html_report_locations.py

Verify afterward with:

    python .\scripts\fix_html_report_locations.py --check
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "app" / "dashboard" / "index.html"

FEATURE_START = "<!-- HTML_REPORT_EXPORT_FEATURE_START -->"
FEATURE_END = "<!-- HTML_REPORT_EXPORT_FEATURE_END -->"
FIX_MARKER = "HTML_REPORT_LOCATION_FIX_V1"


LOCATION_HELPERS = r"""
  // HTML_REPORT_LOCATION_FIX_V1
  function endpointNumber(value) {
    if (value === null || value === undefined || value === "") {
      return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function parseCoordinateText(value) {
    const match = String(value ?? "").trim().match(
      /^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/
    );

    if (!match) {
      return null;
    }

    const latitude = endpointNumber(match[1]);
    const longitude = endpointNumber(match[2]);

    if (latitude === null || longitude === null) {
      return null;
    }

    return { latitude, longitude };
  }

  function normalizedLocationLabel(kind, value) {
    const defaultLabel = kind === "origin" ? "Origin" : "Destination";
    const text = String(value ?? "").trim();

    if (!text) {
      return defaultLabel;
    }

    const genericLabels = new Set([
      "origin",
      "selected origin",
      "destination",
      "selected destination",
    ]);

    return genericLabels.has(text.toLowerCase()) ? defaultLabel : text;
  }

  function resolveReportLocation(kind, comparison) {
    const request =
      latestSubmissionRequest &&
      typeof latestSubmissionRequest === "object"
        ? latestSubmissionRequest
        : {};

    const comparisonLocation =
      comparison?.[kind] && typeof comparison[kind] === "object"
        ? comparison[kind]
        : {};

    let latitude = endpointNumber(request[`${kind}_latitude`]);
    let longitude = endpointNumber(request[`${kind}_longitude`]);

    const livePoint =
      kind === "origin"
        ? (typeof origin !== "undefined" ? origin : null)
        : (typeof destination !== "undefined" ? destination : null);

    if ((latitude === null || longitude === null) && livePoint) {
      latitude = endpointNumber(livePoint.lat);
      longitude = endpointNumber(livePoint.lng);
    }

    if (latitude === null || longitude === null) {
      const coordinateElement = document.getElementById(
        kind === "origin" ? "originValue" : "destinationValue"
      );
      const parsedCoordinates = parseCoordinateText(
        coordinateElement?.textContent
      );

      if (parsedCoordinates) {
        latitude = parsedCoordinates.latitude;
        longitude = parsedCoordinates.longitude;
      }
    }

    if (latitude === null || longitude === null) {
      latitude = endpointNumber(
        firstDefined(
          comparisonLocation.latitude,
          comparisonLocation.lat
        )
      );
      longitude = endpointNumber(
        firstDefined(
          comparisonLocation.longitude,
          comparisonLocation.lon,
          comparisonLocation.lng
        )
      );
    }

    const label = normalizedLocationLabel(
      kind,
      firstDefined(
        request[`${kind}_label`],
        comparisonLocation.label,
        comparisonLocation.name,
        comparisonLocation.location_label
      )
    );

    return { label, latitude, longitude };
  }

  function formatResolvedLocation(location) {
    if (
      endpointNumber(location?.latitude) === null ||
      endpointNumber(location?.longitude) === null
    ) {
      return normalizeText(location?.label, "Location unavailable");
    }

    return `${normalizeText(location.label, "Location")} (${Number(location.latitude).toFixed(5)}, ${Number(location.longitude).toFixed(5)})`;
  }

  function hasResolvedCoordinates(location) {
    return (
      endpointNumber(location?.latitude) !== null &&
      endpointNumber(location?.longitude) !== null
    );
  }

  function coordinateSlug(value) {
    const number = endpointNumber(value);

    if (number === null) {
      return null;
    }

    const prefix = number < 0 ? "n" : "";
    return `${prefix}${Math.abs(number).toFixed(4).replace(".", "-")}`;
  }
""".strip("\n")


REPORT_FILENAME_FUNCTION = r"""
  function reportFilename(comparison) {
    function slug(value) {
      return String(value ?? "route")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 45) || "route";
    }

    function locationSlug(location, fallback) {
      const label = String(location?.label ?? "").trim();
      const genericLabels = new Set([
        "origin",
        "selected origin",
        "destination",
        "selected destination",
      ]);

      if (label && !genericLabels.has(label.toLowerCase())) {
        return slug(label);
      }

      const latitudePart = coordinateSlug(location?.latitude);
      const longitudePart = coordinateSlug(location?.longitude);

      if (latitudePart && longitudePart) {
        return `${latitudePart}-${longitudePart}`;
      }

      return fallback;
    }

    const originLocation = resolveReportLocation("origin", comparison);
    const destinationLocation = resolveReportLocation(
      "destination",
      comparison
    );

    return `route-risk-${locationSlug(originLocation, "origin")}-to-${locationSlug(destinationLocation, "destination")}.html`;
  }
""".strip("\n")


DOWNLOAD_REPORT_FUNCTION = r"""
  function downloadReport() {
    if (!latestComparison) {
      exportStatus.textContent =
        "No completed route comparison is available yet.";
      return;
    }

    const originLocation = resolveReportLocation(
      "origin",
      latestComparison
    );
    const destinationLocation = resolveReportLocation(
      "destination",
      latestComparison
    );

    if (
      !hasResolvedCoordinates(originLocation) ||
      !hasResolvedCoordinates(destinationLocation)
    ) {
      exportStatus.textContent =
        "Could not read the selected origin and destination coordinates. Keep both map points selected and try again.";
      return;
    }

    const report = buildReport(latestComparison);
    const blob = new Blob(
      [report],
      { type: "text/html;charset=utf-8" }
    );
    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = reportFilename(latestComparison);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(
      () => URL.revokeObjectURL(downloadUrl),
      1000
    );

    exportStatus.textContent = `Downloaded ${anchor.download}`;
  }
""".strip("\n")


def create_backup(target: Path) -> Path:
    backup_dir = (
        Path(tempfile.gettempdir())
        / "distributed_route_risk_engine_backups"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = (
        backup_dir
        / f"index_before_html_report_location_fix_{timestamp}.html"
    )
    shutil.copy2(target, backup_path)
    return backup_path


def extract_feature(text: str) -> tuple[int, int, str]:
    start = text.find(FEATURE_START)
    end = text.find(FEATURE_END)

    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            "Could not find one complete HTML report export feature block."
        )

    if text.find(FEATURE_START, start + len(FEATURE_START)) != -1:
        raise RuntimeError(
            "Multiple HTML report export feature blocks were found."
        )

    end += len(FEATURE_END)
    return start, end, text[start:end]


def replace_function(
    feature: str,
    function_name: str,
    replacement: str,
    next_function_name: str,
) -> str:
    pattern = re.compile(
        rf"  function {re.escape(function_name)}\([^)]*\) \{{.*?"
        rf"(?=\n  function {re.escape(next_function_name)}\()",
        re.DOTALL,
    )
    updated, count = pattern.subn(
        replacement + "\n\n",
        feature,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not replace exactly one {function_name} function."
        )

    return updated


def install_fix() -> None:
    if not DASHBOARD_PATH.is_file():
        raise FileNotFoundError(
            f"Dashboard file not found: {DASHBOARD_PATH}"
        )

    original = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
    start, end, feature = extract_feature(original)

    if FIX_MARKER not in feature:
        insertion_anchor = "  function segmentResults(route) {"
        if insertion_anchor not in feature:
            raise RuntimeError(
                "Could not find the helper insertion point."
            )

        feature = feature.replace(
            insertion_anchor,
            LOCATION_HELPERS + "\n\n" + insertion_anchor,
            1,
        )

    feature = replace_function(
        feature,
        "reportFilename",
        REPORT_FILENAME_FUNCTION,
        "buildReport",
    )

    old_location_lines = (
        '    const origin = formatLocation(comparison.origin, "Origin");\n'
        '    const destination = formatLocation(comparison.destination, "Destination");'
    )
    new_location_lines = (
        '    const originLocation = resolveReportLocation(\n'
        '      "origin",\n'
        '      comparison\n'
        '    );\n'
        '    const destinationLocation = resolveReportLocation(\n'
        '      "destination",\n'
        '      comparison\n'
        '    );\n'
        '    const origin = formatResolvedLocation(originLocation);\n'
        '    const destination = formatResolvedLocation(destinationLocation);'
    )

    if old_location_lines in feature:
        feature = feature.replace(
            old_location_lines,
            new_location_lines,
            1,
        )
    elif (
        "const origin = formatResolvedLocation(originLocation);" not in feature
        or "const destination = formatResolvedLocation(destinationLocation);"
        not in feature
    ):
        raise RuntimeError(
            "Could not locate the report endpoint assignments."
        )

    feature = replace_function(
        feature,
        "downloadReport",
        DOWNLOAD_REPORT_FUNCTION,
        "resetExport",
    )

    updated = original[:start] + feature + original[end:]
    backup_path = create_backup(DASHBOARD_PATH)
    DASHBOARD_PATH.write_text(updated, encoding="utf-8")

    print(f"Fixed HTML report locations in: {DASHBOARD_PATH}")
    print(f"Backup created at: {backup_path}")
    print()
    print("The exporter now uses:")
    print("1. The submitted request coordinates")
    print("2. The live selected map points")
    print("3. The visible coordinate text above the map")
    print("4. The API response as a final fallback")
    print()
    print("It will not download a generic origin-to-destination report")
    print("when valid endpoint coordinates cannot be found.")


def check_fix() -> None:
    if not DASHBOARD_PATH.is_file():
        raise FileNotFoundError(
            f"Dashboard file not found: {DASHBOARD_PATH}"
        )

    text = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
    _, _, feature = extract_feature(text)

    checks = {
        "fix marker": FIX_MARKER in feature,
        "strict endpoint-number parsing": "function endpointNumber(value)" in feature,
        "request coordinate lookup": (
            'request[`${kind}_latitude`]' in feature
            and 'request[`${kind}_longitude`]' in feature
        ),
        "live map-point fallback": (
            'typeof origin !== "undefined"' in feature
            and 'typeof destination !== "undefined"' in feature
        ),
        "visible-coordinate fallback": (
            '"originValue"' in feature
            and '"destinationValue"' in feature
        ),
        "report uses resolved locations": (
            "formatResolvedLocation(originLocation)" in feature
            and "formatResolvedLocation(destinationLocation)" in feature
        ),
        "filename uses coordinates": (
            'coordinateSlug(location?.latitude)' in feature
            and 'coordinateSlug(location?.longitude)' in feature
        ),
        "download guard": (
            "!hasResolvedCoordinates(originLocation)" in feature
            and "!hasResolvedCoordinates(destinationLocation)" in feature
        ),
    }

    all_passed = True
    for label, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")
        all_passed = all_passed and passed

    if not all_passed:
        raise SystemExit(1)

    print()
    print("HTML report location fix is installed correctly.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the fix is installed.",
    )
    arguments = parser.parse_args()

    if arguments.check:
        check_fix()
    else:
        install_fix()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
