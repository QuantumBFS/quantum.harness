#!/usr/bin/env python3
"""Fail-closed entry point for the production-v2 joint two-mode audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fcs_time_series import validate_fcs_time_series
from src.production_v2_manifest import sha256_file
from src.research_dataset import load_research_dataset
from src.two_mode_cross_validation import (
    apply_cross_validation_gate,
    panel_sha256,
    rules_sha256,
)
from src.two_mode_forward import (
    RegisteredForwardPredictor,
    fidelity_from_rules,
)
from src.two_mode_joint_fit import (
    fit_registered_model,
    robust_train_scales,
    score_registered_parameters,
)
from src.two_mode_model_selection import decide_two_mode_verdict
from src.two_mode_models import MODEL_NAMES
from src.two_mode_observables import (
    build_joint_observable_panel,
    subset_joint_observable_panel,
)

TARGET_IDS = {
    "amp_mu002_up",
    "amp_mu002_down",
    "amp_mu005_up",
    "amp_mu005_down",
    "amp_mu010_up",
    "amp_mu010_down",
    "amp_mu020_up",
    "amp_mu020_down",
    "response_local_pulse_pos",
    "response_local_pulse_neg",
    "equilibrium_m0",
}
ANALYSIS_SOURCE_PATHS = (
    "configs/two_mode_fcs_decision_rules_20260730.json",
    "scripts/run_two_mode_comparison.py",
    "scripts/run_two_mode_cross_validation.py",
    "src/fcs_time_series.py",
    "src/scalar_nlfh.py",
    "src/two_mode_forward.py",
    "src/two_mode_cross_validation.py",
    "src/two_mode_joint_fit.py",
    "src/two_mode_model_selection.py",
    "src/two_mode_models.py",
    "src/two_mode_nlfh.py",
    "src/two_mode_observables.py",
)


def _write_report(outdir: Path, summary: Mapping[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    temporary = outdir / "summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(outdir / "summary.json")
    lines = [
        "# Two-mode/FCS joint audit",
        "",
        f"**Status:** `{summary['status']}`",
        "",
        str(summary["explanation"]),
        "",
        (
            "This audit is fail-closed: absent observables are not reconstructed "
            "from magnetization profiles, and no model parameter is reported "
            "before the registered data and numerical gates pass."
        ),
    ]
    missing = list(summary.get("missing_observables", []))
    if missing:
        lines.extend(["", "## Exact missing inputs", ""])
        lines.extend(f"- {item}" for item in missing)
    (outdir / "REPORT.md").write_text("\n".join(lines) + "\n")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return dict(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return None


def _source_path_by_id(base_manifest: Mapping[str, Any]) -> dict[str, Path]:
    return {
        str(job["job_id"]): Path(str(job["output_path"]))
        for job in base_manifest.get("jobs", [])
    }


def _required_observable_names(job: Mapping[str, Any]) -> tuple[str, ...]:
    names = ["dataset"]
    observables = set(job.get("observables", []))
    if "local_spin_current" in observables:
        names.append("local_spin_current")
    if "czz" in observables:
        names.append("czz")
    if "fcs_logZ" in observables:
        names.append("fcs_logZ")
    return tuple(names)


def _execute_dataset_path(
    job: Mapping[str, Any],
    *,
    data_root: Path | None,
) -> Path:
    """Resolve a frozen local path or an explicit cluster data root."""

    if data_root is None:
        return Path(str(job["output_path"]))
    return (
        Path(data_root)
        / str(job["stage"])
        / f"{job['job_id']}.npz"
    )


def audit_available_inputs(
    *,
    manifest_path: Path,
    base_manifest_path: Path,
    rules_path: Path,
    solver_budget_path: Path,
    reuse_attestations_path: Path,
    phase: str,
    selection_record_path: Path | None,
    data_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate all inputs reachable before the expensive registered fit."""

    manifest = _load_json(manifest_path)
    rules = _load_json(rules_path)
    solver_budget = _load_json(solver_budget_path)
    base_manifest = _load_json(base_manifest_path)
    reuse = _load_json(reuse_attestations_path) or {}
    hashes = {
        str(path): sha256_file(path)
        for path in (
            manifest_path,
            base_manifest_path,
            rules_path,
            solver_budget_path,
        )
        if path.is_file()
    }
    if manifest is None or rules is None or base_manifest is None:
        return (
            {
                "status": "insufficient_observables",
                "explanation": "The production-v2 manifest or frozen rules are unavailable.",
                "tested": False,
                "missing_observables": ["production-v2 manifest/rules"],
            },
            {},
        )
    if solver_budget is None or solver_budget.get("status") != "pass":
        return (
            {
                "status": "solver_unresolved",
                "explanation": "The independent stochastic solver-budget gate is not pass.",
                "tested": False,
            },
            {},
        )
    if phase not in {"validation", "blind"}:
        raise ValueError("phase must be validation or blind")
    if phase == "blind":
        selection = (
            _load_json(selection_record_path)
            if selection_record_path is not None
            else None
        )
        if (
            selection is None
            or selection.get("status")
            not in {
                "independent_two_burgers_supported",
                "coupled_two_mode_supported",
            }
            or not selection.get("analysis_sha256")
        ):
            return (
                {
                    "status": "insufficient_observables",
                    "explanation": (
                        "Blind evaluation requires a frozen signed validation "
                        "selection and cannot refit the model family."
                    ),
                    "tested": False,
                    "missing_observables": [
                        "signed validation-selection record"
                    ],
                },
                {},
            )

    stage = "production_a" if phase == "validation" else "production_b"
    rows = [
        dict(job)
        for job in manifest["jobs"]
        if job["stage"] == stage and job["condition_id"] in TARGET_IDS
    ]
    expected = len(TARGET_IDS)
    if len(rows) != expected:
        return (
            {
                "status": "insufficient_observables",
                "explanation": "The production-v2 target row set is incomplete.",
                "tested": False,
                "missing_observables": [
                    f"{stage}: expected {expected} target rows, found {len(rows)}"
                ],
            },
            {},
        )
    source_paths = _source_path_by_id(base_manifest)
    missing: list[str] = []
    datasets: dict[str, Any] = {}
    fcs_diagnostics: dict[str, Any] = {}
    for job in rows:
        job_id = str(job["job_id"])
        condition_id = str(job["condition_id"])
        if job.get("execution_mode") == "reuse":
            attestation = reuse.get(job_id)
            if not isinstance(attestation, Mapping) or attestation.get("status") != "accepted":
                missing.append(f"{job_id}: reuse_attestation")
                continue
            source_id = str(job["reuse_from_job_id"])
            path = Path(str(attestation.get("dataset_path", source_paths.get(source_id, ""))))
        else:
            path = _execute_dataset_path(job, data_root=data_root)
        if not path.is_file():
            missing.append(f"{job_id}: dataset")
            continue
        try:
            dataset = load_research_dataset(path)
        except (EOFError, KeyError, OSError, ValueError) as error:
            missing.append(f"{job_id}: invalid_dataset:{type(error).__name__}")
            continue
        required = _required_observable_names(job)
        if "local_spin_current" in required and dataset.current is None:
            missing.append(f"{job_id}: local_spin_current")
        if "czz" in required and dataset.czz is None:
            missing.append(f"{job_id}: czz")
        if "fcs_logZ" in required:
            if dataset.fcs_gamma is None or dataset.fcs_logZ is None:
                missing.append(f"{job_id}: fcs_logZ")
            else:
                try:
                    validated = validate_fcs_time_series(
                        dataset.t,
                        dataset.fcs_gamma,
                        dataset.fcs_logZ,
                        normalization_tol=1e-10,
                        conjugacy_tol=1e-10,
                        cumulant_stability_tol=float(
                            rules["thresholds"]["fcs_cumulant_stability_max"]
                        ),
                    )
                    fcs_diagnostics[condition_id] = validated.diagnostics
                except ValueError as error:
                    missing.append(f"{job_id}: fcs_validation:{error}")
        datasets[condition_id] = dataset
    if missing:
        return (
            {
                "status": "insufficient_observables",
                "explanation": (
                    "The preregistered profile/current/response/FCS panel is "
                    "not complete, so no model comparison was run."
                ),
                "tested": False,
                "missing_observables": sorted(missing),
                "input_hashes": hashes,
            },
            {},
        )
    try:
        panel = build_joint_observable_panel(
            datasets,
            pulse_amplitude=0.02,
            spatial_window=(-128.0, 128.0),
        )
    except ValueError as error:
        return (
            {
                "status": "fcs_validation_failed",
                "explanation": f"Joint panel validation failed: {error}",
                "tested": False,
                "input_hashes": hashes,
            },
            {},
        )
    return (
        {
            "status": "observables_ready",
            "explanation": (
                "All registered data inputs pass structural validation; the "
                "expensive common-random-number fit may now run under the "
                "frozen rules."
            ),
            "tested": False,
            "input_hashes": hashes,
            "fcs_diagnostics": fcs_diagnostics,
            "panel_diagnostics": panel.diagnostics,
        },
        {"panel": panel, "datasets": datasets, "rules": rules},
    )


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def analysis_source_closure() -> dict[str, Any]:
    files = {
        relative: sha256_file(ROOT / relative)
        for relative in ANALYSIS_SOURCE_PATHS
    }
    return {
        "files": files,
        "closure_sha256": hashlib.sha256(
            "\n".join(
                f"{relative}:{files[relative]}"
                for relative in sorted(files)
            ).encode()
        ).hexdigest(),
    }


