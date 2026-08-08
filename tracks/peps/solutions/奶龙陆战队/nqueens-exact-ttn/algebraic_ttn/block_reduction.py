"""Exact key/value block aggregation backends.

The contraction algebra stays on the host for now.  This module isolates the
first GPU-ready primitive: sort uint64 key/value records and sum consecutive
equal keys exactly.  The NumPy backend is the reference implementation; the
optional CUDA backend uses CuPy without making it a CPU runtime dependency.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from math import ceil, prod
from time import perf_counter
from typing import Iterable, Iterator, Protocol

import numpy as np


class AcceleratorUnavailable(RuntimeError):
    """The requested optional accelerator backend cannot be constructed."""


@dataclass(slots=True)
class BlockReductionStatistics:
    backend: str
    device: str
    devices: tuple[str, ...] = ()
    calls: int = 0
    input_records: int = 0
    output_records: int = 0
    seconds: float = 0.0
    async_submissions: int = 0
    cpu_fallback_calls: int = 0
    cpu_fallback_records: int = 0
    gpu_device_dispatches: int = 0
    gpu_join_plan_calls: int = 0
    gpu_join_plan_input_records: int = 0
    gpu_join_plan_seconds: float = 0.0

    def as_dict(self) -> dict[str, str | int | float | list[str]]:
        return {
            "block_reducer_backend": self.backend,
            "block_reducer_device": self.device,
            "block_reducer_devices": list(self.devices or (self.device,)),
            "block_reducer_calls": self.calls,
            "block_reducer_input_records": self.input_records,
            "block_reducer_output_records": self.output_records,
            "block_reducer_seconds": self.seconds,
            "block_reducer_async_submissions": self.async_submissions,
            "block_reducer_cpu_fallback_calls": self.cpu_fallback_calls,
            "block_reducer_cpu_fallback_records": (
                self.cpu_fallback_records
            ),
            "block_reducer_gpu_device_dispatches": (
                self.gpu_device_dispatches
            ),
            "gpu_join_plan_calls": self.gpu_join_plan_calls,
            "gpu_join_plan_input_records": (
                self.gpu_join_plan_input_records
            ),
            "gpu_join_plan_seconds": self.gpu_join_plan_seconds,
        }


class ExactBlockReducer(Protocol):
    """Sort and exactly reduce one uint64 key/value contribution block."""

    statistics: BlockReductionStatistics

    def reduce(
        self, keys: np.ndarray, values: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return strictly increasing nonzero key/value records."""


def _validate_inputs(keys: np.ndarray, values: np.ndarray) -> None:
    if keys.dtype != np.uint64 or values.dtype != np.uint64:
        raise ValueError("block reduction requires uint64 keys and values")
    if keys.ndim != 1 or values.ndim != 1:
        raise ValueError("block reduction inputs must be vectors")
    if keys.size != values.size:
        raise ValueError("block reduction keys and values differ in length")


