from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import linprog
import sympy as sp
from sympy.polys.polyerrors import PolynomialError

from oracle.fock_basis import QuadraticBasisElement, quadratic_term
from oracle.metzler_system import (
    ExactMetzlerSystem,
    exact_nonnegative,
    numeric_coefficients,
    verify_exact_metzler,
)


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
    anchor = _anchor_index(system, anchor_label)
    _require_sign(sign)
    _validate_system_field(system)

    try:
        matrix = numeric_coefficients(system)
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
    value: float, *, max_denominator: int
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
    if abs(float(normalized) - value) > 1e-9 * max(1.0, abs(value)):
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
        _reconstruct_float(value, max_denominator=max_denominator)
        for value in solve.coefficients
    )
    exact = exact[:anchor] + (sp.Integer(solve.sign),) + exact[anchor + 1 :]
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
) -> np.ndarray:
    matrix = numeric_coefficients(system)
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
    return np.where(np.abs(weights) <= 1e-10, 0.0, weights)


def _fit_free_parameters(
    expressions: tuple[sp.Expr, ...],
    parameters: tuple[sp.Symbol, ...],
    numerical: np.ndarray,
    *,
    max_denominator: int,
) -> dict[sp.Symbol, sp.Expr]:
    zero_substitution = {parameter: sp.Integer(0) for parameter in parameters}
    particular = np.array(
        [float(expression.subs(zero_substitution)) for expression in expressions]
    )
    directions = np.array(
        [
            [float(sp.diff(expression, parameter)) for parameter in parameters]
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
    *,
    max_denominator: int = 10000,
) -> tuple[sp.Expr, ...]:
    _require_denominator_limit(max_denominator)

    try:
        direct = tuple(
            _reconstruct_float(float(value), max_denominator=max_denominator)
            for value in numerical
        )
    except ArithmeticError:
        direct = ()
    if direct and _dual_identity_holds(system, direct, target):
        return direct

    active = tuple(
        index for index, value in enumerate(numerical) if value > 1e-10
    )
    if not active:
        raise ArithmeticError("dual support reconstruction is empty")
    exact_matrix = system.coefficients.T.extract(
        range(len(system.labels)), active
    )
    solution_set = sp.linsolve((exact_matrix, target))
    if solution_set == sp.EmptySet:
        raise ArithmeticError(
            "numerical dual support has no exact solution"
        )
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
                    max_denominator=max_denominator,
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
                    expression.subs(substitution),
                    max_denominator=max_denominator,
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
    system: ExactMetzlerSystem, anchor_label: str
) -> ExactDualCertificate:
    _require_system(system)
    anchor = _anchor_index(system, anchor_label)
    _validate_system_field(system)
    exact_weights: list[tuple[sp.Expr, ...]] = []
    for sign in (1, -1):
        target_values = [sp.Integer(0)] * len(system.labels)
        target_values[anchor] = sp.Integer(sign)
        target = sp.ImmutableMatrix(target_values)
        numerical = _numeric_dual(system, anchor=anchor, sign=sign)
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
    return sp.sstr(_normalized_q_sqrt_two(expression))


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
