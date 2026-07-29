from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import sys
from typing import Literal

import numpy as np
import numpy.typing as npt


Phase = Literal["validation", "benchmark", "pilot", "confirmatory"]
F64 = npt.NDArray[np.float64]
U32 = npt.NDArray[np.uint32]
U64 = npt.NDArray[np.uint64]

_STREAM_COUNT = 4
_UINT64_LIMIT = 1 << 64
_PHASES = frozenset(("validation", "benchmark", "pilot", "confirmatory"))
_HEX256 = re.compile(r"[0-9a-f]{64}")
_REQUEST_DOMAIN = b"challenge-194-trajectory-request-v1\0"


def _frozen_copy(array: np.ndarray, dtype: np.dtype) -> np.ndarray:
    copy = np.array(array, dtype=dtype, order="C", copy=True)
    copy.setflags(write=False)
    return copy


@dataclass(frozen=True)
class TrajectoryRequest:
    length: int
    sigma: float
    sigma_grid_id: str
    kappas: F64
    master_seed: int
    phase: Phase
    replica: int
    kernel_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kappas, np.ndarray)
            or self.kappas.dtype != np.dtype(np.float64)
            or self.kappas.ndim != 1
            or not self.kappas.flags.c_contiguous
        ):
            raise ValueError(
                "kappas must be a C-contiguous one-dimensional float64 array"
            )
        object.__setattr__(
            self,
            "kappas",
            _frozen_copy(self.kappas, np.dtype(np.float64)),
        )


