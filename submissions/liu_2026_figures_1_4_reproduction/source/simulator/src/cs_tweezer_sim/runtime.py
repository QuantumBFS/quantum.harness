"""Public finite-shot experiment runtime."""

from __future__ import annotations

from collections import Counter

import numpy as np

from .backend import PhysicsBackend
from .contracts import ExperimentProgram, ExperimentResult, Measure, ResourceUsage
from .observation import ObservationModel


class ExperimentRuntime:
    """Execute laboratory programs and return only raw finite-shot observations."""

    def __init__(
        self,
        backend: PhysicsBackend,
        *,
        seed: int = 0,
        observation_model: ObservationModel | None = None,
    ):
        self._backend = backend
        self._rng = np.random.default_rng(seed)
        self._observation_model = observation_model
        self._execution_counter = 0
        self._virtual_time_us = 0.0

    def execute(self, program: ExperimentProgram, *, shots: int) -> ExperimentResult:
        """Execute one immutable program repeatedly.

        The seed is intentionally fixed when the platform is constructed rather
        than supplied by a controller on each call.
        """

        if shots <= 0:
            raise ValueError("shots must be positive")
        measurements = [
            operation
            for operation in program.operations
            if isinstance(operation, Measure)
        ]
        if len(measurements) != 1 or not isinstance(program.operations[-1], Measure):
            raise ValueError("program must end with exactly one measurement")

        snapshot = self._backend.simulate(program)
        probability_map = self._backend.outcome_probabilities(snapshot.state)
        labels = tuple(sorted(probability_map))
        probabilities = np.asarray([probability_map[label] for label in labels])
        sampled = self._rng.choice(labels, size=shots, p=probabilities)
        if self._observation_model is None:
            outcomes = tuple(str(value) for value in sampled)
            shot_readouts = ()
        else:
            latent_outcomes = tuple(str(value) for value in sampled)
            batch_observer = getattr(
                self._observation_model, "observe_latent_outcomes", None
            )
            if callable(batch_observer):
                shot_readouts = tuple(
                    batch_observer(latent_outcomes, self._rng)
                )
            else:
                shot_readouts = tuple(
                    self._observation_model.observe_latent_outcome(
                        value, self._rng
                    )
                    for value in latent_outcomes
                )
            outcomes = tuple(record.outcome for record in shot_readouts)
        counts = dict(Counter(outcomes))

        self._execution_counter += 1
        execution_id = f"run-{self._execution_counter:06d}"
        start_time_us = self._virtual_time_us
        self._virtual_time_us += shots * snapshot.duration_us
        resources = ResourceUsage(
            shots=shots,
            pulses_per_shot=snapshot.pulse_count,
            pulse_time_per_shot_us=snapshot.pulse_time_us,
            sequence_time_per_shot_us=snapshot.duration_us,
            total_sequence_time_us=shots * snapshot.duration_us,
            channel_time_per_shot_us=snapshot.channel_time_us,
        )
        return ExperimentResult(
            execution_id=execution_id,
            counts=counts,
            shot_outcomes=outcomes,
            public_timestamp_us=start_time_us,
            status="completed",
            resources=resources,
            metadata={"program_name": program.name},
            shot_readouts=shot_readouts,
        )
