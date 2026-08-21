"""Tests for the spin-basis random-bond Ising row transfer."""

import importlib.util
import math
import sys
import unittest
from pathlib import Path

import numpy as np


_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent / "random_bond_ising_transfer.py"


def _load_module():
    if not _SCRIPT.exists():
        raise AssertionError(f"missing production module: {_SCRIPT}")
    spec = importlib.util.spec_from_file_location("random_bond_ising_transfer", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["random_bond_ising_transfer"] = module
    spec.loader.exec_module(module)
    return module


def _dense_row_transfer(L, coupling, horizontal, vertical):
    """Independent fixed-bond Boltzmann matrix, used only at small width."""
    states = np.arange(1 << L, dtype=np.uint64)
    bits = ((states[:, None] >> np.arange(L, dtype=np.uint64)) & 1).astype(float)
    spins = 2.0 * bits - 1.0
    horizontal_energy = np.sum(
        horizontal[None, :] * spins * np.roll(spins, -1, axis=1), axis=1
    )
    vertical_energy = (spins * vertical[None, :]) @ spins.T
    return np.exp(
        coupling * horizontal_energy[:, None] + coupling * vertical_energy
    )


class RandomBondRowActionTests(unittest.TestCase):
    def test_nishimori_coupling_satisfies_probability_identity(self):
        """Catches an inverted p convention or a missing factor of two."""
        module = _load_module()
        p = 0.1092212

        coupling = module.nishimori_coupling(p)

        self.assertAlmostEqual(
            math.exp(-2.0 * coupling), p / (1.0 - p), places=14
        )

    def test_matrix_free_fixed_row_matches_dense_oracle(self):
        """Catches wrong source/destination bonds or butterfly ordering."""
        module = _load_module()
        L = 4
        coupling = 0.73
        horizontal = np.array([1, -1, 1, -1], dtype=np.int8)
        vertical = np.array([-1, 1, 1, -1], dtype=np.int8)
        vector = np.arange(1, (1 << L) + 1, dtype=float) / 17.0
        expected = _dense_row_transfer(L, coupling, horizontal, vertical) @ vector

        actual = module.RandomBondRowTransfer(L, coupling).apply(
            vector, horizontal, vertical
        )

        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_rejects_invalid_probability_width_vector_and_bonds(self):
        """Catches silent acceptance of a different RBIM convention."""
        module = _load_module()
        with self.assertRaises(ValueError):
            module.nishimori_coupling(0.5)
        with self.assertRaises(ValueError):
            module.RandomBondRowTransfer(1, 0.4)
        operator = module.RandomBondRowTransfer(3, 0.4)
        with self.assertRaises(ValueError):
            operator.apply(np.ones(4), np.ones(3), np.ones(3))
        with self.assertRaises(ValueError):
            operator.apply(np.ones(8), np.array([1, 0, 1]), np.ones(3))


class RandomStripTests(unittest.TestCase):
    def test_fixed_count_rows_have_exact_antiferromagnetic_count(self):
        """Catches an IID sampler accidentally used for retained disorder."""
        module = _load_module()
        rng = np.random.default_rng(19)

        horizontal, vertical, antiferromagnetic = module.fixed_count_bond_rows(
            rng, L=5, retained_rows=37, p=0.1092212
        )

        self.assertEqual(horizontal.shape, (37, 5))
        self.assertEqual(vertical.shape, (37, 5))
        self.assertEqual(antiferromagnetic, round(0.1092212 * 2 * 5 * 37))
        self.assertEqual(
            int(
                np.count_nonzero(horizontal == -1)
                + np.count_nonzero(vertical == -1)
            ),
            antiferromagnetic,
        )
        self.assertTrue(np.all(np.isin(horizontal, (-1, 1))))
        self.assertTrue(np.all(np.isin(vertical, (-1, 1))))

    def test_fixed_count_strip_is_reproducible_and_reports_ensemble(self):
        """Catches lost seeds, wrong retained counts, or missing metadata."""
        module = _load_module()
        arguments = dict(
            L=4,
            p=0.1092212,
            seed=31,
            burn_in=8,
            retained_rows=40,
            block_length=10,
            progress=False,
        )

        first = module.run_fixed_count_strip(**arguments)
        second = module.run_fixed_count_strip(**arguments)

        np.testing.assert_array_equal(
            first["block_log_norm_means"], second["block_log_norm_means"]
        )
        self.assertEqual(first["disorder_ensemble"], "fixed_count")
        self.assertEqual(
            first["antiferromagnetic_bonds"],
            round(0.1092212 * 2 * 4 * 40),
        )
        self.assertEqual(first["total_retained_bonds"], 2 * 4 * 40)

    def test_random_strip_is_seed_reproducible_and_blocked(self):
        """Catches lost RNG control, burn-in leakage, or malformed blocks."""
        module = _load_module()
        self.assertTrue(hasattr(module, "run_random_strip"), "run_random_strip is missing")
        arguments = dict(
            L=3,
            p=0.1092212,
            seed=122,
            burn_in=6,
            retained_rows=24,
            block_length=8,
            progress=False,
        )

        first = module.run_random_strip(**arguments)
        second = module.run_random_strip(**arguments)

        np.testing.assert_array_equal(
            first["block_log_norm_means"], second["block_log_norm_means"]
        )
        self.assertEqual(len(first["block_log_norm_means"]), 3)
        self.assertTrue(math.isfinite(first["lyapunov"]))
        self.assertTrue(math.isfinite(first["free_energy"]))
        self.assertGreaterEqual(first["free_energy_se"], 0.0)

    def test_random_strip_rejects_incomplete_blocks(self):
        """Catches silently dropping retained rows from the error estimate."""
        module = _load_module()
        self.assertTrue(hasattr(module, "run_random_strip"), "run_random_strip is missing")
        with self.assertRaises(ValueError):
            module.run_random_strip(
                L=3,
                p=0.1,
                seed=1,
                burn_in=2,
                retained_rows=10,
                block_length=6,
                progress=False,
            )


if __name__ == "__main__":
    unittest.main()
