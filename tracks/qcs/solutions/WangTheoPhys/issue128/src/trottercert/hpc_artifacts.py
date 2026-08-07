from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .cubic_field import Cubic
from .cubic_local import CubicTerms
from .local_commutators import CoordinateRegistry, SymplecticPauli, _iter_set_bits


CoordinatePauli = tuple[tuple[int, int, str], ...]
EncodedCubicTerm = list[object]
CoordinateCubicTerms = dict[CoordinatePauli, Cubic]


def _pauli_coordinates(
    registry: CoordinateRegistry,
    pauli: SymplecticPauli,
) -> CoordinatePauli:
    x_mask, z_mask = pauli
    result: list[tuple[int, int, str]] = []
    for site in _iter_set_bits(x_mask | z_mask):
        bit = 1 << site
        x = bool(x_mask & bit)
        z = bool(z_mask & bit)
        operator = "Y" if x and z else ("X" if x else "Z")
        coordinate = registry.coordinate(site)
        result.append((coordinate[0], coordinate[1], operator))
    return tuple(sorted(result))


def _pair(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _encode_cubic(value: Cubic) -> list[list[int]]:
    return [_pair(value.a0), _pair(value.a1), _pair(value.a2)]


def _decode_fraction(value: object) -> Fraction:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or isinstance(value[0], bool)
        or isinstance(value[1], bool)
        or not isinstance(value[0], int)
        or not isinstance(value[1], int)
        or value[1] <= 0
    ):
        raise ValueError("malformed rational pair")
    return Fraction(value[0], value[1])


def _decode_cubic(value: object) -> Cubic:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("malformed cubic coefficient")
    return Cubic(*(_decode_fraction(part) for part in value))


def cubic_to_json(value: Cubic) -> list[list[int]]:
    return _encode_cubic(value)


def cubic_from_json(value: object) -> Cubic:
    return _decode_cubic(value)


def coordinate_encode_terms(
    registry: CoordinateRegistry,
    terms: Mapping[SymplecticPauli, Cubic],
) -> list[EncodedCubicTerm]:
    encoded = [
        [
            [[x, y, operator] for x, y, operator in _pauli_coordinates(registry, pauli)],
            _encode_cubic(coefficient),
        ]
        for pauli, coefficient in terms.items()
    ]
    return sorted(encoded, key=lambda term: term[0])


def coordinate_decode_terms(
    terms: object,
) -> CoordinateCubicTerms:
    if not isinstance(terms, list):
        raise ValueError("encoded terms must be a list")
    result: CoordinateCubicTerms = {}
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("malformed encoded term")
        raw_key, raw_coefficient = term
        if not isinstance(raw_key, list):
            raise ValueError("malformed coordinate Pauli key")
        key_parts: list[tuple[int, int, str]] = []
        for part in raw_key:
            if (
                not isinstance(part, list)
                or len(part) != 3
                or isinstance(part[0], bool)
                or isinstance(part[1], bool)
                or not isinstance(part[0], int)
                or not isinstance(part[1], int)
                or part[2] not in {"X", "Y", "Z"}
            ):
                raise ValueError("malformed coordinate Pauli factor")
            key_parts.append((part[0], part[1], part[2]))
        key = tuple(sorted(key_parts))
        if key in result:
            raise ValueError("duplicate coordinate Pauli term")
        coefficient = _decode_cubic(raw_coefficient)
        if coefficient == Cubic.zero():
            raise ValueError("encoded shard contains a zero coefficient")
        result[key] = coefficient
    return result


def coordinate_terms_to_json(
    terms: Mapping[CoordinatePauli, Cubic],
) -> list[EncodedCubicTerm]:
    return [
        [
            [[x, y, operator] for x, y, operator in key],
            _encode_cubic(terms[key]),
        ]
        for key in sorted(terms)
    ]


def coordinate_encode_series(
    registry: CoordinateRegistry,
    series: Sequence[Mapping[SymplecticPauli, Cubic]],
) -> list[list[EncodedCubicTerm]]:
    return [coordinate_encode_terms(registry, degree) for degree in series]


def merge_coordinate_series(
    shards: Sequence[Sequence[object]],
) -> list[CoordinateCubicTerms]:
    if not shards:
        return []
    order = len(shards[0])
    if any(len(shard) != order for shard in shards):
        raise ValueError("coordinate series orders differ")
    result: list[CoordinateCubicTerms] = [{} for _ in range(order)]
    for shard in shards:
        for degree, raw_terms in enumerate(shard):
            for key, coefficient in coordinate_decode_terms(raw_terms).items():
                updated = result[degree].get(key, Cubic.zero()) + coefficient
                if updated == Cubic.zero():
                    result[degree].pop(key, None)
                else:
                    result[degree][key] = updated
    return result


def _canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_shard_gzip(path: str | Path, payload: object) -> None:
    raw = gzip.compress(_canonical_json_bytes(payload), compresslevel=9, mtime=0)
    _atomic_write(Path(path), raw)


def read_shard_gzip(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    try:
        payload = json.loads(gzip.decompress(raw))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("shard is not valid canonical gzip JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("shard root must be an object")
    expected = gzip.compress(_canonical_json_bytes(payload), compresslevel=9, mtime=0)
    if expected != raw:
        raise ValueError("shard gzip JSON is not canonical")
    return payload


def write_manifest_atomic(path: str | Path, payload: object) -> None:
    _atomic_write(Path(path), _canonical_json_bytes(payload))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
