"""Exact rational candidate cards for the exterior-cone discovery loop.

The serialized card is the mathematical candidate.  Numerical arrays are
derived from it and never participate in candidate identity.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping
from fractions import Fraction
from functools import lru_cache
from typing import Any

import numpy as np
import sympy as sp


_SCHEMA = "exterior-candidate-card-v1"
_TEMPLATE_SPECS = {
    "exact3-oddcycle-shear-pair": (3, "odd-cycle-routing"),
    "exact3-diagonal-oddcycle-pair": (3, "odd-cycle-routing"),
    "exact4-shear-loop-pair": (4, "loop"),
    "exact4-graded-shear-pair": (4, "cross-block-edge"),
    "exact4-block-shear-pair": (4, "cross-block-edge"),
    "exact4-diagonal-loop-pair": (4, "loop"),
    "exact5-shear-loop-pair": (5, "loop"),
    "exact5-oddcycle-block-pair": (5, "odd-cycle-routing"),
    "exact6-graded-shear-pair": (6, "degree-three"),
}
TEMPLATES = tuple(_TEMPLATE_SPECS)

_MAGNITUDE_TIERS = ("unit", "quarter", "triple")
_TIER_MULTIPLIERS = {
    "quarter": Fraction(1, 4),
    "unit": Fraction(1, 1),
    "triple": Fraction(3, 1),
}
_FORBIDDEN_RUNTIME_KEYS = {
    "hostname",
    "username",
    "absolute_path",
    "package_version",
    "runtime",
}
_RATIONAL_KEYS = {"numerator", "denominator"}
_DECIMAL_STRING = re.compile(r"[+-]?(?:\d+\.\d*|\d*\.\d+)")


def _magnitude_tier(seed: int) -> str:
    return _MAGNITUDE_TIERS[seed % len(_MAGNITUDE_TIERS)]


def _promotion_status(template: str) -> str:
    if template == "exact3-diagonal-oddcycle-pair":
        return "known-odd-monomial-p0-control"
    return "discovery-eligible"


def _encode_rational(value: Fraction | int) -> dict[str, int]:
    fraction = value if isinstance(value, Fraction) else Fraction(value)
    return {
        "numerator": fraction.numerator,
        "denominator": fraction.denominator,
    }


def _parse_rational(value: object, *, path: str) -> Fraction:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be a canonical rational mapping")
    if set(value) != _RATIONAL_KEYS:
        raise ValueError(f"{path} must contain only numerator and denominator")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if (
        not isinstance(numerator, int)
        or isinstance(numerator, bool)
        or not isinstance(denominator, int)
        or isinstance(denominator, bool)
    ):
        raise TypeError(f"{path} numerator and denominator must be integers")
    if denominator <= 0:
        raise ValueError(f"{path} denominator must be strictly positive")
    if math.gcd(numerator, denominator) != 1:
        raise ValueError(f"{path} rational must be reduced")
    if numerator == 0 and denominator != 1:
        raise ValueError(f"{path} zero must be encoded as 0/1")
    return Fraction(numerator, denominator)


def _validate_json_tree(value: object, *, path: str = "card") -> None:
    if isinstance(value, Mapping):
        keys = set(value)
        if keys & _RATIONAL_KEYS:
            _parse_rational(value, path=path)
            return
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            if key in _FORBIDDEN_RUNTIME_KEYS:
                raise ValueError(f"{path}.{key} is runtime-dependent")
            _validate_json_tree(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_tree(child, path=f"{path}[{index}]")
        return
    if isinstance(value, float):
        raise TypeError(f"{path} contains a float")
    if isinstance(value, bool):
        raise TypeError(f"{path} contains a boolean instead of exact data")
    if isinstance(value, int) or value is None:
        return
    if isinstance(value, str):
        if value.casefold() in {"nan", "infinity", "+infinity", "-infinity"}:
            raise ValueError(f"{path} contains a nonfinite string")
        if _DECIMAL_STRING.fullmatch(value):
            raise ValueError(f"{path} contains a decimal string")
        return
    raise TypeError(f"{path} contains non-JSON value {type(value).__name__}")


def _canonical_json(card: Mapping[str, object]) -> str:
    _validate_json_tree(card)
    return json.dumps(
        card,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def candidate_id(card: Mapping[str, object]) -> str:
    """Return the SHA-256 identity of the complete canonical exact card."""

    if not isinstance(card, Mapping):
        raise TypeError("card must be a mapping")
    return hashlib.sha256(_canonical_json(card).encode("utf-8")).hexdigest()


def _shear(
    dimension: int,
    i: int,
    j: int,
    q: Fraction,
) -> dict[str, object]:
    return {
        "kind": "rational-shear",
        "dimension": dimension,
        "i": i,
        "j": j,
        "q": _encode_rational(q),
        "support": sorted((i, j)),
        "witness": "nilpotent-rational-exponential",
    }


def _diagonal(
    dimension: int,
    diagonal: tuple[Fraction, ...],
) -> dict[str, object]:
    return {
        "kind": "positive-rational-diagonal",
        "dimension": dimension,
        "diagonal": [_encode_rational(value) for value in diagonal],
        "support": list(range(dimension)),
        "witness": "real-diagonal-log",
    }


def _odd_cycle(
    dimension: int,
    cycle: tuple[int, ...],
    diagonal: tuple[Fraction, ...],
    *,
    orientation: str = "forward",
) -> dict[str, object]:
    return {
        "kind": "positive-odd-cycle",
        "dimension": dimension,
        "cycle": list(cycle),
        "diagonal": [_encode_rational(value) for value in diagonal],
        "orientation": orientation,
        "support": sorted(cycle),
        "witness": "odd-cycle-real-log",
    }


def _strength(seed: int, offset: int, attempt: int) -> Fraction:
    tier = _magnitude_tier(seed)
    numerator = 1 + ((17 * seed + 11 * offset + 7 * attempt) % 9)
    denominator = 1 + ((5 * seed + 3 * offset + attempt) % 5)
    sign = -1 if (seed + offset + attempt) % 2 else 1
    return _TIER_MULTIPLIERS[tier] * Fraction(sign * numerator, denominator)


def _positive_diagonal_values(
    seed: int,
    dimension: int,
    attempt: int,
) -> tuple[Fraction, ...]:
    primes = (2, 3, 5, 7, 11, 13)
    multiplier = _TIER_MULTIPLIERS[_magnitude_tier(seed)]
    return tuple(
        multiplier
        * (
            Fraction(primes[index], 1)
            + Fraction((seed * (index + 1) + attempt) % 5, index + 2)
        )
        for index in range(dimension)
    )


def _template_factors(
    template: str,
    seed: int,
    attempt: int,
) -> tuple[dict[str, object], ...]:
    dimension, _ = _TEMPLATE_SPECS[template]
    q = tuple(_strength(seed, index, attempt) for index in range(8))

    if template == "exact3-oddcycle-shear-pair":
        diagonal = _positive_diagonal_values(seed, 3, attempt)
        return (
            _shear(3, 0, 1, q[0]),
            _odd_cycle(3, (0, 1, 2), diagonal),
        )

    if template == "exact3-diagonal-oddcycle-pair":
        if seed == 0 and attempt == 0:
            first_diagonal = (Fraction(1),) * 3
            odd_diagonal = (Fraction(2), Fraction(3), Fraction(5))
        else:
            first_diagonal = tuple(
                Fraction(1) + abs(_strength(seed, index + 3, attempt))
                for index in range(3)
            )
            odd_diagonal = _positive_diagonal_values(seed, 3, attempt)
        return (
            _diagonal(3, first_diagonal),
            _odd_cycle(3, (0, 1, 2), odd_diagonal),
        )

    if template == "exact4-shear-loop-pair":
        return tuple(
            _shear(4, i, j, q[index])
            for index, (i, j) in enumerate(((0, 1), (1, 2), (2, 3), (3, 0)))
        )

    if template == "exact4-graded-shear-pair":
        return (
            _shear(4, 0, 1, q[0]),
            _shear(4, 1, 2, q[1]),
            _shear(4, 2, 3, q[2]),
            _diagonal(4, _positive_diagonal_values(seed, 4, attempt)),
        )

    if template == "exact4-block-shear-pair":
        return tuple(
            _shear(4, i, j, q[index + 2])
            for index, (i, j) in enumerate(((0, 1), (1, 2), (2, 3), (3, 0)))
        )

    if template == "exact4-diagonal-loop-pair":
        return (
            _diagonal(4, _positive_diagonal_values(seed, 4, attempt)),
            *(
                _shear(4, i, j, q[index])
                for index, (i, j) in enumerate(
                    ((0, 1), (1, 2), (2, 3), (3, 0))
                )
            ),
        )

    if template == "exact5-shear-loop-pair":
        return tuple(
            _shear(5, i, j, q[index])
            for index, (i, j) in enumerate(
                ((0, 1), (1, 2), (2, 3), (3, 4), (4, 0))
            )
        )

    if template == "exact5-oddcycle-block-pair":
        return (
            _odd_cycle(
                5,
                (0, 1, 2),
                _positive_diagonal_values(seed, 3, attempt),
            ),
            _shear(5, 2, 3, q[1]),
            _shear(5, 3, 4, q[2]),
            _shear(5, 4, 0, q[3]),
        )

    if template == "exact6-graded-shear-pair":
        return tuple(
            _shear(6, i, j, q[index])
            for index, (i, j) in enumerate(
                ((0, 1), (0, 2), (0, 3), (3, 4), (4, 5), (5, 0))
            )
        )

    raise ValueError(f"unknown template: {template}")


def _transpose_factor(factor: Mapping[str, object]) -> dict[str, object]:
    result = copy.deepcopy(dict(factor))
    kind = result.get("kind")
    if kind == "rational-shear":
        result["i"], result["j"] = result["j"], result["i"]
    elif kind == "positive-rational-diagonal":
        pass
    elif kind == "positive-odd-cycle":
        orientation = result.get("orientation")
        if orientation == "forward":
            result["orientation"] = "transpose"
        elif orientation == "transpose":
            result["orientation"] = "forward"
        else:
            raise ValueError("odd-cycle orientation must be forward or transpose")
    else:
        raise ValueError(f"unknown factor kind: {kind}")
    return result


def _factor_matrix(
    factor: Mapping[str, object],
    *,
    expected_dimension: int,
    path: str,
) -> sp.ImmutableMatrix:
    kind = factor.get("kind")
    dimension = factor.get("dimension")
    if (
        not isinstance(dimension, int)
        or isinstance(dimension, bool)
        or dimension != expected_dimension
    ):
        raise ValueError(f"{path}.dimension does not match the card")

    if kind == "rational-shear":
        expected_keys = {
            "kind",
            "dimension",
            "i",
            "j",
            "q",
            "support",
            "witness",
        }
        if set(factor) != expected_keys:
            raise ValueError(f"{path} has invalid shear fields")
        i = factor["i"]
        j = factor["j"]
        if (
            not isinstance(i, int)
            or isinstance(i, bool)
            or not isinstance(j, int)
            or isinstance(j, bool)
            or not 0 <= i < dimension
            or not 0 <= j < dimension
            or i == j
        ):
            raise ValueError(f"{path} has invalid shear indices")
        if factor["support"] != sorted((i, j)):
            raise ValueError(f"{path} has inconsistent shear support")
        if factor["witness"] != "nilpotent-rational-exponential":
            raise ValueError(f"{path} lacks the shear generator witness")
        result = sp.eye(dimension)
        result[i, j] = sp.Rational(
            *_parse_rational(factor["q"], path=f"{path}.q").as_integer_ratio()
        )
        return sp.ImmutableMatrix(result)

    if kind == "positive-rational-diagonal":
        expected_keys = {
            "kind",
            "dimension",
            "diagonal",
            "support",
            "witness",
        }
        if set(factor) != expected_keys:
            raise ValueError(f"{path} has invalid diagonal fields")
        diagonal = factor["diagonal"]
        if not isinstance(diagonal, list) or len(diagonal) != dimension:
            raise ValueError(f"{path}.diagonal has invalid length")
        values = [
            _parse_rational(entry, path=f"{path}.diagonal[{index}]")
            for index, entry in enumerate(diagonal)
        ]
        if any(value <= 0 for value in values):
            raise ValueError(f"{path}.diagonal must be strictly positive")
        if factor["support"] != list(range(dimension)):
            raise ValueError(f"{path} has inconsistent diagonal support")
        if factor["witness"] != "real-diagonal-log":
            raise ValueError(f"{path} lacks the diagonal generator witness")
        return sp.ImmutableMatrix(
            sp.diag(
                *[
                    sp.Rational(value.numerator, value.denominator)
                    for value in values
                ]
            )
        )

    if kind == "positive-odd-cycle":
        expected_keys = {
            "kind",
            "dimension",
            "cycle",
            "diagonal",
            "orientation",
            "support",
            "witness",
        }
        if set(factor) != expected_keys:
            raise ValueError(f"{path} has invalid odd-cycle fields")
        cycle = factor["cycle"]
        diagonal = factor["diagonal"]
        orientation = factor["orientation"]
        if (
            not isinstance(cycle, list)
            or len(cycle) < 3
            or len(cycle) % 2 != 1
            or any(
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < dimension
                for index in cycle
            )
            or len(set(cycle)) != len(cycle)
        ):
            raise ValueError(f"{path}.cycle must be a valid odd local cycle")
        if not isinstance(diagonal, list) or len(diagonal) != len(cycle):
            raise ValueError(f"{path}.diagonal does not match its cycle")
        values = [
            _parse_rational(entry, path=f"{path}.diagonal[{index}]")
            for index, entry in enumerate(diagonal)
        ]
        if any(value <= 0 for value in values):
            raise ValueError(f"{path}.diagonal must be strictly positive")
        if orientation not in {"forward", "transpose"}:
            raise ValueError(f"{path}.orientation is invalid")
        if factor["support"] != sorted(cycle):
            raise ValueError(f"{path} has inconsistent odd-cycle support")
        if factor["witness"] != "odd-cycle-real-log":
            raise ValueError(f"{path} lacks the odd-cycle generator witness")

        permutation = sp.eye(dimension)
        for index in cycle:
            permutation[index, index] = 0
        for source, target in zip(cycle, cycle[1:] + cycle[:1]):
            permutation[target, source] = 1
        embedded_diagonal = sp.eye(dimension)
        for index, value in zip(cycle, values):
            embedded_diagonal[index, index] = sp.Rational(
                value.numerator, value.denominator
            )
        if orientation == "forward":
            return sp.ImmutableMatrix(permutation * embedded_diagonal)
        return sp.ImmutableMatrix(embedded_diagonal * permutation.T)

    raise ValueError(f"{path} has unknown factor kind {kind!r}")


def _factor_product(
    factors: list[dict[str, object]] | tuple[dict[str, object], ...],
    *,
    dimension: int,
    path: str,
) -> sp.ImmutableMatrix:
    if not 2 <= len(factors) <= 6:
        raise ValueError(f"{path} must contain two through six factors")
    result = sp.eye(dimension)
    for index, factor in enumerate(factors):
        if not isinstance(factor, Mapping):
            raise TypeError(f"{path}[{index}] must be a mapping")
        result = (
            _factor_matrix(
                factor,
                expected_dimension=dimension,
                path=f"{path}[{index}]",
            )
            * result
        )
    return sp.ImmutableMatrix(result)


def _encode_matrix(matrix: sp.MatrixBase) -> list[list[dict[str, int]]]:
    return [
        [
            _encode_rational(
                Fraction(int(sp.numer(matrix[row, column])), int(sp.denom(matrix[row, column])))
            )
            for column in range(matrix.cols)
        ]
        for row in range(matrix.rows)
    ]


def _parse_matrix(value: object, *, dimension: int, path: str) -> sp.ImmutableMatrix:
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError(f"{path} must have {dimension} rows")
    rows: list[list[sp.Rational]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != dimension:
            raise ValueError(f"{path}[{row_index}] must have {dimension} entries")
        exact_row: list[sp.Rational] = []
        for column_index, entry in enumerate(row):
            fraction = _parse_rational(
                entry,
                path=f"{path}[{row_index}][{column_index}]",
            )
            exact_row.append(sp.Rational(fraction.numerator, fraction.denominator))
        rows.append(exact_row)
    return sp.ImmutableMatrix(rows)


def _coefficient(seed: int) -> Fraction:
    base = Fraction(1 + seed % 7, 1 + (seed // 7) % 5)
    return _TIER_MULTIPLIERS[_magnitude_tier(seed)] * base


def _connected_support(
    factors: tuple[tuple[dict[str, object], ...], ...],
    *,
    dimension: int,
) -> bool:
    adjacency = {index: set() for index in range(dimension)}
    for factorization in factors:
        for factor in factorization:
            kind = factor["kind"]
            if kind == "rational-shear":
                i = int(factor["i"])
                j = int(factor["j"])
                adjacency[i].add(j)
                adjacency[j].add(i)
            elif kind == "positive-odd-cycle":
                cycle = factor["cycle"]
                assert isinstance(cycle, list)
                for i, j in zip(cycle, cycle[1:] + cycle[:1]):
                    adjacency[i].add(j)
                    adjacency[j].add(i)
    reached = {0}
    frontier = [0]
    while frontier:
        current = frontier.pop()
        for neighbor in adjacency[current] - reached:
            reached.add(neighbor)
            frontier.append(neighbor)
    return reached == set(range(dimension))


def _build_card(template: str, seed: int) -> dict[str, object]:
    dimension, structural_feature = _TEMPLATE_SPECS[template]
    for attempt in range(32):
        factors = _template_factors(template, seed, attempt)
        primary = _factor_product(
            factors,
            dimension=dimension,
            path="generated.primary",
        )
        partner_factors = tuple(
            _transpose_factor(factor) for factor in reversed(factors)
        )
        partner = _factor_product(
            partner_factors,
            dimension=dimension,
            path="generated.partner",
        )
        if partner != primary.T:
            raise RuntimeError("internal transpose construction failed")
        if primary * partner == partner * primary:
            continue
        if not _connected_support((factors, partner_factors), dimension=dimension):
            continue

        card: dict[str, object] = {
            "schema": _SCHEMA,
            "template": template,
            "seed": seed,
            "dimension": dimension,
            "magnitude_tier": _magnitude_tier(seed),
            "support": list(range(dimension)),
            "structural_feature": structural_feature,
            "promotion_status": _promotion_status(template),
            "atoms": [
                {
                    "atom_id": "atom-0",
                    "orbit_id": "orbit-0",
                    "matrix": _encode_matrix(primary),
                    "factors": list(factors),
                },
                {
                    "atom_id": "atom-1",
                    "orbit_id": "orbit-0",
                    "matrix": _encode_matrix(partner),
                    "factors": list(partner_factors),
                },
            ],
            "orbits": [
                {
                    "orbit_id": "orbit-0",
                    "atom_indices": [0, 1],
                    "relation": "transpose",
                    "coefficient": _encode_rational(_coefficient(seed)),
                }
            ],
        }
        return card
    raise RuntimeError(
        f"could not construct a noncommuting connected candidate for {template} seed {seed}"
    )


@lru_cache(maxsize=None)
def _cached_card_json(template: str, seed: int) -> str:
    return _canonical_json(_build_card(template, seed))


def candidate_card(
    *,
    template: str,
    seed: int,
) -> dict[str, object]:
    """Build one deterministic, exact, transpose-paired candidate card."""

    if not isinstance(template, str):
        raise TypeError("template must be a string")
    if template not in _TEMPLATE_SPECS:
        raise ValueError(f"unknown template: {template}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    if not 0 <= seed <= 255:
        raise ValueError("seed must be in 0..255")
    card = json.loads(_cached_card_json(template, seed))
    if not isinstance(card, dict):
        raise RuntimeError("internal candidate serialization was not an object")
    return card


def _validated_components(
    card: Mapping[str, object],
) -> tuple[
    tuple[sp.ImmutableMatrix, ...],
    tuple[tuple[dict[str, object], ...], ...],
]:
    if not isinstance(card, Mapping):
        raise TypeError("card must be a mapping")
    _validate_json_tree(card)
    expected_card_keys = {
        "schema",
        "template",
        "seed",
        "dimension",
        "magnitude_tier",
        "support",
        "structural_feature",
        "promotion_status",
        "atoms",
        "orbits",
    }
    if set(card) != expected_card_keys:
        raise ValueError("card has missing or unknown fields")
    if card["schema"] != _SCHEMA:
        raise ValueError("card schema is unsupported")

    template = card["template"]
    seed = card["seed"]
    dimension = card["dimension"]
    if not isinstance(template, str) or template not in _TEMPLATE_SPECS:
        raise ValueError("card template is invalid")
    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
        or not 0 <= seed <= 255
    ):
        raise ValueError("card seed is invalid")
    expected_dimension, expected_feature = _TEMPLATE_SPECS[template]
    if (
        not isinstance(dimension, int)
        or isinstance(dimension, bool)
        or dimension != expected_dimension
    ):
        raise ValueError("card dimension does not match its template")
    if card["magnitude_tier"] != _magnitude_tier(seed):
        raise ValueError("card magnitude tier does not match its seed")
    if card["support"] != list(range(dimension)):
        raise ValueError("card support must be the complete ordered local support")
    if card["structural_feature"] != expected_feature:
        raise ValueError("card structural feature does not match its template")
    if card["promotion_status"] != _promotion_status(template):
        raise ValueError("card promotion status does not match its template")

    atoms = card["atoms"]
    if not isinstance(atoms, list) or len(atoms) != 2:
        raise ValueError("the first tranche requires exactly two atoms")
    exact_atoms: list[sp.ImmutableMatrix] = []
    exact_factorizations: list[tuple[dict[str, object], ...]] = []
    expected_atom_keys = {"atom_id", "orbit_id", "matrix", "factors"}
    for atom_index, atom in enumerate(atoms):
        if not isinstance(atom, Mapping) or set(atom) != expected_atom_keys:
            raise ValueError(f"atoms[{atom_index}] has invalid fields")
        if atom["atom_id"] != f"atom-{atom_index}":
            raise ValueError(f"atoms[{atom_index}] has invalid identity")
        if atom["orbit_id"] != "orbit-0":
            raise ValueError(f"atoms[{atom_index}] has invalid orbit")
        factors_value = atom["factors"]
        if not isinstance(factors_value, list):
            raise TypeError(f"atoms[{atom_index}].factors must be a list")
        factors = tuple(copy.deepcopy(factor) for factor in factors_value)
        product = _factor_product(
            factors,
            dimension=dimension,
            path=f"atoms[{atom_index}].factors",
        )
        stored = _parse_matrix(
            atom["matrix"],
            dimension=dimension,
            path=f"atoms[{atom_index}].matrix",
        )
        if product != stored:
            raise ValueError(f"atoms[{atom_index}] does not replay from its factors")
        exact_atoms.append(stored)
        exact_factorizations.append(factors)

    expected_partner_factors = tuple(
        _transpose_factor(factor)
        for factor in reversed(exact_factorizations[0])
    )
    if exact_factorizations[1] != expected_partner_factors:
        raise ValueError("transpose factorization was not derived algebraically")
    if exact_atoms[1] != exact_atoms[0].T:
        raise ValueError("atom alphabet is not exactly transpose closed")

    orbits = card["orbits"]
    if not isinstance(orbits, list) or len(orbits) != 1:
        raise ValueError("the first tranche requires one coefficient orbit")
    orbit = orbits[0]
    if not isinstance(orbit, Mapping) or set(orbit) != {
        "orbit_id",
        "atom_indices",
        "relation",
        "coefficient",
    }:
        raise ValueError("coefficient orbit has invalid fields")
    if (
        orbit["orbit_id"] != "orbit-0"
        or orbit["atom_indices"] != [0, 1]
        or orbit["relation"] != "transpose"
    ):
        raise ValueError("coefficient orbit does not pair both transpose atoms")
    if _parse_rational(orbit["coefficient"], path="orbits[0].coefficient") <= 0:
        raise ValueError("orbit coefficient must be strictly positive")

    if exact_atoms[0] * exact_atoms[1] == exact_atoms[1] * exact_atoms[0]:
        raise ValueError("candidate atoms must be noncommuting")
    if not _connected_support(
        tuple(exact_factorizations),
        dimension=dimension,
    ):
        raise ValueError("candidate support is disconnected")
    for atom_index, atom in enumerate(exact_atoms):
        determinant = sp.det(atom)
        if determinant <= 0:
            raise ValueError(
                f"atoms[{atom_index}] must be invertible with positive determinant"
            )

    return tuple(exact_atoms), tuple(exact_factorizations)


def exact_atoms_from_card(
    card: Mapping[str, object],
) -> tuple[sp.ImmutableMatrix, ...]:
    """Replay and return the exact atom alphabet after strict validation."""

    exact_atoms, _ = _validated_components(card)
    return exact_atoms


def float_atoms_from_card(
    card: Mapping[str, object],
) -> tuple[np.ndarray, ...]:
    """Project exact atoms to NumPy float arrays for frozen numerical oracles."""

    return tuple(
        np.asarray(atom.tolist(), dtype=float)
        for atom in exact_atoms_from_card(card)
    )


def exact_factorizations_from_card(
    card: Mapping[str, object],
) -> tuple[tuple[dict[str, object], ...], ...]:
    """Return validated ordered exact factor witnesses for every atom."""

    _, factorizations = _validated_components(card)
    return factorizations


def candidate_structure_audit(
    card: Mapping[str, object],
) -> dict[str, object]:
    """Return the exact structural launch-gate audit for one valid card."""

    atoms, factorizations = _validated_components(card)
    dimension = atoms[0].rows
    known_reduction: str | None
    if card["promotion_status"] == "known-odd-monomial-p0-control":
        known_reduction = "known-odd-monomial-p0-control"
    else:
        known_reduction = None
    return {
        "valid": True,
        "dimension": dimension,
        "transpose_closed": atoms[1] == atoms[0].T,
        "noncommuting": atoms[0] * atoms[1] != atoms[1] * atoms[0],
        "connected_support": _connected_support(
            factorizations,
            dimension=dimension,
        ),
        "structural_feature": card["structural_feature"],
        "factor_lengths_valid": all(
            2 <= len(factorization) <= 6 for factorization in factorizations
        ),
        "positive_determinants": all(sp.det(atom) > 0 for atom in atoms),
        "invertible": all(sp.det(atom) != 0 for atom in atoms),
        "finite_real_microword": True,
        "known_reduction": known_reduction,
    }


__all__ = [
    "TEMPLATES",
    "candidate_card",
    "candidate_id",
    "candidate_structure_audit",
    "exact_atoms_from_card",
    "exact_factorizations_from_card",
    "float_atoms_from_card",
]
