from __future__ import annotations

import argparse
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import tempfile
import time

import numpy as np
import scipy
from scipy.optimize import linprog
import sympy as sp
from sympy.polys.polyerrors import PolynomialError

from oracle import __version__
from oracle.fock_basis import QuadraticBasisElement, parity_indices, quadratic_term
from oracle.klein_hodge import overlap_klein_circuit
from oracle.metzler_system import (
    ExactMetzlerSystem,
    compile_metzler_system,
    exact_nonnegative,
    verify_exact_metzler,
)


_WORKER_SYSTEM: ExactMetzlerSystem | None = None
_WORKER_NUMERIC_MATRIX: np.ndarray | None = None


@dataclass(frozen=True)
class OverlapGeometry:
    modes: int
    blocks: tuple[tuple[int, ...], ...]
    ring_edges: tuple[tuple[int, int], ...]
    diagonal_edges: tuple[tuple[int, int], ...]
    bridge_edges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnchorSolve:
    label: str
    sign: int
    status: str
    coefficients: tuple[float, ...]
    min_slack: float | None
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("anchor label must be a nonempty string")
        if (
            not isinstance(self.sign, int)
            or isinstance(self.sign, bool)
            or self.sign not in (-1, 1)
        ):
            raise ValueError("anchor sign must be +1 or -1")
        if self.status not in ("feasible", "infeasible", "error"):
            raise ValueError(
                "anchor solve status must be feasible, infeasible, or error"
            )
        object.__setattr__(
            self,
            "coefficients",
            tuple(float(value) for value in self.coefficients),
        )
        if self.min_slack is not None:
            object.__setattr__(self, "min_slack", float(self.min_slack))
        if not isinstance(self.message, str):
            raise TypeError("anchor solve message must be a string")


@dataclass(frozen=True)
class ExactPrimalCertificate:
    anchor_label: str
    anchor_sign: int
    coefficients: tuple[sp.Expr, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "coefficients",
            tuple(sp.sympify(value) for value in self.coefficients),
        )


@dataclass(frozen=True)
class ExactDualCertificate:
    anchor_label: str
    plus_weights: tuple[sp.Expr, ...]
    minus_weights: tuple[sp.Expr, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "plus_weights",
            tuple(sp.sympify(value) for value in self.plus_weights),
        )
        object.__setattr__(
            self,
            "minus_weights",
            tuple(sp.sympify(value) for value in self.minus_weights),
        )


_GEOMETRY = OverlapGeometry(
    modes=6,
    blocks=((0, 1, 2, 3), (2, 3, 4, 5)),
    ring_edges=(
        (0, 1),
        (0, 3),
        (1, 2),
        (2, 3),
        (2, 5),
        (3, 4),
        (4, 5),
    ),
    diagonal_edges=((0, 2), (1, 3), (2, 4), (3, 5)),
    bridge_edges=((0, 4), (1, 5)),
)


def overlap_geometry() -> OverlapGeometry:
    return _GEOMETRY


def support_edges(mask: str) -> tuple[tuple[int, int], ...]:
    geometry = overlap_geometry()
    masks = {
        "rings": geometry.ring_edges,
        "rings-bridges": geometry.ring_edges + geometry.bridge_edges,
        "rings-diagonals-bridges": (
            geometry.ring_edges
            + geometry.diagonal_edges
            + geometry.bridge_edges
        ),
    }
    try:
        return tuple(sorted(masks[mask]))
    except KeyError as error:
        raise ValueError(f"unknown support mask: {mask}") from error


def _basis_element(
    label: str, kind: str, i: int, j: int
) -> QuadraticBasisElement:
    return QuadraticBasisElement(
        label=label,
        kind=kind,
        i=i,
        j=j,
        fock=quadratic_term(_GEOMETRY.modes, kind, i, j),
    )


def quadratic_basis(
    family: str, mask: str
) -> tuple[QuadraticBasisElement, ...]:
    if family not in ("number-conserving", "bdg"):
        raise ValueError(f"unknown quadratic family: {family}")

    elements = [
        _basis_element(f"n{index}", "hop", index, index)
        for index in range(_GEOMETRY.modes)
    ]
    for i, j in support_edges(mask):
        elements.extend(
            (
                _basis_element(f"h{i}<-{j}", "hop", i, j),
                _basis_element(f"h{j}<-{i}", "hop", j, i),
            )
        )
        if family == "bdg":
            elements.extend(
                (
                    _basis_element(f"pc{i},{j}", "pair_create", i, j),
                    _basis_element(f"pa{i},{j}", "pair_annihilate", i, j),
                )
            )
    return tuple(sorted(elements, key=lambda element: element.label))


