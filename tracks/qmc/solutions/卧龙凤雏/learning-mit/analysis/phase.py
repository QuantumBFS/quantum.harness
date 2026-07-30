"""Finite-size phase evidence and adaptive refinement requests."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from .data_io import LoadedRun
from .entanglement import EntropyFitSet, fit_entropy_arc


@dataclass(frozen=True)
class PhaseEvidence:
    phi_pi: float
    phase: str
    supporting_widths: tuple[int, ...]
    score: float


@dataclass(frozen=True)
class TransitionBracket:
    lower_phi_pi: float
    upper_phi_pi: float
    lower_phase: str
    upper_phase: str


@dataclass(frozen=True)
class CandidateSelection:
    status: str
    lower_phi_pi: float
    upper_phi_pi: float
    candidate_phi_pi: float
    reasons: tuple[str, ...]


def classify_angle(
    phi_pi: float, fits_by_width: dict[int, EntropyFitSet]
) -> PhaseEvidence:
    if len(fits_by_width) < 3:
        return PhaseEvidence(phi_pi, "inconclusive", tuple(sorted(fits_by_width)), 0.0)
    ordered = sorted(fits_by_width.items())
    best = [fit_set.best_model for _, fit_set in ordered]
    squared = {"log2", "log_log2", "page_log_log2"}
    if all(model == "constant" for model in best):
        phase = "insulator"
        score = min(fit_set.by_name("constant").weight for _, fit_set in ordered)
    elif all(model in squared for model in best):
        phase = "metal"
        score = min(
            sum(fit.weight for fit in fit_set.fits if fit.model in squared)
            for _, fit_set in ordered
        )
    elif all(model == "log" for model in best):
        phase = "critical"
        score = min(fit_set.by_name("log").weight for _, fit_set in ordered)
    else:
        phase = "inconclusive"
        score = 0.0
    return PhaseEvidence(phi_pi, phase, tuple(width for width, _ in ordered), score)


def locate_bracket(evidence: list[PhaseEvidence]) -> TransitionBracket:
    ordered = sorted(evidence, key=lambda item: item.phi_pi)
    for left, right in zip(ordered, ordered[1:], strict=False):
        if {left.phase, right.phase} == {"insulator", "metal"}:
            return TransitionBracket(
                lower_phi_pi=left.phi_pi,
                upper_phi_pi=right.phi_pi,
                lower_phase=left.phase,
                upper_phase=right.phase,
            )
    raise ValueError("phase change is not bracketed by adjacent angles")


def select_candidate(evidence: list[PhaseEvidence]) -> CandidateSelection:
    ordered = sorted(evidence, key=lambda item: item.phi_pi)
    if (
        len(ordered) < 2
        or len({item.phi_pi for item in ordered}) != len(ordered)
        or any(not np.isfinite(item.phi_pi) or not np.isfinite(item.score) for item in ordered)
    ):
        raise ValueError("candidate selection requires two distinct finite angles")
    try:
        bracket = locate_bracket(ordered)
        status = "bracketed"
        reasons: tuple[str, ...] = ()
        lower, upper = bracket.lower_phi_pi, bracket.upper_phi_pi
    except ValueError:
        pairs = list(zip(ordered, ordered[1:], strict=False))
        left, right = min(
            pairs,
            key=lambda pair: (
                -abs(pair[1].score - pair[0].score),
                0.5 * (pair[0].phi_pi + pair[1].phi_pi),
            ),
        )
        status = "exploratory"
        reasons = ("diii_transition_not_bracketed",)
        lower, upper = left.phi_pi, right.phi_pi
    midpoint = 0.5 * (lower + upper)
    available = [item.phi_pi for item in ordered if lower <= item.phi_pi <= upper]
    minimum_distance = min(abs(value - midpoint) for value in available)
    candidate = min(
        value
        for value in available
        if np.isclose(abs(value - midpoint), minimum_distance, atol=1e-12, rtol=0.0)
    )
    return CandidateSelection(status, lower, upper, candidate, reasons)


def propose_refinement(
    loaded: LoadedRun, budget_forecast: dict[str, Any]
) -> dict[str, Any]:
    del budget_forecast
    grouped: dict[float, dict[int, list[tuple[float, float]]]] = {}
    for key, stream in loaded.streams.items():
        stage, _, phi_pi, width, _ = key
        if "diii" not in stage:
            continue
        by_width = grouped.setdefault(phi_pi, {}).setdefault(width, [])
        for block in stream.blocks:
            by_width.extend(
                (point.interval_sites, point.entropy) for point in block.entropy_arc
            )

    models = ("constant", "log", "log2", "log_log2", "page_log_log2")
    evidence = []
    for phi_pi, widths in sorted(grouped.items()):
        fits = {}
        for width, observations in widths.items():
            intervals = sorted({interval for interval, _ in observations})
            rows = []
            for interval in intervals:
                values = np.array(
                    [value for current, value in observations if current == interval]
                )
                uncertainty = max(
                    float(values.std(ddof=1) / np.sqrt(len(values)))
                    if len(values) > 1
                    else 1e-6,
                    1e-9,
                )
                rows.append([interval, width, float(values.mean()), uncertainty])
            fits[width] = fit_entropy_arc(np.asarray(rows), models)
        evidence.append(classify_angle(phi_pi, fits))

    if len(evidence) < 2:
        return {
            "schema_version": 1,
            "status": "inconclusive",
            "stage": "diii-refine",
            "theta_pi": 0.45,
            "phi_pi": [],
            "widths": [],
            "streams": 0,
            "burn_in_layers_per_width": 12,
            "measurement_layers_per_width": 40,
            "block_layers_per_width": 5,
        }
    selection = select_candidate(evidence)
    midpoint = 0.5 * (selection.lower_phi_pi + selection.upper_phi_pi)
    return {
        "schema_version": 1,
        "status": selection.status,
        "stage": "diii-refine",
        "theta_pi": 0.45,
        "phi_pi": sorted(
            {selection.lower_phi_pi, midpoint, selection.upper_phi_pi}
        ),
        "widths": [8, 12, 16, 20, 24, 28, 32],
        "streams": 8,
        "burn_in_layers_per_width": 16,
        "measurement_layers_per_width": 96,
        "block_layers_per_width": 8,
    }


def write_refinement_request(
    loaded: LoadedRun, budget_forecast: dict[str, Any]
) -> Path:
    request = propose_refinement(loaded, budget_forecast)
    relative = Path("processed/refinement_request.json")
    destination = loaded.run_dir / relative
    payload = (json.dumps(request, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(destination, payload)

    manifest_path = loaded.run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("artifact_sha256", {})[relative.as_posix()] = hashlib.sha256(
        payload
    ).hexdigest()
    manifest_payload = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write(manifest_path, manifest_payload)
    return destination


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp"
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
