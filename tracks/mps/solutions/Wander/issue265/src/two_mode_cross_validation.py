"""Registered condition and orientation cross-validation for two-mode models."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .two_mode_joint_fit import (
    fit_registered_model,
    observed_block_map,
    robust_train_scales,
    score_registered_parameters,
)
from .two_mode_models import ModelName
from .two_mode_observables import (
    JointObservablePanel,
    subset_joint_observable_panel,
)

Array = np.ndarray


@dataclass(frozen=True)
class CrossValidationFold:
    fold_id: str
    kind: str
    held_out_conditions: tuple[str, ...]
    training_conditions: tuple[str, ...]


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def rules_sha256(rules: Mapping[str, Any]) -> str:
    """Hash the complete registered rule payload canonically."""

    return _canonical_sha256(rules)


def panel_sha256(panel: JointObservablePanel) -> str:
    """Hash every observed number and registered condition descriptor."""

    digest = hashlib.sha256()
    for name, values in (
        ("t", panel.t),
        ("x", panel.x),
        *sorted(observed_block_map(panel).items()),
    ):
        array = np.ascontiguousarray(values)
        digest.update(str(name).encode())
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.view(np.uint8))
    digest.update(
        json.dumps(
            panel.metadata,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    )
    return digest.hexdigest()


def _is_core_condition(metadata: Mapping[str, object]) -> bool:
    if str(metadata.get("role", "")) != "primary_amplitude":
        return True
    return float(metadata.get("mu", float("inf"))) <= 0.05 + 1e-14


def registered_cross_validation_folds(
    panel: JointObservablePanel,
    controls: Mapping[str, Any] | None = None,
) -> tuple[CrossValidationFold, ...]:
    """Return the frozen two orientation and leave-one-condition folds."""

    controls = controls or {
        "evaluation_phase": "validation",
        "orientation_values": [1, -1],
        "condition_folds": "all_core_conditions",
    }
    if controls.get("evaluation_phase") != "validation":
        raise ValueError(
            "registered cross-validation must score the validation phase"
        )
    orientations = tuple(map(int, controls["orientation_values"]))
    if set(orientations) != {-1, 1} or len(orientations) != 2:
        raise ValueError(
            "registered orientation folds must contain exactly -1 and +1"
        )
    if controls.get("condition_folds") != "all_core_conditions":
        raise ValueError(
            "registered condition folds must cover all core conditions"
        )
    core = tuple(
        sorted(
            condition_id
            for condition_id in panel.profile
            if _is_core_condition(panel.metadata.get(condition_id, {}))
        )
    )
    if len(core) < 3:
        raise ValueError(
            "registered cross-validation requires at least three core conditions"
        )
    folds: list[CrossValidationFold] = []
    for orientation in orientations:
        label = "up" if orientation == 1 else "down"
        held = tuple(
            condition_id
            for condition_id in core
            if str(
                panel.metadata.get(condition_id, {}).get("role", "")
            )
            != "two_mode_equilibrium"
            and int(
                panel.metadata.get(condition_id, {}).get("orientation", 0)
            )
            == orientation
        )
        training = tuple(
            condition_id for condition_id in core if condition_id not in held
        )
        if not held or not training:
            raise ValueError(
                f"orientation {label} has an empty training or holdout set"
            )
        folds.append(
            CrossValidationFold(
                fold_id=f"leave_orientation_{label}_out",
                kind="orientation",
                held_out_conditions=held,
                training_conditions=training,
            )
        )
    folds.extend(
        CrossValidationFold(
            fold_id=f"leave_condition_{condition_id}_out",
            kind="condition",
            held_out_conditions=(condition_id,),
            training_conditions=tuple(
                candidate for candidate in core if candidate != condition_id
            ),
        )
        for condition_id in core
    )
    return tuple(folds)


def inherited_holdout_scales(
    training_panel: JointObservablePanel,
    holdout_panel: JointObservablePanel,
    *,
    numerical_floor: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Build holdout scales solely from all-but-held-out training blocks."""

    training = robust_train_scales(
        training_panel,
        numerical_floor=numerical_floor,
    )
    holdout: dict[str, float] = {}
    for block_name in observed_block_map(holdout_panel):
        prefix = block_name.split(":", 1)[0]
        references = [
            value
            for name, value in training.items()
            if name.split(":", 1)[0] == prefix
        ]
        if not references:
            raise ValueError(
                f"no training scale is available for held-out block {block_name}"
            )
        holdout[block_name] = max(references)
    return training, holdout


