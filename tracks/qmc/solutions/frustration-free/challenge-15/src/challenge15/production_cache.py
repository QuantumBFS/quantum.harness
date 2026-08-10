from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from math import ceil, pi

import numpy as np

from challenge15.fermions import DeterminantBasis
from challenge15.projector import ProjectionGrid
from challenge15.spec import SphereSpec


_ALLOWED_DTYPES = frozenset({"float64", "complex128"})


@dataclass(frozen=True, slots=True)
class ProductionCacheKey:
    particles: int
    sectors: tuple[int, ...]
    orders: tuple[tuple[int, int], ...]
    dtype: str
    source_sha256: str
    policy_sha256: str
    runtime_profile: str
    rank: int
    determinant_block: int
    carrier_block: int
    quadrature_block: int

    def __post_init__(self) -> None:
        _positive_integer("particles", self.particles)
        if self.particles < 2:
            raise ValueError("particles must be at least 2")
        if (
            not isinstance(self.sectors, tuple)
            or len(self.sectors) != 2
            or set(self.sectors) != {0, 2}
        ):
            raise ValueError("sectors must contain L=0 and L=2 exactly once")
        if not isinstance(self.orders, tuple) or len(self.orders) != len(self.sectors):
            raise ValueError("orders must contain one (alpha, beta) pair per sector")
        spec = SphereSpec(self.particles)
        for sector, order in zip(self.sectors, self.orders, strict=True):
            if (
                not isinstance(order, tuple)
                or len(order) != 2
                or any(
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value <= 0
                    for value in order
                )
            ):
                raise ValueError("orders must contain positive integer pairs")
            n_alpha, n_beta = order
            if n_alpha < 2 * spec.l_max + 1 or 2 * n_beta - 1 < spec.l_max + sector:
                raise ValueError("orders do not satisfy the exact projection bounds")
        if self.dtype not in _ALLOWED_DTYPES:
            raise ValueError("dtype must be float64 or complex128")
        _validate_sha256("source_sha256", self.source_sha256)
        _validate_sha256("policy_sha256", self.policy_sha256)
        if not isinstance(self.runtime_profile, str) or not self.runtime_profile:
            raise ValueError("runtime_profile must be a nonempty string")
        for name in (
            "rank",
            "determinant_block",
            "carrier_block",
            "quadrature_block",
        ):
            _positive_integer(name, getattr(self, name))

    @property
    def canonical_bytes(self) -> bytes:
        payload = {
            "carrier_block": self.carrier_block,
            "determinant_block": self.determinant_block,
            "dtype": self.dtype,
            "orders": [list(order) for order in self.orders],
            "particles": self.particles,
            "policy_sha256": self.policy_sha256,
            "quadrature_block": self.quadrature_block,
            "rank": self.rank,
            "runtime_profile": self.runtime_profile,
            "sectors": list(self.sectors),
            "source_sha256": self.source_sha256,
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class OrbitalGroups:
    positive: np.ndarray
    negative: np.ndarray
    zero: np.ndarray


@dataclass(frozen=True, slots=True)
class ProductionCache:
    key: ProductionCacheKey
    content_sha256: str
    determinant_blocks: np.ndarray
    determinant_masks: np.ndarray
    occupation_indices: np.ndarray
    orbital_groups: OrbitalGroups
    projection_grids: tuple[ProjectionGrid, ...]
    beta_rotations: tuple[np.ndarray, ...]
    alpha_phases: tuple[np.ndarray, ...]
    sector_tokens: np.ndarray
    carrier_masks: np.ndarray
    quadrature_masks: tuple[np.ndarray, ...]


@lru_cache(maxsize=32)
def build_production_cache(key: ProductionCacheKey) -> ProductionCache:
    """Build and reuse one immutable cache addressed by all scientific inputs."""

    spec = SphereSpec(key.particles)
    basis = DeterminantBasis.with_two_m(spec, 0)
    determinant_blocks, determinant_masks = _padded_blocks(
        np.asarray(basis.states, dtype=np.int64),
        key.determinant_block,
        fill=0,
    )
    occupations = np.full(
        (*determinant_blocks.shape, key.particles), -1, dtype=np.int64
    )
    for block_index, state_index in np.ndindex(determinant_blocks.shape):
        if determinant_masks[block_index, state_index]:
            state = int(determinant_blocks[block_index, state_index])
            occupied = [
                orbital
                for orbital in range(spec.orbital_count)
                if state & (1 << orbital)
            ]
            occupations[block_index, state_index] = occupied

    positive = np.asarray(
        [index for index, two_m in enumerate(spec.two_m_values) if two_m > 0],
        dtype=np.int64,
    )
    negative = np.asarray(
        [spec.two_m_values.index(-spec.two_m_values[index]) for index in positive],
        dtype=np.int64,
    )
    zero = np.asarray(
        [spec.two_m_values.index(0)] if spec.particles % 2 else [], dtype=np.int64
    )
    orbital_groups = OrbitalGroups(
        positive=_sealed(positive),
        negative=_sealed(negative),
        zero=_sealed(zero),
    )

    grids = tuple(
        _projection_grid(spec, sector, order)
        for sector, order in zip(key.sectors, key.orders, strict=True)
    )
    beta_rotations = tuple(_beta_rotations(grid.beta_nodes) for grid in grids)
    alpha_phases = tuple(_alpha_phases(grid.alpha_nodes) for grid in grids)
    sector_tokens = _sealed(
        np.asarray([[sector == 0, sector == 2] for sector in key.sectors], dtype=np.float64)
    )
    _, carrier_masks = _padded_blocks(
        np.arange(key.rank, dtype=np.int64), key.carrier_block, fill=0
    )
    quadrature_masks = tuple(
        _padded_blocks(
            np.arange(grid.n_alpha * grid.n_beta, dtype=np.int64),
            key.quadrature_block,
            fill=0,
        )[1]
        for grid in grids
    )

    arrays = (
        determinant_blocks,
        determinant_masks,
        occupations,
        orbital_groups.positive,
        orbital_groups.negative,
        orbital_groups.zero,
        sector_tokens,
        carrier_masks,
        *(
            array
            for group in (
                tuple(
                    array
                    for grid in grids
                    for array in (
                        grid.alpha_nodes,
                        grid.alpha_weights,
                        grid.beta_nodes,
                        grid.beta_weights,
                    )
                ),
                beta_rotations,
                alpha_phases,
                quadrature_masks,
            )
            for array in group
        ),
    )
    digest = hashlib.sha256()
    digest.update(key.canonical_bytes)
    for array in arrays:
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
        digest.update(array.tobytes(order="C"))

    return ProductionCache(
        key=key,
        content_sha256=digest.hexdigest(),
        determinant_blocks=_sealed(determinant_blocks),
        determinant_masks=_sealed(determinant_masks),
        occupation_indices=_sealed(occupations),
        orbital_groups=orbital_groups,
        projection_grids=grids,
        beta_rotations=beta_rotations,
        alpha_phases=alpha_phases,
        sector_tokens=sector_tokens,
        carrier_masks=_sealed(carrier_masks),
        quadrature_masks=quadrature_masks,
    )


def clear_production_cache() -> None:
    build_production_cache.cache_clear()


def _projection_grid(
    spec: SphereSpec, sector: int, order: tuple[int, int]
) -> ProjectionGrid:
    n_alpha, n_beta = order
    alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2.0 * pi / n_alpha)
    alpha_weights = np.full(
        n_alpha, 2.0 * pi / n_alpha, dtype=np.complex128
    )
    beta_nodes, beta_weights = np.polynomial.legendre.leggauss(n_beta)
    return ProjectionGrid(
        alpha_nodes=_sealed(alpha_nodes),
        alpha_weights=_sealed(alpha_weights),
        beta_nodes=_sealed(np.asarray(beta_nodes, dtype=np.float64)),
        beta_weights=_sealed(np.asarray(beta_weights, dtype=np.complex128)),
        target_l=sector,
        l_max=spec.l_max,
    )


