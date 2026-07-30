"""Exact global column-reflection even-sector tensor contraction."""

from dataclasses import dataclass
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
from math import prod
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory, gettempdir
from time import perf_counter
from typing import Any

import numpy as np

from .block_reduction import ExactBlockReducer, NumPyBlockReducer
from .gpu_join import GroupedParityJoinWork
from .packed import (
    UINT64_MAX,
    PackedTensor,
    build_packed_copy_absorbed_network,
    packed_contraction_plan,
)


@dataclass(slots=True)
class EqualityJoinPlan:
    """Sorted equality groups and their exact Cartesian-product prefix."""

    left_order: np.ndarray
    right_order: np.ndarray
    left_starts: np.ndarray
    left_counts: np.ndarray
    right_starts: np.ndarray
    right_counts: np.ndarray
    pair_offsets: np.ndarray

    @property
    def pair_count(self) -> int:
        return int(self.pair_offsets[-1])

    @property
    def group_count(self) -> int:
        return int(self.left_starts.size)


class JoinBudgetExceeded(RuntimeError):
    """Raised before materializing an equality join that exceeds its budget."""

    def __init__(
        self,
        pair_count: int,
        limit: int,
        join_plan: EqualityJoinPlan | None = None,
    ) -> None:
        self.pair_count = pair_count
        self.limit = limit
        self.join_plan = join_plan
        super().__init__(
            f"equality join requires {pair_count:,} pairs; "
            f"limit is {limit:,}"
        )


class _DiskTensorStorage:
    """Own a temporary tensor directory until its last tensor is released."""

    def __init__(self, temp_directory: Path | None) -> None:
        self._workspace = TemporaryDirectory(
            prefix="nqueens_stream_", dir=temp_directory
        )
        self.path = Path(self._workspace.name)
        self.validated_output = False

    def cleanup(self) -> None:
        self._workspace.cleanup()

    def __del__(self) -> None:
        self.cleanup()


_RUN_MERGER_BINARY: Path | None = None


