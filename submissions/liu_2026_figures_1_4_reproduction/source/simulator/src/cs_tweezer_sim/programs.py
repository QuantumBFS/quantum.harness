"""User-level experiment programs built solely from public primitives."""

from __future__ import annotations

import math

from .contracts import (
    ConstantPulse,
    Delay,
    ExperimentProgram,
    Measure,
    Play,
    Prepare,
)


def rotation_program(
    *,
    n_atoms: int,
    atom: int,
    angle_rad: float,
    phase_rad: float,
    rabi_rad_per_us: float,
    initial_bitstring: str | None = None,
    measure: bool = True,
    name: str = "single-qubit-rotation",
) -> ExperimentProgram:
    """Construct a microwave rotation from generic experiment operations."""

    if rabi_rad_per_us <= 0:
        raise ValueError("rabi_rad_per_us must be positive")
    program = ExperimentProgram(name=name)
    if initial_bitstring is not None:
        if len(initial_bitstring) != n_atoms:
            raise ValueError("initial bitstring length must equal n_atoms")
        program = program.then(Prepare(initial_bitstring))
    program = program.then(
        Play(
            channel="microwave",
            targets=(atom,),
            pulse=ConstantPulse(
                duration_us=abs(angle_rad) / rabi_rad_per_us,
                amplitude_rad_per_us=rabi_rad_per_us,
                phase_rad=phase_rad + (math.pi if angle_rad < 0 else 0.0),
            ),
        )
    )
    if measure:
        program = program.then(Measure())
    return program


def ramsey_phase_program(
    *,
    phase_rad: float,
    rabi_rad_per_us: float,
    delay_us: float = 0.0,
    measure: bool = True,
) -> ExperimentProgram:
    """Construct a one-atom Ramsey phase scan with two pi/2 pulses."""

    half_pi = 0.5 * math.pi
    program = ExperimentProgram(name="ramsey-phase").then(Prepare("0"))
    program = program.then(
        Play(
            "microwave",
            (0,),
            ConstantPulse(half_pi / rabi_rad_per_us, rabi_rad_per_us, 0.0),
        )
    )
    program = program.then(Delay(delay_us))
    program = program.then(
        Play(
            "microwave",
            (0,),
            ConstantPulse(
                half_pi / rabi_rad_per_us, rabi_rad_per_us, phase_rad
            ),
        )
    )
    if measure:
        program = program.then(Measure())
    return program


def fixed_blockade_cz_program(
    *,
    control: int,
    target: int,
    rabi_rad_per_us: float,
    initial_bitstring: str = "00",
    measure: bool = True,
) -> ExperimentProgram:
    """Build the standard pi(control)-2pi(target)-pi(control) blockade gate.

    In the infinite-blockade limit its computational action is
    ``diag(1, -1, -1, -1)``, which becomes CZ after known local Z corrections.
    The sequence is intentionally a user-level program, not a simulator opcode.
    """

    if control == target:
        raise ValueError("control and target must be different atoms")
    if rabi_rad_per_us <= 0:
        raise ValueError("rabi_rad_per_us must be positive")
    pi_duration = math.pi / rabi_rad_per_us
    program = ExperimentProgram(name="fixed-blockade-cz").then(
        Prepare(initial_bitstring)
    )
    program = program.then(
        Play(
            "rydberg",
            (control,),
            ConstantPulse(pi_duration, rabi_rad_per_us),
        )
    )
    program = program.then(
        Play(
            "rydberg",
            (target,),
            ConstantPulse(2.0 * pi_duration, rabi_rad_per_us),
        )
    )
    program = program.then(
        Play(
            "rydberg",
            (control,),
            ConstantPulse(pi_duration, rabi_rad_per_us),
        )
    )
    if measure:
        program = program.then(Measure())
    return program


def repeated_blockade_cz_return_program(
    *,
    control: int,
    target: int,
    rabi_rad_per_us: float,
    duration_scale: float,
    gate_count: int = 2,
    initial_bitstring: str = "11",
    measure: bool = True,
) -> ExperimentProgram:
    """Return-population calibration surrogate using ordinary CZ pulses.

    The Rabi command is held fixed while every Rydberg-pulse duration receives
    one common scale. This makes pulse-area calibration observable. It is a
    compact dry-run circuit, not the full six-parameter Radnaev cost circuit.
    """

    if (
        control == target
        or rabi_rad_per_us <= 0
        or duration_scale <= 0
        or gate_count <= 0
    ):
        raise ValueError("repeated blockade-CZ parameters are invalid")
    pi_duration = math.pi / rabi_rad_per_us
    program = ExperimentProgram(name="repeated-blockade-cz-return").then(
        Prepare(initial_bitstring)
    )
    for _ in range(gate_count):
        for atom, area in ((control, 1.0), (target, 2.0), (control, 1.0)):
            program = program.then(
                Play(
                    "rydberg",
                    (atom,),
                    ConstantPulse(
                        duration_scale * area * pi_duration,
                        rabi_rad_per_us,
                    ),
                )
            )
    if measure:
        program = program.then(Measure())
    return program
