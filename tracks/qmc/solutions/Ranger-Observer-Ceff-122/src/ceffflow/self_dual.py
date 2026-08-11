"""Born-sampled weak self-dual monitored Ising circuit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

SELF_DUAL_BETA = float(np.arctanh(1.0 / np.sqrt(2.0)))


@dataclass(frozen=True, slots=True)
class CoupledSelfDualEstimate:
    """Paired Shannon-rate blocks for several periodic circumferences."""

    lengths: NDArray[np.int64]
    beta: float
    steps: int
    burn_in: int
    block_size: int
    blocks: NDArray[np.float64]

    @property
    def means(self) -> NDArray[np.float64]:
        return np.mean(self.blocks, axis=0)

    @property
    def covariance_of_mean(self) -> NDArray[np.float64]:
        return np.cov(self.blocks, rowvar=False, ddof=1) / self.blocks.shape[0]


class SelfDualBornCylinder:
    r"""Exact conditional state for the self-dual nonunitary Ising circuit."""

    def __init__(self, length: int, beta: float = SELF_DUAL_BETA):
        if length < 3:
            raise ValueError("periodic self-dual cylinder requires L >= 3")
        if beta <= 0.0:
            raise ValueError("beta must be positive")
        self.length = int(length)
        self.beta = float(beta)
        self.dimension = 1 << self.length
        states = np.arange(self.dimension, dtype=np.uint64)
        bits = (
            (states[:, None] >> np.arange(self.length, dtype=np.uint64)) & 1
        )
        spins = 2.0 * bits.astype(float) - 1.0
        self._zz = (spins * np.roll(spins, -1, axis=1)).T
        self._flip = np.asarray(
            [
                states ^ (np.uint64(1) << np.uint64(site))
                for site in range(self.length)
            ]
        )
        self._cosh_half = float(np.cosh(self.beta / 2.0))
        self._sinh_half = float(np.sinh(self.beta / 2.0))
        self._normalization = float(np.sqrt(2.0 * np.cosh(self.beta)))
        self._tanh = float(np.tanh(self.beta))

    def plus_state(self) -> NDArray[np.complex128]:
        return np.full(
            self.dimension,
            1.0 / np.sqrt(self.dimension),
            dtype=np.complex128,
        )

    @staticmethod
    def _sample_sign(
        expectation: float, tanh_beta: float, uniform: float
    ) -> tuple[int, float]:
        expectation = float(np.clip(expectation, -1.0, 1.0))
        probability_plus = 0.5 * (1.0 + tanh_beta * expectation)
        sign = 1 if uniform < probability_plus else -1
        probability = probability_plus if sign == 1 else 1.0 - probability_plus
        return sign, float(probability)

    def sample_zz(
        self,
        state: NDArray[np.complex128],
        bond: int,
        uniform: float,
    ) -> tuple[NDArray[np.complex128], float, int]:
        probability_plus = self.zz_probability_plus(state, bond)
        sign = 1 if uniform < probability_plus else -1
        probability = (
            probability_plus if sign == 1 else 1.0 - probability_plus
        )
        updated, checked_probability = self.update_zz(state, bond, sign)
        if not np.isclose(probability, checked_probability, atol=1e-14):
            raise FloatingPointError("inconsistent ZZ Born probability")
        return updated, probability, sign

    def zz_probability_plus(
        self, state: NDArray[np.complex128], bond: int
    ) -> float:
        expectation = float(np.abs(state) ** 2 @ self._zz[bond])
        return float(0.5 * (1.0 + self._tanh * expectation))

    def update_zz(
        self, state: NDArray[np.complex128], bond: int, sign: int
    ) -> tuple[NDArray[np.complex128], float]:
        if sign not in (-1, 1):
            raise ValueError("measurement sign must be -1 or 1")
        probability_plus = self.zz_probability_plus(state, bond)
        probability = probability_plus if sign == 1 else 1.0 - probability_plus
        factor = np.exp(0.5 * sign * self.beta * self._zz[bond])
        updated = state * factor / self._normalization
        updated /= np.sqrt(probability)
        return updated, float(probability)

    def sample_x(
        self,
        state: NDArray[np.complex128],
        site: int,
        uniform: float,
    ) -> tuple[NDArray[np.complex128], float, int]:
        probability_plus = self.x_probability_plus(state, site)
        sign = 1 if uniform < probability_plus else -1
        probability = (
            probability_plus if sign == 1 else 1.0 - probability_plus
        )
        updated, checked_probability = self.update_x(state, site, sign)
        if not np.isclose(probability, checked_probability, atol=1e-14):
            raise FloatingPointError("inconsistent X Born probability")
        return updated, probability, sign

    def x_probability_plus(
        self, state: NDArray[np.complex128], site: int
    ) -> float:
        flipped = state[self._flip[site]]
        expectation = float(np.real(np.vdot(state, flipped)))
        return float(0.5 * (1.0 + self._tanh * expectation))

    def x_pair_expectations(
        self,
        state: NDArray[np.complex128],
        first: int,
        second: int,
    ) -> tuple[float, float, float]:
        """Return <X_first>, <X_second>, and <X_first X_second>."""

        if first == second:
            raise ValueError("sites must be distinct")
        if not (
            0 <= first < self.length and 0 <= second < self.length
        ):
            raise ValueError("sites must be in range")
        if state.shape != (self.dimension,):
            raise ValueError("state has incompatible dimension")
        first_flipped = state[self._flip[first]]
        second_flipped = state[self._flip[second]]
        pair_flipped = state[self._flip[first]][self._flip[second]]
        return (
            float(np.real(np.vdot(state, first_flipped))),
            float(np.real(np.vdot(state, second_flipped))),
            float(np.real(np.vdot(state, pair_flipped))),
        )

    def update_x(
        self, state: NDArray[np.complex128], site: int, sign: int
    ) -> tuple[NDArray[np.complex128], float]:
        if sign not in (-1, 1):
            raise ValueError("measurement sign must be -1 or 1")
        probability_plus = self.x_probability_plus(state, site)
        probability = probability_plus if sign == 1 else 1.0 - probability_plus
        flipped = state[self._flip[site]]
        updated = (
            self._cosh_half * state + sign * self._sinh_half * flipped
        ) / self._normalization
        updated /= np.sqrt(probability)
        return updated, float(probability)

    def sample_row(
        self,
        state: NDArray[np.complex128],
        zz_uniforms: NDArray[np.float64],
        x_uniforms: NDArray[np.float64],
    ) -> tuple[NDArray[np.complex128], float]:
        if zz_uniforms.shape != (self.length,) or x_uniforms.shape != (
            self.length,
        ):
            raise ValueError("each row needs L uniforms for both gate families")
        log_probability = 0.0
        for bond, uniform in enumerate(zz_uniforms):
            state, probability, _ = self.sample_zz(
                state, bond, float(uniform)
            )
            log_probability += np.log(probability)
        for site, uniform in enumerate(x_uniforms):
            state, probability, _ = self.sample_x(
                state, site, float(uniform)
            )
            log_probability += np.log(probability)
        return state, float(log_probability)


class SelfDualGaussianCylinder:
    r"""Pure-Gaussian covariance implementation of the same Born circuit."""

    def __init__(self, length: int, beta: float = SELF_DUAL_BETA):
        if length < 3:
            raise ValueError("periodic self-dual cylinder requires L >= 3")
        if beta <= 0.0:
            raise ValueError("beta must be positive")
        self.length = int(length)
        self.beta = float(beta)
        self.majorana_dimension = 2 * self.length
        self._tanh = float(np.tanh(self.beta))
        self._cosh = float(np.cosh(self.beta))
        self._sinh = float(np.sinh(self.beta))

    def plus_covariance(self) -> NDArray[np.float64]:
        covariance = np.zeros(
            (self.majorana_dimension, self.majorana_dimension)
        )
        for site in range(self.length):
            first = 2 * site
            covariance[first, first + 1] = 1.0
            covariance[first + 1, first] = -1.0
        return covariance

    def _sample_bilinear(
        self,
        covariance: NDArray[np.float64],
        first: int,
        second: int,
        uniform: float,
    ) -> tuple[NDArray[np.float64], float, int]:
        probability_plus = self._bilinear_probability_plus(
            covariance, first, second
        )
        sign = 1 if uniform < probability_plus else -1
        probability = (
            probability_plus if sign == 1 else 1.0 - probability_plus
        )
        updated, checked_probability = self._update_bilinear(
            covariance, first, second, sign
        )
        if not np.isclose(probability, checked_probability, atol=1e-14):
            raise FloatingPointError("inconsistent Gaussian Born probability")
        return updated, probability, sign

    def _bilinear_probability_plus(
        self,
        covariance: NDArray[np.float64],
        first: int,
        second: int,
    ) -> float:
        expectation = float(covariance[first, second])
        return float(0.5 * (1.0 + self._tanh * expectation))

    def bilinear_probability_plus_batch(
        self,
        covariances: NDArray[np.float64],
        first: int,
        second: int,
    ) -> NDArray[np.float64]:
        """Return plus probabilities for a leading batch of covariances."""

        values = np.asarray(covariances, dtype=float)
        if values.ndim != 3:
            raise ValueError(
                "covariances must have shape (particles, 2L, 2L)"
            )
        expected_shape = (
            values.shape[0],
            self.majorana_dimension,
            self.majorana_dimension,
        )
        if values.shape != expected_shape:
            raise ValueError(
                "covariances must have shape (particles, 2L, 2L)"
            )
        if not (
            0 <= first < self.majorana_dimension
            and 0 <= second < self.majorana_dimension
            and first != second
        ):
            raise ValueError("bilinear indices must be distinct and in range")
        expectations = values[:, first, second]
        return 0.5 * (1.0 + self._tanh * expectations)

    def _update_bilinear(
        self,
        covariance: NDArray[np.float64],
        first: int,
        second: int,
        sign: int,
    ) -> tuple[NDArray[np.float64], float]:
        if sign not in (-1, 1):
            raise ValueError("measurement sign must be -1 or 1")
        expectation = float(covariance[first, second])
        probability_plus = self._bilinear_probability_plus(
            covariance, first, second
        )
        probability = probability_plus if sign == 1 else 1.0 - probability_plus
        denominator = self._cosh + sign * self._sinh * expectation
        outside = np.ones(self.majorana_dimension, dtype=bool)
        outside[[first, second]] = False
        indices = np.flatnonzero(outside)
        updated = np.zeros_like(covariance)
        submatrix = covariance[np.ix_(indices, indices)]
        wick = (
            expectation * submatrix
            + np.outer(covariance[indices, first], covariance[second, indices])
            - np.outer(covariance[indices, second], covariance[first, indices])
        )
        updated[np.ix_(indices, indices)] = (
            self._cosh * submatrix + sign * self._sinh * wick
        ) / denominator
        updated[first, indices] = covariance[first, indices] / denominator
        updated[indices, first] = -updated[first, indices]
        updated[second, indices] = covariance[second, indices] / denominator
        updated[indices, second] = -updated[second, indices]
        updated[first, second] = (
            self._cosh * expectation + sign * self._sinh
        ) / denominator
        updated[second, first] = -updated[first, second]
        return updated, float(probability)

    def update_bilinear_batch(
        self,
        covariances: NDArray[np.float64],
        first: int,
        second: int,
        signs: NDArray[np.int8],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Apply one signed bilinear update to every covariance in a batch."""

        values = np.asarray(covariances, dtype=float)
        probabilities_plus = self.bilinear_probability_plus_batch(
            values, first, second
        )
        outcomes = np.asarray(signs, dtype=np.int8)
        if outcomes.shape != (values.shape[0],) or not np.all(
            np.isin(outcomes, (-1, 1))
        ):
            raise ValueError("signs must be one ±1 value per particle")
        expectations = values[:, first, second]
        denominators = (
            self._cosh + outcomes * self._sinh * expectations
        )
        outside = np.ones(self.majorana_dimension, dtype=bool)
        outside[[first, second]] = False
        indices = np.flatnonzero(outside)
        submatrices = values[
            :, indices[:, None], indices[None, :]
        ]
        wick = (
            expectations[:, None, None] * submatrices
            + np.einsum(
                "pi,pj->pij",
                values[:, indices, first],
                values[:, second, indices],
            )
            - np.einsum(
                "pi,pj->pij",
                values[:, indices, second],
                values[:, first, indices],
            )
        )
        updated = np.zeros_like(values)
        updated[:, indices[:, None], indices[None, :]] = (
            self._cosh * submatrices
            + outcomes[:, None, None] * self._sinh * wick
        ) / denominators[:, None, None]
        updated[:, first, indices] = (
            values[:, first, indices] / denominators[:, None]
        )
        updated[:, indices, first] = -updated[:, first, indices]
        updated[:, second, indices] = (
            values[:, second, indices] / denominators[:, None]
        )
        updated[:, indices, second] = -updated[:, second, indices]
        updated[:, first, second] = (
            self._cosh * expectations + outcomes * self._sinh
        ) / denominators
        updated[:, second, first] = -updated[:, first, second]
        selected_probabilities = np.where(
            outcomes == 1, probabilities_plus, 1.0 - probabilities_plus
        )
        return updated, selected_probabilities

    def zz_probability_plus(
        self, covariance: NDArray[np.float64], bond: int
    ) -> float:
        first, second = self._zz_indices(bond)
        return self._bilinear_probability_plus(covariance, first, second)

    def update_zz(
        self, covariance: NDArray[np.float64], bond: int, sign: int
    ) -> tuple[NDArray[np.float64], float]:
        first, second = self._zz_indices(bond)
        return self._update_bilinear(covariance, first, second, sign)

    def _zz_indices(self, bond: int) -> tuple[int, int]:
        if not 0 <= bond < self.length:
            raise ValueError("bond index out of range")
        if bond == self.length - 1:
            return 0, self.majorana_dimension - 1
        return 2 * bond + 1, 2 * bond + 2

    def sample_zz(
        self,
        covariance: NDArray[np.float64],
        bond: int,
        uniform: float,
    ) -> tuple[NDArray[np.float64], float, int]:
        first, second = self._zz_indices(bond)
        return self._sample_bilinear(
            covariance, first, second, uniform
        )

    def x_probability_plus(
        self, covariance: NDArray[np.float64], site: int
    ) -> float:
        if not 0 <= site < self.length:
            raise ValueError("site index out of range")
        return self._bilinear_probability_plus(
            covariance, 2 * site, 2 * site + 1
        )

    def update_x(
        self, covariance: NDArray[np.float64], site: int, sign: int
    ) -> tuple[NDArray[np.float64], float]:
        if not 0 <= site < self.length:
            raise ValueError("site index out of range")
        return self._update_bilinear(
            covariance, 2 * site, 2 * site + 1, sign
        )

    def sample_x(
        self,
        covariance: NDArray[np.float64],
        site: int,
        uniform: float,
    ) -> tuple[NDArray[np.float64], float, int]:
        return self._sample_bilinear(
            covariance, 2 * site, 2 * site + 1, uniform
        )

    def sample_row(
        self,
        covariance: NDArray[np.float64],
        zz_uniforms: NDArray[np.float64],
        x_uniforms: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], float]:
        if zz_uniforms.shape != (self.length,) or x_uniforms.shape != (
            self.length,
        ):
            raise ValueError("each row needs L uniforms for both gate families")
        log_probability = 0.0
        for bond, uniform in enumerate(zz_uniforms):
            covariance, probability, _ = self.sample_zz(
                covariance, bond, float(uniform)
            )
            log_probability += np.log(probability)
        for site, uniform in enumerate(x_uniforms):
            covariance, probability, _ = self.sample_x(
                covariance, site, float(uniform)
            )
            log_probability += np.log(probability)
        return covariance, float(log_probability)