def bridge_labels(family: str) -> tuple[str, ...]:
    if family not in ("number-conserving", "bdg"):
        raise ValueError(f"unknown quadratic family: {family}")

    labels: list[str] = []
    for i, j in _GEOMETRY.bridge_edges:
        labels.extend((f"h{i}<-{j}", f"h{j}<-{i}"))
        if family == "bdg":
            labels.extend((f"pc{i},{j}", f"pa{i},{j}"))
    return tuple(sorted(labels))


def build_system(family: str, mask: str) -> ExactMetzlerSystem:
    """Compile the fixed overlapping-Klein transform for one protocol cell."""
    return compile_metzler_system(
        overlap_klein_circuit(),
        quadratic_basis(family, mask),
        parity_indices(_GEOMETRY.modes),
    )


def _initialize_anchor_worker(
    system: ExactMetzlerSystem,
    numeric_matrix: np.ndarray,
) -> None:
    """Install the parent-compiled system in a spawn-safe worker process."""
    _validated_numeric_system_matrix(
        system, numeric_matrix, require_readonly=False
    )
    worker_matrix = np.array(numeric_matrix, dtype=float, order="C", copy=True)
    worker_matrix.setflags(write=False)
    _validated_numeric_system_matrix(system, worker_matrix)
    global _WORKER_SYSTEM, _WORKER_NUMERIC_MATRIX
    _WORKER_SYSTEM = system
    _WORKER_NUMERIC_MATRIX = worker_matrix


def _solve_anchor_worker(task: tuple[str, int]) -> AnchorSolve:
    """Solve one labelled sign problem using the initialized exact system."""
    if _WORKER_SYSTEM is None or _WORKER_NUMERIC_MATRIX is None:
        raise RuntimeError("anchor worker was not initialized")
    label, sign = task
    return _solve_anchor_with_matrix(
        _WORKER_SYSTEM, label, sign, _WORKER_NUMERIC_MATRIX
    )


def _require_worker_count(workers: int) -> None:
    if not isinstance(workers, int) or isinstance(workers, bool) or workers <= 0:
        raise ValueError("workers must be a positive integer")