def run_cross_validation_shard(
    *,
    model: ModelName,
    fold: CrossValidationFold,
    panel: JointObservablePanel,
    rules: Mapping[str, Any],
    screening_predictor: Any,
    final_predictor: Any,
    quantum_numerical_floor: float,
) -> dict[str, Any]:
    """Refit one model without one registered fold and score it once."""

    effective_floor = max(
        float(rules["thresholds"]["scale_numerical_floor"]),
        float(quantum_numerical_floor),
    )
    training_panel = subset_joint_observable_panel(
        panel,
        set(fold.training_conditions),
    )
    holdout_panel = subset_joint_observable_panel(
        panel,
        set(fold.held_out_conditions),
    )
    training_scales, holdout_scales = inherited_holdout_scales(
        training_panel,
        holdout_panel,
        numerical_floor=effective_floor,
    )
    fitted = fit_registered_model(
        model,
        training_panel,
        noise_panel=None,
        rules=rules,
        predictor=screening_predictor,
        numerical_floor=effective_floor,
        scales_override=training_scales,
    )
    base = {
        "schema_version": 1,
        "model": model,
        "fold": asdict(fold),
        "panel_sha256": panel_sha256(panel),
        "rules_sha256": rules_sha256(rules),
        "quantum_numerical_floor": effective_floor,
        "training_scales_sha256": _canonical_sha256(training_scales),
        "holdout_scales_sha256": _canonical_sha256(holdout_scales),
        "parameters_refit_on_held_out_data": False,
    }
    if fitted.get("status") != "fit_complete":
        return {
            **base,
            "status": "fit_failed",
            "fit": fitted,
        }
    heldout = score_registered_parameters(
        model,
        np.asarray(fitted["free"], dtype=float),
        holdout_panel,
        noise_panel=None,
        predictor=final_predictor,
        scales=holdout_scales,
        phase="validation",
    )
    return {
        **base,
        "status": "fit_complete",
        "free_parameter_names": fitted["free_parameter_names"],
        "free": fitted["free"],
        "parameters": fitted["parameters"],
        "optimizer": {
            "starts": fitted["starts"],
            "successful_starts": fitted["successful_starts"],
            "best_objective_relative_spread": fitted[
                "best_objective_relative_spread"
            ],
            "training": fitted["train"],
        },
        "heldout": heldout,
    }


def _fraction(values: Sequence[bool]) -> float:
    if not values:
        raise ValueError("cross-validation metric group is empty")
    return float(np.mean(np.asarray(values, dtype=float)))


def _positive_finite(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(numeric) and numeric > 0)


