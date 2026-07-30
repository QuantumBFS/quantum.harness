"""Independently rebuild and verify an exact Ky Fan problem artifact."""

from __future__ import annotations

import argparse
from fractions import Fraction
from functools import lru_cache
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import sys


ZERO_G = (Fraction(0), Fraction(0))
ONE_G = (Fraction(1), Fraction(0))
NEG_ONE_G = (Fraction(-1), Fraction(0))
POS_I_G = (Fraction(0), Fraction(1))
NEG_I_G = (Fraction(0), Fraction(-1))

LOCAL_PRODUCT = {
    ("I", "I"): (ONE_G, "I"),
    ("I", "X"): (ONE_G, "X"),
    ("I", "Y"): (ONE_G, "Y"),
    ("I", "Z"): (ONE_G, "Z"),
    ("X", "I"): (ONE_G, "X"),
    ("Y", "I"): (ONE_G, "Y"),
    ("Z", "I"): (ONE_G, "Z"),
    ("X", "X"): (ONE_G, "I"),
    ("Y", "Y"): (ONE_G, "I"),
    ("Z", "Z"): (ONE_G, "I"),
    ("X", "Y"): (POS_I_G, "Z"),
    ("Y", "Z"): (POS_I_G, "X"),
    ("Z", "X"): (POS_I_G, "Y"),
    ("Y", "X"): (NEG_I_G, "Z"),
    ("Z", "Y"): (NEG_I_G, "X"),
    ("X", "Z"): (NEG_I_G, "Y"),
}

LEVELS = {
    "L0": (3, 2, 1),
    "L1": (4, 2, 1),
    "L2": (4, 3, 2),
    "L3": (5, 3, 2),
}

MANIFEST_KEYS = {
    "schema_version",
    "purpose",
    "boundary",
    "local_state_convention",
    "symmetry",
    "localizer_mode",
    "problem_file",
    "problem_sha256",
    "relation_table_sha256",
    "source_file_sha256",
}

PROBLEM_KEYS = {
    "schema_version",
    "purpose",
    "size",
    "detuning",
    "hierarchy",
    "localizer_mode",
    "moment_basis",
    "safe_basis",
    "variables",
    "objective",
    "equalities",
    "psd_blocks",
    "unrealified_psd_blocks",
    "magnitude_witnesses",
    "clique_orbits",
    "clique_images",
    "localizer_sites",
    "constrained_trace_table",
    "provenance",
    "statistics",
}

SOURCE_PATHS = {
    "src/challenge233/sdp/algebra.py",
    "src/challenge233/sdp/constraints.py",
    "src/challenge233/sdp/localizers.py",
    "src/challenge233/sdp/constrained_trace.py",
    "src/challenge233/sdp/hierarchy.py",
    "src/challenge233/sdp/kyfan.py",
    "src/challenge233/sdp/kyfan_artifact.py",
    "src/challenge233/sdp/verify_kyfan_problem.py",
}


def _fail(message):
    raise ValueError(message)


def _fraction_text(value):
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _parse_fraction(value, component):
    if not isinstance(value, str):
        _fail(f"{component} must be an exact fraction string")
    pieces = value.split("/")
    if len(pieces) != 2:
        _fail(f"{component} must be numerator/denominator")
    try:
        result = Fraction(int(pieces[0]), int(pieces[1]))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{component} is not a valid fraction") from error
    if value != _fraction_text(result):
        _fail(f"{component} fraction is not canonical")
    return result


def _gadd(left, right):
    return (left[0] + right[0], left[1] + right[1])


def _gneg(value):
    return (-value[0], -value[1])


def _gmul(left, right):
    return (
        left[0] * right[0] - left[1] * right[1],
        left[0] * right[1] + left[1] * right[0],
    )


def _gconj(value):
    return (value[0], -value[1])


def _gscale(value, scalar):
    scalar = Fraction(scalar)
    return (value[0] * scalar, value[1] * scalar)


def _encode_gaussian(value):
    return {
        "real": _fraction_text(value[0]),
        "imag": _fraction_text(value[1]),
    }


def _word(factors=()):
    factors = tuple((int(site), str(label)) for site, label in factors)
    sites = tuple(site for site, _ in factors)
    if sites != tuple(sorted(set(sites))):
        _fail("independent word is not canonical")
    if any(label not in {"X", "Y", "Z"} for _, label in factors):
        _fail("independent word has a non-Pauli label")
    return factors


