"""Matrix-free log-det dual solver for the compressed RG-LTI hierarchy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.sparse.linalg import LinearOperator, cg

from .model import local_xxz
from .rg_relaxation import RGRelaxationCandidate, mps_flow_maps
from .rg_symmetry import (
    ChargeBasis,
    RGMPSChargeBases,
    assemble_charge_blocks,
    mps_rg_charge_bases,
    split_charge_blocks,
)


RealMatrix = NDArray[np.float64]


class RGConvergenceError(RuntimeError):
    """Raised when an RG optimizer result is unsafe or useless to repair."""


def _all_finite(value: object) -> bool:
    try:
        return bool(np.all(np.isfinite(np.asarray(value))))
    except (TypeError, ValueError):
        return False


def qualify_rg_candidate(
    candidate: RGRelaxationCandidate,
) -> RGRelaxationCandidate:
    """Reject unstable candidates before expensive exact reconstruction.

    The sanity floor is derived solely from the smallest eigenvalue of the
    local Hamiltonian.  It is therefore independent of the Bethe reference:
    summing ``h >= lambda_min(h) I`` already proves that floor for every chain.
    A candidate below it is valid at best but strictly dominated and signals
    the same numerical failure mode as the observed depth-12 barrier run.
    """
    scalar_fields = (
        candidate.delta,
        candidate.raw_lower,
        candidate.dual_objective,
        candidate.max_equality_residual,
        candidate.dual_stationarity_residual,
    )
    if not _all_finite(scalar_fields):
        raise RGConvergenceError("RG candidate contains a non-finite scalar")
    if not candidate.equality_duals or not all(
        _all_finite(value) for value in candidate.equality_duals
    ):
        raise RGConvergenceError("RG candidate contains a non-finite dual")
    if not candidate.dual_slack_min_eigenvalues or not _all_finite(
        candidate.dual_slack_min_eigenvalues
    ):
        raise RGConvergenceError("RG candidate has no finite slack spectrum")
    if min(candidate.dual_slack_min_eigenvalues) <= 0:
        raise RGConvergenceError("RG candidate is not strictly dual feasible")
    stages = candidate.status.removeprefix("barrier-").split(",")
    if not stages or any(
        stage not in {"ok", "max-iterations"} for stage in stages
    ):
        raise RGConvergenceError(
            f"RG solver stopped with status {candidate.status!r}"
        )
    local_floor = float(
        np.linalg.eigvalsh(local_xxz(candidate.delta).real)[0]
    )
    if candidate.raw_lower < local_floor - 1e-8:
        raise RGConvergenceError(
            "RG candidate is dominated by the exact local-term floor"
        )
    if abs(candidate.raw_lower - candidate.dual_objective) > 1e-8:
        raise RGConvergenceError("RG primal and dual objectives disagree")
    return candidate


def _partial_trace_operator(
    matrix: RealMatrix,
    left_dimension: int,
    right_dimension: int,
    *,
    trace_left: bool,
) -> RealMatrix:
    tensor = matrix.reshape(
        left_dimension,
        right_dimension,
        left_dimension,
        right_dimension,
    )
    if trace_left:
        return np.trace(tensor, axis1=0, axis2=2)
    return np.trace(tensor, axis1=1, axis2=3)


@dataclass(frozen=True)
class RGDualBarrierModel:
    delta: float
    depth: int
    bond_dimension: int
    objective: RealMatrix
    first_map: RealMatrix
    second_map: RealMatrix
    left_map: RealMatrix
    right_map: RealMatrix
    charge_bases: RGMPSChargeBases | None = None

    @property
    def equality_dimension(self) -> int:
        return 2 * self.bond_dimension * self.bond_dimension

    @property
    def omega_dimension(self) -> int:
        return 2 * self.equality_dimension

    @property
    def matrix_shapes(self) -> tuple[tuple[int, int], ...]:
        count = 3 + 2 * (self.depth - 4)
        return ((4, 4),) + (
            (self.equality_dimension, self.equality_dimension),
        ) * (count - 1)

    @property
    def parameter_count(self) -> int:
        bases = self.parameter_charge_bases
        if bases is not None:
            return 1 + sum(
                size * (size + 1) // 2
                for basis in bases
                for size in basis.block_sizes
            )
        return 1 + sum(rows * columns for rows, columns in self.matrix_shapes)

    @property
    def parameter_charge_bases(self) -> tuple[ChargeBasis, ...] | None:
        if self.charge_bases is None:
            return None
        transitions = (
            self.charge_bases.first,
            self.charge_bases.second,
        ) * (self.depth - 4)
        return (
            self.charge_bases.local,
            self.charge_bases.first,
            self.charge_bases.second,
            *transitions,
        )

    def unpack(
        self, parameters: NDArray[np.float64]
    ) -> tuple[float, tuple[RealMatrix, ...]]:
        vector = np.asarray(parameters, dtype=float)
        if vector.shape != (self.parameter_count,):
            raise ValueError("RG dual parameter vector has the wrong size")
        bases = self.parameter_charge_bases
        matrices: list[RealMatrix] = []
        offset = 1
        for matrix_index, (rows, columns) in enumerate(self.matrix_shapes):
            if bases is None:
                size = rows * columns
                matrix = vector[offset : offset + size].reshape(rows, columns)
                matrices.append((matrix + matrix.T) / 2)
                offset += size
                continue
            matrix = np.zeros((rows, columns), dtype=float)
            basis = bases[matrix_index]
            for indices in basis.indices:
                for local_row, row in enumerate(indices):
                    for column in indices[local_row:]:
                        value = vector[offset]
                        offset += 1
                        matrix[row, column] = value
                        matrix[column, row] = value
            matrices.append(matrix)
        return float(vector[0]), tuple(matrices)

    def pack(
        self, y: float, matrices: tuple[RealMatrix, ...]
    ) -> NDArray[np.float64]:
        if len(matrices) != len(self.matrix_shapes):
            raise ValueError("RG dual matrix count mismatch")
        payload = [np.asarray([y], dtype=float)]
        bases = self.parameter_charge_bases
        for matrix_index, (matrix, shape) in enumerate(
            zip(matrices, self.matrix_shapes, strict=True)
        ):
            if matrix.shape != shape:
                raise ValueError("RG dual matrix shape mismatch")
            if bases is None:
                payload.append(np.asarray(matrix, dtype=float).reshape(-1))
                continue
            basis = bases[matrix_index]
            split_charge_blocks(
                np.asarray(matrix, dtype=float), basis, tolerance=1e-7
            )
            payload.append(
                np.asarray(
                    [
                        matrix[row, column]
                        for indices in basis.indices
                        for local_row, row in enumerate(indices)
                        for column in indices[local_row:]
                    ],
                    dtype=float,
                )
            )
        return np.concatenate(payload)

    def pack_gradient(
        self, y: float, matrices: tuple[RealMatrix, ...]
    ) -> NDArray[np.float64]:
        """Pack a matrix sensitivity into independent parameter derivatives."""
        bases = self.parameter_charge_bases
        if bases is None:
            return self.pack(y, matrices)
        if len(matrices) != len(self.matrix_shapes):
            raise ValueError("RG dual matrix count mismatch")
        payload = [np.asarray([y], dtype=float)]
        for matrix, shape, basis in zip(
            matrices, self.matrix_shapes, bases, strict=True
        ):
            if matrix.shape != shape:
                raise ValueError("RG dual matrix shape mismatch")
            payload.append(
                np.asarray(
                    [
                        matrix[row, column]
                        * (1.0 if row == column else 2.0)
                        for indices in basis.indices
                        for local_row, row in enumerate(indices)
                        for column in indices[local_row:]
                    ],
                    dtype=float,
                )
            )
        return np.concatenate(payload)


def build_rg_dual_barrier_model(
    delta: float,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    use_symmetry: bool = False,
) -> RGDualBarrierModel:
    """Freeze real MPS flow maps for a matrix-free RG dual."""
    if depth < 4:
        raise ValueError("RG depth must be at least four")
    array = np.asarray(tensor)
    if (
        array.ndim != 3
        or array.shape[1] != 2
        or array.shape[0] != array.shape[2]
    ):
        raise ValueError("RG tensor must have shape (D,2,D)")
    if np.max(np.abs(array.imag)) > 1e-10:
        raise ValueError("matrix-free RG dual currently supports real tensors")
    frozen = array.real.astype(np.complex128)
    w2, left, right = mps_flow_maps(frozen, normalize=False)
    w2 = w2.real
    left = left.real
    right = right.real
    first_map = np.kron(w2, np.eye(2))
    second_map = np.kron(np.eye(2), w2)
    left_map = np.kron(left, np.eye(2))
    right_map = np.kron(np.eye(2), right)
    objective = np.kron(local_xxz(delta).real, np.eye(2))
    return RGDualBarrierModel(
        delta=float(delta),
        depth=depth,
        bond_dimension=array.shape[0],
        objective=objective,
        first_map=first_map,
        second_map=second_map,
        left_map=left_map,
        right_map=right_map,
        charge_bases=(
            mps_rg_charge_bases(frozen) if use_symmetry else None
        ),
    )


def _slack_charge_bases(
    model: RGDualBarrierModel,
) -> tuple[ChargeBasis, ...] | None:
    if model.charge_bases is None:
        return None
    physical = (1, -1)
    rho = ChargeBasis.from_labels(
        tuple(
            first + second + third
            for first in physical
            for second in physical
            for third in physical
        )
    )
    return (rho,) + (model.charge_bases.omega,) * (model.depth - 3)


def _inverse_and_logdet(
    matrix: RealMatrix,
    basis: ChargeBasis | None,
) -> tuple[RealMatrix, float, float]:
    if basis is None:
        eigenvalues = np.linalg.eigvalsh(matrix)
        sign, logdet = np.linalg.slogdet(matrix)
        if sign <= 0:
            raise np.linalg.LinAlgError("matrix is not positive definite")
        return (
            np.linalg.inv(matrix),
            float(logdet),
            float(eigenvalues[0]),
        )
    blocks = split_charge_blocks(matrix, basis, tolerance=1e-7)
    inverse_blocks: list[RealMatrix] = []
    logdet = 0.0
    minimum = np.inf
    for block in blocks:
        minimum = min(minimum, float(np.linalg.eigvalsh(block)[0]))
        sign, block_logdet = np.linalg.slogdet(block)
        if sign <= 0:
            raise np.linalg.LinAlgError(
                "charge block is not positive definite"
            )
        inverse_blocks.append(np.linalg.inv(block))
        logdet += float(block_logdet)
    return (
        assemble_charge_blocks(tuple(inverse_blocks), basis),
        logdet,
        float(minimum),
    )


def rg_dual_slacks(
    model: RGDualBarrierModel,
    parameters: NDArray[np.float64],
) -> tuple[RealMatrix, ...]:
    """Reconstruct floating dual slacks using the exact-verifier convention."""
    y, matrices = model.unpack(parameters)
    lti, first, second, *transition_flat = matrices
    transitions = [
        (transition_flat[index], transition_flat[index + 1])
        for index in range(0, len(transition_flat), 2)
    ]
    rho = (
        model.objective
        + y * np.eye(8)
        + np.kron(np.eye(2), lti)
        - np.kron(lti, np.eye(2))
        + model.first_map.T @ first @ model.first_map
        + model.second_map.T @ second @ model.second_map
    )
    omegas: list[RealMatrix] = []
    for index in range(model.depth - 3):
        if index == 0:
            incoming_left, incoming_right = first, second
        else:
            incoming_left, incoming_right = transitions[index - 1]
        slack = -np.kron(np.eye(2), incoming_left) - np.kron(
            incoming_right, np.eye(2)
        )
        if index < model.depth - 4:
            outgoing_left, outgoing_right = transitions[index]
            slack += (
                model.left_map.T @ outgoing_left @ model.left_map
                + model.right_map.T @ outgoing_right @ model.right_map
            )
        omegas.append((slack + slack.T) / 2)
    return ((rho + rho.T) / 2, *omegas)


def _adjoint(
    model: RGDualBarrierModel,
    sensitivities: tuple[RealMatrix, ...],
) -> NDArray[np.float64]:
    rho, *omegas = sensitivities
    q = model.equality_dimension
    lti_gradient = _partial_trace_operator(
        rho, 2, 4, trace_left=True
    ) - _partial_trace_operator(rho, 4, 2, trace_left=False)
    first_gradient = model.first_map @ rho @ model.first_map.T
    second_gradient = model.second_map @ rho @ model.second_map.T
    first_gradient -= _partial_trace_operator(
        omegas[0], 2, q, trace_left=True
    )
    second_gradient -= _partial_trace_operator(
        omegas[0], q, 2, trace_left=False
    )
    transitions: list[RealMatrix] = []
    for index in range(model.depth - 4):
        current = omegas[index]
        following = omegas[index + 1]
        left_gradient = (
            model.left_map @ current @ model.left_map.T
            - _partial_trace_operator(
                following, 2, q, trace_left=True
            )
        )
        right_gradient = (
            model.right_map @ current @ model.right_map.T
            - _partial_trace_operator(
                following, q, 2, trace_left=False
            )
        )
        transitions.extend((left_gradient, right_gradient))
    return model.pack_gradient(
        float(np.trace(rho)),
        (
            (lti_gradient + lti_gradient.T) / 2,
            (first_gradient + first_gradient.T) / 2,
            (second_gradient + second_gradient.T) / 2,
            *[
                (matrix + matrix.T) / 2 for matrix in transitions
            ],
        ),
    )


def rg_barrier_value_gradient(
    model: RGDualBarrierModel,
    parameters: NDArray[np.float64],
    barrier_parameter: float,
) -> tuple[float, NDArray[np.float64], float]:
    """Evaluate the RG dual log-det barrier and its analytic gradient."""
    if barrier_parameter <= 0:
        raise ValueError("barrier parameter must be positive")
    slacks = rg_dual_slacks(model, parameters)
    charge_bases = _slack_charge_bases(model)
    inverses: list[RealMatrix] = []
    value = float(parameters[0])
    minimum = np.inf
    for index, slack in enumerate(slacks):
        basis = None if charge_bases is None else charge_bases[index]
        try:
            inverse, logdet, slack_minimum = _inverse_and_logdet(
                slack, basis
            )
        except (ValueError, np.linalg.LinAlgError):
            gradient = np.zeros(model.parameter_count)
            gradient[0] = -1
            return 1e100, gradient, float(minimum)
        minimum = min(minimum, slack_minimum)
        if not np.isfinite(slack_minimum) or slack_minimum <= 1e-12:
            gradient = np.zeros(model.parameter_count)
            gradient[0] = -1
            return 1e100, gradient, float(minimum)
        inverses.append(inverse)
        value -= barrier_parameter * float(logdet)
    gradient = np.zeros(model.parameter_count)
    gradient[0] = 1
    gradient -= barrier_parameter * _adjoint(model, tuple(inverses))
    return value, gradient, float(minimum)


def rg_barrier_hessian_product(
    model: RGDualBarrierModel,
    parameters: NDArray[np.float64],
    direction: NDArray[np.float64],
    barrier_parameter: float,
    *,
    regularization: float = 1e-10,
) -> NDArray[np.float64]:
    """Apply the RG barrier Hessian without assembling it."""
    slacks = rg_dual_slacks(model, parameters)
    delta_slacks = rg_dual_slacks(model, direction)
    # The affine objective is present in rg_dual_slacks(direction); remove it.
    delta_slacks = (
        delta_slacks[0] - model.objective,
        *delta_slacks[1:],
    )
    charge_bases = _slack_charge_bases(model)
    sensitivities: list[RealMatrix] = []
    for index, (slack, delta) in enumerate(
        zip(slacks, delta_slacks, strict=True)
    ):
        basis = None if charge_bases is None else charge_bases[index]
        inverse, _, _ = _inverse_and_logdet(slack, basis)
        if basis is None:
            sensitivities.append(inverse @ delta @ inverse)
            continue
        delta_blocks = split_charge_blocks(delta, basis, tolerance=1e-7)
        inverse_blocks = split_charge_blocks(
            inverse, basis, tolerance=1e-7
        )
        sensitivities.append(
            assemble_charge_blocks(
                tuple(
                    inverse_block @ delta_block @ inverse_block
                    for inverse_block, delta_block in zip(
                        inverse_blocks, delta_blocks, strict=True
                    )
                ),
                basis,
            )
        )
    return (
        barrier_parameter * _adjoint(model, tuple(sensitivities))
        + regularization * np.asarray(direction, dtype=float)
    )


def _strictly_interior_start(
    model: RGDualBarrierModel,
) -> NDArray[np.float64]:
    q = model.equality_dimension
    transition_count = model.depth - 4
    amplitudes = [0.0] * (transition_count + 1)
    amplitudes[-1] = 1.0
    flow_gram = (
        model.left_map.T @ model.left_map
        + model.right_map.T @ model.right_map
    )
    flow_norm = float(np.linalg.eigvalsh(flow_gram)[-1])
    for index in range(transition_count - 1, -1, -1):
        amplitudes[index] = 1 + amplitudes[index + 1] * flow_norm / 2
    first = -amplitudes[0] * np.eye(q)
    second = -amplitudes[0] * np.eye(q)
    transitions: list[RealMatrix] = []
    for amplitude in amplitudes[1:]:
        transitions.extend(
            (-amplitude * np.eye(q), -amplitude * np.eye(q))
        )
    matrices = (np.zeros((4, 4)), first, second, *transitions)
    provisional = model.pack(0.0, matrices)
    rho_minimum = float(np.linalg.eigvalsh(rg_dual_slacks(model, provisional)[0])[0])
    return model.pack(max(1.0, 1.0 - rho_minimum), matrices)


def _warm_start_from_duals(
    model: RGDualBarrierModel,
    equality_duals: tuple[NDArray[np.complex128] | float, ...],
    *,
    minimum_slack: float = 1e-7,
) -> NDArray[np.float64]:
    """Embed shallower duals and backtrack to a strict deeper interior."""
    if len(equality_duals) < 2:
        raise ValueError("warm start requires an objective and dual matrices")
    cold = _strictly_interior_start(model)
    cold_y, cold_matrices = model.unpack(cold)
    supplied = equality_duals[1:]
    if len(supplied) > len(cold_matrices):
        raise ValueError("warm start has more matrices than the target model")
    matrices = list(cold_matrices)
    for index, (raw, shape) in enumerate(
        zip(supplied, model.matrix_shapes, strict=False)
    ):
        array = np.asarray(raw)
        if array.shape != shape or not np.all(np.isfinite(array)):
            raise ValueError("warm-start dual matrix is malformed")
        if np.max(np.abs(array.imag)) > 1e-8:
            raise ValueError("warm-start dual matrix must be real")
        matrices[index] = (array.real + array.real.T) / 2
    raw_y = float(equality_duals[0])
    if not np.isfinite(raw_y):
        raise ValueError("warm-start objective is not finite")
    if len(supplied) == len(cold_matrices) - 2:
        size = model.equality_dimension
        amplitude = 1.0
        for _ in range(80):
            matrices[-2] = -amplitude * np.eye(size)
            matrices[-1] = -amplitude * np.eye(size)
            trial = model.pack(raw_y, tuple(matrices))
            slacks = rg_dual_slacks(model, trial)
            if all(
                np.all(np.isfinite(slack))
                and float(np.linalg.eigvalsh(slack)[0]) > minimum_slack
                for slack in slacks
            ):
                return trial
            amplitude *= 0.5
    hybrid = model.pack(raw_y, tuple(matrices))
    direction = hybrid - cold
    step = 1.0
    for _ in range(60):
        trial = cold + step * direction
        slacks = rg_dual_slacks(model, trial)
        if all(
            np.all(np.isfinite(slack))
            and float(np.linalg.eigvalsh(slack)[0]) > minimum_slack
            for slack in slacks
        ):
            return trial
        step *= 0.5
    raise RGConvergenceError("could not construct a strict RG warm start")


def solve_rg_dual_barrier(
    delta: float,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    barrier_parameters: tuple[float, ...] = (
        1e-1,
        3e-2,
        1e-2,
        3e-3,
        1e-3,
        3e-4,
        1e-4,
        3e-5,
        1e-5,
    ),
    max_iterations: int = 80,
    use_symmetry: bool = False,
    algorithm: str = "auto",
    cg_max_iterations: int = 60,
    cg_relative_tolerance: float = 1e-3,
    initial_equality_duals: (
        tuple[NDArray[np.complex128] | float, ...] | None
    ) = None,
) -> RGRelaxationCandidate:
    """Follow the compressed RG dual central path."""
    if algorithm == "auto":
        algorithm = "newton-cg"
    if algorithm not in {"lbfgs", "newton-cg"}:
        raise ValueError("RG barrier algorithm must be lbfgs or newton-cg")
    if cg_max_iterations < 1:
        raise ValueError("cg_max_iterations must be positive")
    if not 0 < cg_relative_tolerance < 1:
        raise ValueError("cg_relative_tolerance must lie between zero and one")
    model = build_rg_dual_barrier_model(
        delta, tensor, depth, use_symmetry=use_symmetry
    )
    parameters = (
        _strictly_interior_start(model)
        if initial_equality_duals is None
        else _warm_start_from_duals(model, initial_equality_duals)
    )
    statuses: list[str] = []
    minimum = np.inf
    for barrier_parameter in barrier_parameters:
        if algorithm == "lbfgs":
            def objective_gradient(
                vector: NDArray[np.float64],
            ) -> tuple[float, NDArray[np.float64]]:
                value, gradient, _ = rg_barrier_value_gradient(
                    model, vector, barrier_parameter
                )
                return value, gradient

            result = minimize(
                objective_gradient,
                parameters,
                method="L-BFGS-B",
                jac=True,
                options={
                    "maxiter": max_iterations,
                    "ftol": 1e-13,
                    "gtol": 1e-8,
                    "maxls": 50,
                    "maxcor": 30,
                },
            )
            parameters = np.asarray(result.x, dtype=float)
            _, _, minimum = rg_barrier_value_gradient(
                model, parameters, barrier_parameter
            )
            if result.success:
                statuses.append("ok")
            elif result.status == 1:
                statuses.append("max-iterations")
            else:
                statuses.append(f"lbfgs-{result.status}")
            continue
        status = "max-iterations"
        for _ in range(max_iterations):
            value, gradient, minimum = rg_barrier_value_gradient(
                model, parameters, barrier_parameter
            )
            if np.linalg.norm(gradient, ord=np.inf) < 1e-8:
                status = "ok"
                break
            operator = LinearOperator(
                (model.parameter_count, model.parameter_count),
                matvec=lambda vector: rg_barrier_hessian_product(
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
                rtol=cg_relative_tolerance,
                atol=0,
                maxiter=min(cg_max_iterations, model.parameter_count),
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
                trial_value, _, trial_minimum = rg_barrier_value_gradient(
                    model, trial, barrier_parameter
                )
                if (
                    np.isfinite(trial_value)
                    and trial_value < 1e90
                    and trial_value
                    <= value + 1e-4 * step * slope
                ):
                    parameters = trial
                    minimum = trial_minimum
                    accepted = True
                    break
                step *= 0.5
            if not accepted:
                status = "line-search-stopped"
                break
        statuses.append(status)
    y, matrices = model.unpack(parameters)
    slacks = rg_dual_slacks(model, parameters)
    return RGRelaxationCandidate(
        delta=float(delta),
        depth=depth,
        bond_dimension=model.bond_dimension,
        raw_lower=-y,
        status="barrier-" + ",".join(statuses),
        omega_dimension=model.omega_dimension,
        rho3=np.empty((0, 0), dtype=np.complex128),
        omegas=(),
        max_equality_residual=0.0,
        minimum_primal_eigenvalue=np.nan,
        dual_objective=-y,
        dual_slack_min_eigenvalues=tuple(
            float(np.linalg.eigvalsh(slack)[0]) for slack in slacks
        ),
        dual_stationarity_residual=0.0,
        equality_duals=(y, *matrices),
    )
