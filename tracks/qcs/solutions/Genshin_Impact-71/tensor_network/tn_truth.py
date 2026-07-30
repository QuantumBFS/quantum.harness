#!/usr/bin/env python3
"""Independent full-domain truth evaluator for issue 71.

This module is intentionally absent from train_mps.py and rank_diag.py.  It is
used only after a model artifact has been frozen.
"""

from __future__ import annotations

import numpy as np

from tn_common import INSTANCE_SPECS


FAMILIES = {
    "practice-add-n4": "add",
    "practice-mul-n4": "mul",
    "mystery-A": "add",
    "mystery-B": "absdiff",
    "mystery-C": "mul",
    "mystery-D": "sos",
}


def enumerate_full_domain(instance: str) -> tuple[np.ndarray, np.ndarray]:
    if instance not in INSTANCE_SPECS or instance not in FAMILIES:
        raise ValueError(f"unknown instance {instance!r}")
    n = int(INSTANCE_SPECS[instance]["n"])
    m = int(INSTANCE_SPECS[instance]["m"])
    indices = np.arange(2 ** (2 * n), dtype=np.uint64)
    mask = np.uint64((1 << n) - 1)
    x_values = indices & mask
    y_values = indices >> np.uint64(n)
    family = FAMILIES[instance]
    if family == "add":
        outputs = x_values + y_values
    elif family == "mul":
        outputs = x_values * y_values
    elif family == "absdiff":
        outputs = np.where(x_values >= y_values, x_values - y_values, y_values - x_values)
    elif family == "sos":
        outputs = x_values * x_values + y_values * y_values
    else:
        raise AssertionError(family)
    x_bits = np.column_stack(
        [((indices >> np.uint64(bit)) & np.uint64(1)).astype(np.int8)
         for bit in range(2 * n)]
    )
    y_bits = np.column_stack(
        [((outputs >> np.uint64(bit)) & np.uint64(1)).astype(np.int8)
         for bit in range(m)]
    )
    return x_bits, y_bits


def tt_rank_vectors(
    values: np.ndarray, order: list[int], tolerance_scale: float = 1e-10
) -> list[list[int]]:
    """Exact numerical real TT ranks of complete scalar truth tensors.

    Returns one cut-rank vector per output channel.  Values may be Boolean 0/1
    or signed -1/+1.  The largest matrix here is only 256 by 256.
    """
    if values.ndim != 2 or len(order) == 0:
        raise ValueError("expected rows-by-output values and a nonempty order")
    n_sites = len(order)
    if values.shape[0] != 2**n_sites:
        raise ValueError("full-domain row count mismatch")
    rank_vectors: list[list[int]] = []
    for output_index in range(values.shape[1]):
        original_axes = values[:, output_index].reshape((2,) * n_sites, order="F")
        ordered_tensor = np.transpose(original_axes, axes=order)
        cut_ranks: list[int] = []
        for cut in range(1, n_sites):
            matrix = ordered_tensor.reshape(2**cut, 2 ** (n_sites - cut))
            singular_values = np.linalg.svd(matrix, compute_uv=False)
            threshold = (
                tolerance_scale
                * max(matrix.shape)
                * (float(singular_values[0]) if singular_values.size else 0.0)
            )
            cut_ranks.append(int(np.count_nonzero(singular_values > threshold)))
        rank_vectors.append(cut_ranks)
    return rank_vectors