def _encode_word(value):
    return [[site, label] for site, label in value]


def _canonicalize(factors):
    phase = ONE_G
    local = {}
    for raw_site, raw_label in factors:
        site = int(raw_site)
        label = str(raw_label)
        previous = local.get(site, "I")
        try:
            local_phase, result = LOCAL_PRODUCT[(previous, label)]
        except KeyError as error:
            raise ValueError("unknown Pauli label") from error
        phase = _gmul(phase, local_phase)
        if result == "I":
            local.pop(site, None)
        else:
            local[site] = result
    return phase, _word(tuple(sorted(local.items())))


def _polynomial(terms=()):
    combined = {}
    for word_value, coefficient in terms:
        coefficient = (
            Fraction(coefficient[0]),
            Fraction(coefficient[1]),
        )
        combined[word_value] = _gadd(
            combined.get(word_value, ZERO_G),
            coefficient,
        )
    return tuple(
        (word_value, coefficient)
        for word_value, coefficient in sorted(combined.items())
        if coefficient != ZERO_G
    )


def _poly_add(*values):
    return _polynomial(
        term
        for value in values
        for term in value
    )


def _poly_scale(coefficient, value):
    return _polynomial(
        (word_value, _gmul(coefficient, word_coefficient))
        for word_value, word_coefficient in value
    )


@lru_cache(maxsize=200_000)
def _poly_multiply(left, right):
    return _polynomial(
        (
            canonical_word,
            _gmul(
                _gmul(left_coefficient, right_coefficient),
                phase,
            ),
        )
        for left_word, left_coefficient in left
        for right_word, right_coefficient in right
        for phase, canonical_word in (
            (_canonicalize(left_word + right_word),)
        )
    )


def _poly_adjoint(value):
    return _polynomial(
        (word_value, _gconj(coefficient))
        for word_value, coefficient in value
    )


def _word_polynomial(word_value):
    return _polynomial(((word_value, ONE_G),))


def _factor(site, label):
    if label == "I":
        return _word_polynomial(_word())
    if label in {"X", "Y", "Z"}:
        return _word_polynomial(_word(((site, label),)))
    identity = _word_polynomial(_word())
    z_value = _word_polynomial(_word(((site, "Z"),)))
    if label == "P":
        return _poly_add(
            _poly_scale((Fraction(1, 2), Fraction(0)), identity),
            _poly_scale((Fraction(-1, 2), Fraction(0)), z_value),
        )
    if label == "n":
        return _poly_add(
            _poly_scale((Fraction(1, 2), Fraction(0)), identity),
            _poly_scale((Fraction(1, 2), Fraction(0)), z_value),
        )
    _fail("unknown expanded operator label")


def _expand_factors(factors):
    result = _word_polynomial(_word())
    for site, label in factors:
        result = _poly_multiply(result, _factor(site, label))
    return result


def _blockade(site, size):
    return _expand_factors(
        (
            (site, "n"),
            ((site + 1) % size, "n"),
        )
    )


def _hamiltonian(size, detuning):
    values = []
    for site in range(size):
        values.append(
            _expand_factors(
                (
                    ((site - 1) % size, "P"),
                    (site, "X"),
                    ((site + 1) % size, "P"),
                )
            )
        )
        values.append(
            _poly_scale(
                (-detuning, Fraction(0)),
                _expand_factors(((site, "n"),)),
            )
        )
    return _poly_add(*values)


def _elements(size):
    return tuple(
        (shift, reflected)
        for reflected in (False, True)
        for shift in range(size)
    )


def _act_site(element, site, size):
    shift, reflected = element
    return (shift + (-site if reflected else site)) % size


def _act_word(element, word_value, size):
    return _word(
        tuple(
            sorted(
                (
                    _act_site(element, site, size),
                    label,
                )
                for site, label in word_value
            )
        )
    )


@lru_cache(maxsize=200_000)
def _word_orbit(size, word_value):
    return tuple(
        sorted(
            {
                _act_word(element, word_value, size)
                for element in _elements(size)
            }
        )
    )


def _blockade_site_image(element, site, size):
    shift, reflected = element
    if reflected:
        return (shift - site - 1) % size
    return (shift + site) % size


def _window(size, start, range_sites):
    width = min(size, range_sites)
    return tuple((start + offset) % size for offset in range(width))