def aggregate_cross_validation(
    *,
    panel: JointObservablePanel,
    rules: Mapping[str, Any],
    shards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate every shard and freeze generalization evidence by model."""

    controls = rules["cross_validation"]
    models = tuple(map(str, controls["models"]))
    folds = registered_cross_validation_folds(panel, controls)
    expected = {(model, fold.fold_id) for model in models for fold in folds}
    registered_shards = int(controls["expected_shards"])
    if len(expected) != registered_shards:
        raise ValueError(
            "registered cross-validation shard count does not match the "
            f"frozen rule: derived {len(expected)}, expected "
            f"{registered_shards}"
        )
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    duplicate: list[str] = []
    for shard in shards:
        key = (
            str(shard.get("model", "")),
            str(shard.get("fold", {}).get("fold_id", "")),
        )
        if key in indexed:
            duplicate.append(":".join(key))
        indexed[key] = shard
    missing = sorted(":".join(key) for key in expected - set(indexed))
    extra = sorted(":".join(key) for key in set(indexed) - expected)
    target_panel_hash = panel_sha256(panel)
    target_rules_hash = rules_sha256(rules)
    invalid = sorted(
        ":".join(key)
        for key, shard in indexed.items()
        if key in expected
        and (
            shard.get("status") != "fit_complete"
            or shard.get("panel_sha256") != target_panel_hash
            or shard.get("rules_sha256") != target_rules_hash
            or shard.get("parameters_refit_on_held_out_data") is not False
            or not shard.get("training_scales_sha256")
            or not shard.get("holdout_scales_sha256")
            or not _positive_finite(
                shard.get("quantum_numerical_floor")
            )
        )
    )
    invalid_keys = {
        tuple(value.split(":", 1))
        for value in invalid
    }
    inconsistent_scales = sorted(
        fold.fold_id
        for fold in folds
        if len(
            {
                (
                    indexed[(model, fold.fold_id)][
                        "training_scales_sha256"
                    ],
                    indexed[(model, fold.fold_id)][
                        "holdout_scales_sha256"
                    ],
                )
                for model in models
                if (model, fold.fold_id) in indexed
                and (model, fold.fold_id) not in invalid_keys
            }
        )
        > 1
    )
    if missing or extra or duplicate or invalid or inconsistent_scales:
        return {
            "schema_version": 1,
            "status": "incomplete",
            "panel_sha256": target_panel_hash,
            "rules_sha256": target_rules_hash,
            "expected_shards": len(expected),
            "received_shards": len(shards),
            "missing": missing,
            "extra": extra,
            "duplicate": sorted(duplicate),
            "invalid": invalid,
            "inconsistent_scales": inconsistent_scales,
        }

    by_model: dict[str, Any] = {}
    for model in models:
        records = []
        for fold in folds:
            shard = indexed[(model, fold.fold_id)]
            score = dict(shard["heldout"]["validation"])
            records.append(
                {
                    "fold_id": fold.fold_id,
                    "kind": fold.kind,
                    "held_out_conditions": list(fold.held_out_conditions),
                    "loss": float(score["loss"]),
                    "normalized_rmse": float(score["normalized_rmse"]),
                    "rss": float(shard["heldout"]["validation_rss"]),
                    "n": int(shard["heldout"]["validation_n"]),
                }
            )
        by_model[model] = {
            "folds": records,
            "orientation_mean_loss": float(
                np.mean(
                    [
                        record["loss"]
                        for record in records
                        if record["kind"] == "orientation"
                    ]
                )
            ),
            "condition_mean_loss": float(
                np.mean(
                    [
                        record["loss"]
                        for record in records
                        if record["kind"] == "condition"
                    ]
                )
            ),
        }

    def comparison(candidate: str, baseline: str) -> dict[str, Any]:
        baseline_by_fold = {
            record["fold_id"]: record for record in by_model[baseline]["folds"]
        }
        rows = []
        rmse_max = float(controls["normalized_rmse_max"])
        improvement_min = float(controls["improvement_min"])
        for candidate_record in by_model[candidate]["folds"]:
            base = baseline_by_fold[candidate_record["fold_id"]]
            improvement = 1.0 - candidate_record["loss"] / max(
                base["loss"], 1e-300
            )
            rows.append(
                {
                    "fold_id": candidate_record["fold_id"],
                    "kind": candidate_record["kind"],
                    "relative_improvement": float(improvement),
                    "candidate_normalized_rmse": candidate_record[
                        "normalized_rmse"
                    ],
                    "passes": bool(
                        improvement >= improvement_min
                        and candidate_record["normalized_rmse"] <= rmse_max
                    ),
                }
            )
        orientation_rows = [
            row for row in rows if row["kind"] == "orientation"
        ]
        condition_rows = [
            row for row in rows if row["kind"] == "condition"
        ]
        orientation_fraction = _fraction(
            [row["passes"] for row in orientation_rows]
        )
        condition_fraction = _fraction(
            [row["passes"] for row in condition_rows]
        )
        passed = (
            orientation_fraction
            >= float(controls["orientation_pass_fraction_min"])
            and condition_fraction
            >= float(controls["condition_pass_fraction_min"])
        )
        return {
            "candidate": candidate,
            "baseline": baseline,
            "folds": rows,
            "orientation_pass_fraction": orientation_fraction,
            "condition_pass_fraction": condition_fraction,
            "pass": bool(passed),
        }

    comparisons = {
        "independent_vs_scalar": comparison(
            "independent_two_burgers", "scalar_surrogate"
        ),
        "coupled_vs_scalar": comparison(
            "coupled_two_mode", "scalar_surrogate"
        ),
        "coupled_vs_independent": comparison(
            "coupled_two_mode", "independent_two_burgers"
        ),
    }
    return {
        "schema_version": 1,
        "status": "complete",
        "panel_sha256": target_panel_hash,
        "rules_sha256": target_rules_hash,
        "expected_shards": len(expected),
        "received_shards": len(shards),
        "folds": [asdict(fold) for fold in folds],
        "models": by_model,
        "comparisons": comparisons,
        "parameters_refit_on_held_out_data": False,
    }


def apply_cross_validation_gate(
    verdict: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Require condition/orientation generalization for supported families."""

    result = dict(verdict)
    result["cross_validation"] = dict(summary)
    status = str(result.get("status", ""))
    if status not in {
        "independent_two_burgers_supported",
        "coupled_two_mode_supported",
    }:
        return result
    comparisons = summary.get("comparisons", {})
    independent_pass = bool(
        comparisons.get("independent_vs_scalar", {}).get("pass")
    )
    coupled_pass = bool(
        comparisons.get("coupled_vs_scalar", {}).get("pass")
    )
    coupled_increment_pass = bool(
        comparisons.get("coupled_vs_independent", {}).get("pass")
    )
    if status == "independent_two_burgers_supported" and not independent_pass:
        result.update(
            {
                "status": "memory_or_more_modes_required",
                "reason": (
                    "independent two-mode validation did not generalize across "
                    "the registered orientation/condition folds"
                ),
            }
        )
    elif status == "coupled_two_mode_supported" and not (
        coupled_pass and coupled_increment_pass
    ):
        if independent_pass and bool(
            result.get("evidence", {}).get("independent_pass")
        ):
            result.update(
                {
                    "status": "independent_two_burgers_supported",
                    "reason": (
                        "coupled terms failed registered cross-validation; "
                        "the independent family retained support"
                    ),
                }
            )
        else:
            result.update(
                {
                    "status": "memory_or_more_modes_required",
                    "reason": (
                        "the selected coupled model did not generalize across "
                        "the registered orientation/condition folds"
                    ),
                }
            )
    return result