def _sorted_run_merger_binary() -> Path:
    """Compile and cache the small exact k-way run merger."""
    global _RUN_MERGER_BINARY
    if _RUN_MERGER_BINARY is not None:
        return _RUN_MERGER_BINARY
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "merge_sorted_runs.cpp"
    )
    digest = sha256(source.read_bytes()).hexdigest()[:16]
    binary = Path(gettempdir()) / f"nqueens_merge_sorted_runs_{digest}"
    if not binary.exists():
        compiler = shutil.which("clang++") or shutil.which("g++")
        if compiler is None:
            raise RuntimeError(
                "sorted-runs streaming requires clang++ or g++"
            )
        completed = subprocess.run(
            [
                compiler,
                "-O3",
                "-std=c++17",
                "-pthread",
                str(source),
                "-o",
                str(binary),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(
                "failed to compile sorted-run merger: "
                + completed.stderr.strip()
            )
    _RUN_MERGER_BINARY = binary
    return binary


def _reflect_flat_keys(
    keys: np.ndarray, dimensions: tuple[int, ...]
) -> np.ndarray:
    reflected = np.zeros(keys.size, dtype=np.uint64)
    for position, dimension in enumerate(dimensions):
        stride = prod(dimensions[position + 1 :])
        coordinate = (keys // stride) % dimension
        reflected *= dimension
        reflected += dimension - 1 - coordinate
    return reflected


def _fixed_flat_key(dimensions: tuple[int, ...]) -> int | None:
    if any(dimension % 2 == 0 for dimension in dimensions):
        return None
    key = 0
    for dimension in dimensions:
        key = key * dimension + dimension // 2
    return key


@dataclass(slots=True)
class ParityTensor:
    """Tensor restricted to the even sector of simultaneous column reflection."""

    name: str
    labels: tuple[str, ...]
    dimensions: tuple[int, ...]
    keys: np.ndarray
    values: np.ndarray
    tree: dict[str, Any]
    storage: Any | None = None
    row_reflection_n: int | None = None
    row_uncompressed_even_nnz: int | None = None
    row_uncompressed_full_nnz: int | None = None

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.dimensions):
            raise ValueError("labels and dimensions differ in length")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("tensor labels must be unique")
        if self.keys.dtype != np.uint64 or self.values.dtype != np.uint64:
            raise ValueError("parity coordinates and values require uint64")
        if self.keys.ndim != 1 or self.values.ndim != 1:
            raise ValueError("parity coordinates and values must be vectors")
        if self.keys.size != self.values.size:
            raise ValueError("parity coordinates and values differ in length")
        if self.keys.size:
            storage_validated = bool(
                isinstance(self.storage, _DiskTensorStorage)
                and self.storage.validated_output
            )
            if not storage_validated:
                check_cells = 1_000_000
                previous_key: int | None = None
                for begin in range(0, self.keys.size, check_cells):
                    end = min(begin + check_cells, self.keys.size)
                    key_block = self.keys[begin:end]
                    value_block = self.values[begin:end]
                    if np.any(value_block == 0):
                        raise ValueError("zero entries must not be stored")
                    if (
                        previous_key is not None
                        and int(key_block[0]) <= previous_key
                    ):
                        raise ValueError(
                            "parity coordinates must be strictly sorted"
                        )
                    if np.any(key_block[1:] <= key_block[:-1]):
                        raise ValueError(
                            "parity coordinates must be strictly sorted"
                        )
                    previous_key = int(key_block[-1])
            if int(self.keys[-1]) >= self.dense_cells:
                raise ValueError("parity coordinate is outside its dimensions")

    @property
    def rank(self) -> int:
        return len(self.labels)

    @property
    def dense_cells(self) -> int:
        return prod(self.dimensions)

    @property
    def nnz(self) -> int:
        return int(self.keys.size)

    @property
    def fixed_count(self) -> int:
        fixed_key = _fixed_flat_key(self.dimensions)
        if fixed_key is None:
            return 0
        return int(np.count_nonzero(self.keys == fixed_key))

    @property
    def full_nnz(self) -> int:
        if self.row_uncompressed_full_nnz is not None:
            return self.row_uncompressed_full_nnz
        return 2 * self.nnz - self.fixed_count

    @property
    def column_even_nnz(self) -> int:
        if self.row_uncompressed_even_nnz is not None:
            return self.row_uncompressed_even_nnz
        return self.nnz

    @property
    def nbytes(self) -> int:
        return int(self.keys.nbytes + self.values.nbytes)


def _row_label_reflection(label: str, n: int) -> str:
    if not label.startswith("column_"):
        return label
    row = int(label.split("_", 1)[1])
    return f"column_{n - 1 - row}"


def _row_reflect_flat_keys(
    keys: np.ndarray,
    labels: tuple[str, ...],
    dimensions: tuple[int, ...],
    n: int,
) -> np.ndarray:
    mapped_positions = {
        label: position for position, label in enumerate(labels)
    }
    if {
        _row_label_reflection(label, n) for label in labels
    } != set(labels):
        raise ValueError("row-reflection block requires a stable label set")
    reflected = np.zeros(keys.size, dtype=np.uint64)
    for target_label, dimension in zip(labels, dimensions):
        source_label = _row_label_reflection(target_label, n)
        source_position = mapped_positions[source_label]
        stride = prod(dimensions[source_position + 1 :])
        coordinate = (keys // stride) % dimensions[source_position]
        reflected *= dimension
        reflected += coordinate
    return np.minimum(
        reflected, _reflect_flat_keys(reflected, dimensions)
    )


def compress_row_reflection_sector(
    tensor: ParityTensor, n: int
) -> ParityTensor:
    """Keep one row-reflection orbit inside the column-even quotient."""
    if tensor.row_reflection_n is not None or tensor.rank == 0:
        return tensor
    reflected = _row_reflect_flat_keys(
        tensor.keys, tensor.labels, tensor.dimensions, n
    )
    representatives = tensor.keys <= reflected
    keys = tensor.keys[representatives].copy()
    values = tensor.values[representatives].copy()
    tree = {
        **tensor.tree,
        "row_reflection_sector": "invariant orbit representatives",
        "row_reflection_stored_nnz": int(keys.size),
        "row_reflection_uncompressed_even_nnz": tensor.nnz,
    }
    return ParityTensor(
        name=tensor.name,
        labels=tensor.labels,
        dimensions=tensor.dimensions,
        keys=keys,
        values=values,
        tree=tree,
        row_reflection_n=n,
        row_uncompressed_even_nnz=tensor.nnz,
        row_uncompressed_full_nnz=tensor.full_nnz,
    )


def expand_row_reflection_sector(tensor: ParityTensor) -> ParityTensor:
    """Restore every column-even coordinate from a row-reflection block."""
    if tensor.row_reflection_n is None:
        return tensor
    reflected = _row_reflect_flat_keys(
        tensor.keys,
        tensor.labels,
        tensor.dimensions,
        tensor.row_reflection_n,
    )
    nonfixed = reflected != tensor.keys
    keys = np.concatenate((tensor.keys, reflected[nonfixed]))
    values = np.concatenate((tensor.values, tensor.values[nonfixed]))
    order = np.argsort(keys, kind="stable")
    keys = keys[order]
    values = values[order]
    if (
        tensor.row_uncompressed_even_nnz is not None
        and keys.size != tensor.row_uncompressed_even_nnz
    ):
        raise AssertionError("row-reflection expansion has the wrong size")
    tree = {
        **tensor.tree,
        "row_reflection_sector": "expanded before contraction",
    }
    return ParityTensor(
        name=tensor.name,
        labels=tensor.labels,
        dimensions=tensor.dimensions,
        keys=keys,
        values=values,
        tree=tree,
    )


def _from_invariant_packed(tensor: PackedTensor) -> ParityTensor:
    reflected = _reflect_flat_keys(tensor.keys, tensor.dimensions)
    canonical = tensor.keys <= reflected
    keys = tensor.keys[canonical].copy()
    values = tensor.values[canonical].copy()
    tree = {
        **tensor.tree,
        "tensor_kind": (
            f"{tensor.tree.get('tensor_kind', 'TENSOR')}_COLUMN_EVEN_SECTOR"
        ),
        "nnz": int(keys.size),
        "full_nnz": tensor.nnz,
        "column_reflection_sector": "even",
    }
    return ParityTensor(
        name=tensor.name,
        labels=tensor.labels,
        dimensions=tensor.dimensions,
        keys=keys,
        values=values,
        tree=tree,
    )


def build_parity_copy_absorbed_network(n: int) -> list[ParityTensor]:
    """Build all invariant leaves directly in their global even sectors."""
    if n**n > UINT64_MAX:
        raise OverflowError("column-reflection sector exceeds the uint64 bound")
    return [
        _from_invariant_packed(tensor)
        for tensor in build_packed_copy_absorbed_network(n)
    ]


def _outside_labels(
    active: list[ParityTensor], left_index: int, right_index: int
) -> set[str]:
    return {
        label
        for index, tensor in enumerate(active)
        if index not in (left_index, right_index)
        for label in tensor.labels
    }


def _signature(
    left: ParityTensor,
    right: ParityTensor,
    outside_labels: set[str],
) -> tuple[list[str], list[str], list[str], dict[str, int]]:
    left_labels = set(left.labels)
    right_labels = set(right.labels)
    shared = [label for label in left.labels if label in right_labels]
    union_labels = list(left.labels) + [
        label for label in right.labels if label not in left_labels
    ]
    keep_labels = [label for label in union_labels if label in outside_labels]
    eliminated = [label for label in union_labels if label not in outside_labels]
    dimensions = {
        **dict(zip(left.labels, left.dimensions)),
        **dict(zip(right.labels, right.dimensions)),
    }
    for label in shared:
        if left.dimensions[left.labels.index(label)] != right.dimensions[
            right.labels.index(label)
        ]:
            raise ValueError(f"shared label {label} has inconsistent dimensions")
    return shared, keep_labels, eliminated, dimensions


def _coordinate(tensor: ParityTensor, position: int) -> np.ndarray:
    stride = prod(tensor.dimensions[position + 1 :])
    return (tensor.keys // stride) % tensor.dimensions[position]


def _coordinate_rows(
    tensor: ParityTensor, position: int, rows: np.ndarray
) -> np.ndarray:
    """Decode only selected rows, which is essential for disk-backed tensors."""
    stride = prod(tensor.dimensions[position + 1 :])
    return (tensor.keys[rows] // stride) % tensor.dimensions[position]


def _fixed_mask(tensor: ParityTensor) -> np.ndarray:
    fixed_key = _fixed_flat_key(tensor.dimensions)
    if fixed_key is None:
        return np.zeros(tensor.nnz, dtype=bool)
    return tensor.keys == fixed_key


def _encoded_coordinates(
    tensor: ParityTensor,
    labels: list[str],
    rows: np.ndarray,
    reflected: np.ndarray | None = None,
) -> np.ndarray:
    encoded = np.zeros(rows.size, dtype=np.uint64)
    selected_keys = tensor.keys[rows]
    for label in labels:
        position = tensor.labels.index(label)
        dimension = tensor.dimensions[position]
        stride = prod(tensor.dimensions[position + 1 :])
        coordinate = (selected_keys // stride) % dimension
        if reflected is not None:
            coordinate = np.where(
                reflected, dimension - 1 - coordinate, coordinate
            )
        encoded *= dimension
        encoded += coordinate
    return encoded


def _equality_join_plan(
    left_keys: np.ndarray,
    right_keys: np.ndarray,
    *,
    max_pairs: int | None = None,
) -> EqualityJoinPlan:
    """Build one reusable sorted-group plan without expanding row pairs."""
    uint32_limit = int(np.iinfo(np.uint32).max)
    if left_keys.size > uint32_limit or right_keys.size > uint32_limit:
        raise OverflowError("parity row indices exceed the uint32 backend")
    left_order = np.argsort(left_keys, kind="stable").astype(np.uint32)
    right_order = np.argsort(right_keys, kind="stable").astype(np.uint32)
    left_sorted = left_keys[left_order]
    right_sorted = right_keys[right_order]
    left_unique, left_start, left_count = np.unique(
        left_sorted, return_index=True, return_counts=True
    )
    right_unique, right_start, right_count = np.unique(
        right_sorted, return_index=True, return_counts=True
    )
    _, left_groups, right_groups = np.intersect1d(
        left_unique, right_unique, assume_unique=True, return_indices=True
    )
    matched_left_starts = left_start[left_groups].astype(
        np.uint64, copy=False
    )
    matched_left_counts = left_count[left_groups].astype(
        np.uint64, copy=False
    )
    matched_right_starts = right_start[right_groups].astype(
        np.uint64, copy=False
    )
    matched_right_counts = right_count[right_groups].astype(
        np.uint64, copy=False
    )
    group_pairs = matched_left_counts * matched_right_counts
    pair_offsets = np.empty(group_pairs.size + 1, dtype=np.uint64)
    pair_offsets[0] = 0
    np.cumsum(group_pairs, dtype=np.uint64, out=pair_offsets[1:])
    pair_count = int(pair_offsets[-1])
    plan = EqualityJoinPlan(
        left_order=left_order,
        right_order=right_order,
        left_starts=matched_left_starts,
        left_counts=matched_left_counts,
        right_starts=matched_right_starts,
        right_counts=matched_right_counts,
        pair_offsets=pair_offsets,
    )
    if max_pairs is not None and pair_count > max_pairs:
        raise JoinBudgetExceeded(pair_count, max_pairs, plan)
    return plan


def _equality_join(
    left_keys: np.ndarray,
    right_keys: np.ndarray,
    *,
    max_pairs: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    plan = _equality_join_plan(
        left_keys, right_keys, max_pairs=max_pairs
    )
    return _materialize_equality_join(plan)


def _materialize_equality_join(
    plan: EqualityJoinPlan,
) -> tuple[np.ndarray, np.ndarray]:
    """Expand a bounded plan for the reference in-memory CPU path."""
    pair_count = plan.pair_count
    left_rows = np.empty(pair_count, dtype=np.uint32)
    right_rows = np.empty(pair_count, dtype=np.uint32)
    cursor = 0
    for group in range(plan.group_count):
        left_begin = int(plan.left_starts[group])
        left_size = int(plan.left_counts[group])
        right_begin = int(plan.right_starts[group])
        right_size = int(plan.right_counts[group])
        block_size = int(left_size * right_size)
        left_block = plan.left_order[left_begin : left_begin + left_size]
        right_block = plan.right_order[right_begin : right_begin + right_size]
        left_rows[cursor : cursor + block_size] = np.repeat(
            left_block, right_size
        )
        right_rows[cursor : cursor + block_size] = np.tile(
            right_block, left_size
        )
        cursor += block_size
    return left_rows, right_rows


def _equality_join_blocks(
    left_keys: np.ndarray,
    right_keys: np.ndarray,
    *,
    max_block_pairs: int,
    plan: EqualityJoinPlan | None = None,
):
    """Yield exact equality-join row pairs without global materialization."""
    if max_block_pairs <= 0:
        raise ValueError("max_block_pairs must be positive")
    active_plan = plan or _equality_join_plan(left_keys, right_keys)
    for group in range(active_plan.group_count):
        left_begin = int(active_plan.left_starts[group])
        left_size = int(active_plan.left_counts[group])
        right_begin = int(active_plan.right_starts[group])
        right_size = int(active_plan.right_counts[group])
        left_block = active_plan.left_order[
            left_begin : left_begin + left_size
        ]
        right_block = active_plan.right_order[
            right_begin : right_begin + right_size
        ]
        if right_size <= max_block_pairs:
            left_chunk_size = max(1, max_block_pairs // right_size)
            for begin in range(0, left_size, left_chunk_size):
                left_chunk = left_block[begin : begin + left_chunk_size]
                yield (
                    np.repeat(left_chunk, right_size),
                    np.tile(right_block, left_chunk.size),
                )
        else:
            for left_row in left_block:
                for begin in range(0, right_size, max_block_pairs):
                    right_chunk = right_block[
                        begin : begin + max_block_pairs
                    ]
                    yield (
                        np.full(
                            right_chunk.size, left_row, dtype=np.uint32
                        ),
                        right_chunk.copy(),
                    )


def _grouped_parity_join_batches(
    *,
    plan: EqualityJoinPlan,
    anchor: ParityTensor,
    other: ParityTensor,
    anchor_fixed: np.ndarray,
    other_fixed: np.ndarray,
    other_orbit_rows: np.ndarray,
    other_orientations: np.ndarray,
    keep_labels: list[str],
    dimensions: dict[str, int],
    max_block_pairs: int,
):
    """Yield compact group slices for GPU-native contribution generation."""
    if max_block_pairs <= 0:
        raise ValueError("max_block_pairs must be positive")
    anchor_positions = {
        label: index for index, label in enumerate(anchor.labels)
    }
    other_positions = {
        label: index for index, label in enumerate(other.labels)
    }
    output_sources = np.empty(len(keep_labels), dtype=np.uint8)
    output_strides = np.empty(len(keep_labels), dtype=np.uint64)
    output_dimensions = np.asarray(
        [dimensions[label] for label in keep_labels], dtype=np.uint64
    )
    for output_position, label in enumerate(keep_labels):
        if label in anchor_positions:
            input_position = anchor_positions[label]
            output_sources[output_position] = 0
            output_strides[output_position] = prod(
                anchor.dimensions[input_position + 1 :]
            )
        else:
            input_position = other_positions[label]
            output_sources[output_position] = 1
            output_strides[output_position] = prod(
                other.dimensions[input_position + 1 :]
            )

    for pair_begin in range(0, plan.pair_count, max_block_pairs):
        pair_end = min(pair_begin + max_block_pairs, plan.pair_count)
        yield GroupedParityJoinWork(
            anchor_source_keys=anchor.keys,
            anchor_source_values=anchor.values,
            anchor_source_fixed=anchor_fixed,
            other_source_keys=other.keys,
            other_source_values=other.values,
            other_source_fixed=other_fixed,
            other_orbit_rows=other_orbit_rows,
            other_orientations=other_orientations,
            left_order=plan.left_order,
            right_order=plan.right_order,
            left_starts=plan.left_starts,
            left_counts=plan.left_counts,
            right_starts=plan.right_starts,
            right_counts=plan.right_counts,
            global_pair_offsets=plan.pair_offsets,
            pair_begin=pair_begin,
            pair_end=pair_end,
            output_sources=output_sources,
            output_strides=output_strides,
            output_dimensions=output_dimensions,
        )


def _pair_contributions(
    *,
    anchor: ParityTensor,
    other: ParityTensor,
    anchor_fixed: np.ndarray,
    other_fixed: np.ndarray,
    other_orbit_rows: np.ndarray,
    other_orientations: np.ndarray,
    anchor_rows: np.ndarray,
    other_oriented_rows: np.ndarray,
    keep_labels: list[str],
    dimensions: dict[str, int],
    output_dimensions: tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Compute canonical output records for one exact join block."""
    keep_pairs = ~(
        anchor_fixed[anchor_rows]
        & other_orientations[other_oriented_rows]
    )
    anchor_rows = anchor_rows[keep_pairs]
    other_oriented_rows = other_oriented_rows[keep_pairs]
    other_rows = other_orbit_rows[other_oriented_rows]
    other_reflected = other_orientations[other_oriented_rows]
    pair_count = int(anchor_rows.size)

    # Gather each sparse tensor key once per pair.  The previous formulation
    # repeated the same irregular host-memory gather for every output label.
    anchor_pair_keys = anchor.keys[anchor_rows]
    other_pair_keys = other.keys[other_rows]
    output_keys = np.zeros(pair_count, dtype=np.uint64)
    reflected_output = np.zeros(pair_count, dtype=np.uint64)
    anchor_positions = {
        label: index for index, label in enumerate(anchor.labels)
    }
    other_positions = {
        label: index for index, label in enumerate(other.labels)
    }
    for label in keep_labels:
        output_keys *= dimensions[label]
        if label in anchor_positions:
            position = anchor_positions[label]
            stride = prod(anchor.dimensions[position + 1 :])
            coordinate = (
                anchor_pair_keys // stride
            ) % anchor.dimensions[position]
        else:
            position = other_positions[label]
            dimension = other.dimensions[position]
            stride = prod(other.dimensions[position + 1 :])
            coordinate = (
                other_pair_keys // stride
            ) % dimension
            coordinate = np.where(
                other_reflected, dimension - 1 - coordinate, coordinate
            )
        output_keys += coordinate
        reflected_output *= dimensions[label]
        reflected_output += dimensions[label] - 1 - coordinate

    canonical_output = np.minimum(output_keys, reflected_output)
    output_fixed = output_keys == reflected_output
    union_fixed = anchor_fixed[anchor_rows] & other_fixed[other_rows]
    orbit_weights = np.where(output_fixed & ~union_fixed, 2, 1).astype(
        np.uint64
    )
    output_values = (
        anchor.values[anchor_rows]
        * other.values[other_rows]
        * orbit_weights
    )
    return canonical_output, output_values


def parity_multiply_and_reduce(
    left: ParityTensor,
    right: ParityTensor,
    *,
    outside_labels: set[str],
    name: str,
    max_join_pairs: int | None = None,
    block_reducer: ExactBlockReducer | None = None,
) -> tuple[ParityTensor, int, list[str]]:
    """Contract one representative of every simultaneous-reflection orbit."""
    reducer = block_reducer or NumPyBlockReducer()
    shared, keep_labels, eliminated, dimensions = _signature(
        left, right, outside_labels
    )
    # The anchor keeps its canonical orientation. Expand the smaller operand
    # into both orientations to reduce sorting and temporary-array traffic.
    if right.nnz <= left.nnz:
        anchor, other = left, right
    else:
        anchor, other = right, left
    anchor_fixed = _fixed_mask(anchor)
    other_fixed = _fixed_mask(other)

    anchor_base_rows = np.arange(anchor.nnz, dtype=np.uint32)
    other_base_rows = np.arange(other.nnz, dtype=np.uint32)
    other_reflectable = np.flatnonzero(~other_fixed).astype(np.uint32)
    other_orbit_rows = np.concatenate((other_base_rows, other_reflectable))
    other_orientations = np.concatenate(
        (
            np.zeros(other.nnz, dtype=bool),
            np.ones(other_reflectable.size, dtype=bool),
        )
    )

    join_plan = None
    gpu_plan_min_records = getattr(
        reducer, "grouped_join_min_records", 0
    )
    oriented_input_records = anchor.nnz + other_orbit_rows.size
    gpu_tensor_join_planner = getattr(
        reducer, "build_parity_equality_join_plan", None
    )
    attempted_gpu_tensor_plan = (
        gpu_tensor_join_planner is not None
        and oriented_input_records >= gpu_plan_min_records
    )
    if attempted_gpu_tensor_plan:
        join_plan = gpu_tensor_join_planner(
            anchor_keys=anchor.keys,
            anchor_dimensions=anchor.dimensions,
            anchor_shared_positions=tuple(
                anchor.labels.index(label) for label in shared
            ),
            other_keys=other.keys,
            other_dimensions=other.dimensions,
            other_shared_positions=tuple(
                other.labels.index(label) for label in shared
            ),
            other_fixed=other_fixed,
        )
    if join_plan is None:
        anchor_shared = _encoded_coordinates(
            anchor, shared, anchor_base_rows
        )
        other_shared = _encoded_coordinates(
            other,
            shared,
            other_orbit_rows,
            other_orientations,
        )
        gpu_join_planner = getattr(
            reducer, "build_equality_join_plan", None
        )
        if (
            not attempted_gpu_tensor_plan
            and gpu_join_planner is not None
            and anchor_shared.size + other_shared.size
            >= gpu_plan_min_records
        ):
            join_plan = gpu_join_planner(
                anchor_shared, other_shared
            )
        if join_plan is None:
            join_plan = _equality_join_plan(
                anchor_shared, other_shared
            )
    if (
        max_join_pairs is not None
        and join_plan.pair_count > max_join_pairs
    ):
        raise JoinBudgetExceeded(
            join_plan.pair_count, max_join_pairs, join_plan
        )
    anchor_rows, other_oriented_rows = _materialize_equality_join(
        join_plan
    )
    output_dimensions = tuple(dimensions[label] for label in keep_labels)
    canonical_output, output_values = _pair_contributions(
        anchor=anchor,
        other=other,
        anchor_fixed=anchor_fixed,
        other_fixed=other_fixed,
        other_orbit_rows=other_orbit_rows,
        other_orientations=other_orientations,
        anchor_rows=anchor_rows,
        other_oriented_rows=other_oriented_rows,
        keep_labels=keep_labels,
        dimensions=dimensions,
        output_dimensions=output_dimensions,
    )
    pair_count = int(canonical_output.size)
    result_keys, result_values = reducer.reduce(
        canonical_output, output_values
    )

    fixed_key = _fixed_flat_key(output_dimensions)
    fixed_count = (
        0
        if fixed_key is None
        else int(np.count_nonzero(result_keys == fixed_key))
    )
    full_nnz = int(
        2 * result_keys.size
        - fixed_count
    )
    tree = {
        "type": "hyper_contract",
        "name": name,
        "matched_indices": shared,
        "summed_indices": eliminated,
        "output_indices": keep_labels,
        "output_rank": len(keep_labels),
        "output_nnz": int(result_keys.size),
        "output_full_nnz": full_nnz,
        "column_reflection_sector": "even",
        "block_reducer_backend": reducer.statistics.backend,
        "left": left.tree,
        "right": right.tree,
    }
    return (
        ParityTensor(
            name=name,
            labels=tuple(keep_labels),
            dimensions=output_dimensions,
            keys=result_keys,
            values=result_values,
            tree=tree,
        ),
        pair_count,
        eliminated,
    )


def parity_multiply_and_reduce_streaming(
    left: ParityTensor,
    right: ParityTensor,
    *,
    outside_labels: set[str],
    name: str,
    expected_join_pairs: int,
    join_chunk_pairs: int,
    join_plan: EqualityJoinPlan | None = None,
    temp_directory: Path | None = None,
    merge_strategy: str = "sorted-runs",
    block_reducer: ExactBlockReducer | None = None,
) -> tuple[ParityTensor, int, list[str]]:
    """Contract through a disk-backed contribution stream with exact reduction."""
    reducer = block_reducer or NumPyBlockReducer()
    if expected_join_pairs < 0:
        raise ValueError("expected_join_pairs must be nonnegative")
    if join_chunk_pairs <= 0:
        raise ValueError("join_chunk_pairs must be positive")
    if merge_strategy not in ("sorted-runs", "single-sort"):
        raise ValueError("unknown streaming merge strategy")
    shared, keep_labels, eliminated, dimensions = _signature(
        left, right, outside_labels
    )
    if right.nnz <= left.nnz:
        anchor, other = left, right
    else:
        anchor, other = right, left
    anchor_fixed = _fixed_mask(anchor)
    other_fixed = _fixed_mask(other)

    anchor_base_rows = np.arange(anchor.nnz, dtype=np.uint32)
    other_base_rows = np.arange(other.nnz, dtype=np.uint32)
    other_reflectable = np.flatnonzero(~other_fixed).astype(np.uint32)
    other_orbit_rows = np.concatenate((other_base_rows, other_reflectable))
    other_orientations = np.concatenate(
        (
            np.zeros(other.nnz, dtype=bool),
            np.ones(other_reflectable.size, dtype=bool),
        )
    )
    if join_plan is None:
        anchor_shared = _encoded_coordinates(
            anchor, shared, anchor_base_rows
        )
        other_shared = _encoded_coordinates(
            other,
            shared,
            other_orbit_rows,
            other_orientations,
        )
        active_join_plan = _equality_join_plan(
            anchor_shared, other_shared
        )
    else:
        # The failed bounded in-memory attempt already paid for the stable
        # sort and matching-group construction.  Reuse it verbatim.
        anchor_shared = np.empty(0, dtype=np.uint64)
        other_shared = np.empty(0, dtype=np.uint64)
        active_join_plan = join_plan
    if active_join_plan.pair_count != expected_join_pairs:
        raise AssertionError(
            "streaming join plan differs from its predicted size"
        )
    output_dimensions = tuple(dimensions[label] for label in keep_labels)

    if temp_directory is not None:
        Path(temp_directory).mkdir(parents=True, exist_ok=True)
    storage = _DiskTensorStorage(temp_directory)
    workspace_path = storage.path
    record_dtype = np.dtype([("key", "<u8"), ("value", "<u8")])
    key_path = workspace_path / "keys.bin"
    value_path = workspace_path / "values.bin"
    raw_pair_count = 0
    pair_count = 0
    contribution_stage_started = perf_counter()
    run_write_seconds = 0.0
    external_merge_seconds = 0.0

    if merge_strategy == "sorted-runs":
        run_paths: list[Path] = []
        pending_keys: list[np.ndarray] = []
        pending_values: list[np.ndarray] = []
        pending_count = 0
        grouped_gpu_reducer = getattr(
            reducer, "reduce_grouped_parity_batches", None
        )
        asynchronous = bool(
            grouped_gpu_reducer is None
            and getattr(reducer, "prefer_async", False)
        )
        reduction_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="nqueens-stream-reducer",
            )
            if asynchronous
            else None
        )
        pending_reduction: Future[
            tuple[np.ndarray, np.ndarray]
        ] | None = None

        def write_completed_run(
            unique_keys: np.ndarray, unique_values: np.ndarray
        ) -> None:
            nonlocal run_write_seconds
            write_started = perf_counter()
            run_records = np.empty(unique_keys.size, dtype=record_dtype)
            run_records["key"] = unique_keys
            run_records["value"] = unique_values
            run_path = workspace_path / f"run_{len(run_paths):06d}.bin"
            run_records.tofile(run_path)
            run_paths.append(run_path)
            run_write_seconds += perf_counter() - write_started

        def drain_reduction() -> None:
            nonlocal pending_reduction
            if pending_reduction is None:
                return
            write_completed_run(*pending_reduction.result())
            pending_reduction = None

        def flush_run() -> None:
            nonlocal pending_count, pending_reduction
            if pending_count == 0:
                return
            if len(pending_keys) == 1:
                run_keys = pending_keys[0]
                run_values = pending_values[0]
            else:
                run_keys = np.concatenate(pending_keys)
                run_values = np.concatenate(pending_values)
            pending_keys.clear()
            pending_values.clear()
            pending_count = 0
            if reduction_executor is None:
                write_completed_run(*reducer.reduce(run_keys, run_values))
            else:
                # A single in-flight block is deliberate: while CUDA sorts
                # this immutable block, the main thread constructs the next
                # one without multiplying peak host memory by the run count.
                drain_reduction()
                reducer.statistics.async_submissions += 1
                pending_reduction = reduction_executor.submit(
                    reducer.reduce, run_keys, run_values
                )

        try:
            if grouped_gpu_reducer is not None:
                batches = _grouped_parity_join_batches(
                    plan=active_join_plan,
                    anchor=anchor,
                    other=other,
                    anchor_fixed=anchor_fixed,
                    other_fixed=other_fixed,
                    other_orbit_rows=other_orbit_rows,
                    other_orientations=other_orientations,
                    keep_labels=keep_labels,
                    dimensions=dimensions,
                    max_block_pairs=join_chunk_pairs,
                )
                for (
                    unique_keys,
                    unique_values,
                    valid_pairs,
                    raw_pairs,
                ) in grouped_gpu_reducer(batches):
                    raw_pair_count += raw_pairs
                    pair_count += valid_pairs
                    if unique_keys.size:
                        write_completed_run(unique_keys, unique_values)
            else:
                for (
                    anchor_rows,
                    other_oriented_rows,
                ) in _equality_join_blocks(
                    anchor_shared,
                    other_shared,
                    max_block_pairs=join_chunk_pairs,
                    plan=active_join_plan,
                ):
                    raw_pair_count += int(anchor_rows.size)
                    block_keys, block_values = _pair_contributions(
                        anchor=anchor,
                        other=other,
                        anchor_fixed=anchor_fixed,
                        other_fixed=other_fixed,
                        other_orbit_rows=other_orbit_rows,
                        other_orientations=other_orientations,
                        anchor_rows=anchor_rows,
                        other_oriented_rows=other_oriented_rows,
                        keep_labels=keep_labels,
                        dimensions=dimensions,
                        output_dimensions=output_dimensions,
                    )
                    pair_count += int(block_keys.size)
                    if pair_count > expected_join_pairs:
                        raise AssertionError(
                            "streaming join exceeded its predicted size"
                        )
                    if block_keys.size == 0:
                        continue
                    if (
                        pending_count
                        and pending_count + block_keys.size
                        > join_chunk_pairs
                    ):
                        flush_run()
                    pending_keys.append(block_keys)
                    pending_values.append(block_values)
                    pending_count += int(block_keys.size)
                    if pending_count >= join_chunk_pairs:
                        flush_run()

            if raw_pair_count != expected_join_pairs:
                raise AssertionError(
                    "streaming join size differs from the equality-join "
                    "preflight"
                )
            if grouped_gpu_reducer is None:
                flush_run()
                drain_reduction()
        finally:
            if reduction_executor is not None:
                reduction_executor.shutdown(wait=True)
        contribution_generation_seconds = (
            perf_counter() - contribution_stage_started
        )
        manifest_path = workspace_path / "runs.txt"
        manifest_path.write_text(
            "".join(f"{path}\n" for path in run_paths),
            encoding="utf-8",
        )
        merge_started = perf_counter()
        completed = subprocess.run(
            [
                str(_sorted_run_merger_binary()),
                str(key_path),
                str(value_path),
                str(manifest_path),
                "--fan-in",
                "128",
                "--threads",
                "4",
                "--workspace",
                str(workspace_path / "merge_stages"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(
                "sorted-run merger failed: " + completed.stderr.strip()
            )
        external_merge_seconds = perf_counter() - merge_started
        output_count = int(completed.stdout.strip())
        manifest_path.unlink()
        for run_path in run_paths:
            run_path.unlink()
        shutil.rmtree(workspace_path / "merge_stages")
    else:
        contribution_path = workspace_path / "contributions.bin"
        records = np.memmap(
            contribution_path,
            dtype=record_dtype,
            mode="w+",
            shape=(expected_join_pairs,),
        )
        for anchor_rows, other_oriented_rows in _equality_join_blocks(
            anchor_shared,
            other_shared,
            max_block_pairs=join_chunk_pairs,
            plan=active_join_plan,
        ):
            raw_pair_count += int(anchor_rows.size)
            block_keys, block_values = _pair_contributions(
                anchor=anchor,
                other=other,
                anchor_fixed=anchor_fixed,
                other_fixed=other_fixed,
                other_orbit_rows=other_orbit_rows,
                other_orientations=other_orientations,
                anchor_rows=anchor_rows,
                other_oriented_rows=other_oriented_rows,
                keep_labels=keep_labels,
                dimensions=dimensions,
                output_dimensions=output_dimensions,
            )
            block_end = pair_count + int(block_keys.size)
            if block_end > expected_join_pairs:
                raise AssertionError(
                    "streaming join exceeded its predicted size"
                )
            records["key"][pair_count:block_end] = block_keys
            records["value"][pair_count:block_end] = block_values
            pair_count = block_end
        if raw_pair_count != expected_join_pairs:
            raise AssertionError(
                "streaming join size differs from the equality-join preflight"
            )

        active_records = records[:pair_count]
        active_records.sort(order="key", kind="quicksort")
        records.flush()
        output_count = 0
        carry_key: np.uint64 | None = None
        carry_value: np.uint64 | None = None
        reduce_cells = max(1, join_chunk_pairs)
        with key_path.open("wb") as key_stream, value_path.open(
            "wb"
        ) as value_stream:
            for begin in range(0, pair_count, reduce_cells):
                end = min(begin + reduce_cells, pair_count)
                block = active_records[begin:end]
                block_keys = block["key"]
                block_values = block["value"]
                starts = np.empty(block_keys.size, dtype=bool)
                starts[0] = True
                starts[1:] = block_keys[1:] != block_keys[:-1]
                start_indices = np.flatnonzero(starts)
                unique_keys = block_keys[start_indices].copy()
                unique_values = np.add.reduceat(
                    block_values, start_indices, dtype=np.uint64
                )

                if carry_key is not None:
                    if unique_keys[0] == carry_key:
                        unique_values[0] += carry_value
                    else:
                        np.asarray([carry_key], dtype=np.uint64).tofile(
                            key_stream
                        )
                        np.asarray([carry_value], dtype=np.uint64).tofile(
                            value_stream
                        )
                        output_count += 1
                if unique_keys.size > 1:
                    unique_keys[:-1].tofile(key_stream)
                    unique_values[:-1].tofile(value_stream)
                    output_count += int(unique_keys.size - 1)
                carry_key = unique_keys[-1]
                carry_value = unique_values[-1]

            if carry_key is not None:
                np.asarray([carry_key], dtype=np.uint64).tofile(key_stream)
                np.asarray([carry_value], dtype=np.uint64).tofile(
                    value_stream
                )
                output_count += 1

        records.flush()
        mmap_handle = records._mmap
        del active_records
        del records
        mmap_handle.close()
        contribution_path.unlink()
        contribution_generation_seconds = (
            perf_counter() - contribution_stage_started
        )

    if key_path.stat().st_size != 8 * output_count:
        raise AssertionError("merged key file has the wrong size")
    if value_path.stat().st_size != 8 * output_count:
        raise AssertionError("merged value file has the wrong size")
    storage.validated_output = True

    if output_count:
        result_keys = np.memmap(
            key_path,
            dtype=np.uint64,
            mode="r",
            shape=(output_count,),
        )
        result_values = np.memmap(
            value_path,
            dtype=np.uint64,
            mode="r",
            shape=(output_count,),
        )
    else:
        result_keys = np.empty(0, dtype=np.uint64)
        result_values = np.empty(0, dtype=np.uint64)
        storage.cleanup()
        storage = None

    fixed_key = _fixed_flat_key(output_dimensions)
    if fixed_key is None or output_count == 0:
        fixed_count = 0
    else:
        fixed_count = int(
            np.searchsorted(result_keys, fixed_key, side="right")
            - np.searchsorted(result_keys, fixed_key, side="left")
        )
    full_nnz = int(2 * output_count - fixed_count)
    tree = {
        "type": "hyper_contract",
        "name": name,
        "matched_indices": shared,
        "summed_indices": eliminated,
        "output_indices": keep_labels,
        "output_rank": len(keep_labels),
        "output_nnz": output_count,
        "output_full_nnz": full_nnz,
        "column_reflection_sector": "even",
        "execution": f"disk_streaming_join_{merge_strategy}",
        "join_chunk_pairs": join_chunk_pairs,
        "join_group_count": active_join_plan.group_count,
        "raw_join_pairs": expected_join_pairs,
        "valid_join_pairs": pair_count,
        "gpu_grouped_contribution_generation": (
            grouped_gpu_reducer is not None
            if merge_strategy == "sorted-runs"
            else False
        ),
        "contribution_generation_seconds": (
            contribution_generation_seconds
        ),
        "run_write_seconds": run_write_seconds,
        "external_merge_seconds": external_merge_seconds,
        "merge_fan_in": 128 if merge_strategy == "sorted-runs" else None,
        "merge_threads": 4 if merge_strategy == "sorted-runs" else None,
        "block_reducer_backend": reducer.statistics.backend,
        "left": left.tree,
        "right": right.tree,
    }
    return (
        ParityTensor(
            name=name,
            labels=tuple(keep_labels),
            dimensions=output_dimensions,
            keys=result_keys,
            values=result_values,
            tree=tree,
            storage=storage,
        ),
        pair_count,
        eliminated,
    )


def greedy_parity_hyper_contract(
    tensors: list[ParityTensor],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    """Execute the topology-only tree entirely in the global even sector."""
    active = list(tensors)
    if not active:
        raise ValueError("at least one factor is required")
    plan, _ = packed_contraction_plan(active)
    symmetry_multiply_adds = 0
    max_join_pairs = 0
    max_rank = max(tensor.rank for tensor in active)
    max_nnz = max(tensor.nnz for tensor in active)
    max_full_nnz = max(tensor.full_nnz for tensor in active)
    max_dense = max(tensor.dense_cells for tensor in active)
    max_tensor_bytes = max(tensor.nbytes for tensor in active)
    max_live_array_bytes = sum(tensor.nbytes for tensor in active)

    for step, pair in enumerate(plan):
        left_index, right_index = pair
        outside = _outside_labels(active, left_index, right_index)
        result, operations, _ = parity_multiply_and_reduce(
            active[left_index],
            active[right_index],
            outside_labels=outside,
            name=f"hyper_contract_{step}",
        )
        symmetry_multiply_adds += operations
        max_join_pairs = max(max_join_pairs, operations)
        max_rank = max(max_rank, result.rank)
        max_nnz = max(max_nnz, result.nnz)
        max_full_nnz = max(max_full_nnz, result.full_nnz)
        max_dense = max(max_dense, result.dense_cells)
        max_tensor_bytes = max(max_tensor_bytes, result.nbytes)
        live_bytes = sum(tensor.nbytes for tensor in active)
        max_live_array_bytes = max(
            max_live_array_bytes, live_bytes + result.nbytes
        )
        for index in sorted(pair, reverse=True):
            active.pop(index)
        active.append(result)

    final = active[0]
    if final.labels:
        raise AssertionError("parity contraction did not produce a scalar")
    scalar = (
        int(final.values[0])
        if final.nnz == 1 and int(final.keys[0]) == 0
        else 0
    )
    return (
        scalar,
        final.tree,
        {
            "contractions": len(plan),
            "symmetry_multiply_adds": symmetry_multiply_adds,
            "max_join_pairs": max_join_pairs,
            "max_intermediate_rank": max_rank,
            "max_intermediate_even_sector_nnz": max_nnz,
            "max_intermediate_full_nnz": max_full_nnz,
            "max_intermediate_dense_cells": max_dense,
            "max_tensor_bytes": max_tensor_bytes,
            "max_live_array_bytes": max_live_array_bytes,
        },
    )
