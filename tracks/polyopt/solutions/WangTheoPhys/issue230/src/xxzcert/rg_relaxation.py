"""MPS-compressed LTI relaxation from Kull--Schuch--Dive--Navascués Eq. (14)."""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from .model import local_xxz
from .rg_symmetry import u1_tensor_mask


@dataclass(frozen=True)
class RGRelaxationCandidate:
    delta: float
    depth: int
    bond_dimension: int
    raw_lower: float
    status: str
    omega_dimension: int
    rho3: NDArray[np.complex128]
    omegas: tuple[NDArray[np.complex128], ...]
    max_equality_residual: float
    minimum_primal_eigenvalue: float
    dual_objective: float
    dual_slack_min_eigenvalues: tuple[float, ...]
    dual_stationarity_residual: float
    equality_duals: tuple[NDArray[np.complex128] | float, ...]


def alternating_neel_mps() -> NDArray[np.complex128]:
    """One-site-uniform D=2 MPS tensor for the two Néel configurations."""
    tensor = np.zeros((2, 2, 2), dtype=np.complex128)
    tensor[0, 0, 1] = 1.0
    tensor[1, 1, 0] = 1.0
    return tensor


def dimer_cat_mps() -> NDArray[np.complex128]:
    """Uniform D=3 tensor for the equal translation mixture of singlet dimers."""
    tensor = np.zeros((3, 2, 3), dtype=np.complex128)
    tensor[0, 0, 1] = 1.0
    tensor[1, 1, 0] = 1.0
    tensor[0, 1, 2] = 1.0
    tensor[2, 0, 0] = -1.0
    return tensor


def normalize_mps_tensor(tensor: NDArray[np.complex128]) -> NDArray[np.complex128]:
    """Scale A so the transfer operator has spectral radius one."""
    array = np.asarray(tensor, dtype=np.complex128)
    if array.ndim != 3 or array.shape[0] != array.shape[2]:
        raise ValueError("tensor must have shape (D,d,D)")
    bond, physical, _ = array.shape
    transfer = sum(
        np.kron(array[:, spin, :], array[:, spin, :].conj())
        for spin in range(physical)
    )
    radius = float(np.max(np.abs(np.linalg.eigvals(transfer))))
    if radius <= 0:
        raise ValueError("MPS transfer operator has zero spectral radius")
    return array / np.sqrt(radius)


def mps_flow_maps(
    tensor: NDArray[np.complex128],
    *,
    normalize: bool = True,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.complex128]]:
    """Return W2, L, R maps satisfying W_{m+1}=L(I⊗W_m)=R(W_m⊗I)."""
    array = (
        normalize_mps_tensor(tensor)
        if normalize
        else np.asarray(tensor, dtype=np.complex128)
    )
    if array.ndim != 3 or array.shape[0] != array.shape[2]:
        raise ValueError("tensor must have shape (D,d,D)")
    bond, physical, _ = array.shape
    compressed = bond * bond
    w2 = np.zeros((compressed, physical * physical), dtype=np.complex128)
    for first in range(physical):
        for second in range(physical):
            product = array[:, first, :] @ array[:, second, :]
            w2[:, first * physical + second] = product.reshape(-1)
    left = np.zeros(
        (compressed, physical * compressed), dtype=np.complex128
    )
    right = np.zeros(
        (compressed, compressed * physical), dtype=np.complex128
    )
    for output_left in range(bond):
        for output_right in range(bond):
            output = output_left * bond + output_right
            for spin in range(physical):
                for middle_left in range(bond):
                    middle = middle_left * bond + output_right
                    left[output, spin * compressed + middle] = array[
                        output_left, spin, middle_left
                    ]
                for middle_right in range(bond):
                    middle = output_left * bond + middle_right
                    right[output, middle * physical + spin] = array[
                        middle_right, spin, output_right
                    ]
    return w2, left, right


def uniform_mps_energy(
    tensor: NDArray[np.complex128], delta: float, iterations: int = 500
) -> float:
    """Evaluate a one-site-uniform MPS energy from transfer fixed points."""
    array = normalize_mps_tensor(tensor)
    bond, physical, _ = array.shape
    if physical != 2:
        raise ValueError("XXZ requires physical dimension two")
    def transfer_right(matrix: NDArray[np.complex128]) -> NDArray[np.complex128]:
        return sum(
            array[:, spin, :] @ matrix @ array[:, spin, :].conj().T
            for spin in range(physical)
        )

    def transfer_left(matrix: NDArray[np.complex128]) -> NDArray[np.complex128]:
        return sum(
            array[:, spin, :].conj().T @ matrix @ array[:, spin, :]
            for spin in range(physical)
        )

    def positive_fixed_point(adjoint: bool) -> NDArray[np.complex128]:
        apply = transfer_left if adjoint else transfer_right
        matrix = np.eye(bond, dtype=np.complex128) / bond
        # Apply E^2 to handle the period-two block-cyclic tensors produced by
        # an AB unit cell, then Cesàro-average with E(matrix).
        for _ in range(iterations):
            following = apply(apply(matrix))
            following = (following + following.conj().T) / 2
            trace = float(np.trace(following).real)
            if trace <= 1e-15:
                raise ArithmeticError("transfer iteration lost positivity")
            following /= trace
            if np.linalg.norm(following - matrix) < 1e-13:
                matrix = following
                break
            matrix = following
        averaged = matrix + apply(matrix)
        averaged = (averaged + averaged.conj().T) / 2
        averaged /= np.trace(averaged)
        return averaged

    right = positive_fixed_point(False)
    left = positive_fixed_point(True)
    normalization = np.trace(left @ right)
    if normalization.real <= 1e-12 or abs(normalization.imag) > 1e-8:
        raise ArithmeticError("ill-conditioned transfer fixed points")
    left /= normalization
    normalization = np.trace(left @ right)
    rho2 = np.empty((4, 4), dtype=np.complex128)
    for first in range(2):
        for second in range(2):
            product = array[:, first, :] @ array[:, second, :]
            row = 2 * first + second
            for first_prime in range(2):
                for second_prime in range(2):
                    product_prime = (
                        array[:, first_prime, :] @ array[:, second_prime, :]
                    )
                    col = 2 * first_prime + second_prime
                    rho2[row, col] = np.trace(
                        left @ product @ right @ product_prime.conj().T
                    ) / normalization
    energy = np.trace(local_xxz(delta) @ rho2)
    if abs(energy.imag) > 1e-8 or not np.isfinite(energy.real):
        raise ArithmeticError("invalid uniform-MPS contraction")
    return float(energy.real)


def optimize_uniform_mps(
    delta: float,
    bond_dimension: int = 2,
    restarts: int = 4,
    seed: int = 230,
) -> NDArray[np.complex128]:
    """Optimize a small real uniform MPS tensor for the XXZ energy."""
    if bond_dimension < 1:
        raise ValueError("bond_dimension must be positive")
    rng = np.random.default_rng(seed)
    best_tensor: NDArray[np.complex128] | None = None
    best_energy = np.inf

    def objective(parameters: np.ndarray) -> float:
        tensor = parameters.reshape(bond_dimension, 2, bond_dimension).astype(
            np.complex128
        )
        try:
            return uniform_mps_energy(tensor, delta)
        except (ValueError, ArithmeticError, np.linalg.LinAlgError):
            return 1e3

    initial_tensors = [alternating_neel_mps()] if bond_dimension == 2 else []
    if bond_dimension == 3:
        initial_tensors.append(dimer_cat_mps())
    initial_tensors.extend(
        rng.normal(size=(bond_dimension, 2, bond_dimension))
        for _ in range(restarts)
    )
    for initial in initial_tensors:
        result = minimize(
            objective,
            np.asarray(initial).real.reshape(-1),
            method="L-BFGS-B",
            options={"maxiter": 500, "ftol": 1e-13, "gtol": 1e-9},
        )
        tensor = result.x.reshape(bond_dimension, 2, bond_dimension).astype(
            np.complex128
        )
        energy = objective(result.x)
        if energy < best_energy:
            best_energy = energy
            best_tensor = normalize_mps_tensor(tensor)
    if best_tensor is None:
        raise RuntimeError("uniform-MPS optimization failed")
    return best_tensor


