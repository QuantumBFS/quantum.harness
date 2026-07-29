from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import jax

def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> str:
    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def document(
    evidence_type: str,
    revision: str,
    inputs: dict[str, str],
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "evidence_type": evidence_type,
        "inputs": inputs,
        "payload": payload,
        "schema_version": 1,
        "source_revision": revision,
    }


def parse_time(path: Path) -> tuple[dict[str, object], str]:
    values = {}
    command = ""
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("Command being timed: "):
            command = stripped.removeprefix("Command being timed: ").strip('"')
        elif stripped.startswith("Elapsed (wall clock) time "):
            values["wall"] = stripped.rsplit(": ", 1)[1]
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
            values[key] = value.strip()
    wall_parts = [float(part) for part in values["wall"].split(":")]
    wall_seconds = sum(
        part * multiplier
        for part, multiplier in zip(reversed(wall_parts), (1.0, 60.0, 3600.0))
    )
    return {
        "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "cpu_percent": int(values["Percent of CPU this job got"].rstrip("%")),
        "exit_status": int(values["Exit status"]),
        "peak_rss_kib": int(values["Maximum resident set size (kbytes)"]),
        "system_seconds": float(values["System time (seconds)"]),
        "user_seconds": float(values["User time (seconds)"]),
        "wall_seconds": wall_seconds,
    }, command


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--time", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.revision) is None:
        raise ValueError("revision must be a full git SHA")

    root = Path(__file__).resolve().parents[1]
    calibration_path = args.run_root / "calibration.raw.json"
    pilot_root = args.run_root / "pilot"
    calibration = json.loads(calibration_path.read_text())
    expected_platform = os.environ["JAX_PLATFORMS"]
    actual_platform = jax.devices()[0].platform
    if not jax.config.x64_enabled or actual_platform != expected_platform:
        raise RuntimeError("evidence collection requires the requested JAX x64 runtime")
    config = calibration.pop("config")
    calibration.pop("schema_version")
    config_sha256 = hashlib.sha256(
        json.dumps(
            config,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    lock = root / "uv.lock"
    uv_lock_sha256 = digest(lock)
    trial_paths = sorted((pilot_root / "trials").glob("*.json"))
    if len(trial_paths) != 1:
        raise ValueError("representative pilot must contain exactly one trial")
    trial_path = trial_paths[0]
    trial = json.loads(trial_path.read_text())
    if trial["config"] != config:
        raise ValueError("pilot is not bound to the calibration configuration")
    plan_path = pilot_root / "plan.json"
    ready_path = pilot_root / "ready.json"
    manifest_path = pilot_root / "manifest.json"
    validation = json.loads(args.validation.read_text())
    timing_payload, _ = parse_time(args.time)
    artifact_bytes = sum(
        path.stat().st_size for path in pilot_root.rglob("*") if path.is_file()
    )

    docs: dict[str, dict[str, object]] = {}
    docs["calibration.json"] = document(
        "calibration",
        args.revision,
        {"raw_calibration": digest(calibration_path), "uv_lock": uv_lock_sha256},
        {"config_sha256": config_sha256, **calibration},
    )
    docs["environment.json"] = document(
        "environment",
        args.revision,
        {"uv_lock": uv_lock_sha256},
        {
            "cpu_count": os.cpu_count(),
            "jax": importlib.metadata.version("jax"),
            "jax_platform": actual_platform,
            "jaxlib": importlib.metadata.version("jaxlib"),
            "numpy": importlib.metadata.version("numpy"),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "scipy": importlib.metadata.version("scipy"),
            "uv_lock_sha256": uv_lock_sha256,
            "x64_enabled": bool(jax.config.x64_enabled),
        },
    )
    pilot_payload = {
        "artifact_bytes": artifact_bytes,
        "config_sha256": config_sha256,
        "evaluations": trial["ledger"]["total_queries"],
        "manifest_sha256": digest(manifest_path),
        "plan_sha256": digest(plan_path),
        "ready_sha256": digest(ready_path),
        "total_queries": trial["ledger"]["total_queries"],
        "trial_id": trial["trial_id"],
        "trial_sha256": digest(trial_path),
    }
    docs["pilot.json"] = document(
        "pilot",
        args.revision,
        {
            "plan": pilot_payload["plan_sha256"],
            "trial": pilot_payload["trial_sha256"],
            "uv_lock": uv_lock_sha256,
        },
        pilot_payload,
    )
    docs["time.json"] = document(
        "time",
        args.revision,
        {"raw_time": digest(args.time), "trial": pilot_payload["trial_sha256"]},
        timing_payload,
    )
    docs["validation.json"] = document(
        "validation",
        args.revision,
        {
            "raw_validation": digest(args.validation),
            "ready": pilot_payload["ready_sha256"],
            "trial": pilot_payload["trial_sha256"],
        },
        validation,
    )
    trial_count = 9_500
    trial_hours = timing_payload["wall_seconds"] * trial_count / 3600
    projection_payload = {
        "cpus_per_trial": 8,
        "formula": "trial_hours=pilot_wall_seconds*trial_count/3600; core_hours=trial_hours*cpus_per_trial; storage_bytes=pilot_artifact_bytes*trial_count",
        "pilot_artifact_bytes": artifact_bytes,
        "pilot_wall_seconds": timing_payload["wall_seconds"],
        "projected_core_hours": trial_hours * 8,
        "projected_storage_bytes": artifact_bytes * trial_count,
        "projected_trial_hours": trial_hours,
        "provisional": True,
        "trial_count": trial_count,
    }
    docs["report_metadata.json"] = document(
        "report_metadata",
        args.revision,
        {"uv_lock": uv_lock_sha256},
        {"report_sha256": digest(args.report)},
    )

    hashes = {}
    for name in (
        "calibration.json",
        "environment.json",
        "pilot.json",
        "time.json",
        "validation.json",
    ):
        hashes[name] = write(args.output / name, docs[name])
    docs["projection.json"] = document(
        "projection",
        args.revision,
        {"pilot": hashes["pilot.json"], "time": hashes["time.json"]},
        projection_payload,
    )
    for name in ("projection.json", "report_metadata.json"):
        hashes[name] = write(args.output / name, docs[name])
    write(
        args.output / "index.json",
        {
            "documents": dict(sorted(hashes.items())),
            "schema_version": 1,
            "source_revision": args.revision,
        },
    )


if __name__ == "__main__":
    main()
