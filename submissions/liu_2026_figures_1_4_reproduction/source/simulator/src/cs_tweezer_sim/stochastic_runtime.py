"""Public finite-shot runtime backed by hidden per-shot physical contexts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from .backend import PhysicsBackend
from .contracts import ExperimentProgram, ExperimentResult, Measure, ResourceUsage
from .observation import ObservationModel
from .stochastic import ShotNoiseModel, StochasticScopeEngine


@dataclass(frozen=True)
class BlockExecutionSlot:
    """One pre-randomized candidate slot in a physical confirmation block."""

    slot_id: str
    program: ExperimentProgram
    shots: int

    def __post_init__(self) -> None:
        if (
            not self.slot_id
            or len(self.slot_id.encode("utf-8")) > 128
            or self.shots <= 0
        ):
            raise ValueError("block execution slot is invalid")


@dataclass(frozen=True)
class PublicBlockSlotResult:
    """Public receipt with block/order identity but no seed or latent value."""

    block_id: str
    slot_index: int
    slot_id: str
    order_code: str
    result: ExperimentResult


class StochasticExperimentRuntime:
    """Execute one controller query as one iteration with fresh shot contexts."""

    def __init__(
        self,
        backend: PhysicsBackend,
        noise_model: ShotNoiseModel,
        *,
        seed: int = 0,
        observation_model: ObservationModel | None = None,
    ):
        self._backend = backend
        self._noise_model = noise_model
        latent_seed, measurement_seed = np.random.SeedSequence(seed).spawn(2)
        self._scope = StochasticScopeEngine(
            noise_model.blocks(backend.n_atoms),
            seed=np.random.default_rng(latent_seed),
        )
        self._measurement_rng = np.random.default_rng(measurement_seed)
        self._observation_model = observation_model
        self._execution_counter = 0
        self._virtual_time_us = 0.0

    @property
    def iteration_index(self) -> int:
        """Validator-visible physical-block index; controllers do not own this runtime."""

        return self._scope.iteration_index

    @staticmethod
    def _validate_program(program: ExperimentProgram, shots: int) -> None:
        if shots <= 0:
            raise ValueError("shots must be positive")
        measurements = [
            operation
            for operation in program.operations
            if isinstance(operation, Measure)
        ]
        if len(measurements) != 1 or not isinstance(program.operations[-1], Measure):
            raise ValueError("program must end with exactly one measurement")

    def execute(
        self, program: ExperimentProgram, *, shots: int
    ) -> ExperimentResult:
        self._validate_program(program, shots)
        self._scope.begin_iteration()
        return self._execute_active_iteration(
            program,
            shots=shots,
            public_metadata={"program_name": program.name},
        )

    def execute_block(
        self,
        block_id: str,
        slots: tuple[BlockExecutionSlot, ...],
    ) -> tuple[PublicBlockSlotResult, ...]:
        """Execute all slots under one shared iteration-scoped latent draw.

        Slot order must be randomized by the confirmation design before this
        call.  The iteration cache is shared; shot-scoped, within-shot, and
        measurement draws continue advancing independently for every shot.
        No hidden latent value or random seed is copied into the public
        metadata.
        """

        if (
            not isinstance(block_id, str)
            or not block_id
            or len(block_id.encode("utf-8")) > 128
            or not slots
        ):
            raise ValueError("physical block id and slots must be non-empty")
        slot_ids = tuple(slot.slot_id for slot in slots)
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot ids must be unique within a physical block")
        for slot in slots:
            self._validate_program(slot.program, slot.shots)
        order_code = ">".join(slot_ids)
        self._scope.begin_iteration()
        receipts: list[PublicBlockSlotResult] = []
        for slot_index, slot in enumerate(slots):
            metadata = {
                "program_name": slot.program.name,
                "physical_block_id": block_id,
                "slot_index": str(slot_index),
                "slot_id": slot.slot_id,
                "randomized_order": order_code,
            }
            result = self._execute_active_iteration(
                slot.program,
                shots=slot.shots,
                public_metadata=metadata,
            )
            receipts.append(
                PublicBlockSlotResult(
                    block_id=block_id,
                    slot_index=slot_index,
                    slot_id=slot.slot_id,
                    order_code=order_code,
                    result=result,
                )
            )
        return tuple(receipts)

    def _execute_active_iteration(
        self,
        program: ExperimentProgram,
        *,
        shots: int,
        public_metadata: dict[str, str],
    ) -> ExperimentResult:
        outcomes: list[str] = []
        shot_readouts = []
        reference_snapshot = None
        for _ in range(shots):
            self._scope.begin_shot()
            if hasattr(self._noise_model, "context_for_program"):
                context = self._noise_model.context_for_program(
                    self._scope,
                    self._backend.n_atoms,
                    program,
                )
            else:
                context = self._noise_model.context(
                    self._scope, self._backend.n_atoms
                )
            snapshot = self._backend.simulate(program, context=context)
            if reference_snapshot is None:
                reference_snapshot = snapshot
            probabilities = self._backend.outcome_probabilities(snapshot.state)
            labels = tuple(sorted(probabilities))
            latent_outcome = str(self._measurement_rng.choice(
                labels,
                p=np.asarray([probabilities[label] for label in labels]),
            ))
            if self._observation_model is None:
                outcomes.append(latent_outcome)
            else:
                record = self._observation_model.observe_latent_outcome(
                    latent_outcome, self._measurement_rng
                )
                shot_readouts.append(record)
                outcomes.append(record.outcome)
        assert reference_snapshot is not None

        self._execution_counter += 1
        execution_id = f"run-{self._execution_counter:06d}"
        start_time_us = self._virtual_time_us
        self._virtual_time_us += shots * reference_snapshot.duration_us
        resources = ResourceUsage(
            shots=shots,
            pulses_per_shot=reference_snapshot.pulse_count,
            pulse_time_per_shot_us=reference_snapshot.pulse_time_us,
            sequence_time_per_shot_us=reference_snapshot.duration_us,
            total_sequence_time_us=shots * reference_snapshot.duration_us,
            channel_time_per_shot_us=reference_snapshot.channel_time_us,
        )
        return ExperimentResult(
            execution_id=execution_id,
            counts=dict(Counter(outcomes)),
            shot_outcomes=tuple(outcomes),
            public_timestamp_us=start_time_us,
            status="completed",
            resources=resources,
            metadata=public_metadata,
            shot_readouts=tuple(shot_readouts),
        )
