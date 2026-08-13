#!/usr/bin/env python3
"""Condition-number diagnosis for a saved DQMC history; does not modify it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from tensor_square.dqmc import (
    DQMCConfig,
    direct_log_weight,
    history_product,
    make_one_body_model,
    slice_matrix,
    stabilized_density_matrix,
    stabilized_direct_log_weight,
    stabilized_history_product,
    stabilized_structured_log_weight,
    structured_log_weight,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    with np.load(args.checkpoint, allow_pickle=False) as saved:
        config_data = json.loads(str(saved["config_json"].item()))
        config_data.pop("slices")
        config = DQMCConfig(**config_data)
        fields = saved["fields"]
        completed = int(saved["completed_sweeps"].item())
    model = make_one_body_model(config)
    kinetic_half = expm(-0.5 * config.dt * model.k)
    slices = [
        slice_matrix(
            field,
            model=model,
            dt=config.dt,
            kinetic_half=kinetic_half,
        )
        for field in fields
    ]
    x = history_product(slices)
    stable_product = stabilized_history_product(slices)
    full_system = np.eye(x.size) + np.kron(x, x)
    singular_x = np.linalg.svd(x, compute_uv=False)
    singular_system = np.linalg.svd(full_system, compute_uv=False)
    sign, direct_log = direct_log_weight(x)
    result = {
        "checkpoint": str(args.checkpoint),
        "completed_sweeps": completed,
        "config": config.as_dict(),
        "x_singular_max": float(singular_x[0]),
        "x_singular_min": float(singular_x[-1]),
        "x_condition": float(singular_x[0] / singular_x[-1]),
        "system_singular_max": float(singular_system[0]),
        "system_singular_min": float(singular_system[-1]),
        "system_condition": float(singular_system[0] / singular_system[-1]),
        "matrix_rank": int(np.linalg.matrix_rank(full_system)),
        "matrix_dimension": full_system.shape[0],
        "direct_sign": sign,
        "direct_log_weight": direct_log,
        "structured_log_weight": structured_log_weight(x),
        "stabilized_direct_log_weight": stabilized_direct_log_weight(
            stable_product
        )[1],
        "stabilized_structured_log_weight": stabilized_structured_log_weight(
            stable_product
        ),
        "stabilized_log_singular_min": float(
            np.min(stable_product.log_singular_values)
        ),
        "stabilized_log_singular_max": float(
            np.max(stable_product.log_singular_values)
        ),
        "stabilized_rho_finite": bool(
            np.all(np.isfinite(stabilized_density_matrix(stable_product)))
        ),
    }
    try:
        np.linalg.inv(full_system)
        result["inverse"] = "success"
    except np.linalg.LinAlgError as error:
        result["inverse"] = f"failure: {error}"
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
