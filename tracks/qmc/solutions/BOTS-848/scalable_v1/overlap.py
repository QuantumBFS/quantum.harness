from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any

import numpy as np

from benchmark_v0.ed_oracle import _select_lowest_l_state
from benchmark_v0.fock_ed import (
    fixed_m_basis,
    hamiltonian_matrix,
    l_squared_matrix,
)
from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)

from .contracts import CandidateAdapter, StateHandle
from .protocol import ProtocolConfig


L2_M_VALUES = (-2, -1, 0, 1, 2)
OVERLAP_LABELS = ("ground", "-2", "-1", "0", "1", "2")


def _finite_complex_vector(values: Any, *, name: str) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.complex128)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite vector") from error
    if array.ndim != 1:
        raise ValueError(f"{name} must be a vector")
    if array.size == 0:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


def _clip_fidelity(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("fidelity must be finite")
    tolerance = 64.0 * np.finfo(float).eps
    if value < -tolerance or value > 1.0 + tolerance:
        raise ValueError("fidelity must be between zero and one")
    return float(np.clip(value, 0.0, 1.0))


def normalized_fidelity(
    candidate_amplitude: Any,
    oracle_amplitude: Any,
) -> float:
    """Return the normalized squared overlap of two amplitude vectors."""

    candidate = _finite_complex_vector(
        candidate_amplitude, name="candidate amplitudes"
    )
    oracle = _finite_complex_vector(oracle_amplitude, name="oracle amplitudes")
    if candidate.shape != oracle.shape:
        raise ValueError("candidate and oracle amplitudes must have the same shape")

    candidate_scale = float(np.max(np.abs(candidate)))
    oracle_scale = float(np.max(np.abs(oracle)))
    if candidate_scale == 0.0 or oracle_scale == 0.0:
        raise ValueError("normalized fidelity has a zero denominator")
    scaled_candidate = candidate / candidate_scale
    scaled_oracle = oracle / oracle_scale
    denominator = float(
        np.real(np.vdot(scaled_candidate, scaled_candidate))
        * np.real(np.vdot(scaled_oracle, scaled_oracle))
    )
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise ValueError("normalized fidelity has a zero denominator")
    numerator = float(abs(np.vdot(scaled_candidate, scaled_oracle)) ** 2)
    return _clip_fidelity(numerator / denominator)


@dataclass(frozen=True)
class FidelityEstimate:
    mean: float
    standard_error: float
    effective_sample_size: float

    def __post_init__(self) -> None:
        values = (self.mean, self.standard_error, self.effective_sample_size)
        if any(type(value) is bool for value in values):
            raise ValueError("fidelity estimate values must be finite")
        try:
            mean, standard_error, effective_sample_size = map(float, values)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("fidelity estimate values must be finite") from error
        if not all(
            math.isfinite(value)
            for value in (mean, standard_error, effective_sample_size)
        ):
            raise ValueError("fidelity estimate values must be finite")
        if mean < 0.0 or mean > 1.0:
            raise ValueError("fidelity mean must be between zero and one")
        if standard_error < 0.0:
            raise ValueError("fidelity standard_error must be nonnegative")
        if effective_sample_size <= 0.0:
            raise ValueError("fidelity effective_sample_size must be positive")
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "standard_error", standard_error)
        object.__setattr__(self, "effective_sample_size", effective_sample_size)

    def to_dict(self) -> dict[str, float]:
        return {
            "mean": float(self.mean),
            "standard_error": float(self.standard_error),
            "effective_sample_size": float(self.effective_sample_size),
        }


def _ratio_fidelity_from_sums(
    ratio_sum: complex,
    squared_magnitude_sum: float,
    count: int,
) -> float:
    if count <= 0 or squared_magnitude_sum <= 0.0:
        raise ValueError("fidelity ratio has a zero denominator")
    value = abs(ratio_sum) ** 2 / (count * squared_magnitude_sum)
    return _clip_fidelity(float(value))


