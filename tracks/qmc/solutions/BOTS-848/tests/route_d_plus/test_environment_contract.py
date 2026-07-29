from __future__ import annotations

import json
import tomllib
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_ROOT = SOLUTION_ROOT / "route_d_plus" / "environment"


def test_phase1_freezes_challenge_15_physics_and_numeric_conventions() -> None:
    with (ENVIRONMENT_ROOT / "phase1.toml").open("rb") as stream:
        config = tomllib.load(stream)

    assert config["physics"]["n_electrons"] == 6
    assert config["physics"]["two_q"] == 3 * (
        config["physics"]["n_electrons"] - 1
    )
    assert config["physics"]["landau_level"] == 0
    assert config["physics"]["ground_l"] == 0
    assert config["physics"]["excited_l"] == 2
    assert config["energy"]["interaction"] == "pair_only_chord"
    assert config["numeric"]["python_major"] == 3
    assert config["numeric"]["python_minor"] == 11
    assert config["numeric"]["jax_enable_x64"] is True
    assert config["numeric"]["production_platform"] == "gpu"
    assert config["numeric"]["allow_production_cpu_fallback"] is False


def test_manifest_schema_requires_reproducibility_and_device_evidence() -> None:
    schema = json.loads(
        (ENVIRONMENT_ROOT / "manifest.schema.json").read_text(encoding="utf-8")
    )
    required = set(schema["required"])

    assert {
        "python_version",
        "jax_version",
        "jaxlib_version",
        "jax_enable_x64",
        "requested_platform",
        "device_kinds",
        "device_count",
        "git_commit",
        "git_dirty",
        "requirements_lock_sha256",
    } <= required
    assert schema["properties"]["jax_enable_x64"]["const"] is True
    assert schema["properties"]["git_dirty"]["const"] is False


def test_bootstrap_requires_explicit_jax_profile_and_ignored_run_directory() -> None:
    bootstrap = (ENVIRONMENT_ROOT / "bootstrap.sh").read_text(encoding="utf-8")
    batch = (ENVIRONMENT_ROOT / "phase1.sbatch").read_text(encoding="utf-8")
    capture = (ENVIRONMENT_ROOT / "capture_manifest.py").read_text(
        encoding="utf-8"
    )
    requirements = (ENVIRONMENT_ROOT / "requirements.in").read_text(
        encoding="utf-8"
    )

    assert "JAX_PROFILE:?" in bootstrap
    assert "ROUTE_D_PLUS_RUN_DIR:?" in bootstrap
    assert "tracks/qmc/results/" in bootstrap
    assert "all|install|validate" in bootstrap
    assert "jax[cuda12]" in bootstrap
    assert "jax[cuda13]" in bootstrap
    assert "--require-platform" in bootstrap
    assert "ROUTE_D_PLUS_REPO_ROOT:?" in batch
    assert 'ROUTE_D_PLUS_MODE="validate"' in batch
    assert "BASH_SOURCE[0]" not in batch
    assert "jsonschema" in requirements
    assert "validate_manifest(manifest)" in capture
