from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from math import ceil, factorial, pi

import numpy as np
from scipy.special import eval_legendre, lpmv

from challenge15.spec import SphereSpec


@dataclass(frozen=True, slots=True)
class ProjectionBlock:
    """One bounded-memory slice of the Cartesian Euler quadrature."""

    alpha_indices: np.ndarray
    beta_indices: np.ndarray
    alpha_nodes: np.ndarray
    beta_nodes: np.ndarray
    weights: np.ndarray

    def __post_init__(self) -> None:
        arrays = (
            self.alpha_indices,
            self.beta_indices,
            self.alpha_nodes,
            self.beta_nodes,
            self.weights,
        )
        if not all(isinstance(array, np.ndarray) for array in arrays):
            raise ValueError("projection block entries must be NumPy arrays")
        if self.alpha_indices.dtype != np.int64 or self.beta_indices.dtype != np.int64:
            raise ValueError("projection block indices must use int64")
        if self.alpha_nodes.dtype != np.float64 or self.beta_nodes.dtype != np.float64:
            raise ValueError("projection block nodes must use float64")
        if self.weights.dtype != np.complex128:
            raise ValueError("projection block weights must use complex128")
        if not all(array.ndim == 1 and array.shape == self.alpha_nodes.shape for array in arrays):
            raise ValueError("projection block entries must be matching one-dimensional arrays")
        for name in (
            "alpha_indices",
            "beta_indices",
            "alpha_nodes",
            "beta_nodes",
            "weights",
        ):
            object.__setattr__(self, name, _sealed_array(getattr(self, name)))

    @property
    def size(self) -> int:
        return int(self.alpha_nodes.size)


