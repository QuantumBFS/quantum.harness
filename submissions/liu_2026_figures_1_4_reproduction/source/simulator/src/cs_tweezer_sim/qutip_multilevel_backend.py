"""QuTiP backend for backend-configured finite-level neutral-atom models."""

from __future__ import annotations

import itertools
from typing import Iterable

import numpy as np
import qutip as qt

from .backend import SimulationContext, SimulationSnapshot
from .contracts import (
    Delay,
    ExperimentProgram,
    Measure,
    ParallelPlay,
    Play,
    Prepare,
)
from .multilevel_config import MultilevelEnvironmentConfig


class QutipMultilevelBackend:
    """Evolve arbitrary configured levels, transitions, decays, and pair shifts."""

    def __init__(self, config: MultilevelEnvironmentConfig):
        self.config = config
        self.n_atoms = config.n_atoms
        self._level_names = tuple(level.name for level in config.model.levels)
        self._level_index = {
            name: index for index, name in enumerate(self._level_names)
        }
        self._measurement_label = {
            level.name: level.measurement_label
            for level in config.model.levels
        }
        self.local_dimension = len(self._level_names)
        self._identity = qt.qeye(self.local_dimension)
        self._projectors = {
            name: qt.basis(self.local_dimension, index)
            * qt.basis(self.local_dimension, index).dag()
            for name, index in self._level_index.items()
        }
        self._static_hamiltonian = self._build_static_hamiltonian()
        self._collapse_operators = self._build_collapse_operators()

    def _embed(self, local_operator: qt.Qobj, atom: int) -> qt.Qobj:
        self._validate_atom(atom)
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
        hamiltonian = 0.0 * self._embed(self._projectors[self._level_names[0]], 0)
        for atom in range(self.n_atoms):
            for level, energy in (
                self.config.model.static_level_energies_rad_per_us.items()
            ):
                hamiltonian += energy * self._embed(self._projectors[level], atom)
            for coupling in self.config.model.static_couplings:
                lower = self._level_index[coupling.lower_level]
                upper = self._level_index[coupling.upper_level]
                local = (
                    coupling.matrix_element_rad_per_us
                    * qt.basis(self.local_dimension, upper)
                    * qt.basis(self.local_dimension, lower).dag()
                )
                hamiltonian += self._embed(local + local.dag(), atom)
            for level in self._level_names:
                offset = context.level_energy_offset_rad_per_us(
                    atom, level, time_us
                )
                hamiltonian += offset * self._embed(
                    self._projectors[level], atom
                )
        for first_atom in range(self.n_atoms):
            for second_atom in range(first_atom + 1, self.n_atoms):
                for interaction in self.config.model.pair_interactions:
                    if interaction.atom_pair is not None and (
                        interaction.atom_pair
                        != (first_atom, second_atom)
                    ):
                        continue
                    scale = context.pair_interaction_scales.get(
                        (first_atom, second_atom, interaction.label), 1.0
                    )
                    first = self._embed(
                        self._projectors[interaction.first_level], first_atom
                    )
                    second = self._embed(
                        self._projectors[interaction.second_level], second_atom
                    )
                    term = first * second
                    if (
                        interaction.symmetric
                        and interaction.first_level != interaction.second_level
                    ):
                        term += self._embed(
                            self._projectors[interaction.second_level], first_atom
                        ) * self._embed(
                            self._projectors[interaction.first_level], second_atom
                        )
                    hamiltonian += (
                        scale * interaction.strength_rad_per_us * term
                    )
                for coupling in self.config.model.pair_couplings:
                    if coupling.atom_pair is not None and (
                        coupling.atom_pair
                        != (first_atom, second_atom)
                    ):
                        continue
                    scale = context.pair_interaction_scales.get(
                        (first_atom, second_atom, coupling.label), 1.0
                    )
                    source_first, source_second = (
                        self._level_index[level]
                        for level in coupling.source_levels
                    )
                    target_first, target_second = (
                        self._level_index[level]
                        for level in coupling.target_levels
                    )
                    first_local = (
                        qt.basis(self.local_dimension, target_first)
                        * qt.basis(self.local_dimension, source_first).dag()
                    )
                    second_local = (
                        qt.basis(self.local_dimension, target_second)
                        * qt.basis(self.local_dimension, source_second).dag()
                    )
                    transfer = self._embed(
                        first_local, first_atom
                    ) * self._embed(second_local, second_atom)
                    term = (
                        coupling.matrix_element_rad_per_us * transfer
                    )
                    hamiltonian += scale * (term + term.dag())
        return hamiltonian

    def _build_collapse_operators(self) -> list[qt.Qobj]:
        operators: list[qt.Qobj] = []
        for decay in self.config.model.decays:
            source = self._level_index[decay.source_level]
            target = self._level_index[decay.target_level]
            local = (
                qt.basis(self.local_dimension, target)
                * qt.basis(self.local_dimension, source).dag()
            )
            for atom in range(self.n_atoms):
                operators.append(
                    np.sqrt(decay.rate_per_us) * self._embed(local, atom)
                )
        return operators

    def computational_basis_state(self, bitstring: str) -> qt.Qobj:
        if len(bitstring) != self.n_atoms or set(bitstring) - {"0", "1"}:
            raise ValueError(
                f"bitstring must contain {self.n_atoms} computational bits"
            )
        basis_levels = self.config.model.computational_levels
        return qt.tensor(
            [
                qt.basis(
                    self.local_dimension,
                    self._level_index[basis_levels[int(bit)]],
                )
                for bit in bitstring
            ]
        )

    def local_level_product_state(self, levels: tuple[str, ...]) -> qt.Qobj:
        """Validator-only preparation of arbitrary configured local levels."""

        if len(levels) != self.n_atoms:
            raise ValueError("one local level is required per atom")
        unknown = set(levels) - set(self._level_index)
        if unknown:
            raise ValueError(f"unknown configured levels: {sorted(unknown)}")
        return qt.tensor(
            [
                qt.basis(self.local_dimension, self._level_index[level])
                for level in levels
            ]
        )

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

        targets: Iterable[int] = (
            range(self.n_atoms)
            if channel.addressing == "global"
            else operation.targets
        )
        hamiltonian = 0.0 * self._static_hamiltonian
        for atom in targets:
            self._validate_atom(atom)
            amplitude_scale = context.channel_amplitude_scales.get(
                (operation.channel, atom), 1.0
            )
            phase = pulse.phase_rad + context.channel_phase_offset_rad(
                operation.channel, atom, time_us
            )
            for coupling in channel.transition_couplings:
                transition = self.config.model.transitions[
                    coupling.transition
                ]
                lower = self._level_index[transition.lower_level]
                upper = self._level_index[transition.upper_level]
                lowering = (
                    qt.basis(self.local_dimension, lower)
                    * qt.basis(self.local_dimension, upper).dag()
                )
                coefficient = (
                    coupling.relative_rabi * np.exp(-1j * phase)
                )
                drive = coefficient * lowering
                drive = (
                    0.5
                    * pulse.amplitude_rad_per_us
                    * amplitude_scale
                    * (drive + drive.dag())
                )
                hamiltonian += self._embed(drive, atom)
            actual_amplitude = (
                pulse.amplitude_rad_per_us * amplitude_scale
            )
            for shift in channel.level_shifts:
                value = shift.coefficient * (
                    abs(actual_amplitude) ** shift.amplitude_power
                )
                hamiltonian += value * self._embed(
                    self._projectors[shift.level], atom
                )
            detuning = pulse.detuning_rad_per_us + (
                context.channel_detuning_offset_rad_per_us(
                    operation.channel, atom, time_us
                )
            )
            detuning_weights: dict[str, float] = {}
            for coupling in channel.transition_couplings:
                transition = self.config.model.transitions[
                    coupling.transition
                ]
                for level, weight in transition.detuning_weights.items():
                    detuning_weights.setdefault(level, weight)
            for level, weight in detuning_weights.items():
                hamiltonian += (
                    detuning
                    * weight
                    * self._embed(self._projectors[level], atom)
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
        """Evolve one public operation across every hidden trace knot."""

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
                options={
                    "store_final_state": True,
                    "method": "bdf",
                    "nsteps": 100000,
                    "atol": 1e-10,
                    "rtol": 1e-8,
                },
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
        for flat_index, local_indices in enumerate(
            itertools.product(range(self.local_dimension), repeat=self.n_atoms)
        ):
            probability = max(0.0, float(diagonal[flat_index]))
            label = "".join(
                self._measurement_label[self._level_names[index]]
                for index in local_indices
            )
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
