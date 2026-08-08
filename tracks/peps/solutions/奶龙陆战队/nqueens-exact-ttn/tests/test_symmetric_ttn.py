import unittest

try:
    from algebraic_ttn.packed import (
        build_packed_copy_absorbed_network,
        greedy_packed_hyper_contract,
    )
    from algebraic_ttn.symmetric import greedy_symmetric_packed_contract

    SYMMETRIC_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    SYMMETRIC_AVAILABLE = False


def _leaf_names(tree: dict) -> list[str]:
    if tree["type"] == "leaf":
        return [tree["name"]]
    return _leaf_names(tree["left"]) + _leaf_names(tree["right"])


@unittest.skipUnless(
    SYMMETRIC_AVAILABLE, "symmetric backend requires NumPy"
)
class SymmetricTensorTests(unittest.TestCase):
    def test_symmetric_dag_matches_baseline_through_ten(self) -> None:
        for n in range(1, 11):
            tensors = build_packed_copy_absorbed_network(n)
            baseline, _, baseline_stats = greedy_packed_hyper_contract(tensors)
            symmetric, tree, symmetric_stats = (
                greedy_symmetric_packed_contract(tensors, n)
            )
            self.assertEqual(symmetric, baseline)
            if n >= 8:
                self.assertLessEqual(
                    symmetric_stats["max_intermediate_rank"],
                    baseline_stats["max_intermediate_rank"],
                )
            self.assertCountEqual(
                _leaf_names(tree), [tensor.name for tensor in tensors]
            )

    def test_n10_reuses_mirrored_subtrees(self) -> None:
        _, _, stats = greedy_symmetric_packed_contract(
            build_packed_copy_absorbed_network(10), 10
        )
        self.assertGreaterEqual(stats["mirror_reuses"], 10)
        self.assertLess(
            stats["executed_contractions"],
            stats["conceptual_contractions"],
        )


if __name__ == "__main__":
    unittest.main()
