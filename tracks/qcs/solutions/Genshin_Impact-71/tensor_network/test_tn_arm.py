#!/usr/bin/env python3
"""Small deterministic unit tests for the self-written TN arm."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from tn_common import (
    initialize_mps,
    load_models,
    load_train_csv,
    predict_scores,
    rank_profile,
    save_models,
    variable_order,
)
from tn_truth import enumerate_full_domain, tt_rank_vectors


class TensorArmTests(unittest.TestCase):
    def test_orders_are_permutations(self) -> None:
        for n in (1, 4, 8):
            for name in (
                "blocked_lsb",
                "blocked_msb",
                "interleaved_lsb",
                "interleaved_msb",
            ):
                self.assertEqual(sorted(variable_order(n, name)), list(range(2 * n)))

    def test_rank_profile_respects_binary_caps(self) -> None:
        self.assertEqual(rank_profile(4, 99), [1, 2, 4, 2, 1])
        self.assertEqual(rank_profile(5, 2), [1, 2, 2, 2, 2, 1])

    def test_strict_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.csv"
            path.write_text("input,output\n00000000,00000\n", encoding="ascii")
            x_bits, y_bits = load_train_csv(path, "practice-add-n4")
            self.assertEqual(x_bits.shape, (1, 8))
            self.assertEqual(y_bits.shape, (1, 5))
            path.write_text("input,output\n0000000X,00000\n", encoding="ascii")
            with self.assertRaises(ValueError):
                load_train_csv(path, "practice-add-n4")

    def test_model_round_trip_preserves_scores(self) -> None:
        rng = np.random.default_rng(42)
        cores = initialize_mps(4, 2, rng)
        x_bits = np.asarray(
            [[(row >> bit) & 1 for bit in range(4)] for row in range(16)],
            dtype=np.int8,
        )
        expected = predict_scores(cores, x_bits)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.npz"
            metadata = {"n_outputs": 1, "n_sites": 4}
            save_models(path, metadata, [cores])
            loaded = load_models(path)
            np.testing.assert_allclose(
                expected, predict_scores(loaded.models[0], x_bits)
            )

    def test_truth_encoding(self) -> None:
        x_bits, outputs = enumerate_full_domain("practice-add-n4")
        self.assertEqual(x_bits.shape, (256, 8))
        self.assertEqual(outputs.shape, (256, 5))
        # index = x + 16*y; x=13, y=4
        index = 13 + 16 * 4
        self.assertEqual(
            sum(int(outputs[index, bit]) << bit for bit in range(5)), 17
        )

    def test_add_interleaved_exact_rank_is_small(self) -> None:
        _, outputs = enumerate_full_domain("practice-add-n4")
        order = variable_order(4, "interleaved_lsb")
        ranks = tt_rank_vectors(outputs.astype(np.float64), order)
        self.assertLessEqual(max(max(vector) for vector in ranks), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