def _estimate_ratio_fidelity(
    ratios: np.ndarray,
    *,
    block_size: int,
) -> FidelityEstimate:
    if type(block_size) is not int or block_size <= 0:
        raise ValueError("block_size must be a positive integer")
    sample_count = int(ratios.size)
    if sample_count % block_size:
        raise ValueError("sample count must be divisible by block_size")
    block_count = sample_count // block_size
    if block_count < 2:
        raise ValueError("fidelity estimation requires at least two blocks")
    if not np.all(np.isfinite(ratios)):
        raise ValueError("stabilized amplitude ratios must be finite")

    squared_magnitudes = np.abs(ratios) ** 2
    ratio_sum = complex(np.sum(ratios, dtype=np.complex128))
    squared_sum = float(np.sum(squared_magnitudes, dtype=np.float64))
    mean = _ratio_fidelity_from_sums(ratio_sum, squared_sum, sample_count)

    block_ratio_sums = ratios.reshape(block_count, block_size).sum(axis=1)
    block_squared_sums = squared_magnitudes.reshape(
        block_count, block_size
    ).sum(axis=1)
    leave_one_out = np.empty(block_count, dtype=float)
    leave_count = sample_count - block_size
    for block_index in range(block_count):
        leave_one_out[block_index] = _ratio_fidelity_from_sums(
            ratio_sum - block_ratio_sums[block_index],
            squared_sum - float(block_squared_sums[block_index]),
            leave_count,
        )
    jackknife_center = float(np.mean(leave_one_out))
    standard_error = math.sqrt(
        (block_count - 1.0)
        / block_count
        * float(np.sum((leave_one_out - jackknife_center) ** 2))
    )
    return FidelityEstimate(mean, standard_error, float(sample_count))


def fidelity_from_log_amplitudes(
    candidate_log_amplitude: Any,
    oracle_log_amplitude: Any,
    *,
    block_size: int,
) -> FidelityEstimate:
    """Estimate fidelity from log amplitudes sampled from candidate |psi|^2."""

    candidate_log = _finite_complex_vector(
        candidate_log_amplitude, name="candidate log amplitudes"
    )
    oracle_log = _finite_complex_vector(
        oracle_log_amplitude, name="oracle log amplitudes"
    )
    if candidate_log.shape != oracle_log.shape:
        raise ValueError("candidate and oracle log amplitudes must have the same shape")

    log_ratio = oracle_log - candidate_log
    shift = float(np.max(np.real(log_ratio)))
    ratios = np.exp(log_ratio - shift)
    return _estimate_ratio_fidelity(ratios, block_size=block_size)


def _fidelity_from_oracle_amplitudes(
    candidate_log_amplitude: Any,
    oracle_amplitude: Any,
    *,
    block_size: int,
) -> FidelityEstimate:
    candidate_log = _finite_complex_vector(
        candidate_log_amplitude, name="candidate log amplitudes"
    )
    oracle = _finite_complex_vector(oracle_amplitude, name="oracle amplitudes")
    if candidate_log.shape != oracle.shape:
        raise ValueError(
            "candidate logs and oracle amplitudes must have the same shape"
        )
    nonzero = np.abs(oracle) > 0.0
    if not np.any(nonzero):
        raise ValueError("fidelity ratio has a zero denominator")

    log_magnitude = np.full(oracle.shape, -np.inf, dtype=float)
    log_magnitude[nonzero] = np.log(np.abs(oracle[nonzero])) - np.real(
        candidate_log[nonzero]
    )
    shift = float(np.max(log_magnitude[nonzero]))
    ratios = np.zeros(oracle.shape, dtype=np.complex128)
    ratios[nonzero] = np.exp(
        log_magnitude[nonzero]
        - shift
        + 1.0j
        * (np.angle(oracle[nonzero]) - np.imag(candidate_log[nonzero]))
    )
    return _estimate_ratio_fidelity(ratios, block_size=block_size)


@dataclass(frozen=True)
class _EDState:
    basis: tuple[int, ...]
    coefficients: np.ndarray
    basis_index: Mapping[int, int]


