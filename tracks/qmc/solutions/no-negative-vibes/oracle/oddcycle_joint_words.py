"""Numerical survivor tests for finite multi-point oddcycle alphabets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence

import numpy as np

from .symmetric_oddcycle_discovery import oddcycle_matrix


SCHEMA = "oddcycle-joint-word-discovery-v1"


def joint_alphabet(points: Sequence[Sequence[float]]) -> tuple[np.ndarray, ...]:
    """Return ``B`` and ``B.T`` for every declared parameter point."""

    normalized = tuple(tuple(float(value) for value in point) for point in points)
    if not normalized or any(len(point) != 3 for point in normalized):
        raise ValueError("points must be a nonempty sequence of triples")
    return tuple(
        atom
        for point in normalized
        for matrix in (oddcycle_matrix(*point),)
        for atom in (matrix, matrix.T)
    )


def _decode_word(code: int, depth: int, alphabet_size: int) -> str:
    symbols = []
    for _ in range(depth):
        symbols.append(str(code % alphabet_size))
        code //= alphabet_size
    return "".join(reversed(symbols))


def exhaustive_joint_short_words(
    points: Sequence[Sequence[float]],
    *,
    max_depth: int = 8,
    max_level_matrices: int = 2_000_000,
    determinant_tolerance: float = 1.0e-10,
) -> dict[str, object]:
    """Exhaust every joint word up to a bounded discovery depth."""

    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    atoms = np.asarray(joint_alphabet(points))
    alphabet_size = len(atoms)
    level = np.eye(5, dtype=float)[None, :, :]
    codes = np.zeros(1, dtype=np.int64)
    identity = np.eye(5, dtype=float)
    word_count = 0
    global_minimum = np.inf
    global_witness = ""
    global_depth = 0
    per_depth = []
    exact_replay: dict[str, object] | None = None
    for depth in range(1, max_depth + 1):
        next_count = alphabet_size * len(level)
        if next_count > max_level_matrices:
            return {
                "schema": SCHEMA,
                "status": "resource-limit",
                "alphabet_size": alphabet_size,
                "max_depth_requested": max_depth,
                "max_depth_reached": depth - 1,
                "word_count": word_count,
                "next_level_matrices": next_count,
                "max_level_matrices": max_level_matrices,
                "minimum_determinant": float(global_minimum),
                "witness": global_witness,
                "witness_depth": global_depth,
                "per_depth": per_depth,
            }
        level = np.matmul(atoms[:, None, :, :], level[None, :, :, :]).reshape(
            next_count, 5, 5
        )
        codes = np.concatenate(
            [codes * alphabet_size + symbol for symbol in range(alphabet_size)]
        )
        determinants = np.linalg.det(level + identity)
        local_index = int(np.argmin(determinants))
        local_minimum = float(determinants[local_index])
        local_witness = _decode_word(
            int(codes[local_index]), depth, alphabet_size
        )
        word_count += next_count
        if local_minimum < global_minimum:
            global_minimum = local_minimum
            global_witness = local_witness
            global_depth = depth
        per_depth.append(
            {
                "depth": depth,
                "word_count": next_count,
                "minimum_determinant": local_minimum,
                "witness": local_witness,
            }
        )
        if not np.all(np.isfinite(determinants)):
            status = "nonfinite"
            break
        if local_minimum <= determinant_tolerance:
            exact_replay = exact_rational_word_replay(points, local_witness)
            status = (
                "exact-nonpositive-word-found"
                if exact_replay["strictly_positive"] is False
                else "floating-point-resolution-limit"
            )
            break
    else:
        status = "all-tested-words-positive"
    return {
        "schema": SCHEMA,
        "status": status,
        "alphabet_size": alphabet_size,
        "max_depth_requested": max_depth,
        "max_depth_reached": depth,
        "word_count": word_count,
        "minimum_determinant": global_minimum,
        "witness": global_witness,
        "witness_depth": global_depth,
        "exact_replay": exact_replay,
        "per_depth": per_depth,
    }


def random_joint_long_words(
    points: Sequence[Sequence[float]],
    *,
    samples: int = 100_000,
    max_depth: int = 40,
    rng_seed: int = 923_771,
    determinant_tolerance: float = 1.0e-10,
) -> dict[str, object]:
    """Stress a joint alphabet with vectorized independent random words."""

    if samples < 1 or max_depth < 1:
        raise ValueError("samples and max_depth must be positive")
    atoms = np.asarray(joint_alphabet(points))
    alphabet_size = len(atoms)
    rng = np.random.default_rng(rng_seed)
    products = np.broadcast_to(np.eye(5), (samples, 5, 5)).copy()
    history = np.empty((samples, max_depth), dtype=np.uint8)
    identity = np.eye(5, dtype=float)
    minimum = np.inf
    witness = ""
    witness_depth = 0
    witness_sample = 0
    per_depth = []
    exact_replay: dict[str, object] | None = None
    status = "all-tested-words-positive"
    for depth in range(1, max_depth + 1):
        symbols = rng.integers(0, alphabet_size, size=samples, dtype=np.uint8)
        history[:, depth - 1] = symbols
        products = np.matmul(atoms[symbols], products)
        determinants = np.linalg.det(products + identity)
        local_index = int(np.argmin(determinants))
        local_minimum = float(determinants[local_index])
        if local_minimum < minimum:
            minimum = local_minimum
            witness = "".join(
                str(int(symbol))
                for symbol in history[local_index, :depth]
            )
            witness_depth = depth
            witness_sample = local_index
        per_depth.append(
            {
                "depth": depth,
                "minimum_determinant": local_minimum,
                "finite_count": int(np.count_nonzero(np.isfinite(determinants))),
            }
        )
        if not np.all(np.isfinite(determinants)):
            status = "nonfinite"
            break
        if local_minimum <= determinant_tolerance:
            exact_replay = exact_rational_word_replay(points, witness)
            status = (
                "exact-nonpositive-word-found"
                if exact_replay["strictly_positive"] is False
                else "floating-point-resolution-limit"
            )
            break
    return {
        "schema": SCHEMA,
        "status": status,
        "alphabet_size": alphabet_size,
        "samples": samples,
        "max_depth_requested": max_depth,
        "max_depth_reached": depth,
        "rng_seed": rng_seed,
        "minimum_determinant": minimum,
        "witness": witness,
        "witness_depth": witness_depth,
        "witness_sample": witness_sample,
        "exact_replay": exact_replay,
        "per_depth": per_depth,
    }


def exact_rational_word_replay(
    points: Sequence[Sequence[object]],
    word: str,
) -> dict[str, object]:
    """Replay one finite-alphabet word with exact rational arithmetic."""

    import sympy as sp

    if not word:
        raise ValueError("word must be nonempty")
    normalized = tuple(
        tuple(sp.Rational(str(value)) for value in point) for point in points
    )
    if not normalized or any(len(point) != 3 for point in normalized):
        raise ValueError("points must be a nonempty sequence of triples")

    def matrix(point: tuple[sp.Rational, ...]) -> sp.ImmutableMatrix:
        p, q, r = point
        return sp.ImmutableMatrix(
            [
                [0, 0, 2, 0, 0],
                [2, 0, 0, 0, 0],
                [0, 2, 0, p, 0],
                [0, 0, 0, 1, q],
                [0, 0, -r, 0, 1],
            ]
        )

    alphabet = tuple(
        atom
        for point in normalized
        for base in (matrix(point),)
        for atom in (base, base.T)
    )
    if any(not symbol.isdigit() or int(symbol) >= len(alphabet) for symbol in word):
        raise ValueError("word contains a symbol outside the alphabet")
    product = sp.eye(5)
    for symbol in word:
        product = alphabet[int(symbol)] * product
    determinant = sp.factor((sp.eye(5) + product).det())
    rational = sp.Rational(determinant)
    return {
        "schema": SCHEMA,
        "status": "exact-rational-word-replay",
        "points": [[str(value) for value in point] for point in normalized],
        "alphabet_size": len(alphabet),
        "word": word,
        "word_length": len(word),
        "word_sha256": hashlib.sha256(word.encode("ascii")).hexdigest(),
        "determinant": {
            "numerator": int(rational.p),
            "denominator": int(rational.q),
        },
        "strictly_positive": bool(rational > 0),
    }


__all__ = [
    "SCHEMA",
    "exact_rational_word_replay",
    "exhaustive_joint_short_words",
    "joint_alphabet",
    "random_joint_long_words",
]


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        required=True,
        metavar=("P", "Q", "R"),
    )
    parser.add_argument("--exhaustive-depth", type=int, default=8)
    parser.add_argument("--max-level-matrices", type=int, default=2_000_000)
    parser.add_argument("--random-samples", type=int, default=100_000)
    parser.add_argument("--random-depth", type=int, default=40)
    parser.add_argument("--rng-seed", type=int, default=923_771)
    parser.add_argument("--summary", action="store_true")
    arguments = parser.parse_args()
    exhaustive = exhaustive_joint_short_words(
        arguments.point,
        max_depth=arguments.exhaustive_depth,
        max_level_matrices=arguments.max_level_matrices,
    )
    random = random_joint_long_words(
        arguments.point,
        samples=arguments.random_samples,
        max_depth=arguments.random_depth,
        rng_seed=arguments.rng_seed,
    )
    payload: dict[str, object] = {
        "points": arguments.point,
        "exhaustive": exhaustive,
        "random": random,
    }
    if arguments.summary:
        payload = {
            "points": arguments.point,
            "exhaustive": {
                key: exhaustive[key]
                for key in (
                    "status",
                    "max_depth_reached",
                    "word_count",
                    "minimum_determinant",
                    "witness",
                    "witness_depth",
                )
            },
            "random": {
                key: random[key]
                for key in (
                    "status",
                    "samples",
                    "max_depth_reached",
                    "minimum_determinant",
                    "witness",
                    "witness_depth",
                    "witness_sample",
                    "rng_seed",
                    "exact_replay",
                )
            },
        }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":  # pragma: no cover - exercised as a CLI
    _main()
