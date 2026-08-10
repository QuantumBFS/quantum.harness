import hashlib
import json
from pathlib import Path

import numpy as np


def create_synthetic_run(run_dir: Path) -> Path:
    widths = [4, 6, 8, 10, 12, 14]
    config = {
        "widths": widths,
        "antiferromagnetic_probability": 0.1092212,
        "nishimori_k": 1.0493604763025683,
        "base_seed": 122464,
        "production_gates": False,
        "disorder": {
            "replicas": 4,
            "burn_in_rows": 32,
            "measurement_rows": 128,
            "block_rows": 16,
            "identity_delta_k": 0.0001,
            "identity_rows": 128,
        },
    }
    raw = run_dir / "raw"
    replicas_dir = raw / "replicas"
    replicas_dir.mkdir(parents=True)
    artifact_hashes = {}
    width_array = np.asarray(widths, dtype=float)
    base_phi = (
        1.337
        + np.pi * 0.464 / (6.0 * width_array**2)
        - 0.4 / width_array**4
    )
    for replica in range(4):
        blocks = []
        for block in range(8):
            delta_c = (replica - 1.5) * 0.001 + (block - 3.5) * 0.0002
            values = base_phi + np.pi * delta_c / (6.0 * width_array**2)
            blocks.append(
                {
                    "block_index": block,
                    "phi_by_width": [float(value) for value in values],
                }
            )
        total_bonds = 100_000
        artifact = {
            "schema_version": 1,
            "config": config,
            "estimate": {
                "replica": replica,
                "seed": 1000 + replica,
                "widths": widths,
                "blocks": blocks,
                "negative_bonds": round(
                    total_bonds * config["antiferromagnetic_probability"]
                ),
                "total_bonds": total_bonds,
            },
            "elapsed_s": 1.0,
        }
        path = replicas_dir / f"replica-{replica:03}.json"
        _write_json(path, artifact)
        artifact_hashes[f"replica-{replica:03}"] = _sha256(path)

    k = config["nishimori_k"]
    oracle = {
        "schema_version": 1,
        "config": config,
        "clean_transfer": [],
        "nishimori_energy_identity": {
            "width": 6,
            "derivative": 2.0 * np.tanh(k) + 0.001,
            "expected": 2.0 * np.tanh(k),
            "absolute_error": 0.001,
            "delta_k": 0.0001,
            "rows": 128,
        },
        "elapsed_s": 0.5,
    }
    oracle_path = raw / "oracles.json"
    _write_json(oracle_path, oracle)
    artifact_hashes["oracles"] = _sha256(oracle_path)

    manifest = {
        "schema_version": 1,
        "config": config,
        "config_path": "synthetic.toml",
        "commands": [],
        "rust_version": "rustc test",
        "cargo_lock_sha256": "test",
        "python_version": None,
        "python_requirements_sha256": None,
        "started_at": "unix:0",
        "updated_at": "unix:1",
        "completed_at": "unix:1",
        "thread_count": 1,
        "seeds": [],
        "completed_replicas": [0, 1, 2, 3],
        "artifact_sha256": artifact_hashes,
        "oracle_elapsed_s": 0.5,
        "simulation_elapsed_s": 4.0,
        "analysis_elapsed_s": None,
        "total_elapsed_s": None,
    }
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
