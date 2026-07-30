"""Cross-disorder aggregation for completed Stage 6 science cells."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math


_OBSERVABLES = (
    "energy",
    "q2",
    "q4",
    "chi0",
    "chik_x",
    "chik_y",
    "chik_z",
)


@dataclass(frozen=True)
class Stage6EquilibrationSummary:
    passed: bool
    expected_cell_count: int
    completed_cell_count: int
    missing_cell_ids: tuple[str, ...]
    round_trips_min: int | None
    swap_acceptance_min: float | None
    swap_acceptance_max: float | None
    rhat_max: float | None
    ess_min: float | None
    thermal_error_fraction_max: float | None
    extension_count_max: int | None
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "expected_cell_count": self.expected_cell_count,
            "completed_cell_count": self.completed_cell_count,
            "missing_cell_ids": list(self.missing_cell_ids),
            "round_trips_min": self.round_trips_min,
            "swap_acceptance_min": self.swap_acceptance_min,
            "swap_acceptance_max": self.swap_acceptance_max,
            "rhat_max": self.rhat_max,
            "ess_min": self.ess_min,
            "thermal_error_fraction_max": self.thermal_error_fraction_max,
            "extension_count_max": self.extension_count_max,
            "elapsed_seconds": self.elapsed_seconds,
        }


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def summarize_equilibration(
    manifests: Sequence[Mapping[str, object]],
    *,
    expected_cell_ids: Sequence[str],
) -> Stage6EquilibrationSummary:
    """Reduce only complete per-J reports, never thermal rows as new disorder."""

    expected = tuple(str(value) for value in expected_cell_ids)
    if not expected or len(expected) != len(set(expected)):
        raise ValueError("expected Stage 6 cell IDs must be unique and nonempty")
    by_id: dict[str, Mapping[str, object]] = {}
    for manifest in manifests:
        if not isinstance(manifest, Mapping):
            raise TypeError("Stage 6 science manifests must be mappings")
        cell_id = manifest.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in set(expected):
            raise ValueError("science manifest substitutes an unregistered cell")
        if cell_id in by_id:
            raise ValueError("duplicate Stage 6 science manifest")
        by_id[cell_id] = manifest
    missing = tuple(cell_id for cell_id in expected if cell_id not in by_id)
    round_trips: list[int] = []
    acceptances: list[float] = []
    rhats: list[float] = []
    effective_samples: list[float] = []
    thermal_errors: list[float] = []
    extensions: list[int] = []
    elapsed_seconds = 0.0
    all_reports_pass = True
    for cell_id in expected:
        if cell_id not in by_id:
            continue
        manifest = by_id[cell_id]
        if manifest.get("classification") != "PILOT_PASS":
            raise ValueError("cross-J aggregation requires terminal PILOT_PASS cells")
        progress = manifest.get("progress")
        equilibration = manifest.get("equilibration")
        spec = manifest.get("spec")
        if not all(isinstance(value, Mapping) for value in (progress, equilibration, spec)):
            raise ValueError("science manifest diagnostics are incomplete")
        elapsed_seconds += _finite(progress.get("elapsed_seconds"), "elapsed seconds")
        reports = equilibration.get("reports")
        temperatures = spec.get("temperatures")
        if not isinstance(reports, list) or not isinstance(temperatures, list):
            raise ValueError("science temperature report arrays are missing")
        if len(reports) != len(temperatures):
            raise ValueError("science temperature report count does not match its ladder")
        expected_reports = {
            f"{cell_id}@T{index:03d}" for index in range(len(temperatures))
        }
        observed_reports: set[str] = set()
        for report in reports:
            if not isinstance(report, Mapping):
                raise ValueError("science equilibration report must be an object")
            report_id = report.get("j_id")
            if not isinstance(report_id, str) or report_id in observed_reports:
                raise ValueError("science equilibration report IDs are invalid")
            observed_reports.add(report_id)
            all_reports_pass &= report.get("passed") is True
            components = report.get("components")
            if not isinstance(components, Mapping):
                raise ValueError("science equilibration components are missing")
            edges = components.get("edge_acceptance")
            trips = components.get("round_trips")
            if not isinstance(edges, list) or not edges or not isinstance(trips, list) or not trips:
                raise ValueError("science travel diagnostics are incomplete")
            acceptances.extend(_finite(value, "edge acceptance") for value in edges)
            round_trips.extend(int(value) for value in trips)
            extension = components.get("extension_count")
            if isinstance(extension, bool) or not isinstance(extension, int) or extension < 0:
                raise ValueError("science extension count is invalid")
            extensions.append(extension)
            thermal_errors.append(
                _finite(
                    components.get("thermal_error_fraction"),
                    "thermal error fraction",
                )
            )
            for observable in _OBSERVABLES:
                diagnostics = components.get(observable)
                if not isinstance(diagnostics, Mapping):
                    raise ValueError(f"science {observable} diagnostics are missing")
                rhats.append(_finite(diagnostics.get("rhat"), f"{observable} R-hat"))
                effective_samples.append(
                    _finite(diagnostics.get("minimum_ess"), f"{observable} ESS")
                )
        if observed_reports != expected_reports:
            raise ValueError("science equilibration temperature IDs are incomplete")
    complete = len(by_id) == len(expected)
    return Stage6EquilibrationSummary(
        passed=complete and all_reports_pass,
        expected_cell_count=len(expected),
        completed_cell_count=len(by_id),
        missing_cell_ids=missing,
        round_trips_min=min(round_trips) if round_trips else None,
        swap_acceptance_min=min(acceptances) if acceptances else None,
        swap_acceptance_max=max(acceptances) if acceptances else None,
        rhat_max=max(rhats) if rhats else None,
        ess_min=min(effective_samples) if effective_samples else None,
        thermal_error_fraction_max=max(thermal_errors) if thermal_errors else None,
        extension_count_max=max(extensions) if extensions else None,
        elapsed_seconds=elapsed_seconds,
    )
