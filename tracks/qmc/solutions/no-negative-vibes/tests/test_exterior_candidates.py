from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
import re
from collections import Counter
from functools import lru_cache
from fractions import Fraction
from typing import Iterator, Mapping

import numpy as np
import pytest
import sympy as sp

import oracle.exterior_candidates as exterior_candidates
from oracle.exterior_candidates import (
    candidate_card,
    candidate_id,
    candidate_structure_audit,
    exact_atoms_from_card,
    exact_factorizations_from_card,
    float_atoms_from_card,
)


EXPECTED_TEMPLATE_DIMENSIONS = {
    "exact3-oddcycle-shear-pair": 3,
    "exact3-diagonal-oddcycle-pair": 3,
    "exact4-shear-loop-pair": 4,
    "exact4-graded-shear-pair": 4,
    "exact4-block-shear-pair": 4,
    "exact4-diagonal-loop-pair": 4,
    "exact5-shear-loop-pair": 5,
    "exact5-oddcycle-block-pair": 5,
    "exact6-graded-shear-pair": 6,
}
EXPECTED_DIMENSION_COUNTS = {3: 512, 4: 1024, 5: 512, 6: 256}
RATIONAL_KEYS = frozenset({"numerator", "denominator"})
FORBIDDEN_RUNTIME_KEYS = frozenset(
    {"hostname", "username", "absolute_path", "package_version", "runtime"}
)