def _pauli_basis(sites, max_weight):
    sites = tuple(dict.fromkeys(sites))
    words = [_word()]
    for weight in range(1, min(max_weight, len(sites)) + 1):
        for chosen in combinations(sites, weight):
            for labels in product(("X", "Y", "Z"), repeat=weight):
                words.append(_word(tuple(sorted(zip(chosen, labels)))))
    return tuple(sorted(set(words)))


def _expand_safe(safe_word, size):
    result = _word_polynomial(_word())
    for raw_site, label in safe_word:
        site = raw_site % size
        if label == "F":
            value = _expand_factors(
                (
                    ((site - 1) % size, "P"),
                    (site, "X"),
                    ((site + 1) % size, "P"),
                )
            )
        else:
            value = _expand_factors(((site, label),))
        result = _poly_multiply(result, value)
    return result


def _poly_support(value):
    return {
        site
        for word_value, _ in value
        for site, _ in word_value
    }


def _safe_basis(size, start, range_sites, safe_depth):
    window = _window(size, start, range_sites)
    window_set = set(window)
    letters = tuple(
        ((site, label),)
        for site in window
        for label in ("F", "Z", "P", "n")
    )
    representatives = {
        _expand_safe((), size): (),
    }
    for depth in range(1, safe_depth + 1):
        for factors in product(letters, repeat=depth):
            safe_word = tuple(
                factor
                for letter in factors
                for factor in letter
            )
            polynomial = _expand_safe(safe_word, size)
            if not _poly_support(polynomial) <= window_set:
                continue
            representatives.setdefault(polynomial, safe_word)
    return tuple(
        sorted(
            representatives.values(),
            key=lambda value: (len(value), value),
        )
    )


def _z_cycle_sum(size, z_sites):
    total = 0
    for first in (0, 1):
        initial = (1 if first else -1) if 0 in z_sites else 1
        states = {(first, first): initial}
        for site in range(1, size):
            next_states = {}
            for (fixed_first, previous), weight in states.items():
                for bit in (0, 1):
                    if previous and bit:
                        continue
                    factor = (
                        (1 if bit else -1)
                        if site in z_sites
                        else 1
                    )
                    key = (fixed_first, bit)
                    next_states[key] = (
                        next_states.get(key, 0) + weight * factor
                    )
            states = next_states
        total += sum(
            weight
            for (fixed_first, final), weight in states.items()
            if not (fixed_first and final)
        )
    return total


def _pauli_trace(size, word_value):
    if any(label in {"X", "Y"} for _, label in word_value):
        return 0
    return _z_cycle_sum(
        size,
        {
            site
            for site, label in word_value
            if label == "Z"
        },
    )


def _poly_trace(size, value):
    result = ZERO_G
    for word_value, coefficient in value:
        result = _gadd(
            result,
            _gscale(coefficient, _pauli_trace(size, word_value)),
        )
    return result


def _form(constant=Fraction(0), terms=()):
    combined = {}
    for variable, coefficient in terms:
        variable = int(variable)
        combined[variable] = (
            combined.get(variable, Fraction(0))
            + Fraction(coefficient)
        )
    return (
        Fraction(constant),
        tuple(
            (variable, coefficient)
            for variable, coefficient in sorted(combined.items())
            if coefficient
        ),
    )


def _fadd(left, right):
    return _form(left[0] + right[0], left[1] + right[1])


def _fneg(value):
    return _fscale(value, Fraction(-1))


def _fsub(left, right):
    return _fadd(left, _fneg(right))


def _fscale(value, coefficient):
    coefficient = Fraction(coefficient)
    return _form(
        value[0] * coefficient,
        (
            (variable, term_coefficient * coefficient)
            for variable, term_coefficient in value[1]
        ),
    )


def _fzero(value):
    return value[0] == 0 and not value[1]


def _encode_form(value):
    return {
        "constant": _fraction_text(value[0]),
        "terms": [
            [variable, _fraction_text(coefficient)]
            for variable, coefficient in value[1]
        ],
    }


def _cform(real=None, imag=None):
    return (
        _form() if real is None else real,
        _form() if imag is None else imag,
    )


def _cadd(left, right):
    return (_fadd(left[0], right[0]), _fadd(left[1], right[1]))


def _cneg(value):
    return (_fneg(value[0]), _fneg(value[1]))


def _cconj(value):
    return (value[0], _fneg(value[1]))


def _cscale(value, coefficient):
    return (
        _fsub(
            _fscale(value[0], coefficient[0]),
            _fscale(value[1], coefficient[1]),
        ),
        _fadd(
            _fscale(value[0], coefficient[1]),
            _fscale(value[1], coefficient[0]),
        ),
    )


