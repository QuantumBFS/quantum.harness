"""Phase-only refinement and final frozen-report command-line entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

from .anisotropy import calibrate_alpha, fit_spatial_dimension
from .bootstrap import bootstrap_candidate, summarize_bootstrap
from .casimir import fit_casimir
from .data_io import LoadedRun, LoadedStream, load_run
from .effective_central_charge import extrapolate_c_eff, fit_width_c_eff
from .entanglement import fit_entropy_arc
from .gates import evaluate_claim_gates
from .html_renderer import render_html
from .pdf_renderer import render_pdf
from .phase import (
    CandidateSelection,
    TransitionBracket,
    classify_angle,
    locate_bracket,
    select_candidate,
    write_refinement_request,
)
from .plots import make_plots
from .report_model import build_report
from .verify_outputs import verify_report_pair


MODELS = ("constant", "log", "log2", "log_log2", "page_log_log2")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--phase-only", type=Path)
    mode.add_argument("--final", type=Path)
    arguments = parser.parse_args()
    if arguments.phase_only:
        loaded = load_run(arguments.phase_only)
        forecast_path = loaded.run_dir / "raw/benchmark.json"
        forecast = (
            json.loads(forecast_path.read_text(encoding="utf-8"))
            if forecast_path.is_file()
            else {}
        )
        path = write_refinement_request(loaded, forecast)
        print(path)
        return 0
    run_final_analysis(arguments.final)
    return 0


def run_final_analysis(run_dir: Path) -> dict[str, Any]:
    loaded = load_run(run_dir)
    summary = build_summary(loaded)
    summary_path = loaded.run_dir / "summary.json"
    _atomic_json(summary_path, summary)
    make_plots(summary, "en", loaded.run_dir / "plots/en")
    make_plots(summary, "zh", loaded.run_dir / "plots/zh")
    english = build_report(summary, "en")
    chinese = build_report(summary, "zh")
    render_html(english, loaded.run_dir / "report.html")
    render_html(chinese, loaded.run_dir / "report-zh.html")
    render_pdf(english, loaded.run_dir / "report.pdf")
    render_pdf(chinese, loaded.run_dir / "report-zh.pdf")
    verification = verify_report_pair(loaded.run_dir)
    if not verification.passed:
        raise ValueError("report verification failed: " + "; ".join(verification.errors))
    _register_stable_artifacts(loaded.run_dir, summary["status"])
    return summary


def build_summary(loaded: LoadedRun) -> dict[str, Any]:
    manifest = dict(loaded.manifest)
    config = manifest["config"]
    grouped = _group_streams(loaded)
    xy_angles = _scan_evidence(grouped, theta_pi=0.5)
    diii_angles = _scan_evidence(grouped, theta_pi=0.45)
    xy_bracket = _xy_bracket(xy_angles)
    phase_evidence = _phase_model_evidence(grouped, theta_pi=0.45)
    selection = select_candidate(phase_evidence) if len(phase_evidence) >= 2 else None
    diii_bracket = (
        (selection.lower_phi_pi, selection.upper_phi_pi)
        if selection is not None and selection.status == "bracketed"
        else None
    )
    arcs, coefficients = _representative_entanglement(grouped)
    entanglement_c_eff = _entanglement_c_eff(grouped, selection)
    casimir, bootstrap, anisotropy, casimir_c_eff = _candidate_statistics(
        loaded, selection
    )
    oracle_raw = _optional_json(loaded.run_dir / "raw/oracles.json")
    negative_raw = _optional_json(loaded.run_dir / "raw/negative-control.json")
    benchmark = _optional_json(loaded.run_dir / "raw/benchmark.json")
    oracle_pass = bool(oracle_raw.get("required_pass", False))
    xy_overlap = xy_bracket is not None and _overlap(xy_bracket, (0.20, 0.28))
    if entanglement_c_eff["value"] is None:
        claim = {
            "status": "unavailable",
            "published": False,
            "value": None,
            "interval": None,
            "reasons": ["entanglement_estimate_unavailable"],
        }
    else:
        diii_widths = sorted(
            {
                key[3]
                for key in loaded.streams
                if "diii" in key[0]
                and selection is not None
                and math.isclose(key[2], selection.candidate_phi_pi, abs_tol=1e-12)
            }
        )
        selected_stream_counts = [
            len(
                {
                    key[4]
                    for key in loaded.streams
                    if "diii" in key[0]
                    and key[3] == width
                    and selection is not None
                    and math.isclose(key[2], selection.candidate_phi_pi, abs_tol=1e-12)
                }
            )
            for width in diii_widths
        ]
        complete_blocks = int(bootstrap.get("effective_sample_size", 0))
        decision = evaluate_claim_gates(
            xy_interval=xy_bracket or (float("inf"), float("inf")),
            xy_reference=(0.20, 0.28),
            diii_width_count=len(diii_widths),
            opposite_phase_evidence=bool(
                selection is not None and selection.status == "bracketed"
            ),
            streams_per_width=min(selected_stream_counts, default=0),
            complete_blocks=complete_blocks,
            oracle_pass=oracle_pass,
            invariant_pass=True,
            casimir_fit_stable=bool(casimir_c_eff["fit_stable"]),
            alpha_stable=bool(anisotropy["alpha_stable"]),
            entanglement_c_eff=float(entanglement_c_eff["value"]),
            entanglement_standard_error=float(
                entanglement_c_eff["standard_error"]
            ),
            casimir_c_eff=casimir_c_eff["value"],
            casimir_standard_error=casimir_c_eff["standard_error"],
            bootstrap_failure_fraction=float(
                casimir_c_eff.get("bootstrap_failure_fraction", 0.0)
            ),
        )
        interval = (
            casimir_c_eff["interval"]
            if casimir_c_eff["value"] is not None
            else entanglement_c_eff["interval"]
        )
        claim = {
            "status": decision.status,
            "published": decision.publish_central_charge,
            "value": decision.central_charge,
            "interval": interval,
            "reasons": list(decision.reasons),
        }
    if not oracle_pass or not xy_overlap:
        status = "validation_failed"
    elif claim["status"] == "candidate":
        status = "xy_reproduced_diii_candidate"
    else:
        status = "xy_reproduced_diii_inconclusive"
    physical = oracle_raw.get("physical_limits", {})
    dense = oracle_raw.get("dense", {})
    control = negative_raw.get("control", oracle_raw.get("negative_control", {}))
    widths = sorted({stream.width for stream in loaded.streams.values()})
    streams = max(
        (stage.get("streams", 0) for stage in config.get("stages", [])), default=0
    )
    block_hash = manifest.get("artifact_sha256", {}).get("raw/blocks.csv")
    stable_hashes = {"blocks": block_hash} if block_hash else {}
    stable_hashes["stream_set"] = _stream_set_hash(manifest)
    return {
        "schema_version": 1,
        "status": status,
        "exploratory": True,
        "team": "卧龙凤雏",
        "run": {
            "elapsed_seconds": manifest.get("elapsed_s", 0.0),
            "ordinary_stop_seconds": config["runtime"]["ordinary_stop_seconds"],
            "hard_stop_seconds": config["runtime"]["hard_stop_seconds"],
            "widths": widths,
            "streams": streams,
        },
        "xy": {
            "theta_pi": 0.5,
            "reference_window": [0.20, 0.28],
            "bracket": list(xy_bracket) if xy_bracket else None,
            "evidence": xy_angles,
        },
        "diii": {
            "theta_pi": 0.45,
            "bracket": list(diii_bracket) if diii_bracket else None,
            "evidence": diii_angles,
        },
        "candidate_selection": _selection_dict(selection),
        "entanglement": {"arcs": arcs, "coefficients": coefficients},
        "entanglement_c_eff": entanglement_c_eff,
        "casimir": casimir,
        "bootstrap": bootstrap,
        "anisotropy": anisotropy,
        "casimir_c_eff": casimir_c_eff,
        "estimator_comparison": _estimator_comparison(
            entanglement_c_eff, casimir_c_eff
        ),
        "claim": claim,
        "central_charge": {
            "published": claim["published"],
            "value": claim["value"],
            "interval": claim["interval"],
        },
        "negative_control": {
            "born_mean": control.get("born_mean", 0.0),
            "iid_mean": control.get("iid_mean", 0.0),
            "z_score": control.get("z_score", 0.0),
            "physical": False,
        },
        "runtime": {
            "allocation": _runtime_allocation(manifest, benchmark),
            "forecast_seconds": benchmark.get("forecast_seconds"),
        },
        "oracles": {
            "dense_probability_error": dense.get("max_joint_probability_error"),
            "dense_covariance_error": dense.get("max_covariance_error"),
            "weak_limit_error": None,
            "y_swap_residual": physical.get("y_swap_residual"),
            "passed": oracle_pass,
        },
        "hashes": stable_hashes,
    }


def _group_streams(
    loaded: LoadedRun,
) -> dict[tuple[str, float, float, int], list[LoadedStream]]:
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]] = {}
    for key, stream in loaded.streams.items():
        grouped.setdefault(key[:4], []).append(stream)
    return grouped


def _scan_evidence(
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]],
    theta_pi: float,
) -> list[dict[str, float]]:
    by_angle: dict[float, list[tuple[int, float]]] = {}
    for (_, theta, phi, width), streams in grouped.items():
        if not math.isclose(theta, theta_pi, abs_tol=1e-12):
            continue
        mean = np.mean(
            [
                block.half_chain_entropy
                for stream in streams
                for block in stream.blocks
            ]
        )
        by_angle.setdefault(phi, []).append((width, float(mean)))
    evidence = []
    for phi, values in sorted(by_angle.items()):
        values = sorted(values)
        if len(values) >= 2:
            x = np.log([value[0] for value in values])
            y = [value[1] for value in values]
            score = float(np.polyfit(x, y, 1)[0])
        else:
            score = 0.0
        evidence.append({"phi_pi": phi, "score": score})
    return evidence


def _xy_bracket(evidence: list[dict[str, float]]) -> tuple[float, float] | None:
    angles = [point["phi_pi"] for point in evidence]
    if len(angles) < 2:
        return None
    below = [value for value in angles if value <= 0.25]
    above = [value for value in angles if value >= 0.25]
    if below and above:
        lower, upper = max(below), min(above)
        if lower == upper:
            index = angles.index(lower)
            if index > 0:
                lower = angles[index - 1]
            elif index + 1 < len(angles):
                upper = angles[index + 1]
        return lower, upper
    nearest = sorted(angles, key=lambda value: abs(value - 0.25))[:2]
    return min(nearest), max(nearest)


def _phase_bracket(
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]],
    theta_pi: float,
) -> tuple[float, float] | None:
    evidence = _phase_model_evidence(grouped, theta_pi)
    try:
        bracket = locate_bracket(evidence)
    except ValueError:
        return None
    return bracket.lower_phi_pi, bracket.upper_phi_pi


def _phase_model_evidence(
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]],
    theta_pi: float,
) -> list:
    by_angle: dict[float, dict[int, Any]] = {}
    candidates = {
        phi
        for (_, theta, phi, _) in grouped
        if math.isclose(theta, theta_pi, abs_tol=1e-12)
    }
    for phi in candidates:
        for (_, theta, current, width), streams in grouped.items():
            if not math.isclose(theta, theta_pi, abs_tol=1e-12) or current != phi:
                continue
            points = _mean_arc(streams, width)
            if len(points) >= 6:
                by_angle.setdefault(phi, {})[width] = fit_entropy_arc(points, MODELS)
    return [classify_angle(phi, fits) for phi, fits in sorted(by_angle.items())]


def _mean_arc(streams: list[LoadedStream], width: int) -> np.ndarray:
    rows = []
    for interval in range(1, width):
        values = np.array(
            [
                point.entropy
                for stream in streams
                for block in stream.blocks
                for point in block.entropy_arc
                if point.interval_sites == interval
            ]
        )
        if len(values):
            error = max(
                float(values.std(ddof=1) / np.sqrt(len(values)))
                if len(values) > 1
                else 1e-6,
                1e-9,
            )
            rows.append([interval, width, float(values.mean()), error])
    return np.asarray(rows, dtype=float)


def _representative_entanglement(
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]],
) -> tuple[list[dict[str, Any]], list[dict[str, float]]]:
    arcs = []
    coefficients = []
    ordered = sorted(grouped.items(), key=lambda item: (item[0][1], item[0][2], item[0][3]))
    representatives = ordered[-2:] if len(ordered) >= 2 else ordered
    for (_, _, phi, width), streams in representatives:
        points = _mean_arc(streams, width)
        arcs.append(
            {
                "label": f"L={width}, φ/π={phi:.2f}",
                "width": width,
                "phi_pi": phi,
                "points": points[:, :3:2].tolist() if len(points) else [],
            }
        )
    for (_, _, phi, width), streams in ordered:
        points = _mean_arc(streams, width)
        if len(points) < 6:
            continue
        fit = fit_entropy_arc(points, MODELS).by_name("page_log_log2")
        coefficients.append(
            {
                "phi_pi": phi,
                "width": width,
                "v": float(fit.coefficients[1]),
                "c_prime": float(6 * fit.coefficients[3]),
                "c": float(6 * fit.coefficients[2]),
            }
        )
    return arcs, coefficients


def _selection_dict(selection: CandidateSelection | None) -> dict[str, Any]:
    if selection is None:
        return {
            "status": "unavailable",
            "lower_phi_pi": None,
            "upper_phi_pi": None,
            "candidate_phi_pi": None,
            "reasons": ["fewer_than_two_diii_angles"],
        }
    return {
        "status": selection.status,
        "lower_phi_pi": selection.lower_phi_pi,
        "upper_phi_pi": selection.upper_phi_pi,
        "candidate_phi_pi": selection.candidate_phi_pi,
        "reasons": list(selection.reasons),
    }


def _empty_entanglement_c_eff(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "phi_pi": None,
        "widths": [],
        "per_width": [],
        "value": None,
        "standard_error": None,
        "interval": None,
        "fitted": [],
        "residuals": [],
        "chi2_per_dof": None,
        "covariance_condition": None,
        "model_weights": {},
        "stable_without_smallest": False,
        "reason": reason,
    }


def _entanglement_c_eff(
    grouped: dict[tuple[str, float, float, int], list[LoadedStream]],
    selection: CandidateSelection | None,
) -> dict[str, Any]:
    if selection is None:
        return _empty_entanglement_c_eff("candidate_selection_unavailable")
    selected: dict[int, list[LoadedStream]] = {}
    for (stage, _, phi, width), streams in grouped.items():
        if "diii" in stage and math.isclose(
            phi, selection.candidate_phi_pi, abs_tol=1e-12
        ):
            selected.setdefault(width, []).extend(streams)
    fits_by_width: dict[int, tuple[float, float]] = {}
    model_weights: dict[str, float] = {model: 0.0 for model in MODELS}
    used_weight_sets = 0
    try:
        for width, streams in sorted(selected.items()):
            rows = _mean_arc(streams, width)
            if len(rows) < 6:
                continue
            estimate, covariance, _ = fit_width_c_eff(rows)
            error = max(float(np.sqrt(max(covariance[1, 1], 0.0))), 1e-8)
            fits_by_width[width] = (estimate, error)
            fit_set = fit_entropy_arc(rows, MODELS)
            for model in MODELS:
                model_weights[model] += fit_set.by_name(model).weight
            used_weight_sets += 1
        if used_weight_sets:
            model_weights = {
                model: value / used_weight_sets
                for model, value in model_weights.items()
            }
        fit = extrapolate_c_eff(
            selection.candidate_phi_pi, fits_by_width, model_weights
        )
    except (ValueError, np.linalg.LinAlgError) as error:
        return _empty_entanglement_c_eff(str(error))
    standard_error = (fit.interval[1] - fit.interval[0]) / (2 * 1.96)
    return {
        "status": "available",
        "phi_pi": fit.phi_pi,
        "widths": fit.widths.tolist(),
        "per_width": fit.per_width.tolist(),
        "value": fit.extrapolated,
        "standard_error": standard_error,
        "interval": list(fit.interval),
        "fitted": fit.fitted.tolist(),
        "residuals": fit.residuals.tolist(),
        "chi2_per_dof": fit.chi2_per_dof,
        "covariance_condition": fit.covariance_condition,
        "model_weights": fit.model_weights,
        "stable_without_smallest": fit.stable_without_smallest,
        "reason": None,
    }


def _empty_candidate_statistics(reason: str) -> tuple[dict, dict, dict, dict]:
    empty_casimir = {
        "widths": [],
        "gamma": [],
        "fitted": [],
        "residuals": [],
        "amplitude": None,
        "amplitude_interval": None,
        "correction": None,
        "chi2_per_dof": None,
        "covariance_condition": None,
        "stable_without_smallest": False,
        "reason": reason,
    }
    empty_bootstrap = {
        "amplitude_samples": [],
        "effective_sample_size": 0.0,
        "valid_replicates": 0,
        "failure_fraction": 1.0,
    }
    empty_anisotropy = {
        "delta": None,
        "spatial": [],
        "temporal": [],
        "alpha": None,
        "alpha_interval": None,
        "alpha_stable": False,
        "window_relative_spread": None,
        "window_estimates": [],
    }
    empty_c_eff = {
        "status": "unavailable",
        "value": None,
        "standard_error": None,
        "interval": None,
        "fit_stable": False,
        "bootstrap_failure_fraction": 0.0,
        "reason": reason,
    }
    return empty_casimir, empty_bootstrap, empty_anisotropy, empty_c_eff


def _candidate_statistics(
    loaded: LoadedRun,
    selection: CandidateSelection | None,
) -> tuple[dict, dict, dict, dict]:
    if selection is None:
        return _empty_candidate_statistics("candidate_selection_unavailable")
    selected: dict[int, list[LoadedStream]] = {}
    for key, stream in loaded.streams.items():
        if "diii" in key[0] and math.isclose(
            key[2], selection.candidate_phi_pi, abs_tol=1e-12
        ):
            selected.setdefault(key[3], []).append(stream)
    widths = np.array(sorted(selected), dtype=float)
    if len(widths) < 5:
        return _empty_candidate_statistics("fewer_than_five_diii_widths")
    gamma = np.array(
        [
            np.mean(
                [block.gamma for stream in selected[int(width)] for block in stream.blocks]
            )
            for width in widths
        ]
    )
    variances = np.array(
        [
            max(
                np.var(
                    [
                        block.gamma
                        for stream in selected[int(width)]
                        for block in stream.blocks
                    ],
                    ddof=1,
                ),
                1e-10,
            )
            for width in widths
        ]
    )
    correlations = {
        width: [
            np.asarray(
                [
                    (point.distance, point.connected_parity)
                    for point in block.spatial_correlations
                ],
                dtype=float,
            )
            for stream in streams
            for block in stream.blocks
        ]
        for width, streams in selected.items()
    }
    lyapunov = {
        width: [
            np.asarray(block.lyapunov, dtype=float)
            for stream in streams
            for block in stream.blocks
        ]
        for width, streams in selected.items()
    }
    try:
        fit = fit_casimir(widths, gamma, np.diag(variances), widths.min(), "l3")
        spatial = fit_spatial_dimension(
            correlations, tuple(widths.astype(int)), (1 / 8, 3 / 8)
        )
        alpha_fit = calibrate_alpha(spatial, lyapunov, (None, None))
        distribution = bootstrap_candidate(
            loaded,
            TransitionBracket(
                selection.candidate_phi_pi,
                selection.candidate_phi_pi,
                selection.status,
                selection.status,
            ),
            samples=1000,
            seed=122,
        )
        central_summary = summarize_bootstrap(
            distribution.central_charge, requested=1000
        )
        amplitude_values = distribution.casimir_amplitude[
            np.isfinite(distribution.casimir_amplitude)
        ]
        alpha_values = distribution.alpha[np.isfinite(distribution.alpha)]
        if central_summary.unavailable or not len(amplitude_values) or not len(alpha_values):
            return _empty_candidate_statistics("bootstrap_failure_rate_exceeds_5_percent")
    except (ValueError, np.linalg.LinAlgError) as error:
        return _empty_candidate_statistics(str(error))
    fitted = gamma - fit.residuals
    casimir = {
        "widths": widths.tolist(),
        "gamma": gamma.tolist(),
        "fitted": fitted.tolist(),
        "residuals": fit.residuals.tolist(),
        "amplitude": fit.casimir_amplitude,
        "amplitude_interval": np.quantile(
            amplitude_values, [0.025, 0.975]
        ).tolist(),
        "correction": "l3",
        "chi2_per_dof": fit.chi2 / max(fit.degrees_of_freedom, 1),
        "covariance_condition": fit.covariance_condition,
        "stable_without_smallest": fit.stable_without_smallest,
        "reason": None,
    }
    bootstrap = {
        "amplitude_samples": amplitude_values.tolist(),
        "effective_sample_size": float(
            sum(len(stream.blocks) for streams in selected.values() for stream in streams)
        ),
        "valid_replicates": central_summary.valid_replicates,
        "failure_fraction": central_summary.failure_fraction,
    }
    alpha_interval = np.quantile(alpha_values, [0.025, 0.975]).tolist()
    anisotropy = {
        "delta": spatial.delta,
        "spatial": [
            [int(width), float(np.mean([abs(row[1]) for block in blocks for row in block]))]
            for width, blocks in sorted(correlations.items())
        ],
        "temporal": [
            [
                int(width),
                float(
                    np.mean(
                        [
                            np.sort(spectrum)[::-1][0]
                            - np.sort(spectrum)[::-1][1]
                            for spectrum in spectra
                        ]
                    )
                ),
            ]
            for width, spectra in sorted(lyapunov.items())
        ],
        "alpha": alpha_fit.alpha,
        "alpha_interval": alpha_interval,
        "alpha_stable": alpha_fit.stable,
        "window_relative_spread": alpha_fit.window_relative_spread,
        "window_estimates": [
            {
                "window": "all complete blocks",
                "alpha": alpha_fit.alpha,
                "error": alpha_fit.standard_error,
            }
        ],
    }
    standard_error = float(
        np.nanstd(distribution.central_charge, ddof=1)
    )
    casimir_c_eff = {
        "status": "available",
        "value": central_summary.estimate,
        "standard_error": standard_error,
        "interval": list(central_summary.interval),
        "fit_stable": bool(
            fit.stable_without_smallest and fit.covariance_condition <= 1.0e10
        ),
        "bootstrap_failure_fraction": central_summary.failure_fraction,
        "reason": None,
    }
    return casimir, bootstrap, anisotropy, casimir_c_eff


def _estimator_comparison(
    entanglement: dict[str, Any], casimir: dict[str, Any]
) -> dict[str, Any]:
    if entanglement.get("value") is None or casimir.get("value") is None:
        return {
            "available": False,
            "difference": None,
            "combined_95_threshold": None,
            "agrees": None,
        }
    difference = abs(float(entanglement["value"]) - float(casimir["value"]))
    threshold = 1.96 * math.sqrt(
        float(entanglement["standard_error"]) ** 2
        + float(casimir["standard_error"]) ** 2
    )
    return {
        "available": True,
        "difference": difference,
        "combined_95_threshold": threshold,
        "agrees": difference <= threshold,
    }


def _runtime_allocation(manifest: dict, benchmark: dict) -> list[list[Any]]:
    del benchmark
    stages: dict[str, float] = {}
    for task in manifest.get("tasks", []):
        stage = task["key"].split("-a", 1)[0]
        stages[stage] = max(stages.get(stage, 0.0), float(task.get("elapsed_s", 0.0)))
    return [[stage, round(seconds / 60, 3)] for stage, seconds in sorted(stages.items())]


def _stream_set_hash(manifest: dict) -> str:
    hashes = [
        value
        for key, value in manifest.get("artifact_sha256", {}).items()
        if key.startswith("raw/streams/")
    ]
    return hashlib.sha256("".join(sorted(hashes)).encode("ascii")).hexdigest()


def _register_stable_artifacts(run_dir: Path, status: str) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stable = [
        run_dir / "summary.json",
        run_dir / "report.html",
        run_dir / "report-zh.html",
        run_dir / "report.pdf",
        run_dir / "report-zh.pdf",
        *sorted((run_dir / "plots/en").glob("*.png")),
        *sorted((run_dir / "plots/zh").glob("*.png")),
        *(path for path in (
            run_dir / "config.toml",
            run_dir / "raw/oracles.json",
            run_dir / "raw/benchmark.json",
            run_dir / "raw/negative-control.json",
            run_dir / "processed/refinement_request.json",
        ) if path.is_file()),
    ]
    for path in stable:
        relative = path.relative_to(run_dir).as_posix()
        manifest.setdefault("artifact_sha256", {})[relative] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    manifest["status"] = status
    manifest["completed_at"] = manifest.get("completed_at") or manifest.get("updated_at")
    _atomic_json(manifest_path, manifest)


def _atomic_json(path: Path, value: dict) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    temporary = path.parent / f".{path.name}.tmp"
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _optional_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _overlap(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return max(left[0], right[0]) <= min(left[1], right[1])


if __name__ == "__main__":
    raise SystemExit(main())
