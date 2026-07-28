"""Separated MPS and MPO uncertainty analysis for the local reproduction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .crossing_analysis import linear_crossing


def numeric_shift(reference: float, candidate: float) -> dict:
    """Return signed absolute and relative candidate-minus-reference shifts."""
    reference = float(reference)
    candidate = float(candidate)
    absolute = candidate - reference
    relative = absolute / abs(reference) if reference != 0.0 else None
    return {
        "reference": reference,
        "candidate": candidate,
        "absolute": absolute,
        "relative": relative,
    }


def _require_same_settings(
    reference: Mapping,
    candidate: Mapping,
    fields: Sequence[str],
) -> None:
    for field in fields:
        left = reference["settings"][field]
        right = candidate["settings"][field]
        if left != right:
            raise ValueError(
                f"settings mismatch for {field}: {left!r} != {right!r}"
            )


def compare_chi(reference: Mapping, candidate: Mapping) -> dict:
    """Compare two bond dimensions at fixed Hamiltonian and fit."""
    _require_same_settings(
        reference,
        candidate,
        (
            "sigma",
            "length",
            "gamma",
            "num_exponentials",
            "alpha",
            "r_fit",
        ),
    )
    result = {
        "kind": "mps",
        "length": reference["settings"]["length"],
        "gamma": reference["settings"]["gamma"],
        "chi": {
            "reference": reference["direct"]["even"]["requested_chi"],
            "candidate": candidate["direct"]["even"]["requested_chi"],
        },
        "energy": {},
    }
    for sector in ("even", "odd"):
        result["energy"][sector] = numeric_shift(
            reference["direct"][sector]["energy"],
            candidate["direct"][sector]["energy"],
        )
        result.setdefault("variance", {})[sector] = numeric_shift(
            reference["direct"][sector]["variance"],
            candidate["direct"][sector]["variance"],
        )
        result.setdefault("discarded_weight", {})[sector] = numeric_shift(
            reference["direct"][sector]["discarded_weight"],
            candidate["direct"][sector]["discarded_weight"],
        )
    result["gap"] = numeric_shift(
        reference["raw_observables"]["gap"],
        candidate["raw_observables"]["gap"],
    )
    result["r_xi"] = numeric_shift(
        reference["raw_observables"]["r_xi"],
        candidate["raw_observables"]["r_xi"],
    )
    result["runtime_seconds"] = {
        "reference_total": sum(
            reference["direct"][sector]["wall_seconds"]
            for sector in ("even", "odd")
        ),
        "candidate_total": sum(
            candidate["direct"][sector]["wall_seconds"]
            for sector in ("even", "odd")
        ),
    }
    return result


def _crossing_record(gammas, values: Mapping[int, Sequence[float]]) -> dict:
    difference = [
        float(small) - float(large)
        for small, large in zip(values[32], values[64], strict=True)
    ]
    crossing = linear_crossing(gammas, values[32], values[64])
    return {
        "gamma": crossing.gamma,
        "difference": difference,
        "left_index": crossing.left_index,
        "right_index": crossing.right_index,
        "fraction": crossing.fraction,
    }


def compare_k_crossing(gammas, k24, k32) -> dict:
    """Compare K crossings using the identical signed R_xi difference."""
    if 32 not in k32:
        return {
            "status": "incomplete_cost_limited",
            "reason": "K32_L32_missing",
        }
    if set(k24) != {32, 64} or set(k32) != {32, 64}:
        raise ValueError("crossing comparison requires L=32 and L=64")
    return {
        "status": "complete",
        "K24": _crossing_record(gammas, k24),
        "K32": _crossing_record(gammas, k32),
    }
