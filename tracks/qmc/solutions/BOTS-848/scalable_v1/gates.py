from __future__ import annotations

import copy
import math
from numbers import Real
from typing import Any, Mapping

import numpy as np

from .audit import AuditResult
from .protocol import ProtocolConfig


L2_COMPONENT_ORDER = ("-2", "-1", "0", "1", "2")
EXPECTED_L2_COMPONENTS = frozenset(L2_COMPONENT_ORDER)
PRE_REVEAL_GATE_NAMES = (
    "lll_valid",
    "antisymmetry_valid",
    "so3_equivariance_valid",
    "l2_casimir_valid",
    "fivefold_multiplet_valid",
    "mc_error_valid",
    "ed_crosscheck_valid",
    "reproducible_run_valid",
    "scalable_path_valid",
    "oracle_isolated",
    "blind_training_valid",
    "resource_budget_valid",
)
FINAL_GATE_NAMES = (*PRE_REVEAL_GATE_NAMES, "scalable_v1_pass")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _required(mapping: Mapping[str, Any], key: str, name: str) -> Any:
    if key not in mapping:
        raise ValueError(f"{name}.{key} is required")
    return mapping[key]


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a boolean")
    return bool(value)


def _json_scalar(value: Any) -> Any:
    return value.item() if isinstance(value, np.generic) else value


