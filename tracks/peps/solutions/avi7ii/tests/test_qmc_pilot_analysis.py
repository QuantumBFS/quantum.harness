import json

import numpy as np
import pytest

from qh147.qmc_pilot_analysis import _load_run, analyze_bins


def _stable_bins(*, drift=0.0):
    beta = 0.5
    m_values = np.asarray([32, 64, 128], dtype=float)
    bins = np.empty((3, 4, 80), dtype=float)
    for m_index, m_value in enumerate(m_values):
        center = -3.0 + 120.0 * (beta / m_value) ** 2
        for chain in range(4):
            rng = np.random.default_rng(100 * m_index + chain)
            values = center + rng.normal(0.0, 0.04, size=80)
            values[40:] += drift
            bins[m_index, chain] = values
    return beta, m_values, bins


def test_stable_pilot_passes_all_gates_and_recovers_limit():
    beta, m_values, bins = _stable_bins()

    result = analyze_bins(
        beta, m_values, bins, bootstrap_samples=500, seed=147
    )

    assert result["accepted"]
    assert set(result["gates"].values()) == {True}
    assert abs(result["fit"]["u_infinity"] + 3.0) < 0.03
    assert result["fit"]["ci95"][0] < result["fit"]["u_infinity"]
    assert result["fit"]["ci95"][1] > result["fit"]["u_infinity"]


def test_split_half_drift_rejects_pilot():
    beta, m_values, bins = _stable_bins(drift=0.2)

    result = analyze_bins(
        beta, m_values, bins, bootstrap_samples=100, seed=147
    )

    assert not result["accepted"]
    assert not result["gates"]["split_half"]


def test_loader_rejects_a_runtime_measurement_mismatch(tmp_path):
    settings = {
        "thermal_sweeps": 4000,
        "measure_sweeps": 128000,
        "bins": 80,
    }
    provenance = {"protocol": "fixture"}
    cells = []
    for index, (m_value, chain) in enumerate(
        ((m, chain) for m in (32, 64, 128) for chain in range(4)), start=1
    ):
        cell_id = f"cell-{index:04d}"
        params = {"h": 3.0, "beta": 0.5, "M": m_value, "chain": chain}
        cells.append({"cell_id": cell_id, "params": params})
        root = tmp_path / "cells" / cell_id
        root.mkdir(parents=True)
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "success",
                    "params": params,
                    "settings": settings,
                    "provenance": provenance,
                    "runtime_settings": {
                        "thermal_sweeps": 4000,
                        "measure_sweeps": 128000,
                        "seed": 1000 + index,
                    },
                }
            ),
            encoding="utf-8",
        )
        np.savez(root / "bins.npz", energy=np.linspace(-3.1, -2.9, 80))
    (tmp_path / "run_spec.json").write_text(
        json.dumps(
            {
                "settings": settings,
                "provenance": provenance,
                "cells": cells,
            }
        ),
        encoding="utf-8",
    )

    _load_run(tmp_path)
    manifest_path = tmp_path / "cells" / "cell-0001" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_settings"]["measure_sweeps"] = 32000
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime measurement"):
        _load_run(tmp_path)