def validate_blas_thread_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Fail closed unless every BLAS implementation is limited to one thread."""
    source = os.environ if environment is None else environment
    names = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
    settings: dict[str, str] = {}
    for name in names:
        value = source.get(name)
        if value != "1":
            raise ValueError(f"{name} must be set to the string '1'")
        settings[name] = value
    return settings


def execution_metadata(
    *,
    workers: int,
    wall_time_seconds: float,
    thread_settings: Mapping[str, str],
) -> dict[str, object]:
    """Describe non-scientific execution controls kept outside scan payloads."""
    _require_worker_count(workers)
    return {
        "workers": workers,
        "wall_time_seconds": wall_time_seconds,
        "blas_threads": validate_blas_thread_environment(thread_settings),
        "process_start_method": multiprocessing.get_context(
            "spawn"
        ).get_start_method(),
    }


def _normalized_source_commit(source_commit: str) -> str:
    if not isinstance(source_commit, str) or re.fullmatch(
        r"[0-9a-fA-F]{40}", source_commit
    ) is None:
        raise ValueError("source_commit must be exactly 40 hexadecimal characters")
    return source_commit.lower()


def _solve_to_json(solve: AnchorSolve) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": solve.status,
        "solver_message": solve.message,
        "min_slack": solve.min_slack,
    }
    if solve.status == "feasible":
        payload["coefficients"] = list(solve.coefficients)
    return payload


def _attach_exact_primal(
    system: ExactMetzlerSystem,
    solve: AnchorSolve,
    payload: dict[str, object],
) -> bool:
    if solve.status != "feasible":
        return False
    try:
        certificate = reconstruct_exact_primal(system, solve)
        payload["exact_primal_certificate"] = certificate_to_json(certificate)
    except (ArithmeticError, TypeError, ValueError) as error:
        payload["exact_replay_diagnostic"] = f"{type(error).__name__}: {error}"
        return False
    return True


def classify_anchor(
    system: ExactMetzlerSystem,
    label: str,
    *,
    positive_solve: AnchorSolve,
    negative_solve: AnchorSolve,
    numeric_matrix: np.ndarray | None = None,
) -> dict[str, object]:
    """Classify one bridge only after its terminal evidence exactly replays."""
    if positive_solve.label != label or positive_solve.sign != 1:
        raise ValueError("positive solve does not match its anchor")
    if negative_solve.label != label or negative_solve.sign != -1:
        raise ValueError("negative solve does not match its anchor")
    positive = _solve_to_json(positive_solve)
    negative = _solve_to_json(negative_solve)
    positive_primal = _attach_exact_primal(system, positive_solve, positive)
    negative_primal = _attach_exact_primal(system, negative_solve, negative)
    anchor: dict[str, object] = {
        "label": label,
        "positive": positive,
        "negative": negative,
    }
    if positive_primal or negative_primal:
        anchor["classification"] = "certified-feasible"
    elif (
        positive_solve.status == "infeasible"
        and negative_solve.status == "infeasible"
    ):
        try:
            zero_certificate = find_zero_dual(
                system, label, numeric_matrix=numeric_matrix
            )
            if not verify_zero_dual(system, zero_certificate):
                raise ArithmeticError("exact dual certificate did not replay")
            anchor["zero_certificate"] = certificate_to_json(zero_certificate)
            anchor["classification"] = "certified-zero"
        except (ArithmeticError, TypeError, ValueError) as error:
            anchor["dual_replay_diagnostic"] = (
                f"{type(error).__name__}: {error}"
            )
            anchor["classification"] = "numerical-only"
    else:
        anchor["classification"] = "numerical-only"
    return anchor


def _system_metadata(system: ExactMetzlerSystem) -> dict[str, object]:
    geometry = overlap_geometry()
    return {
        "system_shape": [system.coefficients.rows, system.coefficients.cols],
        "exact_field": "Q(sqrt(2))",
        "transform": {
            "name": "overlap_klein_circuit",
            "convention": "right embedded Klein-Hodge gate composed after left",
            "formula": "U = U_[2,3,4,5] U_[0,1,2,3]",
        },
        "geometry": {
            "modes": geometry.modes,
            "blocks": [list(block) for block in geometry.blocks],
            "ring_edges": [list(edge) for edge in geometry.ring_edges],
            "diagonal_edges": [list(edge) for edge in geometry.diagonal_edges],
            "bridge_edges": [list(edge) for edge in geometry.bridge_edges],
        },
    }


def run_anchor_scan(
    family: str,
    mask: str,
    *,
    workers: int,
    source_commit: str,
) -> dict[str, object]:
    """Run the fixed anchor scan and return only deterministic scientific data."""
    _require_worker_count(workers)
    normalized_commit = _normalized_source_commit(source_commit)
    system = build_system(family, mask)
    numeric_matrix = _numeric_system_matrix(system)
    labels = bridge_labels(family)
    tasks = tuple((label, sign) for label in labels for sign in (-1, 1))

    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_initialize_anchor_worker,
        initargs=(system, numeric_matrix),
    ) as executor:
        solves = tuple(executor.map(_solve_anchor_worker, tasks))
    by_label_sign = {
        (solve.label, solve.sign): solve
        for solve in solves
    }

    anchors: list[dict[str, object]] = []
    for label in labels:
        negative_solve = by_label_sign[(label, -1)]
        positive_solve = by_label_sign[(label, 1)]
        anchors.append(
            classify_anchor(
                system,
                label,
                positive_solve=positive_solve,
                negative_solve=negative_solve,
                numeric_matrix=numeric_matrix,
            )
        )

    return {
        "schema_version": 1,
        "protocol": "overlap-klein-v1",
        "source_commit": normalized_commit,
        "family": family,
        "mask": mask,
        "anchor_count": len(anchors),
        "system": _system_metadata(system),
        "package_versions": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sympy": sp.__version__,
            "oracle": __version__,
        },
        "anchors": anchors,
    }


def write_result(payload: Mapping[str, object], output: Path) -> None:
    """Write a replay payload as sorted UTF-8 JSON without torn final files."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(serialized)
        Path(temporary_name).replace(destination)
    finally:
        if temporary_name is not None:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()


def _require_system(system: ExactMetzlerSystem) -> None:
    if not isinstance(system, ExactMetzlerSystem):
        raise TypeError("system must be an ExactMetzlerSystem")


def _anchor_index(system: ExactMetzlerSystem, label: str) -> int:
    if not isinstance(label, str) or label not in system.labels:
        raise ValueError(f"unknown anchor label: {label!r}")
    return system.labels.index(label)


def _require_sign(sign: int) -> None:
    if (
        not isinstance(sign, int)
        or isinstance(sign, bool)
        or sign not in (-1, 1)
    ):
        raise ValueError("anchor sign must be +1 or -1")


def _q_sqrt_two_coefficients(
    expression: sp.Expr,
) -> tuple[sp.Rational, sp.Rational]:
    value = sp.sympify(expression)
    if (
        value.has(sp.Float)
        or value.is_number is not True
        or value.is_real is not True
        or value.is_finite is not True
    ):
        raise ValueError("number must be exact, real, and in Q(sqrt(2))")

    normalized = sp.expand(sp.radsimp(value))
    generator = sp.sqrt(2)
    indeterminate = sp.Dummy("sqrt_two")
    lifted = normalized.xreplace({generator: indeterminate})
    try:
        polynomial = sp.Poly(lifted, indeterminate, domain="EX")
    except PolynomialError as error:
        raise ValueError("number must lie in Q(sqrt(2))") from error
    if polynomial.degree() > 1:
        raise ValueError("number must lie in Q(sqrt(2))")

    a = sp.simplify(polynomial.nth(0))
    b = sp.simplify(polynomial.nth(1))
    residual = sp.simplify(value - a - b * generator)
    if (
        residual != 0
        or a.is_Rational is not True
        or b.is_Rational is not True
    ):
        raise ValueError("number must lie in Q(sqrt(2))")
    return sp.Rational(a), sp.Rational(b)


