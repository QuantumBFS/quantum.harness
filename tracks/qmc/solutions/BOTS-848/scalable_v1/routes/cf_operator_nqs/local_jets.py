"""Static 5x5 local-coordinate jets for exact pair action.

Strict-LLL homogeneity reduces each active particle from two spinor variables
to one projective tangent variable.  Degree four in each tangent therefore
needs only 25 coefficients instead of the general four-variable 225 layout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import jax.numpy as jnp
import numpy as np

from .cofactor_seed import _cofactor_seed_family_amplitudes
from .seeds import JKCFSeedFamily


_DEGREE = 4
_WIDTH = _DEGREE + 1
_SIZE = _WIDTH * _WIDTH


def _multiplication_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    left: list[int] = []
    right: list[int] = []
    target: list[int] = []
    for a in range(_WIDTH):
        for b in range(_WIDTH):
            for c in range(_WIDTH):
                for d in range(_WIDTH):
                    if a + c <= _DEGREE and b + d <= _DEGREE:
                        left.append(a * _WIDTH + b)
                        right.append(c * _WIDTH + d)
                        target.append((a + c) * _WIDTH + b + d)
    return (
        np.asarray(left, dtype=np.int32),
        np.asarray(right, dtype=np.int32),
        np.asarray(target, dtype=np.int32),
    )


_LEFT_NP, _RIGHT_NP, _TARGET_NP = _multiplication_tables()
_LEFT = jnp.asarray(_LEFT_NP)
_RIGHT = jnp.asarray(_RIGHT_NP)
_TARGET = jnp.asarray(_TARGET_NP)


@dataclass(frozen=True)
class LocalPairJet:
    """Taylor coefficients ``c[a,b]`` for two local tangent variables."""

    coefficients: object
    constant_only: bool = False

    @staticmethod
    def from_constant(value: object, template: object) -> "LocalPairJet":
        coefficients = jnp.zeros_like(template)
        return LocalPairJet(coefficients.at[..., 0].set(value), constant_only=True)

    @property
    def constant_term(self) -> object:
        return self.coefficients[..., 0]

    def __getitem__(self, item: object) -> "LocalPairJet":
        return LocalPairJet(self.coefficients[item], constant_only=self.constant_only)

    def _coerce(self, other: object) -> "LocalPairJet":
        if isinstance(other, LocalPairJet):
            return other
        return LocalPairJet.from_constant(other, self.coefficients)

    def __add__(self, other: object) -> "LocalPairJet":
        checked = self._coerce(other)
        return LocalPairJet(
            self.coefficients + checked.coefficients,
            constant_only=self.constant_only and checked.constant_only,
        )

    __radd__ = __add__

    def __neg__(self) -> "LocalPairJet":
        return LocalPairJet(-self.coefficients, constant_only=self.constant_only)

    def __sub__(self, other: object) -> "LocalPairJet":
        return self + (-self._coerce(other))

    def __rsub__(self, other: object) -> "LocalPairJet":
        return self._coerce(other) - self

    def __mul__(self, other: object) -> "LocalPairJet":
        checked = self._coerce(other)
        if self.constant_only:
            return LocalPairJet(
                checked.coefficients * self.constant_term[..., None],
                constant_only=checked.constant_only,
            )
        if checked.constant_only:
            return LocalPairJet(
                self.coefficients * checked.constant_term[..., None],
                constant_only=False,
            )
        left, right = jnp.broadcast_arrays(self.coefficients, checked.coefficients)
        products = left[..., _LEFT] * right[..., _RIGHT]
        result = jnp.zeros_like(left)
        return LocalPairJet(
            result.at[..., _TARGET].add(products),
            constant_only=False,
        )

    __rmul__ = __mul__

    def __pow__(self, exponent: int) -> "LocalPairJet":
        if isinstance(exponent, bool) or not isinstance(exponent, int) or exponent < 0:
            raise ValueError("local-jet exponent must be a nonnegative integer")
        result = LocalPairJet.from_constant(1.0, self.coefficients)
        factor = self
        power = exponent
        while power:
            if power & 1:
                result = result * factor
            factor = factor * factor
            power >>= 1
        return result


class _LocalJetNamespace:
    def __init__(self, template: object) -> None:
        self._template = template

    def asarray(self, value: object) -> LocalPairJet:
        if isinstance(value, LocalPairJet):
            return value
        return LocalPairJet.from_constant(value, self._template)

    def stack(self, values: Sequence[object]) -> LocalPairJet:
        checked = [self.asarray(value) for value in values]
        return LocalPairJet(
            jnp.stack([value.coefficients for value in checked], axis=0),
            constant_only=all(value.constant_only for value in checked),
        )


def local_pair_seed_jets(
    family: JKCFSeedFamily,
    configs: object,
    pairs: object,
) -> object:
    """Return coefficients with shape ``(6,B,P,5,5)``."""

    checked = jnp.asarray(configs, dtype=jnp.complex128)
    pair_indices = jnp.asarray(pairs, dtype=jnp.int32)
    batch = checked.shape[0]
    pair_count = pair_indices.shape[0]
    template = jnp.zeros((batch, pair_count, _SIZE), dtype=jnp.complex128)
    namespace = _LocalJetNamespace(template)
    lifted: list[list[LocalPairJet]] = []
    for particle in range(family.n_electrons):
        row: list[LocalPairJet] = []
        first_mask = pair_indices[:, 0] == particle
        second_mask = pair_indices[:, 1] == particle
        u = checked[:, particle, 0]
        v = checked[:, particle, 1]
        tangent = (-jnp.conj(v), jnp.conj(u))
        for component in range(2):
            values = jnp.broadcast_to(
                checked[:, None, particle, component],
                (batch, pair_count),
            )
            coefficients = template.at[..., 0].set(values)
            first_direction = tangent[component][:, None] * first_mask[None, :]
            second_direction = tangent[component][:, None] * second_mask[None, :]
            coefficients = coefficients.at[..., _WIDTH].set(first_direction)
            coefficients = coefficients.at[..., 1].set(second_direction)
            row.append(LocalPairJet(coefficients, constant_only=False))
        lifted.append(row)
    result = _cofactor_seed_family_amplitudes(
        family,
        lifted,
        xp=namespace,
    )
    if not isinstance(result, LocalPairJet):
        raise TypeError("local cofactor evaluation did not return a LocalPairJet")
    return result.coefficients.reshape(6, batch, pair_count, _WIDTH, _WIDTH)


__all__ = ["LocalPairJet", "local_pair_seed_jets"]
