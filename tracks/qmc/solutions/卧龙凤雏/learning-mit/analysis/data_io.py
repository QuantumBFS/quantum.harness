"""Strict loading and validation of frozen Rust trajectory artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


StreamKey = tuple[str, float, float, int, int]


@dataclass(frozen=True)
class EntropyPoint:
    interval_sites: int
    entropy: float


@dataclass(frozen=True)
class CorrelationPoint:
    distance: int
    connected_parity: float


@dataclass(frozen=True)
class BlockRecord:
    block_index: int
    gamma: float
    half_chain_entropy: float
    entropy_arc: tuple[EntropyPoint, ...]
    spatial_correlations: tuple[CorrelationPoint, ...]
    lyapunov: tuple[float, ...]
    min_probability: float
    max_antisymmetry_error: float
    max_purity_error: float


@dataclass(frozen=True)
class LoadedStream:
    stage_index: int
    angle_index: int
    stage_name: str
    theta_pi: float
    phi_pi: float
    width: int
    stream: int
    seed: int
    mode: str
    is_physical: bool
    blocks: tuple[BlockRecord, ...]


@dataclass(frozen=True)
class LoadedRun:
    run_dir: Path
    manifest: Mapping[str, Any]
    streams: Mapping[StreamKey, LoadedStream]


def load_run(run_dir: Path) -> LoadedRun:
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema version")
    config = manifest.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("stages"), list):
        raise ValueError("manifest configuration is malformed")

    hashes = manifest.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("manifest artifact hashes are malformed")
    for relative, expected in hashes.items():
        path = run_dir / relative
        if not path.is_file():
            raise ValueError(f"hashed artifact is missing: {relative}")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch for {relative}")

    seed_records = {
        (
            record["stage"],
            record["angle"],
            record["width"],
            record["stream"],
            record["purpose"],
        ): record["seed"]
        for record in manifest.get("seeds", [])
    }
    streams: dict[StreamKey, LoadedStream] = {}
    for task in manifest.get("tasks", []):
        if task.get("state") != "completed":
            continue
        relative = task.get("artifact")
        if not isinstance(relative, str) or not relative.startswith("raw/streams/"):
            continue
        if relative not in hashes:
            raise ValueError(f"completed stream lacks SHA-256: {relative}")
        artifact = _read_json(run_dir / relative)
        loaded = _validate_stream(artifact, config, seed_records)
        key = (
            loaded.stage_name,
            loaded.theta_pi,
            loaded.phi_pi,
            loaded.width,
            loaded.stream,
        )
        if key in streams:
            raise ValueError(f"duplicate stream coordinate: {key}")
        streams[key] = loaded

    return LoadedRun(
        run_dir=run_dir.resolve(),
        manifest=MappingProxyType(manifest),
        streams=MappingProxyType(streams),
    )


def _validate_stream(
    artifact: dict[str, Any],
    config: dict[str, Any],
    seed_records: dict[tuple[int, int, int, int, int], int],
) -> LoadedStream:
    if artifact.get("schema_version") != 1:
        raise ValueError("stream schema version is incompatible")
    estimate = artifact.get("estimate")
    if not isinstance(estimate, dict):
        raise ValueError("stream estimate is malformed")
    stage_index = _integer(estimate, "stage_index")
    angle_index = _integer(estimate, "angle_index")
    stages = config["stages"]
    if not 0 <= stage_index < len(stages):
        raise ValueError("stream stage is outside the configuration")
    stage = stages[stage_index]
    if artifact.get("stage_config") != stage:
        raise ValueError("stream stage configuration differs from the manifest")
    phi_values = stage["phi_pi"]
    if not 0 <= angle_index < len(phi_values):
        raise ValueError("stream angle is outside the stage")

    width = _integer(estimate, "width")
    stream_index = _integer(estimate, "stream")
    theta_pi = _finite(artifact.get("theta_pi"), "theta_pi")
    phi_pi = _finite(artifact.get("phi_pi"), "phi_pi")
    if (
        artifact.get("stage_name") != stage["name"]
        or theta_pi != stage["theta_pi"]
        or phi_pi != phi_values[angle_index]
        or width not in stage["widths"]
        or not 0 <= stream_index < stage["streams"]
    ):
        raise ValueError("stream coordinates differ from the manifest configuration")

    mode = estimate.get("mode")
    is_physical = estimate.get("is_physical")
    if mode != "born" or is_physical is not True:
        raise ValueError("frozen physical analysis accepts only Born-mode streams")
    seed = _integer(estimate, "seed")
    expected_seed = _derive_seed(
        config["base_seed"], stage_index, angle_index, width, stream_index, 0x424F524E
    )
    recorded_seed = seed_records.get(
        (stage_index, angle_index, width, stream_index, 0x424F524E)
    )
    if seed != expected_seed or recorded_seed != expected_seed:
        raise ValueError("stream seed does not match deterministic seed records")

    raw_blocks = estimate.get("blocks")
    expected_blocks = (
        stage["measurement_layers_per_width"] // stage["block_layers_per_width"]
    )
    if not isinstance(raw_blocks, list) or len(raw_blocks) != expected_blocks:
        raise ValueError("stream does not contain complete blocks")
    tolerance = _finite(config["invariant_tolerance"], "invariant tolerance")
    blocks = tuple(
        _validate_block(raw, index, width, tolerance)
        for index, raw in enumerate(raw_blocks)
    )
    return LoadedStream(
        stage_index=stage_index,
        angle_index=angle_index,
        stage_name=stage["name"],
        theta_pi=theta_pi,
        phi_pi=phi_pi,
        width=width,
        stream=stream_index,
        seed=seed,
        mode=mode,
        is_physical=is_physical,
        blocks=blocks,
    )


def _validate_block(
    raw: dict[str, Any], expected_index: int, width: int, tolerance: float
) -> BlockRecord:
    if raw.get("block_index") != expected_index:
        raise ValueError("stream block indices are not consecutive")
    gamma = _finite(raw.get("gamma"), "gamma")
    half_entropy = _finite(raw.get("half_chain_entropy"), "half-chain entropy")
    probability = _finite(raw.get("min_probability"), "minimum probability")
    antisymmetry = _finite(
        raw.get("max_antisymmetry_error"), "antisymmetry invariant"
    )
    purity = _finite(raw.get("max_purity_error"), "purity invariant")
    if gamma < 0.0 or half_entropy < 0.0:
        raise ValueError("entropy observables must be non-negative")
    if not 0.0 < probability <= 1.0:
        raise ValueError("minimum Born probability is outside (0,1]")
    if antisymmetry < 0.0 or purity < 0.0 or max(antisymmetry, purity) > tolerance:
        raise ValueError("Gaussian invariant exceeds the configured tolerance")

    entropy_arc = tuple(
        EntropyPoint(
            interval_sites=_integer(point, "interval_sites"),
            entropy=_finite(point.get("entropy"), "arc entropy"),
        )
        for point in raw.get("entropy_arc", [])
    )
    if tuple(point.interval_sites for point in entropy_arc) != tuple(range(1, width)):
        raise ValueError("entropy arc does not cover every proper interval")
    correlations = tuple(
        CorrelationPoint(
            distance=_integer(point, "distance"),
            connected_parity=_finite(
                point.get("connected_parity"), "connected parity correlation"
            ),
        )
        for point in raw.get("spatial_correlations", [])
    )
    if tuple(point.distance for point in correlations) != tuple(
        range(1, width // 2 + 1)
    ):
        raise ValueError("spatial correlation distances are incomplete")
    lyapunov = tuple(_finite(value, "Lyapunov exponent") for value in raw.get("lyapunov", []))
    if len(lyapunov) != 2 * width:
        raise ValueError("Lyapunov spectrum has the wrong dimension")
    return BlockRecord(
        block_index=expected_index,
        gamma=gamma,
        half_chain_entropy=half_entropy,
        entropy_arc=entropy_arc,
        spatial_correlations=correlations,
        lyapunov=lyapunov,
        min_probability=probability,
        max_antisymmetry_error=antisymmetry,
        max_purity_error=purity,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"failed to load JSON artifact {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return value


def _integer(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _derive_seed(
    base: int, stage: int, angle: int, width: int, stream: int, purpose: int
) -> int:
    mask = (1 << 64) - 1
    value = base
    for coordinate in (stage, angle, width, stream, purpose):
        value ^= (coordinate + 0x9E3779B97F4A7C15) & mask
        value = _splitmix64(value)
    return value


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask
