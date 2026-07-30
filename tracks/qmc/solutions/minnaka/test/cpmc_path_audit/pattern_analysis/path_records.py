"""Memory-mapped reader for CPMC path-audit fixed-record binaries."""

from __future__ import annotations

from dataclasses import dataclass
import pathlib
import struct
from typing import Tuple
import math

import numpy as np


MAGIC = b"CPAUDIT\x00"
HEADER_STRUCT = struct.Struct("<8s12I3d2Q32x")
PATH_DTYPE_V2 = np.dtype(
    {
        "names": [
            "config_id",
            "log_d",
            "log_q",
            "log_w",
            "min_log_w",
            "min_overlap",
            "argmin_step",
            "first_rejected",
            "sign",
            "alive",
            "linear_bottleneck",
            "argmin_slice",
            "reserved",
        ],
        "formats": [
            "<u8",
            "<f8",
            "<f8",
            "<f8",
            "<f8",
            "<f8",
            "<u4",
            "<u4",
            "i1",
            "u1",
            "<f4",
            "u1",
            "u1",
        ],
        "offsets": [0, 8, 16, 24, 32, 40, 48, 52, 56, 57, 58, 62, 63],
        "itemsize": 64,
    }
)

TRIAL_NAMES = {1: "rhf_x", 2: "rhf_y", 3: "uhf"}
PROPOSAL_NAMES = {1: "site", 2: "joint"}
ORDER_NAMES = {1: "row", 2: "reverse", 3: "sublattice", 4: "na"}


@dataclass(frozen=True)
class PathHeader:
    format_version: int
    lx: int
    ly: int
    n_up: int
    n_down: int
    slices: int
    trial: str
    proposal: str
    order: str
    hopping: float
    interaction: float
    dt: float
    expected_records: int
    actual_records: int


def open_path_records(
    path: pathlib.Path | str,
) -> Tuple[PathHeader, np.memmap]:
    """Validate and memory-map one path-audit binary."""

    source = pathlib.Path(path)
    with source.open("rb") as stream:
        raw = stream.read(HEADER_STRUCT.size)
    if len(raw) != HEADER_STRUCT.size:
        raise ValueError(f"truncated header: {source}")
    values = HEADER_STRUCT.unpack(raw)
    (
        magic,
        version,
        header_bytes,
        record_bytes,
        endian_marker,
        lx,
        ly,
        n_up,
        n_down,
        slices,
        trial_code,
        proposal_code,
        order_code,
        hopping,
        interaction,
        dt,
        expected_records,
        actual_records,
    ) = values
    if magic != MAGIC:
        raise ValueError(f"invalid path magic: {source}")
    if version not in (1, 2):
        raise ValueError(f"unsupported path version {version}: {source}")
    if (
        header_bytes != HEADER_STRUCT.size
        or record_bytes != PATH_DTYPE_V2.itemsize
        or endian_marker != 0x01020304
    ):
        raise ValueError(f"unsupported path layout: {source}")
    if trial_code not in TRIAL_NAMES:
        raise ValueError(f"unknown trial code {trial_code}: {source}")
    if proposal_code not in PROPOSAL_NAMES:
        raise ValueError(f"unknown proposal code {proposal_code}: {source}")
    if order_code not in ORDER_NAMES:
        raise ValueError(f"unknown site-order code {order_code}: {source}")
    expected_size = header_bytes + record_bytes * actual_records
    if source.stat().st_size != expected_size:
        raise ValueError(
            f"path file size mismatch: expected {expected_size}, "
            f"found {source.stat().st_size}: {source}"
        )
    header = PathHeader(
        format_version=version,
        lx=lx,
        ly=ly,
        n_up=n_up,
        n_down=n_down,
        slices=slices,
        trial=TRIAL_NAMES[trial_code],
        proposal=PROPOSAL_NAMES[proposal_code],
        order=ORDER_NAMES[order_code],
        hopping=hopping,
        interaction=interaction,
        dt=dt,
        expected_records=expected_records,
        actual_records=actual_records,
    )
    records = np.memmap(
        source,
        mode="r",
        dtype=PATH_DTYPE_V2,
        offset=header_bytes,
        shape=(actual_records,),
    )
    return header, records


def logsumexp_field(
    records: np.ndarray, field: str, chunk_size: int = 1_000_000
) -> float:
    """Compute a stable log-sum-exp without materializing a field copy."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    maximum = -math.inf
    scaled_sum = 0.0
    for first in range(0, len(records), chunk_size):
        values = np.asarray(
            records[field][first : first + chunk_size], dtype=np.float64
        )
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        chunk_maximum = float(np.max(finite))
        if chunk_maximum > maximum:
            if math.isfinite(maximum):
                scaled_sum *= math.exp(maximum - chunk_maximum)
            maximum = chunk_maximum
        scaled_sum += float(np.exp(finite - maximum).sum(dtype=np.float64))
    if scaled_sum == 0.0:
        return -math.inf
    return maximum + math.log(scaled_sum)
