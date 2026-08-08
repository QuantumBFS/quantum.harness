import unittest
from unittest.mock import patch

try:
    import numpy as np

    from algebraic_ttn.packed import (
        build_packed_copy_absorbed_network,
        greedy_packed_hyper_contract,
    )
    from algebraic_ttn.parity import (
        JoinBudgetExceeded,
        _equality_join_blocks,
        _equality_join_plan,
        build_parity_copy_absorbed_network,
        greedy_parity_hyper_contract,
    )

    PARITY_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    PARITY_AVAILABLE = False


@unittest.skipUnless(PARITY_AVAILABLE, "parity backend requires NumPy")
class ParityTensorTests(unittest.TestCase):
    @staticmethod
    def _tree_topology(tree: dict) -> tuple:
        if tree["type"] == "leaf":
            return ("leaf", tree["name"])
        return (
            tuple(tree["matched_indices"]),
            tuple(tree["summed_indices"]),
            tuple(tree["output_indices"]),
            ParityTensorTests._tree_topology(tree["left"]),
            ParityTensorTests._tree_topology(tree["right"]),
        )

    def test_parity_backend_matches_packed_through_ten(self) -> None:
        for n in range(1, 11):
            packed_scalar, packed_tree, packed_stats = (
                greedy_packed_hyper_contract(
                    build_packed_copy_absorbed_network(n)
                )
            )
            parity_scalar, parity_tree, parity_stats = (
                greedy_parity_hyper_contract(
                    build_parity_copy_absorbed_network(n)
                )
            )
            self.assertEqual(parity_scalar, packed_scalar)
            self.assertEqual(
                parity_stats["max_intermediate_full_nnz"],
                packed_stats["max_intermediate_nnz"],
            )
            self.assertEqual(
                self._tree_topology(parity_tree),
                self._tree_topology(packed_tree),
            )

    def test_even_n_leaves_have_exactly_half_the_full_entries(self) -> None:
        for tensor in build_parity_copy_absorbed_network(10):
            if tensor.rank:
                self.assertEqual(tensor.fixed_count, 0)
                self.assertEqual(2 * tensor.nnz, tensor.full_nnz)

    def test_budgeted_join_plan_is_reused_without_a_second_sort(self) -> None:
        left = np.array([2, 1, 2, 3], dtype=np.uint64)
        right = np.array([2, 2, 1, 3], dtype=np.uint64)
        with self.assertRaises(JoinBudgetExceeded) as context:
            _equality_join_plan(left, right, max_pairs=0)
        plan = context.exception.join_plan
        self.assertIsNotNone(plan)
        self.assertEqual(plan.pair_count, 6)
        with patch.object(
            np,
            "argsort",
            side_effect=AssertionError("join plan was sorted twice"),
        ):
            blocks = list(
                _equality_join_blocks(
                    np.empty(0, dtype=np.uint64),
                    np.empty(0, dtype=np.uint64),
                    max_block_pairs=2,
                    plan=plan,
                )
            )
        pairs = [
            (int(left[left_row]), int(right[right_row]))
            for left_rows, right_rows in blocks
            for left_row, right_row in zip(left_rows, right_rows)
        ]
        self.assertEqual(len(pairs), 6)
        self.assertTrue(
            all(
                left_key == right_key
                for left_key, right_key in pairs
            )
        )


if __name__ == "__main__":
    unittest.main()
