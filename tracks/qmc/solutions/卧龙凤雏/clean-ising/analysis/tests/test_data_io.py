import json

import pytest

from analysis.data_io import DataContractError, load_mc_blocks


def test_duplicate_monte_carlo_block_key_is_rejected(tmp_path):
    manifest = manifest_fixture()
    record = block_fixture()
    path = tmp_path / "blocks.jsonl"
    path.write_text(
        json.dumps(record) + "\n" + json.dumps(record) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DataContractError, match=r"duplicate.*\(4, 0, 0, 0\)"):
        load_mc_blocks(path, manifest)


def test_truncated_final_record_is_reported_as_incomplete(tmp_path):
    manifest = manifest_fixture()
    path = tmp_path / "blocks.jsonl"
    path.write_text(json.dumps(block_fixture()) + '\n{"schema_version":', encoding="utf-8")
    with pytest.raises(DataContractError, match="incomplete final"):
        load_mc_blocks(path, manifest)


def manifest_fixture():
    return {
        "schema_version": 1,
        "config": {
            "widths": [4, 6],
            "aspect_ratio": 2,
            "critical_k": 0.44068679350977147,
            "base_seed": 42,
            "production_gates": False,
            "exact": {
                "max_iterations": 10000,
                "eigenvalue_tolerance": 1.0e-12,
                "residual_tolerance": 1.0e-10,
            },
            "mc": {
                "replicas": 2,
                "grid_intervals": 4,
                "thermal_sweeps": 4,
                "measurement_sweeps": 8,
                "block_sweeps": 4,
            },
        },
        "seeds": [],
    }


def block_fixture():
    return {
        "schema_version": 1,
        "l": 4,
        "m": 8,
        "k_index": 0,
        "k": 0.0,
        "replica": 0,
        "seed": 1,
        "thermal_sweeps": 4,
        "measurement_sweeps": 8,
        "block_index": 0,
        "block_sweeps": 4,
        "cluster_updates_per_sweep": 32,
        "energy_sum": 0,
        "energy_squared_sum": 0,
        "measurement_count": 4,
        "mean_cluster_size": 1.0,
        "max_cluster_size": 1,
        "cumulative_elapsed_s": 0.0,
    }
