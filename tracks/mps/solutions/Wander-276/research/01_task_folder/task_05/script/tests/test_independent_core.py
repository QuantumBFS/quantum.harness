from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from lgeth.combinatorics import laughlin_zero_mode_count
from lgeth.jacobi import (
    haar_row_isometry,
    jacobi_parameters,
    normalized_curvature,
    sample_jacobi_interior,
)
from lgeth.channels import root_response_partition


SCRIPT_ROOT = Path(__file__).resolve().parents[1]


def test_task05_imports_are_isolated() -> None:
    for source in SCRIPT_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert all("task_04" not in module for module in modules)
            assert all("gaccess" not in module for module in modules)


def test_registered_rank_and_external_dimension() -> None:
    assert laughlin_zero_mode_count(3, 20) == 800
    partition = root_response_partition(3, 20)
    assert len(partition.zero_modes) == 800
    assert len(partition.descendant_external) == 680


def test_atom_multiplicity_and_interior_labels() -> None:
    parameters = jacobi_parameters(800, 680)
    assert parameters.plus_atoms == 120
    assert parameters.minus_atoms == 120
    assert parameters.interior_dimension == 560
    interior, labels = sample_jacobi_interior(8, 6, 3, 2026072801)
    assert interior.shape == (3, 4)
    assert labels.shape == (3, 8)
    assert np.all(labels.sum(axis=1) == 4)


def test_whitening_isometry_identity() -> None:
    rng = np.random.default_rng(2026072802)
    rows = haar_row_isometry(8, 20, rng)
    channel_v = rows[:, :10]
    channel_w = rows[:, 10:]
    normalized = normalized_curvature(channel_v, channel_w)
    assert normalized.rank == 8
    np.testing.assert_allclose(
        normalized.Y @ normalized.Y.conj().T,
        np.eye(8),
        atol=1e-10,
        rtol=0.0,
    )
