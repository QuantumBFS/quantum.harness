"""Validator-only leakage-sensitive gate metrics.

These functions consume privileged backend states and must not be passed to an
online controller.  Public experiment results intentionally contain none of
the quantities calculated here.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import qutip as qt
from scipy import optimize

from .backend import PhysicsBackend, SimulationContext
from .contracts import ExperimentProgram
from .oracle import TruthOracle


def _validate_maps(target: np.ndarray, actual: np.ndarray) -> int:
    if (
        target.ndim != 2
        or actual.ndim != 2
        or target.shape != actual.shape
        or target.shape[0] != target.shape[1]
    ):
        raise ValueError("target and actual must be square shape-matched maps")
    return target.shape[0]


def coherent_average_gate_fidelity(
    target: np.ndarray, actual: np.ndarray
) -> float:
    """Haar average fidelity of a projected coherent map.

    ``actual`` may be non-unitary because population can leave the
    computational subspace.  This is Eq. (5) of Jandura--Pupillo generalized
    from diagonal phase maps to an arbitrary projected map.
    """

    dimension = _validate_maps(target, actual)
    return float(
        (
            np.trace(actual.conj().T @ actual).real
            + abs(np.trace(target.conj().T @ actual)) ** 2
        )
        / (dimension * (dimension + 1))
    )


def local_z_cz_target(actual: np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
    """Return the local-Z-dressed CZ maximizing trace overlap with ``actual``.

    Basis order is ``00, 01, 10, 11``.  The optimizer is deterministic and is
    used only once at the nominal point; callers must reuse the returned target
    for noisy realizations.
    """

    if actual.shape != (4, 4):
        raise ValueError("local-Z CZ fitting requires a two-qubit map")

    def target_for(first: float, second: float) -> np.ndarray:
        return np.diag(
            np.asarray(
                (
                    1.0,
                    np.exp(1j * second),
                    np.exp(1j * first),
                    -np.exp(1j * (first + second)),
                ),
                dtype=complex,
            )
        )

    diagonal = np.diag(actual)
    initial_first = float(np.angle(diagonal[2]))
    initial_second = float(np.angle(diagonal[1]))

    def objective(phases: np.ndarray) -> float:
        target = target_for(float(phases[0]), float(phases[1]))
        return -float(abs(np.trace(target.conj().T @ actual)) ** 2)

    starts = (
        (initial_first, initial_second),
        (initial_first + math.pi, initial_second),
        (initial_first, initial_second + math.pi),
        (initial_first + math.pi, initial_second + math.pi),
        (0.0, 0.0),
    )
    candidates = [
        optimize.minimize(
            objective,
            np.asarray(start),
            method="Nelder-Mead",
            options={"xatol": 1e-12, "fatol": 1e-12, "maxiter": 4000},
        )
        for start in starts
    ]
    best = min(candidates, key=lambda result: float(result.fun))
    first, second = (float(value) for value in best.x)
    first = math.remainder(first, 2.0 * math.pi)
    second = math.remainder(second, 2.0 * math.pi)
    return target_for(first, second), (first, second)


@dataclass(frozen=True)
class CoherentGateMetrics:
    average_fidelity: float
    squared_trace_overlap: float
    computational_return: float
    local_z_phase_rad: tuple[float, float]
    projected_map: np.ndarray
    target: np.ndarray


@dataclass(frozen=True)
class CoherentEnsembleMetrics:
    realization_count: int
    fidelity_mean: float
    fidelity_standard_deviation: float
    fidelity_standard_error: float
    infidelity_mean: float
    computational_return_mean: float
    computational_return_standard_deviation: float
    fidelities: tuple[float, ...]
    computational_returns: tuple[float, ...]


def evaluate_coherent_gate(
    backend: PhysicsBackend,
    program: ExperimentProgram,
    *,
    context: SimulationContext | None = None,
    target: np.ndarray | None = None,
) -> CoherentGateMetrics:
    """Evaluate one coherent two-qubit gate realization."""

    projected = TruthOracle(backend).computational_map(
        program, context=context
    )
    phases = (math.nan, math.nan)
    if target is None:
        target, phases = local_z_cz_target(projected)
    dimension = _validate_maps(target, projected)
    return CoherentGateMetrics(
        average_fidelity=coherent_average_gate_fidelity(target, projected),
        squared_trace_overlap=float(
            abs(np.trace(target.conj().T @ projected)) ** 2 / dimension**2
        ),
        computational_return=float(
            np.trace(projected.conj().T @ projected).real / dimension
        ),
        local_z_phase_rad=phases,
        projected_map=projected,
        target=target,
    )


def evaluate_coherent_ensemble(
    backend: PhysicsBackend,
    program: ExperimentProgram,
    *,
    contexts: tuple[SimulationContext, ...],
    target: np.ndarray,
) -> CoherentEnsembleMetrics:
    """Evaluate a fixed-target coherent response over hidden realizations."""

    if not contexts:
        raise ValueError("at least one context is required")
    metrics = tuple(
        evaluate_coherent_gate(
            backend,
            program,
            context=context,
            target=target,
        )
        for context in contexts
    )
    fidelities = np.asarray(
        [metric.average_fidelity for metric in metrics], dtype=float
    )
    returns = np.asarray(
        [metric.computational_return for metric in metrics], dtype=float
    )
    ddof = 1 if len(metrics) > 1 else 0
    fidelity_std = float(np.std(fidelities, ddof=ddof))
    return CoherentEnsembleMetrics(
        realization_count=len(metrics),
        fidelity_mean=float(np.mean(fidelities)),
        fidelity_standard_deviation=fidelity_std,
        fidelity_standard_error=fidelity_std / math.sqrt(len(metrics)),
        infidelity_mean=float(np.mean(1.0 - fidelities)),
        computational_return_mean=float(np.mean(returns)),
        computational_return_standard_deviation=float(
            np.std(returns, ddof=ddof)
        ),
        fidelities=tuple(float(value) for value in fidelities),
        computational_returns=tuple(float(value) for value in returns),
    )


@dataclass(frozen=True)
class OpenSystemGateMetrics:
    raw_average_fidelity: float
    weighted_conditional_fidelity: float
    computational_return: float
    failure_sink: float
    excited_residual: float
    not_failure_sink: float
    bookkeeping_error: float
    trace_error: float


@dataclass(frozen=True)
class StateDesignGateMetrics:
    """Exact validator result averaged over a finite pure-state design."""

    design_name: str
    state_count: int
    raw_average_fidelity: float
    computational_return: float
    weighted_conditional_fidelity: float


def _computational_bitstrings(n_atoms: int) -> tuple[str, ...]:
    return tuple(
        "".join(bits)
        for bits in itertools.product(("0", "1"), repeat=n_atoms)
    )


def evaluate_open_system_gate(
    backend: PhysicsBackend,
    program: ExperimentProgram,
    *,
    target: np.ndarray,
    context: SimulationContext | None = None,
) -> OpenSystemGateMetrics:
    """Calculate exact raw Haar fidelity by propagating a basis of operators."""

    bitstrings = _computational_bitstrings(backend.n_atoms)
    dimension = len(bitstrings)
    if dimension != 4 or target.shape != (dimension, dimension):
        raise ValueError("S3-D open-system evaluator requires two qubits")
    basis = tuple(backend.computational_basis_state(bits) for bits in bitstrings)
    target_vectors = tuple(
        sum(
            (
                target[row, column] * basis[row]
                for row in range(dimension)
            ),
            0.0 * basis[0],
        )
        for column in range(dimension)
    )

    evolved: dict[tuple[int, int], qt.Qobj] = {}
    maximum_trace_error = 0.0
    for row in range(dimension):
        for column in range(dimension):
            operator = basis[row] * basis[column].dag()
            final = backend.simulate(
                program,
                initial_state=operator,
                ignore_prepare=True,
                context=context,
            ).state
            evolved[(row, column)] = final
            expected_trace = 1.0 if row == column else 0.0
            maximum_trace_error = max(
                maximum_trace_error,
                abs(complex(final.tr()) - expected_trace),
            )

    term_population = 0.0
    for column in range(dimension):
        state = evolved[(column, column)]
        for target_vector in target_vectors:
            term_population += float(
                np.real(target_vector.dag() * state * target_vector)
            )
    term_coherence = 0.0j
    for first in range(dimension):
        for second in range(dimension):
            state = evolved[(second, first)]
            term_coherence += (
                target_vectors[second].dag()
                * state
                * target_vectors[first]
            )
    raw_fidelity = float(
        np.real(term_population + term_coherence)
        / (dimension * (dimension + 1))
    )

    label_probabilities: dict[str, float] = {}
    for column in range(dimension):
        probabilities = backend.outcome_probabilities(
            evolved[(column, column)]
        )
        for label, probability in probabilities.items():
            label_probabilities[label] = (
                label_probabilities.get(label, 0.0)
                + probability / dimension
            )
    computational_return = sum(
        probability
        for label, probability in label_probabilities.items()
        if set(label) <= {"0", "1"}
    )
    failure_sink = sum(
        probability
        for label, probability in label_probabilities.items()
        if "L" in label
    )
    excited_residual = sum(
        probability
        for label, probability in label_probabilities.items()
        if "L" not in label and not set(label) <= {"0", "1"}
    )
    not_failure_sink = 1.0 - failure_sink
    bookkeeping_error = abs(
        computational_return + failure_sink + excited_residual - 1.0
    )
    conditional = (
        raw_fidelity / not_failure_sink
        if not_failure_sink > 0
        else math.nan
    )
    return OpenSystemGateMetrics(
        raw_average_fidelity=raw_fidelity,
        weighted_conditional_fidelity=conditional,
        computational_return=computational_return,
        failure_sink=failure_sink,
        excited_residual=excited_residual,
        not_failure_sink=not_failure_sink,
        bookkeeping_error=bookkeeping_error,
        trace_error=float(maximum_trace_error),
    )


def evaluate_state_design_gate(
    backend: PhysicsBackend,
    program: ExperimentProgram,
    *,
    target: np.ndarray,
    state_vectors: tuple[np.ndarray, ...],
    design_name: str,
    context: SimulationContext | None = None,
) -> StateDesignGateMetrics:
    """Average state fidelity over an explicit computational-state design.

    This is a validator-only quantity.  For the 12 symmetric stabilizer states
    used by SSB it equals the symmetric-subspace state-design average, not the
    full two-qubit Haar average.
    """

    bitstrings = _computational_bitstrings(backend.n_atoms)
    dimension = len(bitstrings)
    if (
        dimension != target.shape[0]
        or target.shape != (dimension, dimension)
        or not state_vectors
        or not design_name
    ):
        raise ValueError("target and state design do not match the backend")
    basis = tuple(backend.computational_basis_state(bits) for bits in bitstrings)
    raw_fidelities: list[float] = []
    returns: list[float] = []
    for vector in state_vectors:
        coefficients = np.asarray(vector, dtype=complex)
        if coefficients.shape != (dimension,) or not np.isclose(
            np.vdot(coefficients, coefficients), 1.0, atol=1e-10
        ):
            raise ValueError("each design vector must be normalized")
        initial = sum(
            (
                coefficients[index] * basis[index]
                for index in range(dimension)
            ),
            0.0 * basis[0],
        )
        target_coefficients = target @ coefficients
        target_state = sum(
            (
                target_coefficients[index] * basis[index]
                for index in range(dimension)
            ),
            0.0 * basis[0],
        )
        final = backend.simulate(
            program,
            initial_state=initial,
            ignore_prepare=True,
            context=context,
        ).state
        if final.isket:
            fidelity = float(abs(target_state.dag() * final) ** 2)
        else:
            fidelity = float(np.real(target_state.dag() * final * target_state))
        probabilities = backend.outcome_probabilities(final)
        computational_return = sum(
            probability
            for label, probability in probabilities.items()
            if set(label) <= {"0", "1"}
        )
        raw_fidelities.append(fidelity)
        returns.append(computational_return)
    raw = float(np.mean(raw_fidelities))
    returned = float(np.mean(returns))
    return StateDesignGateMetrics(
        design_name=design_name,
        state_count=len(state_vectors),
        raw_average_fidelity=raw,
        computational_return=returned,
        weighted_conditional_fidelity=(
            raw / returned if returned > 0.0 else math.nan
        ),
    )
