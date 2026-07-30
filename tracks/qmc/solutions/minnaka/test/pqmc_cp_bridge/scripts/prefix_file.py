#!/usr/bin/env python3
"""Reader for the fixed little-endian QHPFX01 C++ prefix format."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Iterator
import zlib


HEADER = struct.Struct("<8s4IQ32x")
RECORD = struct.Struct("<QI?3x6dI4x")


@dataclass(frozen=True)
class PrefixRecord:
    sample_id: int
    slice: int
    alive: bool
    logq: float
    logw_ratio: float
    logw_phys: float
    log_normalized_overlap: float
    sigma_min: float
    min_q_in_slice: float


def records(path: Path) -> Iterator[PrefixRecord]:
    with path.open("rb") as handle:
        raw_header = handle.read(HEADER.size)
        if len(raw_header) != HEADER.size:
            raise ValueError("truncated prefix header")
        magic, version, endian, header_bytes, record_bytes, count = (
            HEADER.unpack(raw_header)
        )
        if (
            magic != b"QHPFX01\0"
            or version != 1
            or endian != 0x01020304
            or header_bytes != HEADER.size
            or record_bytes != RECORD.size
        ):
            raise ValueError("unsupported prefix format")
        for _ in range(count):
            raw = handle.read(RECORD.size)
            if len(raw) != RECORD.size:
                raise ValueError("truncated prefix record")
            values = RECORD.unpack(raw)
            if zlib.crc32(raw[:64]) & 0xFFFFFFFF != values[-1]:
                raise ValueError("prefix record CRC mismatch")
            yield PrefixRecord(*values[:-1])
        if handle.read(1):
            raise ValueError("prefix file has trailing bytes")
