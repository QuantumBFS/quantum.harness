import unittest

from algebraic_ttn import (
    SparseTensor,
    build_copy_absorbed_network,
    build_pair_factor_network,
    contract,
    greedy_contract,
    greedy_hyper_contract,
)


class GenericTensorTests(unittest.TestCase):
    @staticmethod
    def _tree_topology(tree: dict) -> tuple:
        if tree["type"] == "leaf":
            return ("leaf", tree["name"], tuple(tree["indices"]))
        return (
            tree["type"],
            tuple(tree["matched_indices"]),
            tuple(tree["summed_indices"]),
            tuple(tree["output_indices"]),
            GenericTensorTests._tree_topology(tree["left"]),
            GenericTensorTests._tree_topology(tree["right"]),
        )

    def test_matrix_product_is_exact(self) -> None:
        left = SparseTensor(
            name="left",
            labels=("i", "k"),
            dimensions=(2, 2),
            data={(0, 0): 1, (0, 1): 2, (1, 1): 3},
            tree={"type": "leaf"},
        )
        right = SparseTensor(
            name="right",
            labels=("k", "j"),
            dimensions=(2, 2),
            data={(0, 0): 4, (1, 0): 5, (1, 1): 6},
            tree={"type": "leaf"},
        )
        result, operations = contract(left, right, name="product")
        self.assertEqual(result.labels, ("i", "j"))
        self.assertEqual(
            result.data,
            {(0, 0): 14, (0, 1): 12, (1, 0): 15, (1, 1): 18},
        )
        self.assertEqual(operations, 5)

    def test_fixed_n4_network_contracts_to_two(self) -> None:
        scalar, _tree, stats = greedy_contract(build_pair_factor_network(4))
        self.assertEqual(scalar, 2)
        self.assertGreater(stats["contractions"], 0)

    def test_copy_absorbed_n4_network_contracts_to_two(self) -> None:
        scalar, _tree, stats = greedy_hyper_contract(
            build_copy_absorbed_network(4)
        )
        self.assertEqual(scalar, 2)
        self.assertLessEqual(stats["max_intermediate_rank"], 3)

    def test_hypergraph_planner_is_value_blind(self) -> None:
        original = build_copy_absorbed_network(5)
        altered = [
            SparseTensor(
                name=tensor.name,
                labels=tensor.labels,
                dimensions=tensor.dimensions,
                data=(
                    {next(iter(tensor.data)): index + 2}
                    if tensor.data
                    else {}
                ),
                tree=tensor.tree,
            )
            for index, tensor in enumerate(original)
        ]
        _, original_tree, _ = greedy_hyper_contract(original)
        _, altered_tree, _ = greedy_hyper_contract(altered)
        self.assertEqual(
            self._tree_topology(original_tree),
            self._tree_topology(altered_tree),
        )


if __name__ == "__main__":
    unittest.main()