def _q_sqrt_two_to_float(expression: sp.Expr) -> float:
    """Evaluate an exact Q(sqrt(2)) scalar without SymPy/mpmath floats."""
    a, b = _q_sqrt_two_coefficients(expression)
    return (
        int(a.p) / int(a.q)
        + (int(b.p) / int(b.q)) * math.sqrt(2.0)
    )


def _normalized_q_sqrt_two(
    expression: sp.Expr,
    *,
    max_denominator: int | None = None,
) -> sp.Expr:
    a, b = _q_sqrt_two_coefficients(expression)
    if max_denominator is not None and (
        a.q > max_denominator or b.q > max_denominator
    ):
        raise ArithmeticError(
            "reconstructed Q(sqrt(2)) coefficient exceeds "
            "the denominator limit"
        )
    return sp.simplify(a + b * sp.sqrt(2))


def _validate_system_field(system: ExactMetzlerSystem) -> None:
    for value in system.coefficients:
        _q_sqrt_two_coefficients(value)


def _numeric_system_matrix(
    system: ExactMetzlerSystem,
) -> np.ndarray:
    """Convert only stored exact coefficients to an immutable C-order matrix."""
    _require_system(system)
    values = np.zeros(system.coefficients.shape, dtype=float, order="C")
    for (row, column), value in system.coefficients.todok().items():
        values[row, column] = _q_sqrt_two_to_float(value)
    values.setflags(write=False)
    return values


def _validated_numeric_system_matrix(
    system: ExactMetzlerSystem,
    matrix: np.ndarray,
    *,
    require_readonly: bool = True,
) -> np.ndarray:
    if not isinstance(matrix, np.ndarray):
        raise TypeError("numeric system matrix must be a NumPy array")
    if matrix.shape != system.coefficients.shape:
        raise ValueError("numeric system matrix has the wrong shape")
    if not matrix.flags.c_contiguous or (
        require_readonly and matrix.flags.writeable
    ):
        raise ValueError("numeric system matrix must be C-contiguous and read-only")
    if not np.issubdtype(matrix.dtype, np.floating) or not np.all(
        np.isfinite(matrix)
    ):
        raise ValueError("numeric system matrix must be finite floating-point data")
    return matrix


def _empty_anchor_result(
    label: str, sign: int, status: str, message: str
) -> AnchorSolve:
    return AnchorSolve(
        label=label,
        sign=sign,
        status=status,
        coefficients=(),
        min_slack=None,
        message=message,
    )


def solve_anchor(
    system: ExactMetzlerSystem, anchor_label: str, sign: int
) -> AnchorSolve:
    _require_system(system)
    _anchor_index(system, anchor_label)
    _require_sign(sign)
    _validate_system_field(system)
    try:
        matrix = _numeric_system_matrix(system)
    except Exception as error:
        return _empty_anchor_result(
            anchor_label,
            sign,
            "error",
            f"{type(error).__name__}: {error}",
        )
    return _solve_anchor_with_matrix(system, anchor_label, sign, matrix)