def accepted_convergence_floor(
    convergence: Mapping[str, Any] | None,
) -> float:
    """Return the frozen maximum numerical floor or fail closed."""

    if not convergence:
        raise ValueError("accepted convergence audit is missing")
    accepted = (
        convergence.get("status") == "accepted"
        or convergence.get("accepted") is True
    )
    records = list(convergence.get("records", []))
    if not accepted or not records or not all(
        record.get("accepted") is True for record in records
    ):
        raise ValueError("convergence audit is not accepted")
    floors = [float(record["numerical_floor"]) for record in records]
    if any(not np.isfinite(value) or value <= 0 for value in floors):
        raise ValueError("convergence audit has an invalid numerical floor")
    return max(floors)


def solver_budget_error(
    rules: Mapping[str, Any],
    solver_budget: Mapping[str, Any],
) -> str | None:
    """Return why the frozen forward budget is stale, or ``None``."""

    if solver_budget.get("status") != "pass":
        return "The frozen solver budget is not pass."
    source_hashes = dict(solver_budget.get("source_sha256", {}))
    stale_sources = [
        relative
        for relative, expected in source_hashes.items()
        if not (ROOT / relative).is_file()
        or sha256_file(ROOT / relative) != str(expected)
    ]
    budget_config = (
        ROOT / "configs" / "two_mode_solver_budget_20260730.json"
    )
    if source_hashes and (
        stale_sources
        or not budget_config.is_file()
        or sha256_file(budget_config)
        != str(solver_budget.get("config_sha256", ""))
    ):
        return (
            "The solver-budget source/config hashes are stale: "
            + ", ".join(stale_sources or ["budget config"])
        )
    forward = rules["forward_model"]
    if (
        int(forward["screening_ensemble"])
        != int(solver_budget["screening_ensemble"])
        or int(forward["final_ensemble"])
        != int(solver_budget["final_ensemble"])
    ):
        return (
            "Forward-model ensemble counts differ from the independently "
            "frozen solver budget."
        )
    refinement = dict(solver_budget.get("forward_refinement", {}))
    levels = dict(refinement.get("levels", {}))
    registered_levels = {
        "screening": {
            "spatial_stride": int(forward["screening_spatial_stride"]),
            "dt_internal": float(forward["screening_dt_internal"]),
        },
        "final": {
            "spatial_stride": int(forward["final_spatial_stride"]),
            "dt_internal": float(forward["final_dt_internal"]),
        },
    }
    if refinement and (
        refinement.get("status") != "pass"
        or any(
            dict(levels.get(name, {})) != expected
            for name, expected in registered_levels.items()
        )
    ):
        return (
            "Registered screening/final grids differ from the passing "
            "deterministic refinement audit."
        )
    return None


