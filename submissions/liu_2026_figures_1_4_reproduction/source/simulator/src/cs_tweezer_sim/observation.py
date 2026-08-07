"""Likelihood-level fluorescence and retention observations.

The backend supplies latent local measurement labels.  This module turns them
into camera signals and public classifications.  It deliberately does not
return latent labels to the controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.stats import exponnorm, skewnorm

from .contracts import AtomReadout, ShotReadout


@dataclass(frozen=True)
class FluorescenceMixtureCalibration:
    """Conditional dark/bright camera distributions and retention errors."""

    dark_fraction: float
    dark_location_photoelectrons: float
    dark_scale_photoelectrons: float
    dark_shape_k: float
    bright_location_photoelectrons: float
    bright_scale_photoelectrons: float
    bright_shape_a: float
    threshold_photoelectrons: float
    bright_readout_loss_probability: float
    dark_readout_loss_probability: float
    source_id: str
    source_url: str
    source_version: str

    def __post_init__(self) -> None:
        finite = (
            self.dark_fraction,
            self.dark_location_photoelectrons,
            self.dark_scale_photoelectrons,
            self.dark_shape_k,
            self.bright_location_photoelectrons,
            self.bright_scale_photoelectrons,
            self.bright_shape_a,
            self.threshold_photoelectrons,
            self.bright_readout_loss_probability,
            self.dark_readout_loss_probability,
        )
        if (
            not np.all(np.isfinite(finite))
            or not 0.0 <= self.dark_fraction <= 1.0
            or self.dark_scale_photoelectrons <= 0
            or self.bright_scale_photoelectrons <= 0
            or self.dark_shape_k <= 0
            or not 0.0 <= self.bright_readout_loss_probability <= 1.0
            or not 0.0 <= self.dark_readout_loss_probability <= 1.0
            or not self.source_id
            or not self.source_url
            or not self.source_version
        ):
            raise ValueError("fluorescence calibration is invalid")

    def dark_false_positive_probability(self) -> float:
        """Probability that a dark distribution crosses the threshold."""

        return float(
            exponnorm.sf(
                self.threshold_photoelectrons,
                self.dark_shape_k,
                loc=self.dark_location_photoelectrons,
                scale=self.dark_scale_photoelectrons,
            )
        )

    def bright_false_negative_probability(self) -> float:
        """Probability that a bright distribution falls below threshold."""

        return float(
            skewnorm.cdf(
                self.threshold_photoelectrons,
                self.bright_shape_a,
                loc=self.bright_location_photoelectrons,
                scale=self.bright_scale_photoelectrons,
            )
        )

    def discrimination_fidelity(self) -> float:
        """Mixture-weighted threshold classification fidelity."""

        error = (
            self.dark_fraction * self.dark_false_positive_probability()
            + (1.0 - self.dark_fraction)
            * self.bright_false_negative_probability()
        )
        return 1.0 - error

    def sample_dark(
        self, rng: np.random.Generator, size: int | tuple[int, ...] | None = None
    ) -> np.ndarray | float:
        return exponnorm.rvs(
            self.dark_shape_k,
            loc=self.dark_location_photoelectrons,
            scale=self.dark_scale_photoelectrons,
            size=size,
            random_state=rng,
        )

    def sample_bright(
        self, rng: np.random.Generator, size: int | tuple[int, ...] | None = None
    ) -> np.ndarray | float:
        return skewnorm.rvs(
            self.bright_shape_a,
            loc=self.bright_location_photoelectrons,
            scale=self.bright_scale_photoelectrons,
            size=size,
            random_state=rng,
        )


class ObservationModel(Protocol):
    """Turn one latent backend outcome into one public camera record."""

    def observe_latent_outcome(
        self, latent_outcome: str, rng: np.random.Generator
    ) -> ShotReadout:
        ...

    def observe_latent_outcomes(
        self,
        latent_outcomes: tuple[str, ...],
        rng: np.random.Generator,
    ) -> tuple[ShotReadout, ...]:
        """Optionally vectorize a batch while preserving public records."""

        ...


@dataclass(frozen=True)
class SequentialNdssrObservationModel:
    """State-selective signal followed by an occupancy/retention signal.

    ``bright_labels`` maps backend local labels to the bright hyperfine
    manifold. Any present label not in this set is dark. ``lost_labels`` are
    absent during occupancy imaging. A retained leakage label can therefore
    masquerade as logical 0 or 1, matching the operational limitation of a
    manifold-selective readout.
    """

    calibration: FluorescenceMixtureCalibration
    bright_labels: frozenset[str] = frozenset({"1"})
    lost_labels: frozenset[str] = frozenset({"L"})
    loss_classification: str = "L"

    def __post_init__(self) -> None:
        if (
            not self.bright_labels
            or not self.lost_labels
            or self.bright_labels & self.lost_labels
            or any(len(label) != 1 for label in self.bright_labels)
            or any(len(label) != 1 for label in self.lost_labels)
            or len(self.loss_classification) != 1
        ):
            raise ValueError("NDSSR label configuration is invalid")

    def _sample_signal(
        self, bright: bool, rng: np.random.Generator
    ) -> float:
        sample = (
            self.calibration.sample_bright(rng)
            if bright
            else self.calibration.sample_dark(rng)
        )
        return float(sample)

    def observe_latent_outcome(
        self, latent_outcome: str, rng: np.random.Generator
    ) -> ShotReadout:
        if not latent_outcome:
            raise ValueError("latent outcome must be non-empty")
        records = []
        for label in latent_outcome:
            state_bright = label in self.bright_labels
            initially_present = label not in self.lost_labels
            state_signal = self._sample_signal(state_bright, rng)
            readout_loss_probability = (
                self.calibration.bright_readout_loss_probability
                if state_bright
                else self.calibration.dark_readout_loss_probability
            )
            survives_readout = initially_present and (
                rng.random() >= readout_loss_probability
            )
            occupancy_signal = self._sample_signal(survives_readout, rng)
            observed_retained = (
                occupancy_signal >= self.calibration.threshold_photoelectrons
            )
            if not observed_retained:
                classification = self.loss_classification
            elif state_signal >= self.calibration.threshold_photoelectrons:
                classification = "1"
            else:
                classification = "0"
            records.append(
                AtomReadout(
                    state_signal_photoelectrons=state_signal,
                    occupancy_signal_photoelectrons=occupancy_signal,
                    classified_state=classification,
                    retained=observed_retained,
                )
            )
        outcome = "".join(record.classified_state for record in records)
        return ShotReadout(tuple(records), outcome)

    def observe_latent_outcomes(
        self,
        latent_outcomes: tuple[str, ...],
        rng: np.random.Generator,
    ) -> tuple[ShotReadout, ...]:
        """Vectorized camera sampling for many equal-width latent outcomes.

        The final immutable ``ShotReadout`` objects are identical in schema to
        scalar observation. Vectorization only avoids one SciPy distribution
        call per atom per shot, which is important for finite-shot controller
        benchmarks.
        """

        if not latent_outcomes:
            return ()
        width = len(latent_outcomes[0])
        if width == 0 or any(
            len(outcome) != width for outcome in latent_outcomes
        ):
            raise ValueError(
                "latent outcomes in one batch must have equal positive width"
            )
        labels = np.asarray(
            [tuple(outcome) for outcome in latent_outcomes], dtype="<U1"
        )
        bright_labels = tuple(self.bright_labels)
        lost_labels = tuple(self.lost_labels)
        state_bright = np.isin(labels, bright_labels)
        initially_present = ~np.isin(labels, lost_labels)

        def sampled_signals(bright_mask: np.ndarray) -> np.ndarray:
            signals = np.empty(bright_mask.shape, dtype=float)
            bright_count = int(np.sum(bright_mask))
            dark_count = int(bright_mask.size - bright_count)
            if bright_count:
                signals[bright_mask] = self.calibration.sample_bright(
                    rng, bright_count
                )
            if dark_count:
                signals[~bright_mask] = self.calibration.sample_dark(
                    rng, dark_count
                )
            return signals

        state_signals = sampled_signals(state_bright)
        readout_loss = np.where(
            state_bright,
            self.calibration.bright_readout_loss_probability,
            self.calibration.dark_readout_loss_probability,
        )
        survives = initially_present & (
            rng.random(state_bright.shape) >= readout_loss
        )
        occupancy_signals = sampled_signals(survives)
        retained = (
            occupancy_signals
            >= self.calibration.threshold_photoelectrons
        )
        classifications = np.where(
            ~retained,
            self.loss_classification,
            np.where(
                state_signals
                >= self.calibration.threshold_photoelectrons,
                "1",
                "0",
            ),
        )

        output = []
        for shot_index in range(len(latent_outcomes)):
            atoms = tuple(
                AtomReadout(
                    state_signal_photoelectrons=float(
                        state_signals[shot_index, atom_index]
                    ),
                    occupancy_signal_photoelectrons=float(
                        occupancy_signals[shot_index, atom_index]
                    ),
                    classified_state=str(
                        classifications[shot_index, atom_index]
                    ),
                    retained=bool(retained[shot_index, atom_index]),
                )
                for atom_index in range(width)
            )
            output.append(
                ShotReadout(
                    atoms,
                    "".join(atom.classified_state for atom in atoms),
                )
            )
        return tuple(output)
