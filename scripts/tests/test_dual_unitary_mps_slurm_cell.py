import importlib.util
import json
import sys
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "dual_unitary_mps_slurm_cell.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "dual_unitary_mps_slurm_cell", _SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_production_spec_has_unique_one_trajectory_cells(tmp_path):
    module = _load_module()
    path = tmp_path / "run_spec.json"
    spec = module.write_production_spec(path, run_id="test-production")

    assert len(spec["cells"]) == 5600
    assert len({cell["cell_id"] for cell in spec["cells"]}) == 5600
    assert {cell["params"]["L"] for cell in spec["cells"]} == {
        8,
        10,
        12,
        14,
        16,
    }
    chis_by_width = {
        L: {
            cell["params"]["chi"]
            for cell in spec["cells"]
            if cell["params"]["L"] == L
        }
        for L in (8, 10, 12, 14, 16)
    }
    assert chis_by_width == {
        8: {16},
        10: {24, 32},
        12: {48, 64, 96},
        14: {64, 96, 128, 192},
        16: {96, 128, 192, 256},
    }
    assert spec["settings"]["samples_per_point"] == 400
    assert spec["settings"]["burn_in_multiplier"] == 32
    assert spec["settings"]["record_multiplier"] == 256
    assert len(spec["submission_batches"]) == 400
    assert {len(batch) for batch in spec["submission_batches"]} == {14}
    assert sorted(
        selector
        for batch in spec["submission_batches"]
        for selector in batch
    ) == list(range(1, 5601))
    for sample, batch in enumerate(spec["submission_batches"]):
        assert {
            spec["cells"][selector - 1]["params"]["sample_index"]
            for selector in batch
        } == {sample}
    assert json.loads(path.read_text(encoding="utf-8")) == spec


def test_production_spec_pairs_random_trajectories_across_chi(tmp_path):
    module = _load_module()
    spec = module.write_production_spec(
        tmp_path / "run_spec.json", run_id="test-paired-production"
    )

    paired = [
        cell
        for cell in spec["cells"]
        if cell["params"]["L"] == 16
        and cell["params"]["sample_index"] == 17
    ]
    assert {cell["params"]["chi"] for cell in paired} == {96, 128, 192, 256}
    assert len({cell["params"]["seed"] for cell in paired}) == 1

    next_sample = next(
        cell
        for cell in spec["cells"]
        if cell["params"]["L"] == 16
        and cell["params"]["sample_index"] == 18
    )
    assert next_sample["params"]["seed"] != paired[0]["params"]["seed"]


def test_run_cell_writes_manifest_and_resumes(tmp_path):
    module = _load_module()
    spec = {
        "run_id": "test-run",
        "run_dir": str(tmp_path / "results" / "test-run"),
        "settings": {
            "p": 0.14,
            "cutoff": 1e-12,
            "burn_in_multiplier": 2,
            "record_multiplier": 4,
        },
        "cells": [
            {
                "cell_id": "L08-chi016-s000",
                "params": {"L": 8, "chi": 16, "seed": 7001},
            }
        ],
    }
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        steps = kwargs["record_steps"]
        cumulative = [0.25 * (index + 1) for index in range(steps)]
        return {
            "schema_version": 1,
            **kwargs,
            "record_cost": cumulative[-1],
            "cumulative_record_cost": cumulative,
            "discarded_weight_sum": 1e-7,
            "split_count": 10,
            "max_bond_used": kwargs["chi"],
            "runtime_seconds": 0.1,
            "attempted_measurements": 3,
            "outcome_counts": [2, 1],
        }

    first = module.run_cell(spec, 1, trajectory_runner=fake_runner)
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["L"] == 8
    assert manifest["chi"] == 16
    assert manifest["entropy_density_slope"] > 0.0
    assert len(calls) == 1

    second = module.run_cell(spec, 1, trajectory_runner=fake_runner)
    assert second.resumed is True
    assert len(calls) == 1


def test_run_batch_executes_each_listed_cell(tmp_path):
    module = _load_module()
    spec = {
        "run_id": "test-batch",
        "run_dir": str(tmp_path / "results" / "test-batch"),
        "settings": {
            "p": 0.14,
            "cutoff": 1e-12,
            "burn_in_multiplier": 1,
            "record_multiplier": 2,
        },
        "cells": [
            {
                "cell_id": f"L08-chi{chi:03d}-s000",
                "params": {
                    "L": 8,
                    "chi": chi,
                    "sample_index": 0,
                    "seed": 123,
                },
            }
            for chi in (16, 24)
        ],
        "submission_batches": [[1, 2]],
    }
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs["chi"])
        steps = kwargs["record_steps"]
        return {
            "schema_version": 1,
            **kwargs,
            "record_cost": float(steps),
            "cumulative_record_cost": list(range(1, steps + 1)),
            "discarded_weight_sum": 0.0,
            "split_count": 1,
            "max_bond_used": kwargs["chi"],
            "runtime_seconds": 0.01,
            "attempted_measurements": 0,
            "outcome_counts": [0, 0],
        }

    results = module.run_batch(spec, 1, trajectory_runner=fake_runner)

    assert len(results) == 2
    assert calls == [16, 24]
