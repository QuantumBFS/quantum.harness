from __future__ import annotations

import hashlib
import math

import numba
import numpy as np
import numpy.typing as npt

from .alias import AliasTable, draw_alias
from .counter_rng import (
    STREAM_ALIAS_COLUMN,
    STREAM_ALIAS_THRESHOLD,
    STREAM_COUNT,
    STREAM_EDGE_OFFSET,
    STREAM_EXPONENTIAL,
    StreamIdentity,
    bounded_u32,
    derive_stream_material,
    next_u32,
    uniform_open,
)
from .edge_set import (
    allocate_edge_set,
    build_class_start,
    edge_set_insert_kernel,
)
from .poisson_reference import (
    TrajectoryRequest,
    TrajectoryResult,
    _request_digest,
    _validate_event_time_resolution,
    _validate_kernel,
    validate_trajectory_request,
)
from .production_union_find import (
    _scan_basic_observables_kernel,
    allocate_union_find,
    union_incremental,
)


F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
U8 = npt.NDArray[np.uint8]
U32 = npt.NDArray[np.uint32]
U64 = npt.NDArray[np.uint64]

_MINIMUM_OPEN_HAZARD = -math.log(
    (float(np.iinfo(np.uint32).max) + 0.5) * (2.0**-32)
)
_MAX_INT64 = np.iinfo(np.int64).max
_MAX_UINT64 = np.iinfo(np.uint64).max
_LOW32 = np.uint64(0xFFFFFFFF)

_F64_1D = numba.types.Array(numba.float64, 1, "C")
_F64_1D_RO = numba.types.Array(
    numba.float64, 1, "C", readonly=True
)
_F64_2D = numba.types.Array(numba.float64, 2, "C")
_I64_1D = numba.types.Array(numba.int64, 1, "C")
_I64_1D_RO = numba.types.Array(numba.int64, 1, "C", readonly=True)
_U8_1D = numba.types.Array(numba.uint8, 1, "C")
_U8_2D = numba.types.Array(numba.uint8, 2, "C")
_U32_2D = numba.types.Array(numba.uint32, 2, "C")
_U64_1D = numba.types.Array(numba.uint64, 1, "C")
_U64_1D_RO = numba.types.Array(numba.uint64, 1, "C", readonly=True)
_U64_2D = numba.types.Array(numba.uint64, 2, "C")

_RUN_RESULT = numba.types.UniTuple(numba.int64, 3)
_RUN_SIGNATURE = _RUN_RESULT(
    numba.int64,
    _F64_1D_RO,
    numba.float64,
    _F64_1D_RO,
    _I64_1D_RO,
    _U64_1D_RO,
    _U64_1D,
    _U64_1D,
    _U8_1D,
    _U64_1D,
    _I64_1D,
    _I64_1D,
    _U8_1D,
    _F64_1D,
    _I64_1D,
    _U32_2D,
    _U32_2D,
    _U32_2D,
    _U8_2D,
    _U64_2D,
    _F64_2D,
)
_RECORD_SIGNATURE = numba.int64(
    numba.int64,
    numba.int64,
    _I64_1D,
    _I64_1D,
    _U8_1D,
    _F64_1D,
    _I64_1D,
    _F64_2D,
)


@numba.njit(
    _RECORD_SIGNATURE, cache=True, boundscheck=True, fastmath=False
)
def _record_checkpoint(
    length: int,
    row: int,
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
    output: F64,
) -> int:
    (
        status,
        open_edges,
        component_count,
        largest_size,
        second_largest_size,
        sum_size_sq,
        sum_size_fourth,
        q_g,
        four_sector_crossing,
    ) = _scan_basic_observables_kernel(
        parent, size, sector_mask, moments, counts
    )
    if status != 0:
        return 100 + status
    if (
        not math.isfinite(sum_size_sq)
        or not math.isfinite(sum_size_fourth)
        or not math.isfinite(q_g)
    ):
        return 200
    output[row, 0] = float(open_edges)
    output[row, 1] = float(component_count)
    output[row, 2] = float(largest_size)
    output[row, 3] = float(second_largest_size)
    output[row, 4] = float(largest_size) / float(length)
    output[row, 5] = float(second_largest_size) / float(length)
    output[row, 6] = sum_size_sq
    output[row, 7] = sum_size_fourth
    output[row, 8] = q_g
    output[row, 9] = 1.0 if four_sector_crossing else 0.0
    return 0


