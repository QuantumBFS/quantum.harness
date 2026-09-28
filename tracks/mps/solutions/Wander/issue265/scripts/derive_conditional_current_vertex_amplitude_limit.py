#!/usr/bin/env python3
"""Derive the one-sided zero-amplitude current vertex from four wall pairs.

The registered amplitudes are ``mu=0.02,0.05,0.10,0.20``, each with both wall
orientations and microscopic current.  This program consumes target-free
outputs of ``invert_finite_time_mori_from_walls.py`` and extrapolates the
orientation-conditioned vertex to ``mu->0+``.  It does not accept a reference
coefficient and it reports the exact zero physical Kubo vertex separately.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.finite_time_mori_inversion import (  # noqa: E402
    conditional_vertex_zero_amplitude_limit,
    even_amplitude_zero_limit,
)
from src.heisenberg_burgers_bridge import (  # noqa: E402
    physical_quadratic_current_kubo_vertex,
)


def derive(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) < 4:
        raise ValueError("four opposite-orientation amplitude-pair records are required")
    mu: list[float] = []
    orientation: list[int] = []
    coefficient: list[float] = []
    condition_ids: list[str] = []
    windows: set[tuple[float, float]] = set()
    pair_amplitudes: list[float] = []
    mori_rows: list[np.ndarray] = []
    weak_diffusion: list[float] = []
    laplace_grid: np.ndarray | None = None
    for payload in records:
        inputs = payload.get("inputs", {})
        if inputs.get("target_coefficients_used") is not False:
            raise ValueError("every inversion must certify zero target-coefficient input")
        amplitude = float(inputs["mu"])
        pair_amplitudes.append(amplitude)
        window = tuple(map(float, inputs["t_window"]))
        windows.add(window)
        vertex = payload.get("microscopic_current_vertex")
        if not isinstance(vertex, dict):
            raise ValueError("every inversion must contain microscopic current vertices")
        mu.extend([amplitude, amplitude])
        orientation.extend([1, -1])
        coefficient.extend(
            [
                float(vertex["up"]["a_current_vertex"]),
                float(vertex["down"]["a_current_vertex"]),
            ]
        )
        condition_ids.extend(
            [str(inputs["up_condition_id"]), str(inputs["down_condition_id"])]
        )
        mori = payload.get("mori_k0_correction", {})
        current_s = np.asarray(mori.get("s", []), dtype=float)
        current_delta = np.asarray(
            mori.get("delta_K1_total_truncated", []), dtype=float
        )
        if current_s.ndim != 1 or current_s.size == 0 or current_delta.shape != current_s.shape:
            raise ValueError("every pair must contain a common finite-frequency Mori grid")
        if laplace_grid is None:
            laplace_grid = current_s
        elif not np.array_equal(laplace_grid, current_s):
            raise ValueError("all pair inversions must use the same Laplace grid")
        mori_rows.append(current_delta)
        weak_diffusion.append(float(payload["frozen_weak_projection"]["D"]))
    if len(windows) != 1:
        raise ValueError("all amplitude pairs must use the same time window")
    if len(condition_ids) != len(set(condition_ids)):
        raise ValueError("condition IDs must be unique")
    result = conditional_vertex_zero_amplitude_limit(
        np.asarray(mu), np.asarray(orientation), np.asarray(coefficient)
    )
    mori_limit = even_amplitude_zero_limit(
        np.asarray(pair_amplitudes), np.stack(mori_rows)
    )
    diffusion_limit = even_amplitude_zero_limit(
        np.asarray(pair_amplitudes), np.asarray(weak_diffusion)[:, None]
    )

    def serializable(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in payload.items()
        }
    return {
        "schema": 1,
        "inputs": {
            "condition_ids": condition_ids,
            "t_window": list(next(iter(windows))),
            "target_coefficients_used": False,
            "transport_trajectory_used": True,
            "amplitudes": sorted(set(mu)),
        },
        "exact_physical_zero_field_quadratic_kubo_vertex": (
            physical_quadratic_current_kubo_vertex()
        ),
        "conditional_one_sided_vertex": {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in result.items()
        },
        "linear_mori_zero_amplitude": {
            "s": np.asarray(laplace_grid).tolist(),
            **serializable(mori_limit),
        },
        "declared_weak_projection_D_zero_amplitude": serializable(diffusion_limit),
        "interpretation": (
            "a0_one_sided is the mu->0+ intercept after the long-time, "
            "orientation-conditioned projection; it is not the ordinary physical "
            "zero-field quadratic Kubo derivative"
        ),
    }


def _require_frozen_coverage(
    records: list[dict[str, Any]],
    convergence: dict[str, Any],
    production: dict[str, Any],
) -> None:
    if convergence.get("convergence_accepted") is not True:
        raise RuntimeError("frozen convergence validation is not accepted")
    if not (
        production.get("status") == "complete"
        and production.get("all_complete") is True
        and production.get("submission_complete") is True
    ):
        raise RuntimeError("Production A is not complete and validated")
    convergence_text = json.dumps(convergence, sort_keys=True)
    production_text = json.dumps(production, sort_keys=True)
    for payload in records:
        inputs = payload.get("inputs", {})
        for key in ("up_condition_id", "down_condition_id"):
            condition_id = str(inputs.get(key, ""))
            if not condition_id or (
                condition_id not in convergence_text and condition_id not in production_text
            ):
                raise RuntimeError(f"frozen records do not cover {condition_id!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-inversion", type=Path, action="append", required=True)
    parser.add_argument("--convergence-validation", type=Path, required=True)
    parser.add_argument("--production-a-record", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = [
        json.loads(path.read_text(encoding="utf-8")) for path in args.pair_inversion
    ]
    convergence = json.loads(args.convergence_validation.read_text(encoding="utf-8"))
    production = json.loads(args.production_a_record.read_text(encoding="utf-8"))
    _require_frozen_coverage(records, convergence, production)
    result = derive(records)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