def run_registered_validation(
    *,
    panel,
    rules: Mapping[str, Any],
    solver_budget: Mapping[str, Any],
    screening_predictor=None,
    final_predictor=None,
    quantum_numerical_floor: float | None = None,
    cross_validation_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fit at screening fidelity and select using final-fidelity predictions."""

    budget_error = solver_budget_error(rules, solver_budget)
    if budget_error is not None:
        return {
            "status": "solver_unresolved",
            "tested": False,
            "explanation": budget_error,
        }
    cross_validation_required = bool(
        rules.get("cross_validation", {}).get("required", False)
    )
    if cross_validation_required and (
        cross_validation_summary is None
        or cross_validation_summary.get("status") != "complete"
        or cross_validation_summary.get("panel_sha256")
        != panel_sha256(panel)
        or cross_validation_summary.get("rules_sha256")
        != rules_sha256(rules)
        or cross_validation_summary.get(
            "parameters_refit_on_held_out_data"
        )
        is not False
        or cross_validation_summary.get("analysis_source", {}).get(
            "closure_sha256"
        )
        != analysis_source_closure()["closure_sha256"]
    ):
        return {
            "status": "simulation_unresolved",
            "tested": False,
            "explanation": (
                "The registered leave-one-orientation/condition-out audit is "
                "missing, incomplete, or stale."
            ),
        }
    screening_predictor = screening_predictor or RegisteredForwardPredictor(
        fidelity_from_rules(rules, final=False)
    )
    final_predictor = final_predictor or RegisteredForwardPredictor(
        fidelity_from_rules(rules, final=True)
    )
    fit_condition_ids = {
        condition_id
        for condition_id, metadata in panel.metadata.items()
        if str(metadata.get("role", "")) != "primary_amplitude"
        or float(metadata.get("mu", float("inf"))) <= 0.05 + 1e-14
    }
    # Manufactured/unit-test panels may not carry production metadata.
    if not fit_condition_ids:
        fit_condition_ids = set(panel.profile)
    fit_panel = subset_joint_observable_panel(panel, fit_condition_ids)
    effective_numerical_floor = max(
        float(rules["thresholds"]["scale_numerical_floor"]),
        0.0
        if quantum_numerical_floor is None
        else float(quantum_numerical_floor),
    )
    full_scales = robust_train_scales(
        panel,
        numerical_floor=effective_numerical_floor,
    )
    fits: dict[str, Any] = {}
    for model in MODEL_NAMES:
        fit = fit_registered_model(
            model,
            fit_panel,
            noise_panel=None,
            rules=rules,
            predictor=screening_predictor,
            numerical_floor=quantum_numerical_floor,
            scales_override=full_scales,
        )
        if fit.get("status") == "fit_complete":
            fit["screening"] = {
                "train": fit.pop("train"),
                "validation": fit.pop("validation"),
                "validation_rss": fit.pop("validation_rss"),
                "validation_n": fit.pop("validation_n"),
                "validation_loss_by_time": fit.pop(
                    "validation_loss_by_time"
                ),
            }
            fit.update(
                score_registered_parameters(
                    model,
                    np.asarray(fit["free"], dtype=float),
                    panel,
                    noise_panel=None,
                    predictor=final_predictor,
                    scales=fit["scales"],
                    phase="train",
                )
            )
            fit.update(
                score_registered_parameters(
                    model,
                    np.asarray(fit["free"], dtype=float),
                    panel,
                    noise_panel=None,
                    predictor=final_predictor,
                    scales=fit["scales"],
                    phase="validation",
                )
            )
            try:
                fit.update(
                    score_registered_parameters(
                        model,
                        np.asarray(fit["free"], dtype=float),
                        panel,
                        noise_panel=None,
                        predictor=final_predictor,
                        scales=fit["scales"],
                        phase="stress_validation",
                    )
                )
            except ValueError as error:
                fit["stress_validation"] = {
                    "status": "not_available",
                    "reason": str(error),
                }
        fits[model] = fit
    threshold = (
        float(rules["thresholds"]["symmetry_numerical_floor_multiplier"])
        * effective_numerical_floor
    )
    symmetry_defect = max(
        float(
            panel.diagnostics.get(
                "pulse_spin_flip_magnetization_max_abs", float("inf")
            )
        ),
        float(
            panel.diagnostics.get(
                "pulse_even_current_max_abs", float("inf")
            )
        ),
    )
    diagnostics = {
        "observables_ready": True,
        "fcs_status": "pass",
        "solver_status": "pass",
        "symmetry_pass": symmetry_defect <= threshold,
        "symmetry_defect": symmetry_defect,
        "symmetry_threshold": threshold,
        "validation_t": panel.t[panel.masks["validation"]],
    }
    verdict = decide_two_mode_verdict(
        fits,
        diagnostics,
        rules,
        phase="validation",
    )
    if cross_validation_required:
        verdict = apply_cross_validation_gate(
            verdict,
            cross_validation_summary or {},
        )
    source_closure = analysis_source_closure()
    frozen = {
        "fits": fits,
        "verdict": verdict,
        "rules": rules,
        "analysis_source": source_closure,
        "forward_fidelity": {
            "screening": dict(rules["forward_model"]),
            "solver_budget_sha256": solver_budget.get("config_sha256"),
        },
        "cross_validation": (
            dict(cross_validation_summary or {})
            if cross_validation_required
            else {"required": False}
        ),
    }
    return {
        "status": verdict["status"],
        "tested": bool(verdict.get("tested", False)),
        "explanation": (
            "Registered scalar/independent/coupled models were fitted on "
            "50-150, checked by registered condition/orientation refits, and "
            "selected only from final-fidelity 150-200 predictions."
        ),
        "fits": fits,
        "verdict": verdict,
        "analysis_sha256": _canonical_sha256(frozen),
        "parameters_refit_on_blind_data": False,
        "quantum_numerical_floor": effective_numerical_floor,
        "analysis_source": source_closure,
        "cross_validation": (
            dict(cross_validation_summary or {})
            if cross_validation_required
            else {"required": False}
        ),
    }


def run_registered_blind(
    *,
    panel,
    rules: Mapping[str, Any],
    solver_budget: Mapping[str, Any],
    selection: Mapping[str, Any],
    final_predictor=None,
) -> dict[str, Any]:
    """Score the frozen validation families on production B without refitting."""

    selected_status = str(selection.get("status", ""))
    if selected_status not in {
        "independent_two_burgers_supported",
        "coupled_two_mode_supported",
    }:
        return {
            "status": "insufficient_observables",
            "tested": False,
            "explanation": "No supported validation family was frozen for blind scoring.",
        }
    current_source = analysis_source_closure()
    if (
        selection.get("analysis_source", {}).get("closure_sha256")
        != current_source["closure_sha256"]
    ):
        return {
            "status": "solver_unresolved",
            "tested": False,
            "explanation": (
                "Analysis source changed after validation selection; blind "
                "data were not scored."
            ),
        }
    final_predictor = final_predictor or RegisteredForwardPredictor(
        fidelity_from_rules(rules, final=True)
    )
    frozen_fits = selection.get("fits", {})
    fits: dict[str, Any] = {}
    for model in (
        "scalar_surrogate",
        "independent_two_burgers",
        "coupled_two_mode",
    ):
        original = dict(frozen_fits.get(model, {}))
        if original.get("status") != "fit_complete":
            fits[model] = {"status": "fit_failed"}
            continue
        scored = score_registered_parameters(
            model,
            np.asarray(original["free"], dtype=float),
            panel,
            noise_panel=None,
            predictor=final_predictor,
            scales=original["scales"],
            phase="blind",
        )
        try:
            stress_scored = score_registered_parameters(
                model,
                np.asarray(original["free"], dtype=float),
                panel,
                noise_panel=None,
                predictor=final_predictor,
                scales=original["scales"],
                phase="stress_blind",
            )
        except ValueError as error:
            stress_scored = {
                "stress_blind": {
                    "status": "not_available",
                    "reason": str(error),
                }
            }
        fits[model] = {
            "status": "fit_complete",
            "free_parameter_names": original["free_parameter_names"],
            "free": original["free"],
            "parameters": original["parameters"],
            "scales": original["scales"],
            **scored,
            **stress_scored,
        }
    effective_numerical_floor = max(
        float(rules["thresholds"]["scale_numerical_floor"]),
        float(selection.get("quantum_numerical_floor", 0.0)),
    )
    threshold = (
        float(rules["thresholds"]["symmetry_numerical_floor_multiplier"])
        * effective_numerical_floor
    )
    diagnostics = {
        "observables_ready": True,
        "fcs_status": "pass",
        "solver_status": (
            "pass" if solver_budget.get("status") == "pass" else "blocked"
        ),
        "symmetry_pass": float(
            panel.diagnostics.get(
                "pulse_spin_flip_magnetization_max_abs", float("inf")
            )
        )
        <= threshold,
        "blind_t": panel.t[panel.masks["blind"]],
        "frozen_validation_selection": selected_status,
    }
    verdict = decide_two_mode_verdict(
        fits,
        diagnostics,
        rules,
        phase="blind",
    )
    return {
        "status": verdict["status"],
        "tested": bool(verdict.get("tested", False)),
        "explanation": (
            "Frozen validation parameters were scored once on 200-400; no "
            "family or parameter was refitted on blind data."
        ),
        "fits": fits,
        "verdict": verdict,
        "validation_analysis_sha256": selection["analysis_sha256"],
        "parameters_refit_on_blind_data": False,
        "analysis_source": current_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "production_manifest_v2.json",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "configs" / "two_mode_fcs_decision_rules_20260730.json",
    )
    parser.add_argument(
        "--solver-budget",
        type=Path,
        default=ROOT / "results_research_program" / "two_mode" / "solver_budget.json",
    )
    parser.add_argument(
        "--reuse-attestations",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "production_v2_reuse_attestations.json",
    )
    parser.add_argument(
        "--convergence-audit",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "convergence"
        / "summary.json",
    )
    parser.add_argument(
        "--cross-validation-summary",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "two_mode"
        / "cross_validation"
        / "summary.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help=(
            "Cluster root containing production_a/ and production_b/; "
            "execute rows use frozen manifest paths when omitted."
        ),
    )
    parser.add_argument("--phase", choices=("validation", "blind"), default="validation")
    parser.add_argument("--selection-record", type=Path)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results_research_program" / "two_mode",
    )
    args = parser.parse_args()
    summary, context = audit_available_inputs(
        manifest_path=args.manifest,
        base_manifest_path=args.base_manifest,
        rules_path=args.rules,
        solver_budget_path=args.solver_budget,
        reuse_attestations_path=args.reuse_attestations,
        phase=args.phase,
        selection_record_path=args.selection_record,
        data_root=args.data_root,
    )
    if summary["status"] == "observables_ready":
        solver_budget = _load_json(args.solver_budget)
        if args.phase == "validation":
            try:
                numerical_floor = accepted_convergence_floor(
                    _load_json(args.convergence_audit)
                )
            except ValueError as error:
                summary = {
                    **summary,
                    "status": "simulation_unresolved",
                    "tested": False,
                    "explanation": str(error),
                }
                numerical_floor = None
            if summary["status"] != "observables_ready":
                summary = {
                    "schema_version": 2,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "phase": args.phase,
                    **summary,
                }
                _write_report(args.outdir, summary)
                print(
                    json.dumps(
                        {
                            "status": summary["status"],
                            "missing": len(
                                summary.get("missing_observables", [])
                            ),
                        },
                        sort_keys=True,
                    )
                )
                return
            summary = {
                **summary,
                **run_registered_validation(
                    panel=context["panel"],
                    rules=context["rules"],
                    solver_budget=solver_budget or {},
                    quantum_numerical_floor=numerical_floor,
                    cross_validation_summary=_load_json(
                        args.cross_validation_summary
                    ),
                ),
            }
        else:
            selection = _load_json(args.selection_record)
            summary = {
                **summary,
                **run_registered_blind(
                    panel=context["panel"],
                    rules=context["rules"],
                    solver_budget=solver_budget or {},
                    selection=selection or {},
                ),
            }
    summary = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": args.phase,
        **summary,
    }
    _write_report(args.outdir, summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "missing": len(summary.get("missing_observables", [])),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
