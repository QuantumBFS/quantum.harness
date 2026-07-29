"""Tests for the resumable Haar-MIPT production scheduler."""

import importlib.util
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "haar_mipt_production.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("haar_mipt_production", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["haar_mipt_production"] = module
    spec.loader.exec_module(module)
    return module


def _config(stage="pilot", sample_counts=None):
    sample_counts = {8: 2} if sample_counts is None else sample_counts
    return {"schema_version": 1, "stage": stage,
            "sizes": sorted(sample_counts), "sample_counts": sample_counts,
            "families": ["global_haar", "product"], "p": .168,
            "base_seed": 122168, "burn_in_multiplier": 4,
            "record_multiplier": 24, "workers": 2,
            "soft_deadline_seconds": 60.0}


def _production_record(L=8, family="global_haar", index=0,
                       density=1.0, runtime=1.0, seed=None):
    record_steps = 24*L
    family_code = {"global_haar": 0, "product": 1}[family]
    generated = np.random.SeedSequence([122168, L, family_code, index])
    seed = (int(generated.generate_state(1, dtype=np.uint64)[0])
            if seed is None else int(seed))
    return {"schema_version": 1, "L": L, "p": .168,
            "initial_family": family, "sample_index": index, "seed": seed,
            "burn_in_steps": 4*L, "record_steps": record_steps,
            "record_cost": density*L*record_steps,
            "cumulative_record_cost": [density*L*(j+1)
                                       for j in range(record_steps)],
            "runtime_seconds": runtime, "gate_count": 14*L**2,
            "attempted_measurements": 2, "outcome_counts": [1, 1]}


def _valid_record():
    return _production_record()


def _pilot_records_with_stdevs(L, haar_stdev, product_stdev, count):
    centered = np.arange(count, dtype=float) - .5*(count-1)
    centered /= centered.std(ddof=1)
    records = []
    for family, stdev in (("global_haar", haar_stdev),
                          ("product", product_stdev)):
        records.extend(_production_record(L, family, index, 1.0+stdev*z)
                       for index, z in enumerate(centered))
    return records


def _runtime_records(seconds, count):
    return [_production_record(8, family, index, runtime=seconds)
            for family in ("global_haar", "product")
            for index in range(count)]


def test_seeds_are_unique_across_family_width_and_index():
    module = _load_module()
    seeds = {module.trajectory_seed(122168, L, family, index)
             for L in (8, 10, 12)
             for family in ("global_haar", "product")
             for index in range(20)}
    assert len(seeds) == 120
    assert module.trajectory_seed(122168, 8, "product", 0) == int(
        np.random.SeedSequence([122168, 8, 1, 0]).generate_state(
            1, dtype=np.uint64)[0])


def test_pilot_allocation_uses_equal_family_variance():
    module = _load_module()
    records = _pilot_records_with_stdevs(L=8, haar_stdev=.003,
                                         product_stdev=.004, count=64)
    allocation = module.pilot_allocation(records)
    effective = .5*np.sqrt(.003**2 + .004**2)
    expected = 64*math.ceil(max(512, (effective/2e-4)**2)/64)
    assert allocation[8]["requested_per_family"] == expected
    assert allocation[8]["projected_se"] == pytest.approx(
        effective / np.sqrt(expected))
    assert not allocation[8]["cap_limited"]


def test_pilot_allocation_rounds_before_applying_hard_cap():
    module = _load_module()
    records = _pilot_records_with_stdevs(8, .1, .1, 4)
    allocation = module.pilot_allocation(records)
    assert allocation[8]["requested_per_family"] == 25000
    assert allocation[8]["cap_limited"]


def test_pilot_allocation_requires_both_family_variances():
    module = _load_module()
    records = [_production_record(8, "global_haar", index)
               for index in range(2)]
    with pytest.raises(ValueError, match="both family variances"):
        module.pilot_allocation(records)


def test_projection_selects_remote_above_ten_minutes():
    module = _load_module()
    records = _runtime_records(seconds=10.0, count=64)
    projected = module.project_runtime(records, {8: 512}, workers=8)
    assert projected["missing_trajectories"] == 896
    assert projected["projected_cpu_seconds"] == pytest.approx(8960.0)
    assert projected["projected_wall_seconds"] == pytest.approx(1344.0)
    assert projected["route"] == "remote"


def test_projection_counts_only_missing_records_with_family_specific_means():
    module = _load_module()
    records = [_production_record(8, "global_haar", index, runtime=2.0)
               for index in range(3)]
    records += [_production_record(8, "product", index, runtime=5.0)
                for index in range(2)]
    projected = module.project_runtime(records, {"8": 4}, workers=2)
    assert projected["missing_trajectories"] == 3
    assert projected["projected_cpu_seconds"] == pytest.approx(12.0)
    assert projected["projected_wall_seconds"] == pytest.approx(7.2)
    assert projected["worker_memory_mib"] == 24
    assert projected["route"] == "local"