def _canonical_bytes(card: Mapping[str, object]) -> bytes:
    return json.dumps(
        card,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fraction(value: object) -> Fraction:
    assert isinstance(value, Mapping)
    assert set(value) == RATIONAL_KEYS
    numerator = value["numerator"]
    denominator = value["denominator"]
    assert isinstance(numerator, int) and not isinstance(numerator, bool)
    assert isinstance(denominator, int) and not isinstance(denominator, bool)
    return Fraction(numerator, denominator)


def _sympy_rational(value: object) -> sp.Rational:
    fraction = _fraction(value)
    return sp.Rational(fraction.numerator, fraction.denominator)


def _stored_matrix(value: object) -> sp.ImmutableMatrix:
    assert isinstance(value, list) and value
    rows = [
        [_sympy_rational(entry) for entry in row]
        for row in value
        if isinstance(row, list)
    ]
    assert len(rows) == len(value)
    return sp.ImmutableMatrix(rows)


def _factor_matrix(factor: Mapping[str, object]) -> sp.ImmutableMatrix:
    dimension = factor["dimension"]
    assert isinstance(dimension, int) and not isinstance(dimension, bool)
    result = sp.eye(dimension)
    kind = factor["kind"]

    if kind == "rational-shear":
        i = factor["i"]
        j = factor["j"]
        assert isinstance(i, int) and isinstance(j, int)
        result[i, j] = _sympy_rational(factor["q"])
    elif kind == "positive-rational-diagonal":
        diagonal = factor["diagonal"]
        assert isinstance(diagonal, list) and len(diagonal) == dimension
        result = sp.diag(*[_sympy_rational(entry) for entry in diagonal])
    elif kind == "positive-odd-cycle":
        cycle = factor["cycle"]
        diagonal = factor["diagonal"]
        orientation = factor["orientation"]
        assert isinstance(cycle, list) and len(cycle) % 2 == 1
        assert isinstance(diagonal, list) and len(diagonal) == len(cycle)
        permutation = sp.eye(dimension)
        for index in cycle:
            permutation[index, index] = 0
        for source, target in zip(cycle, cycle[1:] + cycle[:1]):
            permutation[target, source] = 1
        embedded_diagonal = sp.eye(dimension)
        for index, entry in zip(cycle, diagonal):
            embedded_diagonal[index, index] = _sympy_rational(entry)
        if orientation == "forward":
            result = permutation * embedded_diagonal
        elif orientation == "transpose":
            result = embedded_diagonal * permutation.T
        else:
            raise AssertionError(f"unexpected odd-cycle orientation: {orientation}")
    else:
        raise AssertionError(f"unexpected factor kind: {kind}")

    return sp.ImmutableMatrix(result)


def _macro_product(
    factorization: tuple[dict[str, object], ...],
) -> sp.ImmutableMatrix:
    dimension = factorization[0]["dimension"]
    assert isinstance(dimension, int)
    result = sp.eye(dimension)
    for factor in factorization:
        result = _factor_matrix(factor) * result
    return sp.ImmutableMatrix(result)


def _transpose_factor(factor: Mapping[str, object]) -> dict[str, object]:
    result = copy.deepcopy(dict(factor))
    kind = result["kind"]
    if kind == "rational-shear":
        result["i"], result["j"] = result["j"], result["i"]
    elif kind == "positive-rational-diagonal":
        pass
    elif kind == "positive-odd-cycle":
        result["orientation"] = (
            "transpose" if result["orientation"] == "forward" else "forward"
        )
    else:
        raise AssertionError(f"unexpected factor kind: {kind}")
    return result


def _walk(value: object) -> Iterator[tuple[str | None, object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield None, child
            yield from _walk(child)


def _assert_float_free_and_canonical_rationals(card: Mapping[str, object]) -> None:
    for key, value in _walk(card):
        assert key not in FORBIDDEN_RUNTIME_KEYS
        assert not isinstance(value, float)
        if isinstance(value, Mapping):
            keys = set(value)
            if keys & RATIONAL_KEYS:
                assert keys == RATIONAL_KEYS
                numerator = value["numerator"]
                denominator = value["denominator"]
                assert isinstance(numerator, int) and not isinstance(numerator, bool)
                assert isinstance(denominator, int) and not isinstance(
                    denominator, bool
                )
                assert denominator > 0
                assert math.gcd(numerator, denominator) == 1
                if numerator == 0:
                    assert denominator == 1
        if isinstance(value, str):
            assert value.casefold() not in {"nan", "infinity", "+infinity", "-infinity"}
            assert re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)", value) is None


@lru_cache(maxsize=1)
def _all_cards() -> tuple[dict[str, object], ...]:
    return tuple(
        candidate_card(template=template, seed=seed)
        for template in EXPECTED_TEMPLATE_DIMENSIONS
        for seed in range(256)
    )


@pytest.mark.parametrize("template", tuple(EXPECTED_TEMPLATE_DIMENSIONS))
def test_candidate_card_accepts_exact_template_list(template: str) -> None:
    """Catches deleting or renaming one of the nine frozen first-tranche templates."""
    assert candidate_card(template=template, seed=0)["template"] == template


def test_candidate_card_rejects_unknown_template() -> None:
    """Catches silently treating a misspelled template as another grammar."""
    with pytest.raises(ValueError, match="template"):
        candidate_card(template="exact4-not-a-template", seed=0)


@pytest.mark.parametrize("seed", (-1, 256, 1.0, "1", True))
def test_candidate_card_rejects_invalid_seed(seed: object) -> None:
    """Catches accepting noninteger or out-of-protocol seed identities."""
    with pytest.raises((TypeError, ValueError), match="seed"):
        candidate_card(template="exact4-shear-loop-pair", seed=seed)  # type: ignore[arg-type]


def test_all_first_tranche_cards_have_frozen_counts_and_unique_ids() -> None:
    """Catches seed collisions, wrong dimensions, or an incomplete 2304-card tranche."""
    cards = _all_cards()
    ids = [candidate_id(card) for card in cards]

    assert len(cards) == 2304
    assert len(set(ids)) == 2304
    assert Counter(card["dimension"] for card in cards) == EXPECTED_DIMENSION_COUNTS
    for template in EXPECTED_TEMPLATE_DIMENSIONS:
        template_ids = [
            candidate_id(card) for card in cards if card["template"] == template
        ]
        assert len(template_ids) == 256
        assert len(set(template_ids)) == 256


def test_cards_are_deterministic_canonical_json_and_sha256_identified() -> None:
    """Catches nondeterministic data or hashing anything except the complete card."""
    first = candidate_card(template="exact5-shear-loop-pair", seed=173)
    second = candidate_card(template="exact5-shear-loop-pair", seed=173)
    encoded = _canonical_bytes(first)
    round_tripped = json.loads(encoded)

    assert first == second
    assert _canonical_bytes(round_tripped) == encoded
    assert candidate_id(first) == hashlib.sha256(encoded).hexdigest()
    assert candidate_id(round_tripped) == candidate_id(first)
    assert re.fullmatch(r"[0-9a-f]{64}", candidate_id(first))


def test_all_cards_are_float_free_with_canonical_reduced_rationals() -> None:
    """Catches a float, decimal string, runtime field, or noncanonical rational."""
    for card in _all_cards():
        _assert_float_free_and_canonical_rationals(card)
        json.dumps(card, allow_nan=False)


@pytest.mark.parametrize("template", tuple(EXPECTED_TEMPLATE_DIMENSIONS))
def test_exact_factor_products_replay_stored_atoms(template: str) -> None:
    """Catches changing factor order or storing a matrix not defined by its factors."""
    card = candidate_card(template=template, seed=91)
    exact_atoms = exact_atoms_from_card(card)
    factorizations = exact_factorizations_from_card(card)
    stored_atoms = tuple(_stored_matrix(atom["matrix"]) for atom in card["atoms"])

    assert len(exact_atoms) == len(factorizations) == len(stored_atoms) == 2
    assert exact_atoms == stored_atoms
    assert tuple(_macro_product(factors) for factors in factorizations) == stored_atoms
    assert all(2 <= len(factors) <= 6 for factors in factorizations)


@pytest.mark.parametrize("template", tuple(EXPECTED_TEMPLATE_DIMENSIONS))
def test_transpose_partner_is_derived_by_reversed_transposed_factors(
    template: str,
) -> None:
    """Catches independently randomizing the transpose partner."""
    card = candidate_card(template=template, seed=211)
    atom, partner = exact_atoms_from_card(card)
    factors, partner_factors = exact_factorizations_from_card(card)

    assert partner == atom.T
    assert partner_factors == tuple(
        _transpose_factor(factor) for factor in reversed(factors)
    )
    assert _macro_product(partner_factors) == partner


def test_every_card_has_one_positive_shared_transpose_coefficient_orbit() -> None:
    """Catches unmatched atoms or unequal/nonpositive Hermitian orbit coefficients."""
    for card in _all_cards():
        orbits = card["orbits"]
        assert isinstance(orbits, list) and len(orbits) == 1
        orbit = orbits[0]
        assert orbit == {
            "orbit_id": "orbit-0",
            "atom_indices": [0, 1],
            "relation": "transpose",
            "coefficient": orbit["coefficient"],
        }
        assert _fraction(orbit["coefficient"]) > 0
        assert [atom["orbit_id"] for atom in card["atoms"]] == [
            "orbit-0",
            "orbit-0",
        ]


def test_complete_card_identity_hashes_magnitude_coefficient_order_and_support() -> None:
    """Catches omitting any frozen mathematical identity field from the hash."""
    card = candidate_card(template="exact4-graded-shear-pair", seed=37)
    original_id = candidate_id(card)
    mutations: list[dict[str, object]] = []

    changed_tier = copy.deepcopy(card)
    changed_tier["magnitude_tier"] = (
        "triple" if card["magnitude_tier"] != "triple" else "quarter"
    )
    mutations.append(changed_tier)

    changed_coefficient = copy.deepcopy(card)
    changed_coefficient["orbits"][0]["coefficient"] = {
        "numerator": 17,
        "denominator": 19,
    }
    mutations.append(changed_coefficient)

    changed_order = copy.deepcopy(card)
    changed_order["atoms"][0]["factors"][0:2] = reversed(
        changed_order["atoms"][0]["factors"][0:2]
    )
    mutations.append(changed_order)

    changed_support = copy.deepcopy(card)
    changed_support["support"] = list(reversed(changed_support["support"]))
    mutations.append(changed_support)

    assert all(candidate_id(mutated) != original_id for mutated in mutations)


def test_all_cards_pass_exact_structure_audit() -> None:
    """Catches a disconnected, commuting, singular, or non-witnessed candidate."""
    allowed_features = {
        "loop",
        "odd-cycle-routing",
        "cross-block-edge",
        "degree-three",
    }
    for card in _all_cards():
        audit = candidate_structure_audit(card)
        assert audit["valid"] is True
        assert audit["dimension"] == card["dimension"]
        assert audit["transpose_closed"] is True
        assert audit["noncommuting"] is True
        assert audit["connected_support"] is True
        assert audit["structural_feature"] in allowed_features
        assert audit["factor_lengths_valid"] is True
        assert audit["positive_determinants"] is True
        assert audit["invertible"] is True
        assert audit["finite_real_microword"] is True


def test_known_odd_monomial_control_replays_minimal_n3_example() -> None:
    """Catches losing the explicit P0 reduction control or its exact anchor."""
    card = candidate_card(template="exact3-diagonal-oddcycle-pair", seed=0)
    permutation = sp.ImmutableMatrix([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
    diagonal = sp.diag(2, 3, 5)
    atom, partner = exact_atoms_from_card(card)
    audit = candidate_structure_audit(card)

    assert atom == permutation * diagonal
    assert partner == atom.T
    assert atom * partner != partner * atom
    assert card["promotion_status"] == "known-odd-monomial-p0-control"
    assert audit["known_reduction"] == "known-odd-monomial-p0-control"


@pytest.mark.parametrize("template", tuple(EXPECTED_TEMPLATE_DIMENSIONS))
def test_float_projection_agrees_entrywise_with_exact_atoms(template: str) -> None:
    """Catches the numerical projection changing an exact candidate."""
    card = candidate_card(template=template, seed=149)
    exact_atoms = exact_atoms_from_card(card)
    float_atoms = float_atoms_from_card(card)

    assert len(float_atoms) == len(exact_atoms)
    for numerical, exact in zip(float_atoms, exact_atoms):
        assert numerical.dtype == np.dtype(float)
        np.testing.assert_array_equal(
            numerical,
            np.asarray(exact.tolist(), dtype=float),
        )


def test_candidate_api_has_no_runtime_scale_and_does_not_need_scipy_expm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches reintroducing a mutable float scale or an expm-defined identity."""
    signature = inspect.signature(candidate_card)
    assert tuple(signature.parameters) == ("template", "seed")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert "scale" not in inspect.signature(float_atoms_from_card).parameters

    def forbidden_expm(*args: object, **kwargs: object) -> object:
        raise AssertionError("candidate identity must not call scipy.linalg.expm")

    if hasattr(exterior_candidates, "expm"):
        monkeypatch.setattr(exterior_candidates, "expm", forbidden_expm)
    try:
        import scipy.linalg as scipy_linalg
    except ModuleNotFoundError:
        scipy_linalg = None
    if scipy_linalg is not None:
        monkeypatch.setattr(scipy_linalg, "expm", forbidden_expm)

    card = candidate_card(template="exact6-graded-shear-pair", seed=255)
    exact_atoms_from_card(card)
    float_atoms_from_card(card)


@pytest.mark.parametrize(
    "mutation",
    (
        "stored-matrix",
        "coefficient",
        "factor-order",
        "support",
        "runtime-field",
    ),
)
def test_invalid_mutated_cards_fail_closed(mutation: str) -> None:
    """Catches accepting a card whose exact replay or protocol identity was altered."""
    card = candidate_card(template="exact4-block-shear-pair", seed=83)
    mutated = copy.deepcopy(card)

    if mutation == "stored-matrix":
        mutated["atoms"][0]["matrix"][0][0] = {"numerator": 999, "denominator": 1}
    elif mutation == "coefficient":
        mutated["orbits"][0]["coefficient"] = {"numerator": 0, "denominator": 1}
    elif mutation == "factor-order":
        mutated["atoms"][0]["factors"][0:2] = reversed(
            mutated["atoms"][0]["factors"][0:2]
        )
    elif mutation == "support":
        mutated["support"] = mutated["support"][:-1]
    elif mutation == "runtime-field":
        mutated["runtime"] = "host-dependent"
    else:
        raise AssertionError(mutation)

    with pytest.raises(ValueError):
        candidate_structure_audit(mutated)


@pytest.mark.parametrize(
    "bad_rational",
    (
        {"numerator": 1, "denominator": 0},
        {"numerator": 2, "denominator": 4},
        {"numerator": 0, "denominator": 7},
        {"numerator": 1.0, "denominator": 2},
    ),
)
def test_malformed_rationals_and_floats_fail_closed(
    bad_rational: dict[str, object],
) -> None:
    """Catches hashing or replaying a noncanonical exact number."""
    card = candidate_card(template="exact3-oddcycle-shear-pair", seed=19)
    card["orbits"][0]["coefficient"] = bad_rational

    with pytest.raises((TypeError, ValueError)):
        candidate_id(card)
    with pytest.raises((TypeError, ValueError)):
        exact_atoms_from_card(card)
