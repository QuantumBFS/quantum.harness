"""Public Radnaev-like CZ calibration programs.

The six-parameter waveform in this module is an *effective* ``|1>-|r>``
representation.  It is useful for exercising the experiment/control boundary,
and can also be mapped to the platform's deliberately reduced, explicit
``|1>-|e>-|r>`` 459/1040-nm ladder.  Neither form claims to reproduce
unpublished parameters from Radnaev et al.

Every gate is compiled into ordinary public laboratory primitives.  In
particular, this module never emits or calls a privileged backend ``CZ``
operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import (
    ConstantPulse,
    ExperimentProgram,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)


RADNAEV_COST_EXPECTED_OUTCOME = "11"


@dataclass(frozen=True)
class RadnaevLikeSixParameterPulse:
    """Six public controls for one effective phase-modulated entangler.

    The parameter order is frozen by :meth:`as_tuple` and :meth:`from_tuple`:

    ``(A0_rad, omega_mod_rad_per_us, phi0_rad, duration_us,
    detuning_atom0_rad_per_us, detuning_atom1_rad_per_us)``.

    The platform phase convention is
    ``phi(t) = A0 * sin(omega_mod * t + phi0)``.  It is a documented platform
    convention rather than a claim about an unpublished experimental sign
    convention.
    """

    A0_rad: float
    omega_mod_rad_per_us: float
    phi0_rad: float
    duration_us: float
    detuning_atom0_rad_per_us: float
    detuning_atom1_rad_per_us: float

    def __post_init__(self) -> None:
        values = self.as_tuple()
        if not all(math.isfinite(value) for value in values):
            raise ValueError("all six CZ pulse parameters must be finite")
        if self.duration_us <= 0:
            raise ValueError("duration_us must be positive")

    def as_tuple(self) -> tuple[float, float, float, float, float, float]:
        """Return the frozen controller-facing parameter order."""

        return (
            float(self.A0_rad),
            float(self.omega_mod_rad_per_us),
            float(self.phi0_rad),
            float(self.duration_us),
            float(self.detuning_atom0_rad_per_us),
            float(self.detuning_atom1_rad_per_us),
        )

    @classmethod
    def from_tuple(
        cls, values: tuple[float, ...]
    ) -> "RadnaevLikeSixParameterPulse":
        """Construct from one canonical six-dimensional controller vector."""

        if len(values) != 6:
            raise ValueError("a Radnaev-like pulse requires exactly six values")
        return cls(*(float(value) for value in values))

    def phase_rad_at(self, time_us: float) -> float:
        """Evaluate the frozen sinusoidal phase convention."""

        if not math.isfinite(time_us):
            raise ValueError("time_us must be finite")
        return self.A0_rad * math.sin(
            self.omega_mod_rad_per_us * time_us + self.phi0_rad
        )


def _awg_sample_count(duration_us: float, awg_dt_us: float) -> int:
    if not math.isfinite(awg_dt_us) or awg_dt_us <= 0:
        raise ValueError("awg_dt_us must be finite and positive")
    ratio = duration_us / awg_dt_us
    sample_count = round(ratio)
    if sample_count < 1 or not math.isclose(
        ratio, sample_count, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("duration_us must be an integer multiple of awg_dt_us")
    return sample_count


def phase_modulated_entangler_program(
    parameters: RadnaevLikeSixParameterPulse,
    *,
    rabi_rad_per_us: float,
    awg_dt_us: float,
    rydberg_channel: str = "rydberg",
    name: str = "radnaev-like-effective-entangler",
) -> ExperimentProgram:
    """Compile one effective entangler into midpoint-sampled public pulses.

    The Rabi magnitude is held constant.  Each AWG interval is a
    :class:`ParallelPlay` containing one effective ``|1>-|r>`` drive per atom.
    The two drives share the sinusoidal phase while retaining their distinct
    atom-local detunings.  Samples use ``t_i = (i + 1/2) * awg_dt_us``.

    The returned program deliberately has no preparation or measurement so it
    can be embedded in calibration circuits.
    """

    if (
        not math.isfinite(rabi_rad_per_us)
        or rabi_rad_per_us <= 0
        or not rydberg_channel
    ):
        raise ValueError("Rabi rate and Rydberg channel must be valid")
    sample_count = _awg_sample_count(parameters.duration_us, awg_dt_us)

    program = ExperimentProgram(name=name)
    for index in range(sample_count):
        midpoint_us = (index + 0.5) * awg_dt_us
        phase_rad = parameters.phase_rad_at(midpoint_us)
        program = program.then(
            ParallelPlay(
                (
                    Play(
                        rydberg_channel,
                        (0,),
                        ConstantPulse(
                            awg_dt_us,
                            rabi_rad_per_us,
                            phase_rad,
                            parameters.detuning_atom0_rad_per_us,
                        ),
                    ),
                    Play(
                        rydberg_channel,
                        (1,),
                        ConstantPulse(
                            awg_dt_us,
                            rabi_rad_per_us,
                            phase_rad,
                            parameters.detuning_atom1_rad_per_us,
                        ),
                    ),
                )
            )
        )
    return program


def explicit_ladder_upper_phase_rad(
    effective_phase_rad: float,
    *,
    phase_459_rad: float = 0.0,
) -> float:
    """Map a reduced-drive phase to the explicit upper optical-leg phase.

    For a positive intermediate energy ``D``, elimination gives
    ``<1|H_eff|r> = -Omega_459 Omega_1040 exp(-i(phi_459+phi_1040))/(4D)``.
    The reduced backend uses
    ``(Omega_eff/2) exp(-i phi_eff)``.  Therefore
    ``phi_1040 = pi + phi_eff - phi_459`` modulo ``2*pi``.
    """

    if not (
        math.isfinite(effective_phase_rad) and math.isfinite(phase_459_rad)
    ):
        raise ValueError("optical phases must be finite")
    return math.remainder(
        math.pi + effective_phase_rad - phase_459_rad,
        2.0 * math.pi,
    )


def phase_modulated_explicit_ladder_entangler_program(
    parameters: RadnaevLikeSixParameterPulse,
    *,
    omega_459_rad_per_us: float,
    omega_1040_rad_per_us: float,
    awg_dt_us: float,
    channel_459: str = "rydberg_459",
    channel_1040: str = "rydberg_1040",
    phase_459_rad: float = 0.0,
    name: str = "radnaev-like-explicit-ladder-entangler",
) -> ExperimentProgram:
    """Compile the effective waveform into atom-local 459/1040-nm pulses.

    Every midpoint sample emits four ordinary :class:`Play` operations in one
    :class:`ParallelPlay`: one lower and one upper optical leg for each atom.
    Atom-local controller detunings are applied only to the upper ``e-r`` leg,
    whose transition convention shifts ``|r>`` without changing the
    one-photon ``|e>`` energy.  The explicit Hamiltonian itself generates both
    optical light shifts; no additional static ``|1>`` shift is inserted here.

    This mapper targets the platform's single unresolved intermediate state.
    It does not add hyperfine interference, polarization/CG structure, or
    Zeeman-resolved branching.
    """

    if (
        not math.isfinite(omega_459_rad_per_us)
        or omega_459_rad_per_us <= 0.0
        or not math.isfinite(omega_1040_rad_per_us)
        or omega_1040_rad_per_us <= 0.0
        or not math.isfinite(phase_459_rad)
        or not channel_459
        or not channel_1040
        or channel_459 == channel_1040
    ):
        raise ValueError("explicit ladder controls and channels must be valid")

    sample_count = _awg_sample_count(parameters.duration_us, awg_dt_us)
    program = ExperimentProgram(name=name)
    local_detunings = (
        parameters.detuning_atom0_rad_per_us,
        parameters.detuning_atom1_rad_per_us,
    )
    for index in range(sample_count):
        midpoint_us = (index + 0.5) * awg_dt_us
        effective_phase = parameters.phase_rad_at(midpoint_us)
        phase_1040_rad = explicit_ladder_upper_phase_rad(
            effective_phase,
            phase_459_rad=phase_459_rad,
        )
        plays: list[Play] = []
        for atom, detuning_rad_per_us in enumerate(local_detunings):
            plays.extend(
                (
                    Play(
                        channel_459,
                        (atom,),
                        ConstantPulse(
                            awg_dt_us,
                            omega_459_rad_per_us,
                            phase_459_rad,
                            0.0,
                        ),
                    ),
                    Play(
                        channel_1040,
                        (atom,),
                        ConstantPulse(
                            awg_dt_us,
                            omega_1040_rad_per_us,
                            phase_1040_rad,
                            detuning_rad_per_us,
                        ),
                    ),
                )
            )
        program = program.then(ParallelPlay(tuple(plays)))
    return program


def _radnaev_like_cost_program_from_entangler(
    entangler: ExperimentProgram,
    *,
    microwave_rabi_rad_per_us: float,
    cost_pair_count: int,
    microwave_channel: str,
    name: str,
) -> ExperimentProgram:
    """Wrap an already compiled entangler in the frozen public cost circuit."""

    if (
        not math.isfinite(microwave_rabi_rad_per_us)
        or microwave_rabi_rad_per_us <= 0
        or cost_pair_count <= 0
        or not microwave_channel
    ):
        raise ValueError("cost-circuit parameters must be valid")

    def global_rx(angle_rad: float) -> Play:
        return Play(
            microwave_channel,
            (0, 1),
            ConstantPulse(
                duration_us=angle_rad / microwave_rabi_rad_per_us,
                amplitude_rad_per_us=microwave_rabi_rad_per_us,
                phase_rad=0.0,
            ),
        )

    program = ExperimentProgram(name=name).then(Prepare("00"))
    program = program.then(global_rx(0.5 * math.pi))
    for _ in range(cost_pair_count):
        for operation in entangler.operations:
            program = program.then(operation)
        program = program.then(global_rx(math.pi))
        for operation in entangler.operations:
            program = program.then(operation)
    program = program.then(global_rx(0.5 * math.pi))
    return program.then(Measure())


def radnaev_like_cost_program(
    parameters: RadnaevLikeSixParameterPulse,
    *,
    rydberg_rabi_rad_per_us: float,
    microwave_rabi_rad_per_us: float,
    awg_dt_us: float,
    cost_pair_count: int = 1,
    rydberg_channel: str = "rydberg",
    microwave_channel: str = "microwave",
    name: str = "radnaev-like-phase-insensitive-cost",
) -> ExperimentProgram:
    """Build the raw bright-bright CZ cost circuit from public primitives.

    The frozen circuit is

    ``Prepare(00) -> global Rx(pi/2) ->
    [entangler -> global Rx(pi) -> entangler]^N ->
    global Rx(pi/2) -> Measure``.

    A successful online shot is the raw public outcome ``"11"``.  Loss,
    leakage, and any other outcome remain failures; no postselection is
    performed here.
    """

    entangler = phase_modulated_entangler_program(
        parameters,
        rabi_rad_per_us=rydberg_rabi_rad_per_us,
        awg_dt_us=awg_dt_us,
        rydberg_channel=rydberg_channel,
    )

    return _radnaev_like_cost_program_from_entangler(
        entangler,
        microwave_rabi_rad_per_us=microwave_rabi_rad_per_us,
        cost_pair_count=cost_pair_count,
        microwave_channel=microwave_channel,
        name=name,
    )


def radnaev_like_explicit_ladder_cost_program(
    parameters: RadnaevLikeSixParameterPulse,
    *,
    omega_459_rad_per_us: float,
    omega_1040_rad_per_us: float,
    microwave_rabi_rad_per_us: float,
    awg_dt_us: float,
    cost_pair_count: int = 1,
    channel_459: str = "rydberg_459",
    channel_1040: str = "rydberg_1040",
    microwave_channel: str = "microwave",
    phase_459_rad: float = 0.0,
    name: str = "radnaev-like-explicit-ladder-cost",
) -> ExperimentProgram:
    """Build the frozen raw cost circuit using the explicit optical mapper."""

    entangler = phase_modulated_explicit_ladder_entangler_program(
        parameters,
        omega_459_rad_per_us=omega_459_rad_per_us,
        omega_1040_rad_per_us=omega_1040_rad_per_us,
        awg_dt_us=awg_dt_us,
        channel_459=channel_459,
        channel_1040=channel_1040,
        phase_459_rad=phase_459_rad,
    )
    return _radnaev_like_cost_program_from_entangler(
        entangler,
        microwave_rabi_rad_per_us=microwave_rabi_rad_per_us,
        cost_pair_count=cost_pair_count,
        microwave_channel=microwave_channel,
        name=name,
    )