class EDOverlapOracle:
    """Immutable in-memory ED eigenvectors with discrete and sphere amplitudes."""

    def __init__(
        self,
        *,
        n_electrons: int,
        two_q: int,
        state_data: Mapping[str, tuple[tuple[int, ...], np.ndarray]],
        chunk_size: int = 64,
    ) -> None:
        if (
            type(n_electrons) is not int
            or n_electrons <= 0
            or type(two_q) is not int
            or two_q <= 0
        ):
            raise ValueError("ED system sizes must be positive integers")
        if type(chunk_size) is not int or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if set(state_data) != set(OVERLAP_LABELS):
            raise ValueError("ED state data must contain the exact overlap labels")

        states: dict[str, _EDState] = {}
        for label in OVERLAP_LABELS:
            basis_value, coefficients_value = state_data[label]
            basis = tuple(basis_value)
            if (
                not basis
                or len(set(basis)) != len(basis)
                or any(
                    type(state) is not int
                    or state < 0
                    or state.bit_count() != n_electrons
                    for state in basis
                )
            ):
                raise ValueError("ED bases must contain unique occupation bitsets")
            coefficients = _finite_complex_vector(
                coefficients_value, name=f"ED coefficients for {label}"
            ).copy()
            if coefficients.shape != (len(basis),):
                raise ValueError("ED coefficients must match their basis")
            norm = float(np.linalg.norm(coefficients))
            if not math.isfinite(norm) or norm <= 0.0:
                raise ValueError("ED coefficient vectors must have nonzero norm")
            coefficients /= norm
            coefficients.setflags(write=False)
            states[label] = _EDState(
                basis=basis,
                coefficients=coefficients,
                basis_index=MappingProxyType(
                    {state: index for index, state in enumerate(basis)}
                ),
            )

        self._n_electrons = n_electrons
        self._two_q = two_q
        self._chunk_size = chunk_size
        self._states = MappingProxyType(states)
        self._orbital_normalizations = self._build_orbital_normalizations(two_q)

    @staticmethod
    def _build_orbital_normalizations(two_q: int) -> np.ndarray:
        values = np.empty(two_q + 1, dtype=float)
        for orbital in range(two_q + 1):
            v_power = two_q - orbital
            gauge_sign = -1.0 if v_power % 2 else 1.0
            values[orbital] = gauge_sign * math.sqrt(
                (two_q + 1)
                * math.comb(two_q, orbital)
                / (4.0 * math.pi)
            )
        values.setflags(write=False)
        return values

    def amplitude(self, label: str, configs: Any) -> np.ndarray:
        if type(label) is not str or label not in self._states:
            raise ValueError("invalid ED overlap label")
        raw = np.asarray(configs)
        state = self._states[label]
        if raw.ndim == 1 and raw.dtype.kind in "iu":
            if raw.size == 0:
                raise ValueError("occupation configurations have invalid shape")
            if np.issubdtype(raw.dtype, np.signedinteger) and np.any(raw < 0):
                raise ValueError("occupation bitsets must be nonnegative")
            result = np.zeros(raw.shape[0], dtype=np.complex128)
            for sample_index, bitset in enumerate(raw):
                basis_index = state.basis_index.get(int(bitset))
                if basis_index is not None:
                    result[sample_index] = state.coefficients[basis_index]
            return result

        try:
            spinors = np.asarray(configs, dtype=np.complex128)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "sphere spinor configurations have invalid shape"
            ) from error
        if (
            spinors.ndim != 3
            or spinors.shape[0] == 0
            or spinors.shape[1:] != (self._n_electrons, 2)
        ):
            raise ValueError("sphere spinor configurations have invalid shape")
        if not np.all(np.isfinite(spinors)):
            raise ValueError("sphere spinor configurations must be finite")
        return self._sphere_amplitude(state, spinors)

    def _sphere_amplitude(
        self,
        state: _EDState,
        spinors: np.ndarray,
    ) -> np.ndarray:
        result = np.zeros(spinors.shape[0], dtype=np.complex128)
        slater_normalization = 1.0 / math.sqrt(math.factorial(self._n_electrons))
        occupied_by_basis = tuple(
            tuple(
                orbital
                for orbital in range(self._two_q + 1)
                if bitset & (1 << orbital)
            )
            for bitset in state.basis
        )
        for start in range(0, spinors.shape[0], self._chunk_size):
            stop = min(start + self._chunk_size, spinors.shape[0])
            chunk = spinors[start:stop]
            u = chunk[:, :, 0]
            v = chunk[:, :, 1]
            orbitals = np.empty(
                (stop - start, self._n_electrons, self._two_q + 1),
                dtype=np.complex128,
            )
            for orbital in range(self._two_q + 1):
                orbitals[:, :, orbital] = (
                    self._orbital_normalizations[orbital]
                    * u**orbital
                    * v ** (self._two_q - orbital)
                )
            chunk_result = np.zeros(stop - start, dtype=np.complex128)
            for coefficient, occupied in zip(
                state.coefficients, occupied_by_basis, strict=True
            ):
                if coefficient != 0.0:
                    chunk_result += coefficient * np.linalg.det(
                        orbitals[:, :, occupied]
                    )
            result[start:stop] = slater_normalization * chunk_result
        if not np.all(np.isfinite(result)):
            raise ValueError("ED sphere amplitudes are not finite")
        return result


def _validated_physics_integer(physics: Mapping[str, Any], name: str) -> int:
    value = physics.get(name)
    if type(value) is not int or value <= 0:
        raise ValueError(f"physics.{name} must be a positive integer")
    return value