def _solve_anchor_with_matrix(
    system: ExactMetzlerSystem,
    anchor_label: str,
    sign: int,
    matrix: np.ndarray,
) -> AnchorSolve:
    _require_system(system)
    anchor = _anchor_index(system, anchor_label)
    _require_sign(sign)
    _validate_system_field(system)

    try:
        matrix = _validated_numeric_system_matrix(system, matrix)
        variables = len(system.labels)
        equality = np.zeros((1, variables), dtype=float)
        equality[0, anchor] = 1.0
        if matrix.shape[0]:
            inequalities: np.ndarray | None = -matrix
            inequality_rhs: np.ndarray | None = np.zeros(
                matrix.shape[0], dtype=float
            )
        else:
            inequalities = None
            inequality_rhs = None
        result = linprog(
            c=np.zeros(variables, dtype=float),
            A_ub=inequalities,
            b_ub=inequality_rhs,
            A_eq=equality,
            b_eq=np.array([float(sign)]),
            bounds=[(None, None)] * variables,
            method="highs",
        )
    except Exception as error:
        return _empty_anchor_result(
            anchor_label,
            sign,
            "error",
            f"{type(error).__name__}: {error}",
        )

    if result.status == 2:
        return _empty_anchor_result(
            anchor_label, sign, "infeasible", str(result.message)
        )
    if not result.success or result.status != 0 or result.x is None:
        return _empty_anchor_result(
            anchor_label, sign, "error", str(result.message)
        )

    coefficients = np.asarray(result.x, dtype=float)
    if coefficients.shape != (variables,) or not np.all(
        np.isfinite(coefficients)
    ):
        return _empty_anchor_result(
            anchor_label,
            sign,
            "error",
            "solver returned nonfinite or malformed coefficients",
        )
    slacks = matrix @ coefficients
    min_slack = float(np.min(slacks)) if slacks.size else math.inf
    if (not math.isfinite(min_slack) and slacks.size) or min_slack < -1e-9:
        return _empty_anchor_result(
            anchor_label,
            sign,
            "error",
            f"nominal solution has minimum slack {min_slack!r}",
        )
    if abs(coefficients[anchor] - sign) > 1e-8:
        return _empty_anchor_result(
            anchor_label,
            sign,
            "error",
            "nominal solution violates the anchor equality",
        )
    return AnchorSolve(
        label=anchor_label,
        sign=sign,
        status="feasible",
        coefficients=tuple(float(value) for value in coefficients),
        min_slack=min_slack,
        message=str(result.message),
    )


def _require_denominator_limit(max_denominator: int) -> None:
    if (
        not isinstance(max_denominator, int)
        or isinstance(max_denominator, bool)
        or max_denominator <= 0
    ):
        raise ValueError("max_denominator must be a positive integer")


def _reconstruct_float(
    value: float, *, max_denominator: int | None
) -> sp.Expr:
    if not math.isfinite(value):
        raise ArithmeticError("cannot reconstruct a nonfinite coefficient")
    tolerance = 1e-10
    nearest_integer = round(value)
    if abs(value - nearest_integer) <= tolerance:
        candidate = sp.Integer(nearest_integer)
    else:
        try:
            candidate = sp.nsimplify(
                value,
                [sp.sqrt(2)],
                tolerance=tolerance,
                full=True,
            )
        except Exception as error:
            raise ArithmeticError(
                "SymPy failed to reconstruct the coefficient in Q(sqrt(2))"
            ) from error
    try:
        normalized = _normalized_q_sqrt_two(
            candidate, max_denominator=max_denominator
        )
    except ValueError as error:
        raise ArithmeticError(
            "coefficient did not reconstruct in Q(sqrt(2))"
        ) from error
    if (
        abs(_q_sqrt_two_to_float(normalized) - value)
        > 1e-9 * max(1.0, abs(value))
    ):
        raise ArithmeticError(
            "exact reconstruction does not match the numerical coefficient"
        )
    return normalized


def reconstruct_exact_primal(
    system: ExactMetzlerSystem,
    solve: AnchorSolve,
    max_denominator: int = 10000,
) -> ExactPrimalCertificate:
    _require_system(system)
    _require_denominator_limit(max_denominator)
    _validate_system_field(system)
    if not isinstance(solve, AnchorSolve):
        raise TypeError("solve must be an AnchorSolve")
    anchor = _anchor_index(system, solve.label)
    _require_sign(solve.sign)
    if solve.status != "feasible":
        raise ArithmeticError("anchor solve is not feasible")
    if len(solve.coefficients) != len(system.labels):
        raise ArithmeticError("anchor solve has the wrong coefficient count")
    if any(not math.isfinite(value) for value in solve.coefficients):
        raise ArithmeticError("anchor solve contains nonfinite coefficients")
    if abs(solve.coefficients[anchor] - solve.sign) > 1e-8:
        raise ArithmeticError("anchor solve does not satisfy its anchor")

    exact = tuple(
        sp.Integer(solve.sign)
        if index == anchor
        else _reconstruct_float(value, max_denominator=max_denominator)
        for index, value in enumerate(solve.coefficients)
    )
    certificate = ExactPrimalCertificate(
        anchor_label=solve.label,
        anchor_sign=solve.sign,
        coefficients=exact,
    )
    if not verify_primal(system, certificate):
        raise ArithmeticError(
            "reconstructed coefficients do not satisfy the exact Metzler cone"
        )
    return certificate


def verify_primal(
    system: ExactMetzlerSystem,
    certificate: ExactPrimalCertificate,
) -> bool:
    if not isinstance(system, ExactMetzlerSystem) or not isinstance(
        certificate, ExactPrimalCertificate
    ):
        return False
    try:
        anchor = _anchor_index(system, certificate.anchor_label)
        _require_sign(certificate.anchor_sign)
        _validate_system_field(system)
        coefficients = tuple(
            _normalized_q_sqrt_two(value)
            for value in certificate.coefficients
        )
        if len(coefficients) != len(system.labels):
            return False
        if (
            sp.simplify(
                coefficients[anchor] - certificate.anchor_sign
            )
            != 0
        ):
            return False
        return verify_exact_metzler(system, coefficients)
    except (ArithmeticError, TypeError, ValueError):
        return False


