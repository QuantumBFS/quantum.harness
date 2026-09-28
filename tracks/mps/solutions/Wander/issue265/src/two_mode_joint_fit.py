"""Block-normalized joint loss and deterministic registered-model fitting."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.stats import qmc

from .two_mode_models import (
    MODEL_NAMES,
    PARAMETER_BOUNDS,
    ModelName,
    ModelParameters,
    free_parameter_names,
    parameters_for_model,
)
from .two_mode_observables import JointObservablePanel

Array = np.ndarray
Predictor = Callable[
    [ModelName, ModelParameters, JointObservablePanel, Any],
    Mapping[str, Array],
]
CORE_AMPLITUDE_MAX = 0.05
HOLDOUT_AMPLITUDE_MAX = 0.10


@dataclass(frozen=True)
class LossBlock:
    name: str
    observed: Array
    predicted: Array
    scale: Array
    mask: Array


def _expanded_mask(mask: Array, shape: tuple[int, ...]) -> Array:
    mask = np.asarray(mask, dtype=bool)
    if mask.shape == shape:
        return mask
    if mask.ndim == 1 and shape and mask.size == shape[0]:
        return np.broadcast_to(mask.reshape((-1,) + (1,) * (len(shape) - 1)), shape)
    raise ValueError("loss mask must match the array or its leading time axis")


def standardized_residual(block: LossBlock) -> Array:
    observed = np.asarray(block.observed)
    predicted = np.asarray(block.predicted)
    if observed.shape != predicted.shape:
        raise ValueError(f"shape mismatch in loss block {block.name}")
    if np.any(~np.isfinite(observed)) or np.any(~np.isfinite(predicted)):
        raise ValueError(f"non-finite values in loss block {block.name}")
    scale = np.asarray(block.scale, dtype=float)
    try:
        scale = np.broadcast_to(scale, observed.shape)
    except ValueError as error:
        raise ValueError(f"scale shape mismatch in loss block {block.name}") from error
    if np.any(~np.isfinite(scale)) or np.any(scale <= 0):
        raise ValueError(f"scale must be finite and positive in {block.name}")
    selected = _expanded_mask(block.mask, observed.shape)
    residual = (predicted - observed) / scale
    if np.iscomplexobj(residual):
        return np.concatenate([residual.real[selected], residual.imag[selected]])
    return np.asarray(residual[selected], dtype=float)


def joint_loss(blocks: Sequence[LossBlock]) -> dict[str, Any]:
    """Give every available condition/observable block equal total weight."""

    if not blocks:
        raise ValueError("joint loss requires at least one observable block")
    per_block: dict[str, float] = {}
    residuals: list[Array] = []
    for block in blocks:
        residual = standardized_residual(block)
        if residual.size == 0:
            continue
        per_block[block.name] = float(np.mean(residual**2))
        residuals.append(residual)
    if not per_block:
        raise ValueError("joint loss masks select no observations")
    return {
        "loss": float(np.mean(list(per_block.values()))),
        "normalized_rmse": float(np.sqrt(np.mean(list(per_block.values())))),
        "per_block": per_block,
        "residual_vector": np.concatenate(residuals),
    }


def observed_block_map(panel: JointObservablePanel) -> dict[str, Array]:
    """Return the registered observable blocks with stable public names."""

    result: dict[str, Array] = {}
    for prefix, values in (
        ("profile", panel.profile),
        ("current", panel.current),
        ("czz", panel.czz),
        ("response_cmm", panel.response_cmm),
        ("response_cjm", panel.response_cjm),
        ("fcs_logz", panel.fcs_logz),
    ):
        for key, array in values.items():
            result[f"{prefix}:{key}"] = np.asarray(array)
    return result


_observed_map = observed_block_map


def _registered_block_role(
    panel: JointObservablePanel,
    block_name: str,
) -> str:
    """Classify blocks without inspecting any observed numerical value."""

    prefix, condition_id = block_name.split(":", 1)
    if prefix.startswith("response_"):
        return "core"
    metadata = panel.metadata.get(condition_id)
    if not metadata:
        return "core"
    role = str(metadata.get("role", ""))
    if role != "primary_amplitude":
        return "core"
    mu = float(metadata.get("mu", float("inf")))
    if mu <= CORE_AMPLITUDE_MAX + 1e-14:
        return "core"
    if mu <= HOLDOUT_AMPLITUDE_MAX + 1e-14:
        return "amplitude_holdout"
    return "stress"


def _phase_policy(phase: str) -> tuple[str, frozenset[str]]:
    if phase == "train":
        return "train", frozenset({"core"})
    if phase == "validation":
        return "validation", frozenset({"core", "amplitude_holdout"})
    if phase == "blind":
        return "blind", frozenset({"core", "amplitude_holdout"})
    if phase == "stress_validation":
        return "validation", frozenset({"stress"})
    if phase == "stress_blind":
        return "blind", frozenset({"stress"})
    raise ValueError(f"unknown analysis phase {phase}")


def _robust_scale(values: Array, *, numerical_floor: float) -> float:
    selected = np.asarray(values)
    sample = (
        np.concatenate([selected.real.ravel(), selected.imag.ravel()])
        if np.iscomplexobj(selected)
        else selected.ravel()
    )
    median = float(np.median(sample))
    mad = 1.4826 * float(np.median(np.abs(sample - median)))
    return max(mad, float(numerical_floor))


def robust_train_scales(
    panel: JointObservablePanel,
    *,
    numerical_floor: float,
) -> dict[str, float]:
    """Estimate all normalization scales from the train window only."""

    if numerical_floor <= 0:
        raise ValueError("numerical_floor must be positive")
    train = np.asarray(panel.masks["train"], dtype=bool)
    scales: dict[str, float] = {}
    observed = _observed_map(panel)
    roles = {
        name: _registered_block_role(panel, name) for name in observed
    }
    for name, values in observed.items():
        if roles[name] == "core":
            scales[name] = _robust_scale(
                np.asarray(values)[train],
                numerical_floor=numerical_floor,
            )
    for name in observed:
        if name in scales:
            continue
        prefix = name.split(":", 1)[0]
        references = [
            scale
            for reference, scale in scales.items()
            if reference.split(":", 1)[0] == prefix
        ]
        if not references:
            raise ValueError(
                f"no core training scale is registered for held-out block {name}"
            )
        # No held-out numerical value enters its scale.  The conservative
        # maximum prevents a small core condition from overweighting a larger
        # amplitude holdout.
        scales[name] = max(references)
    return scales


def build_loss_blocks(
    panel: JointObservablePanel,
    predictions: Mapping[str, Array],
    *,
    phase: str,
    scales: Mapping[str, float],
) -> list[LossBlock]:
    mask_name, allowed_roles = _phase_policy(phase)
    observed = _observed_map(panel)
    if set(predictions) != set(observed):
        missing = sorted(set(observed) - set(predictions))
        extra = sorted(set(predictions) - set(observed))
        raise ValueError(f"prediction block mismatch; missing={missing}, extra={extra}")
    blocks = [
        LossBlock(
            name=name,
            observed=values,
            predicted=np.asarray(predictions[name]),
            scale=np.asarray(float(scales[name])),
            mask=np.asarray(panel.masks[mask_name]),
        )
        for name, values in observed.items()
        if _registered_block_role(panel, name) in allowed_roles
    ]
    if not blocks:
        raise ValueError(f"analysis phase {phase} has no registered blocks")
    return blocks


def loss_by_time(blocks: Sequence[LossBlock]) -> Array:
    """Return paired mean squared standardized error at each selected time."""

    if not blocks:
        raise ValueError("time loss requires blocks")
    leading = np.asarray(blocks[0].observed).shape[0]
    selected = np.asarray(blocks[0].mask, dtype=bool)
    if selected.shape != (leading,):
        raise ValueError("time-loss masks must be one-dimensional")
    contributions: list[Array] = []
    for block in blocks:
        observed = np.asarray(block.observed)
        predicted = np.asarray(block.predicted)
        if observed.shape[0] != leading or not np.array_equal(block.mask, selected):
            raise ValueError("all time-loss blocks must share time and mask")
        residual = (predicted - observed) / float(np.asarray(block.scale))
        axes = tuple(range(1, residual.ndim))
        squared = np.abs(residual) ** 2
        contributions.append(
            np.mean(squared, axis=axes) if axes else squared
        )
    return np.mean(np.stack(contributions), axis=0)[selected]


def _noise_hash(noise_panel: Any) -> str:
    if noise_panel is None:
        return "none"
    digest = hashlib.sha256()
    for name in ("initial_m", "initial_phi", "face_m", "face_phi"):
        if hasattr(noise_panel, name):
            array = np.ascontiguousarray(getattr(noise_panel, name))
            digest.update(name.encode())
            digest.update(str(array.shape).encode())
            digest.update(array.view(np.uint8))
    digest.update(str(getattr(noise_panel, "seed", "unknown")).encode())
    return digest.hexdigest()


def fit_registered_model(
    name: ModelName,
    panel: JointObservablePanel,
    *,
    noise_panel: Any,
    rules: Mapping[str, Any],
    predictor: Predictor,
    numerical_floor: float | None = None,
    scales_override: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Fit one registered model on train data and score held-out validation."""

    if name not in MODEL_NAMES:
        raise ValueError(f"unknown registered model {name}")
    names = free_parameter_names(name)
    bounds = [PARAMETER_BOUNDS[item] for item in names]
    optimization = rules["optimization"]
    multistarts = int(optimization["multistarts"])
    if multistarts < 2:
        raise ValueError("registered fit requires at least two starts")
    floor = max(
        float(rules["thresholds"]["scale_numerical_floor"]),
        0.0 if numerical_floor is None else float(numerical_floor),
    )
    scales = (
        robust_train_scales(panel, numerical_floor=floor)
        if scales_override is None
        else {str(key): float(value) for key, value in scales_override.items()}
    )
    missing_scales = set(_observed_map(panel)) - set(scales)
    if missing_scales:
        raise ValueError(
            "provided scales miss blocks: " + ", ".join(sorted(missing_scales))
        )
    sampler = qmc.LatinHypercube(
        d=len(names), seed=int(optimization["seed"])
    )
    starts = qmc.scale(
        sampler.random(multistarts),
        np.asarray([value[0] for value in bounds]),
        np.asarray([value[1] for value in bounds]),
    )
    records: list[dict[str, Any]] = []

    def objective(free: Array) -> float:
        try:
            params = parameters_for_model(name, free)
            predictions = predictor(name, params, panel, noise_panel)
            blocks = build_loss_blocks(
                panel, predictions, phase="train", scales=scales
            )
            return float(joint_loss(blocks)["loss"])
        except (FloatingPointError, OverflowError, ValueError):
            return 1e100

    def optimize_start(item: tuple[int, Array]) -> dict[str, Any]:
        index, start = item
        result = minimize(
            objective,
            start,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": int(optimization["maxiter"])},
        )
        return {
            "start_index": index,
            "initial": [float(value) for value in start],
            "objective": float(result.fun),
            "success": bool(result.success and np.isfinite(result.fun)),
            "message": str(result.message),
            "iterations": int(result.nit),
            "free": [float(value) for value in result.x],
        }

    workers = int(optimization.get("parallel_starts", 1))
    if workers < 1 or workers > multistarts:
        raise ValueError("parallel_starts must be between one and multistarts")
    indexed_starts = list(enumerate(starts))
    if workers == 1:
        records = [optimize_start(item) for item in indexed_starts]
    else:
        # The stochastic forward operator is deterministic for a frozen seed
        # and keeps only immutable noise descriptors in its cache.  Threads
        # therefore parallelize independent starts without copying the large
        # observable panel into separate processes.
        with ThreadPoolExecutor(max_workers=workers) as executor:
            records = list(executor.map(optimize_start, indexed_starts))
    successful = [
        record
        for record in records
        if bool(record["success"])
        and np.isfinite(record["objective"])
        and float(record["objective"]) < 1e99
    ]
    minimum_successful = int(
        optimization.get("successful_starts_min", 1)
    )
    if len(successful) < minimum_successful:
        return {
            "status": "fit_failed",
            "model": name,
            "reason": (
                f"only {len(successful)} optimizer starts converged; "
                f"{minimum_successful} required"
            ),
            "starts": records,
            "noise_panel_sha256": _noise_hash(noise_panel),
        }
    successful.sort(key=lambda item: float(item["objective"]))
    best = successful[0]
    if len(successful) >= 2:
        best_value = float(best["objective"])
        second_value = float(successful[1]["objective"])
        relative_spread = abs(second_value - best_value) / max(
            abs(best_value),
            1e-10,
        )
    else:
        relative_spread = 0.0
    maximum_spread = float(
        optimization.get(
            "best_objective_relative_spread_max",
            float("inf"),
        )
    )
    if relative_spread > maximum_spread:
        return {
            "status": "fit_failed",
            "model": name,
            "reason": (
                "the two best converged starts disagree beyond the "
                "registered objective-spread threshold"
            ),
            "best_objective_relative_spread": relative_spread,
            "starts": records,
            "noise_panel_sha256": _noise_hash(noise_panel),
        }
    parameters = parameters_for_model(name, np.asarray(best["free"]))
    predictions = predictor(name, parameters, panel, noise_panel)
    train_blocks = build_loss_blocks(
        panel, predictions, phase="train", scales=scales
    )
    validation_blocks = build_loss_blocks(
        panel, predictions, phase="validation", scales=scales
    )
    train_score = joint_loss(train_blocks)
    validation_score = joint_loss(validation_blocks)
    train_score.pop("residual_vector")
    residual = np.asarray(validation_score.pop("residual_vector"))
    validation_by_time = loss_by_time(validation_blocks)
    return {
        "status": "fit_complete",
        "model": name,
        "free_parameter_names": list(names),
        "free": list(best["free"]),
        "parameters": {
            key: float(value)
            for key, value in parameters.__dict__.items()
        },
        "train": train_score,
        "validation": validation_score,
        "validation_rss": float(np.sum(residual**2)),
        "validation_n": int(residual.size),
        "validation_loss_by_time": [
            float(value) for value in validation_by_time
        ],
        "scales": scales,
        "starts": records,
        "successful_starts": len(successful),
        "best_objective_relative_spread": relative_spread,
        "noise_panel_sha256": _noise_hash(noise_panel),
    }


def score_registered_parameters(
    name: ModelName,
    free: Array,
    panel: JointObservablePanel,
    *,
    noise_panel: Any,
    predictor: Predictor,
    scales: Mapping[str, float],
    phase: str,
) -> dict[str, Any]:
    """Score frozen parameters without optimizing or changing train scales."""

    parameters = parameters_for_model(name, np.asarray(free, dtype=float))
    predictions = predictor(name, parameters, panel, noise_panel)
    blocks = build_loss_blocks(
        panel,
        predictions,
        phase=phase,
        scales=scales,
    )
    score = joint_loss(blocks)
    residual = np.asarray(score.pop("residual_vector"))
    return {
        phase: score,
        f"{phase}_rss": float(np.sum(residual**2)),
        f"{phase}_n": int(residual.size),
        f"{phase}_loss_by_time": [
            float(value) for value in loss_by_time(blocks)
        ],
    }