def _cconstant(value):
    return _cform(_form(value[0]), _form(value[1]))


def _czero(value):
    return _fzero(value[0]) and _fzero(value[1])


def _encode_cform(value):
    return {
        "real": _encode_form(value[0]),
        "imag": _encode_form(value[1]),
    }


class _Functional:
    def __init__(self, size, variables):
        self.size = size
        self.indices = {
            variable["representative_word"]: variable["index"]
            for variable in variables
        }
        self.cache = {}

    def word(self, word_value):
        if word_value in self.cache:
            return self.cache[word_value]
        if not word_value:
            result = _cform(_form(Fraction(2)))
        else:
            representative = _word_orbit(self.size, word_value)[0]
            if representative not in self.indices:
                _fail("independent moment was not registered")
            result = _cform(
                _form(
                    Fraction(0),
                    ((self.indices[representative], Fraction(1)),),
                )
            )
        self.cache[word_value] = result
        return result

    def polynomial(self, value):
        result = _cform()
        for word_value, coefficient in value:
            result = _cadd(
                result,
                _cscale(self.word(word_value), coefficient),
            )
        return result


def _support_rows(size, basis, sites):
    rows = []
    tests = tuple(_word_polynomial(word_value) for word_value in basis)
    for site in sites:
        blockade = _blockade(site, size)
        for test_index, test in enumerate(tests):
            rows.append(
                (
                    site,
                    "left",
                    test_index,
                    _poly_multiply(blockade, test),
                )
            )
            rows.append(
                (
                    site,
                    "right",
                    test_index,
                    _poly_multiply(test, blockade),
                )
            )
    return tuple(rows)


def _sandwich_rows(size, safe_basis, sites):
    expanded = tuple(_expand_safe(word_value, size) for word_value in safe_basis)
    adjoints = tuple(_poly_adjoint(value) for value in expanded)
    rows = []
    for site in sites:
        blockade = _blockade(site, size)
        lefts = tuple(
            _poly_multiply(adjoint, blockade)
            for adjoint in adjoints
        )
        for row, left in enumerate(lefts):
            for column in range(row, len(expanded)):
                rows.append(
                    (
                        site,
                        row,
                        column,
                        _poly_multiply(left, expanded[column]),
                    )
                )
    return tuple(rows)


def _representative_localizer_sites(size, start, range_sites):
    window = _window(size, start, range_sites)
    window_set = set(window)
    internal = {
        site
        for site in range(size)
        if site in window_set and (site + 1) % size in window_set
    }
    stabilizer = tuple(
        element
        for element in _elements(size)
        if {
            _act_site(element, site, size)
            for site in window
        }
        == window_set
    )
    unassigned = set(internal)
    representatives = []
    while unassigned:
        representative = min(unassigned)
        orbit = {
            _blockade_site_image(element, representative, size)
            for element in stabilizer
        } & internal
        representatives.append(representative)
        unassigned.difference_update(orbit)
    return tuple(representatives)


def _clique_orbit(size, start, range_sites):
    seed = _window(size, start, range_sites)
    return tuple(
        sorted(
            {
                tuple(
                    sorted(
                        _act_site(element, site, size)
                        for site in seed
                    )
                )
                for element in _elements(size)
            }
        )
    )


def _clique_images(
    size,
    start,
    range_sites,
    moment_weight,
    localizer_representatives,
):
    basis = _pauli_basis(_window(size, start, range_sites), moment_weight)
    window = _window(size, start, range_sites)
    images = []
    for element in _elements(size):
        transformed = tuple(
            _act_word(element, word_value, size)
            for word_value in basis
        )
        image_basis = tuple(sorted(transformed))
        index = {
            word_value: position
            for position, word_value in enumerate(image_basis)
        }
        images.append(
            {
                "shift": element[0],
                "reflected": element[1],
                "sites": sorted(
                    _act_site(element, site, size)
                    for site in window
                ),
                "representative_blocks": [
                    "gamma",
                    "blockade-complement",
                ],
                "row_permutation": [
                    index[word_value] for word_value in transformed
                ],
                "localizer_sites": sorted(
                    {
                        _blockade_site_image(
                            element,
                            site,
                            size,
                        )
                        for site in localizer_representatives
                    }
                ),
            }
        )
    return images