def _finite_real(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    positive: bool = False,
    integer: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite real number")
    if positive and number <= 0.0:
        raise ValueError(f"{name} must be positive")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if integer and not number.is_integer():
        raise ValueError(f"{name} must have integer semantics")
    return number


def _estimate(value: Any, name: str) -> dict[str, float]:
    estimate = _mapping(value, name)
    return {
        "mean": _finite_real(_required(estimate, "mean", name), f"{name}.mean"),
        "variance": _finite_real(
            _required(estimate, "variance", name),
            f"{name}.variance",
            minimum=0.0,
        ),
        "standard_error": _finite_real(
            _required(estimate, "standard_error", name),
            f"{name}.standard_error",
            minimum=0.0,
        ),
        "effective_sample_size": _finite_real(
            _required(estimate, "effective_sample_size", name),
            f"{name}.effective_sample_size",
            minimum=0.0,
        ),
        "maximum_imaginary_part": _finite_real(
            _required(estimate, "maximum_imaginary_part", name),
            f"{name}.maximum_imaginary_part",
            minimum=0.0,
        ),
    }


def _state(value: Any, name: str) -> dict[str, dict[str, float]]:
    state = _mapping(value, name)
    return {
        observable: _estimate(
            _required(state, observable, name), f"{name}.{observable}"
        )
        for observable in ("energy", "l2")
    }


def within(
    mean: float,
    target: float,
    error: float,
    floor: float,
    sigma: float,
) -> bool:
    return abs(mean - target) <= max(floor, sigma * error)


def evaluate_pre_reveal(
    evidence: Mapping[str, Any],
    protocol: ProtocolConfig,
    audit: AuditResult,
) -> dict[str, Any]:
    result = copy.deepcopy(evidence)
    construction = _mapping(
        _required(result, "construction", "evidence"), "construction"
    )
    statistics = _mapping(
        _required(result, "statistics", "evidence"), "statistics"
    )
    diagnostic_record = _mapping(
        _required(result, "diagnostics", "evidence"), "diagnostics"
    )
    resource_record = _mapping(
        _required(result, "resources", "evidence"), "resources"
    )

    raw_l2_by_m = _mapping(
        _required(statistics, "l2_by_m", "statistics"), "statistics.l2_by_m"
    )
    if set(raw_l2_by_m) != EXPECTED_L2_COMPONENTS:
        raise ValueError("complete L=2 multiplet is required")

    ground = _state(
        _required(statistics, "ground", "statistics"), "statistics.ground"
    )
    l2_by_m = {
        m: _state(raw_l2_by_m[m], f"statistics.l2_by_m.{m}")
        for m in L2_COMPONENT_ORDER
    }
    gap_record = _mapping(
        _required(statistics, "gap", "statistics"), "statistics.gap"
    )
    gap = {
        "mean": _finite_real(
            _required(gap_record, "mean", "statistics.gap"),
            "statistics.gap.mean",
        ),
        "standard_error": _finite_real(
            _required(gap_record, "standard_error", "statistics.gap"),
            "statistics.gap.standard_error",
            minimum=0.0,
        ),
    }
    all_states = [ground, *l2_by_m.values()]

    diagnostics = {
        name: _finite_real(
            _required(diagnostic_record, name, "diagnostics"),
            f"diagnostics.{name}",
            minimum=0.0,
        )
        for name in (
            "lll_residual",
            "particle_swap_residual",
            "finite_rotation_residual",
            "tower_ladder_residual",
        )
    }
    wall_seconds = _finite_real(
        _required(resource_record, "wall_seconds", "resources"),
        "resources.wall_seconds",
        positive=True,
    )
    peak_rss_bytes = _finite_real(
        _required(resource_record, "peak_rss_bytes", "resources"),
        "resources.peak_rss_bytes",
        minimum=0.0,
        integer=True,
    )
    checkpoint_bytes = _finite_real(
        _required(resource_record, "checkpoint_bytes", "resources"),
        "resources.checkpoint_bytes",
        minimum=0.0,
        integer=True,
    )
    trainable_parameters = _finite_real(
        _required(construction, "trainable_parameters", "construction"),
        "construction.trainable_parameters",
        positive=True,
        integer=True,
    )
    strict_lll = _boolean(
        _required(construction, "strict_lll", "construction"),
        "construction.strict_lll",
    )
    antisymmetric = _boolean(
        _required(construction, "antisymmetric", "construction"),
        "construction.antisymmetric",
    )
    scalable = _boolean(
        _required(construction, "scalable", "construction"),
        "construction.scalable",
    )
    n8_smoke_complete = _boolean(
        _required(resource_record, "n8_smoke_complete", "resources"),
        "resources.n8_smoke_complete",
    )

    sampling = protocol.sampling
    minimum_ess = sampling["minimum_ess_per_state"]
    maximum_imaginary = sampling["maximum_local_energy_imaginary_part"]
    mc_valid = (
        all(
            state[observable]["effective_sample_size"] >= minimum_ess
            for state in all_states
            for observable in ("energy", "l2")
        )
        and all(
            state["energy"]["maximum_imaginary_part"] <= maximum_imaginary
            for state in all_states
        )
        and gap["standard_error"] <= sampling["maximum_gap_standard_error"]
    )

    symmetry = protocol.symmetry
    l2_floor = symmetry["l2_expectation_absolute_floor"]
    l2_sigma = symmetry["l2_sigma_multiplier"]
    l2_variance_max = symmetry["l2_variance_max"]

    def valid_l2(state: Mapping[str, Any], target: float) -> bool:
        estimate = state["l2"]
        return within(
            estimate["mean"],
            target,
            estimate["standard_error"],
            l2_floor,
            l2_sigma,
        ) and estimate["variance"] <= l2_variance_max

    l2_valid = valid_l2(ground, 0.0) and all(
        valid_l2(state, 6.0) for state in l2_by_m.values()
    )

    highest = max(l2_by_m.values(), key=lambda state: state["energy"]["mean"])
    lowest = min(l2_by_m.values(), key=lambda state: state["energy"]["mean"])
    multiplet_splitting = (
        highest["energy"]["mean"] - lowest["energy"]["mean"]
    )
    multiplet_limit = max(
        abs(symmetry["multiplet_absolute_floor"]),
        symmetry["multiplet_sigma_multiplier"]
        * math.hypot(
            highest["energy"]["standard_error"],
            lowest["energy"]["standard_error"],
        ),
    )

    resource_limits = protocol.resources
    placement_value = _required(resource_record, "placement", "resources")
    if not isinstance(placement_value, str):
        raise ValueError("resources.placement must be local or remote")
    placement = str(placement_value)
    if placement == "local":
        wall_limit = resource_limits["local_wall_seconds"]
        rss_limit = resource_limits["local_peak_rss_bytes"]
    elif placement == "remote":
        wall_limit = resource_limits["remote_wall_seconds"]
        rss_limit = resource_limits["remote_peak_rss_bytes"]
    else:
        raise ValueError("resources.placement must be local or remote")
    resource_valid = bool(
        wall_seconds <= wall_limit
        and peak_rss_bytes <= rss_limit
        and checkpoint_bytes <= resource_limits["max_checkpoint_bytes"]
    )

    canonical_construction = {
        key: _json_scalar(value) for key, value in construction.items()
    }
    canonical_construction.update(
        strict_lll=strict_lll,
        antisymmetric=antisymmetric,
        scalable=scalable,
        trainable_parameters=int(trainable_parameters),
    )
    result["construction"] = canonical_construction

    canonical_statistics = {
        key: _json_scalar(value) for key, value in statistics.items()
    }
    canonical_statistics.update(
        ground=ground,
        l2_by_m=l2_by_m,
        gap=gap,
    )
    result["statistics"] = canonical_statistics

    canonical_diagnostics = {
        key: _json_scalar(value) for key, value in diagnostic_record.items()
    }
    canonical_diagnostics.update(diagnostics)
    canonical_diagnostics["multiplet_splitting"] = float(
        multiplet_splitting
    )
    result["diagnostics"] = canonical_diagnostics

    canonical_resources = {
        key: _json_scalar(value) for key, value in resource_record.items()
    }
    canonical_resources.update(
        placement=placement,
        wall_seconds=float(wall_seconds),
        peak_rss_bytes=int(peak_rss_bytes),
        checkpoint_bytes=int(checkpoint_bytes),
        n8_smoke_complete=n8_smoke_complete,
    )
    result["resources"] = canonical_resources

    result["gates"] = {
        "lll_valid": bool(
            strict_lll
            and diagnostics["lll_residual"] <= symmetry["lll_residual_max"]
        ),
        "antisymmetry_valid": bool(
            antisymmetric
            and diagnostics["particle_swap_residual"]
            <= symmetry["swap_residual_max"]
        ),
        "so3_equivariance_valid": bool(
            diagnostics["finite_rotation_residual"]
            <= symmetry["so3_residual_max"]
            and diagnostics["tower_ladder_residual"]
            <= symmetry["ladder_residual_max"]
        ),
        "l2_casimir_valid": bool(l2_valid),
        "fivefold_multiplet_valid": bool(
            multiplet_splitting <= multiplet_limit
        ),
        "mc_error_valid": bool(mc_valid),
        "ed_crosscheck_valid": "pending",
        "reproducible_run_valid": bool(audit.valid),
        "scalable_path_valid": bool(
            scalable
            and trainable_parameters
            <= protocol.capacity["max_trainable_parameters"]
            and n8_smoke_complete
        ),
        "oracle_isolated": bool(audit.valid),
        "blind_training_valid": bool(
            bool(audit.valid) and protocol.oracle["human_blind"] is False
        ),
        "resource_budget_valid": bool(resource_valid),
    }
    result["audit"] = {
        "valid": bool(audit.valid),
        "issues": list(audit.issues),
        "manifest_sha256": audit.manifest_sha256,
    }
    return result


def apply_ed_reveal(
    pre_reveal: Mapping[str, Any],
    oracle: Mapping[str, Any],
    protocol: ProtocolConfig,
) -> dict[str, Any]:
    pre_reveal = _mapping(pre_reveal, "pre-reveal evidence")
    pre_gates = _mapping(
        _required(pre_reveal, "gates", "pre-reveal evidence"),
        "pre-reveal gates",
    )
    if set(pre_gates) != set(PRE_REVEAL_GATE_NAMES):
        raise ValueError("pre-reveal gate schema does not match the frozen gate set")
    if pre_gates["ed_crosscheck_valid"] != "pending" or any(
        type(pre_gates[name]) is not bool
        for name in PRE_REVEAL_GATE_NAMES
        if name != "ed_crosscheck_valid"
    ):
        raise ValueError("pre-reveal gate schema has invalid gate values")
    if pre_gates["oracle_isolated"] is not True:
        raise ValueError("ED oracle cannot be loaded before oracle isolation passes")

    if not isinstance(oracle, Mapping) or set(oracle) != {
        "ground_energy",
        "l2_by_m",
    }:
        raise ValueError(
            "ED oracle schema must contain exactly ground_energy and l2_by_m"
        )
    oracle_components = _mapping(oracle["l2_by_m"], "ED oracle.l2_by_m")
    if set(oracle_components) != EXPECTED_L2_COMPONENTS:
        raise ValueError("ED oracle must contain a complete L=2 multiplet")

    ground_energy = _finite_real(
        oracle["ground_energy"], "ED oracle.ground_energy"
    )
    oracle_energies = {
        m: _finite_real(oracle_components[m], f"ED oracle.l2_by_m.{m}")
        for m in L2_COMPONENT_ORDER
    }
    ed_combined = sum(oracle_energies.values()) / len(oracle_energies)
    ed_gap = ed_combined - ground_energy

    result = copy.deepcopy(pre_reveal)
    statistics = _mapping(
        _required(result, "statistics", "pre-reveal evidence"), "statistics"
    )
    candidate_components = _mapping(
        _required(statistics, "l2_by_m", "statistics"), "statistics.l2_by_m"
    )
    if set(candidate_components) != EXPECTED_L2_COMPONENTS:
        raise ValueError("complete L=2 multiplet is required")
    ground = _state(
        _required(statistics, "ground", "statistics"), "statistics.ground"
    )
    excited = {
        m: _state(candidate_components[m], f"statistics.l2_by_m.{m}")
        for m in L2_COMPONENT_ORDER
    }
    gap_record = _mapping(
        _required(statistics, "gap", "statistics"), "statistics.gap"
    )
    gap_mean = _finite_real(
        _required(gap_record, "mean", "statistics.gap"),
        "statistics.gap.mean",
    )
    gap_standard_error = _finite_real(
        _required(gap_record, "standard_error", "statistics.gap"),
        "statistics.gap.standard_error",
        minimum=0.0,
    )

    ground_error = abs(ground["energy"]["mean"] - ground_energy)
    excited_errors = {
        m: abs(excited[m]["energy"]["mean"] - oracle_energies[m])
        for m in L2_COMPONENT_ORDER
    }
    gap_error = abs(gap_mean - ed_gap)

    oracle_protocol = protocol.oracle
    numerical_floor = oracle_protocol["numerical_floor"]
    sigma = oracle_protocol["ed_sigma_multiplier"]
    ground_standard_error = ground["energy"]["standard_error"]
    ed_valid = bool(
        ground_error <= max(numerical_floor, sigma * ground_standard_error)
        and gap_error <= max(numerical_floor, sigma * gap_standard_error)
        and all(
            excited_errors[m]
            <= max(
                numerical_floor,
                sigma * excited[m]["energy"]["standard_error"],
            )
            for m in L2_COMPONENT_ORDER
        )
    )

    result["ed_comparison"] = {
        "ground_absolute_error": ground_error,
        "excited_absolute_error_by_m": excited_errors,
        "gap_absolute_error": gap_error,
        "gap_z_score": gap_error / max(gap_standard_error, numerical_floor),
    }
    result["gates"]["ed_crosscheck_valid"] = bool(ed_valid)
    result["gates"]["scalable_v1_pass"] = all(
        result["gates"][name] is True for name in PRE_REVEAL_GATE_NAMES
    )
    if set(result["gates"]) != set(FINAL_GATE_NAMES):
        raise AssertionError("final gate schema diverged from the frozen gate set")
    return result