def test_build_tasks_balances_completion_then_prefers_large_width():
    module = _load_module()
    completed = {(8, "global_haar", 0), (8, "global_haar", 1),
                 (10, "product", 0)}
    tasks = module.build_tasks({"8": 4, "10": 4}, completed)
    keys = [(task["L"], task["family"], task["sample_index"])
            for task in tasks]
    assert keys[:4] == [(10, "global_haar", 0), (10, "global_haar", 1),
                        (10, "global_haar", 2), (10, "global_haar", 3)]
    assert keys[4:7] == [(8, "product", 0), (8, "product", 1),
                         (8, "product", 2)]
    assert len(keys) == len(set(keys)) == 13


def test_atomic_records_resume_and_reject_malformed_files(tmp_path):
    module = _load_module()
    config = _config(stage="pilot", sample_counts={8: 2})
    path = module.write_trajectory_record_atomic(_valid_record(), tmp_path)
    bad = path.with_name("trajectory_00001.json")
    bad.write_text("{broken", encoding="utf-8")
    records, invalid = module.load_valid_records(tmp_path, config)
    assert len(records) == 1
    assert invalid == [bad]
    assert json.loads(path.read_text(encoding="utf-8")) == _valid_record()
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("schema_version", 2),
        ("L", 10),
        ("p", .17),
        ("initial_family", "unknown"),
        ("sample_index", 2),
        ("seed", 9),
        ("burn_in_steps", 31),
        ("record_steps", 191),
        ("record_cost", -1.0),
        ("runtime_seconds", float("inf")),
        ("gate_count", 895),
        ("attempted_measurements", 3),
    ],
)
def test_invalid_record_invariants_are_isolated(tmp_path, mutation, value):
    module = _load_module()
    record = _valid_record()
    record[mutation] = value
    path = module.write_trajectory_record_atomic(record, tmp_path)
    records, invalid = module.load_valid_records(tmp_path, _config())
    assert records == []
    assert invalid == [path]


@pytest.mark.parametrize("cumulative", [[0.0], [1.0]*191 + [.5]])
def test_invalid_cumulative_cost_is_isolated(tmp_path, cumulative):
    module = _load_module()
    record = _valid_record()
    record["cumulative_record_cost"] = cumulative
    path = module.write_trajectory_record_atomic(record, tmp_path)
    records, invalid = module.load_valid_records(tmp_path, _config())
    assert records == []
    assert invalid == [path]


def test_production_requires_explicit_approval(tmp_path):
    module = _load_module()
    with pytest.raises(PermissionError, match="--approved"):
        module.run_ensemble(_config(stage="production", sample_counts={8: 2}),
                            tmp_path, approved=False)


def _slow_fake_trajectory(**kwargs):
    time.sleep(.03)
    return _production_record(L=int(kwargs["L"]),
                              family=kwargs["initial_family"],
                              density=1.0, runtime=.03,
                              seed=int(kwargs["seed"]))


def test_deadline_drains_running_tasks_without_replacement(tmp_path):
    module = _load_module()
    config = _config(sample_counts={8: 3})
    config["soft_deadline_seconds"] = .01
    result = module.run_ensemble(config, tmp_path,
                                 trajectory_runner=_slow_fake_trajectory,
                                 executor_factory=ThreadPoolExecutor)
    assert sum(result["actual_counts"].values()) == 2
    assert result["deadline_reached"]
    assert not result["requested_complete"]
    checkpoint = json.loads(
        (tmp_path / "run_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["actual_counts"] == result["actual_counts"]
    assert len(list((tmp_path / "records").glob("L*/*/*.json"))) == 2


def _fast_fake_trajectory(**kwargs):
    return _production_record(L=int(kwargs["L"]),
                              family=kwargs["initial_family"],
                              runtime=.001, seed=int(kwargs["seed"]))


def test_resume_reuses_pilot_records_and_normalizes_json_width_keys(tmp_path):
    module = _load_module()
    module.write_trajectory_record_atomic(
        _production_record(8, "global_haar", 0), tmp_path)
    config = _config(stage="production", sample_counts={"8": 2})
    result = module.run_ensemble(
        config, tmp_path, approved=True,
        trajectory_runner=_fast_fake_trajectory,
        executor_factory=ThreadPoolExecutor)
    assert result["actual_counts"] == {"L8/global_haar": 2, "L8/product": 2}
    assert result["requested_complete"]
    assert not result["deadline_reached"]
    records, invalid = module.load_valid_records(tmp_path, config)
    assert len(records) == 4
    assert invalid == []
    assert {(r["initial_family"], r["sample_index"]) for r in records} == {
        ("global_haar", 0), ("global_haar", 1),
        ("product", 0), ("product", 1)}
