import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_slurm_cell.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_slurm_cell", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_slurm_cell"] = module
    spec.loader.exec_module(module)
    return module


def _run_spec(tmp_path):
    return {
        "run_id": "test-run",
        "run_dir": str(tmp_path / "results" / "test-run"),
        "settings": {
            "p": 0.17,
            "base_seed": 122170,
            "burn_in_multiplier": 4,
            "record_multiplier": 24,
            "samples_per_cell": 3,
            "samples_per_family_width": 3,
        },
        "provenance": {"source": "test"},
        "cells": [
            {
                "cell_id": "cell-0001",
                "params": {
                    "L": 6,
                    "initial_family": "global_haar",
                    "block_index": 0,
                },
            }
        ],
    }


def _fake_trajectory(L, p, seed, initial_family, burn_in_steps, record_steps):
    density = 0.1 + (int(seed) % 7) * 1e-4
    cumulative = density * int(L) * np.arange(1, int(record_steps) + 1)
    return {
        "schema_version": 1,
        "L": int(L),
        "p": float(p),
        "initial_family": initial_family,
        "seed": int(seed),
        "burn_in_steps": int(burn_in_steps),
        "record_steps": int(record_steps),
        "record_cost": float(cumulative[-1]),
        "cumulative_record_cost": cumulative.tolist(),
        "runtime_seconds": 0.01,
        "gate_count": 1,
        "attempted_measurements": 2,
        "outcome_counts": [1, 1],
    }


def test_run_cell_writes_valid_batch_and_resumes(tmp_path):
    module = _load_module()
    spec = _run_spec(tmp_path)
    first = module.run_cell(spec, 1, trajectory_runner=_fake_trajectory)
    manifest = json.loads(first.manifest_path.read_text())
    assert manifest["status"] == "success"
    assert manifest["samples_expected"] == manifest["samples_valid"] == 3
    assert not list(first.batch_path.parent.glob("*.tmp"))
    records = list(module.iter_batch_records(first.batch_path))
    assert [record["sample_index"] for record in records] == [0, 1, 2]
    assert all(record["L"] == 6 for record in records)

    def fail_if_called(**kwargs):
        raise AssertionError("valid batch should be resumed")

    second = module.run_cell(spec, 1, trajectory_runner=fail_if_called)
    assert second.resumed is True
    assert second.batch_path == first.batch_path


def test_select_cell_rejects_zero_based_selector(tmp_path):
    module = _load_module()
    try:
        module.select_cell(_run_spec(tmp_path), 0)
    except ValueError as error:
        assert "one-based" in str(error)
    else:
        raise AssertionError("zero selector was accepted")
