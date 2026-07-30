import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from algebraic_ttn.block_reduction import (
    CuPyBlockReducer,
    NumPyBlockReducer,
    create_block_reducer,
)
from algebraic_ttn.gpu_join import GroupedParityJoinBatch


class ExactBlockReductionTests(unittest.TestCase):
    def test_numpy_reducer_sorts_and_sums_equal_keys(self) -> None:
        reducer = NumPyBlockReducer()
        keys = np.array([9, 2, 9, 4, 2, 2], dtype=np.uint64)
        values = np.array([3, 5, 7, 11, 13, 17], dtype=np.uint64)
        result_keys, result_values = reducer.reduce(keys, values)
        np.testing.assert_array_equal(
            result_keys, np.array([2, 4, 9], dtype=np.uint64)
        )
        np.testing.assert_array_equal(
            result_values, np.array([35, 11, 10], dtype=np.uint64)
        )
        self.assertEqual(reducer.statistics.calls, 1)
        self.assertEqual(reducer.statistics.input_records, 6)
        self.assertEqual(reducer.statistics.output_records, 3)
        self.assertGreaterEqual(reducer.statistics.seconds, 0.0)

    def test_empty_block_is_well_formed(self) -> None:
        reducer = NumPyBlockReducer()
        keys, values = reducer.reduce(
            np.empty(0, dtype=np.uint64),
            np.empty(0, dtype=np.uint64),
        )
        self.assertEqual(keys.dtype, np.uint64)
        self.assertEqual(values.dtype, np.uint64)
        self.assertEqual(keys.size, 0)
        self.assertEqual(values.size, 0)

    def test_invalid_input_is_rejected(self) -> None:
        reducer = NumPyBlockReducer()
        with self.assertRaises(ValueError):
            reducer.reduce(
                np.array([1], dtype=np.uint32),
                np.array([1], dtype=np.uint64),
            )
        with self.assertRaises(ValueError):
            reducer.reduce(
                np.array([1], dtype=np.uint64),
                np.array([], dtype=np.uint64),
            )

    def test_factory_keeps_cuda_optional(self) -> None:
        reducer = create_block_reducer("numpy")
        self.assertEqual(reducer.statistics.backend, "numpy")
        with self.assertRaises(ValueError):
            create_block_reducer("unknown")

    def test_cuda_adapter_preserves_exact_reduction_contract(self) -> None:
        class FakeDevice:
            def __init__(self, device: int) -> None:
                self.device = device

            def use(self) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args) -> None:
                pass

        fake_cupy = SimpleNamespace(
            cuda=SimpleNamespace(
                Device=FakeDevice,
                runtime=SimpleNamespace(
                    getDeviceProperties=lambda device: {
                        "name": b"test-gpu"
                    }
                ),
            ),
            asarray=np.asarray,
            argsort=np.argsort,
            empty=np.empty,
            bool_=np.bool_,
            flatnonzero=np.flatnonzero,
            add=np.add,
            asnumpy=np.asarray,
        )
        with patch.dict(sys.modules, {"cupy": fake_cupy}):
            reducer = CuPyBlockReducer(3, min_gpu_records=0)
            keys, values = reducer.reduce(
                np.array([7, 1, 7, 1], dtype=np.uint64),
                np.array([2, 3, 5, 11], dtype=np.uint64),
            )
        np.testing.assert_array_equal(
            keys, np.array([1, 7], dtype=np.uint64)
        )
        np.testing.assert_array_equal(
            values, np.array([14, 7], dtype=np.uint64)
        )
        self.assertEqual(reducer.statistics.backend, "cuda-cupy")
        self.assertIn("cuda:3:test-gpu", reducer.statistics.device)

    def test_multi_cuda_adapter_uses_disjoint_sorted_key_ranges(self) -> None:
        class FakeDevice:
            def __init__(self, device: int) -> None:
                self.device = device

            def use(self) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args) -> None:
                pass

        fake_cupy = SimpleNamespace(
            cuda=SimpleNamespace(
                Device=FakeDevice,
                runtime=SimpleNamespace(
                    getDeviceProperties=lambda device: {
                        "name": f"test-gpu-{device}".encode()
                    }
                ),
            ),
            asarray=np.asarray,
            argsort=np.argsort,
            empty=np.empty,
            bool_=np.bool_,
            flatnonzero=np.flatnonzero,
            add=np.add,
            asnumpy=np.asarray,
        )
        keys = np.array(
            [300, 1, 150, 300, 151, 2, 220, 1], dtype=np.uint64
        )
        values = np.array(
            [5, 7, 11, 13, 17, 19, 23, 29], dtype=np.uint64
        )
        expected = NumPyBlockReducer().reduce(keys, values)
        with patch.dict(sys.modules, {"cupy": fake_cupy}):
            reducer = create_block_reducer(
                "cuda",
                cuda_devices=(0, 1, 2),
                cuda_min_records=0,
                cuda_records_per_device=1,
            )
            actual = reducer.reduce(keys, values)
            reducer.close()
        np.testing.assert_array_equal(actual[0], expected[0])
        np.testing.assert_array_equal(actual[1], expected[1])
        self.assertEqual(reducer.statistics.backend, "cuda-cupy-multi")
        self.assertEqual(len(reducer.statistics.devices), 3)
        self.assertEqual(reducer.statistics.input_records, keys.size)

    def test_real_cuda_generates_grouped_cartesian_product_on_device(
        self,
    ) -> None:
        try:
            import cupy as cp

            if cp.cuda.runtime.getDeviceCount() == 0:
                self.skipTest("no CUDA device")
        except (ModuleNotFoundError, RuntimeError):
            self.skipTest("CuPy CUDA runtime is unavailable")
        batch = GroupedParityJoinBatch(
            anchor_keys=np.array([0, 1], dtype=np.uint64),
            anchor_values=np.array([2, 3], dtype=np.uint64),
            anchor_fixed=np.array([0, 0], dtype=np.uint8),
            other_keys=np.array([0, 1], dtype=np.uint64),
            other_values=np.array([5, 7], dtype=np.uint64),
            other_fixed=np.array([0, 0], dtype=np.uint8),
            other_reflected=np.array([0, 0], dtype=np.uint8),
            anchor_starts=np.array([0], dtype=np.uint64),
            anchor_counts=np.array([2], dtype=np.uint64),
            other_starts=np.array([0], dtype=np.uint64),
            other_counts=np.array([2], dtype=np.uint64),
            pair_begins=np.array([0], dtype=np.uint64),
            pair_offsets=np.array([0, 4], dtype=np.uint64),
            output_sources=np.array([0], dtype=np.uint8),
            output_strides=np.array([1], dtype=np.uint64),
            output_dimensions=np.array([2], dtype=np.uint64),
        )
        reducer = CuPyBlockReducer(0, min_gpu_records=0)
        keys, values, valid_count = (
            reducer.reduce_grouped_parity_join(batch)
        )
        np.testing.assert_array_equal(
            keys, np.array([0], dtype=np.uint64)
        )
        np.testing.assert_array_equal(
            values, np.array([60], dtype=np.uint64)
        )
        self.assertEqual(valid_count, 4)


if __name__ == "__main__":
    unittest.main()
