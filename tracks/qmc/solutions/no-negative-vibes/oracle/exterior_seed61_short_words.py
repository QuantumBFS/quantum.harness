"""Exact finite-word verifier for the frozen seed-61 transpose pair.

The safe word symmetries are cyclic rotation and
``w -> complement(reverse(w))``, the latter being induced by matrix
transposition.  Binary necklaces are generated directly, then paired under
that twisted reflection.  A global bit complement is deliberately *not*
used: it does not preserve the seed-61 determinant series from length six.

For a common exact denominator ``s`` and integer atoms ``M_a = s B_a``,

``det(I + B_w) = det(s^|w| I + M_w) / s^(5 |w|)``.

Each shard therefore performs only sparse integer matrix products and a
fraction-free 5-by-5 determinant.  No floating-point acceptance gate is
present.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from fractions import Fraction
from math import lcm
from pathlib import Path

import sympy as sp

from .exterior_candidates import candidate_card, candidate_id, exact_atoms_from_card
from .exterior_seed61_positive_realization import transpose_reversal_word


SCHEMA_VERSION = "exterior-seed61-short-words-v1"
TEMPLATE = "exact5-shear-loop-pair"
SEED = 61
DIMENSION = 5

Matrix = tuple[tuple[int, ...], ...]
Word = tuple[int, ...]


def _checked_word(word: Sequence[int]) -> Word:
    checked = tuple(word)
    if any(
        not isinstance(symbol, int)
        or isinstance(symbol, bool)
        or symbol not in (0, 1)
        for symbol in checked
    ):
        raise ValueError("word entries must be 0 or 1")
    return checked


def _rotations(word: Word) -> Iterator[Word]:
    if not word:
        yield ()
        return
    for offset in range(len(word)):
        yield word[offset:] + word[:offset]


def symmetry_orbit(word: Sequence[int]) -> frozenset[Word]:
    """Return the exact cyclic/transpose-reversal orbit of one word."""

    checked = _checked_word(word)
    reflected = transpose_reversal_word(checked)
    return frozenset((*_rotations(checked), *_rotations(reflected)))


def canonical_word(word: Sequence[int]) -> Word:
    """Return the lexicographically least safe symmetry representative."""

    orbit = symmetry_orbit(word)
    return min(orbit) if orbit else ()


def _binary_necklaces(length: int) -> Iterator[Word]:
    """Generate lexicographically ordered binary necklaces (FKM algorithm)."""

    if not isinstance(length, int) or isinstance(length, bool) or length < 0:
        raise ValueError("length must be a nonnegative integer")
    if length == 0:
        yield ()
        return

    symbols = [0] * (length + 1)

    def visit(position: int, period: int) -> Iterator[Word]:
        if position > length:
            if length % period == 0:
                yield tuple(symbols[1:])
            return
        symbols[position] = symbols[position - period]
        yield from visit(position + 1, period)
        for symbol in range(symbols[position - period] + 1, 2):
            symbols[position] = symbol
            yield from visit(position + 1, position)

    yield from visit(1, 1)


def canonical_words(length: int) -> Iterator[Word]:
    """Generate one ordered representative per safe word-symmetry class."""

    for necklace in _binary_necklaces(length):
        reflected_necklace = min(_rotations(transpose_reversal_word(necklace)))
        if necklace <= reflected_necklace:
            yield necklace


def _integer_seed61_atoms() -> tuple[int, tuple[Matrix, Matrix], str]:
    """Replay the frozen exact card and clear one common atom denominator."""

    card = candidate_card(template=TEMPLATE, seed=SEED)
    exact_atoms = exact_atoms_from_card(card)
    if len(exact_atoms) != 2 or exact_atoms[1] != exact_atoms[0].T:
        raise ArithmeticError("seed 61 is no longer an exact transpose pair")
    if exact_atoms[0].shape != (DIMENSION, DIMENSION):
        raise ArithmeticError("seed 61 no longer has dimension five")

    scale = 1
    for atom in exact_atoms:
        for value in atom:
            scale = lcm(scale, int(sp.denom(value)))
    integer_atoms = tuple(
        tuple(
            tuple(int(sp.Rational(value) * scale) for value in atom.row(row))
            for row in range(DIMENSION)
        )
        for atom in exact_atoms
    )
    if any(
        sp.ImmutableMatrix(atom) / scale != exact
        for atom, exact in zip(integer_atoms, exact_atoms, strict=True)
    ):
        raise ArithmeticError("integer atom replay failed")
    if any(sp.det(exact) != 1 for exact in exact_atoms):
        raise ArithmeticError("seed-61 atoms are no longer unimodular")
    return scale, (integer_atoms[0], integer_atoms[1]), candidate_id(card)


def _identity() -> Matrix:
    return tuple(
        tuple(int(row == column) for column in range(DIMENSION))
        for row in range(DIMENSION)
    )


def _sparse_columns(matrix: Matrix) -> tuple[tuple[tuple[int, int], ...], ...]:
    return tuple(
        tuple(
            (row, matrix[row][column])
            for row in range(DIMENSION)
            if matrix[row][column]
        )
        for column in range(DIMENSION)
    )


def _right_multiply_sparse(
    left: Matrix,
    right_columns: tuple[tuple[tuple[int, int], ...], ...],
) -> Matrix:
    return tuple(
        tuple(
            sum(left[row][inner] * value for inner, value in column)
            for column in right_columns
        )
        for row in range(DIMENSION)
    )


def _bareiss_determinant(matrix: Matrix) -> int:
    """Return the exact integer determinant by fraction-free elimination."""

    work = [list(row) for row in matrix]
    sign = 1
    previous = 1
    for pivot_index in range(DIMENSION - 1):
        if work[pivot_index][pivot_index] == 0:
            swap = next(
                (
                    row
                    for row in range(pivot_index + 1, DIMENSION)
                    if work[row][pivot_index]
                ),
                None,
            )
            if swap is None:
                return 0
            work[pivot_index], work[swap] = work[swap], work[pivot_index]
            sign = -sign
        pivot = work[pivot_index][pivot_index]
        for row in range(pivot_index + 1, DIMENSION):
            for column in range(pivot_index + 1, DIMENSION):
                numerator = (
                    work[row][column] * pivot
                    - work[row][pivot_index] * work[pivot_index][column]
                )
                quotient, remainder = divmod(numerator, previous)
                if remainder:
                    raise ArithmeticError("Bareiss division was not exact")
                work[row][column] = quotient
        previous = pivot
    return sign * work[-1][-1]


def _scaled_weight_numerator(product_matrix: Matrix, length: int, scale: int) -> int:
    identity_scale = scale**length
    shifted = tuple(
        tuple(
            product_matrix[row][column]
            + (identity_scale if row == column else 0)
            for column in range(DIMENSION)
        )
        for row in range(DIMENSION)
    )
    return _bareiss_determinant(shifted)


def _ratio_less(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    return int(left["numerator"]) * int(right["denominator"]) < int(
        right["numerator"]
    ) * int(left["denominator"])


def _weight_record(numerator: int, denominator: int, word: Word) -> dict[str, object]:
    reduced = Fraction(numerator, denominator)
    return {
        "numerator": str(reduced.numerator),
        "denominator": str(reduced.denominator),
        "word": list(word),
        "length": len(word),
    }


def _longest_common_prefix(left: Word, right: Word) -> int:
    shared = 0
    for first, second in zip(left, right):
        if first != second:
            break
        shared += 1
    return shared


def scan_shard(
    *,
    max_depth: int,
    shard_id: int = 0,
    shard_count: int = 1,
    min_depth: int = 1,
    stop_on_nonpositive: bool = False,
) -> dict[str, object]:
    """Exactly scan one deterministic shard of the safe symmetry classes."""

    if (
        not isinstance(min_depth, int)
        or isinstance(min_depth, bool)
        or min_depth < 1
        or not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or max_depth < min_depth
    ):
        raise ValueError("require integer depths with 1 <= min_depth <= max_depth")
    if (
        not isinstance(shard_count, int)
        or isinstance(shard_count, bool)
        or shard_count < 1
        or not isinstance(shard_id, int)
        or isinstance(shard_id, bool)
        or not 0 <= shard_id < shard_count
    ):
        raise ValueError("require 0 <= shard_id < shard_count")

    scale, atoms, card_id = _integer_seed61_atoms()
    sparse_atoms = tuple(_sparse_columns(atom) for atom in atoms)
    per_length: list[dict[str, object]] = []
    minimum: dict[str, object] | None = None
    stopped = False

    for length in range(min_depth, max_depth + 1):
        assigned: list[tuple[Word, int]] = []
        global_class_count = 0
        global_word_count = 0
        for class_index, word in enumerate(canonical_words(length)):
            orbit_size = len(symmetry_orbit(word))
            global_class_count += 1
            global_word_count += orbit_size
            if class_index % shard_count == shard_id:
                assigned.append((word, orbit_size))
        if global_word_count != 2**length:
            raise ArithmeticError("safe symmetry classes do not cover binary words")

        previous_word: Word = ()
        products: list[Matrix] = [_identity()]
        checked_class_count = 0
        checked_word_count = 0
        length_minimum: dict[str, object] | None = None
        witness: dict[str, object] | None = None
        denominator = scale ** (DIMENSION * length)

        for word, orbit_size in assigned:
            shared = _longest_common_prefix(previous_word, word)
            products = products[: shared + 1]
            for symbol in word[shared:]:
                products.append(
                    _right_multiply_sparse(products[-1], sparse_atoms[symbol])
                )
            previous_word = word
            numerator = _scaled_weight_numerator(products[-1], length, scale)
            record = _weight_record(numerator, denominator, word)
            checked_class_count += 1
            checked_word_count += orbit_size
            if length_minimum is None or _ratio_less(record, length_minimum):
                length_minimum = record
            if minimum is None or _ratio_less(record, minimum):
                minimum = record
            if numerator <= 0 and witness is None:
                witness = record
                if stop_on_nonpositive:
                    stopped = True
                    break

        per_length.append(
            {
                "length": length,
                "global_class_count": global_class_count,
                "global_word_count": global_word_count,
                "assigned_class_count": len(assigned),
                "assigned_word_count": sum(size for _, size in assigned),
                "checked_class_count": checked_class_count,
                "checked_word_count": checked_word_count,
                "minimum_weight": length_minimum,
                "nonpositive_witness": witness,
                "complete": checked_class_count == len(assigned),
            }
        )
        if stopped:
            break

    nonpositive = next(
        (
            entry["nonpositive_witness"]
            for entry in per_length
            if entry["nonpositive_witness"] is not None
        ),
        None,
    )
    complete = (
        len(per_length) == max_depth - min_depth + 1
        and all(bool(entry["complete"]) for entry in per_length)
    )
    return {
        "schema": SCHEMA_VERSION,
        "candidate": f"{TEMPLATE}-seed-{SEED}",
        "candidate_id": card_id,
        "dimension": DIMENSION,
        "integer_atom_scale": scale,
        "min_depth": min_depth,
        "max_depth": max_depth,
        "shard_id": shard_id,
        "shard_count": shard_count,
        "symmetry": "cyclic-rotation+transpose-reversal",
        "bit_complement_quotiented": False,
        "per_length": per_length,
        "minimum_weight": minimum,
        "nonpositive_witness": nonpositive,
        "complete": complete,
        "status": (
            "nonpositive-witness"
            if nonpositive is not None
            else "strictly-positive"
            if complete
            else "incomplete"
        ),
    }


def collect_shards(manifests: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Validate and merge all shard manifests into one exact result."""

    checked = tuple(dict(manifest) for manifest in manifests)
    if not checked:
        raise ValueError("at least one shard manifest is required")
    first = checked[0]
    shard_count = int(first["shard_count"])
    shard_ids = {int(manifest["shard_id"]) for manifest in checked}
    if shard_ids != set(range(shard_count)) or len(checked) != shard_count:
        raise ValueError("shard manifests are not one complete unique shard set")
    consensus_keys = (
        "schema",
        "candidate",
        "candidate_id",
        "dimension",
        "integer_atom_scale",
        "min_depth",
        "max_depth",
        "shard_count",
        "symmetry",
        "bit_complement_quotiented",
    )
    for manifest in checked[1:]:
        if any(manifest[key] != first[key] for key in consensus_keys):
            raise ValueError("shard manifest consensus failed")

    minimum: dict[str, object] | None = None
    witness: dict[str, object] | None = None
    per_length: list[dict[str, object]] = []
    complete = all(bool(manifest["complete"]) for manifest in checked)
    for offset, length in enumerate(
        range(int(first["min_depth"]), int(first["max_depth"]) + 1)
    ):
        entries = []
        for manifest in checked:
            values = manifest["per_length"]
            if not isinstance(values, list) or offset >= len(values):
                complete = False
                continue
            entry = values[offset]
            if not isinstance(entry, Mapping) or int(entry["length"]) != length:
                raise ValueError("per-length shard ordering is inconsistent")
            entries.append(entry)
        if not entries:
            continue
        global_classes = {int(entry["global_class_count"]) for entry in entries}
        global_words = {int(entry["global_word_count"]) for entry in entries}
        if len(global_classes) != 1 or global_words != {2**length}:
            raise ValueError("global symmetry counts disagree across shards")
        assigned_classes = sum(int(entry["assigned_class_count"]) for entry in entries)
        assigned_words = sum(int(entry["assigned_word_count"]) for entry in entries)
        checked_classes = sum(int(entry["checked_class_count"]) for entry in entries)
        checked_words = sum(int(entry["checked_word_count"]) for entry in entries)
        expected_classes = next(iter(global_classes))
        depth_complete = (
            len(entries) == shard_count
            and all(bool(entry["complete"]) for entry in entries)
            and assigned_classes == checked_classes == expected_classes
            and assigned_words == checked_words == 2**length
        )
        complete &= depth_complete
        depth_minimum: dict[str, object] | None = None
        for entry in entries:
            value = entry["minimum_weight"]
            if isinstance(value, Mapping):
                record = dict(value)
                if depth_minimum is None or _ratio_less(record, depth_minimum):
                    depth_minimum = record
                if minimum is None or _ratio_less(record, minimum):
                    minimum = record
            value = entry["nonpositive_witness"]
            if isinstance(value, Mapping) and witness is None:
                witness = dict(value)
        per_length.append(
            {
                "length": length,
                "canonical_class_count": expected_classes,
                "covered_word_count": checked_words,
                "minimum_weight": depth_minimum,
                "complete": depth_complete,
            }
        )

    return {
        "schema": SCHEMA_VERSION,
        "candidate": first["candidate"],
        "candidate_id": first["candidate_id"],
        "dimension": first["dimension"],
        "integer_atom_scale": first["integer_atom_scale"],
        "min_depth": first["min_depth"],
        "max_depth": first["max_depth"],
        "shard_count": shard_count,
        "symmetry": first["symmetry"],
        "bit_complement_quotiented": first["bit_complement_quotiented"],
        "per_length": per_length,
        "canonical_class_count": sum(
            int(entry["canonical_class_count"]) for entry in per_length
        ),
        "covered_word_count": sum(
            int(entry["covered_word_count"]) for entry in per_length
        ),
        "minimum_weight": minimum,
        "nonpositive_witness": witness,
        "complete": complete,
        "status": (
            "nonpositive-witness"
            if witness is not None
            else "strictly-positive"
            if complete
            else "incomplete"
        ),
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--max-depth", type=int, default=23)
    scan.add_argument("--min-depth", type=int, default=1)
    scan.add_argument("--shard-id", type=int, required=True)
    scan.add_argument("--shard-count", type=int, required=True)
    scan.add_argument("--run-dir", type=Path, required=True)
    scan.add_argument("--stop-on-nonpositive", action="store_true")
    collect = subparsers.add_parser("collect")
    collect.add_argument("--shard-count", type=int, required=True)
    collect.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "scan":
        payload = scan_shard(
            max_depth=args.max_depth,
            min_depth=args.min_depth,
            shard_id=args.shard_id,
            shard_count=args.shard_count,
            stop_on_nonpositive=args.stop_on_nonpositive,
        )
        output = args.run_dir / (
            f"shard-{args.shard_id:04d}-of-{args.shard_count:04d}.json"
        )
    else:
        manifests = []
        for shard_id in range(args.shard_count):
            path = args.run_dir / (
                f"shard-{shard_id:04d}-of-{args.shard_count:04d}.json"
            )
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        payload = collect_shards(manifests)
        output = args.run_dir / "collect.json"
    _atomic_json(output, payload)
    print(json.dumps(payload, allow_nan=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "canonical_word",
    "canonical_words",
    "collect_shards",
    "scan_shard",
    "symmetry_orbit",
]
