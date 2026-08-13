"""Frozen Survivor-A identity loading and exact transfer reconstruction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import sympy as sp

from oracle.oddcycle_word_operator import WordPairColumn, build_word_dictionary


_RESULT_SCHEMA = "oddcycle-local-hs-first-batch-v1"


@dataclass(frozen=True)
class FrozenSourceSpec:
    result_sha256: str
    source_cell_payload_sha256: str
    source_raw_file_sha256: str
    source_cell_id: str
    sample_index: int
    sample_seed: int
    exact_shift: sp.Rational
    exact_vacuum_value: sp.Rational
    exact_minimum_row_margin: sp.Rational


@dataclass(frozen=True)
class SurvivorASeed:
    source_result_sha256: str
    source_cell_payload_sha256: str
    source_cell_id: str
    sample_index: int
    seed: int
    words: tuple[tuple[int, ...], ...]
    transpose_words: tuple[tuple[int, ...], ...]
    weights: tuple[sp.Rational, ...]
    shift: sp.Rational
    vacuum_value: sp.Rational
    minimum_row_margin: sp.Rational


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _require_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _rational_object(value: object, field: str) -> sp.Rational:
    payload = _require_mapping(value, field)
    if set(payload) != {"numerator", "denominator"}:
        raise ValueError(f"{field} must be a rational object")
    numerator = _require_integer(payload["numerator"], f"{field}.numerator")
    denominator = _require_integer(payload["denominator"], f"{field}.denominator")
    if denominator == 0:
        raise ValueError(f"{field}.denominator must be nonzero")
    return sp.Rational(numerator, denominator)


def _word(value: object, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a nonempty word")
    word = tuple(_require_integer(symbol, field) for symbol in value)
    if any(symbol not in range(4) for symbol in word):
        raise ValueError(f"{field} symbols must be in 0, 1, 2, 3")
    return word


def _seed_payload(payload: Mapping[str, object], label: str) -> Mapping[str, object]:
    routes = _require_mapping(payload.get("routes"), "routes")
    portfolio = _require_mapping(routes.get("route_d_portfolio"), "route_d_portfolio")
    candidates = portfolio.get("accepted_reverse_construction_seeds")
    if not isinstance(candidates, list):
        raise ValueError("accepted_reverse_construction_seeds must be a list")
    matching = [
        _require_mapping(candidate, "accepted_reverse_construction_seed")
        for candidate in candidates
        if isinstance(candidate, Mapping) and candidate.get("label") == label
    ]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one survivor label {label!r}")
    return matching[0]


def _cell_summary(
    payload: Mapping[str, object], cell_id: str
) -> Mapping[str, object]:
    routes = _require_mapping(payload.get("routes"), "routes")
    portfolio = _require_mapping(routes.get("route_d_portfolio"), "route_d_portfolio")
    summaries = portfolio.get("cell_summaries")
    if not isinstance(summaries, list):
        raise ValueError("route_d_portfolio.cell_summaries must be a list")
    matches = [
        _require_mapping(summary, "route_d_portfolio.cell_summary")
        for summary in summaries
        if isinstance(summary, Mapping) and summary.get("cell_id") == cell_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one summary for source cell {cell_id!r}")
    return matches[0]


def _canonical_matrix_sha256(matrix: sp.MatrixBase) -> str:
    """Hash a shape-tagged row-major list of exact numerator/denominator pairs."""

    payload = {
        "columns": matrix.cols,
        "entries": [
            [int(sp.Rational(value).p), int(sp.Rational(value).q)]
            for value in matrix
        ],
        "rows": matrix.rows,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def load_survivor_a(
    result_path: Path,
    *,
    expected: FrozenSourceSpec,
    label: str = "A",
) -> SurvivorASeed:
    """Load Survivor A only when every frozen source identity matches."""

    raw = Path(result_path).read_bytes()
    result_sha256 = hashlib.sha256(raw).hexdigest()
    if result_sha256 != expected.result_sha256:
        raise ValueError("source result SHA-256 mismatch")
    try:
        result = _require_mapping(json.loads(raw), "result")
    except json.JSONDecodeError as error:
        raise ValueError("source result is not valid JSON") from error
    if result.get("schema") != _RESULT_SCHEMA:
        raise ValueError("source result schema mismatch")

    seed_payload = _seed_payload(result, label)
    source_cell_id = _require_string(
        seed_payload.get("source_cell_id"), "source_cell_id"
    )
    cell_summary = _cell_summary(result, source_cell_id)
    payload_sha256 = _require_string(
        seed_payload.get("source_cell_payload_sha256"),
        "source_cell_payload_sha256",
    )
    raw_file_sha256 = _require_string(
        seed_payload.get("source_raw_file_sha256"), "source_raw_file_sha256"
    )
    if (
        _require_string(cell_summary.get("payload_sha256"), "cell payload_sha256")
        != payload_sha256
        or _require_string(cell_summary.get("raw_file_sha256"), "cell raw_file_sha256")
        != raw_file_sha256
    ):
        raise ValueError("source cell digest reference mismatch")
    if payload_sha256 != expected.source_cell_payload_sha256:
        raise ValueError("source cell payload SHA-256 mismatch")
    if raw_file_sha256 != expected.source_raw_file_sha256:
        raise ValueError("source raw file SHA-256 mismatch")
    if source_cell_id != expected.source_cell_id:
        raise ValueError("source cell ID mismatch")

    sample_index = _require_integer(seed_payload.get("sample_index"), "sample_index")
    seed = _require_integer(seed_payload.get("seed"), "seed")
    shift = sp.Rational(_require_integer(seed_payload.get("exact_shift"), "exact_shift"))
    vacuum_value = _rational_object(
        seed_payload.get("exact_vacuum_value"), "exact_vacuum_value"
    )
    minimum_row_margin = _rational_object(
        seed_payload.get("exact_minimum_row_margin"),
        "exact_minimum_row_margin",
    )
    if sample_index != expected.sample_index:
        raise ValueError("source sample index mismatch")
    if seed != expected.sample_seed:
        raise ValueError("source sample seed mismatch")
    if shift != expected.exact_shift:
        raise ValueError("exact shift mismatch")
    if vacuum_value != expected.exact_vacuum_value:
        raise ValueError("exact vacuum value mismatch")
    if minimum_row_margin != expected.exact_minimum_row_margin:
        raise ValueError("exact minimum row margin mismatch")

    raw_words = seed_payload.get("source_words")
    raw_transpose_words = seed_payload.get("source_transpose_words")
    raw_weights = seed_payload.get("exact_weights")
    if not isinstance(raw_words, list) or not isinstance(raw_transpose_words, list):
        raise ValueError("source words must be lists")
    if not isinstance(raw_weights, list):
        raise ValueError("exact weights must be a list")
    words = tuple(_word(word, "source_words") for word in raw_words)
    transpose_words = tuple(
        _word(word, "source_transpose_words") for word in raw_transpose_words
    )
    weights = tuple(
        _rational_object(weight, "exact_weights") for weight in raw_weights
    )
    if not words or len(words) != len(transpose_words) or len(words) != len(weights):
        raise ValueError("source words and weights have incompatible lengths")
    if len(set(words)) != len(words):
        raise ValueError("source words must be distinct")
    if any(weight <= 0 for weight in weights) or sum(weights) != 1:
        raise ValueError("exact weights must be positive and sum to one")
    return SurvivorASeed(
        source_result_sha256=result_sha256,
        source_cell_payload_sha256=payload_sha256,
        source_cell_id=source_cell_id,
        sample_index=sample_index,
        seed=seed,
        words=words,
        transpose_words=transpose_words,
        weights=weights,
        shift=shift,
        vacuum_value=vacuum_value,
        minimum_row_margin=minimum_row_margin,
    )


def reconstruct_survivor_transfer(
    seed: SurvivorASeed,
) -> tuple[sp.ImmutableMatrix, tuple[WordPairColumn, ...], dict[str, object]]:
    """Replay the frozen Survivor-A transfer and its exact SPD certificate."""

    dictionary = {column.word: column for column in build_word_dictionary(2)}
    try:
        columns = tuple(dictionary[word] for word in seed.words)
    except KeyError as error:
        raise ValueError("Survivor A references a word outside length two") from error
    if len(columns) != 12:
        raise ValueError("Survivor A must declare exactly twelve columns")
    if tuple(column.transpose_word for column in columns) != seed.transpose_words:
        raise ValueError("Survivor A transpose words do not match the dictionary")
    transfer = sp.eye(columns[0].fock_pair.rows) * seed.shift
    for weight, column in zip(seed.weights, columns, strict=True):
        transfer += weight * column.fock_pair
    transfer = sp.ImmutableMatrix(transfer)
    margins = tuple(
        transfer[row, row]
        - sum(
            abs(transfer[row, column])
            for column in range(transfer.cols)
            if column != row
        )
        for row in range(transfer.rows)
    )
    minimum_margin = min(margins)
    certificate = {
        "canonical_matrix_sha256": _canonical_matrix_sha256(transfer),
        "minimum_row_margin": minimum_margin,
        "positive_diagonal": all(transfer[index, index] > 0 for index in range(transfer.rows)),
        "strict_symmetric_diagonal_dominance": all(margin > 0 for margin in margins),
        "symmetric": transfer == transfer.T,
    }
    return transfer, columns, certificate


__all__ = [
    "FrozenSourceSpec",
    "SurvivorASeed",
    "load_survivor_a",
    "reconstruct_survivor_transfer",
]
