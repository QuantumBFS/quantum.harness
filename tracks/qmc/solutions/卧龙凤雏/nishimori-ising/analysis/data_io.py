import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class LoadedRun:
    run_dir: Path
    manifest: dict
    config: dict
    oracle: dict
    replicas: list[dict]
    widths: np.ndarray
    block_tensor: np.ndarray
    negative_bonds: int
    total_bonds: int


def load_run(run_dir: Path) -> LoadedRun:
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest schema_version must equal 1")
    config = manifest["config"]
    widths = np.asarray(config["widths"], dtype=float)

    oracle_path = run_dir / "raw" / "oracles.json"
    _verify_hash(oracle_path, manifest, "oracles")
    oracle = _read_json(oracle_path)
    _validate_artifact(oracle, config, "oracle")

    replicas = []
    negative_bonds = 0
    total_bonds = 0
    expected_replicas = config["disorder"]["replicas"]
    for replica_index in range(expected_replicas):
        key = f"replica-{replica_index:03d}"
        path = run_dir / "raw" / "replicas" / f"{key}.json"
        _verify_hash(path, manifest, key)
        artifact = _read_json(path)
        _validate_artifact(artifact, config, key)
        estimate = artifact["estimate"]
        if estimate["replica"] != replica_index:
            raise ValueError(f"{key} contains the wrong replica index")
        if estimate["widths"] != config["widths"]:
            raise ValueError(f"{key} width list does not match the manifest")
        replicas.append(artifact)
        negative_bonds += estimate["negative_bonds"]
        total_bonds += estimate["total_bonds"]

    block_counts = {len(artifact["estimate"]["blocks"]) for artifact in replicas}
    if len(block_counts) != 1 or not block_counts or next(iter(block_counts)) == 0:
        raise ValueError("replicas must contain the same positive number of blocks")
    block_count = next(iter(block_counts))
    tensor = np.empty((expected_replicas, block_count, len(widths)), dtype=float)
    for replica_index, artifact in enumerate(replicas):
        blocks = artifact["estimate"]["blocks"]
        for block_index, block in enumerate(blocks):
            if block["block_index"] != block_index:
                raise ValueError("block indices must be contiguous and ordered")
            values = np.asarray(block["phi_by_width"], dtype=float)
            if values.shape != widths.shape or not np.all(np.isfinite(values)):
                raise ValueError("each block must contain one finite value per width")
            tensor[replica_index, block_index] = values

    return LoadedRun(
        run_dir=run_dir,
        manifest=manifest,
        config=config,
        oracle=oracle,
        replicas=replicas,
        widths=widths,
        block_tensor=tensor,
        negative_bonds=negative_bonds,
        total_bonds=total_bonds,
    )


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"failed to read valid JSON from {path}: {error}") from error


def _verify_hash(path: Path, manifest: dict, key: str) -> None:
    expected = manifest.get("artifact_sha256", {}).get(key)
    if expected is None:
        raise ValueError(f"manifest is missing SHA-256 for {key}")
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"SHA-256 mismatch for {key}: {observed} != {expected}")


def _validate_artifact(artifact: dict, config: dict, label: str) -> None:
    if artifact.get("schema_version") != 1:
        raise ValueError(f"{label} schema_version must equal 1")
    if artifact.get("config") != config:
        raise ValueError(f"{label} configuration does not match the manifest")
