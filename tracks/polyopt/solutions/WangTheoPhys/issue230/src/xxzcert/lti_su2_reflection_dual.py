"""Matrix-free log-det dual solver for joint SU(2)-reflection LTI."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.sparse.linalg import LinearOperator, cg

from .lti_su2 import su2_multiplicity_bases
from .lti_su2_reflection import (
    SU2ReflectionLTICandidate,
    su2_reflection_bases,
)
from .lti_u1 import _selection, sector_basis
from .model import finite_xxz


@dataclass(frozen=True)
class DualMapContribution:
    constraint_index: int
    weight: float
    even_map: NDArray[np.float64]
    odd_map: NDArray[np.float64]


@dataclass(frozen=True)
class SU2ReflectionDualModel:
    level: int
    objective_blocks: tuple[NDArray[np.float64], ...]
    contributions: tuple[tuple[DualMapContribution, ...], ...]
    constraint_shapes: tuple[tuple[int, int], ...]
    block_dimensions: tuple[tuple[int, int], ...]

    @property
    def parameter_count(self) -> int:
        return 1 + sum(rows * columns for rows, columns in self.constraint_shapes)

    def unpack(
        self, parameters: NDArray[np.float64]
    ) -> tuple[float, tuple[NDArray[np.float64], ...]]:
        if parameters.shape != (self.parameter_count,):
            raise ValueError("dual parameter vector has the wrong size")
        offset = 1
        duals: list[NDArray[np.float64]] = []
        for rows, columns in self.constraint_shapes:
            size = rows * columns
            duals.append(
                parameters[offset : offset + size].reshape(rows, columns)
            )
            offset += size
        return float(parameters[0]), tuple(duals)


def build_su2_reflection_dual_model(
    level: int,
) -> SU2ReflectionDualModel:
    """Build reduced maps without flattening them into a conic matrix."""
    if level < 2:
        raise ValueError("level must be at least two")
    twice_js, bases_by_j = su2_multiplicity_bases(level)
    parity_twice_js, parity_by_j = su2_reflection_bases(level)
    if twice_js != parity_twice_js:
        raise ArithmeticError("inconsistent SU(2) parity sectors")

    two_site = finite_xxz(1.0, 2, periodic=False).real
    first_bond = np.kron(two_site, np.eye(1 << (level - 2)))
    last_bond = np.kron(np.eye(1 << (level - 2)), two_site)
    objective_full = (first_bond + last_bond) / 2

    objective_blocks: list[NDArray[np.float64]] = []
    block_dimensions: list[tuple[int, int]] = []
    sector_components: list[
        list[tuple[int, NDArray[np.float64], int]]
    ] = [[] for _ in range(level + 1)]
    for twice_j, sectors, parity in zip(
        twice_js, bases_by_j, parity_by_j, strict=True
    ):
        block_dimensions.append(
            (parity.even.shape[1], parity.odd.shape[1])
        )
        weight = 1 / (twice_j + 1)
        for transform in (parity.even, parity.odd):
            if transform.shape[1] == 0:
                continue
            block_index = len(objective_blocks)
            objective = np.zeros(
                (transform.shape[1], transform.shape[1])
            )
            for ones, basis in enumerate(sectors):
                if basis is None:
                    continue
                adapted = basis @ transform
                computational = sector_basis(level, ones)
                objective += weight * (
                    adapted.T
                    @ objective_full[np.ix_(computational, computational)]
                    @ adapted
                )
                sector_components[ones].append(
                    (block_index, adapted, twice_j)
                )
            objective_blocks.append((objective + objective.T) / 2)

    reduced_twice_js, reduced_bases_by_j = su2_multiplicity_bases(
        level - 1
    )
    parity_reduced_twice_js, reduced_parity_by_j = su2_reflection_bases(
        level - 1
    )
    if reduced_twice_js != parity_reduced_twice_js:
        raise ArithmeticError("inconsistent reduced parity sectors")
    constraint_shapes: list[tuple[int, int]] = []
    contributions: list[list[DualMapContribution]] = [
        [] for _ in objective_blocks
    ]
    for constraint_index, (
        reduced_twice_j,
        reduced_sectors,
        reduced_parity,
    ) in enumerate(
        zip(
            reduced_twice_js,
            reduced_bases_by_j,
            reduced_parity_by_j,
            strict=True,
        )
    ):
        shape = (
            reduced_parity.even.shape[1],
            reduced_parity.odd.shape[1],
        )
        constraint_shapes.append(shape)
        if 0 in shape:
            continue
        reduced_ones = (level - 1 - reduced_twice_j) // 2
        reduced_basis = reduced_sectors[reduced_ones]
        if reduced_basis is None:
            raise ArithmeticError("missing reduced highest-weight basis")
        reduced_even = reduced_basis @ reduced_parity.even
        reduced_odd = reduced_basis @ reduced_parity.odd
        for removed_bit in (0, 1):
            global_ones = reduced_ones + removed_bit
            selection = _selection(
                level, global_ones, "last", removed_bit
            )
            for block_index, basis, twice_j in sector_components[global_ones]:
                contributions[block_index].append(
                    DualMapContribution(
                        constraint_index=constraint_index,
                        weight=1 / (twice_j + 1),
                        even_map=reduced_even.T @ selection.T @ basis,
                        odd_map=reduced_odd.T @ selection.T @ basis,
                    )
                )
    return SU2ReflectionDualModel(
        level=level,
        objective_blocks=tuple(objective_blocks),
        contributions=tuple(tuple(items) for items in contributions),
        constraint_shapes=tuple(constraint_shapes),
        block_dimensions=tuple(block_dimensions),
    )


def barrier_value_gradient(
    model: SU2ReflectionDualModel,
    parameters: NDArray[np.float64],
    barrier_parameter: float,
) -> tuple[float, NDArray[np.float64], float]:
    """Return log-det objective, analytic gradient, and minimum slack."""
    if barrier_parameter <= 0:
        raise ValueError("barrier parameter must be positive")
    y, duals = model.unpack(np.asarray(parameters, dtype=float))
    gradient_y = 1.0
    dual_gradients = [
        np.zeros(shape) for shape in model.constraint_shapes
    ]
    value = y
    minimum = np.inf
    for objective, contributions in zip(
        model.objective_blocks, model.contributions, strict=True
    ):
        slack = objective + y * np.eye(objective.shape[0])
        for contribution in contributions:
            dual = duals[contribution.constraint_index]
            term = (
                contribution.even_map.T
                @ dual
                @ contribution.odd_map
            )
            slack += contribution.weight * (term + term.T) / 2
        slack = (slack + slack.T) / 2
        eigenvalues = np.linalg.eigvalsh(slack)
        block_minimum = float(eigenvalues[0])
        minimum = min(minimum, block_minimum)
        if (
            not np.all(np.isfinite(eigenvalues))
            or block_minimum <= 1e-12
        ):
            gradient = np.zeros(model.parameter_count)
            gradient[0] = -1
            return 1e100, gradient, minimum
        sign, logdet = np.linalg.slogdet(slack)
        if sign <= 0:
            gradient = np.zeros(model.parameter_count)
            gradient[0] = -1
            return 1e100, gradient, minimum
        inverse = np.linalg.inv(slack)
        value -= barrier_parameter * float(logdet)
        gradient_y -= barrier_parameter * float(np.trace(inverse))
        for contribution in contributions:
            dual_gradients[contribution.constraint_index] -= (
                barrier_parameter
                * contribution.weight
                * contribution.even_map
                @ inverse
                @ contribution.odd_map.T
            )
    gradient = np.empty(model.parameter_count)
    gradient[0] = gradient_y
    offset = 1
    for block in dual_gradients:
        size = block.size
        gradient[offset : offset + size] = block.reshape(-1)
        offset += size
    return float(value), gradient, float(minimum)


def barrier_hessian_product(
    model: SU2ReflectionDualModel,
    parameters: NDArray[np.float64],
    direction: NDArray[np.float64],
    barrier_parameter: float,
    *,
    regularization: float = 1e-10,
) -> NDArray[np.float64]:
    """Apply the log-det Hessian without assembling it."""
    y, duals = model.unpack(np.asarray(parameters, dtype=float))
    direction_y, direction_duals = model.unpack(
        np.asarray(direction, dtype=float)
    )
    result_y = 0.0
    result_duals = [
        np.zeros(shape) for shape in model.constraint_shapes
    ]
    for objective, contributions in zip(
        model.objective_blocks, model.contributions, strict=True
    ):
        slack = objective + y * np.eye(objective.shape[0])
        delta_slack = direction_y * np.eye(objective.shape[0])
        for contribution in contributions:
            dual_term = (
                contribution.even_map.T
                @ duals[contribution.constraint_index]
                @ contribution.odd_map
            )
            slack += (
                contribution.weight
                * (dual_term + dual_term.T)
                / 2
            )
            direction_term = (
                contribution.even_map.T
                @ direction_duals[contribution.constraint_index]
                @ contribution.odd_map
            )
            delta_slack += (
                contribution.weight
                * (direction_term + direction_term.T)
                / 2
            )
        inverse = np.linalg.inv((slack + slack.T) / 2)
        sandwich = inverse @ delta_slack @ inverse
        result_y += barrier_parameter * float(np.trace(sandwich))
        for contribution in contributions:
            result_duals[contribution.constraint_index] += (
                barrier_parameter
                * contribution.weight
                * contribution.even_map
                @ sandwich
                @ contribution.odd_map.T
            )
    result = np.empty(model.parameter_count)
    result[0] = result_y
    offset = 1
    for block in result_duals:
        size = block.size
        result[offset : offset + size] = block.reshape(-1)
        offset += size
    result += regularization * np.asarray(direction, dtype=float)
    return result


def solve_su2_reflection_dual_barrier(
    level: int,
    *,
    barrier_parameters: tuple[float, ...] = (
        1e-1,
        3e-2,
        1e-2,
        3e-3,
        1e-3,
        3e-4,
        1e-4,
    ),
    max_iterations: int = 80,
) -> SU2ReflectionLTICandidate:
    """Follow a log-det central path and return a certifiable dual candidate."""
    if not barrier_parameters or any(
        value <= 0 for value in barrier_parameters
    ):
        raise ValueError("barrier parameters must be positive")
    model = build_su2_reflection_dual_model(level)
    parameters = np.zeros(model.parameter_count)
    parameters[0] = 1.0
    final_minimum = np.inf
    statuses: list[str] = []
    for barrier_parameter in barrier_parameters:
        status = "max-iterations"
        for _ in range(max_iterations):
            value, gradient, final_minimum = barrier_value_gradient(
                model, parameters, barrier_parameter
            )
            if np.linalg.norm(gradient, ord=np.inf) < 1e-8:
                status = "ok"
                break
            operator = LinearOperator(
                (model.parameter_count, model.parameter_count),
                matvec=lambda vector: barrier_hessian_product(
                    model,
                    parameters,
                    vector,
                    barrier_parameter,
                ),
                dtype=float,
            )
            direction, information = cg(
                operator,
                -gradient,
                rtol=1e-6,
                atol=0.0,
                maxiter=min(200, model.parameter_count),
            )
            if (
                information < 0
                or not np.all(np.isfinite(direction))
                or float(gradient @ direction) >= 0
            ):
                direction = -gradient
            slope = float(gradient @ direction)
            step = 1.0
            accepted = False
            for _ in range(80):
                trial = parameters + step * direction
                trial_value, _, trial_minimum = barrier_value_gradient(
                    model, trial, barrier_parameter
                )
                if (
                    np.isfinite(trial_value)
                    and trial_value < 1e90
                    and trial_value
                    <= value + 1e-4 * step * slope
                ):
                    parameters = trial
                    final_minimum = trial_minimum
                    accepted = True
                    break
                step *= 0.5
            if not accepted:
                status = "line-search-stopped"
                break
        statuses.append(status)
    y, duals = model.unpack(parameters)
    return SU2ReflectionLTICandidate(
        level=level,
        raw_lower=-y,
        status="barrier-" + ",".join(statuses),
        solver="SCIPY-LBFGSB-logdet",
        dual_trace=y,
        dual_cross_blocks=duals,
        max_equality_residual=0.0,
        minimum_block_eigenvalue=final_minimum,
        block_dimensions=model.block_dimensions,
        compatibility_shapes=model.constraint_shapes,
    )