@numba.njit(
    _RUN_SIGNATURE,
    cache=True,
    boundscheck=True,
    fastmath=False,
)
def _run_poisson_kernel(
    length: int,
    kappas: F64,
    total_rate: float,
    alias_probability: F64,
    alias_index: I64,
    multiplicity: U64,
    class_start: U64,
    keys: U64,
    occupied: U8,
    hash_diagnostics: U64,
    parent: I64,
    size: I64,
    sector_mask: U8,
    moments: F64,
    counts: I64,
    counters: U32,
    keys_by_stream: U32,
    blocks: U32,
    lane_valid: U8,
    draw_counts: U64,
    output: F64,
) -> tuple[int, int, int]:
    checkpoint = 0
    current_kappa = 0.0
    event_count = 0
    duplicate_count = 0
    kappa_max = kappas[len(kappas) - 1]
    class_count = len(alias_probability)

    while checkpoint < len(kappas) and kappas[checkpoint] == 0.0:
        status = _record_checkpoint(
            length,
            checkpoint,
            parent,
            size,
            sector_mask,
            moments,
            counts,
            output,
        )
        if status != 0:
            return status, event_count, duplicate_count
        checkpoint += 1

    if kappa_max > 0.0:
        while True:
            exponential_uniform = uniform_open(
                counters[STREAM_EXPONENTIAL],
                keys_by_stream[STREAM_EXPONENTIAL],
                blocks[STREAM_EXPONENTIAL],
                lane_valid[STREAM_EXPONENTIAL],
                draw_counts[STREAM_EXPONENTIAL],
            )
            hazard = -math.log(exponential_uniform)
            remaining_kappa = kappa_max - current_kappa
            terminal_hazard = remaining_kappa * total_rate
            if (
                not math.isfinite(hazard)
                or hazard <= 0.0
                or not math.isfinite(terminal_hazard)
                or terminal_hazard < 0.0
            ):
                return 1, event_count, duplicate_count
            if hazard > terminal_hazard:
                break

            delta = hazard / total_rate
            next_kappa = current_kappa + delta
            if (
                not math.isfinite(delta)
                or delta <= 0.0
                or not math.isfinite(next_kappa)
                or next_kappa <= current_kappa
                or next_kappa > kappa_max
            ):
                return 2, event_count, duplicate_count

            while (
                checkpoint < len(kappas)
                and kappas[checkpoint] < next_kappa
            ):
                status = _record_checkpoint(
                    length,
                    checkpoint,
                    parent,
                    size,
                    sector_mask,
                    moments,
                    counts,
                    output,
                )
                if status != 0:
                    return status, event_count, duplicate_count
                checkpoint += 1

            rejection_threshold = (
                np.uint64(1 << 32) - np.uint64(class_count)
            ) % np.uint64(class_count)
            while True:
                column_word = next_u32(
                    counters[STREAM_ALIAS_COLUMN],
                    keys_by_stream[STREAM_ALIAS_COLUMN],
                    blocks[STREAM_ALIAS_COLUMN],
                    lane_valid[STREAM_ALIAS_COLUMN],
                    draw_counts[STREAM_ALIAS_COLUMN],
                )
                product = np.uint64(column_word) * np.uint64(class_count)
                if (product & _LOW32) < rejection_threshold:
                    if (
                        draw_counts[STREAM_ALIAS_COLUMN, 2]
                        == np.uint64(0xFFFFFFFFFFFFFFFF)
                    ):
                        return 3, event_count, duplicate_count
                    draw_counts[STREAM_ALIAS_COLUMN, 2] += np.uint64(1)
                    continue
                break
            threshold_word = next_u32(
                counters[STREAM_ALIAS_THRESHOLD],
                keys_by_stream[STREAM_ALIAS_THRESHOLD],
                blocks[STREAM_ALIAS_THRESHOLD],
                lane_valid[STREAM_ALIAS_THRESHOLD],
                draw_counts[STREAM_ALIAS_THRESHOLD],
            )
            selected = draw_alias(
                alias_probability,
                alias_index,
                column_word,
                threshold_word,
            )
            offset = int(
                bounded_u32(
                    int(multiplicity[selected]),
                    counters[STREAM_EDGE_OFFSET],
                    keys_by_stream[STREAM_EDGE_OFFSET],
                    blocks[STREAM_EDGE_OFFSET],
                    lane_valid[STREAM_EDGE_OFFSET],
                    draw_counts[STREAM_EDGE_OFFSET],
                )
            )

            if event_count == _MAX_INT64:
                return 4, event_count, duplicate_count
            event_count += 1
            edge_id = class_start[selected] + np.uint64(offset)
            keys, occupied, inserted = edge_set_insert_kernel(
                keys, occupied, hash_diagnostics, edge_id
            )
            if not inserted:
                if duplicate_count == _MAX_INT64:
                    return 5, event_count, duplicate_count
                duplicate_count += 1
            else:
                if counts[0] == _MAX_INT64:
                    return 6, event_count, duplicate_count
                counts[0] += 1
                distance = selected + 1
                left = offset
                right = (offset + distance) % length
                union_incremental(
                    parent,
                    size,
                    sector_mask,
                    moments,
                    counts,
                    left,
                    right,
                )
            current_kappa = next_kappa

            while (
                checkpoint < len(kappas)
                and kappas[checkpoint] <= current_kappa
            ):
                status = _record_checkpoint(
                    length,
                    checkpoint,
                    parent,
                    size,
                    sector_mask,
                    moments,
                    counts,
                    output,
                )
                if status != 0:
                    return status, event_count, duplicate_count
                checkpoint += 1

    while checkpoint < len(kappas):
        status = _record_checkpoint(
            length,
            checkpoint,
            parent,
            size,
            sector_mask,
            moments,
            counts,
            output,
        )
        if status != 0:
            return status, event_count, duplicate_count
        checkpoint += 1
    return 0, event_count, duplicate_count


