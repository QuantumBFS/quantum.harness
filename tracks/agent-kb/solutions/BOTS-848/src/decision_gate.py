"""Evidence-aware triage for the level of electron-phonon correction."""

from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Number, Real

from .channel_decomposition import CHANNELS


DEFAULT_THRESHOLDS = {
    "charge_safe_weight": 0.80,
    "correction_channel_weight": 0.20,
    "dynamic_energy_ratio": 0.10,
}


def _validated_weights(weights: Mapping[str, Number]) -> dict[str, float]:
    if set(weights) != set(CHANNELS):
        raise ValueError(f"weights must contain exactly {', '.join(CHANNELS)}")
    values = {}
    for name in CHANNELS:
        value = weights[name]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("channel weights must be finite real numbers and not booleans")
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("channel weights must be finite real numbers and not booleans")
        values[name] = numeric_value
    if any(value < 0.0 for value in values.values()):
        raise ValueError("channel weights must be nonnegative")
    total = sum(values.values())
    if total != 0.0 and abs(total - 1.0) > 1.0e-8:
        raise ValueError("nonzero channel weights must sum to one")
    return values


def _validated_thresholds(thresholds: Mapping[str, Number] | None) -> dict[str, float]:
    values = dict(DEFAULT_THRESHOLDS)
    if thresholds is not None:
        unknown = set(thresholds) - set(DEFAULT_THRESHOLDS)
        if unknown:
            raise ValueError(f"unknown thresholds: {', '.join(sorted(unknown))}")
        for name, value in thresholds.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError("thresholds must be finite real numbers and not booleans")
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                raise ValueError("thresholds must be finite real numbers and not booleans")
            values[name] = numeric_value
    if any(value < 0.0 or value > 1.0 for value in values.values()):
        raise ValueError("thresholds must lie between zero and one")
    return values


def _result(decision, reasons, weights, evidence, thresholds):
    return {
        "decision": decision,
        "reasons": reasons,
        "weights": dict(weights),
        "evidence": dict(evidence),
        "thresholds": dict(thresholds),
    }


def select_correction_level(
    weights: Mapping[str, Number],
    evidence: Mapping[str, object],
    thresholds: Mapping[str, Number] | None = None,
) -> dict[str, object]:
    """Choose a research action while refusing unsupported classifications.

    ``adiabatic_ratio`` means phonon energy divided by the electronic relaxation
    energy scale. The thresholds are calibration parameters, not universal
    constants or claims of predictive accuracy. ``full_space_common_shift``
    must describe the original unprojected perturbation under a fixed energy-zero
    convention; projected global-charge weight alone cannot establish it.
    """

    values = _validated_weights(weights)
    limits = _validated_thresholds(thresholds)
    required = (
        "source_traceable",
        "reference_valid",
        "adiabatic_ratio",
        "uniform_q_zero",
        "full_space_common_shift",
    )
    missing = [name for name in required if name not in evidence]
    if missing:
        return _result(
            "abstain",
            [f"missing required evidence: {', '.join(missing)}"],
            values,
            evidence,
            limits,
        )
    if not isinstance(evidence["uniform_q_zero"], bool):
        raise ValueError("uniform_q_zero must be a boolean")
    if not isinstance(evidence["full_space_common_shift"], bool):
        raise ValueError("full_space_common_shift must be a boolean")
    ratio_value = evidence["adiabatic_ratio"]
    if isinstance(ratio_value, bool) or not isinstance(ratio_value, Real):
        raise ValueError(
            "adiabatic_ratio must be a finite nonnegative real number and not a boolean"
        )
    adiabatic_ratio = float(ratio_value)
    if not math.isfinite(adiabatic_ratio) or adiabatic_ratio < 0.0:
        raise ValueError(
            "adiabatic_ratio must be a finite nonnegative real number and not a boolean"
        )
    if evidence["source_traceable"] is not True:
        return _result(
            "abstain",
            ["source_traceable must be true before a scientific recommendation"],
            values,
            evidence,
            limits,
        )
    if evidence["reference_valid"] is not True:
        return _result(
            "abstain",
            ["the electronic reference state is not validated"],
            values,
            evidence,
            limits,
        )
    if sum(values.values()) == 0.0:
        return _result(
            "abstain",
            ["the projected perturbation has zero measured channel strength"],
            values,
            evidence,
            limits,
        )
    if adiabatic_ratio >= limits["dynamic_energy_ratio"]:
        return _result(
            "dynamic-correction",
            [
                "the phonon energy is not small relative to the electronic relaxation scale",
                "a static comparison cannot validate the physical-frequency vertex",
            ],
            values,
            evidence,
            limits,
        )

    correction_weight = (
        values["site_charge"] + values["internal"] + values["nonlocal"]
    )
    if correction_weight > limits["correction_channel_weight"]:
        return _result(
            "static-correction",
            [
                "the perturbation has appreciable site-charge, internal, or nonlocal weight",
                "global charge conservation does not constrain these channels",
            ],
            values,
            evidence,
            limits,
        )
    if (
        values["global_charge"] >= limits["charge_safe_weight"]
        and evidence["uniform_q_zero"] is True
        and evidence["full_space_common_shift"] is True
    ):
        return _result(
            "dfpt-safe",
            [
                "the validated low-energy perturbation is global-charge dominated",
                "uniform_q_zero is explicitly established",
                "full_space_common_shift is established before projection",
                "this is a calibration candidate, not a universal accuracy guarantee",
            ],
            values,
            evidence,
            limits,
        )
    if values["global_charge"] >= limits["charge_safe_weight"]:
        return _result(
            "abstain",
            [
                "uniform_q_zero and full_space_common_shift must both be true "
                "for a global-charge dfpt-safe classification"
            ],
            values,
            evidence,
            limits,
        )
    return _result(
        "abstain",
        ["the channel mixture lies between calibrated decision regions"],
        values,
        evidence,
        limits,
    )
