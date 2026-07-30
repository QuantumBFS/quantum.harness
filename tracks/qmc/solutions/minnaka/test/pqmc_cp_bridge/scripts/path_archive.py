#!/usr/bin/env python3
"""Reference reader/writer for the QHPATH01 append-only archive."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import struct
from typing import Iterator, Mapping, Sequence
import zlib


MAGIC = b"QHPATH01"
VERSION = 1
ENDIAN_MARKER = 0x01020304
HEADER_BYTES = 256
HEADER_STRUCT = struct.Struct("<8s12I5d4B64s64s")
RECORD_PREFIX = struct.Struct("<QIIQIIbbH4db7x4d")
CRC_STRUCT = struct.Struct("<I")
MAX_ARCHIVE_CHAINS = 2048


def _align64(value: int) -> int:
    return (value + 63) // 64 * 64


def _hash_bytes(value: str) -> bytes:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SHA-256 must be 64 lowercase hexadecimal characters")
    return value.encode("ascii")


@dataclass(frozen=True)
class ArchiveHeader:
    lx: int
    ly: int
    n_up: int
    n_down: int
    ltrot: int
    hopping: float
    interaction: float
    dt: float
    beta: float
    theta: float
    ensemble_code: int
    selected_projection_sha256: str
    trial_manifest_sha256: str
    bit_order_code: int = 1
    time_order_code: int = 1

    @property
    def nsites(self) -> int:
        return self.lx * self.ly

    @property
    def nfield(self) -> int:
        return self.ltrot * self.nsites

    @property
    def payload_bytes(self) -> int:
        return (self.nfield + 7) // 8

    @property
    def record_bytes(self) -> int:
        return _align64(RECORD_PREFIX.size + self.payload_bytes + 4)


@dataclass(frozen=True)
class ArchiveRecord:
    sample_id: int
    chain_id: int
    bin_id: int
    sweep_id: int
    frozen_sign: int
    central_ekin: float
    central_epot: float
    central_etot: float
    central_npart: float
    endpoint_sign: int
    endpoint_logabs_d: float
    endpoint_ekin: float
    endpoint_epot: float
    endpoint_etot: float
    fields: tuple[int, ...]
    endpoint_present: bool = True
    flags: int = 0


@dataclass(frozen=True)
class ArchiveScan:
    complete_records: int
    truncated_tail: bool


def _pack_header(header: ArchiveHeader) -> bytes:
    if header.ensemble_code not in (1, 2):
        raise ValueError("ensemble code must be 1=II or 2=TI")
    packed = HEADER_STRUCT.pack(
        MAGIC,
        VERSION,
        ENDIAN_MARKER,
        HEADER_BYTES,
        header.record_bytes,
        header.lx,
        header.ly,
        header.n_up,
        header.n_down,
        header.ltrot,
        header.nsites,
        header.nfield,
        header.payload_bytes,
        header.hopping,
        header.interaction,
        header.dt,
        header.beta,
        header.theta,
        header.ensemble_code,
        header.bit_order_code,
        header.time_order_code,
        0,
        _hash_bytes(header.selected_projection_sha256),
        _hash_bytes(header.trial_manifest_sha256),
    )
    if len(packed) > HEADER_BYTES:
        raise AssertionError("archive header exceeds 256 bytes")
    return packed + bytes(HEADER_BYTES - len(packed))


def _unpack_header(raw: bytes) -> ArchiveHeader:
    if len(raw) != HEADER_BYTES:
        raise ValueError("truncated archive header")
    values = HEADER_STRUCT.unpack(raw[:HEADER_STRUCT.size])
    (
        magic, version, endian, header_bytes, record_bytes,
        lx, ly, n_up, n_down, ltrot, nsites, nfield, payload_bytes,
        hopping, interaction, dt, beta, theta,
        ensemble, bit_order, time_order, reserved,
        selected_hash, trial_hash,
    ) = values
    if magic != MAGIC or version != VERSION:
        raise ValueError("unsupported archive magic or version")
    if endian != ENDIAN_MARKER or header_bytes != HEADER_BYTES:
        raise ValueError("archive endian/header mismatch")
    if reserved != 0 or any(raw[HEADER_STRUCT.size:]):
        raise ValueError("archive header reserved bytes are not zero")
    header = ArchiveHeader(
        lx=lx, ly=ly, n_up=n_up, n_down=n_down, ltrot=ltrot,
        hopping=hopping, interaction=interaction, dt=dt, beta=beta,
        theta=theta, ensemble_code=ensemble,
        selected_projection_sha256=selected_hash.decode("ascii"),
        trial_manifest_sha256=trial_hash.decode("ascii"),
        bit_order_code=bit_order, time_order_code=time_order,
    )
    if (
        nsites != header.nsites
        or nfield != header.nfield
        or payload_bytes != header.payload_bytes
        or record_bytes != header.record_bytes
    ):
        raise ValueError("archive derived sizes are inconsistent")
    if bit_order != 1 or time_order != 1:
        raise ValueError("unsupported field bit/time order")
    return header


def _pack_fields(fields: Sequence[int], nfield: int) -> bytes:
    if len(fields) != nfield:
        raise ValueError(f"expected {nfield} fields, found {len(fields)}")
    payload = bytearray((nfield + 7) // 8)
    for index, field in enumerate(fields):
        if field not in (-1, 1):
            raise ValueError("archive fields must be -1 or +1")
        if field == 1:
            payload[index // 8] |= 1 << (index % 8)
    return bytes(payload)


def _unpack_fields(payload: bytes, nfield: int) -> tuple[int, ...]:
    return tuple(
        1 if payload[index // 8] & (1 << (index % 8)) else -1
        for index in range(nfield)
    )


def _pack_record(header: ArchiveHeader, record: ArchiveRecord) -> bytes:
    if not 0 <= record.chain_id < MAX_ARCHIVE_CHAINS:
        raise ValueError(
            f"chain_id must be in [0,{MAX_ARCHIVE_CHAINS})"
        )
    if record.frozen_sign not in (-1, 0, 1):
        raise ValueError("invalid frozen sign")
    payload = _pack_fields(record.fields, header.nfield)
    endpoint_present = 1 if record.endpoint_present else 0
    if record.endpoint_present:
        endpoint = (
            record.endpoint_logabs_d, record.endpoint_ekin,
            record.endpoint_epot, record.endpoint_etot,
        )
    else:
        endpoint = (math.nan,) * 4
    prefix = RECORD_PREFIX.pack(
        record.sample_id, record.chain_id, record.bin_id, record.sweep_id,
        header.ltrot, header.nfield, record.frozen_sign, endpoint_present,
        record.flags, record.central_ekin, record.central_epot,
        record.central_etot, record.central_npart, record.endpoint_sign,
        *endpoint,
    )
    covered = prefix + payload
    crc = CRC_STRUCT.pack(zlib.crc32(covered) & 0xFFFFFFFF)
    raw = covered + crc
    return raw + bytes(header.record_bytes - len(raw))


def _unpack_record(header: ArchiveHeader, raw: bytes) -> ArchiveRecord:
    if len(raw) != header.record_bytes:
        raise ValueError("truncated archive record")
    payload_end = RECORD_PREFIX.size + header.payload_bytes
    stored_crc = CRC_STRUCT.unpack(
        raw[payload_end:payload_end + CRC_STRUCT.size]
    )[0]
    actual_crc = zlib.crc32(raw[:payload_end]) & 0xFFFFFFFF
    if stored_crc != actual_crc:
        raise ValueError("archive record CRC mismatch")
    if any(raw[payload_end + CRC_STRUCT.size:]):
        raise ValueError("archive record padding is not zero")
    values = RECORD_PREFIX.unpack(raw[:RECORD_PREFIX.size])
    (
        sample_id, chain_id, bin_id, sweep_id, ltrot, nfield,
        frozen_sign, endpoint_present, flags,
        central_ekin, central_epot, central_etot, central_npart,
        endpoint_sign, endpoint_logabs, endpoint_ekin, endpoint_epot,
        endpoint_etot,
    ) = values
    if ltrot != header.ltrot or nfield != header.nfield:
        raise ValueError("record/header projection mismatch")
    if endpoint_present not in (0, 1):
        raise ValueError("invalid endpoint_present")
    if endpoint_present == 0 and not all(math.isnan(value) for value in (
        endpoint_logabs, endpoint_ekin, endpoint_epot, endpoint_etot,
    )):
        raise ValueError("absent endpoint must use canonical NaN values")
    fields = _unpack_fields(
        raw[RECORD_PREFIX.size:payload_end], header.nfield
    )
    return ArchiveRecord(
        sample_id=sample_id, chain_id=chain_id, bin_id=bin_id,
        sweep_id=sweep_id, frozen_sign=frozen_sign,
        central_ekin=central_ekin, central_epot=central_epot,
        central_etot=central_etot, central_npart=central_npart,
        endpoint_sign=endpoint_sign, endpoint_logabs_d=endpoint_logabs,
        endpoint_ekin=endpoint_ekin, endpoint_epot=endpoint_epot,
        endpoint_etot=endpoint_etot, fields=fields,
        endpoint_present=bool(endpoint_present), flags=flags,
    )


class ArchiveReader:
    def __init__(
        self, path: Path, expected: Mapping[str, object] | None = None
    ):
        self.path = path
        with path.open("rb") as handle:
            self.header = _unpack_header(handle.read(HEADER_BYTES))
        for key, value in (expected or {}).items():
            actual = getattr(self.header, key)
            if actual != value:
                label = "ensemble" if key == "ensemble_code" else key
                raise ValueError(
                    f"archive {label} mismatch: {actual!r} != {value!r}"
                )

    def records(self) -> Iterator[ArchiveRecord]:
        with self.path.open("rb") as handle:
            handle.seek(HEADER_BYTES)
            while True:
                raw = handle.read(self.header.record_bytes)
                if not raw:
                    break
                if len(raw) != self.header.record_bytes:
                    break
                yield _unpack_record(self.header, raw)

    def scan(self) -> ArchiveScan:
        size = self.path.stat().st_size
        if size < HEADER_BYTES:
            raise ValueError("truncated archive")
        payload_size = size - HEADER_BYTES
        complete, remainder = divmod(
            payload_size, self.header.record_bytes
        )
        # Force CRC validation for every complete record.
        if sum(1 for _record in self.records()) != complete:
            raise ValueError("archive complete-record scan mismatch")
        return ArchiveScan(
            complete_records=complete,
            truncated_tail=(remainder != 0),
        )


def write_archive(
    path: Path, header: ArchiveHeader, records: Sequence[ArchiveRecord]
) -> None:
    with path.open("wb") as handle:
        handle.write(_pack_header(header))
        for record in records:
            handle.write(_pack_record(header, record))
