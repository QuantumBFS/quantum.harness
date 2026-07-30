from __future__ import annotations

from pathlib import Path

from vmcrg_ref.artifacts import canonical_json_bytes, sha256_bytes, sha256_file


TRACK = Path(__file__).resolve().parents[1]
STAGE6_SOURCE_PATHS = (
    "jobs/hard_goal_pilot.slurm",
    "jobs/hard_goal_science_pilot.slurm",
    "scripts/hard_goal_freeze_protocol.py",
    "scripts/hard_goal_pilot_cell.py",
    "scripts/hard_goal_science_pilot_cell.py",
    "src/spinglass3d/backend.py",
    "src/spinglass3d/config.py",
    "src/spinglass3d/equilibration.py",
    "src/spinglass3d/gauge.py",
    "src/spinglass3d/jax_backend.py",
    "src/spinglass3d/model.py",
    "src/spinglass3d/pilot.py",
    "src/spinglass3d/rg.py",
    "src/spinglass3d/science_pilot.py",
    "src/spinglass3d/symmetry.py",
    "src/spinglass3d/templates.py",
    "src/spinglass3d/tensor_train.py",
    "src/spinglass3d/workflow.py",
    "src/vmcrg_ref/artifacts.py",
)


def write_passing_stage6_pilot(
    root: Path,
    *,
    j_counts: dict[str, int] | None = None,
    accelerator: str = "profile-accelerator:1",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    counts = j_counts or {"12": 64, "18": 32, "24": 16, "27": 8, "45": 128}
    temperatures = {length: [2.0, 1.4, 1.0, 0.8] for length in counts}
    sampling = {
        "chain_pairs": 4,
        "calibration_sweeps": 4096,
        "equilibration_sweeps": 65536,
        "measurement_sweeps": 8192,
    }
    equilibration = {
        "passed": True,
        "round_trips_min": 12,
        "swap_acceptance_min": 0.22,
        "rhat_max": 1.03,
        "ess_min": 240.0,
    }
    selection = {
        "route": "C",
        "template": "cube",
        "chi": 4,
        "mps_beats_conditioned_linear": True,
        "held_out_metric": "uniform_target_tv",
    }
    power = {"sufficient": True, "j_counts": counts}
    resources = {
        "cluster_profile": "test-profile",
        "partition": "profile-selected",
        "partition_candidates": ["profile-selected", "profile-fallback"],
        "accelerator": accelerator,
        "cpus": 8,
        "memory_bytes": 16 * 1024**3,
        "wall_seconds": 24 * 3600,
        "projected_l45_segment_seconds": 20 * 3600,
        "projected_peak_memory_bytes": 8 * 1024**3,
        "projected_output_bytes": 4 * 1024**3,
        "reserved_output_bytes": 6 * 1024**3,
    }
    thresholds = {
        "provisional": False,
        "swap_bottleneck": 0.15,
        "minimum_round_trips": 10,
        "maximum_rhat": 1.05,
        "minimum_ess": 200.0,
    }
    seeds = {"bootstrap": 2026073101, "pilot": 2026073102}
    artifact_root = root / "pilot-artifacts"
    artifact_root.mkdir()
    artifact_payloads = {
        "equilibration.json": equilibration,
        "power.json": power,
        "protocol.json": {
            "second_rg_enabled": False,
            "temperatures_by_length": temperatures,
            "sampling": sampling,
            "thresholds": thresholds,
            "seeds": seeds,
        },
        "resources.json": resources,
        "selection.json": selection,
    }
    for name, value in artifact_payloads.items():
        (artifact_root / name).write_bytes(canonical_json_bytes(value))
    artifacts = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in sorted(artifact_root.rglob("*"))
        if path.is_file()
    }
    config_path = TRACK / "config/hard_goal/stage6_pilot_v1.toml"
    design_path = TRACK / "config/hard_goal/design_v1.toml"
    source_hashes = {
        relative: sha256_file(TRACK / relative)
        for relative in STAGE6_SOURCE_PATHS
    }
    hashes = {
        "config": sha256_file(config_path),
        "design": sha256_file(design_path),
        "sources": sha256_bytes(canonical_json_bytes(source_hashes)),
        "artifacts": sha256_bytes(canonical_json_bytes(artifacts)),
    }
    payload = {
        "schema_version": 1,
        "stage": "stage6",
        "classification": "PASS",
        "second_rg_enabled": False,
        "artifact_root": "pilot-artifacts",
        "artifacts": artifacts,
        "provenance": {
            "config_path": "config/hard_goal/stage6_pilot_v1.toml",
            "design_path": "config/hard_goal/design_v1.toml",
            "config_sha256": hashes["config"],
            "design_sha256": hashes["design"],
            "source_sha256": source_hashes,
        },
        "temperatures_by_length": temperatures,
        "sampling": sampling,
        "equilibration": equilibration,
        "selection": selection,
        "power": power,
        "resources": resources,
        "thresholds": thresholds,
        "seeds": seeds,
        "hashes": hashes,
    }
    manifest = root / "pilot-manifest.json"
    manifest.write_bytes(canonical_json_bytes(payload))
    return manifest