@dataclass(frozen=True)
class TrajectoryResult:
    request_sha256: str
    observables: F64
    terminal_counters: U32
    draw_counts: U64
    event_count: int
    duplicate_count: int
    hash_diagnostics: U64

    def __post_init__(self) -> None:
        if not isinstance(self.request_sha256, str) or _HEX256.fullmatch(
            self.request_sha256
        ) is None:
            raise ValueError("request_sha256 must be a lowercase SHA-256 digest")
        arrays = (
            (self.observables, np.dtype(np.float64), 2, "observables"),
            (
                self.terminal_counters,
                np.dtype(np.uint32),
                2,
                "terminal_counters",
            ),
            (self.draw_counts, np.dtype(np.uint64), 2, "draw_counts"),
            (
                self.hash_diagnostics,
                np.dtype(np.uint64),
                1,
                "hash_diagnostics",
            ),
        )
        for value, dtype, ndim, name in arrays:
            if (
                not isinstance(value, np.ndarray)
                or value.dtype != dtype
                or value.ndim != ndim
                or not value.flags.c_contiguous
            ):
                raise ValueError(
                    f"{name} must be a C-contiguous {ndim}-dimensional "
                    f"{dtype.name} array"
                )
        if self.observables.shape[1:] != (10,):
            raise ValueError("observables must have shape (n_kappa, 10)")
        if self.terminal_counters.shape != (_STREAM_COUNT, 4):
            raise ValueError("terminal_counters must have shape (4, 4)")
        if self.draw_counts.shape != (_STREAM_COUNT, 3):
            raise ValueError("draw_counts must have shape (4, 3)")
        if self.hash_diagnostics.shape != (5,):
            raise ValueError("hash_diagnostics must have shape (5,)")
        for value, name in (
            (self.event_count, "event_count"),
            (self.duplicate_count, "duplicate_count"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative Python integer")
        if self.duplicate_count > self.event_count:
            raise ValueError("duplicate_count cannot exceed event_count")
        if not np.all(np.isfinite(self.observables)):
            raise ValueError("observables must be finite")
        for name, value, dtype in (
            ("observables", self.observables, np.dtype(np.float64)),
            ("terminal_counters", self.terminal_counters, np.dtype(np.uint32)),
            ("draw_counts", self.draw_counts, np.dtype(np.uint64)),
            ("hash_diagnostics", self.hash_diagnostics, np.dtype(np.uint64)),
        ):
            object.__setattr__(self, name, _frozen_copy(value, dtype))


@dataclass(frozen=True)
class TrajectoryDiagnostics:
    result: TrajectoryResult
    event_times: tuple[float, ...]
    edge_ids_by_checkpoint: tuple[frozenset[int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.result, TrajectoryResult):
            raise ValueError("result must be a TrajectoryResult")
        if len(self.edge_ids_by_checkpoint) != self.result.observables.shape[0]:
            raise ValueError("edge diagnostics must cover every checkpoint")
        if any(
            not math.isfinite(value) or value < 0.0
            for value in self.event_times
        ):
            raise ValueError("event times must be finite and nonnegative")
        if any(
            not isinstance(snapshot, frozenset)
            or any(
                isinstance(edge_id, bool)
                or not isinstance(edge_id, int)
                or edge_id < 0
                for edge_id in snapshot
            )
            for snapshot in self.edge_ids_by_checkpoint
        ):
            raise ValueError("edge diagnostics must contain nonnegative IDs")


def validate_trajectory_request(request: TrajectoryRequest) -> None:
    if not isinstance(request, TrajectoryRequest):
        raise ValueError("request must be a TrajectoryRequest")
    if (
        isinstance(request.length, bool)
        or not isinstance(request.length, int)
        or request.length < 2
        or request.length % 2
        or request.length > sys.maxsize
    ):
        raise ValueError("length must be an even addressable Python integer")
    if (
        isinstance(request.sigma, bool)
        or not isinstance(request.sigma, (int, float))
    ):
        raise ValueError("sigma must be a finite positive real number")
    sigma = float(request.sigma)
    exponent = 1.0 + sigma
    if (
        not math.isfinite(sigma)
        or sigma <= 0.0
        or not math.isfinite(exponent)
        or exponent <= 1.0
    ):
        raise ValueError(
            "sigma must be finite, positive, and satisfy 1.0 + sigma > 1.0"
        )
    if (
        not isinstance(request.kappas, np.ndarray)
        or request.kappas.dtype != np.dtype(np.float64)
        or request.kappas.ndim != 1
        or not request.kappas.flags.c_contiguous
        or request.kappas.size < 1
        or np.any(~np.isfinite(request.kappas))
        or np.any(request.kappas < 0.0)
        or (
            request.kappas.size > 1
            and np.any(request.kappas[1:] <= request.kappas[:-1])
        )
    ):
        raise ValueError(
            "kappas must be finite, nonnegative, sorted, unique float64 values"
        )
    for value, name in (
        (request.master_seed, "master_seed"),
        (request.replica, "replica"),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < _UINT64_LIMIT
        ):
            raise ValueError(f"{name} must fit uint64")
    if not isinstance(request.phase, str) or request.phase not in _PHASES:
        raise ValueError("phase is not in the frozen phase namespace")
    if (
        not isinstance(request.sigma_grid_id, str)
        or not request.sigma_grid_id
        or request.sigma_grid_id != request.sigma_grid_id.strip()
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in request.sigma_grid_id
        )
    ):
        raise ValueError(
            "sigma_grid_id must be trimmed, nonempty, and contain no controls"
        )
    try:
        request.sigma_grid_id.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("sigma_grid_id must be valid UTF-8") from error
    if (
        not isinstance(request.kernel_sha256, str)
        or _HEX256.fullmatch(request.kernel_sha256) is None
    ):
        raise ValueError("kernel_sha256 must be a lowercase SHA-256 digest")


def validate_kernel(request: TrajectoryRequest, kernel: F64) -> None:
    if (
        not isinstance(kernel, np.ndarray)
        or kernel.dtype != np.dtype(np.float64)
        or kernel.shape != (request.length // 2,)
        or not kernel.flags.c_contiguous
    ):
        raise ValueError(
            "kernel must be a C-contiguous float64 array with exact shape"
        )
    if np.any(~np.isfinite(kernel)) or np.any(kernel <= 0.0):
        raise ValueError("kernel must contain finite positive values")
    actual = hashlib.sha256(kernel.tobytes(order="C")).hexdigest()
    if actual != request.kernel_sha256:
        raise ValueError("kernel digest does not match kernel_sha256")


def validate_event_time_resolution(
    kappa_max: float,
    total_rate: float,
    minimum_hazard: float,
) -> None:
    if not math.isfinite(minimum_hazard) or minimum_hazard <= 0.0:
        raise ValueError("minimum exponential hazard must be finite and positive")
    terminal_hazard = kappa_max * total_rate
    if not math.isfinite(terminal_hazard):
        raise ValueError("largest coupling times total rate must be finite")
    if terminal_hazard < minimum_hazard:
        return
    minimum_delta = minimum_hazard / total_rate
    if minimum_delta == 0.0 or minimum_delta <= math.ulp(kappa_max):
        raise ValueError(
            "total rate is too large to preserve float64 event ordering"
        )


def request_digest(request: TrajectoryRequest) -> str:
    document = {
        "kernel_sha256": request.kernel_sha256,
        "kappas_le_f64": request.kappas.astype("<f8", copy=False).tobytes().hex(),
        "length": request.length,
        "master_seed": request.master_seed,
        "phase": request.phase,
        "replica": request.replica,
        "sigma": request.sigma,
        "sigma_grid_id": request.sigma_grid_id,
    }
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(_REQUEST_DOMAIN + encoded).hexdigest()


# Compatibility names used by existing internal tests and call sites.
_validate_kernel = validate_kernel
_validate_event_time_resolution = validate_event_time_resolution
_request_digest = request_digest