def _beta_rotations(beta_nodes: np.ndarray) -> np.ndarray:
    beta = np.arccos(beta_nodes)
    cosine = np.cos(beta / 2.0)
    sine = np.sin(beta / 2.0)
    rotations = np.empty((beta_nodes.size, 2, 2), dtype=np.complex128)
    rotations[:, 0, 0] = cosine
    rotations[:, 0, 1] = sine
    rotations[:, 1, 0] = -sine
    rotations[:, 1, 1] = cosine
    return _sealed(rotations)


def _alpha_phases(alpha_nodes: np.ndarray) -> np.ndarray:
    half = alpha_nodes / 2.0
    return _sealed(
        np.stack((np.exp(-1j * half), np.exp(1j * half)), axis=-1).astype(
            np.complex128
        )
    )


def _padded_blocks(
    values: np.ndarray, block_size: int, *, fill: int
) -> tuple[np.ndarray, np.ndarray]:
    block_count = ceil(values.size / block_size)
    padded_size = block_count * block_size
    padded = np.full(padded_size, fill, dtype=values.dtype)
    padded[: values.size] = values
    masks = np.arange(padded_size) < values.size
    return (
        _sealed(padded.reshape(block_count, block_size)),
        _sealed(masks.reshape(block_count, block_size)),
    )


def _sealed(array: np.ndarray) -> np.ndarray:
    contiguous = np.ascontiguousarray(array)
    return np.frombuffer(contiguous.tobytes(), dtype=contiguous.dtype).reshape(
        contiguous.shape
    )


def _validate_sha256(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")


def _positive_integer(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive Python integer")
