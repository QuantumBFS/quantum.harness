"""U(1)-block conic solver for the compressed RG-LTI dual."""

from __future__ import annotations

from typing import Any, Mapping

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray

from .rg_dual_barrier import (
    RGDualBarrierModel,
    build_rg_dual_barrier_model,
    rg_dual_slacks,
)
from .rg_relaxation import RGRelaxationCandidate
from .rg_symmetry import ChargeBasis, assemble_charge_blocks


def _block_matrix_variable(
    basis: ChargeBasis,
    *,
    name: str,
) -> tuple[cp.Expression, tuple[cp.Variable, ...]]:
    full: cp.Expression = cp.Constant(
        np.zeros((basis.size, basis.size), dtype=float)
    )
    variables: list[cp.Variable] = []
    for sector, indices in zip(
        basis.sectors, basis.indices, strict=True
    ):
        block = cp.Variable(
            (len(indices), len(indices)),
            symmetric=True,
            name=f"{name}_q{sector}",
        )
        selection = np.zeros((basis.size, len(indices)), dtype=float)
        selection[np.asarray(indices), np.arange(len(indices))] = 1.0
        full = full + selection @ block @ selection.T
        variables.append(block)
    return full, tuple(variables)


def _slack_expressions(
    model: RGDualBarrierModel,
    y: cp.Variable,
    matrices: tuple[cp.Expression, ...],
) -> tuple[cp.Expression, ...]:
    lti, first, second, *transition_flat = matrices
    transitions = [
        (transition_flat[index], transition_flat[index + 1])
        for index in range(0, len(transition_flat), 2)
    ]
    rho = (
        model.objective
        + y * np.eye(8)
        + cp.kron(np.eye(2), lti)
        - cp.kron(lti, np.eye(2))
        + model.first_map.T @ first @ model.first_map
        + model.second_map.T @ second @ model.second_map
    )
    omegas: list[cp.Expression] = []
    for index in range(model.depth - 3):
        if index == 0:
            incoming_left, incoming_right = first, second
        else:
            incoming_left, incoming_right = transitions[index - 1]
        slack = -cp.kron(np.eye(2), incoming_left) - cp.kron(
            incoming_right, np.eye(2)
        )
        if index < model.depth - 4:
            outgoing_left, outgoing_right = transitions[index]
            slack = (
                slack
                + model.left_map.T @ outgoing_left @ model.left_map
                + model.right_map.T @ outgoing_right @ model.right_map
            )
        omegas.append(slack)
    return (rho, *omegas)


