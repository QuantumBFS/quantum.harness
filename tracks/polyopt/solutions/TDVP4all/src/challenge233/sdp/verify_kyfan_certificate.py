"""Independent exact checker for finite-N Ky Fan gap certificates."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct

from challenge233.sdp.verify_kyfan_problem import verify_kyfan_problem


CERTIFICATE_PURPOSE = "finite-N-ky-fan-gap-certificate"
TRIAL_PURPOSE = "finite-N-pxp-variational-upper-bound"


def _solver_seed_accuracy(result) -> str:
    statuses = (
        result.get("termination_status"),
        result.get("primal_status"),
        result.get("dual_status"),
    )
    if statuses == (
        "OPTIMAL",
        "FEASIBLE_POINT",
        "FEASIBLE_POINT",
    ):
        return "full"
    if statuses != (
        "ALMOST_OPTIMAL",
        "NEARLY_FEASIBLE_POINT",
        "NEARLY_FEASIBLE_POINT",
    ):
        raise ValueError("unexpected solver status combination")
    if result.get("raw_status") != "ALMOST_SOLVED":
        raise ValueError("reduced-accuracy seed has unexpected raw status")
    diagnostics = result.get("numerical_diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("reduced-accuracy seed lacks diagnostics")
    if (
        diagnostics.get("has_values") is not True
        or diagnostics.get("has_duals") is not True
    ):
        raise ValueError("reduced-accuracy seed lacks primal or dual data")
    for key in (
        "res_primal",
        "res_dual",
        "gap_abs",
        "gap_rel",
        "ktratio",
    ):
        try:
            value = float(diagnostics[key])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"invalid reduced-accuracy diagnostic {key}"
            ) from error
        if not math.isfinite(value) or value < 0:
            raise ValueError(
                f"invalid reduced-accuracy diagnostic {key}"
            )
    return "reduced"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"missing JSON artifact: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON artifact: {path}") from error


def _parse_fraction(value) -> Fraction:
    if not isinstance(value, str):
        raise TypeError("exact value must be a fraction string")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"invalid exact fraction: {value}") from error


def _encode_fraction(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _safe_file(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError("artifact file must be a basename")
    return directory / name


def _verify_file(
    directory: Path,
    metadata,
    *,
    size_field="byte_count",
):
    path = _safe_file(directory, metadata["file"])
    if not path.is_file():
        raise FileNotFoundError(f"missing artifact file: {path}")
    if size_field in metadata and path.stat().st_size != int(
        metadata[size_field]
    ):
        raise ValueError(f"artifact byte count mismatch: {path.name}")
    if _sha256_file(path) != metadata["sha256"]:
        raise ValueError(f"artifact SHA-256 mismatch: {path.name}")
    return path


def _resolve_certificate_directory(cell_directory: Path) -> Path:
    direct = cell_directory / "certificate.json"
    nested = cell_directory / "certificate/certificate.json"
    if direct.is_file():
        return cell_directory
    if nested.is_file():
        return cell_directory / "certificate"
    raise FileNotFoundError("cannot locate certificate.json")


def _periodic_legal(size: int, state: int) -> bool:
    return all(
        not (
            (state >> site) & 1
            and (state >> ((site + 1) % size)) & 1
        )
        for site in range(size)
    )


def _periodic_dimension(size: int) -> int:
    previous, current = 2, 1
    for _ in range(size):
        previous, current = current, previous + current
    return previous


def _exact_rayleigh(size, detuning, states, coefficients):
    if not 4 <= size <= 20:
        raise ValueError("trial size lies outside the finite-N contract")
    if len(states) != len(coefficients) or not states:
        raise ValueError("trial integer arrays are misaligned or empty")
    coefficient_by_state = {}
    for state, coefficient in zip(states, coefficients):
        if not 0 <= state < (1 << size):
            raise ValueError("trial state is outside the declared size")
        if not _periodic_legal(size, state):
            raise ValueError("trial contains an illegal periodic state")
        if state in coefficient_by_state:
            raise ValueError("trial contains a duplicate state")
        coefficient_by_state[state] = coefficient
    denominator = sum(value * value for value in coefficients)
    if denominator == 0:
        raise ValueError("trial vector is zero")
    rabi = 0
    occupation = 0
    for state, coefficient in coefficient_by_state.items():
        occupation += (
            bin(state).count("1") * coefficient * coefficient
        )
        for site in range(size):
            rabi += (
                coefficient
                * coefficient_by_state.get(state ^ (1 << site), 0)
            )
    return (
        Fraction(rabi) - detuning * occupation
    ) / denominator


def _verify_trial(
    trial_directory: Path,
    size: int,
    detuning: Fraction,
):
    metadata_path = trial_directory / "trial-vector.json"
    metadata = _load_json(metadata_path)
    if metadata.get("purpose") != TRIAL_PURPOSE:
        raise ValueError("unexpected trial purpose")
    if int(metadata.get("size")) != size:
        raise ValueError("trial size does not match problem")
    if _parse_fraction(metadata.get("detuning")) != detuning:
        raise ValueError("trial detuning does not match problem")
    if int(metadata.get("basis_state_count")) != _periodic_dimension(size):
        raise ValueError("trial basis dimension is not the Lucas count")

    state_path = _safe_file(trial_directory, metadata["state_file"])
    coefficient_path = _safe_file(
        trial_directory,
        metadata["coefficient_file"],
    )
    state_payload = state_path.read_bytes()
    coefficient_payload = coefficient_path.read_bytes()
    count = int(metadata["nonzero_count"])
    if len(state_payload) != 8 * count:
        raise ValueError("trial state byte count is inconsistent")
    if len(coefficient_payload) != 8 * count:
        raise ValueError("trial coefficient byte count is inconsistent")
    if int(metadata["state_file_bytes"]) != len(state_payload):
        raise ValueError("recorded trial state byte count is inconsistent")
    if (
        int(metadata["coefficient_file_bytes"])
        != len(coefficient_payload)
    ):
        raise ValueError(
            "recorded trial coefficient byte count is inconsistent"
        )
    if _sha256_bytes(state_payload) != metadata["state_file_sha256"]:
        raise ValueError("trial state SHA-256 mismatch")
    if (
        _sha256_bytes(coefficient_payload)
        != metadata["coefficient_file_sha256"]
    ):
        raise ValueError("trial coefficient SHA-256 mismatch")
    states = tuple(
        item[0] for item in struct.iter_unpack("<Q", state_payload)
    )
    coefficients = tuple(
        item[0] for item in struct.iter_unpack("<q", coefficient_payload)
    )
    b_var = _exact_rayleigh(size, detuning, states, coefficients)
    denominator = sum(value * value for value in coefficients)
    if _parse_fraction(metadata["b_var"]) != b_var:
        raise ValueError("trial B_var is inconsistent")
    if int(metadata["rayleigh_denominator"]) != denominator:
        raise ValueError("trial Rayleigh denominator is inconsistent")
    if (
        _parse_fraction(metadata["rayleigh_numerator"])
        != b_var * denominator
    ):
        raise ValueError("trial Rayleigh numerator is inconsistent")

    project_root = Path(__file__).resolve().parents[3]
    if (
        metadata.get("trusted_basis_path")
        != "external/1d-basis/pxpbasis.py"
    ):
        raise ValueError("unexpected trusted basis path")
    trusted_path = project_root / metadata["trusted_basis_path"]
    if _sha256_file(trusted_path) != metadata["trusted_basis_sha256"]:
        raise ValueError("trusted basis SHA-256 mismatch")
    for relative, expected in metadata.get(
        "source_file_sha256",
        {},
    ).items():
        source_path = project_root / relative
        if _sha256_file(source_path) != expected:
            raise ValueError(f"trial source SHA-256 mismatch: {relative}")
    return b_var, _sha256_file(metadata_path)


def _verify_solver(
    solver_directory: Path,
    problem_sha256: str,
    problem_manifest_sha256: str,
):
    manifest_path = solver_directory / "solver-manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("purpose") != "numerical-ky-fan-solve-manifest":
        raise ValueError("unexpected solver manifest purpose")
    if manifest.get("success") is not True:
        raise ValueError("solver manifest does not report success")
    if manifest.get("problem_sha256") != problem_sha256:
        raise ValueError("solver problem SHA-256 mismatch")
    if (
        manifest.get("problem_manifest_sha256")
        != problem_manifest_sha256
    ):
        raise ValueError("solver problem-manifest SHA-256 mismatch")
    result_path = _safe_file(
        solver_directory,
        manifest["solver_result_file"],
    )
    if _sha256_file(result_path) != manifest["solver_result_sha256"]:
        raise ValueError("solver-result SHA-256 mismatch")
    seen = set()
    for metadata in manifest.get("files", []):
        if metadata["file"] in seen:
            raise ValueError("duplicate solver file metadata")
        seen.add(metadata["file"])
        _verify_file(solver_directory, metadata)
    result = _load_json(result_path)
    if result.get("purpose") != "numerical-ky-fan-dual":
        raise ValueError("unexpected solver-result purpose")
    if result.get("success") is not True:
        raise ValueError("solver result does not report success")
    if result.get("problem_sha256") != problem_sha256:
        raise ValueError("solver-result problem SHA-256 mismatch")
    _solver_seed_accuracy(result)
    if result.get("dual_cone") != "triangle-psd":
        raise ValueError("unexpected solver dual_cone")
    if result.get("dual_identity_sign_calibrated") is not True:
        raise ValueError("solver dual identity sign was not calibrated")
    if result.get("offdiagonal_scaling_calibrated") is not True:
        raise ValueError("solver off-diagonal scaling was not calibrated")
    for metadata in result["psd_duals"]:
        _verify_file(solver_directory, metadata)
        if metadata.get("layout") != "row-major":
            raise ValueError("solver dual layout is unsupported")
        if (
            metadata.get("scalar_format")
            != "float64-little-endian"
        ):
            raise ValueError("solver dual scalar format is unsupported")
    return (
        result,
        _sha256_file(result_path),
        _sha256_file(manifest_path),
    )


def _resolve_bound_reference(
    manifest_path: Path,
    reference,
    run_root: Path,
) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("artifact reference must be non-empty")
    relative = Path(reference)
    if relative.is_absolute() or "\\" in reference:
        raise ValueError("artifact reference must be normalized and relative")
    path = (manifest_path.parent / relative).resolve()
    root = run_root.resolve()
    if path != root and root not in path.parents:
        raise ValueError("artifact reference escapes the run directory")
    if not path.is_file():
        raise FileNotFoundError(f"missing bound artifact: {path}")
    return path


def _verify_v2_problem(problem_directory: Path):
    from challenge233.sdp.verify_kyfan_reduction import (
        verify_kyfan_reduction,
    )
    from challenge233.sdp.verify_kyfan_structure import (
        verify_bound_kyfan_structure,
    )

    manifest_path = problem_directory / "manifest.json"
    manifest = _load_json(manifest_path)
    if (
        manifest.get("schema_version") != 2
        or manifest.get("purpose")
        != "finite-N-ky-fan-instance-binding"
    ):
        raise ValueError("unexpected schema-v2 problem manifest")
    run_root = problem_directory.parents[2].resolve()
    structure_summary = verify_bound_kyfan_structure(
        problem_directory,
        run_root,
    )
    resolved = {}
    for component, reference_key, hash_key in (
        ("instance", "instance_file", "instance_sha256"),
        ("structure", "structure_reference", "structure_sha256"),
        (
            "structure_manifest",
            "structure_manifest_reference",
            "structure_manifest_sha256",
        ),
        ("reduction", "reduction_reference", "reduction_sha256"),
        (
            "reduction_manifest",
            "reduction_manifest_reference",
            "reduction_manifest_sha256",
        ),
    ):
        path = _resolve_bound_reference(
            manifest_path,
            manifest[reference_key],
            run_root,
        )
        if _sha256_file(path) != manifest[hash_key]:
            raise ValueError(f"schema-v2 {component} SHA-256 mismatch")
        resolved[component] = path
    reduction_summary = verify_kyfan_reduction(
        resolved["reduction"].parent
    )
    return {
        "manifest": manifest,
        "manifest_sha256": _sha256_file(manifest_path),
        "instance": _load_json(resolved["instance"]),
        "structure": _load_json(resolved["structure"]),
        "reduction": _load_json(resolved["reduction"]),
        "structure_summary": structure_summary,
        "reduction_summary": reduction_summary,
    }


def _verify_solver_v2(solver_directory: Path, problem):
    manifest_path = solver_directory / "solver-manifest.json"
    manifest = _load_json(manifest_path)
    bindings = {
        "problem_manifest_sha256": problem["manifest_sha256"],
        "structure_sha256": problem["manifest"]["structure_sha256"],
        "instance_sha256": problem["manifest"]["instance_sha256"],
        "reduction_sha256": problem["manifest"]["reduction_sha256"],
        "solver_view": problem["reduction"]["selected_view"],
    }
    if (
        manifest.get("schema_version") != 2
        or manifest.get("purpose")
        != "numerical-ky-fan-solve-manifest"
        or manifest.get("success") is not True
    ):
        raise ValueError("unexpected schema-v2 solver manifest")
    for key, expected in bindings.items():
        if manifest.get(key) != expected:
            raise ValueError(f"schema-v2 solver manifest {key} mismatch")
    result_path = _safe_file(
        solver_directory,
        manifest["solver_result_file"],
    )
    if _sha256_file(result_path) != manifest["solver_result_sha256"]:
        raise ValueError("solver-result SHA-256 mismatch")
    seen = set()
    for metadata in manifest.get("files", []):
        if metadata["file"] in seen:
            raise ValueError("duplicate solver file metadata")
        seen.add(metadata["file"])
        _verify_file(solver_directory, metadata)
    result = _load_json(result_path)
    if (
        result.get("schema_version") != 2
        or result.get("purpose")
        != "numerical-ky-fan-reduced-dual-v2"
        or result.get("success") is not True
    ):
        raise ValueError("unexpected schema-v2 solver result")
    for key, expected in bindings.items():
        if result.get(key) != expected:
            raise ValueError(f"schema-v2 solver result {key} mismatch")
    _solver_seed_accuracy(result)
    if result.get("dual_cone") != "triangle-psd":
        raise ValueError("unexpected solver dual_cone")
    if result.get("dual_identity_sign_calibrated") is not True:
        raise ValueError("solver dual identity sign was not calibrated")
    if result.get("offdiagonal_scaling_calibrated") is not True:
        raise ValueError("solver off-diagonal scaling was not calibrated")
    for metadata in result["psd_duals"]:
        _verify_file(solver_directory, metadata)
        if metadata.get("layout") != "row-major":
            raise ValueError("solver dual layout is unsupported")
        if (
            metadata.get("scalar_format")
            != "float64-little-endian"
        ):
            raise ValueError("solver dual scalar format is unsupported")
    return (
        result,
        _sha256_file(result_path),
        _sha256_file(manifest_path),
    )


def _read_factor(directory: Path, metadata):
    if metadata.get("layout") != "row-major":
        raise ValueError("factor layout must be row-major")
    rows = int(metadata["rows"])
    columns = int(metadata["columns"])
    requested_bits = int(metadata["requested_bits"])
    used_bits = int(metadata["used_bits"])
    if rows <= 0 or columns < 0:
        raise ValueError("factor dimensions are invalid")
    if not 0 <= used_bits <= requested_bits <= 60:
        raise ValueError("factor dyadic bits are invalid")
    path = _verify_file(directory, metadata)
    storage = metadata["storage"]
    if storage == "int64":
        if metadata.get("scalar_format") != "int64-little-endian":
            raise ValueError("factor scalar format is invalid")
        payload = path.read_bytes()
        if len(payload) != 8 * rows * columns:
            raise ValueError("factor byte count does not match dimensions")
        values = tuple(
            item[0] for item in struct.iter_unpack("<q", payload)
        )
        numerators = tuple(
            values[row * columns:(row + 1) * columns]
            for row in range(rows)
        )
    elif storage == "decimal-json":
        if metadata.get("scalar_format") != "decimal-string-json":
            raise ValueError("big-integer factor format is invalid")
        payload = _load_json(path)
        numerators = tuple(
            tuple(int(entry) for entry in row)
            for row in payload["rows"]
        )
        if len(numerators) != rows or any(
            len(row) != columns for row in numerators
        ):
            raise ValueError("big-integer factor shape is invalid")
    else:
        raise ValueError("factor storage is unsupported")
    maximum = max(
        (
            abs(entry)
            for row in numerators
            for entry in row
        ),
        default=0,
    )
    overflow_bound = columns * maximum * maximum
    if int(metadata["overflow_bound"]) != overflow_bound:
        raise ValueError("factor overflow bound is inconsistent")
    if storage == "int64" and overflow_bound >= 1 << 62:
        raise ValueError("factor int64 Gram bound is unsafe")
    return {
        "rows": rows,
        "columns": columns,
        "requested_bits": requested_bits,
        "used_bits": used_bits,
        "storage": storage,
        "numerators": numerators,
        "overflow_bound": overflow_bound,
    }


def _gram(factor):
    rows = factor["rows"]
    columns = factor["columns"]
    numerators = factor["numerators"]
    work = rows * rows * max(columns, 1)
    if factor["storage"] == "int64" and columns and work >= 1_000_000:
        try:
            import numpy as np
        except ImportError:
            pass
        else:
            array = np.asarray(numerators, dtype=np.int64)
            gram = array @ array.T
            return tuple(
                tuple(int(entry) for entry in row)
                for row in gram
            )
    return tuple(
        tuple(
            sum(
                numerators[row][column]
                * numerators[other][column]
                for column in range(columns)
            )
            for other in range(rows)
        )
        for row in range(rows)
    )


def _word(raw):
    word = tuple((int(site), str(label)) for site, label in raw)
    if tuple(site for site, _ in word) != tuple(
        sorted({site for site, _ in word})
    ):
        raise ValueError("Pauli word sites are not canonical")
    if any(label not in {"X", "Y", "Z"} for _, label in word):
        raise ValueError("Pauli word contains an invalid label")
    return word


def _act_word(word, shift, reflected, size):
    sign = -1 if reflected else 1
    return tuple(
        sorted(
            (
                (int(shift) + sign * site) % size,
                label,
            )
            for site, label in word
        )
    )


def _inverse_basis_permutation(
    basis,
    shift,
    reflected,
    size,
):
    index = {word: position for position, word in enumerate(basis)}
    permutation = []
    for word in basis:
        image = _act_word(word, shift, reflected, size)
        if image not in index:
            raise ValueError("moment basis is not closed under group image")
        permutation.append(index[image])
    if sorted(permutation) != list(range(len(basis))):
        raise ValueError("group image is not a basis permutation")
    inverse = [None] * len(permutation)
    for source, image in enumerate(permutation):
        inverse[image] = source
    return tuple(inverse)


def _factor_gram_entry(factor, inverse, row, column):
    left = factor["numerators"][inverse[row]]
    right = factor["numerators"][inverse[column]]
    return Fraction(
        sum(
            left[index] * right[index]
            for index in range(factor["columns"])
        ),
        1 << (2 * factor["used_bits"]),
    )


def _complex_form_parts(form, variable_count):
    real_constant, real = _form(form["real"], variable_count)
    imag_constant, imag = _form(form["imag"], variable_count)
    return real_constant, real, imag_constant, imag


def _phase_transform_parts(parts, exponent):
    real_constant, real, imag_constant, imag = parts
    exponent %= 4
    if exponent == 0:
        return real_constant, real, imag_constant, imag
    if exponent == 1:
        return (
            -imag_constant,
            {key: -value for key, value in imag.items()},
            real_constant,
            real,
        )
    if exponent == 2:
        return (
            -real_constant,
            {key: -value for key, value in real.items()},
            -imag_constant,
            {key: -value for key, value in imag.items()},
        )
    return (
        imag_constant,
        imag,
        -real_constant,
        {key: -value for key, value in real.items()},
    )


def _v2_psd_contribution(
    structure,
    reduction,
    factor_orbits,
):
    size = int(structure["size"])
    basis = tuple(_word(word) for word in structure["moment_basis"])
    variables = structure["variables"]
    variable_count = len(variables)
    phases = tuple(
        sum(label == "Y" for _, label in word) % 2
        for word in basis
    )
    odd_variables = {
        int(variable["index"])
        for variable in variables
        if sum(
            label == "Y"
            for _, label in _word(variable["representative"])
        )
        % 2
    }
    source_blocks = {
        block["identifier"]: block
        for block in structure["psd_blocks"]
    }
    reduced_blocks = {
        block["identifier"]: block
        for block in reduction["psd_blocks"]
    }
    spatial_blocks = {
        block["identifier"]: block
        for block in reduction["spatial"]
    }
    if set(factor_orbits) != set(reduced_blocks):
        raise ValueError("factor-orbit inventory mismatch")
    constant = Fraction(0)
    coefficients = [Fraction(0)] * variable_count
    for identifier, pair in factor_orbits.items():
        metadata, factor = pair
        reduced = reduced_blocks[identifier]
        spatial = spatial_blocks[reduced["spatial_block"]]
        if metadata.get("source_block") != reduced["source_block"]:
            raise ValueError("factor-orbit source block mismatch")
        if metadata.get("spatial_block") != spatial["identifier"]:
            raise ValueError("factor-orbit spatial block mismatch")
        if metadata.get("irrep_label") != spatial["irrep_label"]:
            raise ValueError("factor-orbit irrep label mismatch")
        if int(metadata.get("irrep_degree")) != int(
            spatial["irrep_degree"]
        ):
            raise ValueError("factor-orbit irrep degree mismatch")
        if tuple(metadata.get("phase_exponents", ())) != phases:
            raise ValueError("factor-orbit phase exponent mismatch")
        expected_images = tuple(
            (
                int(element["shift"]),
                bool(element["reflected"]),
            )
            for element in spatial["internal_group"]
        )
        actual_images = tuple(
            (
                int(element["shift"]),
                bool(element["reflected"]),
            )
            for element in metadata.get("group_images", ())
        )
        if actual_images != expected_images:
            raise ValueError("factor-orbit group image inventory mismatch")
        weight = _parse_fraction(metadata["weight"])
        if weight != Fraction(1, len(expected_images)):
            raise ValueError("factor-orbit weight mismatch")
        if factor["rows"] != len(basis):
            raise ValueError("factor-orbit row count mismatch")
        transform_hash = hashlib.sha256(
            json.dumps(
                spatial["transform"],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if (
            metadata.get("transform_hash_encoding")
            != "sha256-json3-compact-source-order"
            or metadata.get("transform_sha256") != transform_hash
        ):
            raise ValueError("factor-orbit transform hash mismatch")
        inverses = tuple(
            _inverse_basis_permutation(
                basis,
                shift,
                reflected,
                size,
            )
            for shift, reflected in actual_images
        )
        source = source_blocks.get(metadata["source_block"])
        if source is None:
            raise ValueError("factor-orbit logical source is unknown")
        for entry in source["upper_entries"]:
            row = int(entry["row"])
            column = int(entry["column"])
            gram = weight * sum(
                (
                    _factor_gram_entry(
                        factor,
                        inverse,
                        row,
                        column,
                    )
                    for inverse in inverses
                ),
                Fraction(0),
            )
            if not gram:
                continue
            if row != column:
                gram *= 2
            parts = _phase_transform_parts(
                _complex_form_parts(
                    entry["form"],
                    variable_count,
                ),
                phases[column] - phases[row],
            )
            (
                real_constant,
                real,
                imag_constant,
                imag,
            ) = parts
            if imag_constant or any(
                variable not in odd_variables and value
                for variable, value in imag.items()
            ):
                raise ValueError(
                    "factor-orbit inverse phase identity is not real"
                )
            constant += gram * real_constant
            for variable, value in real.items():
                coefficients[variable] += gram * value
    return constant, tuple(coefficients)


def _solve_exact_square(matrix, right_hand_side):
    rows = [
        [Fraction(value) for value in row]
        + [Fraction(right_hand_side[index])]
        for index, row in enumerate(matrix)
    ]
    dimension = len(rows)
    if any(len(row) != dimension + 1 for row in rows):
        raise ValueError("equality pivot system is not square")
    for column in range(dimension):
        pivot = next(
            (
                row
                for row in range(column, dimension)
                if rows[row][column]
            ),
            None,
        )
        if pivot is None:
            raise ValueError("equality pivot system is singular")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        inverse = Fraction(1) / rows[column][column]
        rows[column] = [
            inverse * value for value in rows[column]
        ]
        for row in range(dimension):
            if row == column or not rows[row][column]:
                continue
            factor = rows[row][column]
            rows[row] = [
                left - factor * right
                for left, right in zip(rows[row], rows[column])
            ]
    return tuple(row[-1] for row in rows)


def _v2_equality_identity(instance, reduction, psd_coefficients):
    variable_count = len(psd_coefficients)
    objective_constant, objective_map = _form(
        instance["objective"],
        variable_count,
    )
    objective = tuple(
        objective_map.get(index, Fraction(0))
        for index in range(variable_count)
    )
    equality = reduction["equality"]
    kept = tuple(equality["kept_rows"])
    pivots = tuple(int(value) for value in equality["pivot_columns"])
    if len(kept) != len(pivots):
        raise ValueError("equality kept-row/pivot count mismatch")
    parsed = tuple(
        _form(row["form"], variable_count)
        for row in kept
    )
    target = tuple(
        objective[index] - psd_coefficients[index]
        for index in range(variable_count)
    )
    matrix = tuple(
        tuple(coefficients.get(pivot, Fraction(0))
              for _, coefficients in parsed)
        for pivot in pivots
    )
    values = _solve_exact_square(
        matrix,
        tuple(target[pivot] for pivot in pivots),
    )
    all_identifiers = tuple(
        str(value)
        for value in equality["statistics"]["all_identifiers"]
    )
    multipliers = {
        identifier: Fraction(0)
        for identifier in all_identifiers
    }
    for row, value in zip(kept, values):
        identifier = str(row["identifier"])
        if identifier not in multipliers:
            raise ValueError("kept equality is absent from full inventory")
        multipliers[identifier] = value
    equality_constant = Fraction(0)
    equality_coefficients = [Fraction(0)] * variable_count
    for row, (constant, coefficients) in zip(kept, parsed):
        multiplier = multipliers[str(row["identifier"])]
        equality_constant += multiplier * constant
        for variable, coefficient in coefficients.items():
            equality_coefficients[variable] += multiplier * coefficient
    for pivot in pivots:
        if (
            target[pivot] - equality_coefficients[pivot]
        ):
            raise ValueError("equality pivot cancellation failed")
    return (
        objective_constant,
        objective,
        multipliers,
        equality_constant,
        tuple(equality_coefficients),
    )


def _form(form, number_of_variables):
    constant = _parse_fraction(form["constant"])
    coefficients = {}
    for term in form["terms"]:
        if len(term) != 2:
            raise ValueError("affine term shape is invalid")
        variable = int(term[0])
        if not 0 <= variable < number_of_variables:
            raise ValueError("affine variable is out of range")
        coefficients[variable] = (
            coefficients.get(variable, Fraction(0))
            + _parse_fraction(term[1])
        )
    return constant, coefficients


def _v2_moment_correction(structure, residuals):
    bounds = {}
    for witness in structure["magnitude_witnesses"]:
        variable = int(witness["variable"])
        if variable in bounds:
            raise ValueError("duplicate magnitude witness")
        bound = _parse_fraction(witness["bound"])
        if bound < 0:
            raise ValueError("negative magnitude witness")
        bounds[variable] = bound
    if set(bounds) != set(range(len(residuals))):
        raise ValueError("missing magnitude witness")
    return sum(
        bounds[index] * abs(value)
        for index, value in enumerate(residuals)
    )


def _periodic_legal_state(size, state):
    return all(
        not (
            ((state >> site) & 1)
            and ((state >> ((site + 1) % size)) & 1)
        )
        for site in range(size)
    )


def _act_state(state, shift, reflected, size):
    sign = -1 if reflected else 1
    output = 0
    for site in range(size):
        if (state >> site) & 1:
            output |= 1 << ((shift + sign * site) % size)
    return output


def _canonical_legal_states(size, legal):
    unseen = set(legal)
    representatives = []
    elements = tuple(
        (shift, reflected)
        for reflected in (False, True)
        for shift in range(size)
    )
    while unseen:
        representative = min(unseen)
        orbit = {
            _act_state(
                representative,
                shift,
                reflected,
                size,
            )
            for shift, reflected in elements
        }
        if not orbit <= set(legal):
            raise ValueError("group action does not preserve legal states")
        representatives.append(representative)
        unseen.difference_update(orbit)
    return tuple(representatives)


def _complex_multiply(left, right):
    left_real, left_imag = left
    right_real, right_imag = right
    return (
        left_real * right_real - left_imag * right_imag,
        left_real * right_imag + left_imag * right_real,
    )


def _literal_word_action(word, state):
    output = state
    phase = (1, 0)
    for site, label in word:
        bit = (output >> site) & 1
        if label == "X":
            output ^= 1 << site
            local = (1, 0)
        elif label == "Y":
            output ^= 1 << site
            local = (0, 1 if bit else -1)
        elif label == "Z":
            local = (1 if bit else -1, 0)
        else:
            raise ValueError("invalid Pauli label")
        phase = _complex_multiply(phase, local)
    return output, phase


def _v2_operator_correction(structure, residuals):
    size = int(structure["size"])
    variables = tuple(structure["variables"])
    if tuple(int(item["index"]) for item in variables) != tuple(
        range(len(variables))
    ):
        raise ValueError("moment variable indices are not contiguous")
    legal = tuple(
        state
        for state in range(1 << size)
        if _periodic_legal_state(size, state)
    )
    legal_set = set(legal)
    representatives = _canonical_legal_states(size, legal)
    maximum = Fraction(0)
    for input_state in representatives:
        row = {}
        for variable, residual in zip(variables, residuals):
            if not residual:
                continue
            orbit = tuple(_word(word) for word in variable["orbit"])
            if not orbit:
                raise ValueError("moment variable orbit is empty")
            coefficient = residual / len(orbit)
            for word in orbit:
                output, (phase_real, phase_imag) = (
                    _literal_word_action(word, input_state)
                )
                if output not in legal_set:
                    continue
                current_real, current_imag = row.get(
                    output,
                    (Fraction(0), Fraction(0)),
                )
                row[output] = (
                    current_real + coefficient * phase_real,
                    current_imag + coefficient * phase_imag,
                )
        row_sum = sum(
            abs(real) + abs(imag)
            for real, imag in row.values()
        )
        maximum = max(maximum, row_sum)
    return 2 * maximum


def _exact_identity(problem, factors, equality_multipliers):
    number_of_variables = len(problem["variables"])
    for index, variable in enumerate(problem["variables"]):
        if int(variable["index"]) != index:
            raise ValueError("problem variable indices are not contiguous")
    bounds = [None] * number_of_variables
    for witness in problem["magnitude_witnesses"]:
        variable = int(witness["variable"])
        if not 0 <= variable < number_of_variables:
            raise ValueError("magnitude witness variable is invalid")
        if bounds[variable] is not None:
            raise ValueError("duplicate magnitude witness")
        bound = _parse_fraction(witness["bound"])
        if bound != 2:
            raise ValueError("unsupported magnitude witness")
        bounds[variable] = bound
    if any(bound is None for bound in bounds):
        raise ValueError("missing magnitude witness")

    objective_constant, objective_map = _form(
        problem["objective"],
        number_of_variables,
    )
    objective = [
        objective_map.get(index, Fraction(0))
        for index in range(number_of_variables)
    ]
    blocks = {
        str(block["identifier"]): block
        for block in problem["psd_blocks"]
    }
    if set(blocks) != set(factors):
        raise ValueError("factor inventory does not match PSD blocks")
    psd_constant = Fraction(0)
    psd = [Fraction(0)] * number_of_variables
    for identifier, block in blocks.items():
        factor = factors[identifier]
        dimension = int(block["dimension"])
        if factor["rows"] != dimension:
            raise ValueError("factor dimension does not match PSD block")
        gram = _gram(factor)
        denominator = 1 << (2 * factor["used_bits"])
        for row in range(dimension):
            for column in range(dimension):
                numerator = gram[row][column]
                if numerator == 0:
                    continue
                weight = Fraction(numerator, denominator)
                constant, coefficients = _form(
                    block["entries"][row][column],
                    number_of_variables,
                )
                psd_constant += weight * constant
                for variable, coefficient in coefficients.items():
                    psd[variable] += weight * coefficient

    equalities = {
        str(row["identifier"]): row
        for row in problem["equalities"]
    }
    if set(equalities) != set(equality_multipliers):
        raise ValueError("equality multiplier inventory is incomplete")
    equality_constant = Fraction(0)
    equality = [Fraction(0)] * number_of_variables
    for identifier, row in equalities.items():
        multiplier = equality_multipliers[identifier]
        constant, coefficients = _form(
            row["form"],
            number_of_variables,
        )
        equality_constant += multiplier * constant
        for variable, coefficient in coefficients.items():
            equality[variable] += multiplier * coefficient
    a = objective_constant - psd_constant - equality_constant
    residuals = tuple(
        objective[index] - psd[index] - equality[index]
        for index in range(number_of_variables)
    )
    rho = sum(
        bound * abs(residual)
        for bound, residual in zip(bounds, residuals)
    )
    return a, residuals, tuple(bounds), rho, a - rho


def _compare_residual_artifact(
    residual_payload,
    a,
    residuals,
    bounds,
    rho,
    a_cert,
):
    if _parse_fraction(residual_payload["a"]) != a:
        raise ValueError("recorded residual constant a is inconsistent")
    rows = residual_payload["residuals"]
    if len(rows) != len(residuals):
        raise ValueError("recorded residual inventory is incomplete")
    for index, row in enumerate(rows):
        if int(row["variable"]) != index:
            raise ValueError("recorded residual variable order is invalid")
        if _parse_fraction(row["value"]) != residuals[index]:
            raise ValueError("recorded residual value is inconsistent")
        if _parse_fraction(row["bound"]) != bounds[index]:
            raise ValueError("recorded residual bound is inconsistent")
        if (
            _parse_fraction(row["correction"])
            != bounds[index] * abs(residuals[index])
        ):
            raise ValueError("recorded residual correction is inconsistent")
    if _parse_fraction(residual_payload["rho"]) != rho:
        raise ValueError("recorded residual rho is inconsistent")
    if _parse_fraction(residual_payload["a_cert"]) != a_cert:
        raise ValueError("recorded residual A_cert is inconsistent")


def _verify_v2_certificate(
    cell_directory: Path,
    certificate_directory: Path,
    manifest,
):
    if (
        manifest.get("schema_version") != 2
        or manifest.get("purpose")
        != "finite-N-ky-fan-gap-certificate-manifest"
    ):
        raise ValueError("unexpected schema-v2 certificate manifest")
    bound_directories = {}
    for component, key in (
        ("problem", "problem_directory"),
        ("solver", "solver_directory"),
        ("trial", "trial_directory"),
    ):
        path = (certificate_directory / manifest[key]).resolve()
        if path != cell_directory and cell_directory not in path.parents:
            raise ValueError(
                f"certificate {component} directory escapes the cell"
            )
        bound_directories[component] = path
    problem = _verify_v2_problem(bound_directories["problem"])
    for key in (
        "problem_manifest_sha256",
        "structure_sha256",
        "instance_sha256",
        "reduction_sha256",
    ):
        expected = (
            problem["manifest_sha256"]
            if key == "problem_manifest_sha256"
            else problem["manifest"][key]
        )
        if manifest.get(key) != expected:
            raise ValueError(f"certificate manifest {key} mismatch")
    solver_result, solver_result_sha256, solver_manifest_sha256 = (
        _verify_solver_v2(bound_directories["solver"], problem)
    )
    if manifest.get("solver_result_sha256") != solver_result_sha256:
        raise ValueError("certificate solver-result SHA-256 mismatch")
    if manifest.get("solver_manifest_sha256") != solver_manifest_sha256:
        raise ValueError("certificate solver-manifest SHA-256 mismatch")
    structure = problem["structure"]
    reduction = problem["reduction"]
    instance = problem["instance"]
    reduced_blocks = {
        block["identifier"]: block
        for block in reduction["psd_blocks"]
    }
    solver_duals = {
        metadata["block"]: metadata
        for metadata in solver_result["psd_duals"]
    }
    if (
        len(solver_duals) != len(solver_result["psd_duals"])
        or set(solver_duals) != set(reduced_blocks)
    ):
        raise ValueError("solver reduced-dual inventory mismatch")
    spatial = {
        block["identifier"]: block
        for block in reduction["spatial"]
    }
    for identifier, block in reduced_blocks.items():
        metadata = solver_duals[identifier]
        spatial_block = spatial[block["spatial_block"]]
        for key, expected in (
            ("dimension", int(block["dimension"])),
            ("source_effect", block["source_block"]),
            ("spatial_block", block["spatial_block"]),
            ("irrep_label", spatial_block["irrep_label"]),
            ("irrep_degree", int(spatial_block["irrep_degree"])),
        ):
            actual = (
                int(metadata[key])
                if key in {"dimension", "irrep_degree"}
                else metadata.get(key)
            )
            if actual != expected:
                raise ValueError(f"solver reduced-dual {key} mismatch")
    size = int(structure["size"])
    detuning = _parse_fraction(instance["detuning"])
    b_var, trial_vector_sha256 = _verify_trial(
        bound_directories["trial"],
        size,
        detuning,
    )
    if (
        trial_vector_sha256
        != instance["trial_manifest_sha256"]
        or manifest.get("trial_vector_sha256")
        != trial_vector_sha256
    ):
        raise ValueError("certificate trial-vector SHA-256 mismatch")

    certificate_path = _safe_file(
        certificate_directory,
        manifest["certificate_file"],
    )
    if _sha256_file(certificate_path) != manifest["certificate_sha256"]:
        raise ValueError("certificate SHA-256 mismatch")
    certificate = _load_json(certificate_path)
    if (
        certificate.get("schema_version") != 2
        or certificate.get("purpose") != CERTIFICATE_PURPOSE
    ):
        raise ValueError("unexpected schema-v2 certificate")
    certificate_bindings = {
        "problem_manifest_sha256": problem["manifest_sha256"],
        "structure_sha256": problem["manifest"]["structure_sha256"],
        "instance_sha256": problem["manifest"]["instance_sha256"],
        "reduction_sha256": problem["manifest"]["reduction_sha256"],
        "solver_result_sha256": solver_result_sha256,
        "solver_manifest_sha256": solver_manifest_sha256,
        "trial_vector_sha256": trial_vector_sha256,
        "solver_view": reduction["selected_view"],
    }
    for key, expected in certificate_bindings.items():
        if certificate.get(key) != expected:
            raise ValueError(f"certificate {key} mismatch")
    manifest_files = {
        item["file"]: item for item in manifest["files"]
    }
    if len(manifest_files) != len(manifest["files"]):
        raise ValueError("duplicate certificate file metadata")
    factor_bits = int(certificate["factor_bits_requested"])
    if not 0 <= factor_bits <= 60:
        raise ValueError("certificate factor precision is invalid")
    factors = {}
    for metadata in certificate["factor_orbits"]:
        identifier = str(metadata["block"])
        if identifier in factors:
            raise ValueError("duplicate certificate factor orbit")
        if metadata["file"] not in manifest_files:
            raise ValueError("factor orbit is absent from manifest")
        manifest_metadata = manifest_files[metadata["file"]]
        if (
            manifest_metadata["sha256"] != metadata["sha256"]
            or int(manifest_metadata["byte_count"])
            != int(metadata["byte_count"])
        ):
            raise ValueError("factor-orbit manifest metadata mismatch")
        factor = _read_factor(certificate_directory, metadata)
        if factor["requested_bits"] < factor_bits:
            raise ValueError("factor requested precision is inconsistent")
        factors[identifier] = (metadata, factor)
    psd_constant, psd_coefficients = _v2_psd_contribution(
        structure,
        reduction,
        factors,
    )
    (
        objective_constant,
        objective,
        expected_multipliers,
        equality_constant,
        equality_coefficients,
    ) = _v2_equality_identity(
        instance,
        reduction,
        psd_coefficients,
    )
    recorded_multipliers = {}
    for item in certificate["equality_multipliers"]:
        identifier = str(item["identifier"])
        if identifier in recorded_multipliers:
            raise ValueError("duplicate equality multiplier")
        recorded_multipliers[identifier] = _parse_fraction(item["value"])
    if recorded_multipliers != expected_multipliers:
        raise ValueError(
            "reconstructed equality multiplier inventory is inconsistent"
        )
    a = objective_constant - psd_constant - equality_constant
    residuals = tuple(
        objective[index]
        - psd_coefficients[index]
        - equality_coefficients[index]
        for index in range(len(objective))
    )
    rho_mom = _v2_moment_correction(structure, residuals)
    rho_op = _v2_operator_correction(structure, residuals)
    rho = min(rho_mom, rho_op)
    route = (
        "pseudo-moment"
        if rho_mom <= rho_op
        else "physical-operator"
    )
    a_cert = a - rho

    residual_path = _safe_file(
        certificate_directory,
        certificate["dual_residuals_file"],
    )
    residual_sha256 = _sha256_file(residual_path)
    if (
        residual_sha256 != certificate["dual_residuals_sha256"]
        or residual_sha256 != manifest["dual_residuals_sha256"]
        or residual_path.name != manifest["dual_residuals_file"]
    ):
        raise ValueError("dual residual SHA-256 binding mismatch")
    residual_payload = _load_json(residual_path)
    expected_residual_keys = {
        "schema_version",
        "purpose",
        "coordinate_system",
        "a",
        "residuals",
        "rho_mom",
        "rho_op",
        "rho",
        "residual_route",
        "a_cert",
    }
    if set(residual_payload) != expected_residual_keys:
        raise ValueError(
            "schema-v2 residual payload contains an invalid coordinate"
        )
    if (
        residual_payload.get("schema_version") != 2
        or residual_payload.get("purpose")
        != "exact-ky-fan-lifted-dual-residuals"
    ):
        raise ValueError("unexpected schema-v2 residual payload")
    rows = residual_payload["residuals"]
    if len(rows) != len(residuals):
        raise ValueError("recorded residual inventory is incomplete")
    for index, row in enumerate(rows):
        if (
            set(row) != {"variable", "value"}
            or int(row["variable"]) != index
            or _parse_fraction(row["value"]) != residuals[index]
        ):
            raise ValueError("recorded residual value is inconsistent")
    residual_comparisons = (
        ("a", a),
        ("rho_mom", rho_mom),
        ("rho_op", rho_op),
        ("rho", rho),
        ("a_cert", a_cert),
    )
    for key, expected in residual_comparisons:
        if _parse_fraction(residual_payload[key]) != expected:
            raise ValueError(f"recorded residual {key} is inconsistent")
    if residual_payload["residual_route"] != route:
        raise ValueError("recorded residual route is inconsistent")

    delta_cert = a_cert - 2 * b_var
    status = "certified" if delta_cert > 0 else "not_certified"
    for key, expected in (
        ("a", a),
        ("rho_mom", rho_mom),
        ("rho_op", rho_op),
        ("rho", rho),
        ("a_cert", a_cert),
        ("b_var", b_var),
        ("delta_cert", delta_cert),
    ):
        if _parse_fraction(certificate[key]) != expected:
            label = "B_var" if key == "b_var" else key
            raise ValueError(f"certificate {label} is inconsistent")
    if certificate["residual_route"] != route:
        raise ValueError("certificate residual route is inconsistent")
    if certificate["status"] != status:
        raise ValueError("certificate status is inconsistent")
    project_root = Path(__file__).resolve().parents[3]
    for relative, expected in manifest.get(
        "source_file_sha256",
        {},
    ).items():
        if _sha256_file(project_root / relative) != expected:
            raise ValueError(
                f"certificate source SHA-256 mismatch: {relative}"
            )
    return {
        "status": "verified",
        "schema_version": 2,
        "problem_status": problem["structure_summary"]["status"],
        "reduction_status": problem["reduction_summary"]["status"],
        "size": size,
        "detuning": _encode_fraction(detuning),
        "a_cert": _encode_fraction(a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "certificate_status": status,
        "factor_count": len(factors),
        "residual_count": len(residuals),
        "rho_mom": _encode_fraction(rho_mom),
        "rho_op": _encode_fraction(rho_op),
        "residual_route": route,
    }


def verify_kyfan_certificate(cell_directory):
    """Verify hashes and recompute the exact certificate from raw integers."""
    cell_directory = Path(cell_directory).resolve()
    certificate_directory = _resolve_certificate_directory(cell_directory)
    manifest_path = certificate_directory / "manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") == 2:
        return _verify_v2_certificate(
            cell_directory,
            certificate_directory,
            manifest,
        )
    if (
        manifest.get("purpose")
        != "finite-N-ky-fan-gap-certificate-manifest"
    ):
        raise ValueError("unexpected certificate manifest purpose")
    problem_directory = (
        certificate_directory / manifest["problem_directory"]
    ).resolve()
    solver_directory = (
        certificate_directory / manifest["solver_directory"]
    ).resolve()
    trial_directory = (
        certificate_directory / manifest["trial_directory"]
    ).resolve()

    problem_summary = verify_kyfan_problem(problem_directory)
    problem_manifest_path = problem_directory / "manifest.json"
    problem_manifest = _load_json(problem_manifest_path)
    problem_path = _safe_file(
        problem_directory,
        problem_manifest["problem_file"],
    )
    problem_sha256 = _sha256_file(problem_path)
    problem_manifest_sha256 = _sha256_file(problem_manifest_path)
    if problem_sha256 != problem_manifest["problem_sha256"]:
        raise ValueError("problem SHA-256 mismatch")
    if manifest["problem_sha256"] != problem_sha256:
        raise ValueError("certificate problem SHA-256 mismatch")
    if (
        manifest["problem_manifest_sha256"]
        != problem_manifest_sha256
    ):
        raise ValueError("certificate problem-manifest SHA-256 mismatch")
    problem = _load_json(problem_path)

    solver_result, solver_result_sha256, solver_manifest_sha256 = (
        _verify_solver(
            solver_directory,
            problem_sha256,
            problem_manifest_sha256,
        )
    )
    if manifest["solver_result_sha256"] != solver_result_sha256:
        raise ValueError("certificate solver-result SHA-256 mismatch")
    if manifest["solver_manifest_sha256"] != solver_manifest_sha256:
        raise ValueError("certificate solver-manifest SHA-256 mismatch")
    solver_duals = {
        str(item["block"]): item
        for item in solver_result["psd_duals"]
    }
    problem_blocks = {
        str(block["identifier"]): block
        for block in problem["psd_blocks"]
    }
    if len(solver_duals) != len(solver_result["psd_duals"]):
        raise ValueError("duplicate solver PSD dual block")
    if set(solver_duals) != set(problem_blocks):
        raise ValueError("solver PSD dual inventory does not match problem")
    for identifier, block in problem_blocks.items():
        if int(solver_duals[identifier]["dimension"]) != int(
            block["dimension"]
        ):
            raise ValueError("solver PSD dual dimension does not match problem")

    size = int(problem["size"])
    detuning = _parse_fraction(problem["detuning"])
    b_var, trial_vector_sha256 = _verify_trial(
        trial_directory,
        size,
        detuning,
    )
    if manifest["trial_vector_sha256"] != trial_vector_sha256:
        raise ValueError("certificate trial-vector SHA-256 mismatch")

    certificate_path = _safe_file(
        certificate_directory,
        manifest["certificate_file"],
    )
    if _sha256_file(certificate_path) != manifest["certificate_sha256"]:
        raise ValueError("certificate SHA-256 mismatch")
    certificate = _load_json(certificate_path)
    if certificate.get("purpose") != CERTIFICATE_PURPOSE:
        raise ValueError("unexpected certificate purpose")
    for key, expected in (
        ("problem_sha256", problem_sha256),
        ("problem_manifest_sha256", problem_manifest_sha256),
        ("solver_result_sha256", solver_result_sha256),
        ("solver_manifest_sha256", solver_manifest_sha256),
        ("trial_vector_sha256", trial_vector_sha256),
    ):
        if certificate.get(key) != expected:
            raise ValueError(f"certificate {key} mismatch")

    manifest_files = {
        entry["file"]: entry for entry in manifest["files"]
    }
    if len(manifest_files) != len(manifest["files"]):
        raise ValueError("duplicate certificate file metadata")
    factors = {}
    factor_bits_requested = int(certificate["factor_bits_requested"])
    if not 0 <= factor_bits_requested <= 60:
        raise ValueError("certificate factor precision is invalid")
    for metadata in certificate["factors"]:
        identifier = str(metadata["block"])
        if identifier in factors:
            raise ValueError("duplicate certificate factor block")
        if metadata["file"] not in manifest_files:
            raise ValueError("factor is absent from certificate manifest")
        manifest_metadata = manifest_files[metadata["file"]]
        if manifest_metadata["sha256"] != metadata["sha256"]:
            raise ValueError("factor manifest SHA-256 mismatch")
        if int(manifest_metadata["byte_count"]) != int(
            metadata["byte_count"]
        ):
            raise ValueError("factor manifest byte count mismatch")
        factors[identifier] = _read_factor(
            certificate_directory,
            metadata,
        )
        if (
            factors[identifier]["requested_bits"]
            != factor_bits_requested
        ):
            raise ValueError("factor requested precision is inconsistent")

    equality_multipliers = {}
    multiplier_bits = int(certificate["multiplier_bits"])
    if not 0 <= multiplier_bits <= 60:
        raise ValueError("certificate multiplier precision is invalid")
    for item in certificate["equality_multipliers"]:
        identifier = str(item["identifier"])
        if identifier in equality_multipliers:
            raise ValueError("duplicate equality multiplier")
        equality_multipliers[identifier] = _parse_fraction(item["value"])
        if (
            (1 << multiplier_bits)
            % equality_multipliers[identifier].denominator
            != 0
        ):
            raise ValueError("equality multiplier is not dyadic at precision")
    solver_equality_ids = {
        str(item["identifier"])
        for item in solver_result["equality_multipliers"]
    }
    if set(equality_multipliers) != solver_equality_ids:
        raise ValueError("certificate equality inventory mismatch")

    a, residuals, bounds, rho, a_cert = _exact_identity(
        problem,
        factors,
        equality_multipliers,
    )
    residual_path = _safe_file(
        certificate_directory,
        certificate["dual_residuals_file"],
    )
    residual_sha256 = _sha256_file(residual_path)
    if residual_sha256 != certificate["dual_residuals_sha256"]:
        raise ValueError("dual residual SHA-256 mismatch")
    if residual_sha256 != manifest["dual_residuals_sha256"]:
        raise ValueError("manifest dual residual SHA-256 mismatch")
    if residual_path.name != manifest["dual_residuals_file"]:
        raise ValueError("manifest dual residual file mismatch")
    residual_payload = _load_json(residual_path)
    _compare_residual_artifact(
        residual_payload,
        a,
        residuals,
        bounds,
        rho,
        a_cert,
    )

    delta_cert = a_cert - 2 * b_var
    status = "certified" if delta_cert > 0 else "not_certified"
    comparisons = (
        ("a", a),
        ("rho", rho),
        ("a_cert", a_cert),
        ("b_var", b_var),
        ("delta_cert", delta_cert),
    )
    for field, expected in comparisons:
        if _parse_fraction(certificate[field]) != expected:
            label = "B_var" if field == "b_var" else field
            raise ValueError(f"certificate {label} is inconsistent")
    if certificate["status"] != status:
        raise ValueError("certificate status is inconsistent")

    project_root = Path(__file__).resolve().parents[3]
    for relative, expected in manifest.get(
        "source_file_sha256",
        {},
    ).items():
        if _sha256_file(project_root / relative) != expected:
            raise ValueError(
                f"certificate source SHA-256 mismatch: {relative}"
            )
    return {
        "status": "verified",
        "problem_status": problem_summary["status"],
        "size": size,
        "detuning": _encode_fraction(detuning),
        "a_cert": _encode_fraction(a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "certificate_status": status,
        "factor_count": len(factors),
        "residual_count": len(residuals),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify an exact Ky Fan gap certificate"
    )
    parser.add_argument("cell_directory")
    arguments = parser.parse_args(argv)
    print(
        json.dumps(
            verify_kyfan_certificate(arguments.cell_directory),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
