"""Reproducible one-cell execution and fail-closed result manifests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .channels import ConfusionChannel, ErasureChannel
from .clean_ising import critical_ground_energy
from .nishimori import estimate_coupled_nishimori_free_energies
from .resolution import estimate_degraded_record_rates
from .schema import CellConfig, CellManifest
from .self_dual import estimate_coupled_gaussian_self_dual_record_rates


def _git_commit() -> str:
    declared = os.environ.get("CEFFFLOW_SOURCE_COMMIT")
    if declared is not None:
        if re.fullmatch(r"[0-9a-f]{40}", declared) is None:
            raise ValueError(
                "CEFFFLOW_SOURCE_COMMIT must be a 40-character lowercase "
                "Git commit"
            )
        return declared
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_blocks(path: Path, blocks: NDArray[np.float64]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".blocks-", suffix=".npz", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, blocks=np.asarray(blocks, dtype=float))
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, path)
        return digest
    finally:
        temporary.unlink(missing_ok=True)


def execute_cell(config: CellConfig) -> NDArray[np.float64]:
    """Execute one validated cell and return paired width blocks."""

    if config.model == "clean_ising":
        return critical_ground_energy(config.lengths)[None, :]
    if config.model == "nishimori":
        return estimate_coupled_nishimori_free_energies(
            config.lengths,
            rows=config.steps,
            burn_in=config.burn_in,
            block_size=config.block_size,
            seed=config.seed,
        ).blocks
    if config.channel.kind == "identity":
        return estimate_coupled_gaussian_self_dual_record_rates(
            config.lengths,
            steps=config.steps,
            burn_in=config.burn_in,
            block_size=config.block_size,
            seed=config.seed,
        ).blocks
    channel = (
        ErasureChannel(config.channel.parameter)
        if config.channel.kind == "erasure"
        else ConfusionChannel(config.channel.parameter)
    )
    return estimate_degraded_record_rates(
        config.lengths,
        channel,
        particles=config.particles,
        steps=config.steps,
        burn_in=config.burn_in,
        block_size=config.block_size,
        seed=config.seed,
    ).blocks


def run_cell(
    config: CellConfig,
    output_directory: str | Path,
    *,
    cell_id: str,
) -> CellManifest:
    """Execute a cell and atomically publish blocks then its manifest."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    try:
        blocks = execute_cell(config)
        finite = bool(np.all(np.isfinite(blocks)))
        if not finite:
            raise FloatingPointError("cell produced non-finite blocks")
        digest = _atomic_blocks(output / "blocks.npz", blocks)
        manifest = CellManifest(
            status="success",
            cell_id=cell_id,
            settings=config,
            provenance={"git_commit": _git_commit(), "numpy": np.__version__},
            normalization_ok=True,
            finite_blocks=True,
            blocks_sha256=digest,
        )
    except Exception as exc:
        manifest = CellManifest(
            status="failed",
            cell_id=cell_id,
            settings=config,
            provenance={"git_commit": _git_commit(), "numpy": np.__version__},
            normalization_ok=False,
            finite_blocks=False,
            blocks_sha256="0" * 64,
            error=f"{type(exc).__name__}: {exc}",
        )
        _atomic_json(manifest_path, manifest.model_dump(mode="json"))
        raise
    _atomic_json(manifest_path, manifest.model_dump(mode="json"))
    return manifest


def cell_from_run_spec(
    run_spec_path: str | Path,
    cell_id: str,
) -> tuple[CellConfig, Path]:
    """Resolve a cell and its result directory from a run specification."""

    path = Path(run_spec_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        cell for cell in payload["cells"] if str(cell["cell_id"]) == cell_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one cell named {cell_id!r}")
    declared_root = payload.get("result_root")
    if declared_root is None:
        root = (path.parent / "cells").resolve()
    else:
        root = Path(declared_root)
    if declared_root is not None and not root.is_absolute():
        root = (path.parent / root).resolve()
    cell = matches[0]
    settings = cell.get("settings")
    if settings is None:
        settings = cell.get("params", {}).get("settings")
    if settings is None:
        raise ValueError(f"cell {cell_id!r} does not contain settings")
    return CellConfig.model_validate(settings), root / cell_id