def optimize_u1_uniform_mps(
    delta: float,
    virtual_charges: tuple[int, ...],
    *,
    restarts: int = 4,
    seed: int = 230,
    max_iterations: int = 500,
    fixed_point_iterations: int = 200,
) -> NDArray[np.complex128]:
    """Optimize a real uniform MPS inside an exact U(1) selection pattern."""
    if restarts < 1:
        raise ValueError("restarts must be positive")
    if fixed_point_iterations < 1:
        raise ValueError("fixed_point_iterations must be positive")
    mask = u1_tensor_mask(virtual_charges)
    allowed = np.flatnonzero(mask.reshape(-1))
    if allowed.size == 0:
        raise ValueError("virtual charges permit no tensor entries")
    bond = len(virtual_charges)
    rng = np.random.default_rng(seed)
    best_tensor: NDArray[np.complex128] | None = None
    best_energy = np.inf

    def assemble(parameters: NDArray[np.float64]) -> NDArray[np.complex128]:
        flat = np.zeros(mask.size, dtype=float)
        flat[allowed] = parameters
        return flat.reshape(bond, 2, bond).astype(np.complex128)

    def objective(parameters: NDArray[np.float64]) -> float:
        try:
            return uniform_mps_energy(
                assemble(parameters),
                delta,
                iterations=fixed_point_iterations,
            )
        except (ValueError, ArithmeticError, np.linalg.LinAlgError):
            return 1e3

    for _ in range(restarts):
        initial = rng.normal(size=allowed.size)
        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            options={
                "maxiter": max_iterations,
                "ftol": 1e-13,
                "gtol": 1e-9,
            },
        )
        energy = objective(result.x)
        if energy < best_energy:
            best_energy = energy
            best_tensor = normalize_mps_tensor(assemble(result.x))
    if best_tensor is None or not np.isfinite(best_energy):
        raise RuntimeError("U(1) uniform-MPS optimization failed")
    return best_tensor