def _validated_lengths(
    lengths: list[int] | NDArray[np.int64],
    steps: int,
    burn_in: int,
    block_size: int,
) -> NDArray[np.int64]:
    sizes = np.asarray(lengths, dtype=int)
    if (
        sizes.ndim != 1
        or sizes.size < 3
        or np.unique(sizes).size != sizes.size
    ):
        raise ValueError("lengths must contain at least three unique widths")
    if np.any(sizes < 3):
        raise ValueError("all widths must be at least three")
    if steps < block_size or steps % block_size:
        raise ValueError("steps must be a positive multiple of block_size")
    if burn_in < 0:
        raise ValueError("burn_in must be nonnegative")
    return np.sort(sizes).astype(np.int64)


def _estimate_coupled(
    lengths: list[int] | NDArray[np.int64],
    *,
    beta: float,
    steps: int,
    burn_in: int,
    block_size: int,
    seed: int,
    gaussian: bool,
) -> CoupledSelfDualEstimate:
    sizes = _validated_lengths(lengths, steps, burn_in, block_size)
    if gaussian:
        cylinders = [
            SelfDualGaussianCylinder(int(length), beta) for length in sizes
        ]
        states = [cylinder.plus_covariance() for cylinder in cylinders]
    else:
        cylinders = [
            SelfDualBornCylinder(int(length), beta) for length in sizes
        ]
        states = [cylinder.plus_state() for cylinder in cylinders]
    rng = np.random.default_rng(seed)
    maximum_length = int(sizes[-1])

    def coupled_step() -> NDArray[np.float64]:
        zz_uniforms = rng.random(maximum_length)
        x_uniforms = rng.random(maximum_length)
        log_probabilities = np.empty(sizes.size)
        for index, (length, cylinder) in enumerate(
            zip(sizes, cylinders, strict=True)
        ):
            width = int(length)
            states[index], log_probabilities[index] = cylinder.sample_row(
                states[index], zz_uniforms[:width], x_uniforms[:width]
            )
        return log_probabilities

    for _ in range(burn_in):
        coupled_step()
    blocks = np.empty((steps // block_size, sizes.size))
    for block in range(blocks.shape[0]):
        total = np.zeros(sizes.size)
        for _ in range(block_size):
            total += coupled_step()
        blocks[block] = -total / block_size
    return CoupledSelfDualEstimate(
        lengths=sizes,
        beta=float(beta),
        steps=steps,
        burn_in=burn_in,
        block_size=block_size,
        blocks=blocks,
    )


def estimate_coupled_self_dual_record_rates(
    lengths: list[int] | NDArray[np.int64],
    *,
    beta: float = SELF_DUAL_BETA,
    steps: int = 20_000,
    burn_in: int = 1_000,
    block_size: int = 200,
    seed: int = 0,
) -> CoupledSelfDualEstimate:
    """Estimate exact-spin Born-record Shannon rates under common uniforms."""

    return _estimate_coupled(
        lengths,
        beta=beta,
        steps=steps,
        burn_in=burn_in,
        block_size=block_size,
        seed=seed,
        gaussian=False,
    )


def estimate_coupled_gaussian_self_dual_record_rates(
    lengths: list[int] | NDArray[np.int64],
    *,
    beta: float = SELF_DUAL_BETA,
    steps: int = 20_000,
    burn_in: int = 1_000,
    block_size: int = 200,
    seed: int = 0,
) -> CoupledSelfDualEstimate:
    """Estimate exact-Gaussian Born-record Shannon rates."""

    return _estimate_coupled(
        lengths,
        beta=beta,
        steps=steps,
        burn_in=burn_in,
        block_size=block_size,
        seed=seed,
        gaussian=True,
    )
