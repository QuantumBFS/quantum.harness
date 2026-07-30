"""Four-independent-chain CT-HYB statistics and production gates."""

from __future__ import annotations

import math
from statistics import mean, stdev
from typing import Sequence


STUDENT_95_DF3 = 3.182446305284263


def effective_samples(n_cycles: int, tau_int: float) -> int:
    if isinstance(n_cycles, bool) or n_cycles <= 0:
        raise ValueError("n_cycles must be positive")
    tau = float(tau_int)
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("autocorrelation time must be finite and nonnegative")
    return math.floor(n_cycles / (2 * max(1.0, tau)))


def independent_chain_statistics(values: Sequence[float]) -> dict[str, object]:
    if len(values) != 4:
        raise ValueError("exactly four independent chain values are required")
    converted = [float(value) for value in values]
    if not all(math.isfinite(value) for value in converted):
        raise ValueError("chain values must be finite")
    center = mean(converted)
    standard_error = stdev(converted) / 2
    half_width = STUDENT_95_DF3 * standard_error
    return {
        "chain_values": converted,
        "mean": center,
        "standard_error": standard_error,
        "degrees_of_freedom": 3,
        "student_quantile_95": STUDENT_95_DF3,
        "interval_95": [center - half_width, center + half_width],
    }


def build_summary(
    input_artifact: object,
    chains: Sequence[object],
    calibration: object,
) -> dict[str, object]:
    from artifacts import canonical_json, sha256_bytes

    if not isinstance(input_artifact, dict) or not isinstance(calibration, dict):
        raise ValueError("input and calibration artifacts are required")
    if len(chains) != 4 or any(not isinstance(chain, dict) for chain in chains):
        raise ValueError("exactly four chain summary artifacts are required")
    payloads = [chain.get("payload") for chain in chains]
    if any(not isinstance(payload, dict) for payload in payloads):
        raise ValueError("chain summary payload is malformed")
    indices = [payload["chain_index"] for payload in payloads]
    seeds = [payload["seed"] for payload in payloads]
    if sorted(indices) != list(range(4)) or len(set(seeds)) != 4:
        raise ValueError("chain index or seed inventory is invalid")
    if any(payload["input_sha256"] != input_artifact.get("sha256") for payload in payloads):
        raise ValueError("chain input identity mismatch")
    for payload in payloads:
        diagnostics = payload["diagnostics"]
        if (
            diagnostics["auto_corr_time_converged"] is not True
            or diagnostics["auto_corr_time"] > 5
            or diagnostics["effective_samples"] < 100000
            or diagnostics["average_sign"] < 0.99
        ):
            raise ValueError("per-chain production gate failed")
    if sum(payload["diagnostics"]["effective_samples"] for payload in payloads) < 400000:
        raise ValueError("total effective sample gate failed")
    scalars = {}
    for name in ("n_d", "double_occupancy"):
        scalars[name] = independent_chain_statistics(
            [payload["observables"][name] for payload in payloads]
        )
    tau = payloads[0]["reported_tau"]
    greens = {}
    for spin in ("G_up", "G_down"):
        if any(payload["reported_tau"] != tau for payload in payloads):
            raise ValueError("reported tau identity mismatch")
        greens[spin] = [
            independent_chain_statistics(
                [payload["observables"][spin][point] for payload in payloads]
            )
            for point in range(len(tau))
        ]
    payload = {
        "artifact_type": "cthyb_summary",
        "schema_version": 2,
        "status": "accepted",
        "input_sha256": input_artifact["sha256"],
        "calibration_sha256": calibration["sha256"],
        "chain_summary_sha256": [chain["sha256"] for chain in chains],
        "chain_indices": indices,
        "seeds": seeds,
        "reported_tau": tau,
        "scalars": scalars,
        "greens": greens,
    }
    return {"payload": payload, "sha256": sha256_bytes(canonical_json(payload))}
