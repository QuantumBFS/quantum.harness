"""Tests for the exact clean-Ising matrix-free transfer operator."""

import csv
import importlib.util
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent / "clean_ising_transfer.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("clean_ising_transfer", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["clean_ising_transfer"] = module
    spec.loader.exec_module(module)
    return module


def _dense_transfer(L, kx, ktau):
    """Independent Boltzmann-form oracle, used only at small width."""
    states = np.arange(1 << L, dtype=np.uint64)
    bits = ((states[:, None] >> np.arange(L, dtype=np.uint64)) & 1).astype(float)
    spins = 2.0 * bits - 1.0
    horizontal = np.sum(spins * np.roll(spins, -1, axis=1), axis=1)
    vertical = spins @ spins.T
    return np.exp(
        0.5 * kx * (horizontal[:, None] + horizontal[None, :])
        + ktau * vertical
    )


class TransferActionTests(unittest.TestCase):
    def test_matrix_free_action_matches_dense_boltzmann_sum(self):
        """Catches a wrong bit axis, periodic bond, or D/V/D ordering."""
        if not _SCRIPT.exists():
            self.fail("scripts/clean_ising_transfer.py is missing")

        module = _load_module()
        L = 4
        k = 0.5 * math.log(1.0 + math.sqrt(2.0))
        dense = _dense_transfer(L, k, k)
        vector = np.arange(1, (1 << L) + 1, dtype=float) / (1 << L)

        operator = module.IsingTransferOperator(L, k, k)
        actual = operator @ vector
        expected = dense @ vector

        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_rejects_width_below_two(self):
        """Catches accidental construction of an ill-defined periodic row."""
        if not _SCRIPT.exists():
            self.fail("scripts/clean_ising_transfer.py is missing")
        module = _load_module()
        with self.assertRaises(ValueError):
            module.IsingTransferOperator(1, 0.4, 0.4)

    def test_rejects_wrong_vector_dimension(self):
        """Catches silent broadcasting of a boundary vector for another L."""
        if not _SCRIPT.exists():
            self.fail("scripts/clean_ising_transfer.py is missing")
        module = _load_module()
        operator = module.IsingTransferOperator(4, 0.4, 0.4)
        with self.assertRaises(ValueError):
            operator._matvec(np.ones(8))


if __name__ == "__main__":
    unittest.main()