def _registry(size, polynomials):
    representatives = {
        _word_orbit(size, word_value)[0]
        for polynomial in polynomials
        for word_value, _ in polynomial
        if word_value
    }
    return tuple(
        {
            "index": index,
            "representative_word": representative,
            "representative": _encode_word(representative),
            "orbit": [
                _encode_word(word_value)
                for word_value in _word_orbit(size, representative)
            ],
        }
        for index, representative in enumerate(sorted(representatives))
    )


def _normalized_matrices(size, products, functional):
    kappa = _z_cycle_sum(size, set())
    gamma = []
    complement = []
    for product_row in products:
        gamma_row = []
        complement_row = []
        for polynomial in product_row:
            ell = functional.polynomial(polynomial)
            tau = _cconstant(_poly_trace(size, polynomial))
            gamma_row.append(
                _cscale(
                    ell,
                    (Fraction(1, 2), Fraction(0)),
                )
            )
            complement_row.append(
                _cadd(
                    _cscale(
                        tau,
                        (Fraction(1, kappa - 2), Fraction(0)),
                    ),
                    _cscale(
                        ell,
                        (Fraction(-1, kappa - 2), Fraction(0)),
                    ),
                )
            )
        gamma.append(tuple(gamma_row))
        complement.append(tuple(complement_row))
    return tuple(gamma), tuple(complement)


def _realify(matrix):
    dimension = len(matrix)
    return tuple(
        tuple(
            (
                matrix[row][column][0]
                if row < dimension and column < dimension
                else _fneg(matrix[row][column - dimension][1])
                if row < dimension
                else matrix[row - dimension][column][1]
                if column < dimension
                else matrix[row - dimension][column - dimension][0]
            )
            for column in range(2 * dimension)
        )
        for row in range(2 * dimension)
    )


def _complex_block(identifier, matrix, provenance):
    return {
        "identifier": identifier,
        "dimension": len(matrix),
        "entries": [
            [_encode_cform(entry) for entry in row]
            for row in matrix
        ],
        "provenance": provenance,
    }


def _real_block(identifier, matrix, provenance):
    return {
        "identifier": identifier,
        "dimension": len(matrix),
        "entries": [
            [_encode_form(entry) for entry in row]
            for row in matrix
        ],
        "provenance": provenance,
    }


def _magnitude_witnesses(variables, gamma):
    unit = _form(Fraction(1))
    coordinates = {}
    dimension = len(gamma)
    for row in range(dimension):
        if gamma[row][row] != unit:
            continue
        for column in range(dimension):
            if row == column or gamma[column][column] != unit:
                continue
            entry = gamma[row][column]
            if entry[0] != 0 or len(entry[1]) != 1:
                continue
            variable, coefficient = entry[1][0]
            if abs(coefficient) != Fraction(1, 2):
                continue
            coordinates.setdefault(
                variable,
                (row, column, (2 * coefficient, Fraction(0))),
            )
    result = []
    for variable in variables:
        index = variable["index"]
        if index not in coordinates:
            _fail("independent PSD magnitude witness is missing")
        row, column, phase = coordinates[index]
        result.append(
            {
                "variable": index,
                "block": "gamma",
                "row": row,
                "column": column,
                "phase": _encode_gaussian(phase),
                "bound": "2/1",
            }
        )
    return result


def _localizer_equalities(functional, support_rows, sandwich_rows):
    equalities = []
    for site, side, test_index, polynomial in support_rows:
        value = functional.polynomial(polynomial)
        provenance = {
            "localizer_kind": f"{side}-support",
            "site": site,
            "test_index": test_index,
        }
        prefix = f"support-site-{site}-{side}-test-{test_index}"
        if not _fzero(value[0]):
            equalities.append(
                {
                    "identifier": f"{prefix}-real",
                    "form": _encode_form(value[0]),
                    "provenance": {
                        **provenance,
                        "component": "real",
                    },
                }
            )
        if not _fzero(value[1]):
            equalities.append(
                {
                    "identifier": f"{prefix}-imag",
                    "form": _encode_form(value[1]),
                    "provenance": {
                        **provenance,
                        "component": "imag",
                    },
                }
            )
    for site, row, column, polynomial in sandwich_rows:
        value = functional.polynomial(polynomial)
        provenance = {
            "localizer_kind": "safe-sandwich",
            "site": site,
            "row": row,
            "column": column,
        }
        prefix = (
            f"safe-sandwich-site-{site}"
            f"-row-{row}-column-{column}"
        )
        if not _fzero(value[0]):
            equalities.append(
                {
                    "identifier": f"{prefix}-real",
                    "form": _encode_form(value[0]),
                    "provenance": {
                        **provenance,
                        "component": "real",
                    },
                }
            )
        if not _fzero(value[1]):
            equalities.append(
                {
                    "identifier": f"{prefix}-imag",
                    "form": _encode_form(value[1]),
                    "provenance": {
                        **provenance,
                        "component": "imag",
                    },
                }
            )
    return equalities