def _dual_identity_holds(
    system: ExactMetzlerSystem,
    weights: tuple[sp.Expr, ...],
    target: sp.ImmutableMatrix,
) -> bool:
    if len(weights) != len(system.rows):
        return False
    try:
        normalized = tuple(
            _normalized_q_sqrt_two(weight) for weight in weights
        )
        if any(not exact_nonnegative(weight) for weight in normalized):
            return False
    except ValueError:
        return False
    observed = system.coefficients.T * sp.ImmutableMatrix(normalized)
    return all(
        sp.simplify(observed[index] - target[index]) == 0
        for index in range(target.rows)
    )


def _numeric_dual(
    system: ExactMetzlerSystem,
    *,
    anchor: int,
    sign: int,
    numeric_matrix: np.ndarray | None = None,
) -> np.ndarray:
    matrix = _validated_numeric_system_matrix(
        system,
        _numeric_system_matrix(system)
        if numeric_matrix is None
        else numeric_matrix,
    )
    row_count = len(system.rows)
    target = np.zeros(len(system.labels), dtype=float)
    target[anchor] = float(sign)
    if row_count == 0:
        raise ArithmeticError("dual feasibility problem has no rows")
    try:
        result = linprog(
            c=np.zeros(row_count, dtype=float),
            A_eq=matrix.T,
            b_eq=target,
            bounds=[(0.0, None)] * row_count,
            method="highs",
        )
    except Exception as error:
        raise ArithmeticError(
            f"dual solver error: {type(error).__name__}: {error}"
        ) from error
    if result.status == 2:
        raise ArithmeticError(
            f"dual identity is infeasible: {result.message}"
        )
    if not result.success or result.status != 0 or result.x is None:
        raise ArithmeticError(f"dual solver error: {result.message}")

    weights = np.asarray(result.x, dtype=float)
    if weights.shape != (row_count,) or not np.all(np.isfinite(weights)):
        raise ArithmeticError("dual solver returned malformed weights")
    if float(np.min(weights)) < -1e-9:
        raise ArithmeticError("dual solver returned a negative weight")
    residual = matrix.T @ weights - target
    if np.max(np.abs(residual), initial=0.0) > 1e-8:
        raise ArithmeticError("dual solver returned an inaccurate identity")
    return weights


def _fit_free_parameters(
    expressions: tuple[sp.Expr, ...],
    parameters: tuple[sp.Symbol, ...],
    numerical: np.ndarray,
    *,
    max_denominator: int | None,
) -> dict[sp.Symbol, sp.Expr]:
    zero_substitution = {parameter: sp.Integer(0) for parameter in parameters}
    particular = np.array(
        [
            _q_sqrt_two_to_float(expression.subs(zero_substitution))
            for expression in expressions
        ]
    )
    directions = np.array(
        [
            [
                _q_sqrt_two_to_float(sp.diff(expression, parameter))
                for parameter in parameters
            ]
            for expression in expressions
        ],
        dtype=float,
    )
    fitted, *_ = np.linalg.lstsq(
        directions, numerical - particular, rcond=None
    )
    return {
        parameter: _reconstruct_float(
            float(value), max_denominator=max_denominator
        )
        for parameter, value in zip(parameters, fitted, strict=True)
    }


