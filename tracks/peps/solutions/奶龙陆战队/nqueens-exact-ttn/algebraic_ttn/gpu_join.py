"""GPU-native exact grouped Cartesian products for parity contractions.

The host describes matching equality-join groups compactly.  A CUDA kernel
maps contribution indices to group-local row pairs, decodes tensor
coordinates, applies the reflection canonicalization, and emits exact uint64
key/value records.  In particular, the host never materializes one left-row
and one right-row index for every Cartesian-product contribution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class GroupedParityJoinBatch:
    """One bounded batch of consecutive equality-join contributions."""

    anchor_keys: np.ndarray
    anchor_values: np.ndarray
    anchor_fixed: np.ndarray
    other_keys: np.ndarray
    other_values: np.ndarray
    other_fixed: np.ndarray
    other_reflected: np.ndarray
    anchor_starts: np.ndarray
    anchor_counts: np.ndarray
    other_starts: np.ndarray
    other_counts: np.ndarray
    pair_begins: np.ndarray
    pair_offsets: np.ndarray
    output_sources: np.ndarray
    output_strides: np.ndarray
    output_dimensions: np.ndarray

    @property
    def raw_pair_count(self) -> int:
        return int(self.pair_offsets[-1]) if self.pair_offsets.size else 0

    @property
    def group_count(self) -> int:
        return int(self.anchor_starts.size)

    def validate(self) -> None:
        uint64_vectors = (
            self.anchor_keys,
            self.anchor_values,
            self.other_keys,
            self.other_values,
            self.anchor_starts,
            self.anchor_counts,
            self.other_starts,
            self.other_counts,
            self.pair_begins,
            self.pair_offsets,
            self.output_strides,
            self.output_dimensions,
        )
        if any(array.dtype != np.uint64 for array in uint64_vectors):
            raise ValueError("grouped parity join uint64 metadata is invalid")
        byte_vectors = (
            self.anchor_fixed,
            self.other_fixed,
            self.other_reflected,
            self.output_sources,
        )
        if any(array.dtype != np.uint8 for array in byte_vectors):
            raise ValueError("grouped parity join byte metadata is invalid")
        if any(array.ndim != 1 for array in uint64_vectors + byte_vectors):
            raise ValueError("grouped parity join inputs must be vectors")
        if self.anchor_keys.size != self.anchor_values.size:
            raise ValueError("anchor keys and values differ in length")
        if self.anchor_keys.size != self.anchor_fixed.size:
            raise ValueError("anchor fixed flags differ in length")
        if self.other_keys.size != self.other_values.size:
            raise ValueError("other keys and values differ in length")
        if self.other_keys.size != self.other_fixed.size:
            raise ValueError("other fixed flags differ in length")
        if self.other_keys.size != self.other_reflected.size:
            raise ValueError("other orientations differ in length")
        groups = self.group_count
        group_vectors = (
            self.anchor_counts,
            self.other_starts,
            self.other_counts,
            self.pair_begins,
        )
        if any(array.size != groups for array in group_vectors):
            raise ValueError("grouped parity join group metadata differs")
        if self.pair_offsets.size != groups + 1:
            raise ValueError("pair offsets require one terminal entry")
        if groups and int(self.pair_offsets[0]) != 0:
            raise ValueError("pair offsets must begin at zero")
        if np.any(self.pair_offsets[1:] < self.pair_offsets[:-1]):
            raise ValueError("pair offsets must be nondecreasing")
        if not (
            self.output_sources.size
            == self.output_strides.size
            == self.output_dimensions.size
        ):
            raise ValueError("output coordinate metadata differs in length")
        if np.any(self.output_sources > 1):
            raise ValueError("output sources must select anchor or other")


@dataclass(slots=True)
class GroupedParityJoinWork:
    """A cheap batch descriptor materialized inside its GPU worker thread."""

    anchor_source_keys: np.ndarray
    anchor_source_values: np.ndarray
    anchor_source_fixed: np.ndarray
    other_source_keys: np.ndarray
    other_source_values: np.ndarray
    other_source_fixed: np.ndarray
    other_orbit_rows: np.ndarray
    other_orientations: np.ndarray
    left_order: np.ndarray
    right_order: np.ndarray
    left_starts: np.ndarray
    left_counts: np.ndarray
    right_starts: np.ndarray
    right_counts: np.ndarray
    global_pair_offsets: np.ndarray
    pair_begin: int
    pair_end: int
    output_sources: np.ndarray
    output_strides: np.ndarray
    output_dimensions: np.ndarray

    @property
    def raw_pair_count(self) -> int:
        return self.pair_end - self.pair_begin

    def materialize(self, cp=None) -> GroupedParityJoinBatch:
        first_group = int(
            np.searchsorted(
                self.global_pair_offsets,
                np.uint64(self.pair_begin),
                side="right",
            )
            - 1
        )
        last_group = int(
            np.searchsorted(
                self.global_pair_offsets,
                np.uint64(self.pair_end - 1),
                side="right",
            )
            - 1
        )
        group_slice = slice(first_group, last_group + 1)
        group_pair_starts = self.global_pair_offsets[
            first_group : last_group + 1
        ]
        group_pair_ends = self.global_pair_offsets[
            first_group + 1 : last_group + 2
        ]
        selected_starts = np.maximum(
            group_pair_starts, np.uint64(self.pair_begin)
        )
        selected_ends = np.minimum(
            group_pair_ends, np.uint64(self.pair_end)
        )
        pair_begins = (
            selected_starts - group_pair_starts
        ).astype(np.uint64, copy=False)
        selected_counts = selected_ends - selected_starts
        pair_offsets = np.empty(
            selected_counts.size + 1, dtype=np.uint64
        )
        pair_offsets[0] = 0
        np.cumsum(
            selected_counts, dtype=np.uint64, out=pair_offsets[1:]
        )

        anchor_sorted_begin = int(self.left_starts[first_group])
        anchor_sorted_end = int(
            self.left_starts[last_group] + self.left_counts[last_group]
        )
        other_sorted_begin = int(self.right_starts[first_group])
        other_sorted_end = int(
            self.right_starts[last_group] + self.right_counts[last_group]
        )
        anchor_rows = self.left_order[
            anchor_sorted_begin:anchor_sorted_end
        ]
        other_oriented_rows = self.right_order[
            other_sorted_begin:other_sorted_end
        ]
        other_rows = self.other_orbit_rows[other_oriented_rows]

        def gather(
            source: np.ndarray,
            rows: np.ndarray,
            dtype,
        ) -> np.ndarray:
            if cp is None:
                return np.asarray(source[rows], dtype=dtype)
            output = _pinned_empty(cp, rows.size, dtype)
            np.take(source, rows, out=output)
            return output

        return GroupedParityJoinBatch(
            anchor_keys=gather(
                self.anchor_source_keys, anchor_rows, np.uint64
            ),
            anchor_values=gather(
                self.anchor_source_values, anchor_rows, np.uint64
            ),
            anchor_fixed=gather(
                self.anchor_source_fixed, anchor_rows, np.uint8
            ),
            other_keys=gather(
                self.other_source_keys, other_rows, np.uint64
            ),
            other_values=gather(
                self.other_source_values, other_rows, np.uint64
            ),
            other_fixed=gather(
                self.other_source_fixed, other_rows, np.uint8
            ),
            other_reflected=gather(
                self.other_orientations,
                other_oriented_rows,
                np.uint8,
            ),
            anchor_starts=(
                self.left_starts[group_slice]
                - np.uint64(anchor_sorted_begin)
            ).astype(np.uint64, copy=False),
            anchor_counts=self.left_counts[group_slice],
            other_starts=(
                self.right_starts[group_slice]
                - np.uint64(other_sorted_begin)
            ).astype(np.uint64, copy=False),
            other_counts=self.right_counts[group_slice],
            pair_begins=pair_begins,
            pair_offsets=pair_offsets,
            output_sources=self.output_sources,
            output_strides=self.output_strides,
            output_dimensions=self.output_dimensions,
        )


def _pinned_empty(cp, size: int, dtype) -> np.ndarray:
    """Return a NumPy vector backed by CUDA page-locked host memory."""
    normalized_dtype = np.dtype(dtype)
    memory = cp.cuda.alloc_pinned_memory(size * normalized_dtype.itemsize)
    return np.frombuffer(memory, dtype=normalized_dtype, count=size)


CUDA_PARITY_JOIN_SOURCE = r"""
extern "C" __global__
void grouped_parity_join(
    const unsigned long long* anchor_keys,
    const unsigned long long* anchor_values,
    const unsigned char* anchor_fixed,
    const unsigned long long* other_keys,
    const unsigned long long* other_values,
    const unsigned char* other_fixed,
    const unsigned char* other_reflected,
    const unsigned long long* anchor_starts,
    const unsigned long long* anchor_counts,
    const unsigned long long* other_starts,
    const unsigned long long* other_counts,
    const unsigned long long* pair_begins,
    const unsigned long long* pair_offsets,
    const unsigned char* output_sources,
    const unsigned long long* output_strides,
    const unsigned long long* output_dimensions,
    const int group_count,
    const int output_rank,
    const unsigned long long pair_count,
    unsigned long long* output_keys,
    unsigned long long* output_values
) {
    const unsigned long long pair =
        (unsigned long long)blockDim.x * blockIdx.x + threadIdx.x;
    if (pair >= pair_count) {
        return;
    }

    int low = 0;
    int high = group_count;
    while (low + 1 < high) {
        const int middle = low + (high - low) / 2;
        if (pair_offsets[middle] <= pair) {
            low = middle;
        } else {
            high = middle;
        }
    }
    const int group = low;
    const unsigned long long within =
        pair_begins[group] + pair - pair_offsets[group];
    const unsigned long long right_count = other_counts[group];
    const unsigned long long anchor_row =
        anchor_starts[group] + within / right_count;
    const unsigned long long other_row =
        other_starts[group] + within % right_count;

    // A fixed anchor has no distinct reflected orientation.  The host-side
    // reference implementation removes precisely these duplicate pairs.
    if (anchor_fixed[anchor_row] && other_reflected[other_row]) {
        output_keys[pair] = 0;
        output_values[pair] = 0;
        return;
    }

    const unsigned long long anchor_key = anchor_keys[anchor_row];
    const unsigned long long other_key = other_keys[other_row];
    unsigned long long key = 0;
    unsigned long long reflected_key = 0;
    for (int position = 0; position < output_rank; ++position) {
        const unsigned long long dimension = output_dimensions[position];
        unsigned long long coordinate;
        if (output_sources[position] == 0) {
            coordinate =
                (anchor_key / output_strides[position]) % dimension;
        } else {
            coordinate =
                (other_key / output_strides[position]) % dimension;
            if (other_reflected[other_row]) {
                coordinate = dimension - 1 - coordinate;
            }
        }
        key = key * dimension + coordinate;
        reflected_key =
            reflected_key * dimension + (dimension - 1 - coordinate);
    }

    const unsigned long long canonical_key =
        key < reflected_key ? key : reflected_key;
    const bool output_fixed = key == reflected_key;
    const bool union_fixed =
        anchor_fixed[anchor_row] && other_fixed[other_row];
    const unsigned long long orbit_weight =
        output_fixed && !union_fixed ? 2ULL : 1ULL;
    output_keys[pair] = canonical_key;
    output_values[pair] =
        anchor_values[anchor_row] * other_values[other_row] * orbit_weight;
}
"""


def reduce_grouped_parity_join(
    cp,
    device,
    batch: GroupedParityJoinBatch,
    kernel=None,
):
    """Generate and exactly reduce one join batch entirely on one GPU."""
    batch.validate()
    pair_count = batch.raw_pair_count
    with device:
        if kernel is None:
            kernel = cp.RawKernel(
                CUDA_PARITY_JOIN_SOURCE, "grouped_parity_join"
            )
        if pair_count == 0:
            empty = np.empty(0, dtype=np.uint64)
            return empty, empty.copy(), 0, kernel

        device_arrays = [
            cp.asarray(array)
            for array in (
                batch.anchor_keys,
                batch.anchor_values,
                batch.anchor_fixed,
                batch.other_keys,
                batch.other_values,
                batch.other_fixed,
                batch.other_reflected,
                batch.anchor_starts,
                batch.anchor_counts,
                batch.other_starts,
                batch.other_counts,
                batch.pair_begins,
                batch.pair_offsets,
                batch.output_sources,
                batch.output_strides,
                batch.output_dimensions,
            )
        ]
        output_keys = cp.empty(pair_count, dtype=cp.uint64)
        output_values = cp.empty(pair_count, dtype=cp.uint64)
        threads = 256
        blocks = (pair_count + threads - 1) // threads
        kernel(
            (blocks,),
            (threads,),
            (
                *device_arrays,
                np.int32(batch.group_count),
                np.int32(batch.output_dimensions.size),
                np.uint64(pair_count),
                output_keys,
                output_values,
            ),
        )

        valid = output_values != 0
        valid_count = int(cp.count_nonzero(valid).item())
        if valid_count != pair_count:
            output_keys = output_keys[valid]
            output_values = output_values[valid]
        if valid_count == 0:
            result_keys = np.empty(0, dtype=np.uint64)
            result_values = np.empty(0, dtype=np.uint64)
        else:
            order = cp.argsort(output_keys)
            sorted_keys = output_keys[order]
            sorted_values = output_values[order]
            starts = cp.empty(valid_count, dtype=cp.bool_)
            starts[0] = True
            starts[1:] = sorted_keys[1:] != sorted_keys[:-1]
            start_indices = cp.flatnonzero(starts)
            unique_keys = sorted_keys[start_indices]
            unique_values = cp.add.reduceat(sorted_values, start_indices)
            nonzero = unique_values != 0
            active_keys = unique_keys[nonzero]
            active_values = unique_values[nonzero]
            result_keys = _pinned_empty(cp, int(active_keys.size), np.uint64)
            result_values = _pinned_empty(
                cp, int(active_values.size), np.uint64
            )
            cp.asnumpy(active_keys, out=result_keys)
            cp.asnumpy(active_values, out=result_values)

    return (
        result_keys.astype(np.uint64, copy=False),
        result_values.astype(np.uint64, copy=False),
        valid_count,
        kernel,
    )
