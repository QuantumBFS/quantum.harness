from pathlib import Path

import numpy as np

from xxzcert.su2_reflection_benchmark import (
    load_candidate,
    save_candidate,
)
from xxzcert.lti_su2_reflection import SU2ReflectionLTICandidate


def test_candidate_round_trip_without_pickle(tmp_path: Path):
    candidate = SU2ReflectionLTICandidate(
        level=5,
        raw_lower=-0.46,
        status="optimal",
        solver="SCS",
        dual_trace=0.46,
        dual_cross_blocks=(np.zeros((1, 0)), np.ones((2, 1))),
        max_equality_residual=1e-9,
        minimum_block_eigenvalue=-1e-10,
        block_dimensions=((1, 0), (2, 1)),
        compatibility_shapes=((1, 0), (2, 1)),
    )
    path = tmp_path / "candidate.npz"
    save_candidate(
        path,
        candidate,
        elapsed_seconds=2.5,
        eps=1e-6,
        max_iters=1000,
        use_indirect=True,
    )
    loaded = load_candidate(path)
    assert loaded.level == candidate.level
    assert loaded.raw_lower == candidate.raw_lower
    assert loaded.block_dimensions == candidate.block_dimensions
    assert all(
        np.array_equal(left, right)
        for left, right in zip(
            loaded.dual_cross_blocks,
            candidate.dual_cross_blocks,
            strict=True,
        )
    )
