"""Independent exact checker for schema-v2 sparse Ky Fan structures."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import sys


_independent = importlib.import_module(
    "challenge233.sdp.verify_kyfan_problem"
)

STRUCTURE_KEYS = {
    "schema_version",
    "purpose",
    "size",
    "hierarchy",
    "localizer_mode",
    "moment_basis",
    "safe_basis",
    "variables",
    "objective_components",
    "equalities",
    "psd_blocks",
    "magnitude_witnesses",
    "clique_orbits",
    "clique_images",
    "localizer_sites",
    "constrained_trace_table",
    "blockade_action_table",
    "provenance",
    "statistics",
}

SHARED_MANIFEST_KEYS = {
    "schema_version",
    "purpose",
    "structure_file",
    "structure_sha256",
    "structure_bytes",
    "relation_table_sha256",
    "source_file_sha256",
}

CELL_MANIFEST_KEYS = {
    "schema_version",
    "purpose",
    "instance_file",
    "instance_sha256",
    "structure_reference",
    "structure_sha256",
    "structure_manifest_reference",
    "structure_manifest_sha256",
}

CELL_REDUCTION_BINDING_KEYS = CELL_MANIFEST_KEYS | {
    "reduction_reference",
    "reduction_sha256",
    "reduction_manifest_reference",
    "reduction_manifest_sha256",
}

INSTANCE_KEYS = {
    "schema_version",
    "purpose",
    "structure_sha256",
    "detuning",
    "objective",
    "physical_contract",
    "trial_manifest_sha256",
}

SOURCE_PATHS = {
    "src/challenge233/sdp/algebra.py",
    "src/challenge233/sdp/constraints.py",
    "src/challenge233/sdp/localizers.py",
    "src/challenge233/sdp/constrained_trace.py",
    "src/challenge233/sdp/hierarchy.py",
    "src/challenge233/sdp/kyfan.py",
    "src/challenge233/sdp/kyfan_sparse.py",
    "src/challenge233/sdp/kyfan_v2_artifact.py",
    "src/challenge233/sdp/verify_kyfan_problem.py",
    "src/challenge233/sdp/verify_kyfan_structure.py",
}


def _fail(message):
    raise ValueError(message)


_VERIFIED_STRUCTURE_SUMMARIES = {}


def _canonical_json_bytes(payload) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


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


def _fraction_text(value):
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _parse_fraction(value, component):
    return _independent._parse_fraction(value, component)


def _encode_polynomial(polynomial):
    return [
        {
            "word": _independent._encode_word(word_value),
            "coefficient": _independent._encode_gaussian(coefficient),
        }
        for word_value, coefficient in polynomial
    ]


def _encode_trace_table(trace_values):
    rows = [
        {
            "polynomial": _encode_polynomial(polynomial),
            "value": _independent._encode_gaussian(value),
        }
        for polynomial, value in trace_values.items()
    ]
    return sorted(rows, key=_canonical_json_bytes)


def _basis_contract(size, hierarchy):
    if hierarchy.startswith("global-d"):
        try:
            moment_weight = int(hierarchy.removeprefix("global-d"))
        except ValueError as error:
            raise ValueError("unknown global hierarchy") from error
        if moment_weight < 0:
            _fail("global moment weight must be nonnegative")
        range_sites = size
        safe_depth = 1
        basis = _independent._pauli_basis(
            range(size),
            moment_weight,
        )
        safe_basis = _independent._safe_basis(
            size,
            0,
            range_sites,
            safe_depth,
        )
        localizer_sites = tuple(range(size))
        image_localizer_sites = (
            _independent._representative_localizer_sites(
                size,
                0,
                range_sites,
            )
        )
    elif hierarchy in _independent.LEVELS:
        range_sites, moment_weight, safe_depth = (
            _independent.LEVELS[hierarchy]
        )
        basis = _independent._pauli_basis(
            _independent._window(size, 0, range_sites),
            moment_weight,
        )
        safe_basis = _independent._safe_basis(
            size,
            0,
            range_sites,
            safe_depth,
        )
        localizer_sites = (
            _independent._representative_localizer_sites(
                size,
                0,
                range_sites,
            )
        )
        image_localizer_sites = localizer_sites
    else:
        _fail("unknown Ky Fan hierarchy")
    return (
        range_sites,
        moment_weight,
        basis,
        safe_basis,
        localizer_sites,
        image_localizer_sites,
    )


def _moment_product(left, right):
    phase, word_value = _independent._canonicalize(left + right)
    return _independent._polynomial(((word_value, phase),))


def _complex_affine_nonzeros(value):
    return (
        _independent._affine_nonzeros(value[0])
        + _independent._affine_nonzeros(value[1])
    )


def _sparse_blocks_and_traces(
    size,
    basis,
    products,
    functional,
):
    kappa = _independent._z_cycle_sum(size, set())
    gamma_entries = []
    complement_entries = []
    trace_values = {}
    gamma_forms = {}
    for row, column, polynomial in products:
        ell = functional.polynomial(polynomial)
        trace = trace_values.setdefault(
            polynomial,
            _independent._poly_trace(size, polynomial),
        )
        gamma = _independent._cscale(
            ell,
            (Fraction(1, 2), Fraction(0)),
        )
        complement = _independent._cadd(
            _independent._cscale(
                _independent._cconstant(trace),
                (Fraction(1, kappa - 2), Fraction(0)),
            ),
            _independent._cscale(
                ell,
                (Fraction(-1, kappa - 2), Fraction(0)),
            ),
        )
        if row == column and (
            not _independent._fzero(gamma[1])
            or not _independent._fzero(complement[1])
        ):
            _fail("independent Hermitian diagonal is not real")
        gamma_forms[(row, column)] = gamma
        if not _independent._czero(gamma):
            gamma_entries.append(
                {
                    "row": row,
                    "column": column,
                    "form": _independent._encode_cform(gamma),
                }
            )
        if not _independent._czero(complement):
            complement_entries.append(
                {
                    "row": row,
                    "column": column,
                    "form": _independent._encode_cform(complement),
                }
            )
    blocks = [
        {
            "identifier": "gamma",
            "dimension": len(basis),
            "upper_entries": gamma_entries,
            "provenance": {
                "normalization": "Tr(Gamma)=2",
                "scale": "1/2",
            },
        },
        {
            "identifier": "blockade-complement",
            "dimension": len(basis),
            "upper_entries": complement_entries,
            "provenance": {
                "normalization": "Tr(Pi_K-Gamma)=kappa_N-2",
                "scale": f"1/{kappa - 2}",
            },
        },
    ]
    return blocks, gamma_forms, _encode_trace_table(trace_values)


def _sparse_magnitude_witnesses(variables, gamma_forms, dimension):
    unit = _independent._cform(
        _independent._form(Fraction(1)),
    )
    unit_diagonal = {
        row
        for row in range(dimension)
        if gamma_forms.get((row, row)) == unit
    }
    coordinates = {}
    for (row, column), value in gamma_forms.items():
        if row == column:
            continue
        real, imag = value
        if (
            row not in unit_diagonal
            or column not in unit_diagonal
            or real[0]
            or imag[0]
        ):
            continue
        indices = {
            variable
            for variable, _ in real[1] + imag[1]
        }
        if len(indices) != 1:
            continue
        variable = next(iter(indices))
        real_coefficient = dict(real[1]).get(
            variable,
            Fraction(0),
        )
        imag_coefficient = dict(imag[1]).get(
            variable,
            Fraction(0),
        )
        if (
            real_coefficient**2 + imag_coefficient**2
            != Fraction(1, 4)
        ):
            continue
        coordinates.setdefault(
            variable,
            (
                row,
                column,
                (2 * real_coefficient, 2 * imag_coefficient),
            ),
        )
    witnesses = []
    for variable in variables:
        index = variable["index"]
        if index not in coordinates:
            _fail("independent PSD magnitude witness is missing")
        row, column, phase = coordinates[index]
        witnesses.append(
            {
                "variable": index,
                "block": "gamma",
                "row": row,
                "column": column,
                "phase": _independent._encode_gaussian(phase),
                "bound": "2/1",
            }
        )
    return witnesses


def _blockade_action_table(size):
    return {
        "state_encoding": "bit i is site i; 0=down, 1=up",
        "periodic_constraint": "n_i n_{i+1}=0 including wrap bond",
        "periodic_legal_state_count": (
            _independent._z_cycle_sum(size, set())
        ),
        "local_projectors": {
            "P": [
                {"input": 0, "value": "1/1"},
                {"input": 1, "value": "0/1"},
            ],
            "n": [
                {"input": 0, "value": "0/1"},
                {"input": 1, "value": "1/1"},
            ],
            "Z": [
                {"input": 0, "value": "-1/1"},
                {"input": 1, "value": "1/1"},
            ],
        },
        "local_pauli_action": [
            {
                "label": label,
                "input": bit,
                "output": output,
                "phase": {"real": real, "imag": imag},
            }
            for label, bit, output, real, imag in (
                ("X", 0, 1, "1/1", "0/1"),
                ("X", 1, 0, "1/1", "0/1"),
                ("Y", 0, 1, "0/1", "-1/1"),
                ("Y", 1, 0, "0/1", "1/1"),
                ("Z", 0, 0, "-1/1", "0/1"),
                ("Z", 1, 1, "1/1", "0/1"),
            )
        ],
    }


def _expected_payload(size, hierarchy, localizer_mode):
    (
        range_sites,
        moment_weight,
        basis,
        safe_basis,
        localizer_sites,
        image_localizer_sites,
    ) = _basis_contract(size, hierarchy)
    products = tuple(
        (
            row,
            column,
            _moment_product(basis[row], basis[column]),
        )
        for row in range(len(basis))
        for column in range(row, len(basis))
    )
    h_rabi = _independent._hamiltonian(size, Fraction(0))
    h_at_one = _independent._hamiltonian(size, Fraction(1))
    minus_number = _independent._poly_add(
        h_at_one,
        _independent._poly_scale(
            _independent.NEG_ONE_G,
            h_rabi,
        ),
    )
    support_rows = _independent._support_rows(
        size,
        basis,
        localizer_sites,
    )
    sandwich_rows = _independent._sandwich_rows(
        size,
        safe_basis,
        localizer_sites,
    )
    registry_inputs = [
        polynomial
        for _, _, polynomial in products
    ]
    registry_inputs.extend((h_rabi, minus_number))
    registry_inputs.extend(row[3] for row in support_rows)
    registry_inputs.extend(row[3] for row in sandwich_rows)
    variables = _independent._registry(size, registry_inputs)
    functional = _independent._Functional(size, variables)
    blocks, gamma_forms, trace_table = _sparse_blocks_and_traces(
        size,
        basis,
        products,
        functional,
    )
    objective_components = {}
    for identifier, polynomial in (
        ("rabi", h_rabi),
        ("minus-number", minus_number),
    ):
        value = functional.polynomial(polynomial)
        if not _independent._fzero(value[1]):
            _fail("independent objective component is not real")
        objective_components[identifier] = (
            _independent._encode_form(value[0])
        )
    normalization = {
        "identifier": "trace-gamma-equals-2",
        "form": _independent._encode_form(
            _independent._form()
        ),
        "provenance": {
            "normalization": "ell(I)=2",
            "implementation": "identity moment eliminated exactly",
        },
    }
    sound_equalities = _independent._localizer_equalities(
        functional,
        support_rows,
        sandwich_rows,
    )
    equalities = (
        [normalization, *sound_equalities]
        if localizer_mode == "sound"
        else [normalization]
    )
    raw_variables = [
        {
            key: value
            for key, value in variable.items()
            if key != "representative_word"
        }
        for variable in variables
    ]
    witnesses = _sparse_magnitude_witnesses(
        variables,
        gamma_forms,
        len(basis),
    )
    entry_count = sum(
        len(block["upper_entries"]) for block in blocks
    )
    affine_nonzeros = (
        sum(
            _independent._affine_nonzeros(
                functional.polynomial(polynomial)[0]
            )
            for polynomial in (h_rabi, minus_number)
        )
        + sum(
            int(row["form"]["constant"] != "0/1")
            + len(row["form"]["terms"])
            for row in equalities
        )
        + sum(
            _complex_affine_nonzeros(gamma_forms[
                (entry["row"], entry["column"])
            ])
            if block["identifier"] == "gamma"
            else (
                int(entry["form"]["real"]["constant"] != "0/1")
                + len(entry["form"]["real"]["terms"])
                + int(entry["form"]["imag"]["constant"] != "0/1")
                + len(entry["form"]["imag"]["terms"])
            )
            for block in blocks
            for entry in block["upper_entries"]
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
        "complex_psd_block_dimensions": [
            len(basis),
            len(basis),
        ],
        "stored_complex_upper_entry_count": entry_count,
        "affine_nonzero_count": affine_nonzeros,
        "bounded_variable_count": len(witnesses),
        "sparse_payload_coordinate_bytes": 24 * entry_count,
    }
    return {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-effect-moment-structure",
        "size": size,
        "hierarchy": hierarchy,
        "localizer_mode": localizer_mode,
        "moment_basis": [
            _independent._encode_word(word_value)
            for word_value in basis
        ],
        "safe_basis": [
            [[site, label] for site, label in word_value]
            for word_value in safe_basis
        ],
        "variables": raw_variables,
        "objective_components": objective_components,
        "equalities": equalities,
        "psd_blocks": blocks,
        "magnitude_witnesses": witnesses,
        "clique_orbits": [
            [
                list(image)
                for image in _independent._clique_orbit(
                    size,
                    0,
                    range_sites,
                )
            ]
        ],
        "clique_images": _independent._clique_images(
            size,
            0,
            range_sites,
            moment_weight,
            image_localizer_sites,
        ),
        "localizer_sites": list(localizer_sites),
        "constrained_trace_table": trace_table,
        "blockade_action_table": _blockade_action_table(size),
        "provenance": {
            "boundary": "periodic",
            "local_state_convention": "0=down, 1=up",
            "symmetry": "D_N group-averaged effect, all physical sectors",
            "localizer_mode": localizer_mode,
            "identity_moment": "ell(I)=2 eliminated exactly",
            "storage": "complex sparse upper triangle",
        },
        "statistics": statistics,
    }


def _validate_sparse_coordinates(payload):
    blocks = payload.get("psd_blocks")
    if not isinstance(blocks, list):
        _fail("psd_blocks must be a list")
    for block in blocks:
        if not isinstance(block, dict):
            _fail("PSD block must be an object")
        entries = block.get("upper_entries")
        if not isinstance(entries, list):
            _fail("PSD upper_entries must be a list")
        coordinates = []
        for entry in entries:
            if not isinstance(entry, dict):
                _fail("sparse entry must be an object")
            row = entry.get("row")
            column = entry.get("column")
            if (
                not isinstance(row, int)
                or not isinstance(column, int)
                or row < 0
                or column < 0
                or row > column
            ):
                _fail("sparse coordinate is outside the upper triangle")
            coordinates.append((row, column))
        if len(coordinates) != len(set(coordinates)):
            _fail("duplicate sparse coordinate")
        if coordinates != sorted(coordinates):
            _fail("sparse coordinates are not sorted")


def _compare_equalities(actual, expected):
    actual_ids = {
        row.get("identifier")
        for row in actual
        if isinstance(row, dict)
    }
    expected_right = {
        row["identifier"]
        for row in expected
        if row["provenance"].get("localizer_kind")
        == "right-support"
    }
    if not expected_right <= actual_ids:
        _fail("right-support localizer is missing")
    if actual != expected:
        _fail("localizer equality map mismatch")


def validate_structure_payload(payload) -> dict:
    """Rebuild every logical field without importing candidate builders."""
    _exact_keys(payload, STRUCTURE_KEYS, "structure")
    if payload["schema_version"] != 2:
        _fail("structure schema version mismatch")
    if (
        payload["purpose"]
        != "finite-N-ky-fan-effect-moment-structure"
    ):
        _fail("structure purpose mismatch")
    size = payload["size"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 4:
        _fail("structure size must be an integer at least four")
    hierarchy = payload["hierarchy"]
    if not isinstance(hierarchy, str):
        _fail("structure hierarchy must be a string")
    localizer_mode = payload["localizer_mode"]
    if localizer_mode not in {"sound", "none"}:
        _fail("unknown localizer mode")
    _validate_sparse_coordinates(payload)

    expected = _expected_payload(size, hierarchy, localizer_mode)
    for key in (
        "schema_version",
        "purpose",
        "size",
        "hierarchy",
        "localizer_mode",
        "moment_basis",
        "safe_basis",
        "variables",
        "objective_components",
        "localizer_sites",
        "blockade_action_table",
        "provenance",
        "statistics",
    ):
        if payload[key] != expected[key]:
            _fail(f"structure {key} does not match independent rebuild")
    if payload["constrained_trace_table"] != expected[
        "constrained_trace_table"
    ]:
        _fail("constrained trace table mismatch")
    if payload["psd_blocks"] != expected["psd_blocks"]:
        _fail("moment product or sparse complex block mismatch")
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
        "hierarchy": hierarchy,
        "sound_localizers": localizer_mode == "sound",
        "moment_variable_count": len(payload["variables"]),
        "complex_psd_dimensions": [
            block["dimension"] for block in payload["psd_blocks"]
        ],
    }


def _verify_shared_manifest(directory):
    manifest_path = directory / "manifest.json"
    manifest = _load_json(manifest_path, "shared manifest")
    _exact_keys(
        manifest,
        SHARED_MANIFEST_KEYS,
        "shared manifest",
    )
    expected_header = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-shared-structure",
        "structure_file": "structure.json",
    }
    for key, value in expected_header.items():
        if manifest[key] != value:
            _fail(f"shared manifest {key} mismatch")
    structure_path = directory / manifest["structure_file"]
    try:
        structure_bytes = structure_path.read_bytes()
    except OSError as error:
        raise ValueError(
            f"cannot read shared structure: {error}"
        ) from error
    if len(structure_bytes) != manifest["structure_bytes"]:
        _fail("shared manifest structure byte count mismatch")
    digest = hashlib.sha256(structure_bytes).hexdigest()
    if digest != manifest["structure_sha256"]:
        _fail("shared manifest structure SHA-256 mismatch")
    if directory.name != digest:
        _fail("content-addressed structure directory mismatch")
    relation_hash = hashlib.sha256(
        _independent._canonical_relation_table_json().encode("utf-8")
    ).hexdigest()
    if manifest["relation_table_sha256"] != relation_hash:
        _fail("shared manifest relation-table SHA-256 mismatch")
    source_hashes = manifest["source_file_sha256"]
    if not isinstance(source_hashes, dict):
        _fail("shared manifest source hashes must be an object")
    if set(source_hashes) != SOURCE_PATHS:
        _fail("shared manifest source-file inventory mismatch")
    project_root = Path(__file__).resolve().parents[3]
    for relative in sorted(SOURCE_PATHS):
        digest = hashlib.sha256(
            (project_root / relative).read_bytes()
        ).hexdigest()
        if source_hashes[relative] != digest:
            _fail(f"shared manifest source SHA-256 mismatch: {relative}")
    return manifest, structure_path


def verify_kyfan_structure(path) -> dict:
    """Verify a structure file or its content-addressed directory."""
    path = Path(path)
    if path.is_dir():
        _, structure_path = _verify_shared_manifest(path)
    else:
        structure_path = path
    try:
        structure_bytes = structure_path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read structure: {error}") from error
    digest = hashlib.sha256(structure_bytes).hexdigest()
    cached = _VERIFIED_STRUCTURE_SUMMARIES.get(digest)
    if cached is not None:
        return dict(cached)
    try:
        payload = json.loads(structure_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid structure JSON") from error
    summary = validate_structure_payload(payload)
    _VERIFIED_STRUCTURE_SUMMARIES[digest] = dict(summary)
    return summary


def resolve_bound_path(manifest_path, relative, run_root) -> Path:
    """Resolve one normalized relative reference inside a run directory."""
    manifest_path = Path(manifest_path)
    root = Path(run_root).resolve()
    if not isinstance(relative, str) or not relative:
        _fail("artifact reference must be a non-empty string")
    if "\\" in relative or PurePosixPath(relative).is_absolute():
        _fail("artifact reference must be normalized and relative")
    pure_reference = PurePosixPath(relative)
    parts = pure_reference.parts
    if any(part in {"", "."} for part in parts):
        _fail("artifact reference must be normalized and relative")
    if pure_reference.as_posix() != relative:
        _fail("artifact reference must be normalized and relative")
    candidate = (
        manifest_path.parent / Path(*parts)
    ).resolve()
    if candidate != root and root not in candidate.parents:
        _fail("artifact reference escapes the run directory")
    return candidate


def _parse_form(payload, component):
    _exact_keys(payload, {"constant", "terms"}, component)
    constant = _parse_fraction(payload["constant"], f"{component} constant")
    terms = payload["terms"]
    if not isinstance(terms, list):
        _fail(f"{component} terms must be a list")
    parsed = []
    for item in terms:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], int)
        ):
            _fail(f"{component} term is malformed")
        parsed.append(
            (
                item[0],
                _parse_fraction(
                    item[1],
                    f"{component} coefficient",
                ),
            )
        )
    if tuple(parsed) != tuple(sorted(parsed)):
        _fail(f"{component} terms are not sorted")
    return _independent._form(constant, parsed)


def _physical_contract(structure, detuning):
    return {
        "hamiltonian": (
            "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
            "-delta sum_i n_i"
        ),
        "rabi_coefficient": "1/1",
        "detuning": _fraction_text(detuning),
        "detuning_sign": "-delta",
        "projectors": {
            "P": "|0><0|=(I-Z)/2",
            "n": "|1><1|=(I+Z)/2",
        },
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "blockade_constraint": (
            "n_i n_{i+1}=0 including wrap bond"
        ),
        "symmetry_sector": "full constrained Hilbert space",
        "target_gap": "E_1-E_0 with multiplicity, all momenta",
        "size": structure["size"],
        "hierarchy": structure["hierarchy"],
        "localizer_mode": structure["localizer_mode"],
    }


def _validate_instance_payload(payload, structure, structure_sha256):
    _exact_keys(payload, INSTANCE_KEYS, "instance")
    if payload["schema_version"] != 2:
        _fail("instance schema version mismatch")
    if (
        payload["purpose"]
        != "finite-N-ky-fan-effect-moment-instance"
    ):
        _fail("instance purpose mismatch")
    if payload["structure_sha256"] != structure_sha256:
        _fail("instance structure SHA-256 mismatch")
    detuning = _parse_fraction(payload["detuning"], "detuning")
    if not Fraction(0) <= detuning <= Fraction(3):
        _fail("instance detuning lies outside [0,3]")
    rabi = _parse_form(
        structure["objective_components"]["rabi"],
        "rabi objective component",
    )
    minus_number = _parse_form(
        structure["objective_components"]["minus-number"],
        "minus-number objective component",
    )
    expected_objective = _independent._fadd(
        rabi,
        _independent._fscale(minus_number, detuning),
    )
    if payload["objective"] != _independent._encode_form(
        expected_objective
    ):
        _fail("instance objective overlay mismatch")
    if payload["physical_contract"] != _physical_contract(
        structure,
        detuning,
    ):
        _fail("instance physical contract mismatch")
    trial_hash = payload["trial_manifest_sha256"]
    if trial_hash is not None and (
        not isinstance(trial_hash, str)
        or len(trial_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in trial_hash
        )
    ):
        _fail("instance trial manifest hash is not a SHA-256")
    return detuning


def verify_bound_kyfan_structure(
    problem_directory,
    run_root,
) -> dict:
    """Verify a cell instance and both hashes of its shared structure."""
    problem_directory = Path(problem_directory)
    manifest_path = problem_directory / "manifest.json"
    manifest = _load_json(manifest_path, "cell manifest")
    manifest_keys = frozenset(manifest)
    if manifest_keys not in {
        frozenset(CELL_MANIFEST_KEYS),
        frozenset(CELL_REDUCTION_BINDING_KEYS),
    }:
        _fail(
            "cell manifest keys mismatch for structure-only "
            "or structure-reduction binding"
        )
    expected_header = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-instance-binding",
        "instance_file": "instance.json",
    }
    for key, value in expected_header.items():
        if manifest[key] != value:
            _fail(f"cell manifest {key} mismatch")

    structure_path = resolve_bound_path(
        manifest_path,
        manifest["structure_reference"],
        run_root,
    )
    shared_manifest_path = resolve_bound_path(
        manifest_path,
        manifest["structure_manifest_reference"],
        run_root,
    )
    if structure_path.parent != shared_manifest_path.parent:
        _fail("shared structure and manifest directories differ")
    shared_manifest_bytes = shared_manifest_path.read_bytes()
    if hashlib.sha256(shared_manifest_bytes).hexdigest() != (
        manifest["structure_manifest_sha256"]
    ):
        _fail("shared manifest SHA-256 binding mismatch")
    shared_manifest = _load_json(
        shared_manifest_path,
        "shared manifest",
    )
    if shared_manifest.get("structure_sha256") != (
        manifest["structure_sha256"]
    ):
        _fail("shared manifest structure SHA-256 binding mismatch")
    summary = verify_kyfan_structure(structure_path.parent)
    structure_bytes = structure_path.read_bytes()
    structure_sha256 = hashlib.sha256(structure_bytes).hexdigest()
    if structure_sha256 != manifest["structure_sha256"]:
        _fail("cell structure SHA-256 binding mismatch")
    structure_payload = json.loads(structure_bytes.decode("utf-8"))

    instance_path = resolve_bound_path(
        manifest_path,
        manifest["instance_file"],
        run_root,
    )
    if instance_path.parent != problem_directory.resolve():
        _fail("instance artifact reference leaves problem directory")
    instance_bytes = instance_path.read_bytes()
    if hashlib.sha256(instance_bytes).hexdigest() != (
        manifest["instance_sha256"]
    ):
        _fail("instance SHA-256 binding mismatch")
    instance = json.loads(instance_bytes.decode("utf-8"))
    detuning = _validate_instance_payload(
        instance,
        structure_payload,
        structure_sha256,
    )
    result = {
        **summary,
        "detuning": _fraction_text(detuning),
        "structure_sha256": structure_sha256,
        "instance_sha256": manifest["instance_sha256"],
    }
    if manifest_keys == frozenset(CELL_REDUCTION_BINDING_KEYS):
        reduction_path = resolve_bound_path(
            manifest_path,
            manifest["reduction_reference"],
            run_root,
        )
        reduction_manifest_path = resolve_bound_path(
            manifest_path,
            manifest["reduction_manifest_reference"],
            run_root,
        )
        if reduction_path.parent != reduction_manifest_path.parent:
            _fail("reduction and reduction manifest directories differ")
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
        reduction_manifest = json.loads(
            reduction_manifest_bytes.decode("utf-8")
        )
        if reduction_manifest.get("structure_sha256") != (
            structure_sha256
        ):
            _fail("cell reduction structure SHA-256 binding mismatch")
        if reduction_manifest.get("reduction_sha256") != (
            manifest["reduction_sha256"]
        ):
            _fail("cell reduction manifest hash binding mismatch")
        result["reduction_sha256"] = manifest["reduction_sha256"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Independently verify a schema-v2 Ky Fan structure."
    )
    parser.add_argument("path")
    parser.add_argument("--run-root")
    arguments = parser.parse_args(argv)
    try:
        if arguments.run_root is None:
            summary = verify_kyfan_structure(arguments.path)
        else:
            summary = verify_bound_kyfan_structure(
                arguments.path,
                arguments.run_root,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
