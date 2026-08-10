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
    widths: np.ndarray
    gamma_blocks: dict[int, np.ndarray]
    electric_counts: dict[int, np.ndarray]
    magnetic_counts: dict[int, np.ndarray]
    face_counts: dict[int, np.ndarray]
    min_probabilities: dict[int, np.ndarray]
    invariant_errors: dict[int, np.ndarray]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_run(run_dir: Path) -> LoadedRun:
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    if manifest.get("schema_version") != 3:
        raise ValueError("manifest schema_version must equal 3")
    config = manifest["config"]
    widths = np.asarray(config["widths"], dtype=int)
    if len(widths) == 0 or np.any(np.diff(widths) <= 0):
        raise ValueError("manifest widths must be nonempty and increasing")
    stream_count = int(config["sampling"]["streams_per_width"])
    hashes = manifest.get("artifact_sha256", {})

    oracle_path = run_dir / "raw/oracles.json"
    _verify_hash(oracle_path, hashes.get("oracles"), "oracles")
    oracle = _read_json(oracle_path)
    if oracle.get("schema_version") != 3 or oracle.get("config") != config:
        raise ValueError("oracle artifact is incompatible with the manifest")

    fields = {
        "gamma": {},
        "electric_count": {},
        "magnetic_count": {},
        "faces_per_species": {},
        "min_probability": {},
        "max_invariant_error": {},
    }
    expected_blocks = None
    for width in widths:
        rows = {name: [] for name in fields}
        for stream in range(stream_count):
            key = f"stream-L{int(width):02}-{stream:03}"
            path = run_dir / "raw/streams" / f"{key}.json"
            _verify_hash(path, hashes.get(key), key)
            artifact = _read_json(path)
            estimate = artifact.get("estimate", {})
            if (
                artifact.get("schema_version") != 3
                or artifact.get("config") != config
                or estimate.get("width") != int(width)
                or estimate.get("stream") != stream
                or estimate.get("sector_wilson_loop") != 1
                or estimate.get("sector_fermion_parity") != 1
            ):
                raise ValueError(f"{key} is incompatible with the manifest")
            blocks = estimate.get("blocks", [])
            if not blocks:
                raise ValueError(f"{key} contains no blocks")
            if [row.get("block_index") for row in blocks] != list(range(len(blocks))):
                raise ValueError(f"{key} block indices are not consecutive")
            if expected_blocks is None:
                expected_blocks = len(blocks)
            if len(blocks) != expected_blocks:
                raise ValueError("all stream artifacts must contain the same block count")
            for name in fields:
                values = np.asarray([row[name] for row in blocks], dtype=float)
                if not np.all(np.isfinite(values)):
                    raise ValueError(f"{key} contains non-finite {name}")
                rows[name].append(values)
        for name in fields:
            fields[name][int(width)] = np.stack(rows[name])

    for width in widths:
        if np.any(fields["gamma"][int(width)] <= 0):
            raise ValueError("gamma blocks must be positive")
        if np.any(fields["faces_per_species"][int(width)] <= 0):
            raise ValueError("vortex face denominators must be positive")
        probabilities = fields["min_probability"][int(width)]
        if np.any((probabilities <= 0) | (probabilities > 1)):
            raise ValueError("recorded probabilities must lie in (0,1]")

    return LoadedRun(
        run_dir=run_dir,
        manifest=manifest,
        config=config,
        oracle=oracle,
        widths=widths,
        gamma_blocks=fields["gamma"],
        electric_counts=fields["electric_count"],
        magnetic_counts=fields["magnetic_count"],
        face_counts=fields["faces_per_species"],
        min_probabilities=fields["min_probability"],
        invariant_errors=fields["max_invariant_error"],
    )


def _verify_hash(path: Path, expected: str | None, label: str) -> None:
    if expected is None:
        raise ValueError(f"manifest lacks SHA-256 for {label}")
    if not path.exists() or sha256_file(path) != expected:
        raise ValueError(f"SHA-256 mismatch for {label}")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"failed to read JSON {path}") from error
