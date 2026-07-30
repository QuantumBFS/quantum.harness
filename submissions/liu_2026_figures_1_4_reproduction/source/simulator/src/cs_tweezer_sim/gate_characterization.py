"""Experimental single-qubit and CZ characterization over public primitives.

This module deliberately contains no simulator state or truth oracle.  It
compiles ordinary microwave and user-supplied entangling-pulse programs, then
estimates operational quantities from finite-shot public counts.  Exact
channel validation remains in :mod:`cs_tweezer_sim.gate_metrics`.

The symmetric-stabilizer benchmarking (SSB) circuits and tables follow
Tsai et al., PRX Quantum 6, 010331 (2025), Appendix E.  SSB estimates the
symmetric-subspace fidelity ``F_sym``; it is not a full two-qubit Haar
fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np
from scipy import optimize, stats

from .contracts import (
    ConstantPulse,
    ExperimentProgram,
    ExperimentResult,
    Measure,
    Operation,
    Play,
    Prepare,
)


_TWO_PI = 2.0 * math.pi


def wrap_phase(phase_rad: float) -> float:
    """Wrap one phase to ``[-pi, pi]``."""

    return math.remainder(float(phase_rad), _TWO_PI)


def _validate_gate_body(program: ExperimentProgram) -> tuple[Operation, ...]:
    """Return a reusable gate body, rejecting preparation and measurement."""

    if any(isinstance(op, (Prepare, Measure)) for op in program.operations):
        raise ValueError(
            "a reusable gate program may not contain Prepare or Measure"
        )
    return program.operations


def _rotation_play(
    *,
    channel: str,
    targets: tuple[int, ...],
    angle_rad: float,
    phase_rad: float,
    rabi_rad_per_us: float,
) -> Play | None:
    if rabi_rad_per_us <= 0 or not math.isfinite(rabi_rad_per_us):
        raise ValueError("rabi_rad_per_us must be finite and positive")
    angle = wrap_phase(angle_rad)
    if abs(angle) < 1e-14:
        return None
    phase = float(phase_rad)
    if angle < 0:
        angle = -angle
        phase += math.pi
    return Play(
        channel=channel,
        targets=targets,
        pulse=ConstantPulse(
            duration_us=angle / rabi_rad_per_us,
            amplitude_rad_per_us=rabi_rad_per_us,
            phase_rad=wrap_phase(phase),
        ),
    )


def equatorial_rotation_matrix(angle_rad: float, phase_rad: float) -> np.ndarray:
    """Return the ideal matrix implemented by an equatorial microwave pulse."""

    axis = np.asarray(
        (
            (0.0, np.exp(-1j * phase_rad)),
            (np.exp(1j * phase_rad), 0.0),
        ),
        dtype=complex,
    )
    return (
        math.cos(0.5 * angle_rad) * np.eye(2, dtype=complex)
        - 1j * math.sin(0.5 * angle_rad) * axis
    )


def _normalize_unitary_to_su2(unitary: np.ndarray) -> np.ndarray:
    matrix = np.asarray(unitary, dtype=complex)
    if matrix.shape != (2, 2):
        raise ValueError("single-qubit unitary must have shape (2, 2)")
    if not np.allclose(matrix.conj().T @ matrix, np.eye(2), atol=1e-10):
        raise ValueError("single-qubit target must be unitary")
    root = np.sqrt(np.linalg.det(matrix))
    if abs(root) < 1e-14:
        raise ValueError("single-qubit target has singular determinant")
    return matrix / root


def zyz_angles(unitary: np.ndarray) -> tuple[float, float, float]:
    """Return ``alpha, beta, gamma`` for ``Rz(alpha) Ry(beta) Rz(gamma)``.

    Global phase is discarded.  Singular north/south-pole decompositions use a
    deterministic convention so manifests remain reproducible.
    """

    su2 = _normalize_unitary_to_su2(unitary)
    a = complex(su2[0, 0])
    b = complex(su2[0, 1])
    beta = 2.0 * math.atan2(abs(b), abs(a))
    if abs(b) < 1e-13:
        alpha = -2.0 * float(np.angle(a))
        gamma = 0.0
    elif abs(a) < 1e-13:
        alpha = -2.0 * float(np.angle(-b))
        gamma = 0.0
    else:
        angle_sum = -2.0 * float(np.angle(a))
        angle_difference = -2.0 * float(np.angle(-b))
        alpha = 0.5 * (angle_sum + angle_difference)
        gamma = 0.5 * (angle_sum - angle_difference)
    return wrap_phase(alpha), beta, wrap_phase(gamma)


def _physical_rz_plays(
    *,
    angle_rad: float,
    channel: str,
    targets: tuple[int, ...],
    rabi_rad_per_us: float,
) -> tuple[Play, ...]:
    """Compile Rz without a privileged frame opcode.

    In chronological order this is ``Rx(-pi/2), Ry(theta), Rx(pi/2)`` and
    implements ``Rx(pi/2) Ry(theta) Rx(-pi/2) = Rz(theta)``.
    """

    specifications = (
        (-0.5 * math.pi, 0.0),
        (angle_rad, 0.5 * math.pi),
        (0.5 * math.pi, 0.0),
    )
    return tuple(
        play
        for angle, phase in specifications
        if (
            play := _rotation_play(
                channel=channel,
                targets=targets,
                angle_rad=angle,
                phase_rad=phase,
                rabi_rad_per_us=rabi_rad_per_us,
            )
        )
        is not None
    )


def compile_single_qubit_unitary(
    unitary: np.ndarray,
    *,
    n_atoms: int,
    atom: int,
    rabi_rad_per_us: float,
    channel: str = "microwave",
    initial_bitstring: str | None = None,
    measure: bool = False,
    name: str = "arbitrary-single-qubit",
) -> ExperimentProgram:
    """Compile an arbitrary SU(2) operation into existing ``Play`` primitives."""

    if n_atoms <= 0 or atom < 0 or atom >= n_atoms:
        raise ValueError("atom must address one of n_atoms")
    if initial_bitstring is not None and (
        len(initial_bitstring) != n_atoms or set(initial_bitstring) - {"0", "1"}
    ):
        raise ValueError("initial_bitstring must contain one bit per atom")
    alpha, beta, gamma = zyz_angles(unitary)
    targets = (atom,)
    operations: list[Operation] = []
    if initial_bitstring is not None:
        operations.append(Prepare(initial_bitstring))
    operations.extend(
        _physical_rz_plays(
            angle_rad=gamma,
            channel=channel,
            targets=targets,
            rabi_rad_per_us=rabi_rad_per_us,
        )
    )
    middle = _rotation_play(
        channel=channel,
        targets=targets,
        angle_rad=beta,
        phase_rad=0.5 * math.pi,
        rabi_rad_per_us=rabi_rad_per_us,
    )
    if middle is not None:
        operations.append(middle)
    operations.extend(
        _physical_rz_plays(
            angle_rad=alpha,
            channel=channel,
            targets=targets,
            rabi_rad_per_us=rabi_rad_per_us,
        )
    )
    if measure:
        operations.append(Measure())
    return ExperimentProgram(tuple(operations), name=name)


def ideal_program_single_qubit_matrix(program: ExperimentProgram) -> np.ndarray:
    """Evaluate the ideal 2x2 matrix of a microwave-only compiled program."""

    result = np.eye(2, dtype=complex)
    for operation in program.operations:
        if isinstance(operation, Play):
            pulse = operation.pulse
            result = equatorial_rotation_matrix(
                pulse.duration_us * pulse.amplitude_rad_per_us,
                pulse.phase_rad,
            ) @ result
        elif not isinstance(operation, (Prepare, Measure)):
            raise ValueError("program contains a non-microwave operation")
    return result


def _append_operations(
    program: ExperimentProgram, operations: Iterable[Operation]
) -> ExperimentProgram:
    for operation in operations:
        program = program.then(operation)
    return program


def conditional_ramsey_program(
    gate_program: ExperimentProgram,
    *,
    control_state: int,
    analysis_phase_rad: float,
    rabi_rad_per_us: float,
    control_atom: int = 0,
    target_atom: int = 1,
    microwave_channel: str = "microwave",
    name: str = "cz-conditional-ramsey",
) -> ExperimentProgram:
    """Build one conditional-Ramsey point around an external CZ program."""

    if control_state not in (0, 1) or control_atom == target_atom:
        raise ValueError("conditional Ramsey control/target are invalid")
    n_atoms = max(control_atom, target_atom) + 1
    bits = ["0"] * n_atoms
    bits[control_atom] = str(control_state)
    program = ExperimentProgram(
        (Prepare("".join(bits)),),
        name=f"{name}:control-{control_state}",
    )
    first = _rotation_play(
        channel=microwave_channel,
        targets=(target_atom,),
        angle_rad=0.5 * math.pi,
        phase_rad=0.0,
        rabi_rad_per_us=rabi_rad_per_us,
    )
    assert first is not None
    program = program.then(first)
    program = _append_operations(program, _validate_gate_body(gate_program))
    second = _rotation_play(
        channel=microwave_channel,
        targets=(target_atom,),
        angle_rad=0.5 * math.pi,
        phase_rad=analysis_phase_rad,
        rabi_rad_per_us=rabi_rad_per_us,
    )
    assert second is not None
    return program.then(second).then(Measure())


def parity_analysis_program(
    prepared_state_program: ExperimentProgram,
    *,
    analysis_phase_rad: float,
    rabi_rad_per_us: float,
    atoms: tuple[int, int] = (0, 1),
    microwave_channel: str = "microwave",
    name: str = "bell-parity",
) -> ExperimentProgram:
    """Append a global pi/2 analysis pulse and measurement to a state program."""

    if atoms[0] == atoms[1]:
        raise ValueError("Bell parity requires two distinct atoms")
    if any(isinstance(op, Measure) for op in prepared_state_program.operations):
        raise ValueError("prepared_state_program may not already measure")
    analysis = _rotation_play(
        channel=microwave_channel,
        targets=atoms,
        angle_rad=0.5 * math.pi,
        phase_rad=analysis_phase_rad,
        rabi_rad_per_us=rabi_rad_per_us,
    )
    assert analysis is not None
    return ExperimentProgram(
        prepared_state_program.operations + (analysis, Measure()),
        name=name,
    )


def _eligible_and_successes(
    result: ExperimentResult,
    *,
    success: Callable[[str], bool],
    postselect_retained: bool,
) -> tuple[int, int]:
    trials = 0
    successes = 0
    for outcome, count in result.counts.items():
        # Postselection removes detected loss only.  Retained leakage labels
        # remain in the denominator and count as gate failure; otherwise a
        # leakage-heavy protocol would acquire an artificially high score.
        retained = "L" not in outcome
        if postselect_retained and not retained:
            continue
        trials += count
        if retained and success(outcome):
            successes += count
    return successes, trials


@dataclass(frozen=True)
class HarmonicEstimate:
    offset: float
    cosine: float
    sine: float
    amplitude: float
    phase_rad: float
    amplitude_standard_error: float
    phase_standard_error_rad: float
    residual_rms: float
    shots: int
    eligible_shots: int


def _fit_harmonic(
    phases_rad: Sequence[float],
    values: Sequence[float],
    weights: Sequence[float],
    *,
    harmonic: int,
    shots: int,
    eligible_shots: int,
) -> HarmonicEstimate:
    phases = np.asarray(phases_rad, dtype=float)
    observations = np.asarray(values, dtype=float)
    sample_weights = np.sqrt(np.asarray(weights, dtype=float))
    if (
        phases.ndim != 1
        or len(phases) < 3
        or observations.shape != phases.shape
        or sample_weights.shape != phases.shape
        or np.any(sample_weights <= 0)
    ):
        raise ValueError("harmonic fit requires at least three weighted points")
    design = np.column_stack(
        (
            np.ones(len(phases)),
            np.cos(harmonic * phases),
            np.sin(harmonic * phases),
        )
    )
    weighted_design = design * sample_weights[:, None]
    weighted_values = observations * sample_weights
    coefficients, *_ = np.linalg.lstsq(
        weighted_design, weighted_values, rcond=None
    )
    fitted = design @ coefficients
    residual_rms = float(np.sqrt(np.mean((observations - fitted) ** 2)))
    cosine, sine = float(coefficients[1]), float(coefficients[2])
    fitted_probabilities = np.clip(fitted, 1e-9, 1.0 - 1e-9)
    information = design.T @ (
        (
            np.asarray(weights, dtype=float)
            / (fitted_probabilities * (1.0 - fitted_probabilities))
        )[:, None]
        * design
    )
    covariance = np.linalg.pinv(information)
    amplitude = float(math.hypot(cosine, sine))
    if amplitude > 1e-14:
        amplitude_gradient = np.asarray(
            (0.0, cosine / amplitude, sine / amplitude)
        )
        phase_gradient = np.asarray(
            (
                0.0,
                -sine / (harmonic * amplitude**2),
                cosine / (harmonic * amplitude**2),
            )
        )
        amplitude_standard_error = float(
            math.sqrt(
                max(0.0, amplitude_gradient @ covariance @ amplitude_gradient)
            )
        )
        phase_standard_error = float(
            math.sqrt(
                max(0.0, phase_gradient @ covariance @ phase_gradient)
            )
        )
    else:
        amplitude_standard_error = math.nan
        phase_standard_error = math.nan
    return HarmonicEstimate(
        offset=float(coefficients[0]),
        cosine=cosine,
        sine=sine,
        amplitude=amplitude,
        phase_rad=wrap_phase(math.atan2(sine, cosine) / harmonic),
        amplitude_standard_error=amplitude_standard_error,
        phase_standard_error_rad=phase_standard_error,
        residual_rms=residual_rms,
        shots=shots,
        eligible_shots=eligible_shots,
    )


def estimate_ramsey_fringe(
    phases_rad: Sequence[float],
    results: Sequence[ExperimentResult],
    *,
    target_atom: int,
    postselect_retained: bool,
) -> HarmonicEstimate:
    """Estimate one Ramsey fringe from public counts."""

    if len(phases_rad) != len(results):
        raise ValueError("one result is required per phase")
    values: list[float] = []
    weights: list[float] = []
    total_shots = 0
    total_eligible = 0
    for result in results:
        successes, trials = _eligible_and_successes(
            result,
            success=lambda value: (
                len(value) > target_atom and value[target_atom] == "1"
            ),
            postselect_retained=postselect_retained,
        )
        if trials == 0:
            raise ValueError("Ramsey point has no eligible shots")
        values.append(successes / trials)
        weights.append(trials)
        total_shots += result.resources.shots
        total_eligible += trials
    return _fit_harmonic(
        phases_rad,
        values,
        weights,
        harmonic=1,
        shots=total_shots,
        eligible_shots=total_eligible,
    )


@dataclass(frozen=True)
class ConditionalPhaseEstimate:
    control_zero: HarmonicEstimate
    control_one: HarmonicEstimate
    controlled_phase_rad: float
    controlled_phase_standard_error_rad: float
    postselected: bool


def estimate_conditional_phase(
    phases_rad: Sequence[float],
    control_zero_results: Sequence[ExperimentResult],
    control_one_results: Sequence[ExperimentResult],
    *,
    target_atom: int = 1,
    postselect_retained: bool = False,
) -> ConditionalPhaseEstimate:
    """Return the conditional phase as the difference of Ramsey fringes."""

    zero = estimate_ramsey_fringe(
        phases_rad,
        control_zero_results,
        target_atom=target_atom,
        postselect_retained=postselect_retained,
    )
    one = estimate_ramsey_fringe(
        phases_rad,
        control_one_results,
        target_atom=target_atom,
        postselect_retained=postselect_retained,
    )
    return ConditionalPhaseEstimate(
        control_zero=zero,
        control_one=one,
        controlled_phase_rad=wrap_phase(one.phase_rad - zero.phase_rad),
        controlled_phase_standard_error_rad=math.hypot(
            zero.phase_standard_error_rad,
            one.phase_standard_error_rad,
        ),
        postselected=postselect_retained,
    )


@dataclass(frozen=True)
class BellParityEstimate:
    population_even: float
    parity: HarmonicEstimate
    fidelity: float
    fidelity_standard_error: float
    postselected: bool
    population_eligible_shots: int


def estimate_bell_parity_fidelity(
    population_result: ExperimentResult,
    phases_rad: Sequence[float],
    parity_results: Sequence[ExperimentResult],
    *,
    postselect_retained: bool = False,
) -> BellParityEstimate:
    """Estimate ``(P00 + P11 + parity_amplitude) / 2`` from public counts."""

    even, population_trials = _eligible_and_successes(
        population_result,
        success=lambda value: value in {"00", "11"},
        postselect_retained=postselect_retained,
    )
    if population_trials == 0:
        raise ValueError("population measurement has no eligible shots")
    parity_values: list[float] = []
    weights: list[float] = []
    total_shots = 0
    total_eligible = 0
    for result in parity_results:
        even_count, trials = _eligible_and_successes(
            result,
            success=lambda value: value in {"00", "11"},
            postselect_retained=postselect_retained,
        )
        if trials == 0:
            raise ValueError("parity point has no eligible shots")
        odd_count = sum(
            count
            for outcome, count in result.counts.items()
            if set(outcome) <= {"0", "1"} and outcome in {"01", "10"}
        )
        parity_values.append((even_count - odd_count) / trials)
        weights.append(trials)
        total_shots += result.resources.shots
        total_eligible += trials
    parity = _fit_harmonic(
        phases_rad,
        parity_values,
        weights,
        harmonic=2,
        shots=total_shots,
        eligible_shots=total_eligible,
    )
    population_even = even / population_trials
    return BellParityEstimate(
        population_even=population_even,
        parity=parity,
        fidelity=0.5 * (population_even + parity.amplitude),
        fidelity_standard_error=0.5
        * math.hypot(
            math.sqrt(
                population_even
                * (1.0 - population_even)
                / population_trials
            ),
            parity.amplitude_standard_error,
        ),
        postselected=postselect_retained,
        population_eligible_shots=population_trials,
    )


# Appendix-E tables from Tsai et al.  Rotation tokens mean global +/-pi/2.
SSB_INITIALIZATION: Mapping[str, tuple[str, ...]] = {
    "IX,XI": ("X", "X", "Y", "-Y", "Y"),
    "-IX,-XI": ("X", "-X", "Y", "-Y", "Y"),
    "IY,YI": ("X", "-X", "X", "-X", "X"),
    "-IY,-YI": ("X", "X", "X", "-X", "X"),
    "IZ,ZI": ("X", "X", "X", "-Y", "-X"),
    "-IZ,-ZI": ("X", "-X", "X", "-Y", "-X"),
    "XZ,ZX": ("-X", "-Y", "X", "-Y", "-X"),
    "-XZ,-ZX": ("X", "Y", "X", "-Y", "-X"),
    "YZ,ZY": ("-X", "-Y", "X", "-X", "X"),
    "-YZ,-ZY": ("X", "Y", "X", "-X", "X"),
    "XY,YX": ("X", "Y", "Y", "-Y", "Y"),
    "-XY,-YX": ("-X", "-Y", "Y", "-Y", "Y"),
}

SSB_RECOVERY: Mapping[str, tuple[str, ...]] = {
    "IX,XI": ("X", "-Y", "X", "X"),
    "-IX,-XI": ("X", "Y", "X", "X"),
    "IY,YI": ("Y", "X", "X", "X"),
    "-IY,-YI": ("Y", "-X", "X", "X"),
    "IZ,ZI": ("-X", "X", "X", "X"),
    "-IZ,-ZI": ("X", "X", "X", "X"),
    "XZ,ZX": ("-X", "Y", "Y", "X"),
    "-XZ,-ZX": ("X", "Y", "Y", "X"),
    "YZ,ZY": ("Y", "Y", "Y", "X"),
    "-YZ,-ZY": ("X", "X", "Y", "X"),
    "XY,YX": ("-Y", "X", "Y", "X"),
    "-XY,-YX": ("Y", "X", "Y", "X"),
}


def _token_matrix(token: str) -> np.ndarray:
    axis = token[-1]
    sign = -1.0 if token.startswith("-") else 1.0
    local = equatorial_rotation_matrix(
        sign * 0.5 * math.pi,
        0.0 if axis == "X" else 0.5 * math.pi,
    )
    return np.kron(local, local)


_CZ_MATRIX = np.diag(np.asarray((1.0, 1.0, 1.0, -1.0), dtype=complex))
_STATE_11 = np.asarray((0.0, 0.0, 0.0, 1.0), dtype=complex)


def _apply_reference(
    state: np.ndarray, sequence: Sequence[str]
) -> np.ndarray:
    for token in sequence:
        state = (_CZ_MATRIX if token == "CZ" else _token_matrix(token)) @ state
    return state


def _initialization_sequence(label: str) -> tuple[str, ...]:
    rotations = SSB_INITIALIZATION[label]
    return rotations[:2] + ("CZ",) + rotations[2:]


def _recovery_sequence(label: str) -> tuple[str, ...]:
    rotations = SSB_RECOVERY[label]
    return rotations[:2] + ("CZ",) + rotations[2:]


_SSB_STATES = {
    label: _apply_reference(_STATE_11, _initialization_sequence(label))
    for label in SSB_INITIALIZATION
}


def symmetric_stabilizer_state_vectors() -> tuple[np.ndarray, ...]:
    """Return copies of the 12 normalized SSB state-design vectors."""

    return tuple(state.copy() for state in _SSB_STATES.values())


def _match_ssb_state(state: np.ndarray) -> str:
    overlaps = {
        label: float(abs(np.vdot(candidate, state)) ** 2)
        for label, candidate in _SSB_STATES.items()
    }
    label = max(overlaps, key=overlaps.get)
    if overlaps[label] < 1.0 - 1e-10:
        raise RuntimeError("ideal SSB sequence left the stabilizer design")
    return label


@dataclass(frozen=True)
class SSBSequence:
    program: ExperimentProgram
    initialization_label: str
    random_rotations: tuple[str, ...]
    recovery_label: str
    cz_count: int
    ideal_return_probability: float


def _append_ssb_rotation(
    program: ExperimentProgram,
    token: str,
    *,
    rabi_rad_per_us: float,
    microwave_channel: str,
    frame_phase_rad: float,
) -> ExperimentProgram:
    phase = (0.0 if token[-1] == "X" else 0.5 * math.pi) + frame_phase_rad
    angle = -0.5 * math.pi if token.startswith("-") else 0.5 * math.pi
    play = _rotation_play(
        channel=microwave_channel,
        targets=(0, 1),
        angle_rad=angle,
        phase_rad=phase,
        rabi_rad_per_us=rabi_rad_per_us,
    )
    assert play is not None
    return program.then(play)


def build_ssb_sequence(
    gate_program: ExperimentProgram,
    *,
    cz_count: int,
    random_rotation_count: int,
    rabi_rad_per_us: float,
    seed: int,
    sequence_index: int = 0,
    microwave_channel: str = "microwave",
    virtual_z_after_cz_rad: float = 0.0,
) -> SSBSequence:
    """Compile one SSB sequence around an external entangling waveform.

    ``virtual_z_after_cz_rad`` shifts the phase of all subsequent global
    microwave pulses.  It is a frame update, not a simulator gate opcode.
    """

    gate_body = _validate_gate_body(gate_program)
    if (
        cz_count < 2
        or random_rotation_count < cz_count - 2
        or sequence_index < 0
    ):
        raise ValueError("SSB requires 2 <= cz_count <= rotations + 2")
    sequence_seed = np.random.SeedSequence((int(seed), int(sequence_index)))
    rng = np.random.default_rng(sequence_seed)
    labels = tuple(SSB_INITIALIZATION)
    initialization_label = labels[int(rng.integers(len(labels)))]
    tokens = ("X", "-X", "Y", "-Y")
    random_rotations = tuple(
        tokens[int(rng.integers(len(tokens)))]
        for _ in range(random_rotation_count)
    )

    reference = _SSB_STATES[initialization_label]
    random_reference_sequence: list[str] = []
    for index, token in enumerate(random_rotations):
        random_reference_sequence.append(token)
        if index < cz_count - 2:
            random_reference_sequence.append("CZ")
    reference = _apply_reference(reference, random_reference_sequence)
    recovery_label = _match_ssb_state(reference)
    final_reference = _apply_reference(
        reference, _recovery_sequence(recovery_label)
    )
    ideal_return = float(abs(np.vdot(_STATE_11, final_reference)) ** 2)

    program = ExperimentProgram((Prepare("11"),), name="ssb")
    frame = 0.0

    def append_gate(current: ExperimentProgram) -> ExperimentProgram:
        nonlocal frame
        current = _append_operations(current, gate_body)
        frame = wrap_phase(frame + virtual_z_after_cz_rad)
        return current

    initialization = SSB_INITIALIZATION[initialization_label]
    for token in initialization[:2]:
        program = _append_ssb_rotation(
            program,
            token,
            rabi_rad_per_us=rabi_rad_per_us,
            microwave_channel=microwave_channel,
            frame_phase_rad=frame,
        )
    program = append_gate(program)
    for token in initialization[2:]:
        program = _append_ssb_rotation(
            program,
            token,
            rabi_rad_per_us=rabi_rad_per_us,
            microwave_channel=microwave_channel,
            frame_phase_rad=frame,
        )
    for index, token in enumerate(random_rotations):
        program = _append_ssb_rotation(
            program,
            token,
            rabi_rad_per_us=rabi_rad_per_us,
            microwave_channel=microwave_channel,
            frame_phase_rad=frame,
        )
        if index < cz_count - 2:
            program = append_gate(program)
    recovery = SSB_RECOVERY[recovery_label]
    for token in recovery[:2]:
        program = _append_ssb_rotation(
            program,
            token,
            rabi_rad_per_us=rabi_rad_per_us,
            microwave_channel=microwave_channel,
            frame_phase_rad=frame,
        )
    program = append_gate(program)
    for token in recovery[2:]:
        program = _append_ssb_rotation(
            program,
            token,
            rabi_rad_per_us=rabi_rad_per_us,
            microwave_channel=microwave_channel,
            frame_phase_rad=frame,
        )
    program = program.then(Measure())
    return SSBSequence(
        program=program,
        initialization_label=initialization_label,
        random_rotations=random_rotations,
        recovery_label=recovery_label,
        cz_count=cz_count,
        ideal_return_probability=ideal_return,
    )


@dataclass(frozen=True)
class SSBDepthCounts:
    cz_count: int
    successes: int
    trials: int

    def __post_init__(self) -> None:
        if (
            self.cz_count < 2
            or self.successes < 0
            or self.trials <= 0
            or self.successes > self.trials
        ):
            raise ValueError("invalid SSB depth counts")


def aggregate_ssb_results(
    cz_count: int,
    results: Sequence[ExperimentResult],
    *,
    postselect_retained: bool = False,
) -> SSBDepthCounts:
    """Aggregate public SSB experiment results at one repeated-CZ depth."""

    successes = 0
    trials = 0
    for result in results:
        point_successes, point_trials = _eligible_and_successes(
            result,
            success=lambda value: value == "11",
            postselect_retained=postselect_retained,
        )
        successes += point_successes
        trials += point_trials
    return SSBDepthCounts(cz_count, successes, trials)


@dataclass(frozen=True)
class SSBFit:
    fidelity_symmetric: float
    baseline_return_at_two_cz: float
    confidence_interval_95: tuple[float, float]
    negative_log_likelihood: float
    converged: bool
    total_successes: int
    total_trials: int
    postselected: bool


def fit_ssb_decay(
    depth_counts: Sequence[SSBDepthCounts],
    *,
    postselected: bool = False,
) -> SSBFit:
    """Fit ``P11 = b0 * F_sym**(N_CZ - 2)`` by binomial MLE."""

    if len(depth_counts) < 2 or len({item.cz_count for item in depth_counts}) < 2:
        raise ValueError("SSB fit requires at least two distinct CZ depths")
    depths = np.asarray([item.cz_count for item in depth_counts], dtype=float)
    successes = np.asarray([item.successes for item in depth_counts], dtype=float)
    trials = np.asarray([item.trials for item in depth_counts], dtype=float)
    exponents = depths - 2.0
    epsilon = 1e-12

    def nll_parameters(parameters: np.ndarray) -> float:
        baseline, fidelity = (float(value) for value in parameters)
        probabilities = np.clip(
            baseline * fidelity**exponents, epsilon, 1.0 - epsilon
        )
        return float(
            -np.sum(
                successes * np.log(probabilities)
                + (trials - successes) * np.log1p(-probabilities)
            )
        )

    empirical = np.clip(successes / trials, epsilon, 1.0 - epsilon)
    baseline_start = float(empirical[np.argmin(depths)])
    positive_exponents = exponents > 0
    if np.any(positive_exponents):
        ratios = np.clip(
            empirical[positive_exponents] / max(baseline_start, epsilon),
            epsilon,
            1.0,
        )
        fidelity_start = float(
            np.exp(np.mean(np.log(ratios) / exponents[positive_exponents]))
        )
    else:
        fidelity_start = 0.99
    fit = optimize.minimize(
        nll_parameters,
        np.asarray((baseline_start, fidelity_start)),
        method="L-BFGS-B",
        bounds=((epsilon, 1.0 - epsilon), (epsilon, 1.0 - epsilon)),
    )
    baseline, fidelity = (float(value) for value in fit.x)
    minimum = float(fit.fun)

    def profile_nll(fixed_fidelity: float) -> float:
        result = optimize.minimize_scalar(
            lambda value: nll_parameters(
                np.asarray((float(value), fixed_fidelity))
            ),
            bounds=(epsilon, 1.0 - epsilon),
            method="bounded",
            options={"xatol": 1e-12},
        )
        return float(result.fun)

    cutoff = minimum + 0.5 * float(stats.chi2.ppf(0.95, df=1))

    def crossing(value: float) -> float:
        return profile_nll(value) - cutoff

    lower = epsilon
    upper = 1.0 - epsilon
    if fidelity > epsilon and crossing(epsilon) > 0:
        lower = float(optimize.brentq(crossing, epsilon, fidelity))
    if fidelity < 1.0 - epsilon and crossing(1.0 - epsilon) > 0:
        upper = float(
            optimize.brentq(crossing, fidelity, 1.0 - epsilon)
        )
    return SSBFit(
        fidelity_symmetric=fidelity,
        baseline_return_at_two_cz=baseline,
        confidence_interval_95=(lower, upper),
        negative_log_likelihood=minimum,
        converged=bool(fit.success),
        total_successes=int(np.sum(successes)),
        total_trials=int(np.sum(trials)),
        postselected=postselected,
    )


@dataclass(frozen=True)
class OutcomeConfusionMatrix:
    """Calibrated ``P(observed | latent)`` matrix for public outcome labels."""

    labels: tuple[str, ...]
    observed_given_latent: np.ndarray

    def __post_init__(self) -> None:
        matrix = np.asarray(self.observed_given_latent, dtype=float)
        count = len(self.labels)
        if (
            count == 0
            or len(set(self.labels)) != count
            or matrix.shape != (count, count)
            or np.any(matrix < 0)
            or not np.all(np.isfinite(matrix))
            or not np.allclose(np.sum(matrix, axis=0), 1.0, atol=1e-10)
        ):
            raise ValueError(
                "confusion matrix columns must be observed distributions"
            )
        object.__setattr__(self, "observed_given_latent", matrix.copy())

    def correct_counts(self, counts: Mapping[str, int]) -> Mapping[str, float]:
        """Maximum-likelihood latent probabilities constrained to the simplex."""

        unknown = set(counts) - set(self.labels)
        if unknown:
            raise ValueError(f"unknown observed labels: {sorted(unknown)}")
        observed = np.asarray(
            [int(counts.get(label, 0)) for label in self.labels], dtype=float
        )
        if np.any(observed < 0) or np.sum(observed) <= 0:
            raise ValueError("counts must be non-negative with positive total")
        epsilon = 1e-15

        def objective(latent: np.ndarray) -> float:
            probabilities = np.clip(
                self.observed_given_latent @ latent, epsilon, 1.0
            )
            return float(-np.dot(observed, np.log(probabilities)))

        result = optimize.minimize(
            objective,
            np.full(len(self.labels), 1.0 / len(self.labels)),
            method="SLSQP",
            bounds=((0.0, 1.0),) * len(self.labels),
            constraints=(
                {
                    "type": "eq",
                    "fun": lambda value: float(np.sum(value) - 1.0),
                },
            ),
            options={"ftol": 1e-12, "maxiter": 2000},
        )
        if not result.success:
            raise RuntimeError(f"SPAM correction failed: {result.message}")
        latent = np.clip(np.asarray(result.x, dtype=float), 0.0, 1.0)
        latent /= np.sum(latent)
        return {
            label: float(probability)
            for label, probability in zip(self.labels, latent)
        }


@dataclass(frozen=True)
class CharacterizationResourceUsage:
    """Exact aggregate resources across heterogeneous experiment programs."""

    execution_count: int
    shots: int
    total_pulse_commands: int
    total_pulse_time_us: float
    total_sequence_time_us: float
    total_channel_time_us: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "total_channel_time_us",
            MappingProxyType(dict(self.total_channel_time_us)),
        )


def sum_resource_usage(
    results: Sequence[ExperimentResult],
) -> CharacterizationResourceUsage:
    """Aggregate heterogeneous characterization calls without hiding cost."""

    if not results:
        raise ValueError("at least one result is required")
    shots = sum(result.resources.shots for result in results)
    total_time = sum(
        result.resources.total_sequence_time_us for result in results
    )
    total_pulses = sum(
        result.resources.pulses_per_shot * result.resources.shots
        for result in results
    )
    total_pulse_time = sum(
        result.resources.pulse_time_per_shot_us * result.resources.shots
        for result in results
    )
    channels: dict[str, float] = {}
    for result in results:
        for channel, duration in result.resources.channel_time_per_shot_us.items():
            channels[channel] = channels.get(channel, 0.0) + (
                duration * result.resources.shots
            )
    return CharacterizationResourceUsage(
        execution_count=len(results),
        shots=shots,
        total_pulse_commands=total_pulses,
        total_pulse_time_us=total_pulse_time,
        total_sequence_time_us=total_time,
        total_channel_time_us=channels,
    )