def _partial_trace_value(
    matrix: NDArray[np.complex128], dims: list[int], axis: int
) -> NDArray[np.complex128]:
    sites = len(dims)
    tensor = matrix.reshape(tuple(dims + dims))
    reduced = np.trace(tensor, axis1=axis, axis2=axis + sites)
    remaining = int(np.prod(dims) // dims[axis])
    return reduced.reshape(remaining, remaining)


def solve_rg_lti(
    delta: float,
    tensor: NDArray[np.complex128],
    depth: int,
    solver: str = "CVXOPT",
    *,
    normalize_maps: bool = True,
    solver_options: dict[str, float | int] | None = None,
    local_operator: NDArray[np.complex128] | None = None,
) -> RGRelaxationCandidate:
    """Solve the MPS-compressed thermodynamic lower relaxation."""
    if depth < 4:
        raise ValueError("RG depth must be at least 4")
    w2, left, right = mps_flow_maps(tensor, normalize=normalize_maps)
    bond = tensor.shape[0]
    physical = tensor.shape[1]
    if local_operator is None:
        if physical != 2:
            raise ValueError(
                "a local operator is required for non-qubit physical cells"
            )
        local_operator = local_xxz(delta)
    local_operator = np.asarray(local_operator, dtype=np.complex128)
    if local_operator.shape != (physical * physical, physical * physical):
        raise ValueError("local operator dimension mismatch")
    compressed = bond * bond
    omega_dim = physical * compressed * physical
    rho3_dim = physical**3
    rho3 = cp.Variable((rho3_dim, rho3_dim), hermitian=True, name="rho3")
    omegas = [
        cp.Variable((omega_dim, omega_dim), hermitian=True, name=f"omega_{level}")
        for level in range(4, depth + 1)
    ]
    rho_psd = rho3 >> 0
    trace_constraint = cp.trace(rho3) == 1
    constraints: list[cp.Constraint] = [rho_psd, trace_constraint]
    rho_left = cp.partial_trace(
        rho3, [physical, physical, physical], axis=0
    )
    rho_right = cp.partial_trace(
        rho3, [physical, physical, physical], axis=2
    )
    lti_constraint = rho_left == rho_right
    constraints.append(lti_constraint)
    omega_psd_constraints: list[cp.Constraint] = []
    for omega in omegas:
        constraint = omega >> 0
        omega_psd_constraints.append(constraint)
        constraints.append(constraint)
    first_map = np.kron(w2, np.eye(physical))
    second_map = np.kron(np.eye(physical), w2)
    omega4 = omegas[0]
    first_constraint = (
        first_map @ rho3 @ first_map.conj().T
        == cp.partial_trace(
            omega4, [physical, compressed, physical], axis=0
        )
    )
    second_constraint = (
        second_map @ rho3 @ second_map.conj().T
        == cp.partial_trace(
            omega4, [physical, compressed, physical], axis=2
        )
    )
    constraints.extend([first_constraint, second_constraint])
    left_map = np.kron(left, np.eye(physical))
    right_map = np.kron(np.eye(physical), right)
    transition_constraints: list[tuple[cp.Constraint, cp.Constraint]] = []
    for current, following in zip(omegas[:-1], omegas[1:], strict=True):
        left_constraint = (
            left_map @ current @ left_map.conj().T
            == cp.partial_trace(
                following, [physical, compressed, physical], axis=0
            )
        )
        right_constraint = (
            right_map @ current @ right_map.conj().T
            == cp.partial_trace(
                following, [physical, compressed, physical], axis=2
            )
        )
        transition_constraints.append((left_constraint, right_constraint))
        constraints.extend([left_constraint, right_constraint])
    objective_operator = np.kron(local_operator, np.eye(physical))
    objective = cp.real(cp.trace(objective_operator @ rho3))
    problem = cp.Problem(cp.Minimize(objective), constraints)
    kwargs: dict[str, float | int] = (
        {"eps": 1e-7, "max_iters": 200_000}
        if solver.upper() == "SCS"
        else {}
    )
    if solver_options:
        kwargs.update(solver_options)
    value = problem.solve(solver=solver, verbose=False, **kwargs)
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"RG relaxation failed: {problem.status}")
    rho_value = np.asarray(rho3.value, dtype=np.complex128)
    omega_values = tuple(
        np.asarray(variable.value, dtype=np.complex128) for variable in omegas
    )
    residuals = [
        abs(float(np.trace(rho_value).real) - 1),
        float(
            np.linalg.norm(
                _partial_trace_value(
                    rho_value, [physical, physical, physical], 0
                )
                - _partial_trace_value(
                    rho_value, [physical, physical, physical], 2
                )
            )
        ),
    ]
    residuals.extend(
        [
            float(np.linalg.norm(constraint.violation()))
            for constraint in constraints
            if isinstance(constraint, cp.constraints.zero.Equality)
        ]
    )
    min_eigenvalue = min(
        float(np.linalg.eigvalsh((matrix + matrix.conj().T) / 2)[0])
        for matrix in (rho_value,) + omega_values
    )
    y = float(np.real(trace_constraint.dual_value))
    lti_dual = np.asarray(lti_constraint.dual_value, dtype=np.complex128)
    first_dual = np.asarray(first_constraint.dual_value, dtype=np.complex128)
    second_dual = np.asarray(second_constraint.dual_value, dtype=np.complex128)
    transition_duals = [
        (
            np.asarray(left_constraint.dual_value, dtype=np.complex128),
            np.asarray(right_constraint.dual_value, dtype=np.complex128),
        )
        for left_constraint, right_constraint in transition_constraints
    ]
    rho_slack = (
        objective_operator
        + y * np.eye(rho3_dim)
        + np.kron(np.eye(physical), lti_dual)
        - np.kron(lti_dual, np.eye(physical))
        + first_map.conj().T @ first_dual @ first_map
        + second_map.conj().T @ second_dual @ second_map
    )
    reconstructed_slacks: list[NDArray[np.complex128]] = [rho_slack]
    for index in range(len(omegas)):
        if index == 0:
            slack = -np.kron(np.eye(physical), first_dual) - np.kron(
                second_dual, np.eye(physical)
            )
        else:
            incoming_left, incoming_right = transition_duals[index - 1]
            slack = -np.kron(np.eye(physical), incoming_left) - np.kron(
                incoming_right, np.eye(physical)
            )
        if index < len(omegas) - 1:
            outgoing_left, outgoing_right = transition_duals[index]
            slack = (
                slack
                + left_map.conj().T @ outgoing_left @ left_map
                + right_map.conj().T @ outgoing_right @ right_map
            )
        reconstructed_slacks.append(slack)
    solver_slacks = [
        np.asarray(rho_psd.dual_value, dtype=np.complex128),
        *[
            np.asarray(constraint.dual_value, dtype=np.complex128)
            for constraint in omega_psd_constraints
        ],
    ]
    stationarity_residual = max(
        float(np.linalg.norm(reconstructed - solver_slack, ord="fro"))
        for reconstructed, solver_slack in zip(
            reconstructed_slacks, solver_slacks, strict=True
        )
    )
    slack_minima = tuple(
        float(np.linalg.eigvalsh((slack + slack.conj().T) / 2)[0])
        for slack in reconstructed_slacks
    )
    equality_duals: list[NDArray[np.complex128] | float] = [
        y,
        lti_dual,
        first_dual,
        second_dual,
    ]
    for left_dual, right_dual in transition_duals:
        equality_duals.extend([left_dual, right_dual])
    return RGRelaxationCandidate(
        delta=float(delta),
        depth=depth,
        bond_dimension=bond,
        raw_lower=float(value),
        status=problem.status,
        omega_dimension=omega_dim,
        rho3=rho_value,
        omegas=omega_values,
        max_equality_residual=max(residuals),
        minimum_primal_eigenvalue=min_eigenvalue,
        dual_objective=-y,
        dual_slack_min_eigenvalues=slack_minima,
        dual_stationarity_residual=stationarity_residual,
        equality_duals=tuple(equality_duals),
    )