def _validate_alias(
    request: TrajectoryRequest,
    kernel: F64,
    alias: AliasTable,
) -> None:
    if not isinstance(alias, AliasTable):
        raise ValueError("alias must be an AliasTable")
    class_count = request.length // 2
    arrays = (
        (alias.probability, np.dtype(np.float64), (class_count,), "probability"),
        (alias.alias, np.dtype(np.int64), (class_count,), "index"),
        (
            alias.multiplicity,
            np.dtype(np.uint64),
            (class_count,),
            "multiplicity",
        ),
        (
            alias.class_weight,
            np.dtype(np.float64),
            (class_count,),
            "class weight",
        ),
    )
    for value, dtype, shape, name in arrays:
        if (
            not isinstance(value, np.ndarray)
            or value.dtype != dtype
            or value.shape != shape
            or not value.flags.c_contiguous
        ):
            raise ValueError(
                f"alias {name} must be a C-contiguous {dtype.name} array "
                "with exact shape"
            )
    if (
        np.any(~np.isfinite(alias.probability))
        or np.any(alias.probability < 0.0)
        or np.any(alias.probability > 1.0)
    ):
        raise ValueError("alias probabilities must be finite and in [0, 1]")
    if np.any(alias.alias < 0) or np.any(alias.alias >= class_count):
        raise ValueError("alias index is outside the distance classes")

    expected_multiplicity = np.full(
        class_count, request.length, dtype=np.uint64
    )
    expected_multiplicity[-1] = np.uint64(request.length // 2)
    if not np.array_equal(alias.multiplicity, expected_multiplicity):
        raise ValueError("alias multiplicity does not match the ring classes")
    if int(alias.multiplicity.max()) > np.iinfo(np.uint32).max:
        raise ValueError("alias multiplicity exceeds the bounded-draw range")
    expected_weight = alias.multiplicity * kernel
    if (
        np.any(~np.isfinite(alias.class_weight))
        or np.any(alias.class_weight <= 0.0)
        or not np.array_equal(alias.class_weight, expected_weight)
    ):
        raise ValueError("alias class weights do not match kernel rates")
    expected_total = math.fsum(float(value) for value in expected_weight)
    if (
        not isinstance(alias.total_rate, (int, float))
        or not math.isfinite(float(alias.total_rate))
        or float(alias.total_rate) <= 0.0
        or float(alias.total_rate) != expected_total
    ):
        raise ValueError("alias total rate is not the canonical finite sum")
    if (
        alias.kernel_sha256 != request.kernel_sha256
        or alias.kernel_sha256
        != hashlib.sha256(kernel.tobytes(order="C")).hexdigest()
    ):
        raise ValueError("alias kernel digest does not match the request")
    expected_residual = (
        math.fsum(float(value / expected_total) for value in expected_weight)
        - 1.0
    )
    if (
        not isinstance(alias.normalized_residual, (int, float))
        or not math.isfinite(float(alias.normalized_residual))
        or float(alias.normalized_residual) != expected_residual
    ):
        raise ValueError("alias normalized residual is not canonical")


def _build_stream_state(
    request: TrajectoryRequest,
) -> tuple[U32, U32, U32, U8, U64]:
    counters = np.empty((STREAM_COUNT, 4), dtype=np.uint32)
    keys = np.empty((STREAM_COUNT, 2), dtype=np.uint32)
    fingerprints: set[str] = set()
    for stream_id in range(STREAM_COUNT):
        material = derive_stream_material(
            StreamIdentity(
                master_seed=request.master_seed,
                phase=request.phase,
                length=request.length,
                sigma_grid_id=request.sigma_grid_id,
                replica=request.replica,
                stream_id=stream_id,
            )
        )
        if material.material_sha256 in fingerprints:
            raise ValueError("derived RNG stream material collides")
        fingerprints.add(material.material_sha256)
        counters[stream_id] = material.initial_counter
        keys[stream_id] = material.key
    return (
        counters,
        keys,
        np.zeros((STREAM_COUNT, 4), dtype=np.uint32),
        np.zeros((STREAM_COUNT, 2), dtype=np.uint8),
        np.zeros((STREAM_COUNT, 3), dtype=np.uint64),
    )


def run_poisson_numba(
    request: TrajectoryRequest,
    kernel: F64,
    alias: AliasTable,
) -> TrajectoryResult:
    validate_trajectory_request(request)
    _validate_kernel(request, kernel)
    _validate_alias(request, kernel, alias)
    total_rate = float(alias.total_rate)
    kappa_max = float(request.kappas[-1])
    _validate_event_time_resolution(
        kappa_max, total_rate, _MINIMUM_OPEN_HAZARD
    )
    terminal_hazard = kappa_max * total_rate
    if (
        math.isfinite(terminal_hazard)
        and terminal_hazard > float(_MAX_INT64)
    ):
        raise ValueError("expected event count exceeds the int64 engine range")
    canonical_edges = request.length * (request.length - 1) // 2
    if canonical_edges > _MAX_INT64:
        raise ValueError("canonical edge count exceeds the int64 engine range")

    class_start = build_class_start(alias.multiplicity)
    counters, stream_keys, blocks, lane_valid, draw_counts = (
        _build_stream_state(request)
    )
    keys, occupied, hash_diagnostics = allocate_edge_set(0)
    parent, size, sector_mask, moments, counts = allocate_union_find(
        request.length
    )
    output = np.empty((request.kappas.size, 10), dtype=np.float64)

    status, event_count, duplicate_count = _run_poisson_kernel(
        request.length,
        request.kappas,
        total_rate,
        alias.probability,
        alias.alias,
        alias.multiplicity,
        class_start,
        keys,
        occupied,
        hash_diagnostics,
        parent,
        size,
        sector_mask,
        moments,
        counts,
        counters,
        stream_keys,
        blocks,
        lane_valid,
        draw_counts,
        output,
    )
    if status != 0:
        details = {
            1: "nonfinite exponential terminal comparison",
            2: "event time failed finite strict advancement",
            3: "alias rejection accounting overflow",
            4: "event counter overflow",
            5: "duplicate counter overflow",
            6: "open-edge counter overflow",
            200: "nonfinite checkpoint observable",
        }
        detail = details.get(
            int(status), "incremental union-find checkpoint mismatch"
        )
        raise RuntimeError(
            f"Poisson kernel failed with status {status}: {detail}"
        )

    return TrajectoryResult(
        request_sha256=_request_digest(request),
        observables=output,
        terminal_counters=counters,
        draw_counts=draw_counts,
        event_count=int(event_count),
        duplicate_count=int(duplicate_count),
        hash_diagnostics=hash_diagnostics,
    )


def assert_nopython_signatures() -> None:
    if numba.config.DISABLE_JIT:
        raise RuntimeError("nopython signatures are unavailable with JIT disabled")
    dispatchers = (_run_poisson_kernel, _record_checkpoint)
    missing = [
        dispatcher.py_func.__name__
        for dispatcher in dispatchers
        if not dispatcher.nopython_signatures
    ]
    if missing:
        raise RuntimeError(
            "production kernels lack nopython signatures: " + ", ".join(missing)
        )
