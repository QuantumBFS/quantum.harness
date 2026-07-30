import unittest

try:
    from algebraic_ttn.compact import (
        build_compact_copy_absorbed_network,
        greedy_compact_hyper_contract,
    )
    from algebraic_ttn.packed import (
        PackedTensor,
        build_packed_copy_absorbed_network,
        choose_horizontal_reflection_row,
        greedy_packed_hyper_contract,
        with_horizontal_reflection_domain,
    )

    PACKED_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    PACKED_AVAILABLE = False

from algebraic_ttn import build_copy_absorbed_network, greedy_hyper_contract


@unittest.skipUnless(PACKED_AVAILABLE, "packed backend requires NumPy")
class PackedTensorTests(unittest.TestCase):
    @staticmethod
    def _tree_topology(tree: dict) -> tuple:
        if tree["type"] == "leaf":
            return ("leaf", tree["name"])
        return (
            tuple(tree["matched_indices"]),
            tuple(tree["summed_indices"]),
            tuple(tree["output_indices"]),
            PackedTensorTests._tree_topology(tree["left"]),
            PackedTensorTests._tree_topology(tree["right"]),
        )

    def test_packed_n4_matches_both_backends_and_tree(self) -> None:
        sparse_scalar, sparse_tree, _ = greedy_hyper_contract(
            build_copy_absorbed_network(4)
        )
        dense_scalar, dense_tree, _ = greedy_compact_hyper_contract(
            build_compact_copy_absorbed_network(4)
        )
        packed_scalar, packed_tree, _ = greedy_packed_hyper_contract(
            build_packed_copy_absorbed_network(4)
        )
        self.assertEqual((packed_scalar, dense_scalar), (sparse_scalar,) * 2)
        self.assertEqual(packed_tree, sparse_tree)
        self.assertEqual(packed_tree, dense_tree)

    def test_known_scalars_through_eight(self) -> None:
        expected = (1, 0, 0, 2, 10, 4, 40, 92)
        actual = tuple(
            greedy_packed_hyper_contract(
                build_packed_copy_absorbed_network(n)
            )[0]
            for n in range(1, 9)
        )
        self.assertEqual(actual, expected)

    def test_horizontal_reflection_domain_through_ten(self) -> None:
        expected = (0, 0, 2, 10, 4, 40, 92, 352, 724)
        actual = []
        for n in range(2, 11):
            tensors = build_packed_copy_absorbed_network(n)
            row = choose_horizontal_reflection_row(tensors, n)
            symmetric = with_horizontal_reflection_domain(tensors, n, row)
            scalar, symmetric_tree, _ = greedy_packed_hyper_contract(symmetric)
            _, baseline_tree, _ = greedy_packed_hyper_contract(tensors)
            self.assertEqual(
                self._tree_topology(symmetric_tree),
                self._tree_topology(baseline_tree),
            )
            actual.append(scalar)
        self.assertEqual(tuple(actual), expected)

    def test_symmetry_row_choice_is_value_blind(self) -> None:
        original = build_packed_copy_absorbed_network(10)
        altered = [
            PackedTensor(
                name=tensor.name,
                labels=tensor.labels,
                dimensions=tensor.dimensions,
                keys=tensor.keys[:1].copy(),
                values=tensor.values[:1].copy(),
                tree=tensor.tree,
            )
            for tensor in original
        ]
        self.assertEqual(
            choose_horizontal_reflection_row(original, 10),
            choose_horizontal_reflection_row(altered, 10),
        )

    def test_symmetry_factor_is_a_weighted_fundamental_domain(self) -> None:
        n = 10
        row = 1
        mirror = n - 1 - row
        tensors = with_horizontal_reflection_domain(
            build_packed_copy_absorbed_network(n), n, row
        )
        factor = next(
            tensor for tensor in tensors if tensor.name == f"PAIR_{row}_{mirror}"
        )
        self.assertTrue(((factor.keys // n) < (factor.keys % n)).all())
        self.assertTrue((factor.values == 2).all())


if __name__ == "__main__":
    unittest.main()
