import pathlib
import sys
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pattern_analysis.models import (  # noqa: E402
    fit_shallow_tree,
    fit_sparse_logistic,
    grouped_fold,
    precision_recall_auc,
    roc_auc,
)


class SparseLogisticTest(unittest.TestCase):
    def test_sparse_logistic_selects_inserted_binary_rule(self):
        rng = np.random.default_rng(7)
        features = rng.integers(0, 2, size=(800, 6)).astype(float)
        labels = (features[:, 2] == 1).astype(float)

        model = fit_sparse_logistic(features, labels, l1=0.02)
        probability = model.predict_probability(features)

        self.assertEqual(np.argmax(np.abs(model.coefficients)), 2)
        self.assertGreater(roc_auc(labels, probability), 0.95)
        self.assertGreater(precision_recall_auc(labels, probability), 0.95)

    def test_auc_metrics_give_one_for_perfect_ordering(self):
        labels = np.array([0, 1, 0, 1], dtype=float)
        scores = np.array([0.1, 0.9, 0.2, 0.8])

        self.assertAlmostEqual(roc_auc(labels, scores), 1.0)
        self.assertAlmostEqual(precision_recall_auc(labels, scores), 1.0)


class ShallowTreeTest(unittest.TestCase):
    def test_shallow_tree_recovers_two_feature_and_rule(self):
        patterns = np.array(
            [[(value >> bit) & 1 for bit in range(8)] for value in range(256)],
            dtype=float,
        )
        features = np.repeat(patterns, 4, axis=0)
        labels = (
            (features[:, 3] == 1) & (features[:, 7] == 1)
        ).astype(float)
        names = [f"bit_{index}" for index in range(8)]

        tree = fit_shallow_tree(
            features,
            labels,
            names,
            max_depth=2,
            min_leaf=20,
        )

        self.assertEqual(set(tree.used_features()), {"bit_3", "bit_7"})
        self.assertGreater(
            roc_auc(labels, tree.predict_probability(features)), 0.99
        )
        self.assertIn("bit_3", tree.to_rules())
        self.assertIn("bit_7", tree.to_rules())


class GroupedSplitTest(unittest.TestCase):
    def test_symmetry_orbit_never_crosses_folds(self):
        config_ids = np.array([0, 1, 2, 3, 4, 5], dtype=np.uint64)
        orbit_ids = np.array([10, 10, 20, 20, 30, 40], dtype=np.uint64)

        folds = grouped_fold(config_ids, orbit_ids, folds=3)

        self.assertEqual(folds[0], folds[1])
        self.assertEqual(folds[2], folds[3])
        self.assertTrue(np.all((folds >= 0) & (folds < 3)))


if __name__ == "__main__":
    unittest.main()
