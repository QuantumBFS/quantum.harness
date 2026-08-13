"""Discover adversarial long words, with an exact determinant hit gate.

The numerical objective only ranks words.  A candidate is marked ``hit``
iff ``exact_determinant_weight`` independently returns a negative rational.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections.abc import Mapping, Sequence

import mpmath as mp
import numpy as np

from .exterior_candidates import (
    candidate_card,
    exact_atoms_from_card,
    float_atoms_from_card,
)
from .exterior_seed61_positive_realization import exact_determinant_weight


SCHEMA_VERSION = "exterior-longword-adversarial-v1"

# Exact length-600 replays routinely exceed Python 3.11's default 4300-digit
# conversion guard.  This standalone research CLI intentionally serializes
# those trusted, locally computed integers as decimal JSON strings.
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


def _target_card(target: str) -> dict[str, object]:
    if not isinstance(target, str) or ":" not in target:
        raise ValueError("target must have the form TEMPLATE:SEED")
    template, seed_text = target.rsplit(":", 1)
    try:
        seed = int(seed_text)
    except ValueError as error:
        raise ValueError("target seed must be an integer") from error
    return candidate_card(template=template, seed=seed)


def _checked_word(word: Sequence[int]) -> tuple[int, ...]:
    checked = tuple(word)
    if not checked or any(
        not isinstance(symbol, int)
        or isinstance(symbol, bool)
        or symbol not in (0, 1)
        for symbol in checked
    ):
        raise ValueError("word must be a nonempty binary sequence")
    return checked


def _compound(matrix: np.ndarray, grade: int) -> np.ndarray:
    basis = tuple(itertools.combinations(range(matrix.shape[0]), grade))
    return np.asarray(
        [
            [
                np.linalg.det(matrix[np.ix_(rows, columns)])
                for columns in basis
            ]
            for rows in basis
        ],
        dtype=float,
    )


def _positive_grade13_gauge(
    atoms: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, ...] | None:
    dimension = atoms[0].shape[0]
    if dimension != 5 or len(atoms) != 2:
        return None
    for tail in itertools.product((-1.0, 1.0), repeat=dimension - 1):
        signs = np.asarray((1.0, *tail))
        gauged = tuple(
            signs[:, None] * atom * signs[None, :]
            for atom in atoms
        )
        if min(float(np.min(atom)) for atom in gauged) < -1e-12:
            continue
        grade3 = tuple(_compound(atom, 3) for atom in gauged)
        if min(float(np.min(atom)) for atom in grade3) >= -1e-10:
            return gauged
    return None


def _compound_discovery(
    compound_atoms: tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]],
    word: tuple[int, ...],
) -> dict[str, object]:
    grade2_atoms, grade3_atoms = compound_atoms
    dimension = grade2_atoms[0].shape[0]
    grade2_word = np.eye(dimension)
    grade3_word = np.eye(dimension)
    grade2_log_scale = 0.0
    grade3_log_scale = 0.0
    for symbol in word:
        grade2_word = grade2_word @ grade2_atoms[symbol]
        grade3_word = grade3_word @ grade3_atoms[symbol]
        grade2_scale = max(1.0, float(np.linalg.norm(grade2_word, ord=np.inf)))
        grade3_scale = max(1.0, float(np.linalg.norm(grade3_word, ord=np.inf)))
        grade2_word /= grade2_scale
        grade3_word /= grade3_scale
        grade2_log_scale += float(np.log(grade2_scale))
        grade3_log_scale += float(np.log(grade3_scale))
    grade2_roots = np.linalg.eigvals(grade2_word)
    dominant = grade2_roots[int(np.argmax(np.abs(grade2_roots)))]
    grade3_radius = float(np.max(np.abs(np.linalg.eigvals(grade3_word))))
    real_negative = bool(
        dominant.real < 0
        and abs(dominant.imag) <= 1e-8 * max(1.0, abs(dominant.real))
    )
    if real_negative:
        log_ratio = (
            grade3_log_scale
            + float(np.log(grade3_radius))
            - grade2_log_scale
            - float(np.log(abs(dominant.real)))
        )
        ratio = float(np.exp(np.clip(log_ratio, -700.0, 700.0)))
        score = log_ratio
    else:
        log_ratio = None
        ratio = None
        phase_penalty = abs(float(dominant.imag)) / max(1.0, abs(dominant))
        score = 1_000_000.0 + phase_penalty + float(dominant.real >= 0)
    return {
        "method": "compound-ratio",
        "score": float(score),
        "dominant_grade2": [float(dominant.real), float(dominant.imag)],
        "grade3_radius": grade3_radius,
        "lambda3_log_modulus_proxy": log_ratio,
        "lambda3_modulus_proxy": ratio,
        "suggests_negative": bool(
            real_negative and log_ratio is not None and log_ratio < 0
        ),
    }


def _rescaled_determinant_discovery(
    atoms: tuple[np.ndarray, ...],
    word: tuple[int, ...],
) -> dict[str, object]:
    dimension = atoms[0].shape[0]
    matrix = np.eye(dimension)
    log_scale = 0.0
    for symbol in word:
        matrix = matrix @ atoms[symbol]
        scale = max(1.0, float(np.linalg.norm(matrix, ord=np.inf)))
        matrix /= scale
        log_scale += float(np.log(scale))
    identity_scale = 0.0 if log_scale > 700 else float(np.exp(-log_scale))
    sign, logabs = np.linalg.slogdet(
        matrix + identity_scale * np.eye(dimension)
    )
    finite_logabs = float(logabs) if np.isfinite(logabs) else 100_000.0
    score = (
        -1_000_000.0 - min(finite_logabs, 100_000.0)
        if sign < 0
        else finite_logabs
    )
    return {
        "method": "rescaled-determinant",
        "score": float(score),
        "rescaled_sign": int(np.sign(sign)),
        "rescaled_logabs": finite_logabs,
        "log_scale": log_scale,
        "suggests_negative": bool(sign < 0),
    }


def _mpmath_rescaled_determinant_discovery(
    atoms: tuple[mp.matrix, ...],
    word: tuple[int, ...],
    *,
    dps: int,
    float_prefilter: Mapping[str, object],
) -> dict[str, object]:
    """Re-rank one float finalist with a high-precision determinant."""

    dimension = atoms[0].rows
    matrix = mp.eye(dimension)
    log_scale = mp.mpf("0")
    for symbol in word:
        matrix *= atoms[symbol]
        scale = max(
            mp.fsum(abs(matrix[row, column]) for column in range(dimension))
            for row in range(dimension)
        )
        scale = max(mp.mpf("1"), scale)
        matrix /= scale
        log_scale += mp.log(scale)
    identity_scale = mp.exp(-log_scale)
    shifted = matrix + identity_scale * mp.eye(dimension)
    value = mp.det(shifted)
    sign = int(mp.sign(value))
    if value:
        logabs = mp.log(abs(value))
        finite_logabs = float(
            max(mp.mpf("-100000"), min(mp.mpf("100000"), logabs))
        )
    else:
        logabs = mp.ninf
        finite_logabs = -100_000.0
    score = (
        -1_000_000.0 - finite_logabs
        if sign < 0
        else -999_999.0
        if sign == 0
        else finite_logabs
    )
    return {
        "method": "mpmath-rescaled-determinant",
        "score": float(score),
        "objective_dps": dps,
        "high_precision_sign": sign,
        "rescaled_value": mp.nstr(value, min(dps, 80)),
        "rescaled_logabs": mp.nstr(logabs, min(dps, 80)),
        "log_scale": mp.nstr(log_scale, min(dps, 80)),
        "suggests_negative": sign < 0,
        "float_prefilter": dict(float_prefilter),
    }


def _rerank_with_mpmath(
    exact_atoms: Sequence[object],
    finalists: Sequence[
        tuple[float, tuple[int, ...], Mapping[str, object]]
    ],
    *,
    dps: int,
) -> tuple[float, tuple[int, ...], dict[str, object]]:
    unique: dict[tuple[int, ...], Mapping[str, object]] = {}
    for _, word, discovery in finalists:
        unique.setdefault(word, discovery)
    with mp.workdps(dps):
        atoms = tuple(
            mp.matrix(
                [
                    [
                        mp.mpf(str(value.p)) / mp.mpf(str(value.q))
                        for value in atom.row(row)
                    ]
                    for row in range(atom.rows)
                ]
            )
            for atom in exact_atoms
        )
        ranked = []
        for word, float_prefilter in unique.items():
            discovery = _mpmath_rescaled_determinant_discovery(
                atoms,
                word,
                dps=dps,
                float_prefilter=float_prefilter,
            )
            ranked.append((float(discovery["score"]), word, discovery))
    if not ranked:
        raise ArithmeticError("high-precision reranking received no finalists")
    return min(ranked, key=lambda item: item[0])


def exact_replay_candidate(
    *,
    target: str,
    word: Sequence[int],
    discovery: Mapping[str, object],
) -> dict[str, object]:
    """Replay one discovery candidate and apply the exact-only hit gate."""

    checked_word = _checked_word(word)
    atoms = exact_atoms_from_card(_target_card(target))
    exact_weight = exact_determinant_weight(atoms, checked_word)
    numerator = int(exact_weight.p)
    denominator = int(exact_weight.q)
    bit_text = "".join(str(symbol) for symbol in checked_word)
    sign = (numerator > 0) - (numerator < 0)
    return {
        "word": {
            "bits": bit_text,
            "length": len(checked_word),
            "sha256": hashlib.sha256(bit_text.encode("ascii")).hexdigest(),
        },
        "discovery": dict(discovery),
        "exact_weight": {
            "numerator": str(numerator),
            "denominator": str(denominator),
            "sign": sign,
        },
        "hit": sign < 0,
    }


def search_adversarial_words(
    *,
    target: str,
    lengths: Sequence[int],
    restarts: int,
    rng_seed: int,
    rounds: int = 12,
    proposals_per_round: int = 8,
    objective_dps: int = 80,
) -> dict[str, object]:
    """Run deterministic discrete local search and exactly replay each winner."""

    card = _target_card(target)
    checked_lengths = tuple(lengths)
    if not checked_lengths or any(
        not isinstance(length, int)
        or isinstance(length, bool)
        or length < 1
        for length in checked_lengths
    ):
        raise ValueError("lengths must be nonempty positive integers")
    for name, value in (
        ("restarts", restarts),
        ("rounds", rounds),
        ("proposals_per_round", proposals_per_round),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(rng_seed, int) or isinstance(rng_seed, bool):
        raise ValueError("rng_seed must be an integer")
    if (
        not isinstance(objective_dps, int)
        or isinstance(objective_dps, bool)
        or objective_dps < 30
    ):
        raise ValueError("objective_dps must be an integer of at least 30")

    float_atoms = float_atoms_from_card(card)
    exact_atoms = exact_atoms_from_card(card)
    gauged = _positive_grade13_gauge(float_atoms)
    if gauged is not None:
        objective_atoms: object = (
            tuple(_compound(atom, 2) for atom in gauged),
            tuple(_compound(atom, 3) for atom in gauged),
        )
        objective = _compound_discovery
    else:
        objective_atoms = float_atoms
        objective = _rescaled_determinant_discovery
    rng = np.random.default_rng(rng_seed)
    candidates: list[dict[str, object]] = []

    def evaluate(word: tuple[int, ...]) -> tuple[float, dict[str, object]]:
        discovery = objective(objective_atoms, word)
        return float(discovery["score"]), discovery

    for length in checked_lengths:
        best: tuple[float, tuple[int, ...], dict[str, object]] | None = None
        finalists: list[
            tuple[float, tuple[int, ...], dict[str, object]]
        ] = []
        for _ in range(restarts):
            current_word = tuple(
                int(symbol)
                for symbol in rng.integers(0, 2, size=length, dtype=np.int8)
            )
            current_score, current_discovery = evaluate(current_word)
            for _ in range(rounds):
                proposals = []
                for _ in range(proposals_per_round):
                    changed = list(current_word)
                    flip_count = int(rng.integers(1, min(5, length) + 1))
                    for index in rng.choice(length, size=flip_count, replace=False):
                        changed[int(index)] ^= 1
                    proposal_word = tuple(changed)
                    proposal_score, proposal_discovery = evaluate(proposal_word)
                    proposals.append(
                        (proposal_score, proposal_word, proposal_discovery)
                    )
                proposal = min(proposals, key=lambda item: item[0])
                if proposal[0] < current_score:
                    current_score, current_word, current_discovery = proposal
            current = (current_score, current_word, current_discovery)
            finalists.append(current)
            if best is None or current[0] < best[0]:
                best = current

        if best is None:
            raise ArithmeticError("adversarial search produced no candidate")
        if gauged is None:
            best = _rerank_with_mpmath(
                exact_atoms,
                finalists,
                dps=objective_dps,
            )
        record = exact_replay_candidate(
            target=target,
            word=best[1],
            discovery=best[2],
        )
        candidates.append(record)
        if record["hit"]:
            break

    hit = next((record for record in candidates if record["hit"]), None)
    return {
        "schema": SCHEMA_VERSION,
        "target": target,
        "lengths": list(checked_lengths),
        "restarts": restarts,
        "rng_seed": rng_seed,
        "rounds": rounds,
        "proposals_per_round": proposals_per_round,
        "objective_dps": objective_dps,
        "discovery_method": (
            "compound-ratio"
            if gauged is not None
            else "mpmath-rescaled-determinant"
        ),
        "candidates": candidates,
        "hit": hit,
        "status": (
            "exact-negative-found"
            if hit is not None
            else "no-exact-negative-found"
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--lengths", nargs="+", type=int, required=True)
    parser.add_argument("--restarts", type=int, default=128)
    parser.add_argument("--rng-seed", type=int, default=0)
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--proposals-per-round", type=int, default=8)
    parser.add_argument("--objective-dps", type=int, default=80)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = search_adversarial_words(
        target=args.target,
        lengths=args.lengths,
        restarts=args.restarts,
        rng_seed=args.rng_seed,
        rounds=args.rounds,
        proposals_per_round=args.proposals_per_round,
        objective_dps=args.objective_dps,
    )
    print(json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "exact_replay_candidate",
    "search_adversarial_words",
]
