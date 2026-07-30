import unittest

try:
    from algebraic_ttn.compact import (
        build_compact_copy_absorbed_network,
        greedy_compact_hyper_contract,
    )

    COMPACT_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    COMPACT_AVAILABLE = False

from algebraic_ttn import build_copy_absorbed_network, greedy_hyper_contract


@unittest.skipUnless(COMPACT_AVAILABLE, "compact backend requires NumPy")
class CompactTensorTests(unittest.TestCase):
    def test_compact_n4_matches_sparse_scalar_and_tree(self) -> None:
        sparse_scalar, sparse_tree, _ = greedy_hyper_contract(
            build_copy_absorbed_network(4)
        )
        compact_scalar, compact_tree, _ = greedy_compact_hyper_contract(
            build_compact_copy_absorbed_network(4)
        )
        self.assertEqual(compact_scalar, sparse_scalar)
        self.assertEqual(compact_tree, sparse_tree)

    def test_known_scalars_through_eight(self) -> None:
        expected = (1, 0, 0, 2, 10, 4, 40, 92)
        actual = tuple(
            greedy_compact_hyper_contract(
                build_compact_copy_absorbed_network(n)
            )[0]
            for n in range(1, 9)
        )
        self.assertEqual(actual, expected)

    def test_uint64_bound_is_enforced(self) -> None:
        with self.assertRaises(OverflowError):
            build_compact_copy_absorbed_network(16)


if __name__ == "__main__":
    unittest.main()