def _affine_nonzeros(form_value):
    return int(form_value[0] != 0) + len(form_value[1])


def _expected_payload(size, detuning, hierarchy, localizer_mode):
    if hierarchy.startswith("global-d"):
        try:
            moment_weight = int(hierarchy.removeprefix("global-d"))
        except ValueError as error:
            raise ValueError("unknown global hierarchy") from error
        range_sites = size
        safe_depth = 1
        basis = _pauli_basis(range(size), moment_weight)
        safe_basis = _safe_basis(
            size,
            0,
            range_sites,
            safe_depth,
        )
        localizer_sites = tuple(range(size))
        image_localizer_representatives = (
            _representative_localizer_sites(size, 0, range_sites)
        )
    elif hierarchy in LEVELS:
        range_sites, moment_weight, safe_depth = LEVELS[hierarchy]
        basis = _pauli_basis(
            _window(size, 0, range_sites),
            moment_weight,
        )
        safe_basis = _safe_basis(
            size,
            0,
            range_sites,
            safe_depth,
        )
        localizer_sites = _representative_localizer_sites(
            size,
            0,
            range_sites,
        )
        image_localizer_representatives = localizer_sites
    else:
        _fail("unknown Ky Fan hierarchy")

    products = tuple(
        tuple(
            _polynomial(
                (
                    (
                        _canonicalize(left + right)[1],
                        _canonicalize(left + right)[0],
                    ),
                )
            )
            for right in basis
        )
        for left in basis
    )
    objective_polynomial = _hamiltonian(size, detuning)
    support_rows = _support_rows(size, basis, localizer_sites)
    sandwich_rows = _sandwich_rows(
        size,
        safe_basis,
        localizer_sites,
    )
    registry_inputs = [
        polynomial
        for row in products
        for polynomial in row
    ]
    registry_inputs.append(objective_polynomial)
    registry_inputs.extend(row[3] for row in support_rows)
    registry_inputs.extend(row[3] for row in sandwich_rows)
    variables = _registry(size, registry_inputs)
    functional = _Functional(size, variables)
    gamma_complex, complement_complex = _normalized_matrices(
        size,
        products,
        functional,
    )
    gamma_real = _realify(gamma_complex)
    complement_real = _realify(complement_complex)
    kappa = _z_cycle_sum(size, set())
    gamma_complex_provenance = {
        "normalization": "Tr(Gamma)=2",
        "scale": "1/2",
    }
    complement_complex_provenance = {
        "normalization": "Tr(Pi_K-Gamma)=kappa_N-2",
        "scale": f"1/{kappa - 2}",
    }
    gamma_real_provenance = {
        **gamma_complex_provenance,
        "complex_dimension": len(gamma_complex),
        "realification": "[[Re,-Im],[Im,Re]]",
    }
    complement_real_provenance = {
        **complement_complex_provenance,
        "complex_dimension": len(complement_complex),
        "realification": "[[Re,-Im],[Im,Re]]",
    }
    complex_blocks = [
        _complex_block(
            "gamma",
            gamma_complex,
            gamma_complex_provenance,
        ),
        _complex_block(
            "blockade-complement",
            complement_complex,
            complement_complex_provenance,
        ),
    ]
    real_blocks = [
        _real_block("gamma", gamma_real, gamma_real_provenance),
        _real_block(
            "blockade-complement",
            complement_real,
            complement_real_provenance,
        ),
    ]
    objective = functional.polynomial(objective_polynomial)
    if not _fzero(objective[1]):
        _fail("independent objective is not real")
    normalization = {
        "identifier": "trace-gamma-equals-2",
        "form": _encode_form(_form()),
        "provenance": {
            "normalization": "ell(I)=2",
            "implementation": "identity moment eliminated exactly",
        },
    }
    sound_equalities = _localizer_equalities(
        functional,
        support_rows,
        sandwich_rows,
    )
    equalities = (
        [normalization, *sound_equalities]
        if localizer_mode == "sound"
        else [normalization]
    )
    witnesses = _magnitude_witnesses(variables, gamma_real)
    raw_variables = [
        {
            key: value
            for key, value in variable.items()
            if key != "representative_word"
        }
        for variable in variables
    ]
    affine_nonzero_count = (
        _affine_nonzeros(objective[0])
        + sum(
            (
                int(row["form"]["constant"] != "0/1")
                + len(row["form"]["terms"])
            )
            for row in equalities
        )
        + sum(
            _affine_nonzeros(entry)
            for block in (gamma_real, complement_real)
            for row in block
            for entry in row
        )
    )
    statistics = {
        "moment_word_count": len(basis),
        "moment_variable_count": len(variables),
        "equality_count": len(equalities),
        "support_localizer_count": (
            len(support_rows) if localizer_mode == "sound" else 0
        ),
        "safe_sandwich_count": (
            len(sandwich_rows) if localizer_mode == "sound" else 0
        ),
        "psd_block_dimensions": [
            len(gamma_real),
            len(complement_real),
        ],
        "largest_real_psd_dimension": len(gamma_real),
        "affine_nonzero_count": affine_nonzero_count,
        "bounded_variable_count": len(witnesses),
        "dense_psd_payload_bytes": (
            8 * len(gamma_real) ** 2
            + 8 * len(complement_real) ** 2
        ),
    }
    trace_words = sorted(
        {
            _canonicalize(left + right)[1]
            for left in basis
            for right in basis
        }
    )
    return {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "size": size,
        "detuning": _fraction_text(detuning),
        "hierarchy": hierarchy,
        "localizer_mode": localizer_mode,
        "moment_basis": [_encode_word(word_value) for word_value in basis],
        "safe_basis": [
            [[site, label] for site, label in word_value]
            for word_value in safe_basis
        ],
        "variables": raw_variables,
        "objective": _encode_form(objective[0]),
        "equalities": equalities,
        "psd_blocks": real_blocks,
        "unrealified_psd_blocks": complex_blocks,
        "magnitude_witnesses": witnesses,
        "clique_orbits": [
            [
                list(image)
                for image in _clique_orbit(
                    size,
                    0,
                    range_sites,
                )
            ]
        ],
        "clique_images": _clique_images(
            size,
            0,
            range_sites,
            moment_weight,
            image_localizer_representatives,
        ),
        "localizer_sites": list(localizer_sites),
        "constrained_trace_table": [
            {
                "word": _encode_word(word_value),
                "value": _pauli_trace(size, word_value),
            }
            for word_value in trace_words
        ],
        "provenance": {
            "boundary": "periodic",
            "local_state_convention": "0=down, 1=up",
            "symmetry": "D_N group-averaged effect, all physical sectors",
            "localizer_mode": localizer_mode,
            "identity_moment": "ell(I)=2 eliminated exactly",
        },
        "statistics": statistics,
    }