@dataclass(frozen=True, slots=True)
class StaticProjectionBlocks:
    """Padded Cartesian nodes for one shape-static pairwise reduction."""

    alpha_nodes: np.ndarray
    beta_nodes: np.ndarray
    weights: np.ndarray
    node_valid: np.ndarray
    tree_valid: np.ndarray

    def __post_init__(self) -> None:
        arrays = (
            self.alpha_nodes,
            self.beta_nodes,
            self.weights,
            self.node_valid,
            self.tree_valid,
        )
        if not all(isinstance(array, np.ndarray) for array in arrays):
            raise ValueError("static projection block entries must be NumPy arrays")
        if self.alpha_nodes.dtype != np.float64 or self.beta_nodes.dtype != np.float64:
            raise ValueError("static projection nodes must use float64")
        if self.weights.dtype != np.complex128:
            raise ValueError("static projection weights must use complex128")
        if self.node_valid.dtype != np.bool_ or self.tree_valid.dtype != np.bool_:
            raise ValueError("static projection masks must use bool")
        if not all(array.ndim == 2 and array.shape == self.alpha_nodes.shape for array in arrays):
            raise ValueError("static projection block entries must have matching shapes")
        for name in (
            "alpha_nodes",
            "beta_nodes",
            "weights",
            "node_valid",
            "tree_valid",
        ):
            object.__setattr__(self, name, _sealed_array(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class ProjectionGrid:
    """Exact finite-band Fourier/Gauss--Legendre projector grid."""

    alpha_nodes: np.ndarray
    alpha_weights: np.ndarray
    beta_nodes: np.ndarray
    beta_weights: np.ndarray
    target_l: int
    l_max: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target_l, int)
            or isinstance(self.target_l, bool)
            or self.target_l < 0
        ):
            raise ValueError("target_l must be a nonnegative Python integer")
        if (
            not isinstance(self.l_max, int)
            or isinstance(self.l_max, bool)
            or self.l_max < self.target_l
        ):
            raise ValueError("l_max must be a Python integer at least target_l")
        arrays = (
            self.alpha_nodes,
            self.alpha_weights,
            self.beta_nodes,
            self.beta_weights,
        )
        if not all(isinstance(array, np.ndarray) for array in arrays):
            raise ValueError("quadrature nodes and weights must be NumPy arrays")
        if self.alpha_nodes.ndim != 1 or self.alpha_weights.shape != self.alpha_nodes.shape:
            raise ValueError("alpha nodes and weights must be matching one-dimensional arrays")
        if self.beta_nodes.ndim != 1 or self.beta_weights.shape != self.beta_nodes.shape:
            raise ValueError("beta nodes and weights must be matching one-dimensional arrays")
        if self.n_alpha == 0 or self.n_beta == 0:
            raise ValueError("quadrature rules must be nonempty")
        if self.alpha_nodes.dtype != np.float64 or self.beta_nodes.dtype != np.float64:
            raise ValueError("quadrature nodes must use float64")
        if (
            self.alpha_weights.dtype != np.complex128
            or self.beta_weights.dtype != np.complex128
        ):
            raise ValueError("quadrature weights must use complex128")
        if any(array.flags.writeable for array in arrays):
            raise ValueError("quadrature nodes and weights must be immutable")
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise ValueError("quadrature nodes and weights must be finite")
        if self.n_alpha < 2 * self.l_max + 1:
            raise ValueError("alpha rule does not satisfy the exact finite-band bound")
        if 2 * self.n_beta - 1 < self.l_max + self.target_l:
            raise ValueError("beta rule does not satisfy the exact polynomial bound")

        alpha_step = 2.0 * pi / self.n_alpha
        expected_alpha_nodes = np.arange(self.n_alpha, dtype=np.float64) * alpha_step
        expected_alpha_weights = np.full(
            self.n_alpha, alpha_step, dtype=np.complex128
        )
        tolerance = 8 * np.finfo(np.float64).eps
        if not np.allclose(
            self.alpha_nodes, expected_alpha_nodes, atol=tolerance, rtol=0.0
        ):
            raise ValueError("alpha nodes must be the canonical equispaced periodic rule")
        if not np.allclose(
            self.alpha_weights, expected_alpha_weights, atol=tolerance, rtol=0.0
        ):
            raise ValueError("alpha weights must match the canonical periodic rule")

        expected_beta_nodes, expected_beta_weights = np.polynomial.legendre.leggauss(
            self.n_beta
        )
        if not np.allclose(
            self.beta_nodes, expected_beta_nodes, atol=tolerance, rtol=0.0
        ) or not np.allclose(
            self.beta_weights,
            np.asarray(expected_beta_weights, dtype=np.complex128),
            atol=tolerance,
            rtol=0.0,
        ):
            raise ValueError("beta nodes and weights must match Gauss-Legendre")

        for name in (
            "alpha_nodes",
            "alpha_weights",
            "beta_nodes",
            "beta_weights",
        ):
            object.__setattr__(self, name, _sealed_array(getattr(self, name)))

    @property
    def n_alpha(self) -> int:
        return int(self.alpha_nodes.size)

    @property
    def n_beta(self) -> int:
        return int(self.beta_nodes.size)

    @classmethod
    def exact(cls, spec: SphereSpec, target_l: int) -> ProjectionGrid:
        _validate_target_l(spec, target_l)
        n_alpha = 2 * spec.l_max + 1
        n_beta = (spec.l_max + target_l + 2) // 2
        alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2.0 * pi / n_alpha)
        alpha_weights = np.full(
            n_alpha, 2.0 * pi / n_alpha, dtype=np.complex128
        )
        beta_nodes, beta_weights_real = np.polynomial.legendre.leggauss(n_beta)
        beta_nodes = np.asarray(beta_nodes, dtype=np.float64)
        beta_weights = np.asarray(beta_weights_real, dtype=np.complex128)
        for array in (alpha_nodes, alpha_weights, beta_nodes, beta_weights):
            array.setflags(write=False)
        return cls(
            alpha_nodes=alpha_nodes,
            alpha_weights=alpha_weights,
            beta_nodes=beta_nodes,
            beta_weights=beta_weights,
            target_l=target_l,
            l_max=spec.l_max,
        )

    def iter_blocks(self, block_size: int) -> Iterator[ProjectionBlock]:
        _validate_block_size(block_size)
        total = self.n_alpha * self.n_beta
        for start in range(0, total, block_size):
            flat = np.arange(start, min(start + block_size, total), dtype=np.int64)
            alpha_indices = flat % self.n_alpha
            beta_indices = flat // self.n_alpha
            yield ProjectionBlock(
                alpha_indices=alpha_indices,
                beta_indices=beta_indices,
                alpha_nodes=self.alpha_nodes[alpha_indices],
                beta_nodes=self.beta_nodes[beta_indices],
                weights=(
                    self.alpha_weights[alpha_indices]
                    * self.beta_weights[beta_indices]
                ),
            )

    def blocks(self, block_size: int) -> Iterator[ProjectionBlock]:
        """Alias for callers that prefer a shorter blocked-iteration name."""

        return self.iter_blocks(block_size)

    def static_blocks(self, block_size: int) -> StaticProjectionBlocks:
        """Return padded blocks without materializing rotated walker tensors."""

        _validate_block_size(block_size)
        total = self.n_alpha * self.n_beta
        tree_size = 1 << (total - 1).bit_length()
        padded_size = ceil(tree_size / block_size) * block_size
        flat = np.arange(padded_size, dtype=np.int64)
        node_valid = flat < total
        tree_valid = flat < tree_size
        safe = np.where(node_valid, flat, 0)
        alpha_indices = safe % self.n_alpha
        beta_indices = safe // self.n_alpha
        shape = (padded_size // block_size, block_size)
        return StaticProjectionBlocks(
            alpha_nodes=self.alpha_nodes[alpha_indices].reshape(shape),
            beta_nodes=self.beta_nodes[beta_indices].reshape(shape),
            weights=np.where(
                node_valid,
                self.alpha_weights[alpha_indices]
                * self.beta_weights[beta_indices],
                0.0,
            ).reshape(shape),
            node_valid=node_valid.reshape(shape),
            tree_valid=tree_valid.reshape(shape),
        )


def coordinate_euler_substitutions(
    alpha: np.ndarray, beta_nodes: np.ndarray
) -> np.ndarray:
    """Return substitutions implementing active ``Rz(alpha) Ry(beta)``."""

    half_alpha = alpha / 2.0
    beta = np.arccos(beta_nodes)
    cosine = np.cos(beta / 2.0)
    sine = np.sin(beta / 2.0)
    z_first = np.exp(-1j * half_alpha)
    z_second = np.exp(1j * half_alpha)
    rotations = np.empty((alpha.size, 2, 2), dtype=np.complex128)
    rotations[:, 0, 0] = cosine * z_first
    rotations[:, 0, 1] = sine * z_second
    rotations[:, 1, 0] = -sine * z_first
    rotations[:, 1, 1] = cosine * z_second
    return _sealed_array(rotations)


def wigner_d_m0(target_l: int, m: int, x: np.ndarray) -> np.ndarray:
    if abs(m) > target_l:
        raise ValueError("component M must satisfy |M| <= target_l")
    if m == 0:
        return _sealed_array(
            np.asarray(eval_legendre(target_l, x), dtype=np.float64)
        )
    magnitude = abs(m)
    positive = np.sqrt(
        factorial(target_l - magnitude) / factorial(target_l + magnitude)
    ) * lpmv(magnitude, target_l, x)
    if m < 0:
        positive = (-1) ** magnitude * positive
    return _sealed_array(np.asarray(positive, dtype=np.float64))


def _validate_target_l(spec: SphereSpec, target_l: int) -> None:
    if not isinstance(target_l, int) or isinstance(target_l, bool):
        raise ValueError("target_l must be a Python integer")
    if target_l < 0 or target_l > spec.l_max:
        raise ValueError("target_l must satisfy 0 <= target_l <= spec.l_max")


def _validate_block_size(block_size: int) -> None:
    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError("block_size must be a positive Python integer")


def _sealed_array(array: np.ndarray) -> np.ndarray:
    """Copy an array onto an immutable bytes backing store."""

    return np.frombuffer(array.tobytes(order="C"), dtype=array.dtype).reshape(array.shape)