def _reconstruct_dual_weights(
    system: ExactMetzlerSystem,
    numerical: np.ndarray,
    target: sp.ImmutableMatrix,
) -> tuple[sp.Expr, ...]:
    try:
        direct = tuple(
            _reconstruct_float(float(value), max_denominator=None)
            for value in numerical
        )
    except ArithmeticError:
        direct = ()
    if direct and _dual_identity_holds(system, direct, target):
        return direct

    raw_positive = tuple(
        index for index, value in enumerate(numerical) if value > 0
    )
    expanded = tuple(
        index for index, value in enumerate(numerical) if value != 0
    )
    all_rows = tuple(range(len(system.rows)))
    supports: list[tuple[int, ...]] = []
    for support in (raw_positive, expanded, all_rows):
        if support and support not in supports:
            supports.append(support)

    for active in supports:
        exact_matrix = system.coefficients.T.extract(
            range(len(system.labels)), active
        )
        solution_set = sp.linsolve((exact_matrix, target))
        if solution_set == sp.EmptySet:
            continue
        expressions = tuple(next(iter(solution_set)))
        parameters = tuple(
            sorted(
                set().union(
                    *(expression.free_symbols for expression in expressions)
                ),
                key=str,
            )
        )
        substitutions: list[dict[sp.Symbol, sp.Expr]] = []
        if parameters:
            try:
                substitutions.append(
                    _fit_free_parameters(
                        expressions,
                        parameters,
                        numerical[np.array(active)],
                        max_denominator=None,
                    )
                )
            except (ArithmeticError, TypeError, ValueError):
                pass
            substitutions.append(
                {parameter: sp.Integer(0) for parameter in parameters}
            )
        else:
            substitutions.append({})

        for substitution in substitutions:
            try:
                support_values = tuple(
                    _normalized_q_sqrt_two(
                        expression.subs(substitution)
                    )
                    for expression in expressions
                )
            except (ArithmeticError, ValueError):
                continue
            candidate = [sp.Integer(0)] * len(system.rows)
            for index, value in zip(active, support_values, strict=True):
                candidate[index] = value
            exact = tuple(candidate)
            if _dual_identity_holds(system, exact, target):
                return exact
    raise ArithmeticError(
        "dual support could not be reconstructed as a nonnegative "
        "Q(sqrt(2)) identity"
    )


def find_zero_dual(
    system: ExactMetzlerSystem,
    anchor_label: str,
    *,
    numeric_matrix: np.ndarray | None = None,
) -> ExactDualCertificate:
    _require_system(system)
    anchor = _anchor_index(system, anchor_label)
    _validate_system_field(system)
    matrix = _validated_numeric_system_matrix(
        system,
        _numeric_system_matrix(system)
        if numeric_matrix is None
        else numeric_matrix,
    )
    exact_weights: list[tuple[sp.Expr, ...]] = []
    for sign in (1, -1):
        target_values = [sp.Integer(0)] * len(system.labels)
        target_values[anchor] = sp.Integer(sign)
        target = sp.ImmutableMatrix(target_values)
        numerical = _numeric_dual(
            system,
            anchor=anchor,
            sign=sign,
            numeric_matrix=matrix,
        )
        exact_weights.append(
            _reconstruct_dual_weights(system, numerical, target)
        )

    certificate = ExactDualCertificate(
        anchor_label=anchor_label,
        plus_weights=exact_weights[0],
        minus_weights=exact_weights[1],
    )
    if not verify_zero_dual(system, certificate):
        raise ArithmeticError("reconstructed dual certificate is not exact")
    return certificate


def verify_zero_dual(
    system: ExactMetzlerSystem,
    certificate: ExactDualCertificate,
) -> bool:
    if not isinstance(system, ExactMetzlerSystem) or not isinstance(
        certificate, ExactDualCertificate
    ):
        return False
    try:
        anchor = _anchor_index(system, certificate.anchor_label)
        _validate_system_field(system)
    except (TypeError, ValueError):
        return False
    plus_target = [sp.Integer(0)] * len(system.labels)
    minus_target = [sp.Integer(0)] * len(system.labels)
    plus_target[anchor] = sp.Integer(1)
    minus_target[anchor] = sp.Integer(-1)
    return _dual_identity_holds(
        system,
        certificate.plus_weights,
        sp.ImmutableMatrix(plus_target),
    ) and _dual_identity_holds(
        system,
        certificate.minus_weights,
        sp.ImmutableMatrix(minus_target),
    )


def _canonical_q_sqrt_two(expression: sp.Expr) -> str:
    serialized = sp.sstr(_normalized_q_sqrt_two(expression))
    if len(serialized) > 256:
        raise ValueError("canonical certificate number is too long")
    return serialized


def _parse_canonical_q_sqrt_two(value: object) -> sp.Expr:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("certificate numbers must be short strings")
    remainder = value.replace("sqrt(2)", "")
    if "sqrt" in remainder or "**" in remainder:
        raise ValueError("certificate number is outside the generated grammar")
    if any(
        character not in "0123456789+-*/() "
        for character in remainder
    ):
        raise ValueError("certificate number is outside the generated grammar")
    try:
        expression = sp.sympify(value, locals={"sqrt": sp.sqrt})
        normalized = _normalized_q_sqrt_two(expression)
    except Exception as error:
        raise ValueError(
            "certificate number is not in Q(sqrt(2))"
        ) from error
    if value != _canonical_q_sqrt_two(normalized):
        raise ValueError("certificate number is not in canonical form")
    return normalized


