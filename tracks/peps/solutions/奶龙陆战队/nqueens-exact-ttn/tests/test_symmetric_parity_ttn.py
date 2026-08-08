import unittest

try:
    from algebraic_ttn.block_reduction import NumPyBlockReducer
    from algebraic_ttn.parity import (
        build_parity_copy_absorbed_network,
        greedy_parity_hyper_contract,
    )
    from algebraic_ttn.symmetric_parity import (
        SymmetricParityBudgetExceeded,
        greedy_symmetric_parity_contract,
    )

    COMBINED_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    COMBINED_AVAILABLE = False


@unittest.skipUnless(
    COMBINED_AVAILABLE, "combined symmetry backend requires NumPy"
)
class SymmetricParityTests(unittest.TestCase):
    def test_row_reflection_blocks_are_exact_through_eight(self) -> None:
        for n in range(4, 9):
            tensors = build_parity_copy_absorbed_network(n)
            expected, _, _ = greedy_symmetric_parity_contract(tensors, n)
            actual, _, stats = greedy_symmetric_parity_contract(
                tensors,
                n,
                planner_tie_break="symmetry-first",
                row_reflection_blocks=True,
            )
            self.assertEqual(actual, expected)
            self.assertGreater(stats["row_sector_compressions"], 0)
            self.assertLessEqual(
                stats["max_intermediate_stored_nnz"],
                stats["max_intermediate_even_sector_nnz"],
            )

    def test_disk_streaming_matches_in_memory_contraction(self) -> None:
        tensors = build_parity_copy_absorbed_network(6)
        expected, _, _ = greedy_symmetric_parity_contract(tensors, 6)
        for strategy in ("single-sort", "sorted-runs"):
            with self.subTest(strategy=strategy):
                actual, _, stats = greedy_symmetric_parity_contract(
                    tensors,
                    6,
                    join_chunk_pairs=7,
                    streaming_merge_strategy=strategy,
                )
                self.assertEqual(actual, expected)
                self.assertGreater(stats["streaming_contractions"], 0)
                self.assertEqual(stats["block_reducer_backend"], "numpy")
                if strategy == "sorted-runs":
                    self.assertGreater(stats["block_reducer_calls"], 0)

    def test_explicit_block_reducer_accumulates_all_nodes(self) -> None:
        tensors = build_parity_copy_absorbed_network(6)
        reducer = NumPyBlockReducer()
        scalar, _, stats = greedy_symmetric_parity_contract(
            tensors,
            6,
            join_chunk_pairs=7,
            block_reducer=reducer,
        )
        self.assertEqual(scalar, 4)
        self.assertEqual(stats["block_reducer_backend"], "numpy")
        self.assertEqual(
            stats["block_reducer_calls"], reducer.statistics.calls
        )
        self.assertGreater(stats["block_reducer_input_records"], 0)

    def test_accelerator_reducer_uses_bounded_async_stream_pipeline(
        self,
    ) -> None:
        class AsyncReferenceReducer(NumPyBlockReducer):
            prefer_async = True

        tensors = build_parity_copy_absorbed_network(6)
        reducer = AsyncReferenceReducer()
        scalar, _, stats = greedy_symmetric_parity_contract(
            tensors,
            6,
            join_chunk_pairs=7,
            block_reducer=reducer,
        )
        self.assertEqual(scalar, 4)
        self.assertGreater(stats["block_reducer_async_submissions"], 0)
        self.assertEqual(
            stats["block_reducer_async_submissions"],
            reducer.statistics.async_submissions,
        )

    def test_join_budget_stops_before_large_materialization(self) -> None:
        tensors = build_parity_copy_absorbed_network(4)
        with self.assertRaises(SymmetricParityBudgetExceeded) as context:
            greedy_symmetric_parity_contract(
                tensors, 4, max_join_pairs=0
            )
        report = context.exception.report
        self.assertEqual(report["status"], "join_budget_exceeded")
        self.assertGreater(report["required_join_pairs"], 0)
        self.assertEqual(report["max_join_pairs_budget"], 0)

    def test_combined_backend_matches_parity_through_ten(self) -> None:
        for n in range(1, 11):
            tensors = build_parity_copy_absorbed_network(n)
            parity_scalar, _, _ = greedy_parity_hyper_contract(tensors)
            combined_scalar, _, stats = greedy_symmetric_parity_contract(
                tensors, n
            )
            self.assertEqual(combined_scalar, parity_scalar)
            if n >= 8:
                self.assertGreater(stats["mirror_reuses"], 0)


if __name__ == "__main__":
    unittest.main()
