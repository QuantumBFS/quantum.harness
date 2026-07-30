"""QuTiP backend for the reduced three-level neutral-atom model."""

from __future__ import annotations

import itertools
from typing import Iterable

import numpy as np
import qutip as qt

from .backend import SimulationContext, SimulationSnapshot
from .config import EnvironmentConfig
from .contracts import (
    Delay,
    ExperimentProgram,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)


class QutipReducedBackend:
    """Evolve ``|0>, |1>, |r>`` atoms under microwave and Rydberg pulses."""

    local_dimension = 3

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.n_atoms = config.n_atoms
        if any(
            channel.additional_transition_couplings or channel.level_shifts
            for channel in config.channels.values()
        ):
            raise ValueError(
                "reduced backend does not support multi-transition or "
                "actuator-linked level-shift channels; "
                "use QutipMultilevelBackend for shared multi-transition "
                "actuators"
            )
        unsupported = {
            channel.transition
            for channel in config.channels.values()
            if channel.transition not in {"01", "1r"}
        }
        if unsupported:
            raise ValueError(
                "reduced backend supports only 01 and 1r transitions; "
                f"got {sorted(unsupported)}"
            )
        self._identity = qt.qeye(self.local_dimension)
        self._p0_local = qt.basis(3, 0) * qt.basis(3, 0).dag()
        self._p1_local = qt.basis(3, 1) * qt.basis(3, 1).dag()
        self._pr_local = qt.basis(3, 2) * qt.basis(3, 2).dag()
        self._op01_local = qt.basis(3, 0) * qt.basis(3, 1).dag()
        self._op1r_local = qt.basis(3, 1) * qt.basis(3, 2).dag()
        self._static_hamiltonian = self._build_static_hamiltonian()
        self._collapse_operators = self._build_collapse_operators()

    def _embed(self, local_operator: qt.Qobj, atom: int) -> qt.Qobj:
        operators = [self._identity] * self.n_atoms
        operators[atom] = local_operator
        return qt.tensor(operators)

    def _validate_atom(self, atom: int) -> None:
        if atom < 0 or atom >= self.n_atoms:
            raise ValueError(f"target atom {atom} is outside [0, {self.n_atoms})")

    def _build_static_hamiltonian(
        self,
        context: SimulationContext | None = None,
        time_us: float = 0.0,
    ) -> qt.Qobj:
        if (
            context is not None
            and context.is_nominal
            and hasattr(self, "_static_hamiltonian")
        ):
            return self._static_hamiltonian
        context = context or SimulationContext()
        zero = 0.0 * self._embed(self._p0_local, 0)
        hamiltonian = zero
        model = self.config.model
        for atom in range(self.n_atoms):
            hamiltonian += -model.qubit_drift_detuning_rad_per_us * self._embed(
                self._p1_local, atom
            )
            hamiltonian += -model.rydberg_drift_detuning_rad_per_us * self._embed(
                self._pr_local, atom
            )
            for level, projector in (
                ("0", self._p0_local),
                ("1", self._p1_local),
                ("r", self._pr_local),
            ):
                hamiltonian += context.level_energy_offset_rad_per_us(
                    atom, level, time_us
                ) * self._embed(projector, atom)
        for first in range(self.n_atoms):
            for second in range(first + 1, self.n_atoms):
                scale = context.pair_interaction_scales.get(
                    (first, second, "blockade"), 1.0
                )
                hamiltonian += scale * model.blockade_rad_per_us * (
                    self._embed(self._pr_local, first)
                    * self._embed(self._pr_local, second)
                )
        return hamiltonian

    def _build_collapse_operators(self) -> list[qt.Qobj]:
        operators: list[qt.Qobj] = []
        model = self.config.model
        if model.rydberg_relaxation_rate_per_us > 0:
            decay = qt.basis(3, 1) * qt.basis(3, 2).dag()
            for atom in range(self.n_atoms):
                operators.append(
                    np.sqrt(model.rydberg_relaxation_rate_per_us)
                    * self._embed(decay, atom)
                )
        if model.qubit_dephasing_rate_per_us > 0:
            z01 = self._p0_local - self._p1_local
            for atom in range(self.n_atoms):
                operators.append(
                    np.sqrt(model.qubit_dephasing_rate_per_us / 2.0)
                    * self._embed(z01, atom)
                )
        return operators

    def computational_basis_state(self, bitstring: str) -> qt.Qobj:
        if len(bitstring) != self.n_atoms or set(bitstring) - {"0", "1"}:
            raise ValueError(
                f"bitstring must contain {self.n_atoms} computational bits"
            )
        return qt.tensor([qt.basis(3, int(bit)) for bit in bitstring])

    def local_level_product_state(self, levels: tuple[str, ...]) -> qt.Qobj:
        """Validator-only preparation of reduced physical levels."""

        level_index = {"0": 0, "1": 1, "r": 2}
        if len(levels) != self.n_atoms:
            raise ValueError("one local level is required per atom")
        unknown = set(levels) - set(level_index)
        if unknown:
            raise ValueError(f"unknown reduced levels: {sorted(unknown)}")
        return qt.tensor([qt.basis(3, level_index[level]) for level in levels])

    def _play_terms(
        self,
        operation: Play,
        context: SimulationContext,
        time_us: float = 0.0,
    ) -> qt.Qobj:
        try:
            channel = self.config.channels[operation.channel]
        except KeyError as exc:
            raise ValueError(f"unknown channel: {operation.channel}") from exc
        pulse = operation.pulse
        if pulse.amplitude_rad_per_us > channel.max_amplitude_rad_per_us:
            raise ValueError(f"pulse exceeds amplitude limit on {channel.name}")
        if abs(pulse.detuning_rad_per_us) > channel.max_abs_detuning_rad_per_us:
            raise ValueError(f"pulse exceeds detuning limit on {channel.name}")
        if pulse.duration_us < channel.min_duration_us:
            raise ValueError(f"pulse is shorter than minimum on {channel.name}")

        targets: Iterable[int]
        if channel.addressing == "global":
            targets = range(self.n_atoms)
        else:
            targets = operation.targets

        hamiltonian = 0.0 * self._static_hamiltonian
        local_transition = (
            self._op01_local if channel.transition == "01" else self._op1r_local
        )
        detuned_level = (
            self._p1_local if channel.transition == "01" else self._pr_local
        )
        for atom in targets:
            self._validate_atom(atom)
            amplitude_scale = context.channel_amplitude_scales.get(
                (operation.channel, atom), 1.0
            )
            coefficient = 0.5 * pulse.amplitude_rad_per_us * amplitude_scale
            phase = pulse.phase_rad + context.channel_phase_offset_rad(
                operation.channel, atom, time_us
            )
            drive = np.exp(-1j * phase) * local_transition
            drive = coefficient * (drive + drive.dag())
            hamiltonian += self._embed(drive, atom)
            detuning = pulse.detuning_rad_per_us + (
                context.channel_detuning_offset_rad_per_us(
                    operation.channel, atom, time_us
                )
            )
            hamiltonian += -detuning * self._embed(
                detuned_level, atom
            )
        return hamiltonian

    def _segment_hamiltonian(
        self,
        plays: Iterable[Play],
        context: SimulationContext,
        time_us: float = 0.0,
    ) -> qt.Qobj:
        hamiltonian = self._build_static_hamiltonian(context, time_us)
        for play in plays:
            hamiltonian += self._play_terms(play, context, time_us)
        return hamiltonian

    def _evolve_dynamic_segment(
        self,
        state: qt.Qobj,
        plays: Iterable[Play],
        duration_us: float,
        start_time_us: float,
        context: SimulationContext,
    ) -> qt.Qobj:
        end_time_us = start_time_us + duration_us
        boundaries = (
            start_time_us,
            *context.dynamic_breakpoints(start_time_us, duration_us),
            end_time_us,
        )
        plays = tuple(plays)
        for lower, upper in zip(boundaries, boundaries[1:]):
            midpoint = 0.5 * (lower + upper)
            state = self._evolve(
                state,
                self._segment_hamiltonian(plays, context, midpoint),
                upper - lower,
            )
        return state

    def _evolve(self, state: qt.Qobj, hamiltonian: qt.Qobj, duration_us: float) -> qt.Qobj:
        if duration_us == 0:
            return state
        if self._collapse_operators:
            result = qt.mesolve(
                hamiltonian,
                state,
                [0.0, duration_us],
                c_ops=self._collapse_operators,
                options={"store_final_state": True},
            )
            return result.final_state
        propagator = (-1j * hamiltonian * duration_us).expm()
        if state.isket:
            return propagator * state
        return propagator * state * propagator.dag()

    def simulate(
        self,
        program: ExperimentProgram,
        *,
        initial_state: qt.Qobj | None = None,
        ignore_prepare: bool = False,
        context: SimulationContext | None = None,
    ) -> SimulationSnapshot:
        context = context or SimulationContext()
        state = initial_state or self.computational_basis_state("0" * self.n_atoms)
        duration_us = 0.0
        pulse_time_us = 0.0
        pulse_count = 0
        channel_time_us: dict[str, float] = {}
        for operation in program.operations:
            if isinstance(operation, Prepare):
                if not ignore_prepare:
                    state = self.computational_basis_state(operation.bitstring)
            elif isinstance(operation, Play):
                state = self._evolve_dynamic_segment(
                    state,
                    (operation,),
                    operation.pulse.duration_us,
                    duration_us,
                    context,
                )
                duration_us += operation.pulse.duration_us
                pulse_time_us += operation.pulse.duration_us
                pulse_count += 1
                channel_time_us[operation.channel] = (
                    channel_time_us.get(operation.channel, 0.0)
                    + operation.pulse.duration_us
                )
            elif isinstance(operation, ParallelPlay):
                state = self._evolve_dynamic_segment(
                    state,
                    operation.plays,
                    operation.duration_us,
                    duration_us,
                    context,
                )
                duration_us += operation.duration_us
                pulse_time_us += operation.duration_us
                pulse_count += len(operation.plays)
                for play in operation.plays:
                    channel_time_us[play.channel] = (
                        channel_time_us.get(play.channel, 0.0)
                        + operation.duration_us
                    )
            elif isinstance(operation, Delay):
                state = self._evolve_dynamic_segment(
                    state,
                    (),
                    operation.duration_us,
                    duration_us,
                    context,
                )
                duration_us += operation.duration_us
            elif isinstance(operation, Measure):
                continue
            else:
                raise TypeError(f"unsupported operation: {type(operation)!r}")
        return SimulationSnapshot(
            state,
            duration_us,
            pulse_time_us,
            pulse_count,
            channel_time_us,
        )

    def outcome_probabilities(self, state: qt.Qobj) -> dict[str, float]:
        density = qt.ket2dm(state) if state.isket else state
        diagonal = np.real_if_close(np.diag(density.full())).real
        probabilities: dict[str, float] = {}
        for flat_index, local_states in enumerate(
            itertools.product(range(3), repeat=self.n_atoms)
        ):
            probability = max(0.0, float(diagonal[flat_index]))
            label = "".join("R" if level == 2 else str(level) for level in local_states)
            probabilities[label] = probabilities.get(label, 0.0) + probability
        total = sum(probabilities.values())
        if total <= 0:
            raise RuntimeError("state has no measurable probability")
        return {label: value / total for label, value in probabilities.items()}

    def computational_amplitudes(self, state: qt.Qobj) -> np.ndarray:
        if not state.isket:
            raise ValueError("computational amplitudes require a pure state")
        return np.asarray(
            [
                self.computational_basis_state(bits).overlap(state)
                for bits in self._computational_bitstrings()
            ],
            dtype=complex,
        )

    def _computational_bitstrings(self) -> tuple[str, ...]:
        return tuple(
            "".join(bits)
            for bits in itertools.product(("0", "1"), repeat=self.n_atoms)
        )
