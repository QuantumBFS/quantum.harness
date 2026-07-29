"""Atomic, pickle-free checkpoints for stochastic transfer calculations."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .blocking import StreamingBlockAccumulator
from .lyapunov import LyapunovQR
from .rng import export_rng_state, restore_rng_state


@dataclass(frozen=True)
class CheckpointBundle:
    rng: np.random.Generator
    blocks: StreamingBlockAccumulator
    lyapunov: LyapunovQR
    gaussian_state: NDArray[np.float64] | NDArray[np.complex128] | None
    extra: dict[str, Any]


def _json_bytes(payload: dict[str, Any]) -> NDArray[np.uint8]:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return np.frombuffer(encoded, dtype=np.uint8)


def _decode_json(array: NDArray[np.uint8]) -> dict[str, Any]:
    payload = json.loads(np.asarray(array, dtype=np.uint8).tobytes().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("checkpoint metadata must decode to an object")
    return payload


def save_checkpoint(
    path: str | Path,
    *,
    rng: np.random.Generator,
    blocks: StreamingBlockAccumulator,
    lyapunov: LyapunovQR,
    gaussian_state: NDArray[np.floating] | NDArray[np.complexfloating] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    block_metadata, block_arrays = blocks.export_state()
    lyapunov_metadata, lyapunov_arrays = lyapunov.export_state()
    has_gaussian_state = gaussian_state is not None
    gaussian_array = (
        np.asarray(gaussian_state)
        if has_gaussian_state
        else np.empty((0,), dtype=np.float64)
    )
    if has_gaussian_state and not np.all(np.isfinite(gaussian_array)):
        raise ValueError("gaussian_state must be finite")
    metadata = {
        "schema_version": 1,
        "rng": export_rng_state(rng),
        "blocks": block_metadata,
        "lyapunov": lyapunov_metadata,
        "has_gaussian_state": has_gaussian_state,
        "extra": {} if extra is None else extra,
    }
    metadata_array = _json_bytes(metadata)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            np.savez_compressed(
                handle,
                metadata=metadata_array,
                block_current_sum=block_arrays["current_sum"],
                block_completed=block_arrays["completed_blocks"],
                lyapunov_basis=lyapunov_arrays["basis"],
                lyapunov_log_diagonal=lyapunov_arrays["log_diagonal"],
                gaussian_state=gaussian_array,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_checkpoint(path: str | Path) -> CheckpointBundle:
    source = Path(path)
    with np.load(source, allow_pickle=False) as archive:
        required = {
            "metadata",
            "block_current_sum",
            "block_completed",
            "lyapunov_basis",
            "lyapunov_log_diagonal",
            "gaussian_state",
        }
        missing = required.difference(archive.files)
        if missing:
            raise ValueError(f"checkpoint is missing arrays: {sorted(missing)}")
        metadata = _decode_json(archive["metadata"])
        if metadata.get("schema_version") != 1:
            raise ValueError("unsupported checkpoint schema_version")
        rng = restore_rng_state(metadata["rng"])
        blocks = StreamingBlockAccumulator.from_state(
            metadata["blocks"],
            archive["block_current_sum"],
            archive["block_completed"],
        )
        lyapunov = LyapunovQR.from_state(
            metadata["lyapunov"],
            archive["lyapunov_basis"],
            archive["lyapunov_log_diagonal"],
        )
        gaussian_state = (
            archive["gaussian_state"].copy()
            if metadata["has_gaussian_state"]
            else None
        )
        extra = metadata.get("extra", {})
        if not isinstance(extra, dict):
            raise ValueError("checkpoint extra metadata must be an object")
    return CheckpointBundle(
        rng=rng,
        blocks=blocks,
        lyapunov=lyapunov,
        gaussian_state=gaussian_state,
        extra=extra,
    )