def build_ed_overlap_oracle(physics: Mapping[str, Any]) -> EDOverlapOracle:
    """Build the strict-LLL Coulomb ED states after the reveal boundary."""

    n_electrons = _validated_physics_integer(physics, "n_electrons")
    two_q = _validated_physics_integer(physics, "two_q")
    integrals = coulomb_integrals(two_q)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    state_data: dict[str, tuple[tuple[int, ...], np.ndarray]] = {}

    for magnetic_number in L2_M_VALUES:
        basis = fixed_m_basis(n_electrons, two_q, float(magnetic_number))
        hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
        hamiltonian = (hamiltonian + hamiltonian.T.conj()) / 2.0
        l_squared = l_squared_matrix(
            basis,
            two_q=two_q,
            target_m=float(magnetic_number),
        )
        eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
        selected_l2 = _select_lowest_l_state(
            eigenvalues,
            eigenvectors,
            l_squared,
            target_l=2,
        )
        if (
            abs(float(selected_l2["l2_expectation"]) - 6.0) >= 1.0e-5
            or float(selected_l2["l2_variance"]) >= 1.0e-4
        ):
            raise ValueError("ED sector does not contain a resolved L=2 state")
        state_data[str(magnetic_number)] = (
            basis,
            eigenvectors[:, int(selected_l2["eigenvector_index"])],
        )

        if magnetic_number == 0:
            selected_ground = _select_lowest_l_state(
                eigenvalues,
                eigenvectors,
                l_squared,
                target_l=0,
            )
            if (
                abs(float(selected_ground["l2_expectation"])) >= 1.0e-5
                or float(selected_ground["l2_variance"]) >= 1.0e-4
            ):
                raise ValueError("ED sector does not contain a resolved L=0 state")
            state_data["ground"] = (
                basis,
                eigenvectors[:, int(selected_ground["eigenvector_index"])],
            )

    return EDOverlapOracle(
        n_electrons=n_electrons,
        two_q=two_q,
        state_data=state_data,
    )


def _validated_overlap_states(
    candidate: CandidateAdapter,
) -> tuple[StateHandle, dict[int, StateHandle]]:
    tower = dict(candidate.generate_multiplet())
    if not all(type(m) is int for m in tower) or set(tower) != set(L2_M_VALUES):
        raise ValueError("candidate must provide the exact integer M=-2..2 multiplet")
    ground = candidate.ground_state()
    if (
        type(ground.l) is not int
        or type(ground.m) is not int
        or ground.l != 0
        or ground.m != 0
    ):
        raise ValueError("ground state must have exact integer l=0, m=0 metadata")
    for magnetic_number, state in tower.items():
        if (
            type(state.l) is not int
            or type(state.m) is not int
            or state.l != 2
            or state.m != magnetic_number
        ):
            raise ValueError(
                "each L=2 state must have exact integer l=2 and mapping-key m"
            )
    return ground, tower


def evaluate_overlaps(
    candidate: CandidateAdapter,
    protocol: ProtocolConfig,
    oracle: EDOverlapOracle,
) -> dict[str, Any]:
    """Evaluate observed-only ED fidelities on the frozen reveal schedule."""

    ground, tower = _validated_overlap_states(candidate)
    states = (ground, *(tower[m] for m in L2_M_VALUES))
    labels = OVERLAP_LABELS
    sampling = protocol.sampling
    sample_count = int(sampling["minimum_ess_per_state"])
    burn_in_steps = int(sampling["burn_in_steps"])
    block_size = int(sampling["block_size"])
    base_seed = int(protocol.symmetry["seed"])
    estimates: list[FidelityEstimate] = []

    for state_index, (state, label) in enumerate(zip(states, labels, strict=True)):
        seed = base_seed + 1000 * state_index
        batch = state.sample(sample_count, seed)
        if (
            batch.n_samples != sample_count
            or batch.seed != seed
            or len(batch.configs) != sample_count
        ):
            raise ValueError("sample batch does not match the frozen schedule")
        if batch.burn_in_steps != burn_in_steps:
            raise ValueError("sample batch does not use the frozen burn-in")
        candidate_log = np.asarray(state.logpsi(batch.configs))
        if candidate_log.shape != (sample_count,) or not np.all(
            np.isfinite(candidate_log)
        ):
            raise ValueError("logpsi must be a finite vector of sampled values")
        oracle_amplitude = oracle.amplitude(label, batch.configs)
        estimates.append(
            _fidelity_from_oracle_amplitudes(
                candidate_log,
                oracle_amplitude,
                block_size=block_size,
            )
        )

    return {
        "ground_fidelity": estimates[0],
        "l2_fidelity_by_m": {
            str(magnetic_number): estimates[index + 1]
            for index, magnetic_number in enumerate(L2_M_VALUES)
        },
    }