def _identity_tensor_maps(
    matrix_dimension: int,
    *,
    identity_on_left: bool,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Maps K_s with sum_s K_s.T D K_s equal to I⊗D or D⊗I."""
    maps: list[NDArray[np.float64]] = []
    for spin in range(2):
        selector = np.zeros(
            (matrix_dimension, 2 * matrix_dimension), dtype=float
        )
        for index in range(matrix_dimension):
            column = (
                spin * matrix_dimension + index
                if identity_on_left
                else 2 * index + spin
            )
            selector[index, column] = 1.0
        maps.append(selector)
    return maps[0], maps[1]


def _sandwich_sector(
    blocks: tuple[cp.Variable, ...],
    source_basis: ChargeBasis,
    map_matrix: NDArray[np.float64],
    target_indices: tuple[int, ...],
) -> cp.Expression:
    """Build one target-sector block of M.T D M without assembling D."""
    size = len(target_indices)
    result: cp.Expression = cp.Constant(
        np.zeros((size, size), dtype=float)
    )
    for block, source_indices in zip(
        blocks, source_basis.indices, strict=True
    ):
        restricted = map_matrix[
            np.ix_(source_indices, target_indices)
        ]
        if np.any(restricted):
            result = result + restricted.T @ block @ restricted
    return result


def _native_slack_blocks(
    model: RGDualBarrierModel,
    y: cp.Variable,
    variables: tuple[tuple[cp.Variable, ...], ...],
    parameter_bases: tuple[ChargeBasis, ...],
    rho_basis: ChargeBasis,
) -> tuple[tuple[cp.Expression, ...], ...]:
    """Construct only allowed PSD blocks, never a full q×q expression."""
    lti, first, second, *transition_flat = variables
    lti_basis, first_basis, second_basis, *transition_bases_flat = (
        parameter_bases
    )
    transitions = [
        (transition_flat[index], transition_flat[index + 1])
        for index in range(0, len(transition_flat), 2)
    ]
    transition_bases = [
        (
            transition_bases_flat[index],
            transition_bases_flat[index + 1],
        )
        for index in range(0, len(transition_bases_flat), 2)
    ]
    local_left_maps = _identity_tensor_maps(
        lti_basis.size, identity_on_left=True
    )
    local_right_maps = _identity_tensor_maps(
        lti_basis.size, identity_on_left=False
    )
    rho_blocks: list[cp.Expression] = []
    for target_indices in rho_basis.indices:
        block: cp.Expression = cp.Constant(
            model.objective[np.ix_(target_indices, target_indices)]
        ) + y * np.eye(len(target_indices))
        for selector in local_left_maps:
            block = block + _sandwich_sector(
                lti, lti_basis, selector, target_indices
            )
        for selector in local_right_maps:
            block = block - _sandwich_sector(
                lti, lti_basis, selector, target_indices
            )
        block = block + _sandwich_sector(
            first,
            first_basis,
            model.first_map,
            target_indices,
        )
        block = block + _sandwich_sector(
            second,
            second_basis,
            model.second_map,
            target_indices,
        )
        rho_blocks.append(block)

    omega_basis = model.charge_bases.omega
    incoming_left_maps = _identity_tensor_maps(
        model.equality_dimension, identity_on_left=True
    )
    incoming_right_maps = _identity_tensor_maps(
        model.equality_dimension, identity_on_left=False
    )
    omega_levels: list[tuple[cp.Expression, ...]] = []
    for level in range(model.depth - 3):
        if level == 0:
            incoming_left, incoming_right = first, second
            incoming_left_basis = first_basis
            incoming_right_basis = second_basis
        else:
            incoming_left, incoming_right = transitions[level - 1]
            incoming_left_basis, incoming_right_basis = (
                transition_bases[level - 1]
            )
        blocks: list[cp.Expression] = []
        for target_indices in omega_basis.indices:
            block = cp.Constant(
                np.zeros(
                    (len(target_indices), len(target_indices)),
                    dtype=float,
                )
            )
            for selector in incoming_left_maps:
                block = block - _sandwich_sector(
                    incoming_left,
                    incoming_left_basis,
                    selector,
                    target_indices,
                )
            for selector in incoming_right_maps:
                block = block - _sandwich_sector(
                    incoming_right,
                    incoming_right_basis,
                    selector,
                    target_indices,
                )
            if level < model.depth - 4:
                outgoing_left, outgoing_right = transitions[level]
                outgoing_left_basis, outgoing_right_basis = (
                    transition_bases[level]
                )
                block = block + _sandwich_sector(
                    outgoing_left,
                    outgoing_left_basis,
                    model.left_map,
                    target_indices,
                )
                block = block + _sandwich_sector(
                    outgoing_right,
                    outgoing_right_basis,
                    model.right_map,
                    target_indices,
                )
            blocks.append(block)
        omega_levels.append(tuple(blocks))
    return (tuple(rho_blocks), *omega_levels)


def _block_psd_constraints(
    expression: cp.Expression,
    basis: ChargeBasis,
    *,
    margin: float,
) -> list[cp.Constraint]:
    return [
        expression[np.ix_(indices, indices)]
        - margin * np.eye(len(indices))
        >> 0
        for indices in basis.indices
    ]


def solve_rg_u1_conic(
    delta: float,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    solver: str = "CLARABEL",
    slack_margin: float = 0.0,
    native_blocks: bool = True,
    solver_options: Mapping[str, Any] | None = None,
) -> RGRelaxationCandidate:
    """Solve the RG dual using only exact U(1)-allowed matrix sectors."""
    model = build_rg_dual_barrier_model(
        delta, tensor, depth, use_symmetry=True
    )
    if slack_margin < 0 or not np.isfinite(slack_margin):
        raise ValueError("slack_margin must be finite and nonnegative")
    assert model.charge_bases is not None
    parameter_bases = model.parameter_charge_bases
    assert parameter_bases is not None
    variables: list[tuple[cp.Variable, ...]] = []
    for index, basis in enumerate(parameter_bases):
        _, blocks = _block_matrix_variable(
            basis, name=f"dual_{index}"
        )
        variables.append(blocks)
    y = cp.Variable(name="y")
    physical = (1, -1)
    rho_basis = ChargeBasis.from_labels(
        tuple(
            first + second + third
            for first in physical
            for second in physical
            for third in physical
        )
    )
    constraints: list[cp.Constraint] = []
    if native_blocks:
        native_slacks = _native_slack_blocks(
            model,
            y,
            tuple(variables),
            parameter_bases,
            rho_basis,
        )
        for level_blocks in native_slacks:
            constraints.extend(
                block - float(slack_margin) * np.eye(block.shape[0])
                >> 0
                for block in level_blocks
            )
    else:
        # Replace the unused native variables so extraction below refers to
        # the variables which actually occur in the legacy problem.
        variables = [
            _block_matrix_variable(
                basis, name=f"legacy_extract_{index}"
            )[1]
            for index, basis in enumerate(parameter_bases)
        ]
        # Rebuild expressions from the extraction variables.
        legacy_expressions: list[cp.Expression] = []
        for basis, blocks in zip(
            parameter_bases, variables, strict=True
        ):
            expression: cp.Expression = cp.Constant(
                np.zeros((basis.size, basis.size))
            )
            for block, indices in zip(
                blocks, basis.indices, strict=True
            ):
                selection = np.zeros(
                    (basis.size, len(indices)), dtype=float
                )
                selection[np.asarray(indices), np.arange(len(indices))] = 1
                expression = expression + selection @ block @ selection.T
            legacy_expressions.append(expression)
        slacks = _slack_expressions(
            model, y, tuple(legacy_expressions)
        )
        slack_bases = (rho_basis,) + (
            model.charge_bases.omega,
        ) * (depth - 3)
        for slack, basis in zip(slacks, slack_bases, strict=True):
            constraints.extend(
                _block_psd_constraints(
                    slack, basis, margin=float(slack_margin)
                )
            )
    problem = cp.Problem(cp.Minimize(y), constraints)
    options: dict[str, Any] = {}
    if solver.upper() == "CLARABEL":
        options = {
            "tol_gap_abs": 1e-9,
            "tol_feas": 1e-9,
            "tol_gap_rel": 1e-9,
            "max_iter": 1000,
        }
    elif solver.upper() == "SCS":
        options = {
            "eps": 1e-5,
            "max_iters": 10_000,
        }
    if solver_options is not None:
        options.update(solver_options)
    value = problem.solve(solver=solver, verbose=False, **options)
    if problem.status not in {"optimal", "optimal_inaccurate"}:
        raise RuntimeError(f"U(1) RG conic solve failed: {problem.status}")
    if value is None or y.value is None or not np.isfinite(value):
        raise RuntimeError("U(1) RG conic solver returned no finite value")
    numerical_matrices = tuple(
        assemble_charge_blocks(
            tuple(
                np.asarray(block.value, dtype=float)
                for block in blocks
            ),
            basis,
        )
        for blocks, basis in zip(
            variables, parameter_bases, strict=True
        )
    )
    parameters = model.pack(float(y.value), numerical_matrices)
    numerical_slacks = rg_dual_slacks(model, parameters)
    minima = tuple(
        float(np.linalg.eigvalsh(slack)[0])
        for slack in numerical_slacks
    )
    return RGRelaxationCandidate(
        delta=float(delta),
        depth=depth,
        bond_dimension=model.bond_dimension,
        raw_lower=-float(y.value),
        status=f"u1-conic-{problem.status}",
        omega_dimension=model.omega_dimension,
        rho3=np.empty((0, 0), dtype=np.complex128),
        omegas=(),
        max_equality_residual=0.0,
        minimum_primal_eigenvalue=np.nan,
        dual_objective=-float(y.value),
        dual_slack_min_eigenvalues=minima,
        dual_stationarity_residual=0.0,
        equality_duals=(float(y.value), *numerical_matrices),
    )
