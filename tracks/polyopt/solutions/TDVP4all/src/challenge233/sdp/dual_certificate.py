"""Exact dyadic reconstruction of numerical Ky Fan SDP duals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Mapping


CERTIFICATE_PURPOSE = "finite-N-ky-fan-gap-certificate"
SOLVER_PURPOSE = "numerical-ky-fan-dual"
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


@dataclass(frozen=True)
class DyadicFactor:
    rows: int
    columns: int
    requested_bits: int
    used_bits: int
    numerators: tuple[tuple[int, ...], ...]
    storage: str
    overflow_bound: int


@dataclass(frozen=True)
class ExactDualIdentity:
    a: Fraction
    residuals: tuple[Fraction, ...]
    bounds: tuple[Fraction, ...]
    rho: Fraction
    a_cert: Fraction


def _parse_fraction(value) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if not isinstance(value, str):
        raise TypeError("exact coefficient must be a fraction string")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"invalid exact fraction: {value}") from error


def _validate_factor(factor: DyadicFactor) -> None:
    if not isinstance(factor, DyadicFactor):
        raise TypeError("factor must be a DyadicFactor")
    if factor.rows <= 0 or factor.columns < 0:
        raise ValueError("factor dimensions are invalid")
    if not 0 <= factor.used_bits <= factor.requested_bits <= 60:
        raise ValueError("factor dyadic bits are invalid")
    if factor.storage not in {"int64", "decimal-json"}:
        raise ValueError("factor storage is unsupported")
    if len(factor.numerators) != factor.rows:
        raise ValueError("factor row count is inconsistent")
    if any(
        len(row) != factor.columns
        for row in factor.numerators
    ):
        raise ValueError("factor column count is inconsistent")
    if any(
        isinstance(entry, bool) or not isinstance(entry, int)
        for row in factor.numerators
        for entry in row
    ):
        raise TypeError("factor numerators must be integers")
    maximum = max(
        (
            abs(entry)
            for row in factor.numerators
            for entry in row
        ),
        default=0,
    )
    overflow_bound = factor.columns * maximum * maximum
    if overflow_bound != factor.overflow_bound:
        raise ValueError("factor overflow bound is inconsistent")
    if factor.storage == "int64":
        if any(
            not -(1 << 63) <= entry < (1 << 63)
            for row in factor.numerators
            for entry in row
        ):
            raise OverflowError("int64 factor contains an out-of-range entry")
        if overflow_bound >= 1 << 62:
            raise OverflowError("int64 factor Gram bound is unsafe")


def _gram_numerators(
    factor: DyadicFactor,
) -> tuple[tuple[int, ...], ...]:
    _validate_factor(factor)
    work = factor.rows * factor.rows * max(factor.columns, 1)
    if (
        factor.storage == "int64"
        and factor.columns
        and work >= 1_000_000
    ):
        try:
            import numpy as np
        except ImportError:
            pass
        else:
            numerators = np.asarray(
                factor.numerators,
                dtype=np.int64,
            )
            gram = numerators @ numerators.T
            return tuple(
                tuple(int(entry) for entry in row)
                for row in gram
            )
    return tuple(
        tuple(
            sum(
                factor.numerators[row][column]
                * factor.numerators[other_row][column]
                for column in range(factor.columns)
            )
            for other_row in range(factor.rows)
        )
        for row in range(factor.rows)
    )


def _form_coefficients(form, number_of_variables):
    constant = _parse_fraction(form["constant"])
    coefficients = {}
    for term in form["terms"]:
        if len(term) != 2:
            raise ValueError("affine term must have two entries")
        variable = int(term[0])
        if not 0 <= variable < number_of_variables:
            raise ValueError("affine variable index is out of range")
        coefficient = _parse_fraction(term[1])
        coefficients[variable] = (
            coefficients.get(variable, Fraction(0))
            + coefficient
        )
    return constant, coefficients


def _checked_bounds(problem, number_of_variables):
    bounds = [None] * number_of_variables
    for witness in problem["magnitude_witnesses"]:
        variable = int(witness["variable"])
        if not 0 <= variable < number_of_variables:
            raise ValueError("magnitude witness variable is out of range")
        if bounds[variable] is not None:
            raise ValueError("duplicate magnitude witness")
        bound = _parse_fraction(witness["bound"])
        if bound != 2:
            raise ValueError("unsupported magnitude witness bound")
        bounds[variable] = bound
    if any(bound is None for bound in bounds):
        raise ValueError("missing magnitude witness")
    return tuple(bounds)


def exact_dual_identity(
    problem,
    factors: Mapping[str, DyadicFactor],
    equality_multipliers: Mapping[str, Fraction],
) -> ExactDualIdentity:
    """Rebuild the complete dual coefficient identity over rationals."""
    variables = problem["variables"]
    number_of_variables = len(variables)
    for index, variable in enumerate(variables):
        if int(variable["index"]) != index:
            raise ValueError("problem variable indices must be contiguous")
    bounds = _checked_bounds(problem, number_of_variables)

    objective_constant, objective_terms = _form_coefficients(
        problem["objective"],
        number_of_variables,
    )
    objective_coefficients = [
        objective_terms.get(index, Fraction(0))
        for index in range(number_of_variables)
    ]

    block_by_identifier = {
        str(block["identifier"]): block
        for block in problem["psd_blocks"]
    }
    if len(block_by_identifier) != len(problem["psd_blocks"]):
        raise ValueError("duplicate PSD block identifier")
    if set(factors) != set(block_by_identifier):
        raise ValueError("factor inventory does not match PSD blocks")

    psd_constant = Fraction(0)
    psd_coefficients = [Fraction(0)] * number_of_variables
    for identifier, block in block_by_identifier.items():
        factor = factors[identifier]
        _validate_factor(factor)
        dimension = int(block["dimension"])
        if factor.rows != dimension:
            raise ValueError("factor dimension does not match PSD block")
        entries = block["entries"]
        if len(entries) != dimension or any(
            len(row) != dimension for row in entries
        ):
            raise ValueError("PSD block entries do not match dimension")
        gram = _gram_numerators(factor)
        gram_denominator = 1 << (2 * factor.used_bits)
        for row in range(dimension):
            for column in range(dimension):
                numerator = gram[row][column]
                if numerator == 0:
                    continue
                weight = Fraction(numerator, gram_denominator)
                constant, coefficients = _form_coefficients(
                    entries[row][column],
                    number_of_variables,
                )
                psd_constant += weight * constant
                for variable, coefficient in coefficients.items():
                    psd_coefficients[variable] += weight * coefficient

    equality_by_identifier = {
        str(row["identifier"]): row
        for row in problem["equalities"]
    }
    if len(equality_by_identifier) != len(problem["equalities"]):
        raise ValueError("duplicate equality identifier")
    if set(equality_multipliers) != set(equality_by_identifier):
        raise ValueError(
            "equality multiplier inventory does not match equalities"
        )

    equality_constant = Fraction(0)
    equality_coefficients = [Fraction(0)] * number_of_variables
    for identifier, row in equality_by_identifier.items():
        multiplier = equality_multipliers[identifier]
        if not isinstance(multiplier, Fraction):
            raise TypeError("equality multiplier must be a Fraction")
        constant, coefficients = _form_coefficients(
            row["form"],
            number_of_variables,
        )
        equality_constant += multiplier * constant
        for variable, coefficient in coefficients.items():
            equality_coefficients[variable] += multiplier * coefficient

    a = objective_constant - psd_constant - equality_constant
    residuals = tuple(
        objective_coefficients[index]
        - psd_coefficients[index]
        - equality_coefficients[index]
        for index in range(number_of_variables)
    )
    rho = sum(
        bound * abs(residual)
        for bound, residual in zip(bounds, residuals)
    )
    return ExactDualIdentity(
        a=a,
        residuals=residuals,
        bounds=bounds,
        rho=rho,
        a_cert=a - rho,
    )


def _numeric_positive_factor(matrix):
    rows = tuple(tuple(float(entry) for entry in row) for row in matrix)
    dimension = len(rows)
    if dimension == 0 or any(len(row) != dimension for row in rows):
        raise ValueError("matrix must be a nonempty square array")
    if any(
        not math.isfinite(entry)
        for row in rows
        for entry in row
    ):
        raise ValueError("matrix contains a non-finite entry")
    for row in range(dimension):
        for column in range(row, dimension):
            if not math.isclose(
                rows[row][column],
                rows[column][row],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("matrix must be symmetric")

    if all(
        rows[row][column] == 0.0
        for row in range(dimension)
        for column in range(dimension)
        if row != column
    ):
        positive_indices = [
            index
            for index in range(dimension)
            if rows[index][index] > 0.0
        ]
        return tuple(
            tuple(
                (
                    math.sqrt(max(rows[row][row], 0.0))
                    if row == source
                    else 0.0
                )
                for source in positive_indices
            )
            for row in range(dimension)
        )

    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "NumPy is required for non-diagonal dual factorization"
        ) from error
    array = np.asarray(rows, dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(
        (array + array.T) / 2.0
    )
    positive = eigenvalues > 0.0
    factor = eigenvectors[:, positive] * np.sqrt(
        eigenvalues[positive]
    )
    return tuple(
        tuple(float(entry) for entry in row)
        for row in factor
    )


def positive_dyadic_factor(
    matrix,
    requested_bits: int,
) -> DyadicFactor:
    """Clamp the numerical dual to its PSD part and round a dyadic factor."""
    if (
        isinstance(requested_bits, bool)
        or not isinstance(requested_bits, int)
        or not 0 <= requested_bits <= 60
    ):
        raise ValueError("requested_bits must satisfy 0 <= bits <= 60")
    numerical_factor = _numeric_positive_factor(matrix)
    rows = len(numerical_factor)
    columns = len(numerical_factor[0]) if rows else 0

    for used_bits in range(requested_bits, -1, -1):
        scale = 1 << used_bits
        numerators = tuple(
            tuple(round(scale * entry) for entry in row)
            for row in numerical_factor
        )
        maximum = max(
            (
                abs(entry)
                for row in numerators
                for entry in row
            ),
            default=0,
        )
        overflow_bound = columns * maximum * maximum
        entries_fit = all(
            -(1 << 63) <= entry < (1 << 63)
            for row in numerators
            for entry in row
        )
        if entries_fit and overflow_bound < 1 << 62:
            return DyadicFactor(
                rows=rows,
                columns=columns,
                requested_bits=requested_bits,
                used_bits=used_bits,
                numerators=numerators,
                storage="int64",
                overflow_bound=overflow_bound,
            )

    scale = 1 << requested_bits
    numerators = tuple(
        tuple(round(scale * entry) for entry in row)
        for row in numerical_factor
    )
    maximum = max(
        (
            abs(entry)
            for row in numerators
            for entry in row
        ),
        default=0,
    )
    return DyadicFactor(
        rows=rows,
        columns=columns,
        requested_bits=requested_bits,
        used_bits=requested_bits,
        numerators=numerators,
        storage="decimal-json",
        overflow_bound=columns * maximum * maximum,
    )


def _encode_fraction(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"missing JSON artifact: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON artifact: {path}") from error


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _safe_file(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError("artifact file must be a basename")
    return directory / name


def _verify_file(
    directory: Path,
    metadata,
    *,
    hash_field="sha256",
    size_field="byte_count",
) -> Path:
    path = _safe_file(directory, metadata["file"])
    if not path.is_file():
        raise FileNotFoundError(f"missing artifact file: {path}")
    if size_field in metadata and path.stat().st_size != int(
        metadata[size_field]
    ):
        raise ValueError(f"artifact byte count mismatch: {path.name}")
    if _sha256_file(path) != str(metadata[hash_field]):
        raise ValueError(f"artifact SHA-256 mismatch: {path.name}")
    return path


def _read_float_matrix(path: Path, dimension: int):
    payload = path.read_bytes()
    expected_bytes = 8 * dimension * dimension
    if len(payload) != expected_bytes:
        raise ValueError("floating dual byte count does not match dimension")
    try:
        import numpy as np
    except ImportError:
        entries = tuple(
            value[0]
            for value in struct.iter_unpack("<d", payload)
        )
        if any(not math.isfinite(value) for value in entries):
            raise ValueError("floating dual contains a non-finite entry")
        return tuple(
            entries[row * dimension:(row + 1) * dimension]
            for row in range(dimension)
        )
    matrix = np.frombuffer(payload, dtype="<f8").reshape(
        dimension,
        dimension,
    ).copy()
    if not np.all(np.isfinite(matrix)):
        raise ValueError("floating dual contains a non-finite entry")
    return matrix


def _load_problem(problem_directory: Path):
    from challenge233.sdp.verify_kyfan_problem import (
        verify_kyfan_problem,
    )

    verify_kyfan_problem(problem_directory)
    manifest_path = problem_directory / "manifest.json"
    manifest = _load_json(manifest_path)
    problem_path = _safe_file(
        problem_directory,
        manifest["problem_file"],
    )
    if _sha256_file(problem_path) != manifest["problem_sha256"]:
        raise ValueError("problem SHA-256 mismatch")
    return (
        _load_json(problem_path),
        manifest,
        _sha256_file(manifest_path),
    )


def _resolve_v2_reference(
    manifest_path: Path,
    reference,
    run_root: Path,
) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("artifact reference must be non-empty")
    relative = Path(reference)
    if relative.is_absolute() or "\\" in reference:
        raise ValueError("artifact reference must be normalized and relative")
    candidate = (manifest_path.parent / relative).resolve()
    root = run_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("artifact reference escapes the run directory")
    if not candidate.is_file():
        raise FileNotFoundError(f"missing bound artifact: {candidate}")
    return candidate


def _load_v2_problem(problem_directory: Path):
    from challenge233.sdp.hierarchy import LOCAL_LEVELS
    from challenge233.sdp.kyfan_presolve import (
        build_kyfan_solver_reduction,
        solver_reduction_payload,
    )
    from challenge233.sdp.kyfan_sparse import (
        build_global_kyfan_structure,
        build_kyfan_instance,
        build_local_kyfan_structure,
    )
    from challenge233.sdp.kyfan_v2_artifact import (
        canonical_json_bytes,
        instance_payload,
        logical_structure_sha256,
    )
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
    if len(problem_directory.parents) < 3:
        raise ValueError("schema-v2 problem directory has no run root")
    run_root = problem_directory.parents[2].resolve()
    verify_bound_kyfan_structure(problem_directory, run_root)
    resolved = {}
    for component, reference_key, hash_key in (
        ("instance", "instance_file", "instance_sha256"),
        ("structure", "structure_reference", "structure_sha256"),
        (
            "structure manifest",
            "structure_manifest_reference",
            "structure_manifest_sha256",
        ),
        ("reduction", "reduction_reference", "reduction_sha256"),
        (
            "reduction manifest",
            "reduction_manifest_reference",
            "reduction_manifest_sha256",
        ),
    ):
        path = _resolve_v2_reference(
            manifest_path,
            manifest[reference_key],
            run_root,
        )
        if _sha256_file(path) != manifest[hash_key]:
            raise ValueError(f"schema-v2 {component} SHA-256 mismatch")
        resolved[component] = path
    verify_kyfan_reduction(resolved["reduction"].parent)
    structure_payload = _load_json(resolved["structure"])
    size = int(structure_payload["size"])
    hierarchy = str(structure_payload["hierarchy"])
    localizer_mode = str(structure_payload["localizer_mode"])
    if hierarchy.startswith("global-d"):
        structure = build_global_kyfan_structure(
            size,
            int(hierarchy.removeprefix("global-d")),
            localizer_mode,
        )
    else:
        levels = {level.name: level for level in LOCAL_LEVELS}
        if hierarchy not in levels:
            raise ValueError("unknown schema-v2 hierarchy")
        structure = build_local_kyfan_structure(
            size,
            levels[hierarchy],
            localizer_mode,
        )
    structure_sha256 = logical_structure_sha256(structure)
    if structure_sha256 != manifest["structure_sha256"]:
        raise ValueError(
            "rebuilt logical structure SHA-256 mismatch"
        )
    reduction = build_kyfan_solver_reduction(
        structure,
        structure_sha256,
    )
    reduction_bytes = canonical_json_bytes(
        solver_reduction_payload(reduction)
    )
    if _sha256_bytes(reduction_bytes) != manifest["reduction_sha256"]:
        raise ValueError("rebuilt solver reduction SHA-256 mismatch")
    instance_raw = _load_json(resolved["instance"])
    detuning = _parse_fraction(instance_raw["detuning"])
    instance = build_kyfan_instance(
        structure,
        detuning,
        trial_manifest=instance_raw["trial_manifest_sha256"],
    )
    rebuilt_instance = canonical_json_bytes(
        instance_payload(instance, structure_sha256)
    )
    if _sha256_bytes(rebuilt_instance) != manifest["instance_sha256"]:
        raise ValueError("rebuilt instance SHA-256 mismatch")
    return {
        "manifest": manifest,
        "manifest_sha256": _sha256_file(manifest_path),
        "structure": structure,
        "instance": instance,
        "reduction": reduction,
        "structure_sha256": structure_sha256,
        "instance_sha256": manifest["instance_sha256"],
        "reduction_sha256": manifest["reduction_sha256"],
        "solver_view": reduction.selected_view,
        "run_root": run_root,
    }


def _load_solver(
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
    file_entries = manifest.get("files", [])
    if len({entry["file"] for entry in file_entries}) != len(
        file_entries
    ):
        raise ValueError("duplicate solver file metadata")
    for metadata in file_entries:
        _verify_file(solver_directory, metadata)

    result = _load_json(result_path)
    if result.get("purpose") != SOLVER_PURPOSE:
        raise ValueError("unexpected solver-result purpose")
    if result.get("success") is not True:
        raise ValueError("solver result does not report success")
    if result.get("problem_sha256") != problem_sha256:
        raise ValueError("solver-result problem SHA-256 mismatch")
    _solver_seed_accuracy(result)
    if result.get("dual_cone") != "triangle-psd":
        raise ValueError("solver did not use the triangular PSD cone")
    if result.get("dual_identity_sign_calibrated") is not True:
        raise ValueError("solver dual identity sign was not calibrated")
    if result.get("offdiagonal_scaling_calibrated") is not True:
        raise ValueError("solver off-diagonal scaling was not calibrated")
    return (
        result,
        manifest,
        _sha256_file(result_path),
        _sha256_file(manifest_path),
    )


def _load_solver_v2(
    solver_directory: Path,
    problem,
):
    manifest_path = solver_directory / "solver-manifest.json"
    manifest = _load_json(manifest_path)
    expected_hashes = {
        "problem_manifest_sha256": problem["manifest_sha256"],
        "structure_sha256": problem["structure_sha256"],
        "instance_sha256": problem["instance_sha256"],
        "reduction_sha256": problem["reduction_sha256"],
        "solver_view": problem["solver_view"],
    }
    if (
        manifest.get("schema_version") != 2
        or manifest.get("purpose")
        != "numerical-ky-fan-solve-manifest"
        or manifest.get("success") is not True
    ):
        raise ValueError("unexpected schema-v2 solver manifest")
    for key, expected in expected_hashes.items():
        if manifest.get(key) != expected:
            raise ValueError(f"schema-v2 solver manifest {key} mismatch")
    result_path = _safe_file(
        solver_directory,
        manifest["solver_result_file"],
    )
    if _sha256_file(result_path) != manifest["solver_result_sha256"]:
        raise ValueError("solver-result SHA-256 mismatch")
    file_entries = tuple(manifest.get("files", ()))
    if len({entry["file"] for entry in file_entries}) != len(
        file_entries
    ):
        raise ValueError("duplicate solver file metadata")
    for metadata in file_entries:
        _verify_file(solver_directory, metadata)
    result = _load_json(result_path)
    if (
        result.get("schema_version") != 2
        or result.get("purpose")
        != "numerical-ky-fan-reduced-dual-v2"
        or result.get("success") is not True
    ):
        raise ValueError("unexpected schema-v2 solver result")
    for key, expected in expected_hashes.items():
        if result.get(key) != expected:
            raise ValueError(f"schema-v2 solver result {key} mismatch")
    _solver_seed_accuracy(result)
    if result.get("dual_cone") != "triangle-psd":
        raise ValueError("unexpected solver dual_cone")
    if result.get("dual_identity_sign_calibrated") is not True:
        raise ValueError("solver dual identity sign was not calibrated")
    if result.get("offdiagonal_scaling_calibrated") is not True:
        raise ValueError("solver off-diagonal scaling was not calibrated")
    loaded_duals = []
    for metadata in result["psd_duals"]:
        if metadata.get("layout") != "row-major":
            raise ValueError("solver PSD dual layout is unsupported")
        if (
            metadata.get("scalar_format")
            != "float64-little-endian"
        ):
            raise ValueError("solver PSD dual scalar format is unsupported")
        dimension = int(metadata["dimension"])
        path = _verify_file(solver_directory, metadata)
        loaded_duals.append(
            {
                **metadata,
                "matrix": _read_float_matrix(path, dimension),
            }
        )
    loaded_result = {
        **result,
        "psd_duals": loaded_duals,
    }
    return (
        loaded_result,
        manifest,
        _sha256_file(result_path),
        _sha256_file(manifest_path),
    )


def _round_decimal_dyadic(text, bits: int) -> Fraction:
    try:
        value = Fraction(Decimal(str(text)))
    except (InvalidOperation, ValueError, ZeroDivisionError) as error:
        raise ValueError("invalid numerical equality multiplier") from error
    denominator = 1 << bits
    numerator = round(value * denominator)
    return Fraction(numerator, denominator)


def _load_trial(trial_directory: Path, size: int, detuning: Fraction):
    from challenge233.sdp.variational_upper import (
        exact_rayleigh_quotient,
    )

    metadata_path = trial_directory / "trial-vector.json"
    metadata = _load_json(metadata_path)
    if metadata.get("purpose") != TRIAL_PURPOSE:
        raise ValueError("unexpected trial-vector purpose")
    if int(metadata.get("size")) != size:
        raise ValueError("trial size does not match problem")
    if _parse_fraction(metadata.get("detuning")) != detuning:
        raise ValueError("trial detuning does not match problem")

    state_path = _safe_file(trial_directory, metadata["state_file"])
    coefficient_path = _safe_file(
        trial_directory,
        metadata["coefficient_file"],
    )
    state_payload = state_path.read_bytes()
    coefficient_payload = coefficient_path.read_bytes()
    if len(state_payload) != int(metadata["state_file_bytes"]):
        raise ValueError("trial state byte count mismatch")
    if len(coefficient_payload) != int(
        metadata["coefficient_file_bytes"]
    ):
        raise ValueError("trial coefficient byte count mismatch")
    if _sha256_bytes(state_payload) != metadata["state_file_sha256"]:
        raise ValueError("trial state SHA-256 mismatch")
    if (
        _sha256_bytes(coefficient_payload)
        != metadata["coefficient_file_sha256"]
    ):
        raise ValueError("trial coefficient SHA-256 mismatch")
    count = int(metadata["nonzero_count"])
    if len(state_payload) != 8 * count:
        raise ValueError("trial state count does not match bytes")
    if len(coefficient_payload) != 8 * count:
        raise ValueError("trial coefficient count does not match bytes")
    states = tuple(
        value[0]
        for value in struct.iter_unpack("<Q", state_payload)
    )
    coefficients = tuple(
        value[0]
        for value in struct.iter_unpack("<q", coefficient_payload)
    )
    b_var = exact_rayleigh_quotient(
        size,
        detuning,
        states,
        coefficients,
    )
    denominator = sum(value * value for value in coefficients)
    numerator = b_var * denominator
    if _parse_fraction(metadata["b_var"]) != b_var:
        raise ValueError("recorded B_var is inconsistent")
    if int(metadata["rayleigh_denominator"]) != denominator:
        raise ValueError("recorded Rayleigh denominator is inconsistent")
    if _parse_fraction(metadata["rayleigh_numerator"]) != numerator:
        raise ValueError("recorded Rayleigh numerator is inconsistent")

    project_root = Path(__file__).resolve().parents[3]
    trusted_relative = metadata["trusted_basis_path"]
    if trusted_relative != "external/1d-basis/pxpbasis.py":
        raise ValueError("unexpected trusted basis path")
    if (
        _sha256_file(project_root / trusted_relative)
        != metadata["trusted_basis_sha256"]
    ):
        raise ValueError("trusted basis SHA-256 mismatch")
    return b_var, metadata, _sha256_file(metadata_path)


def _write_factor(
    output_directory: Path,
    identifier: str,
    factor: DyadicFactor,
):
    _validate_factor(factor)
    if factor.storage == "int64":
        filename = f"factor-{identifier}.i64le"
        payload = bytearray(8 * factor.rows * factor.columns)
        offset = 0
        for row in factor.numerators:
            for entry in row:
                struct.pack_into("<q", payload, offset, entry)
                offset += 8
        scalar_format = "int64-little-endian"
        bytes_payload = bytes(payload)
    else:
        filename = f"factor-{identifier}.bigint.json"
        scalar_format = "decimal-string-json"
        bytes_payload = _json_bytes(
            {
                "rows": [
                    [str(entry) for entry in row]
                    for row in factor.numerators
                ]
            }
        )
    path = output_directory / filename
    _atomic_write(path, bytes_payload)
    return {
        "block": identifier,
        "rows": factor.rows,
        "columns": factor.columns,
        "requested_bits": factor.requested_bits,
        "used_bits": factor.used_bits,
        "storage": factor.storage,
        "layout": "row-major",
        "scalar_format": scalar_format,
        "overflow_bound": str(factor.overflow_bound),
        "file": filename,
        "byte_count": len(bytes_payload),
        "sha256": _sha256_bytes(bytes_payload),
    }


def _build_dual_certificate_v2(
    problem_directory: Path,
    solver_directory: Path,
    trial_directory: Path,
    output_directory: Path,
    *,
    factor_bits: int,
):
    from challenge233.sdp.dual_lift import (
        ExactLiftedIdentity,
        exact_lifted_psd_contribution,
        lift_reduced_duals,
        moment_residual_correction,
        physical_residual_correction,
        reconstruct_equality_multipliers,
    )

    problem = _load_v2_problem(problem_directory)
    solver_result, _, solver_result_sha256, solver_manifest_sha256 = (
        _load_solver_v2(solver_directory, problem)
    )
    factor_orbits = lift_reduced_duals(
        problem["structure"],
        problem["reduction"],
        solver_result,
        factor_bits,
    )
    psd_constant, psd_coefficients = (
        exact_lifted_psd_contribution(
            problem["structure"],
            factor_orbits,
        )
    )
    psd_map = {
        index: coefficient
        for index, coefficient in enumerate(psd_coefficients)
    }
    equality_multipliers = reconstruct_equality_multipliers(
        problem["instance"],
        problem["reduction"],
        psd_map,
    )
    variable_count = len(problem["structure"].variables)
    equality_constant = Fraction(0)
    equality_coefficients = [Fraction(0)] * variable_count
    for row in problem["reduction"].kept_equalities:
        multiplier = equality_multipliers[row.identifier]
        equality_constant += multiplier * row.form.constant
        for variable, coefficient in row.form.terms:
            equality_coefficients[variable] += (
                multiplier * coefficient
            )
    objective = problem["instance"].objective
    objective_coefficients = [Fraction(0)] * variable_count
    for variable, coefficient in objective.terms:
        objective_coefficients[variable] += coefficient
    a = objective.constant - psd_constant - equality_constant
    residual_values = tuple(
        objective_coefficients[index]
        - psd_coefficients[index]
        - equality_coefficients[index]
        for index in range(variable_count)
    )
    residual_map = {
        index: value for index, value in enumerate(residual_values)
    }
    rho_mom = moment_residual_correction(
        residual_map,
        problem["structure"].magnitude_witnesses,
    )
    rho_op = physical_residual_correction(
        problem["structure"].size,
        problem["structure"].variables,
        residual_map,
    )
    rho = min(rho_mom, rho_op)
    residual_route = (
        "pseudo-moment"
        if rho_mom <= rho_op
        else "physical-operator"
    )
    identity = ExactLiftedIdentity(
        a=a,
        residuals=residual_values,
        rho_mom=rho_mom,
        rho_op=rho_op,
        rho=rho,
        residual_route=residual_route,
        a_cert=a - rho,
    )
    size = problem["structure"].size
    detuning = problem["instance"].detuning
    b_var, _, trial_vector_sha256 = _load_trial(
        trial_directory,
        size,
        detuning,
    )
    if (
        trial_vector_sha256
        != problem["instance"].trial_manifest
    ):
        raise ValueError(
            "trial vector does not match the bound schema-v2 instance"
        )
    delta_cert = identity.a_cert - 2 * b_var
    status = "certified" if delta_cert > 0 else "not_certified"

    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(
            "certificate output directory must be empty"
        )
    output_directory.mkdir(parents=True, exist_ok=True)
    solver_duals = {
        item["block"]: item for item in solver_result["psd_duals"]
    }
    reduction_blocks = {
        block.identifier: block
        for block in problem["reduction"].psd_blocks
    }
    factor_metadata = []
    for item in factor_orbits:
        metadata = _write_factor(
            output_directory,
            item.identifier,
            item.factor,
        )
        solver_metadata = solver_duals[item.identifier]
        reduced_block = reduction_blocks[item.identifier]
        metadata.update(
            {
                "weight": _encode_fraction(item.weight),
                "group_images": [
                    {
                        "shift": element.shift,
                        "reflected": element.reflected,
                    }
                    for element in item.group_images
                ],
                "phase_exponents": list(item.phase_exponents),
                "source_block": item.source_block,
                "spatial_block": reduced_block.spatial_block,
                "irrep_label": item.irrep_label,
                "irrep_degree": item.irrep_degree,
                "transform_sha256": solver_metadata[
                    "transform_sha256"
                ],
                "transform_hash_encoding": solver_metadata[
                    "transform_hash_encoding"
                ],
            }
        )
        factor_metadata.append(metadata)

    residuals = {
        "schema_version": 2,
        "purpose": "exact-ky-fan-lifted-dual-residuals",
        "coordinate_system": (
            "non-identity-D_N-invariant-Pauli-moment-orbits"
        ),
        "a": _encode_fraction(identity.a),
        "residuals": [
            {
                "variable": index,
                "value": _encode_fraction(value),
            }
            for index, value in enumerate(identity.residuals)
        ],
        "rho_mom": _encode_fraction(identity.rho_mom),
        "rho_op": _encode_fraction(identity.rho_op),
        "rho": _encode_fraction(identity.rho),
        "residual_route": identity.residual_route,
        "a_cert": _encode_fraction(identity.a_cert),
    }
    residual_path = output_directory / "dual-residuals.json"
    residual_bytes = _json_bytes(residuals)
    _atomic_write(residual_path, residual_bytes)
    residual_sha256 = _sha256_bytes(residual_bytes)
    certificate = {
        "schema_version": 2,
        "purpose": CERTIFICATE_PURPOSE,
        "problem_manifest_sha256": problem["manifest_sha256"],
        "structure_sha256": problem["structure_sha256"],
        "instance_sha256": problem["instance_sha256"],
        "reduction_sha256": problem["reduction_sha256"],
        "solver_result_sha256": solver_result_sha256,
        "solver_manifest_sha256": solver_manifest_sha256,
        "trial_vector_sha256": trial_vector_sha256,
        "solver_view": problem["solver_view"],
        "factor_bits_requested": factor_bits,
        "factor_orbits": factor_metadata,
        "equality_reconstruction": (
            "exact-kept-row-transposed-pivot-system"
        ),
        "equality_multipliers": [
            {
                "identifier": identifier,
                "value": _encode_fraction(value),
            }
            for identifier, value in equality_multipliers.items()
        ],
        "dual_residuals_file": residual_path.name,
        "dual_residuals_sha256": residual_sha256,
        "a": _encode_fraction(identity.a),
        "rho_mom": _encode_fraction(identity.rho_mom),
        "rho_op": _encode_fraction(identity.rho_op),
        "rho": _encode_fraction(identity.rho),
        "residual_route": identity.residual_route,
        "a_cert": _encode_fraction(identity.a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "status": status,
        "solver_diagnostics": {
            key: solver_result.get(key)
            for key in (
                "termination_status",
                "primal_status",
                "dual_status",
                "raw_status",
                "objective",
                "dual_objective",
                "versions",
                "settings",
            )
        },
    }
    certificate_path = output_directory / "certificate.json"
    certificate_bytes = _json_bytes(certificate)
    _atomic_write(certificate_path, certificate_bytes)
    certificate_sha256 = _sha256_bytes(certificate_bytes)
    manifest_files = [
        {
            "file": metadata["file"],
            "byte_count": metadata["byte_count"],
            "sha256": metadata["sha256"],
        }
        for metadata in factor_metadata
    ]
    manifest = {
        "schema_version": 2,
        "purpose": "finite-N-ky-fan-gap-certificate-manifest",
        "problem_directory": os.path.relpath(
            problem_directory,
            output_directory,
        ),
        "solver_directory": os.path.relpath(
            solver_directory,
            output_directory,
        ),
        "trial_directory": os.path.relpath(
            trial_directory,
            output_directory,
        ),
        "problem_manifest_sha256": problem["manifest_sha256"],
        "structure_sha256": problem["structure_sha256"],
        "instance_sha256": problem["instance_sha256"],
        "reduction_sha256": problem["reduction_sha256"],
        "solver_result_sha256": solver_result_sha256,
        "solver_manifest_sha256": solver_manifest_sha256,
        "trial_vector_sha256": trial_vector_sha256,
        "certificate_file": certificate_path.name,
        "certificate_sha256": certificate_sha256,
        "dual_residuals_file": residual_path.name,
        "dual_residuals_sha256": residual_sha256,
        "files": manifest_files,
        "source_file_sha256": {
            relative: _sha256_file(
                Path(__file__).resolve().parents[3] / relative
            )
            for relative in (
                "src/challenge233/sdp/dual_certificate.py",
                "src/challenge233/sdp/dual_lift.py",
                "src/challenge233/sdp/verify_kyfan_certificate.py",
            )
        },
    }
    _atomic_write(output_directory / "manifest.json", _json_bytes(manifest))
    return {
        "status": status,
        "a_cert": _encode_fraction(identity.a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "certificate_sha256": certificate_sha256,
    }


def build_dual_certificate(
    problem_directory,
    solver_directory,
    trial_directory,
    output_directory,
    *,
    factor_bits: int = 30,
    multiplier_bits: int = 40,
):
    """Reconstruct and write one exact residual-corrected gap certificate."""
    if (
        isinstance(factor_bits, bool)
        or not isinstance(factor_bits, int)
        or not 0 <= factor_bits <= 60
    ):
        raise ValueError("factor_bits must satisfy 0 <= bits <= 60")
    if (
        isinstance(multiplier_bits, bool)
        or not isinstance(multiplier_bits, int)
        or not 0 <= multiplier_bits <= 60
    ):
        raise ValueError("multiplier_bits must satisfy 0 <= bits <= 60")
    problem_directory = Path(problem_directory).resolve()
    solver_directory = Path(solver_directory).resolve()
    trial_directory = Path(trial_directory).resolve()
    output_directory = Path(output_directory).resolve()
    problem_manifest = _load_json(problem_directory / "manifest.json")
    if problem_manifest.get("schema_version") == 2:
        return _build_dual_certificate_v2(
            problem_directory,
            solver_directory,
            trial_directory,
            output_directory,
            factor_bits=factor_bits,
        )

    problem, problem_manifest, problem_manifest_sha256 = _load_problem(
        problem_directory
    )
    problem_sha256 = problem_manifest["problem_sha256"]
    solver_result, _, solver_result_sha256, solver_manifest_sha256 = (
        _load_solver(
            solver_directory,
            problem_sha256,
            problem_manifest_sha256,
        )
    )

    block_by_identifier = {
        str(block["identifier"]): block
        for block in problem["psd_blocks"]
    }
    solver_duals = solver_result["psd_duals"]
    if {
        str(metadata["block"]) for metadata in solver_duals
    } != set(block_by_identifier):
        raise ValueError("solver PSD dual inventory does not match problem")
    factors = {}
    for metadata in solver_duals:
        identifier = str(metadata["block"])
        block = block_by_identifier[identifier]
        dimension = int(block["dimension"])
        if int(metadata["dimension"]) != dimension:
            raise ValueError("solver PSD dual dimension mismatch")
        if metadata.get("layout") != "row-major":
            raise ValueError("solver PSD dual layout is not row-major")
        if (
            metadata.get("scalar_format")
            != "float64-little-endian"
        ):
            raise ValueError("solver PSD dual scalar format is unsupported")
        path = _verify_file(solver_directory, metadata)
        numerical = _read_float_matrix(path, dimension)
        factors[identifier] = positive_dyadic_factor(
            numerical,
            factor_bits,
        )

    equality_identifiers = {
        str(row["identifier"]) for row in problem["equalities"]
    }
    numerical_multipliers = solver_result["equality_multipliers"]
    if {
        str(item["identifier"]) for item in numerical_multipliers
    } != equality_identifiers:
        raise ValueError(
            "solver equality multiplier inventory does not match problem"
        )
    equality_multipliers = {
        str(item["identifier"]): _round_decimal_dyadic(
            item["value"],
            multiplier_bits,
        )
        for item in numerical_multipliers
    }
    identity = exact_dual_identity(
        problem,
        factors,
        equality_multipliers,
    )
    size = int(problem["size"])
    detuning = _parse_fraction(problem["detuning"])
    b_var, _, trial_vector_sha256 = _load_trial(
        trial_directory,
        size,
        detuning,
    )
    delta_cert = identity.a_cert - 2 * b_var
    status = "certified" if delta_cert > 0 else "not_certified"

    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(
            "certificate output directory must be empty"
        )
    output_directory.mkdir(parents=True, exist_ok=True)
    factor_metadata = [
        _write_factor(
            output_directory,
            identifier,
            factors[identifier],
        )
        for identifier in block_by_identifier
    ]

    residuals = {
        "schema_version": 1,
        "purpose": "exact-ky-fan-dual-residuals",
        "a": _encode_fraction(identity.a),
        "residuals": [
            {
                "variable": index,
                "value": _encode_fraction(residual),
                "bound": _encode_fraction(identity.bounds[index]),
                "correction": _encode_fraction(
                    identity.bounds[index] * abs(residual)
                ),
            }
            for index, residual in enumerate(identity.residuals)
        ],
        "rho": _encode_fraction(identity.rho),
        "a_cert": _encode_fraction(identity.a_cert),
    }
    residual_path = output_directory / "dual-residuals.json"
    residual_bytes = _json_bytes(residuals)
    _atomic_write(residual_path, residual_bytes)
    residual_sha256 = _sha256_bytes(residual_bytes)

    certificate = {
        "schema_version": 1,
        "purpose": CERTIFICATE_PURPOSE,
        "problem_sha256": problem_sha256,
        "problem_manifest_sha256": problem_manifest_sha256,
        "solver_result_sha256": solver_result_sha256,
        "solver_manifest_sha256": solver_manifest_sha256,
        "trial_vector_sha256": trial_vector_sha256,
        "factor_bits_requested": factor_bits,
        "multiplier_bits": multiplier_bits,
        "factors": factor_metadata,
        "equality_multipliers": [
            {
                "identifier": identifier,
                "value": _encode_fraction(
                    equality_multipliers[identifier]
                ),
            }
            for identifier in equality_multipliers
        ],
        "dual_residuals_file": residual_path.name,
        "dual_residuals_sha256": residual_sha256,
        "a": _encode_fraction(identity.a),
        "rho": _encode_fraction(identity.rho),
        "a_cert": _encode_fraction(identity.a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "status": status,
        "solver_diagnostics": {
            "termination_status": solver_result["termination_status"],
            "primal_status": solver_result["primal_status"],
            "dual_status": solver_result["dual_status"],
            "raw_status": solver_result["raw_status"],
            "objective": solver_result["objective"],
            "dual_objective": solver_result["dual_objective"],
            "versions": solver_result["versions"],
            "settings": solver_result["settings"],
        },
    }
    certificate_path = output_directory / "certificate.json"
    certificate_bytes = _json_bytes(certificate)
    _atomic_write(certificate_path, certificate_bytes)
    certificate_sha256 = _sha256_bytes(certificate_bytes)

    manifest_files = [
        {
            "file": metadata["file"],
            "byte_count": metadata["byte_count"],
            "sha256": metadata["sha256"],
        }
        for metadata in factor_metadata
    ]
    manifest = {
        "schema_version": 1,
        "purpose": "finite-N-ky-fan-gap-certificate-manifest",
        "problem_directory": os.path.relpath(
            problem_directory,
            output_directory,
        ),
        "solver_directory": os.path.relpath(
            solver_directory,
            output_directory,
        ),
        "trial_directory": os.path.relpath(
            trial_directory,
            output_directory,
        ),
        "problem_sha256": problem_sha256,
        "problem_manifest_sha256": problem_manifest_sha256,
        "solver_result_sha256": solver_result_sha256,
        "solver_manifest_sha256": solver_manifest_sha256,
        "trial_vector_sha256": trial_vector_sha256,
        "certificate_file": certificate_path.name,
        "certificate_sha256": certificate_sha256,
        "dual_residuals_file": residual_path.name,
        "dual_residuals_sha256": residual_sha256,
        "files": manifest_files,
        "source_file_sha256": {
            relative: _sha256_file(
                Path(__file__).resolve().parents[3] / relative
            )
            for relative in (
                "src/challenge233/sdp/dual_certificate.py",
                "src/challenge233/sdp/verify_kyfan_certificate.py",
            )
        },
    }
    manifest_path = output_directory / "manifest.json"
    _atomic_write(manifest_path, _json_bytes(manifest))
    return {
        "status": status,
        "a_cert": _encode_fraction(identity.a_cert),
        "b_var": _encode_fraction(b_var),
        "delta_cert": _encode_fraction(delta_cert),
        "certificate_sha256": certificate_sha256,
    }
