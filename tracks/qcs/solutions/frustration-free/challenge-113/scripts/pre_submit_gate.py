from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import jax
import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qcontrol.config import SystemConfig
from qcontrol.objectives import normalized_infidelity
from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


EXPECTED_OBJECTIVE = 0.9665488081391005
OBJECTIVE_TOLERANCE = 1e-14


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_canonical(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    value = json.loads(data)
    if not isinstance(value, dict) or data != canonical_bytes(value):
        raise ValueError(f"{path} is not canonical JSON")
    return value


def runtime_observation() -> dict[str, object]:
    system = make_system(SystemConfig("one_qubit", 6, 4.0))
    pulse_space = PulseSpace.from_system(system, 6)
    pulse = np.zeros(pulse_space.parameter_count, dtype=np.float64)
    propagator = np.asarray(
        propagate(system, pulse_space.to_physical(pulse)),
        dtype=np.complex128,
    )
    objective = float(normalized_infidelity(pulse, system, pulse_space))
    uv_version = subprocess.check_output(["uv", "--version"], text=True).strip()
    if not uv_version.startswith("uv "):
        raise RuntimeError("uv version output is not canonical")
    return {
        "critical_packages": {
            name: importlib.metadata.version(name)
            for name in ("jax", "jaxlib", "numpy", "scipy")
        },
        "jax_platform": jax.devices()[0].platform,
        "objective": objective,
        "propagation_finite": bool(
            np.all(np.isfinite(propagator.real))
            and np.all(np.isfinite(propagator.imag))
        ),
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "uv_version": uv_version.removeprefix("uv "),
        "x64_enabled": bool(jax.config.x64_enabled),
    }


def validate_runtime(
    observation: dict[str, object],
    deployment: dict[str, object],
) -> None:
    if observation["python_version"] != deployment["python_version"]:
        raise RuntimeError("Python version does not match deployment metadata")
    if observation["uv_version"] != deployment["uv_version"]:
        raise RuntimeError("uv version does not match deployment metadata")
    if observation["critical_packages"] != deployment["critical_packages"]:
        raise RuntimeError("critical package versions do not match deployment metadata")
    if observation["jax_platform"] != "cpu" or observation["x64_enabled"] is not True:
        raise RuntimeError("JAX must use the CPU x64 runtime")
    if observation["propagation_finite"] is not True:
        raise RuntimeError("propagation smoke is nonfinite")
    objective = observation["objective"]
    if (
        type(objective) is not float
        or not math.isfinite(objective)
        or abs(objective - EXPECTED_OBJECTIVE) > OBJECTIVE_TOLERANCE
    ):
        raise RuntimeError("deterministic objective smoke does not match")


def marker_payload(root: Path, metadata_path: Path) -> dict[str, object]:
    deployment = read_canonical(metadata_path)
    source_revision = (root / ".source-revision").read_text().strip()
    if source_revision != deployment["revision"]:
        raise RuntimeError("runtime source revision is stale")
    bindings = {
        "archive_sha256": deployment["archive_sha256"],
        "cluster_profile": deployment["cluster_profile"],
        "deployment_metadata_sha256": sha256(metadata_path),
        "evidence_index_sha256": sha256(root / "evidence/task10a/index.json"),
        "pyproject_sha256": sha256(root / "pyproject.toml"),
        "report_sha256": sha256(root / "REPORT.md"),
        "revision": source_revision,
        "schema_version": 1,
        "sif_sha256": deployment["sif_sha256"],
        "uv_lock_sha256": sha256(root / "uv.lock"),
    }
    for name in (
        "evidence_index_sha256",
        "pyproject_sha256",
        "report_sha256",
        "uv_lock_sha256",
    ):
        if bindings[name] != deployment[name]:
            raise RuntimeError(f"runtime {name} binding is stale")
    return bindings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--deployment-metadata", type=Path, required=True)
    parser.add_argument("--expected-deployment-metadata-sha256", required=True)
    marker = parser.add_mutually_exclusive_group(required=True)
    marker.add_argument("--write-marker", type=Path)
    marker.add_argument("--check-marker", type=Path)
    args = parser.parse_args()
    if (
        re.fullmatch(
            r"[0-9a-f]{64}",
            args.expected_deployment_metadata_sha256,
            re.ASCII,
        )
        is None
        or sha256(args.deployment_metadata)
        != args.expected_deployment_metadata_sha256
    ):
        raise RuntimeError("deployment metadata SHA256 mismatch")
    deployment = read_canonical(args.deployment_metadata)
    observation = runtime_observation()
    validate_runtime(observation, deployment)
    expected_marker = marker_payload(args.root, args.deployment_metadata)
    if args.check_marker is not None:
        if read_canonical(args.check_marker) != expected_marker:
            raise RuntimeError("prepared runtime marker is stale")
    else:
        args.write_marker.parent.mkdir(parents=True, exist_ok=True)
        args.write_marker.write_bytes(canonical_bytes(expected_marker))
    print(canonical_bytes({"pre_submit_gate": "valid"}).decode().strip(), flush=True)


if __name__ == "__main__":
    main()
