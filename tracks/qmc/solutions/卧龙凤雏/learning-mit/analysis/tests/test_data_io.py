import hashlib
import json
from pathlib import Path

import pytest

from analysis.data_io import load_run


def test_load_run_validates_and_groups_a_frozen_stream(tmp_path: Path):
    run_dir = frozen_run(tmp_path)
    loaded = load_run(run_dir)

    assert len(loaded.streams) == 1
    key = ("diii-coarse", 0.45, 0.18, 4, 0)
    assert loaded.streams[key].blocks[0].gamma == pytest.approx(1.25)


def test_load_run_rejects_changed_stream_hash(tmp_path: Path):
    run_dir = frozen_run(tmp_path)
    path = next((run_dir / "raw/streams").glob("*.json"))
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        load_run(run_dir)


def frozen_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    streams_dir = run_dir / "raw/streams"
    streams_dir.mkdir(parents=True)
    stage = {
        "name": "diii-coarse",
        "theta_pi": 0.45,
        "phi_pi": [0.18],
        "widths": [4],
        "streams": 1,
        "burn_in_layers_per_width": 1,
        "measurement_layers_per_width": 2,
        "block_layers_per_width": 1,
    }
    seed = derive_seed(122, 0, 0, 4, 0, 0x424F524E)
    estimate = {
        "stage_index": 0,
        "angle_index": 0,
        "width": 4,
        "stream": 0,
        "seed": seed,
        "mode": "born",
        "is_physical": True,
        "blocks": [
            block(0, 1.25),
            block(1, 1.30),
        ],
    }
    artifact = {
        "schema_version": 1,
        "stage_name": "diii-coarse",
        "theta_pi": 0.45,
        "phi_pi": 0.18,
        "stage_config": stage,
        "estimate": estimate,
    }
    relative = "raw/streams/diii-coarse-a00-L04-s000.json"
    path = run_dir / relative
    payload = json.dumps(artifact, indent=2).encode()
    path.write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "status": "running",
        "config": {
            "base_seed": 122,
            "production_gates": False,
            "invariant_tolerance": 1e-9,
            "runtime": {
                "target_seconds": 4,
                "ordinary_stop_seconds": 3,
                "hard_stop_seconds": 5,
                "finalize_reserve_seconds": 1,
            },
            "stages": [stage],
        },
        "git_commit": "fixture",
        "started_at": "0",
        "updated_at": "0",
        "completed_at": None,
        "elapsed_s": 0.1,
        "tasks": [
            {
                "key": "diii-coarse-a00-L04-s000",
                "state": "completed",
                "elapsed_s": 0.1,
                "reserve_reason": None,
                "artifact": relative,
            }
        ],
        "seeds": [
            {
                "stage": 0,
                "angle": 0,
                "width": 4,
                "stream": 0,
                "purpose": 0x424F524E,
                "seed": seed,
            }
        ],
        "artifact_sha256": {
            relative: hashlib.sha256(payload).hexdigest(),
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def block(index: int, gamma: float) -> dict:
    return {
        "block_index": index,
        "gamma": gamma,
        "half_chain_entropy": 0.7,
        "entropy_arc": [
            {"interval_sites": 1, "entropy": 0.4},
            {"interval_sites": 2, "entropy": 0.7},
            {"interval_sites": 3, "entropy": 0.4},
        ],
        "spatial_correlations": [
            {"distance": 1, "connected_parity": -0.1},
            {"distance": 2, "connected_parity": -0.03},
        ],
        "lyapunov": [0.6, 0.4, 0.2, 0.1, -0.1, -0.2, -0.4, -0.6],
        "min_probability": 0.2,
        "max_antisymmetry_error": 1e-14,
        "max_purity_error": 1e-13,
    }


def derive_seed(base: int, stage: int, angle: int, width: int, stream: int, purpose: int) -> int:
    value = base
    for coordinate in [stage, angle, width, stream, purpose]:
        value ^= (coordinate + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        value = splitmix64(value)
    return value


def splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask
