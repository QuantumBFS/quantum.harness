"""Independent exact checker for schema-v2 Ky Fan solver reductions."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib
import json
import math
from pathlib import Path, PurePosixPath
import sys

_structure = importlib.import_module(
    "challenge233.sdp.verify_kyfan_structure"
)
_q = _structure._independent

REDUCTION_KEYS = {
    "schema_version",
    "purpose",
    "structure_sha256",
    "configuration",
    "conjugation",
    "quotient",
    "spatial",
    "equality",
    "selected_view",
    "psd_blocks",
    "objective_components",
    "statistics",
    "resource_estimate",
    "source_file_sha256",
}

MANIFEST_KEYS = {
    "schema_version",
    "purpose",
    "reduction_file",
    "reduction_sha256",
    "reduction_bytes",
    "structure_reference",
    "structure_sha256",
    "structure_manifest_reference",
    "structure_manifest_sha256",
}

SOURCE_PATHS = {
    "src/challenge233/sdp/exact_linalg.py",
    "src/challenge233/sdp/conjugation_reduction.py",
    "src/challenge233/sdp/blockade_quotient.py",
    "src/challenge233/sdp/equality_reduction.py",
    "src/challenge233/sdp/spatial_reduction.py",
    "src/challenge233/sdp/kyfan_presolve.py",
    "src/challenge233/sdp/kyfan_v2_artifact.py",
    "src/challenge233/sdp/verify_kyfan_structure.py",
    "src/challenge233/sdp/verify_kyfan_reduction.py",
}


def _fail(message):
    raise ValueError(message)


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


def _load_json(path, component):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {component}: {error}") from error


def _parse_fraction(value, component):
    return _structure._parse_fraction(value, component)


def _parse_gaussian(value, component):
    _exact_keys(value, {"real", "imag"}, component)
    return (
        _parse_fraction(value["real"], f"{component} real"),
        _parse_fraction(value["imag"], f"{component} imag"),
    )


def _parse_form(value, component):
    return _structure._parse_form(value, component)


def _gdiv(numerator, denominator):
    norm = denominator[0] ** 2 + denominator[1] ** 2
    if not norm:
        _fail("Gaussian quotient has a zero denominator")
    product = _q._gmul(numerator, _q._gconj(denominator))
    return (product[0] / norm, product[1] / norm)


def _gneg(value):
    return (-value[0], -value[1])


def _gzero(value):
    return value == _q.ZERO_G


def _gaxpy(target, source, coefficient):
    for coordinate, value in source.items():
        updated = _q._gadd(
            target.get(coordinate, _q.ZERO_G),
            _q._gmul(coefficient, value),
        )
        if _gzero(updated):
            target.pop(coordinate, None)
        else:
            target[coordinate] = updated


def _gscale(column, coefficient):
    return {
        coordinate: _q._gmul(coefficient, value)
        for coordinate, value in column.items()
        if not _gzero(_q._gmul(coefficient, value))
    }


def _column_basis(columns):
    pivot_rows = {}
    selected = []
    reconstructions = []
    for original_index, source in enumerate(columns):
        residual = dict(source)
        coefficients = {}
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            vector, representation = pivot_rows[pivot]
            factor = _gdiv(residual[pivot], vector[pivot])
            _gaxpy(residual, vector, _gneg(factor))
            _gaxpy(coefficients, representation, factor)
        if residual:
            pivot = min(residual)
            inverse = _gdiv(_q.ONE_G, residual[pivot])
            normalized = _gscale(residual, inverse)
            position = len(selected)
            representation = {position: inverse}
            _gaxpy(
                representation,
                coefficients,
                _gneg(inverse),
            )
            pivot_rows[pivot] = (normalized, representation)
            selected.append(original_index)
            reconstructions.append(((position, _q.ONE_G),))
        else:
            reconstructions.append(
                tuple(sorted(coefficients.items()))
            )
    selected_set = set(selected)
    kernel = []
    for index, terms in enumerate(reconstructions):
        if index in selected_set:
            continue
        relation = {index: _q.ONE_G}
        for position, coefficient in terms:
            selected_index = selected[position]
            _gaxpy(
                relation,
                {selected_index: _q.ONE_G},
                _gneg(coefficient),
            )
        kernel.append(tuple(sorted(relation.items())))
    return (
        tuple(selected),
        tuple(reconstructions),
        tuple(kernel),
    )


def _local_action(label, bit):
    if label == "X":
        return 1 - bit, _q.ONE_G
    if label == "Y":
        return 1 - bit, _q.POS_I_G if bit else _q.NEG_I_G
    if label == "Z":
        return bit, _q.ONE_G if bit else _q.NEG_ONE_G
    _fail("literal quotient action has an unknown Pauli label")


def _literal_action(word, state, sites):
    positions = {
        site: position for position, site in enumerate(sites)
    }
    output = state
    phase = _q.ONE_G
    for site, label in word:
        position = positions[site]
        bit = (output >> position) & 1
        output_bit, local_phase = _local_action(label, bit)
        if output_bit != bit:
            output ^= 1 << position
        phase = _q._gmul(phase, local_phase)
    return output, phase


def _periodic_legal(state, size):
    return all(
        not (
            (state >> site) & 1
            and (state >> ((site + 1) % size)) & 1
        )
        for site in range(size)
    )


def _open_legal(state, length):
    return all(
        not (
            (state >> site) & 1
            and (state >> (site + 1)) & 1
        )
        for site in range(length - 1)
    )


def _basis(structure):
    return tuple(
        _q._word(tuple((site, label) for site, label in word))
        for word in structure["moment_basis"]
    )


def _expected_quotient(structure):
    size = structure["size"]
    basis = _basis(structure)
    hierarchy = structure["hierarchy"]
    if hierarchy.startswith("global-d"):
        scope = "global"
        sites = tuple(range(size))
        legal = tuple(
            state
            for state in range(1 << size)
            if _periodic_legal(state, size)
        )
    else:
        try:
            width = _q.LEVELS[hierarchy][0]
        except KeyError as error:
            raise ValueError(
                "unknown hierarchy in reduction quotient"
            ) from error
        scope = "local"
        sites = tuple(range(width))
        legal = tuple(
            state
            for state in range(1 << width)
            if _open_legal(state, width)
        )
    columns = []
    for word in basis:
        column = {}
        for input_position, state in enumerate(legal):
            output, phase = _literal_action(word, state, sites)
            coordinate = output * len(legal) + input_position
            column[coordinate] = phase
        columns.append(column)
    selected, reconstruction, kernel = _column_basis(columns)
    return {
        "scope": scope,
        "sites": sites,
        "legal": legal,
        "output_count": 1 << len(sites),
        "selected": selected,
        "reconstruction": reconstruction,
        "kernel": kernel,
        "columns": tuple(columns),
    }


def _decode_relations(rows, component):
    if not isinstance(rows, list):
        _fail(f"{component} must be a list")
    result = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            _fail(f"{component} row must be a list")
        terms = []
        for item in row:
            if (
                not isinstance(item, list)
                or len(item) != 2
                or not isinstance(item[0], int)
            ):
                _fail(f"{component} term is malformed")
            terms.append(
                (
                    item[0],
                    _parse_gaussian(
                        item[1],
                        f"{component} coefficient",
                    ),
                )
            )
        if tuple(terms) != tuple(sorted(terms)):
            _fail(f"{component} row is not sorted")
        result.append(tuple(terms))
    return tuple(result)


def _verify_quotient(structure, payload):
    _exact_keys(
        payload,
        {
            "selected_indices",
            "reconstruction",
            "kernel",
            "legal_inputs",
            "output_count",
            "action_rank",
            "scope",
            "window_sites",
        },
        "quotient",
    )
    expected = _expected_quotient(structure)
    if tuple(payload["selected_indices"]) != expected["selected"]:
        _fail("quotient selected-column inventory mismatch")
    reconstruction = _decode_relations(
        payload["reconstruction"],
        "quotient reconstruction",
    )
    if reconstruction != expected["reconstruction"]:
        _fail("quotient reconstruction mismatch")
    kernel = _decode_relations(
        payload["kernel"],
        "quotient kernel",
    )
    if kernel != expected["kernel"]:
        _fail("quotient kernel mismatch")
    if tuple(payload["legal_inputs"]) != expected["legal"]:
        _fail("quotient legal-input domain mismatch")
    if payload["output_count"] != expected["output_count"]:
        _fail("quotient output domain mismatch")
    if payload["scope"] != expected["scope"]:
        _fail("quotient scope mismatch")
    if tuple(payload["window_sites"]) != expected["sites"]:
        _fail("quotient window mismatch")
    if payload["action_rank"] != len(expected["selected"]):
        _fail("quotient action rank mismatch")
    return expected


def _word_y_parity(word):
    return sum(label == "Y" for _, label in word) % 2


def _zero_form_variables(form, variables):
    variables = set(variables)
    return _q._form(
        form[0],
        (
            (variable, coefficient)
            for variable, coefficient in form[1]
            if variable not in variables
        ),
    )


def _phase(exponent):
    return (
        _q.ONE_G,
        _q.POS_I_G,
        _q.NEG_ONE_G,
        _q.NEG_I_G,
    )[exponent % 4]


def _expected_real_blocks(structure, phases, odd_variables):
    blocks = []
    for source in structure["psd_blocks"]:
        entries = {}
        for item in source["upper_entries"]:
            row = item["row"]
            column = item["column"]
            real = _parse_form(
                item["form"]["real"],
                "source real affine form",
            )
            imag = _parse_form(
                item["form"]["imag"],
                "source imaginary affine form",
            )
            gauged = _q._cscale(
                (real, imag),
                _phase(-phases[row] + phases[column]),
            )
            gauged = (
                _zero_form_variables(gauged[0], odd_variables),
                _zero_form_variables(gauged[1], odd_variables),
            )
            if not _q._fzero(gauged[1]):
                _fail("phase gauge did not make a source block real")
            if not _q._fzero(gauged[0]):
                entries[(row, column)] = gauged[0]
        blocks.append(
            {
                "identifier": source["identifier"],
                "dimension": source["dimension"],
                "entries": entries,
            }
        )
    return tuple(blocks)


def _verify_conjugation(structure, payload):
    _exact_keys(
        payload,
        {"phases", "odd_variables", "odd_equalities"},
        "conjugation",
    )
    basis = _basis(structure)
    phases = tuple(_word_y_parity(word) for word in basis)
    if tuple(payload["phases"]) != phases:
        _fail("conjugation phase inventory mismatch")
    odd_variables = tuple(
        variable["index"]
        for variable in structure["variables"]
        if _word_y_parity(
            _q._word(
                tuple(
                    (site, label)
                    for site, label in variable["representative"]
                )
            )
        )
    )
    if tuple(payload["odd_variables"]) != odd_variables:
        _fail("conjugation odd-Y variable inventory mismatch")
    expected_rows = []
    by_index = {
        variable["index"]: variable
        for variable in structure["variables"]
    }
    for index in odd_variables:
        expected_rows.append(
            {
                "identifier": f"conjugation-odd-y-{index}",
                "form": {
                    "constant": "0/1",
                    "terms": [[index, "1/1"]],
                },
                "provenance": {
                    "kind": "complex-conjugation",
                    "representative": by_index[index][
                        "representative"
                    ],
                },
            }
        )
    if payload["odd_equalities"] != expected_rows:
        _fail("conjugation odd-Y equality inventory mismatch")
    return (
        phases,
        odd_variables,
        _expected_real_blocks(
            structure,
            phases,
            odd_variables,
        ),
    )


def _act_site(element, site, size):
    shift, reflected = element
    return (shift + (-site if reflected else site)) % size


def _act_word(element, word, size):
    return tuple(
        sorted(
            (_act_site(element, site, size), label)
            for site, label in word
        )
    )


def _mat_identity(dimension):
    return tuple(
        tuple(Fraction(int(row == column)) for column in range(dimension))
        for row in range(dimension)
    )


def _mat_add(*terms):
    coefficient, first = terms[0]
    rows = len(first)
    columns = len(first[0]) if rows else 0
    return tuple(
        tuple(
            sum(
                Fraction(weight) * matrix[row][column]
                for weight, matrix in terms
            )
            for column in range(columns)
        )
        for row in range(rows)
    )


def _mat_mul(left, right):
    rows = len(left)
    middle = len(right)
    columns = len(right[0]) if middle else 0
    return tuple(
        tuple(
            sum(
                left[row][index] * right[index][column]
                for index in range(middle)
            )
            for column in range(columns)
        )
        for row in range(rows)
    )


def _rational_column_basis(matrix):
    if not matrix:
        return ()
    rows = len(matrix)
    columns = len(matrix[0])
    pivot_rows = {}
    selected = []
    for column in range(columns):
        residual = {
            row: matrix[row][column]
            for row in range(rows)
            if matrix[row][column]
        }
        for pivot in sorted(pivot_rows):
            if pivot not in residual:
                continue
            vector = pivot_rows[pivot]
            factor = residual[pivot] / vector[pivot]
            for row, value in vector.items():
                updated = residual.get(row, Fraction(0)) - factor * value
                if updated:
                    residual[row] = updated
                else:
                    residual.pop(row, None)
        if residual:
            pivot = min(residual)
            inverse = Fraction(1, 1) / residual[pivot]
            pivot_rows[pivot] = {
                row: inverse * value
                for row, value in residual.items()
            }
            selected.append(column)
    return tuple(selected)


def _matrix_image(matrix):
    selected = _rational_column_basis(matrix)
    return tuple(
        tuple(matrix[row][column] for column in selected)
        for row in range(len(matrix))
    )


def _induced_action(
    element,
    structure,
    quotient,
    phases,
):
    basis = _basis(structure)
    indices = {word: index for index, word in enumerate(basis)}
    selected = quotient["selected"]
    rank = len(selected)
    result = [
        [Fraction(0) for _ in range(rank)]
        for _ in range(rank)
    ]
    size = structure["size"]
    for source_position, source_index in enumerate(selected):
        image = _act_word(element, basis[source_index], size)
        try:
            image_index = indices[image]
        except KeyError as error:
            raise ValueError(
                "basis is not closed under spatial action"
            ) from error
        for target_position, coefficient in (
            quotient["reconstruction"][image_index]
        ):
            target_index = selected[target_position]
            gauged = _q._gmul(
                coefficient,
                _phase(
                    phases[source_index]
                    - phases[target_index]
                ),
            )
            if gauged[1]:
                _fail("induced spatial action remained complex")
            result[target_position][source_position] += gauged[0]
    return tuple(tuple(row) for row in result)


def _transform_payload(matrix, selected_indices, full_dimension):
    rows = len(matrix)
    columns = len(matrix[0]) if rows else 0
    entries = []
    for row in range(rows):
        for column in range(columns):
            if matrix[row][column]:
                entries.append(
                    [
                        selected_indices[row],
                        column,
                        _q._fraction_text(matrix[row][column]),
                    ]
                )
    return {
        "rows": full_dimension,
        "columns": columns,
        "entries": entries,
    }


def _expected_spatial(structure, quotient, phases):
    size = structure["size"]
    rank = len(quotient["selected"])
    identity = _mat_identity(rank)
    full_dimension = len(structure["moment_basis"])
    if quotient["scope"] == "global":
        if size != 4:
            _fail("global reduction is not the N=4 anchor")
        group = tuple(
            (shift, reflected)
            for reflected in (False, True)
            for shift in range(4)
        )
        translation = _induced_action(
            (1, False), structure, quotient, phases
        )
        translation_squared = _induced_action(
            (2, False), structure, quotient, phases
        )
        translation_cubed = _induced_action(
            (3, False), structure, quotient, phases
        )
        reflection = _induced_action(
            (0, True), structure, quotient, phases
        )
        blocks = []
        for label, translation_sign, reflection_sign in (
            ("k0+", 1, 1),
            ("k0-", 1, -1),
            ("kpi+", -1, 1),
            ("kpi-", -1, -1),
        ):
            momentum = _mat_add(
                (Fraction(1, 4), identity),
                (Fraction(translation_sign, 4), translation),
                (Fraction(1, 4), translation_squared),
                (
                    Fraction(translation_sign, 4),
                    translation_cubed,
                ),
            )
            parity = _mat_add(
                (Fraction(1, 2), identity),
                (Fraction(reflection_sign, 2), reflection),
            )
            image = _matrix_image(_mat_mul(momentum, parity))
            blocks.append(
                (
                    f"global-d4-{label}",
                    label,
                    1,
                    image,
                    group,
                    {
                        "scope": "global",
                        "projector": (
                            "1/4(I+tT+T^2+tT^3)"
                            " 1/2(I+rR)"
                        ),
                        "translation_sign": translation_sign,
                        "reflection_sign": reflection_sign,
                    },
                )
            )
        generic = _mat_mul(
            _mat_add(
                (Fraction(1, 2), identity),
                (Fraction(-1, 2), translation_squared),
            ),
            _mat_add(
                (Fraction(1, 2), identity),
                (Fraction(1, 2), reflection),
            ),
        )
        blocks.append(
            (
                "global-d4-generic-k1-k3",
                "generic-k1-k3",
                2,
                _matrix_image(generic),
                group,
                {
                    "scope": "global",
                    "projector": "1/4(I-T^2)(I+R)",
                    "carrier": (
                        "reflection-even multiplicity slice"
                    ),
                },
            )
        )
    else:
        window = quotient["sites"]
        stabilizer = ((window[0] + window[-1]) % size, True)
        group = ((0, False), stabilizer)
        reflection = _induced_action(
            stabilizer,
            structure,
            quotient,
            phases,
        )
        blocks = []
        for label, sign in (
            ("reflection-even", 1),
            ("reflection-odd", -1),
        ):
            projector = _mat_add(
                (Fraction(1, 2), identity),
                (Fraction(sign, 2), reflection),
            )
            blocks.append(
                (
                    f"local-{label}",
                    label,
                    1,
                    _matrix_image(projector),
                    group,
                    {
                        "scope": "local-window-stabilizer",
                        "window_sites": list(window),
                        "stabilizer": {
                            "shift": stabilizer[0],
                            "reflected": True,
                        },
                        "projector": (
                            "1/2(I+R_window)"
                            if sign == 1
                            else "1/2(I-R_window)"
                        ),
                    },
                )
            )
    return tuple(
        {
            "identifier": identifier,
            "irrep_label": label,
            "irrep_degree": degree,
            "dimension": len(matrix[0]) if matrix else 0,
            "transform": _transform_payload(
                matrix,
                quotient["selected"],
                full_dimension,
            ),
            "internal_group": [
                {"shift": shift, "reflected": reflected}
                for shift, reflected in group
            ],
            "provenance": {
                **provenance,
                "transform_codomain": (
                    "phase-gauged-full-test-index-basis"
                ),
                "quotient_selected_indices": list(
                    quotient["selected"]
                ),
            },
        }
        for (
            identifier,
            label,
            degree,
            matrix,
            group,
            provenance,
        ) in blocks
    )


def _verify_spatial(structure, quotient, phases, payload):
    if not isinstance(payload, list):
        _fail("spatial inventory must be a list")
    expected = _expected_spatial(
        structure,
        quotient,
        phases,
    )
    if len(payload) != len(expected):
        _fail("spatial block inventory mismatch")
    matrices = []
    degree_sum = 0
    for actual, reference in zip(payload, expected):
        _exact_keys(
            actual,
            {
                "identifier",
                "irrep_label",
                "irrep_degree",
                "dimension",
                "transform",
                "internal_group",
                "provenance",
            },
            "spatial block",
        )
        for key in (
            "identifier",
            "irrep_label",
            "irrep_degree",
            "dimension",
            "transform",
            "internal_group",
            "provenance",
        ):
            if actual[key] != reference[key]:
                _fail(f"spatial block {key} mismatch")
        transform = actual["transform"]
        matrix = [
            [Fraction(0) for _ in range(transform["columns"])]
            for _ in range(transform["rows"])
        ]
        for row, column, value in transform["entries"]:
            matrix[row][column] = _parse_fraction(
                value,
                "spatial transform coefficient",
            )
        matrices.append(tuple(tuple(row) for row in matrix))
        degree_sum += actual["irrep_degree"] * actual["dimension"]
    if degree_sum != len(quotient["selected"]):
        _fail("spatial degree-weighted dimension sum mismatch")
    return tuple(matrices)


def _functional(structure):
    variables = [
        {
            "index": variable["index"],
            "representative_word": _q._word(
                tuple(
                    (site, label)
                    for site, label in variable["representative"]
                )
            ),
        }
        for variable in structure["variables"]
    ]
    return _q._Functional(structure["size"], variables)


def _kernel_rows(structure, quotient):
    basis = _basis(structure)
    functional = _functional(structure)
    rows = []
    for kernel_index, relation in enumerate(quotient["kernel"]):
        kernel = _q._polynomial(
            tuple(
                (basis[index], coefficient)
                for index, coefficient in relation
            )
        )
        relation_provenance = [
            [
                index,
                {
                    "real": _q._fraction_text(coefficient[0]),
                    "imag": _q._fraction_text(coefficient[1]),
                },
            ]
            for index, coefficient in relation
        ]
        for left_position, left_index in enumerate(
            quotient["selected"]
        ):
            left = _q._poly_adjoint(
                _q._word_polynomial(basis[left_index])
            )
            value = functional.polynomial(
                _q._poly_multiply(left, kernel)
            )
            prefix = (
                "blockade-right-ideal-localizer"
                f"-kernel-{kernel_index}"
                f"-left-{left_position}"
            )
            provenance = {
                "localizer_kind": "blockade-right-ideal",
                "kernel_index": kernel_index,
                "left_selected_position": left_position,
                "left_basis_index": left_index,
                "kernel_relation": relation_provenance,
            }
            if not _q._fzero(value[0]):
                rows.append(
                    {
                        "identifier": f"{prefix}-real",
                        "form": _q._encode_form(value[0]),
                        "provenance": {
                            **provenance,
                            "component": "real",
                        },
                    }
                )
            if not _q._fzero(value[1]):
                rows.append(
                    {
                        "identifier": f"{prefix}-imag",
                        "form": _q._encode_form(value[1]),
                        "provenance": {
                            **provenance,
                            "component": "imag",
                        },
                    }
                )
    return tuple(rows)


def _source_equalities(structure, conjugation, quotient):
    return (
        *structure["equalities"],
        *conjugation["odd_equalities"],
        *_kernel_rows(structure, quotient),
    )


def _row_values(form, variable_count):
    coefficients = dict(form[1])
    return (
        form[0],
        *(
            coefficients.get(index, Fraction(0))
            for index in range(variable_count)
        ),
    )


def _row_rank(rows):
    pivots = {}
    rank = 0
    for row in rows:
        residual = {
            index: value
            for index, value in enumerate(row)
            if value
        }
        for pivot in sorted(pivots):
            if pivot in residual:
                factor = residual[pivot]
                for index, value in pivots[pivot].items():
                    updated = (
                        residual.get(index, Fraction(0))
                        - factor * value
                    )
                    if updated:
                        residual[index] = updated
                    else:
                        residual.pop(index, None)
        if residual:
            pivot = min(residual)
            inverse = Fraction(1, 1) / residual[pivot]
            pivots[pivot] = {
                index: inverse * value
                for index, value in residual.items()
            }
            rank += 1
    return rank


def _primitive_row(values):
    denominator = math.lcm(
        *(value.denominator for value in values),
        1,
    )
    integers = tuple(
        value.numerator * (denominator // value.denominator)
        for value in values
    )
    divisor = math.gcd(*(abs(value) for value in integers), 0)
    if not divisor:
        return integers, Fraction(1)
    primitive = tuple(value // divisor for value in integers)
    scale = Fraction(divisor, denominator)
    if next(value for value in primitive if value) < 0:
        primitive = tuple(-value for value in primitive)
        scale = -scale
    return primitive, scale


def _primitive_hash(primitive):
    return hashlib.sha256(
        json.dumps(
            list(primitive),
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _parse_sparse_pairs(value, component):
    if not isinstance(value, list):
        _fail(f"{component} must be a list")
    result = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], int)
        ):
            _fail(f"{component} term is malformed")
        result.append(
            (
                item[0],
                _parse_fraction(item[1], f"{component} value"),
            )
        )
    if tuple(result) != tuple(sorted(result)):
        _fail(f"{component} must be sorted")
    return tuple(result)


def _parse_parameterization(payload):
    _exact_keys(
        payload,
        {
            "offset",
            "nullspace",
            "free_variables",
            "affine_nonzeros",
        },
        "equality parameterization",
    )
    offset = _parse_sparse_pairs(
        payload["offset"],
        "equality offset",
    )
    nullspace = tuple(
        _parse_sparse_pairs(
            column,
            "equality nullspace column",
        )
        for column in payload["nullspace"]
    )
    free = tuple(payload["free_variables"])
    if len(nullspace) != len(free):
        _fail("equality nullspace/free-variable count mismatch")
    if payload["affine_nonzeros"] != (
        len(offset) + sum(len(column) for column in nullspace)
    ):
        _fail("equality parameterization nonzero count mismatch")
    return offset, nullspace, free


def _substitute_form(form, parameterization, selected_view):
    if selected_view == "row-reduced":
        return form
    offset, nullspace, _ = parameterization
    offset = dict(offset)
    columns = tuple(dict(column) for column in nullspace)
    coefficients = dict(form[1])
    constant = form[0] + sum(
        coefficient * offset.get(variable, Fraction(0))
        for variable, coefficient in coefficients.items()
    )
    terms = []
    for position, column in enumerate(columns):
        value = sum(
            coefficient * column.get(variable, Fraction(0))
            for variable, coefficient in coefficients.items()
        )
        if value:
            terms.append((position, value))
    return _q._form(constant, terms)


def _verify_equality(
    structure,
    conjugation,
    quotient,
    payload,
):
    _exact_keys(
        payload,
        {
            "kept_rows",
            "kept_identifiers",
            "duplicate_map",
            "span_map",
            "pivot_columns",
            "row_rank",
            "parameterization",
            "selected_view",
            "statistics",
        },
        "equality reduction",
    )
    source = _source_equalities(
        structure,
        conjugation,
        quotient,
    )
    by_identifier = {
        row["identifier"]: row for row in source
    }
    kept_identifiers = tuple(payload["kept_identifiers"])
    if len(set(kept_identifiers)) != len(kept_identifiers):
        _fail("equality kept identifiers are not unique")
    try:
        expected_kept = [
            by_identifier[identifier]
            for identifier in kept_identifiers
        ]
    except KeyError as error:
        raise ValueError(
            "equality kept identifier is not a source row"
        ) from error
    if payload["kept_rows"] != expected_kept:
        _fail("equality kept-row payload mismatch")
    variable_count = len(structure["variables"])
    forms = {
        identifier: _parse_form(
            row["form"],
            f"equality row {identifier}",
        )
        for identifier, row in by_identifier.items()
    }
    rows = {
        identifier: _row_values(form, variable_count)
        for identifier, form in forms.items()
    }
    kept_rows = [rows[identifier] for identifier in kept_identifiers]
    if _row_rank(kept_rows) != len(kept_rows):
        _fail("equality kept rows are not independent")
    if _row_rank(tuple(rows.values())) != len(kept_rows):
        _fail("equality kept rows do not have full row rank")
    if payload["row_rank"] != len(kept_rows):
        _fail("equality row rank mismatch")
    span_map = payload["span_map"]
    if set(span_map) != set(rows):
        _fail("equality span-map identifier inventory mismatch")
    for identifier, source_row in rows.items():
        reconstructed = [Fraction(0) for _ in source_row]
        terms = span_map[identifier]
        if not isinstance(terms, list):
            _fail("equality span-map row must be a list")
        for item in terms:
            if (
                not isinstance(item, list)
                or len(item) != 2
                or item[0] not in set(kept_identifiers)
            ):
                _fail("equality span-map term is malformed")
            coefficient = _parse_fraction(
                item[1],
                "equality span-map coefficient",
            )
            kept = rows[item[0]]
            reconstructed = [
                left + coefficient * right
                for left, right in zip(reconstructed, kept)
            ]
        if tuple(reconstructed) != source_row:
            _fail("equality span-map reconstruction mismatch")
    parameterization = _parse_parameterization(
        payload["parameterization"]
    )
    offset, nullspace, free = parameterization
    if tuple(payload["pivot_columns"]) != tuple(
        sorted(set(payload["pivot_columns"]))
    ):
        _fail("equality pivot columns are not unique and sorted")
    if len(payload["pivot_columns"]) != len(kept_rows):
        _fail("equality pivot-column count mismatch")
    if set(payload["pivot_columns"]) | set(free) != set(
        range(variable_count)
    ):
        _fail("equality pivot/free partition mismatch")
    offset_map = dict(offset)
    nullspace_maps = tuple(dict(column) for column in nullspace)
    for form in forms.values():
        constant = form[0] + sum(
            coefficient * offset_map.get(variable, Fraction(0))
            for variable, coefficient in form[1]
        )
        if constant:
            _fail("equality parameterization offset mismatch")
        for column in nullspace_maps:
            value = sum(
                coefficient * column.get(variable, Fraction(0))
                for variable, coefficient in form[1]
            )
            if value:
                _fail("equality parameterization nullspace mismatch")
    if payload["selected_view"] not in {
        "row-reduced",
        "parameterized",
    }:
        _fail("unknown selected equality view")
    if payload["statistics"].get("all_identifiers") != list(
        rows
    ):
        _fail("equality source identifier inventory mismatch")
    statistics = payload["statistics"]
    primitive_first = {}
    primitive_scales = {}
    primitive_hashes = {}
    expected_duplicate = {}
    for source_row in source:
        identifier = source_row["identifier"]
        primitive, scale = _primitive_row(rows[identifier])
        primitive_scales[identifier] = _q._fraction_text(scale)
        primitive_hashes[identifier] = _primitive_hash(primitive)
        if not any(primitive):
            continue
        if primitive in primitive_first:
            kept_identifier, kept_scale = primitive_first[primitive]
            expected_duplicate[identifier] = {
                "kept_identifier": kept_identifier,
                "scale_to_kept": _q._fraction_text(
                    scale / kept_scale
                ),
                "provenance": source_row["provenance"],
            }
        else:
            primitive_first[primitive] = (identifier, scale)
    if payload["duplicate_map"] != expected_duplicate:
        _fail("equality duplicate map mismatch")
    expected_basic_statistics = {
        "original_row_count": len(source),
        "unique_primitive_row_count": len(primitive_first),
        "parameterization_input_row_count": len(kept_rows),
        "row_rank": len(kept_rows),
        "free_variable_count": len(free),
        "fill_cap": "2/1",
        "primitive_scales": primitive_scales,
        "canonical_row_sha256": primitive_hashes,
        "row_provenance": {
            row["identifier"]: row["provenance"]
            for row in source
        },
        "all_identifiers": list(rows),
    }
    for key, value in expected_basic_statistics.items():
        if statistics.get(key) != value:
            _fail(f"equality {key} statistic mismatch")
    if statistics.get("modular_primes") != [
        2305843009213693951,
        2305843009213693921,
    ]:
        _fail("equality modular-prime inventory mismatch")
    if not isinstance(
        statistics.get("used_modular_fallback"),
        bool,
    ):
        _fail("equality modular fallback flag is malformed")
    if (
        not isinstance(statistics.get("max_bit_length"), int)
        or statistics["max_bit_length"] < 0
    ):
        _fail("equality maximum bit length is malformed")
    return (
        parameterization,
        payload["selected_view"],
        forms,
    )


def _congruence(source, transform):
    columns = [
        {
            row: transform[row][column]
            for row in range(len(transform))
            if transform[row][column]
        }
        for column in range(len(transform[0]) if transform else 0)
    ]
    result = {}
    for row in range(len(columns)):
        for column in range(row, len(columns)):
            form = _q._form()
            for source_row, left in columns[row].items():
                for source_column, right in columns[column].items():
                    coordinate = tuple(
                        sorted((source_row, source_column))
                    )
                    if coordinate in source["entries"]:
                        form = _q._fadd(
                            form,
                            _q._fscale(
                                source["entries"][coordinate],
                                left * right,
                            ),
                        )
            if not _q._fzero(form):
                result[(row, column)] = form
    return result


def _parse_reduced_blocks(payload):
    result = []
    for block in payload:
        _exact_keys(
            block,
            {
                "identifier",
                "dimension",
                "source_block",
                "spatial_block",
                "upper_entries",
            },
            "reduced PSD block",
        )
        entries = {}
        coordinates = []
        for entry in block["upper_entries"]:
            _exact_keys(
                entry,
                {"row", "column", "form"},
                "reduced PSD entry",
            )
            coordinate = (entry["row"], entry["column"])
            if (
                not 0 <= coordinate[0] <= coordinate[1]
                < block["dimension"]
            ):
                _fail("reduced PSD coordinate is outside upper triangle")
            coordinates.append(coordinate)
            entries[coordinate] = _parse_form(
                entry["form"],
                "reduced PSD affine form",
            )
        if coordinates != sorted(set(coordinates)):
            _fail("reduced PSD coordinates are not unique and sorted")
        result.append({**block, "entries": entries})
    return tuple(result)


def _verify_reduced_affine(
    structure,
    real_blocks,
    spatial_payload,
    spatial_matrices,
    equality_payload,
    payload,
):
    parameterization, selected_view, _ = _verify_equality(
        structure,
        {
            "odd_equalities": equality_payload[
                "_odd_equalities"
            ]
        },
        equality_payload["_quotient"],
        equality_payload["payload"],
    )
    actual = _parse_reduced_blocks(payload)
    expected_count = len(real_blocks) * len(spatial_matrices)
    if len(actual) != expected_count:
        _fail("reduced PSD block inventory mismatch")
    index = 0
    unreduced_forms = []
    for source in real_blocks:
        for spatial_block, transform in zip(
            spatial_payload,
            spatial_matrices,
        ):
            block = actual[index]
            expected_identifier = (
                f"{source['identifier']}::"
                f"{spatial_block['identifier']}"
            )
            if (
                block["identifier"] != expected_identifier
                or block["source_block"] != source["identifier"]
                or block["spatial_block"]
                != spatial_block["identifier"]
                or block["dimension"]
                != spatial_block["dimension"]
            ):
                _fail("reduced PSD block metadata mismatch")
            raw_entries = _congruence(source, transform)
            unreduced_forms.extend(raw_entries.values())
            expected_entries = {
                coordinate: _substitute_form(
                    form,
                    parameterization,
                    selected_view,
                )
                for coordinate, form in raw_entries.items()
            }
            expected_entries = {
                coordinate: form
                for coordinate, form in expected_entries.items()
                if not _q._fzero(form)
            }
            if block["entries"] != expected_entries:
                _fail("reduced PSD affine congruence mismatch")
            index += 1
    source_objective = {
        identifier: _parse_form(
            form,
            f"source objective component {identifier}",
        )
        for identifier, form in (
            structure["objective_components"].items()
        )
    }
    unreduced_forms.extend(source_objective.values())
    expected_objective = {
        identifier: _substitute_form(
            form,
            parameterization,
            selected_view,
        )
        for identifier, form in source_objective.items()
    }
    statistics = equality_payload["payload"]["statistics"]
    row_reduced_nnz = sum(
        int(form[0] != 0) + len(form[1])
        for form in unreduced_forms
    )
    parameterized_forms = tuple(
        _substitute_form(
            form,
            parameterization,
            "parameterized",
        )
        for form in unreduced_forms
    )
    parameterized_nnz = sum(
        int(form[0] != 0) + len(form[1])
        for form in parameterized_forms
    )
    variable_count = len(structure["variables"])
    row_rank = equality_payload["payload"]["row_rank"]
    free_count = len(parameterization[2])
    row_kkt = (
        (variable_count + row_rank) ** 2
        + row_reduced_nnz
    )
    parameterized_kkt = free_count**2 + parameterized_nnz
    within_fill = parameterized_nnz <= 2 * row_reduced_nnz
    lower_kkt = parameterized_kkt < row_kkt
    expected_view = (
        "parameterized"
        if within_fill and lower_kkt
        else "row-reduced"
    )
    expected_reason = (
        "parameterized-within-fill-cap-and-lower-kkt-proxy"
        if expected_view == "parameterized"
        else (
            "parameterized-fill-exceeds-cap"
            if not within_fill
            else "parameterized-kkt-proxy-not-lower"
        )
    )
    expected_affine_statistics = {
        "row_reduced_affine_nonzeros": row_reduced_nnz,
        "parameterized_affine_nonzeros": parameterized_nnz,
        "row_reduced_kkt_proxy": row_kkt,
        "parameterized_kkt_proxy": parameterized_kkt,
        "selection_reason": expected_reason,
    }
    for key, value in expected_affine_statistics.items():
        if statistics.get(key) != value:
            _fail(f"equality {key} statistic mismatch")
    if selected_view != expected_view:
        _fail("equality selected view mismatch")
    return actual, expected_objective, parameterization, selected_view


def _slater_check(structure, quotient, phases):
    basis = _basis(structure)
    selected = tuple(
        basis[index] for index in quotient["selected"]
    )
    kappa = _q._z_cycle_sum(structure["size"], set())
    matrix = []
    for left in selected:
        row = []
        for right in selected:
            product = _q._poly_multiply(
                _q._poly_adjoint(_q._word_polynomial(left)),
                _q._word_polynomial(right),
            )
            trace = _q._poly_trace(structure["size"], product)
            phase = _phase(
                -_word_y_parity(left) + _word_y_parity(right)
            )
            gauged = _q._gmul(phase, trace)
            if gauged[1]:
                _fail("phase-gauged Slater Gram is not real")
            row.append(gauged[0] / kappa)
        matrix.append(row)
    lower = [
        [Fraction(int(row == column)) for column in range(len(matrix))]
        for row in range(len(matrix))
    ]
    diagonal = []
    for column in range(len(matrix)):
        pivot = matrix[column][column] - sum(
            lower[column][prior] ** 2 * diagonal[prior]
            for prior in range(column)
        )
        if pivot <= 0:
            _fail("Slater Gram is not positive definite")
        diagonal.append(pivot)
        for row in range(column + 1, len(matrix)):
            lower[row][column] = (
                matrix[row][column]
                - sum(
                    lower[row][prior]
                    * lower[column][prior]
                    * diagonal[prior]
                    for prior in range(column)
                )
            ) / pivot
    return tuple(diagonal)


def _verify_sources(payload):
    if not isinstance(payload, dict) or set(payload) != SOURCE_PATHS:
        _fail("reduction source-file inventory mismatch")
    root = Path(__file__).resolve().parents[3]
    for relative in sorted(SOURCE_PATHS):
        digest = hashlib.sha256(
            (root / relative).read_bytes()
        ).hexdigest()
        if payload[relative] != digest:
            _fail(f"reduction source SHA-256 mismatch: {relative}")


def _verify_resource(payload, blocks, serialized_bytes):
    _exact_keys(
        payload,
        {
            "clarabel_hs_bytes",
            "estimated_rss_bytes",
            "requires_wall_benchmark",
        },
        "resource estimate",
    )
    hs = sum(
        8 * (block["dimension"] * (block["dimension"] + 1) // 2) ** 2
        for block in blocks
    )
    if payload["clarabel_hs_bytes"] != hs:
        _fail("Clarabel Hs resource estimate mismatch")
    if payload["estimated_rss_bytes"] != (
        8 * hs + 2 * serialized_bytes + (1 << 30)
    ):
        _fail("reduced RSS resource estimate mismatch")
    if payload["requires_wall_benchmark"] is not True:
        _fail("reduction must require a wall benchmark")


def _verify_statistics(
    payload,
    structure,
    quotient,
    spatial,
    equality,
    selected_view,
    blocks,
    objective,
):
    parameterization = equality["parameterization"]
    expected = {
        "original_test_dimension": len(
            structure["moment_basis"]
        ),
        "quotient_action_rank": len(quotient["selected"]),
        "spatial_dimensions": [
            {
                "identifier": block["identifier"],
                "irrep_degree": block["irrep_degree"],
                "dimension": block["dimension"],
            }
            for block in spatial
        ],
        "original_variable_count": len(structure["variables"]),
        "solver_variable_count": (
            len(parameterization["free_variables"])
            if selected_view == "parameterized"
            else len(structure["variables"])
        ),
        "equality_row_rank": equality["row_rank"],
        "reduced_psd_nonzeros": sum(
            len(block["entries"]) for block in blocks
        ),
        "objective_nonzeros": sum(
            int(form[0] != 0) + len(form[1])
            for form in objective.values()
        ),
    }
    if payload != expected:
        _fail("reduction statistics mismatch")


def _load_binding(directory):
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    manifest = _load_json(manifest_path, "reduction manifest")
    _exact_keys(manifest, MANIFEST_KEYS, "reduction manifest")
    expected = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-solver-reduction",
        "reduction_file": "solver-reduction.json",
    }
    for key, value in expected.items():
        if manifest[key] != value:
            _fail(f"reduction manifest {key} mismatch")
    reduction_path = directory / manifest["reduction_file"]
    reduction_bytes = reduction_path.read_bytes()
    if len(reduction_bytes) != manifest["reduction_bytes"]:
        _fail("reduction byte-count binding mismatch")
    reduction_sha256 = hashlib.sha256(reduction_bytes).hexdigest()
    if reduction_sha256 != manifest["reduction_sha256"]:
        _fail("reduction SHA-256 binding mismatch")
    run_root = directory.resolve().parents[2]
    structure_path = _structure.resolve_bound_path(
        manifest_path,
        manifest["structure_reference"],
        run_root,
    )
    structure_manifest_path = _structure.resolve_bound_path(
        manifest_path,
        manifest["structure_manifest_reference"],
        run_root,
    )
    structure_manifest_bytes = structure_manifest_path.read_bytes()
    if hashlib.sha256(structure_manifest_bytes).hexdigest() != (
        manifest["structure_manifest_sha256"]
    ):
        _fail("structure manifest SHA-256 binding mismatch")
    structure_bytes = structure_path.read_bytes()
    structure_sha256 = hashlib.sha256(structure_bytes).hexdigest()
    if structure_sha256 != manifest["structure_sha256"]:
        _fail("reduction structure SHA-256 binding mismatch")
    _structure.verify_kyfan_structure(structure_path.parent)
    return (
        manifest,
        reduction_bytes,
        json.loads(reduction_bytes.decode("utf-8")),
        json.loads(structure_bytes.decode("utf-8")),
        reduction_sha256,
        structure_sha256,
    )


def _resolve_reduction_directory(problem_directory):
    path = Path(problem_directory)
    if (path / "solver-reduction.json").is_file():
        return path, None
    manifest_path = path / "manifest.json"
    manifest = _load_json(manifest_path, "cell manifest")
    required = {
        "reduction_reference",
        "reduction_sha256",
        "reduction_manifest_reference",
        "reduction_manifest_sha256",
    }
    if not required <= set(manifest):
        _fail("cell manifest has no solver reduction binding")
    reference = manifest["reduction_reference"]
    manifest_reference = manifest["reduction_manifest_reference"]
    for value, component in (
        (reference, "reduction reference"),
        (manifest_reference, "reduction manifest reference"),
    ):
        if (
            not isinstance(value, str)
            or not value
            or "\\"
            in value
            or PurePosixPath(value).is_absolute()
            or any(
                part in {"", "."}
                for part in PurePosixPath(value).parts
            )
            or PurePosixPath(value).as_posix() != value
        ):
            _fail(f"{component} is not normalized and relative")
    reduction_path = (
        manifest_path.parent
        / Path(*PurePosixPath(reference).parts)
    ).resolve()
    reduction_manifest_path = (
        manifest_path.parent
        / Path(*PurePosixPath(manifest_reference).parts)
    ).resolve()
    if (
        reduction_path.name != "solver-reduction.json"
        or reduction_manifest_path.name != "manifest.json"
        or reduction_path.parent != reduction_manifest_path.parent
    ):
        _fail("cell reduction references do not share one directory")
    reduction_bytes = reduction_path.read_bytes()
    if hashlib.sha256(reduction_bytes).hexdigest() != (
        manifest["reduction_sha256"]
    ):
        _fail("cell reduction SHA-256 binding mismatch")
    reduction_manifest_bytes = reduction_manifest_path.read_bytes()
    if hashlib.sha256(reduction_manifest_bytes).hexdigest() != (
        manifest["reduction_manifest_sha256"]
    ):
        _fail("cell reduction manifest SHA-256 binding mismatch")
    return reduction_path.parent, manifest


def verify_kyfan_reduction(problem_directory) -> dict:
    """Independently rebuild and verify one exact reduction artifact."""
    reduction_directory, cell_manifest = (
        _resolve_reduction_directory(problem_directory)
    )
    (
        manifest,
        reduction_bytes,
        payload,
        structure,
        reduction_sha256,
        structure_sha256,
    ) = _load_binding(reduction_directory)
    if cell_manifest is not None:
        cell_summary = _structure.verify_bound_kyfan_structure(
            problem_directory,
            reduction_directory.resolve().parents[2],
        )
        if cell_manifest["reduction_sha256"] != reduction_sha256:
            _fail("cell and shared reduction SHA-256 differ")
        if cell_manifest.get("structure_sha256") != structure_sha256:
            _fail("cell and reduction structure SHA-256 differ")
        if cell_summary.get("reduction_sha256") != reduction_sha256:
            _fail("cell reduction binding did not verify")
    _exact_keys(payload, REDUCTION_KEYS, "solver reduction")
    if payload["schema_version"] != 2:
        _fail("solver reduction schema version mismatch")
    if payload["purpose"] != "finite-N-ky-fan-solver-reduction":
        _fail("solver reduction purpose mismatch")
    if payload["structure_sha256"] != structure_sha256:
        _fail("solver reduction structure SHA-256 mismatch")
    expected_configuration = {
        "composition_order": [
            "logical-sparse-structure",
            "complex-conjugation-real-gauge",
            "blockade-action-quotient",
            "internal-spatial-blocks",
            "exact-equality-compression",
            "selected-equality-view",
            "sparse-reduced-affine-triplets",
        ],
        "equality_fill_cap": "2/1",
    }
    if payload["configuration"] != expected_configuration:
        _fail("solver reduction configuration mismatch")

    phases, odd_variables, real_blocks = _verify_conjugation(
        structure,
        payload["conjugation"],
    )
    quotient = _verify_quotient(
        structure,
        payload["quotient"],
    )
    _slater_check(structure, quotient, phases)
    spatial_matrices = _verify_spatial(
        structure,
        quotient,
        phases,
        payload["spatial"],
    )
    equality_context = {
        "payload": payload["equality"],
        "_odd_equalities": payload["conjugation"][
            "odd_equalities"
        ],
        "_quotient": quotient,
    }
    blocks, expected_objective, _, selected_view = (
        _verify_reduced_affine(
            structure,
            real_blocks,
            payload["spatial"],
            spatial_matrices,
            equality_context,
            payload["psd_blocks"],
        )
    )
    if payload["selected_view"] != selected_view:
        _fail("selected equality view binding mismatch")
    actual_objective = {
        identifier: _parse_form(
            form,
            f"reduced objective component {identifier}",
        )
        for identifier, form in (
            payload["objective_components"].items()
        )
    }
    if actual_objective != expected_objective:
        _fail("reduced objective component mismatch")
    _verify_statistics(
        payload["statistics"],
        structure,
        quotient,
        payload["spatial"],
        payload["equality"],
        selected_view,
        blocks,
        actual_objective,
    )
    _verify_resource(
        payload["resource_estimate"],
        blocks,
        len(reduction_bytes),
    )
    _verify_sources(payload["source_file_sha256"])
    return {
        "status": "verified",
        "structure_sha256": structure_sha256,
        "reduction_sha256": reduction_sha256,
        "selected_view": selected_view,
        "quotient_action_rank": len(quotient["selected"]),
        "slater_rank": len(quotient["selected"]),
        "reduced_psd_dimensions": [
            block["dimension"] for block in blocks
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify a schema-v2 Ky Fan solver reduction."
        )
    )
    parser.add_argument("problem_directory")
    arguments = parser.parse_args(argv)
    try:
        summary = verify_kyfan_reduction(
            arguments.problem_directory
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
