"""Classical observation channels acting on binary Born records."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _binary_probability(latent_prob_plus: float) -> float:
    probability = float(latent_prob_plus)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("latent_prob_plus must lie in [0, 1]")
    return probability


def _validated_record(outcomes: ArrayLike) -> NDArray[np.int8]:
    record = np.asarray(outcomes, dtype=np.int8)
    if not np.all(np.isin(record, (-1, 0, 1))):
        raise ValueError("record values must be -1, 0, or 1")
    return record


def _validated_uniforms(
    uniforms: ArrayLike, shape: tuple[int, ...]
) -> NDArray[np.float64]:
    values = np.asarray(uniforms, dtype=float)
    if values.shape != shape:
        raise ValueError("uniforms must have the same shape as outcomes")
    if not np.all((values >= 0.0) & (values < 1.0)):
        raise ValueError("uniforms must lie in [0, 1)")
    return values


@dataclass(frozen=True, slots=True)
class ErasureChannel:
    """Replace retained binary outcomes by a declared null symbol."""

    retain_probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.retain_probability <= 1.0:
            raise ValueError("retain_probability must lie in [0, 1]")

    def apply(
        self, outcomes: ArrayLike, uniforms: ArrayLike
    ) -> NDArray[np.int8]:
        record = _validated_record(outcomes)
        draws = _validated_uniforms(uniforms, record.shape)
        retained = (draws < self.retain_probability) & (record != 0)
        return np.where(retained, record, 0).astype(np.int8)

    def log_observed_probability(
        self, observed: int, latent_prob_plus: float
    ) -> float:
        probability_plus = _binary_probability(latent_prob_plus)
        if observed == 0:
            probability = 1.0 - self.retain_probability
        elif observed == 1:
            probability = self.retain_probability * probability_plus
        elif observed == -1:
            probability = self.retain_probability * (1.0 - probability_plus)
        else:
            raise ValueError("erasure observations must be -1, 0, or 1")
        return float(np.log(probability)) if probability > 0.0 else -np.inf

    def conditional_probability(self, observed: int, latent: int) -> float:
        """Return the classical kernel K(observed | latent)."""

        if latent not in (-1, 1):
            raise ValueError("latent outcome must be -1 or 1")
        if observed == 0:
            return 1.0 - self.retain_probability
        if observed in (-1, 1):
            return self.retain_probability if observed == latent else 0.0
        raise ValueError("erasure observations must be -1, 0, or 1")


@dataclass(frozen=True, slots=True)
class ConfusionChannel:
    """Flip a binary record with a declared readout-error probability."""

    error_probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.error_probability <= 0.5:
            raise ValueError("error_probability must lie in [0, 1/2]")

    def apply(
        self, outcomes: ArrayLike, uniforms: ArrayLike
    ) -> NDArray[np.int8]:
        record = _validated_record(outcomes)
        draws = _validated_uniforms(uniforms, record.shape)
        flips = (draws < self.error_probability) & (record != 0)
        return np.where(flips, -record, record).astype(np.int8)

    def log_observed_probability(
        self, observed: int, latent_prob_plus: float
    ) -> float:
        if observed not in (-1, 1):
            raise ValueError("confusion observations must be -1 or 1")
        probability_plus = _binary_probability(latent_prob_plus)
        error = self.error_probability
        observed_plus = (
            probability_plus * (1.0 - error)
            + (1.0 - probability_plus) * error
        )
        probability = observed_plus if observed == 1 else 1.0 - observed_plus
        return float(np.log(probability)) if probability > 0.0 else -np.inf

    def conditional_probability(self, observed: int, latent: int) -> float:
        """Return the classical kernel K(observed | latent)."""

        if latent not in (-1, 1) or observed not in (-1, 1):
            raise ValueError("confusion outcomes must be -1 or 1")
        return (
            1.0 - self.error_probability
            if observed == latent
            else self.error_probability
        )