def _canonical_relation_table_json():
    local_products = {}
    for (left, right), (phase, result) in sorted(LOCAL_PRODUCT.items()):
        local_products[f"{left},{right}"] = {
            "phase": _encode_gaussian(phase),
            "result": result,
        }
    return json.dumps(
        {
            "definitions": {
                "P": "(I-Z)/2",
                "Y": "iXZ",
                "n": "(I+Z)/2",
            },
            "different_site": "commute",
            "local_products": local_products,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_json(path, component):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {component}: {error}") from error


def _exact_keys(value, expected, component):
    if not isinstance(value, dict):
        _fail(f"{component} must be a JSON object")
    actual = set(value)
    if actual != expected:
        _fail(
            f"{component} keys mismatch: "
            f"missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _verify_manifest(output_directory):
    manifest_path = output_directory / "manifest.json"
    manifest = _load_json(manifest_path, "manifest")
    _exact_keys(manifest, MANIFEST_KEYS, "manifest")
    expected = {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-effect-moment-problem",
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "symmetry": "D_N group-averaged effect, all physical sectors",
        "problem_file": "problem.json",
    }
    for key, value in expected.items():
        if manifest[key] != value:
            _fail(f"manifest {key} does not match the schema")
    problem_path = output_directory / manifest["problem_file"]
    try:
        problem_bytes = problem_path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read problem data: {error}") from error
    if (
        hashlib.sha256(problem_bytes).hexdigest()
        != manifest["problem_sha256"]
    ):
        _fail("problem SHA-256 does not match manifest")
    relation_hash = hashlib.sha256(
        _canonical_relation_table_json().encode("utf-8")
    ).hexdigest()
    if relation_hash != manifest["relation_table_sha256"]:
        _fail("relation-table SHA-256 does not match manifest")
    source_hashes = manifest["source_file_sha256"]
    if not isinstance(source_hashes, dict):
        _fail("manifest source_file_sha256 must be an object")
    if set(source_hashes) != SOURCE_PATHS:
        _fail("manifest source-file inventory mismatch")
    project_root = Path(__file__).resolve().parents[3]
    for relative in sorted(SOURCE_PATHS):
        actual = hashlib.sha256(
            (project_root / relative).read_bytes()
        ).hexdigest()
        if source_hashes[relative] != actual:
            _fail(f"source SHA-256 mismatch: {relative}")
    return manifest, problem_path


def _compare_equalities(actual, expected):
    if not isinstance(actual, list):
        _fail("equalities must be a list")
    actual_kinds = {
        row.get("provenance", {}).get("localizer_kind")
        for row in actual
        if isinstance(row, dict)
    }
    if "bare-pauli-sandwich" in actual_kinds:
        _fail("safe-sandwich localizer semantics were replaced")
    expected_right = {
        row["identifier"]
        for row in expected
        if row["provenance"].get("localizer_kind") == "right-support"
    }
    actual_ids = {
        row.get("identifier")
        for row in actual
        if isinstance(row, dict)
    }
    if not expected_right <= actual_ids:
        _fail("right-support localizer is missing")
    if actual != expected:
        _fail("localizer equality map mismatch")


def verify_kyfan_problem(output_directory) -> dict:
    """Rebuild the exact map without trusting the candidate implementation."""
    output_directory = Path(output_directory)
    manifest, problem_path = _verify_manifest(output_directory)
    payload = _load_json(problem_path, "problem")
    _exact_keys(payload, PROBLEM_KEYS, "problem")
    if payload["schema_version"] != 1:
        _fail("problem schema version mismatch")
    if payload["purpose"] != "finite-N-ky-fan-effect-moment-problem":
        _fail("problem purpose mismatch")
    size = payload["size"]
    if not isinstance(size, int) or size < 4:
        _fail("problem size must be an integer at least four")
    detuning = _parse_fraction(payload["detuning"], "detuning")
    hierarchy = payload["hierarchy"]
    localizer_mode = payload["localizer_mode"]
    if localizer_mode not in {"sound", "none"}:
        _fail("unknown localizer mode")
    if manifest["localizer_mode"] != localizer_mode:
        _fail("manifest localizer mode mismatch")

    expected = _expected_payload(
        size,
        detuning,
        hierarchy,
        localizer_mode,
    )
    for key in (
        "schema_version",
        "purpose",
        "size",
        "detuning",
        "hierarchy",
        "localizer_mode",
        "moment_basis",
        "safe_basis",
        "variables",
        "objective",
        "localizer_sites",
        "provenance",
        "statistics",
    ):
        if payload[key] != expected[key]:
            _fail(f"problem {key} does not match independent rebuild")
    if payload["constrained_trace_table"] != expected[
        "constrained_trace_table"
    ]:
        _fail("constrained trace table mismatch")
    if payload["unrealified_psd_blocks"] != expected[
        "unrealified_psd_blocks"
    ]:
        _fail("moment product or complex block mismatch")
    if payload["psd_blocks"] != expected["psd_blocks"]:
        _fail("realification mismatch")
    _compare_equalities(payload["equalities"], expected["equalities"])
    if payload["clique_orbits"] != expected["clique_orbits"]:
        _fail("clique orbit mismatch")
    if payload["clique_images"] != expected["clique_images"]:
        _fail("clique image map mismatch")
    if payload["magnitude_witnesses"] != expected[
        "magnitude_witnesses"
    ]:
        _fail("PSD magnitude witness inventory mismatch")
    return {
        "status": "verified",
        "size": size,
        "detuning": _fraction_text(detuning),
        "hierarchy": hierarchy,
        "sound_localizers": localizer_mode == "sound",
        "moment_variable_count": len(payload["variables"]),
        "largest_real_psd_dimension": payload["statistics"][
            "largest_real_psd_dimension"
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Independently verify a Ky Fan problem artifact."
    )
    parser.add_argument("output_directory")
    arguments = parser.parse_args(argv)
    try:
        summary = verify_kyfan_problem(arguments.output_directory)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
