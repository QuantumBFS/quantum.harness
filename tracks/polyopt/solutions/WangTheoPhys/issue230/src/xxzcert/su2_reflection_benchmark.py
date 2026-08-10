"""Portable storage for joint SU(2)-reflection LTI candidates."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np

from .lti_su2_reflection import SU2ReflectionLTICandidate


def save_candidate(
    path: Path,
    candidate: SU2ReflectionLTICandidate,
    *,
    elapsed_seconds: float,
    eps: float,
    max_iters: int,
    use_indirect: bool,
) -> None:
    """Save arrays without pickle and metadata as a JSON scalar."""
    metadata = {
        "level": candidate.level,
        "raw_lower": candidate.raw_lower,
        "status": candidate.status,
        "solver": candidate.solver,
        "dual_trace": candidate.dual_trace,
        "max_equality_residual": candidate.max_equality_residual,
        "minimum_block_eigenvalue": candidate.minimum_block_eigenvalue,
        "block_dimensions": candidate.block_dimensions,
        "compatibility_shapes": candidate.compatibility_shapes,
        "elapsed_seconds": elapsed_seconds,
        "eps": eps,
        "max_iters": max_iters,
        "use_indirect": use_indirect,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    arrays: dict[str, np.ndarray] = {
        "metadata": np.asarray(json.dumps(metadata, sort_keys=True))
    }
    arrays.update(
        {
            f"dual_cross_{index}": block
            for index, block in enumerate(candidate.dual_cross_blocks)
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def load_candidate(path: Path) -> SU2ReflectionLTICandidate:
    """Load a candidate frozen by :func:`save_candidate`."""
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"]))
        duals = tuple(
            np.asarray(archive[f"dual_cross_{index}"], dtype=float)
            for index in range(len(metadata["compatibility_shapes"]))
        )
    return SU2ReflectionLTICandidate(
        level=int(metadata["level"]),
        raw_lower=float(metadata["raw_lower"]),
        status=str(metadata["status"]),
        solver=str(metadata["solver"]),
        dual_trace=float(metadata["dual_trace"]),
        dual_cross_blocks=duals,
        max_equality_residual=float(
            metadata["max_equality_residual"]
        ),
        minimum_block_eigenvalue=float(
            metadata["minimum_block_eigenvalue"]
        ),
        block_dimensions=tuple(
            tuple(map(int, dimensions))
            for dimensions in metadata["block_dimensions"]
        ),
        compatibility_shapes=tuple(
            tuple(map(int, dimensions))
            for dimensions in metadata["compatibility_shapes"]
        ),
    )