def certificate_to_json(
    certificate: ExactPrimalCertificate | ExactDualCertificate,
) -> dict[str, object]:
    if isinstance(certificate, ExactPrimalCertificate):
        _require_sign(certificate.anchor_sign)
        if (
            not isinstance(certificate.anchor_label, str)
            or not certificate.anchor_label
        ):
            raise ValueError("certificate anchor label must be nonempty")
        return {
            "kind": "primal",
            "anchor_label": certificate.anchor_label,
            "anchor_sign": certificate.anchor_sign,
            "coefficients": [
                _canonical_q_sqrt_two(value)
                for value in certificate.coefficients
            ],
        }
    if isinstance(certificate, ExactDualCertificate):
        if (
            not isinstance(certificate.anchor_label, str)
            or not certificate.anchor_label
        ):
            raise ValueError("certificate anchor label must be nonempty")
        if any(
            not exact_nonnegative(value)
            for value in certificate.plus_weights
            + certificate.minus_weights
        ):
            raise ValueError("dual certificate weights must be nonnegative")
        return {
            "kind": "dual",
            "anchor_label": certificate.anchor_label,
            "plus_weights": [
                _canonical_q_sqrt_two(value)
                for value in certificate.plus_weights
            ],
            "minus_weights": [
                _canonical_q_sqrt_two(value)
                for value in certificate.minus_weights
            ],
        }
    raise TypeError("unsupported certificate type")


def _require_payload_keys(
    payload: Mapping[str, object], expected: set[str]
) -> None:
    if set(payload) != expected:
        raise ValueError("certificate payload has unexpected or missing fields")


def _parse_number_list(value: object, *, expected: int) -> tuple[sp.Expr, ...]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError("certificate numeric list has the wrong length")
    return tuple(_parse_canonical_q_sqrt_two(item) for item in value)


def certificate_from_json(
    payload: Mapping[str, object],
    system: ExactMetzlerSystem,
) -> ExactPrimalCertificate | ExactDualCertificate:
    _require_system(system)
    _validate_system_field(system)
    if not isinstance(payload, Mapping):
        raise ValueError("certificate payload must be a JSON object")
    kind = payload.get("kind")
    if kind == "primal":
        _require_payload_keys(
            payload,
            {"kind", "anchor_label", "anchor_sign", "coefficients"},
        )
        anchor_label = payload["anchor_label"]
        anchor_sign = payload["anchor_sign"]
        if not isinstance(anchor_label, str):
            raise ValueError("certificate anchor label must be a string")
        _anchor_index(system, anchor_label)
        _require_sign(anchor_sign)  # type: ignore[arg-type]
        certificate: ExactPrimalCertificate | ExactDualCertificate = (
            ExactPrimalCertificate(
                anchor_label=anchor_label,
                anchor_sign=anchor_sign,  # type: ignore[arg-type]
                coefficients=_parse_number_list(
                    payload["coefficients"],
                    expected=len(system.labels),
                ),
            )
        )
        if not verify_primal(system, certificate):
            raise ValueError("primal certificate does not verify")
        return certificate
    if kind == "dual":
        _require_payload_keys(
            payload,
            {"kind", "anchor_label", "plus_weights", "minus_weights"},
        )
        anchor_label = payload["anchor_label"]
        if not isinstance(anchor_label, str):
            raise ValueError("certificate anchor label must be a string")
        _anchor_index(system, anchor_label)
        certificate = ExactDualCertificate(
            anchor_label=anchor_label,
            plus_weights=_parse_number_list(
                payload["plus_weights"], expected=len(system.rows)
            ),
            minus_weights=_parse_number_list(
                payload["minus_weights"], expected=len(system.rows)
            ),
        )
        if not verify_zero_dual(system, certificate):
            raise ValueError("dual certificate does not verify")
        return certificate
    raise ValueError(f"unknown certificate kind: {kind!r}")


def _cli_worker_count(value: str) -> int:
    try:
        workers = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "workers must be a positive integer"
        ) from error
    try:
        _require_worker_count(workers)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return workers


def _cli_source_commit(value: str) -> str:
    try:
        return _normalized_source_commit(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the preregistered overlapping Klein-cone anchor scan."
    )
    parser.add_argument(
        "--family", choices=("number-conserving", "bdg"), required=True
    )
    parser.add_argument(
        "--mask",
        choices=("rings-bridges", "rings-diagonals-bridges"),
        required=True,
    )
    parser.add_argument("--workers", type=_cli_worker_count, required=True)
    parser.add_argument(
        "--source-commit", type=_cli_source_commit, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        thread_settings = validate_blas_thread_environment()
    except ValueError as error:
        parser.error(str(error))

    started = time.perf_counter()
    result = run_anchor_scan(
        args.family,
        args.mask,
        workers=args.workers,
        source_commit=args.source_commit,
    )
    result["execution"] = execution_metadata(
        workers=args.workers,
        wall_time_seconds=time.perf_counter() - started,
        thread_settings=thread_settings,
    )
    write_result(result, args.output)


if __name__ == "__main__":
    main()