class NumPyBlockReducer:
    """Reference exact CPU implementation."""

    prefer_async = False

    def __init__(self) -> None:
        self.statistics = BlockReductionStatistics(
            backend="numpy", device="cpu"
        )

    def reduce(
        self, keys: np.ndarray, values: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        _validate_inputs(keys, values)
        started = perf_counter()
        input_records = int(keys.size)
        if input_records == 0:
            result_keys = np.empty(0, dtype=np.uint64)
            result_values = np.empty(0, dtype=np.uint64)
        else:
            order = np.argsort(keys, kind="stable")
            sorted_keys = keys[order]
            sorted_values = values[order]
            starts = np.empty(input_records, dtype=bool)
            starts[0] = True
            starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
            start_indices = np.flatnonzero(starts)
            result_keys = sorted_keys[start_indices].copy()
            result_values = np.add.reduceat(
                sorted_values, start_indices, dtype=np.uint64
            )
            nonzero = result_values != 0
            result_keys = result_keys[nonzero]
            result_values = result_values[nonzero]
        self.statistics.calls += 1
        self.statistics.input_records += input_records
        self.statistics.output_records += int(result_keys.size)
        self.statistics.seconds += perf_counter() - started
        return result_keys, result_values


class CuPyBlockReducer:
    """Optional exact CUDA implementation backed by CuPy primitives."""

    prefer_async = True

    def __init__(
        self, device: int = 0, *, min_gpu_records: int = 1_000_000
    ) -> None:
        if device < 0:
            raise ValueError("CUDA device index must be nonnegative")
        if min_gpu_records < 0:
            raise ValueError("minimum GPU records must be nonnegative")
        try:
            import cupy as cp
        except ModuleNotFoundError as error:
            raise AcceleratorUnavailable(
                "CUDA block reduction requires CuPy built for the cluster's "
                "CUDA runtime"
            ) from error
        try:
            device_handle = cp.cuda.Device(device)
            device_handle.use()
            properties = cp.cuda.runtime.getDeviceProperties(device)
        except Exception as error:
            raise AcceleratorUnavailable(
                f"CUDA device {device} is unavailable: {error}"
            ) from error
        raw_name = properties.get("name", f"cuda:{device}")
        if isinstance(raw_name, bytes):
            raw_name = raw_name.decode("utf-8", errors="replace")
        self._cp = cp
        self._device = device_handle
        self._min_gpu_records = min_gpu_records
        self.grouped_join_min_records = min_gpu_records
        self._cpu_fallback = NumPyBlockReducer()
        self._grouped_join_kernel = None
        self.statistics = BlockReductionStatistics(
            backend="cuda-cupy",
            device=f"cuda:{device}:{raw_name}",
        )

    def build_equality_join_plan(
        self, left_keys: np.ndarray, right_keys: np.ndarray
    ):
        """GPU-sort shared keys and return compact host group metadata.

        The output row orders are uint32 and the unique-key tables are usually
        far smaller than the sparse operands.  If one sort cannot fit safely
        on this device, return ``None`` so the caller can use its exact
        external/CPU planner rather than trigger CUDA OOM.
        """
        from .parity import EqualityJoinPlan

        if (
            left_keys.dtype != np.uint64
            or right_keys.dtype != np.uint64
            or left_keys.ndim != 1
            or right_keys.ndim != 1
        ):
            raise ValueError("equality join keys must be uint64 vectors")
        uint32_limit = int(np.iinfo(np.uint32).max)
        if left_keys.size > uint32_limit or right_keys.size > uint32_limit:
            raise OverflowError("parity row indices exceed the uint32 backend")
        cp = self._cp
        maximum_records = max(int(left_keys.size), int(right_keys.size))
        with self._device:
            free_bytes, _ = cp.cuda.runtime.memGetInfo()
        # argsort temporarily holds uint64 indices before conversion, the
        # sorted keys, flags and start indices.  Keep a conservative margin
        # for the CUDA context, radix-sort workspace and CuPy memory pool.
        if maximum_records * 48 > int(free_bytes * 0.80):
            return None

        started = perf_counter()

        def sorted_groups(keys: np.ndarray):
            count = int(keys.size)
            if count == 0:
                return (
                    np.empty(0, dtype=np.uint32),
                    np.empty(0, dtype=np.uint64),
                    np.empty(0, dtype=np.uint64),
                    np.empty(0, dtype=np.uint64),
                )
            with self._device:
                device_keys = cp.asarray(keys)
                order64 = cp.argsort(device_keys)
                order = order64.astype(cp.uint32)
                del order64
                sorted_keys = device_keys[order]
                starts = cp.empty(count, dtype=cp.bool_)
                starts[0] = True
                starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
                start_indices = cp.flatnonzero(starts)
                unique = sorted_keys[start_indices]
                terminal = cp.asarray([count], dtype=cp.uint64)
                counts = cp.diff(
                    cp.concatenate(
                        (start_indices.astype(cp.uint64), terminal)
                    )
                )
                result = (
                    cp.asnumpy(order),
                    cp.asnumpy(unique),
                    cp.asnumpy(start_indices).astype(
                        np.uint64, copy=False
                    ),
                    cp.asnumpy(counts).astype(np.uint64, copy=False),
                )
            return result

        left_order, left_unique, left_start, left_count = sorted_groups(
            left_keys
        )
        right_order, right_unique, right_start, right_count = sorted_groups(
            right_keys
        )
        _, left_groups, right_groups = np.intersect1d(
            left_unique,
            right_unique,
            assume_unique=True,
            return_indices=True,
        )
        matched_left_starts = left_start[left_groups]
        matched_left_counts = left_count[left_groups]
        matched_right_starts = right_start[right_groups]
        matched_right_counts = right_count[right_groups]
        group_pairs = matched_left_counts * matched_right_counts
        pair_offsets = np.empty(group_pairs.size + 1, dtype=np.uint64)
        pair_offsets[0] = 0
        np.cumsum(group_pairs, dtype=np.uint64, out=pair_offsets[1:])
        plan = EqualityJoinPlan(
            left_order=left_order,
            right_order=right_order,
            left_starts=matched_left_starts,
            left_counts=matched_left_counts,
            right_starts=matched_right_starts,
            right_counts=matched_right_counts,
            pair_offsets=pair_offsets,
        )
        self.statistics.gpu_join_plan_calls += 1
        self.statistics.gpu_join_plan_input_records += (
            int(left_keys.size) + int(right_keys.size)
        )
        self.statistics.gpu_join_plan_seconds += perf_counter() - started
        return plan

    def build_parity_equality_join_plan(
        self,
        *,
        anchor_keys: np.ndarray,
        anchor_dimensions: tuple[int, ...],
        anchor_shared_positions: tuple[int, ...],
        other_keys: np.ndarray,
        other_dimensions: tuple[int, ...],
        other_shared_positions: tuple[int, ...],
        other_fixed: np.ndarray,
    ):
        """Encode shared coordinates and sort equality groups on the GPU."""
        from .parity import EqualityJoinPlan

        if anchor_keys.dtype != np.uint64 or other_keys.dtype != np.uint64:
            raise ValueError("parity tensor keys must be uint64")
        if other_fixed.dtype != np.bool_:
            raise ValueError("parity fixed flags must be boolean")
        if len(anchor_shared_positions) != len(other_shared_positions):
            raise ValueError("shared coordinate positions differ")
        uint32_limit = int(np.iinfo(np.uint32).max)
        oriented_other_records = int(
            other_keys.size + np.count_nonzero(~other_fixed)
        )
        if (
            anchor_keys.size > uint32_limit
            or oriented_other_records > uint32_limit
        ):
            raise OverflowError("parity row indices exceed the uint32 backend")
        cp = self._cp
        maximum_records = max(int(anchor_keys.size), oriented_other_records)
        with self._device:
            free_bytes, _ = cp.cuda.runtime.memGetInfo()
        if maximum_records * 64 > int(free_bytes * 0.80):
            return None
        started = perf_counter()

        def encode(
            keys: np.ndarray,
            dimensions: tuple[int, ...],
            positions: tuple[int, ...],
        ):
            with self._device:
                device_keys = cp.asarray(keys)
                encoded = cp.zeros(keys.size, dtype=cp.uint64)
                for position in positions:
                    dimension = dimensions[position]
                    stride = int(prod(dimensions[position + 1 :]))
                    coordinate = (
                        device_keys // np.uint64(stride)
                    ) % np.uint64(dimension)
                    encoded *= np.uint64(dimension)
                    encoded += coordinate
            return encoded

        def sorted_groups(device_keys):
            count = int(device_keys.size)
            if count == 0:
                return (
                    np.empty(0, dtype=np.uint32),
                    np.empty(0, dtype=np.uint64),
                    np.empty(0, dtype=np.uint64),
                    np.empty(0, dtype=np.uint64),
                )
            with self._device:
                order64 = cp.argsort(device_keys)
                order = order64.astype(cp.uint32)
                del order64
                sorted_keys = device_keys[order]
                starts = cp.empty(count, dtype=cp.bool_)
                starts[0] = True
                starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
                start_indices = cp.flatnonzero(starts)
                unique = sorted_keys[start_indices]
                terminal = cp.asarray([count], dtype=cp.uint64)
                counts = cp.diff(
                    cp.concatenate(
                        (start_indices.astype(cp.uint64), terminal)
                    )
                )
                return (
                    cp.asnumpy(order),
                    cp.asnumpy(unique),
                    cp.asnumpy(start_indices).astype(
                        np.uint64, copy=False
                    ),
                    cp.asnumpy(counts).astype(np.uint64, copy=False),
                )

        anchor_encoded = encode(
            anchor_keys,
            anchor_dimensions,
            anchor_shared_positions,
        )
        (
            left_order,
            left_unique,
            left_start,
            left_count,
        ) = sorted_groups(anchor_encoded)
        del anchor_encoded

        other_encoded = encode(
            other_keys,
            other_dimensions,
            other_shared_positions,
        )
        shared_cells = prod(
            other_dimensions[position]
            for position in other_shared_positions
        )
        with self._device:
            device_fixed = cp.asarray(other_fixed)
            reflected = np.uint64(shared_cells - 1) - other_encoded
            oriented_other = cp.concatenate(
                (other_encoded, reflected[~device_fixed])
            )
        (
            right_order,
            right_unique,
            right_start,
            right_count,
        ) = sorted_groups(oriented_other)

        _, left_groups, right_groups = np.intersect1d(
            left_unique,
            right_unique,
            assume_unique=True,
            return_indices=True,
        )
        matched_left_starts = left_start[left_groups]
        matched_left_counts = left_count[left_groups]
        matched_right_starts = right_start[right_groups]
        matched_right_counts = right_count[right_groups]
        group_pairs = matched_left_counts * matched_right_counts
        pair_offsets = np.empty(group_pairs.size + 1, dtype=np.uint64)
        pair_offsets[0] = 0
        np.cumsum(group_pairs, dtype=np.uint64, out=pair_offsets[1:])
        plan = EqualityJoinPlan(
            left_order=left_order,
            right_order=right_order,
            left_starts=matched_left_starts,
            left_counts=matched_left_counts,
            right_starts=matched_right_starts,
            right_counts=matched_right_counts,
            pair_offsets=pair_offsets,
        )
        self.statistics.gpu_join_plan_calls += 1
        self.statistics.gpu_join_plan_input_records += (
            int(anchor_keys.size) + oriented_other_records
        )
        self.statistics.gpu_join_plan_seconds += perf_counter() - started
        return plan

    def reduce(
        self, keys: np.ndarray, values: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        _validate_inputs(keys, values)
        started = perf_counter()
        input_records = int(keys.size)
        if input_records < self._min_gpu_records:
            result_keys, result_values = self._cpu_fallback.reduce(
                keys, values
            )
            self.statistics.calls += 1
            self.statistics.input_records += input_records
            self.statistics.output_records += int(result_keys.size)
            self.statistics.seconds += perf_counter() - started
            self.statistics.cpu_fallback_calls += 1
            self.statistics.cpu_fallback_records += input_records
            return result_keys, result_values
        cp = self._cp
        with self._device:
            if input_records == 0:
                result_keys = np.empty(0, dtype=np.uint64)
                result_values = np.empty(0, dtype=np.uint64)
            else:
                device_keys = cp.asarray(keys)
                device_values = cp.asarray(values)
                # Stability is unnecessary: exact uint64 addition is
                # associative under the checked no-overflow bound.
                order = cp.argsort(device_keys)
                sorted_keys = device_keys[order]
                sorted_values = device_values[order]
                starts = cp.empty(input_records, dtype=cp.bool_)
                starts[0] = True
                starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
                start_indices = cp.flatnonzero(starts)
                unique_keys = sorted_keys[start_indices]
                unique_values = cp.add.reduceat(
                    sorted_values, start_indices
                )
                nonzero = unique_values != 0
                result_keys = cp.asnumpy(unique_keys[nonzero])
                result_values = cp.asnumpy(unique_values[nonzero])
        if result_keys.dtype != np.uint64:
            result_keys = result_keys.astype(np.uint64, copy=False)
        if result_values.dtype != np.uint64:
            result_values = result_values.astype(np.uint64, copy=False)
        self.statistics.calls += 1
        self.statistics.input_records += input_records
        self.statistics.output_records += int(result_keys.size)
        self.statistics.seconds += perf_counter() - started
        self.statistics.gpu_device_dispatches += 1
        return result_keys, result_values

    def reduce_grouped_parity_join(
        self, batch_or_work
    ) -> tuple[np.ndarray, np.ndarray, int]:
        """Generate and reduce a compact grouped join without host pair rows."""
        from .gpu_join import reduce_grouped_parity_join

        started = perf_counter()
        raw_pair_count = batch_or_work.raw_pair_count
        materialize = getattr(batch_or_work, "materialize", None)
        batch = (
            materialize(self._cp)
            if materialize is not None
            else batch_or_work
        )
        (
            result_keys,
            result_values,
            valid_count,
            self._grouped_join_kernel,
        ) = reduce_grouped_parity_join(
            self._cp,
            self._device,
            batch,
            self._grouped_join_kernel,
        )
        self.statistics.calls += 1
        self.statistics.input_records += raw_pair_count
        self.statistics.output_records += int(result_keys.size)
        self.statistics.seconds += perf_counter() - started
        self.statistics.gpu_device_dispatches += 1
        return result_keys, result_values, valid_count

    def reduce_grouped_parity_batches(
        self, batches: Iterable
    ) -> Iterator[tuple[np.ndarray, np.ndarray, int, int]]:
        """Yield reduced runs as ``keys, values, valid pairs, raw pairs``."""
        for batch in batches:
            raw_count = batch.raw_pair_count
            keys, values, valid_count = self.reduce_grouped_parity_join(batch)
            yield keys, values, valid_count, raw_count


class MultiCuPyBlockReducer:
    """Range-partition each block across multiple independent CUDA devices.

    Every equal key is routed to exactly one device.  Per-device results are
    therefore disjoint sorted key ranges and can be concatenated without a
    cross-device reduction or a second global sort.
    """

    prefer_async = True

    def __init__(
        self,
        devices: tuple[int, ...],
        *,
        min_gpu_records: int = 1_000_000,
        records_per_device: int = 2_000_000,
    ) -> None:
        if len(devices) < 2:
            raise ValueError("multi-CUDA reduction requires at least 2 devices")
        if len(set(devices)) != len(devices):
            raise ValueError("CUDA device indices must be unique")
        if any(device < 0 for device in devices):
            raise ValueError("CUDA device indices must be nonnegative")
        if min_gpu_records < 0:
            raise ValueError("minimum GPU records must be nonnegative")
        if records_per_device <= 0:
            raise ValueError("records per CUDA device must be positive")
        self._reducers = tuple(
            CuPyBlockReducer(device, min_gpu_records=0)
            for device in devices
        )
        self._min_gpu_records = min_gpu_records
        self.grouped_join_min_records = min_gpu_records
        self._records_per_device = records_per_device
        self._cpu_fallback = NumPyBlockReducer()
        self._executor = ThreadPoolExecutor(
            max_workers=len(self._reducers),
            thread_name_prefix="nqueens-cuda-reducer",
        )
        device_names = tuple(
            reducer.statistics.device for reducer in self._reducers
        )
        self.statistics = BlockReductionStatistics(
            backend="cuda-cupy-multi",
            device=",".join(f"cuda:{device}" for device in devices),
            devices=device_names,
        )

    def build_equality_join_plan(
        self, left_keys: np.ndarray, right_keys: np.ndarray
    ):
        """Use one GPU for the reusable shared-key group plan."""
        planner = self._reducers[0]
        before_calls = planner.statistics.gpu_join_plan_calls
        before_records = planner.statistics.gpu_join_plan_input_records
        before_seconds = planner.statistics.gpu_join_plan_seconds
        plan = planner.build_equality_join_plan(left_keys, right_keys)
        self.statistics.gpu_join_plan_calls += (
            planner.statistics.gpu_join_plan_calls - before_calls
        )
        self.statistics.gpu_join_plan_input_records += (
            planner.statistics.gpu_join_plan_input_records - before_records
        )
        self.statistics.gpu_join_plan_seconds += (
            planner.statistics.gpu_join_plan_seconds - before_seconds
        )
        return plan

    def build_parity_equality_join_plan(self, **kwargs):
        """Delegate fused shared-coordinate planning to the first GPU."""
        planner = self._reducers[0]
        before_calls = planner.statistics.gpu_join_plan_calls
        before_records = planner.statistics.gpu_join_plan_input_records
        before_seconds = planner.statistics.gpu_join_plan_seconds
        plan = planner.build_parity_equality_join_plan(**kwargs)
        self.statistics.gpu_join_plan_calls += (
            planner.statistics.gpu_join_plan_calls - before_calls
        )
        self.statistics.gpu_join_plan_input_records += (
            planner.statistics.gpu_join_plan_input_records - before_records
        )
        self.statistics.gpu_join_plan_seconds += (
            planner.statistics.gpu_join_plan_seconds - before_seconds
        )
        return plan

    def reduce(
        self, keys: np.ndarray, values: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        _validate_inputs(keys, values)
        started = perf_counter()
        input_records = int(keys.size)
        if input_records == 0:
            result_keys = np.empty(0, dtype=np.uint64)
            result_values = np.empty(0, dtype=np.uint64)
        elif input_records < self._min_gpu_records:
            result_keys, result_values = self._cpu_fallback.reduce(
                keys, values
            )
            self.statistics.cpu_fallback_calls += 1
            self.statistics.cpu_fallback_records += input_records
        else:
            minimum = int(np.min(keys))
            maximum = int(np.max(keys))
            span = maximum - minimum + 1
            useful_devices = max(
                1, ceil(input_records / self._records_per_device)
            )
            partition_count = min(
                len(self._reducers), span, useful_devices
            )
            width = (span + partition_count - 1) // partition_count
            futures = []
            for partition in range(partition_count):
                low = minimum + partition * width
                high = min(maximum + 1, low + width)
                if partition + 1 == partition_count:
                    selected = keys >= np.uint64(low)
                else:
                    selected = (
                        (keys >= np.uint64(low))
                        & (keys < np.uint64(high))
                    )
                shard_keys = keys[selected]
                shard_values = values[selected]
                futures.append(
                    self._executor.submit(
                        self._reducers[partition].reduce,
                        shard_keys,
                        shard_values,
                    )
                )
            shards = [future.result() for future in futures]
            nonempty = [
                (shard_keys, shard_values)
                for shard_keys, shard_values in shards
                if shard_keys.size
            ]
            if not nonempty:
                result_keys = np.empty(0, dtype=np.uint64)
                result_values = np.empty(0, dtype=np.uint64)
            elif len(nonempty) == 1:
                result_keys, result_values = nonempty[0]
            else:
                result_keys = np.concatenate(
                    [shard[0] for shard in nonempty]
                )
                result_values = np.concatenate(
                    [shard[1] for shard in nonempty]
                )
            if result_keys.size and np.any(
                result_keys[1:] <= result_keys[:-1]
            ):
                raise AssertionError(
                    "multi-CUDA key ranges did not produce sorted output"
                )
            self.statistics.gpu_device_dispatches += partition_count
        self.statistics.calls += 1
        self.statistics.input_records += input_records
        self.statistics.output_records += int(result_keys.size)
        self.statistics.seconds += perf_counter() - started
        return result_keys, result_values

    def close(self) -> None:
        self._executor.shutdown(wait=True)

    def reduce_grouped_parity_batches(
        self, batches: Iterable
    ) -> Iterator[tuple[np.ndarray, np.ndarray, int, int]]:
        """Keep one compact grouped join in flight on every CUDA device."""
        batch_iterator = iter(batches)
        pending = {}
        started = perf_counter()

        def submit_one(reducer_index: int) -> bool:
            try:
                batch = next(batch_iterator)
            except StopIteration:
                return False
            future = self._executor.submit(
                self._reducers[reducer_index].reduce_grouped_parity_join,
                batch,
            )
            pending[future] = (batch.raw_pair_count, reducer_index)
            self.statistics.async_submissions += 1
            return True

        for reducer_index in range(len(self._reducers)):
            if not submit_one(reducer_index):
                break
        try:
            while pending:
                completed, _ = wait(
                    pending, return_when=FIRST_COMPLETED
                )
                for future in completed:
                    raw_count, reducer_index = pending.pop(future)
                    keys, values, valid_count = future.result()
                    self.statistics.calls += 1
                    self.statistics.input_records += raw_count
                    self.statistics.output_records += int(keys.size)
                    self.statistics.gpu_device_dispatches += 1
                    submit_one(reducer_index)
                    yield keys, values, valid_count, raw_count
        finally:
            self.statistics.seconds += perf_counter() - started


def create_block_reducer(
    backend: str = "numpy",
    *,
    cuda_device: int = 0,
    cuda_devices: tuple[int, ...] | None = None,
    cuda_min_records: int = 1_000_000,
    cuda_records_per_device: int = 2_000_000,
) -> ExactBlockReducer:
    if backend == "numpy":
        return NumPyBlockReducer()
    if backend == "cuda":
        devices = cuda_devices or (cuda_device,)
        if len(devices) == 1:
            return CuPyBlockReducer(
                devices[0], min_gpu_records=cuda_min_records
            )
        return MultiCuPyBlockReducer(
            devices,
            min_gpu_records=cuda_min_records,
            records_per_device=cuda_records_per_device,
        )
    raise ValueError(f"unknown exact block reducer: {backend}")
