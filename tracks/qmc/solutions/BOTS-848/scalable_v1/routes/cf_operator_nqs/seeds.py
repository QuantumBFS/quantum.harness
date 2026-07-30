"""Jain--Kamilla projected composite-fermion seeds on the sphere.

The physical flux is ``2Q=3(N-1)`` and the effective composite-fermion flux is
``2Q*=N-1``.  The ``n=0`` effective shell is filled.  A neutral primary is
formed by replacing one filled-shell orbital ``(Q*,m_h)`` with an ``n=1``
orbital ``(Q*+1,m_p)`` and coupling the particle and conjugate hole to ``L=2``.

For particle ``i`` define ``J_i=prod_{j!=i}(u_i v_j-v_i u_j)``.  With
``l_p=Q*+1``, ``a=l_p+m_p`` and ``b=l_p-m_p``, a normalized-gauge ``n=1``
monopole polynomial is proportional to

``sqrt(C(2l_p,a)) [b ubar u^a v^(b-1) - a vbar u^(a-1) v^b]``.

The Jain--Kamilla/Girvin--Jach rule projects ``ubar F`` and ``vbar F`` to a
common constant times ``dF/du`` and ``dF/dv``.  Applied to the orbital times
``J_i``, the derivatives of the bare monomials cancel exactly, leaving the
strictly holomorphic column implemented below.  The omitted projection factor
is common to every ``m_p`` and fixes only the overall normalization of the
entire ``L=2`` multiplet.  LLL orbitals use positive binomial square roots and
the particle--hole tensor uses the Condon--Shortley phase
``(-1)^(Q*-m_h) <l_p,m_p;Q*,-m_h|2,M>``.

Evaluation is pointwise: at most ``O(N)`` particle--hole determinants of size
``N`` occur for a component, while all Jastrow derivatives are constructed in
``O(N^2)`` work.  No many-body determinant basis is allocated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from ...contracts import SampleBatch
from .projected_density import _clebsch_gordan


_PROJECTION = "Jain-Kamilla"
_L2_COMPONENTS = tuple(range(-2, 3))


def _require_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


@dataclass(frozen=True)
class CFSeedCertificate:
    """Construction-level facts for the JK seed family."""

    strict_lll: bool
    antisymmetric: bool
    scalable: bool
    projection: str
    statement: str


@dataclass(frozen=True)
class _ParticleHoleTerm:
    particle_twice_m: int
    hole_twice_m: int
    hole_index: int
    coefficient: float

    @property
    def particle_m(self) -> float:
        return 0.5 * self.particle_twice_m

    @property
    def hole_m(self) -> float:
        return 0.5 * self.hole_twice_m


@dataclass(frozen=True)
class CFSeed:
    """Frozen coordinate-space handle for one member of a JK seed family."""

    label: str
    l: int
    m: int
    n_electrons: int
    two_q: int
    two_q_star: int
    projection: str
    normalization: str
    reduced_object_id: str
    _family: "JKCFSeedFamily" = field(repr=False, compare=False)

    def amplitude(self, config_batch: Any) -> complex | np.ndarray:
        """Evaluate the pointwise amplitude for one config or a config batch."""

        configs, is_single = self._family._validated_configs(config_batch)
        values = np.asarray(
            [self._family._amplitude_one(self.l, self.m, config) for config in configs],
            dtype=np.complex128,
        )
        if is_single:
            return complex(values[0])
        return values

    def logpsi(self, config_batch: Any) -> np.ndarray:
        """Return ``log(abs(psi))+i arg(psi)`` without phase-branch NaNs."""

        configs, is_single = self._family._validated_configs(config_batch)
        result = np.asarray(
            [
                self._family._log_amplitude_one(self.l, self.m, config)
                for config in configs
            ],
            dtype=np.complex128,
        )
        if is_single:
            return np.asarray(result[0])
        return result

    def sample(self, n_samples: int, seed: int) -> SampleBatch:
        raise NotImplementedError("coordinate sampling is supplied in Task 5")

    def local_energy(self, config_batch: Any) -> np.ndarray:
        raise NotImplementedError("local energy is supplied in Task 5")

    def local_l2(self, config_batch: Any) -> np.ndarray:
        raise NotImplementedError("local L2 is supplied in Task 5")


@dataclass(frozen=True)
class JKCFSeedFamily:
    """Filled-shell Laughlin seed and one shared JK-projected ``L=2`` exciton."""

    n_electrons: int
    two_q: int
    certificate: CFSeedCertificate = field(init=False)
    _ground: CFSeed = field(init=False, repr=False, compare=False)
    _tower: Mapping[int, CFSeed] = field(init=False, repr=False, compare=False)
    _couplings: Mapping[int, tuple[_ParticleHoleTerm, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        n_electrons = _require_integer("n_electrons", self.n_electrons)
        two_q = _require_integer("two_q", self.two_q)
        if n_electrons < 2:
            raise ValueError("n_electrons must be at least 2")
        expected_two_q = 3 * (n_electrons - 1)
        if two_q != expected_two_q:
            raise ValueError("two_q must equal 3*(n_electrons-1) at nu=1/3")

        object.__setattr__(self, "n_electrons", n_electrons)
        object.__setattr__(self, "two_q", two_q)
        certificate = CFSeedCertificate(
            strict_lll=True,
            antisymmetric=True,
            scalable=True,
            projection=_PROJECTION,
            statement=(
                "Explicit Jain-Kamilla/Girvin-Jach orbital projection produces "
                "holomorphic fixed-flux determinants; pointwise evaluation uses "
                "no full-basis allocation and no direct-projection fallback."
            ),
        )
        object.__setattr__(self, "certificate", certificate)

        common = {
            "n_electrons": n_electrons,
            "two_q": two_q,
            "two_q_star": n_electrons - 1,
            "projection": _PROJECTION,
            "_family": self,
        }
        ground = CFSeed(
            label="jk-cf-laughlin-l0-m0",
            l=0,
            m=0,
            normalization="unit coefficient for product_(i<j)(u_i v_j-v_i u_j)^3",
            reduced_object_id=f"jk-cf-ground:N={n_electrons}:2Q={two_q}",
            **common,
        )
        reduced_id = f"jk-cf-0to1-primary:N={n_electrons}:2Q={two_q}:L=2"
        tower = MappingProxyType(
            {
                m: CFSeed(
                    label=f"jk-cf-primary-l2-m{m:+d}",
                    l=2,
                    m=m,
                    normalization=(
                        "Condon-Shortley normalized monopole orbitals; one common "
                        "Girvin-Jach projection factor omitted"
                    ),
                    reduced_object_id=reduced_id,
                    **common,
                )
                for m in _L2_COMPONENTS
            }
        )
        couplings = MappingProxyType(
            {m: self._build_couplings(m) for m in _L2_COMPONENTS}
        )
        object.__setattr__(self, "_ground", ground)
        object.__setattr__(self, "_tower", tower)
        object.__setattr__(self, "_couplings", couplings)

    @property
    def two_q_star(self) -> int:
        return self.n_electrons - 1

    @property
    def hole_l(self) -> float:
        return 0.5 * self.two_q_star

    @property
    def particle_l(self) -> float:
        return self.hole_l + 1.0

    def ground_state(self) -> CFSeed:
        return self._ground

    def reduced_l2_state(self) -> CFSeed:
        """Return the ``M=0`` handle of the one shared reduced ``L=2`` object."""

        return self._tower[0]

    def generate_multiplet(self) -> Mapping[int, CFSeed]:
        return self._tower

    def state(self, l: int, m: int) -> CFSeed:
        checked_l = _require_integer("l", l)
        checked_m = _require_integer("m", m)
        if checked_l == 0:
            if checked_m != 0:
                raise ValueError("m must be zero for the L=0 seed")
            return self._ground
        if checked_l == 2:
            if checked_m not in self._tower:
                raise ValueError("m must satisfy -2 <= m <= 2 for the L=2 seed")
            return self._tower[checked_m]
        raise ValueError("only (L,M)=(0,0) and the complete L=2 tower are supported")

    def _build_couplings(self, total_m: int) -> tuple[_ParticleHoleTerm, ...]:
        terms: list[_ParticleHoleTerm] = []
        twice_hole_l = self.two_q_star
        twice_particle_l = twice_hole_l + 2
        for particle_twice_m in range(
            -twice_particle_l, twice_particle_l + 1, 2
        ):
            for hole_index, hole_twice_m in enumerate(
                range(-twice_hole_l, twice_hole_l + 1, 2)
            ):
                if particle_twice_m - hole_twice_m != 2 * total_m:
                    continue
                particle_m = 0.5 * particle_twice_m
                hole_m = 0.5 * hole_twice_m
                phase = (-1) ** int(round(self.hole_l - hole_m))
                coefficient = phase * _clebsch_gordan(
                    self.particle_l,
                    particle_m,
                    self.hole_l,
                    -hole_m,
                    2.0,
                    float(total_m),
                )
                if coefficient != 0.0:
                    terms.append(
                        _ParticleHoleTerm(
                            particle_twice_m=particle_twice_m,
                            hole_twice_m=hole_twice_m,
                            hole_index=hole_index,
                            coefficient=coefficient,
                        )
                    )
        if not terms:
            raise ValueError(f"empty L=2 particle-hole coupling for M={total_m}")
        return tuple(terms)

    def _validated_configs(self, config_batch: Any) -> tuple[np.ndarray, bool]:
        raw = np.asarray(config_batch)
        if raw.dtype.kind not in "biufc":
            raise TypeError("spinor configs must contain numeric values")
        configs = np.asarray(raw, dtype=np.complex128)
        if configs.ndim == 2:
            is_single = True
            configs = configs[np.newaxis, ...]
        elif configs.ndim == 3:
            is_single = False
        else:
            raise ValueError("spinor config shape must be (N,2) or (batch,N,2)")
        if configs.shape[-1] != 2:
            raise ValueError("spinor config shape must end in 2")
        if configs.shape[-2] != self.n_electrons:
            raise ValueError("spinor config n_electrons does not match the family")
        if not np.all(np.isfinite(configs)):
            raise ValueError("spinor configs must be finite")
        norms = np.linalg.norm(configs, axis=-1)
        if not np.allclose(norms, 1.0, rtol=0.0, atol=2.0e-12):
            raise ValueError("each sphere spinor must be normalized")
        return configs, is_single

    def _amplitude_one(self, l: int, m: int, spinors: np.ndarray) -> complex:
        if any(value == 0.0 for value in _pair_factors(spinors)):
            return 0.0 + 0.0j
        state = self.state(l=l, m=m)
        return complex(
            polynomial_seed_amplitude(
                state,
                spinors,
                lambda matrix: np.linalg.det(
                    np.asarray(matrix, dtype=np.complex128)
                ),
            )
        )

    def _log_amplitude_one(self, l: int, m: int, spinors: np.ndarray) -> complex:
        """Evaluate a stable complex logarithm without forming tiny determinants."""

        pair_factors = _pair_factors(spinors)
        if any(value == 0.0 for value in pair_factors):
            return complex(-math.inf, 0.0)
        if l == 0:
            log_magnitude = 3.0 * sum(math.log(abs(value)) for value in pair_factors)
            phase = 3.0 * sum(float(np.angle(value)) for value in pair_factors)
            wrapped_phase = math.atan2(math.sin(phase), math.cos(phase))
            return complex(log_magnitude, wrapped_phase)

        n0, du_jastrow, dv_jastrow = _projected_orbitals(spinors)
        log_terms: list[tuple[float, float]] = []
        for term in self._couplings[m]:
            matrix = n0.copy()
            matrix[:, term.hole_index] = _projected_n1_column(
                spinors,
                du_jastrow,
                dv_jastrow,
                twice_l=int(round(2.0 * self.particle_l)),
                twice_m=term.particle_twice_m,
            )
            determinant_phase, determinant_logabs = np.linalg.slogdet(matrix)
            if determinant_phase == 0.0 or term.coefficient == 0.0:
                continue
            coefficient_phase = 0.0 if term.coefficient > 0.0 else math.pi
            log_terms.append(
                (
                    math.log(abs(term.coefficient)) + float(determinant_logabs),
                    coefficient_phase + float(np.angle(determinant_phase)),
                )
            )
        if not log_terms:
            return complex(-math.inf, 0.0)
        common_scale = max(log_magnitude for log_magnitude, _ in log_terms)
        scaled_sum = sum(
            math.exp(log_magnitude - common_scale) * np.exp(1j * phase)
            for log_magnitude, phase in log_terms
        )
        if scaled_sum == 0.0:
            return complex(-math.inf, 0.0)
        return complex(
            common_scale + math.log(abs(scaled_sum)), float(np.angle(scaled_sum))
        )


def _ring_dtype(spinors: Sequence[Sequence[object]]) -> type[object] | np.dtype:
    raw = np.asarray(spinors)
    return object if raw.dtype.kind == "O" else np.dtype(np.complex128)


def _pair_factors(spinors: Sequence[Sequence[object]]) -> tuple[object, ...]:
    return tuple(
        spinors[i][0] * spinors[j][1] - spinors[i][1] * spinors[j][0]
        for i in range(len(spinors))
        for j in range(i + 1, len(spinors))
    )


def _jastrow_and_derivatives(
    spinors: Sequence[Sequence[object]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``J_i``, ``dJ_i/du_i`` and ``dJ_i/dv_i`` without division."""

    n_electrons = len(spinors)
    dtype = _ring_dtype(spinors)
    jastrow = np.empty(n_electrons, dtype=dtype)
    derivative_u = np.empty(n_electrons, dtype=dtype)
    derivative_v = np.empty(n_electrons, dtype=dtype)
    for particle in range(n_electrons):
        others = [other for other in range(n_electrons) if other != particle]
        factors = np.asarray(
            [
                spinors[particle][0] * spinors[other][1]
                - spinors[particle][1] * spinors[other][0]
                for other in others
            ],
            dtype=dtype,
        )
        prefix = np.ones(len(factors) + 1, dtype=dtype)
        suffix = np.ones(len(factors) + 1, dtype=dtype)
        for index, factor in enumerate(factors):
            prefix[index + 1] = prefix[index] * factor
        for index in range(len(factors) - 1, -1, -1):
            suffix[index] = factors[index] * suffix[index + 1]
        products_excluding = prefix[:-1] * suffix[1:]
        jastrow[particle] = prefix[-1]
        derivative_u[particle] = sum(
            spinors[other][1] * product
            for other, product in zip(others, products_excluding, strict=True)
        )
        derivative_v[particle] = sum(
            -spinors[other][0] * product
            for other, product in zip(others, products_excluding, strict=True)
        )
    return jastrow, derivative_u, derivative_v


def _projected_orbitals(
    spinors: Sequence[Sequence[object]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_electrons = len(spinors)
    dtype = _ring_dtype(spinors)
    checked = np.asarray(spinors, dtype=dtype)
    jastrow, derivative_u, derivative_v = _jastrow_and_derivatives(spinors)
    two_q_star = n_electrons - 1
    n0 = np.empty((n_electrons, n_electrons), dtype=dtype)
    u = checked[:, 0]
    v = checked[:, 1]
    for orbital in range(n_electrons):
        n0[:, orbital] = (
            math.sqrt(math.comb(two_q_star, orbital))
            * u**orbital
            * v ** (two_q_star - orbital)
            * jastrow
        )
    return n0, derivative_u, derivative_v


def _projected_n1_column(
    spinors: Sequence[Sequence[object]],
    derivative_u: np.ndarray,
    derivative_v: np.ndarray,
    *,
    twice_l: int,
    twice_m: int,
) -> np.ndarray:
    dtype = _ring_dtype(spinors)
    checked = np.asarray(spinors, dtype=dtype)
    a = (twice_l + twice_m) // 2
    b = (twice_l - twice_m) // 2
    normalization = math.sqrt(math.comb(twice_l, a))
    u = checked[:, 0]
    v = checked[:, 1]
    first = (
        b * u**a * v ** (b - 1) * derivative_u
        if b > 0
        else np.zeros(len(spinors), dtype=dtype)
    )
    second = (
        a * u ** (a - 1) * v**b * derivative_v
        if a > 0
        else np.zeros(len(spinors), dtype=dtype)
    )
    return normalization * (first - second)


def polynomial_seed_amplitude(
    state: CFSeed,
    spinors: Sequence[Sequence[object]],
    determinant: Callable[[Sequence[Sequence[object]]], object],
) -> object:
    """Evaluate the raw division-free JK polynomial over a scalar ring."""

    if not isinstance(state, CFSeed):
        raise TypeError("state must be a CFSeed")
    if len(spinors) != state.n_electrons or any(len(row) != 2 for row in spinors):
        raise ValueError("spinor shape must be (n_electrons, 2)")
    pair_factors = _pair_factors(spinors)
    if state.l == 0:
        amplitude: object = 1.0
        for factor in pair_factors:
            amplitude = amplitude * factor**3
        return amplitude

    n0, derivative_u, derivative_v = _projected_orbitals(spinors)
    total: object = 0.0
    family = state._family
    for term in family._couplings[state.m]:
        matrix = n0.copy()
        matrix[:, term.hole_index] = _projected_n1_column(
            spinors,
            derivative_u,
            derivative_v,
            twice_l=int(round(2.0 * family.particle_l)),
            twice_m=term.particle_twice_m,
        )
        total = total + term.coefficient * determinant(matrix)
    return total


def _validated_tower(tower: Mapping[int, CFSeed]) -> JKCFSeedFamily:
    if set(tower) != set(_L2_COMPONENTS):
        raise ValueError("complete L=2 multiplet is required")
    states = tuple(tower[m] for m in _L2_COMPONENTS)
    if not all(isinstance(state, CFSeed) for state in states):
        raise TypeError("tower values must be CFSeed handles")
    if any((state.l, state.m) != (2, m) for state, m in zip(states, _L2_COMPONENTS)):
        raise ValueError("tower L/M labels are inconsistent")
    family = states[0]._family
    if any(state._family is not family for state in states):
        raise ValueError("tower must come from one shared reduced multiplet")
    return family


def _symmetric_power_rotation(rotation: np.ndarray, ell: int) -> np.ndarray:
    components = tuple(range(-ell, ell + 1))
    result = np.zeros((2 * ell + 1, 2 * ell + 1), dtype=np.complex128)
    for row, m in enumerate(components):
        a = ell + m
        b = ell - m
        source_normalization = math.sqrt(math.comb(2 * ell, a))
        for first_u in range(a + 1):
            for second_u in range(b + 1):
                target_m = first_u + second_u - ell
                column = target_m + ell
                coefficient = (
                    math.comb(a, first_u)
                    * math.comb(b, second_u)
                    * rotation[0, 0] ** first_u
                    * rotation[0, 1] ** (a - first_u)
                    * rotation[1, 0] ** second_u
                    * rotation[1, 1] ** (b - second_u)
                )
                target_normalization = math.sqrt(
                    math.comb(2 * ell, ell + target_m)
                )
                result[row, column] += (
                    source_normalization / target_normalization * coefficient
                )
    return result


def finite_rotation_residual(
    tower: Mapping[int, CFSeed], *, seed: int = 3848, probes: int = 4
) -> float:
    """Test finite spin-2 covariance without raw-amplitude underflow.

    Each comparison uses one real log-magnitude shift shared by the unrotated
    and rotated five-component vectors.  A probe that is identically zero on
    both sides is not symmetry evidence and is resampled with a bounded retry
    count.
    """

    family = _validated_tower(tower)
    checked_seed = _require_integer("seed", seed)
    checked_probes = _require_integer("probes", probes)
    if checked_probes <= 0:
        raise ValueError("probes must be positive")
    rng = np.random.default_rng(checked_seed)
    maximum = 0.0
    valid_probes = 0
    attempts = 0
    maximum_attempts = max(8, 8 * checked_probes)
    while valid_probes < checked_probes and attempts < maximum_attempts:
        attempts += 1
        spinors = rng.normal(size=(family.n_electrons, 2)) + 1j * rng.normal(
            size=(family.n_electrons, 2)
        )
        spinors /= np.linalg.norm(spinors, axis=1, keepdims=True)
        quaternion = rng.normal(size=4)
        quaternion /= np.linalg.norm(quaternion)
        scalar, x, y, z = quaternion
        rotation = np.asarray(
            [
                [scalar - 1j * z, -y - 1j * x],
                [y - 1j * x, scalar + 1j * z],
            ],
            dtype=np.complex128,
        )
        rotated_spinors = np.einsum("ab,nb->na", rotation, spinors)
        before_logs = np.asarray(
            [complex(tower[m].logpsi(spinors)) for m in _L2_COMPONENTS],
            dtype=np.complex128,
        )
        after_logs = np.asarray(
            [complex(tower[m].logpsi(rotated_spinors)) for m in _L2_COMPONENTS],
            dtype=np.complex128,
        )
        if np.any(np.isnan(before_logs)) or np.any(np.isnan(after_logs)):
            raise FloatingPointError("rotation probe produced a NaN log amplitude")
        if np.any(np.isposinf(before_logs.real)) or np.any(
            np.isposinf(after_logs.real)
        ):
            raise FloatingPointError("rotation probe produced an infinite amplitude")
        before_finite = np.isfinite(before_logs.real)
        after_finite = np.isfinite(after_logs.real)
        finite_real_logs = np.concatenate(
            (before_logs.real[before_finite], after_logs.real[after_finite])
        )
        if finite_real_logs.size == 0:
            continue
        shared_shift = float(np.max(finite_real_logs))
        before = np.zeros(len(_L2_COMPONENTS), dtype=np.complex128)
        after = np.zeros(len(_L2_COMPONENTS), dtype=np.complex128)
        before[before_finite] = np.exp(before_logs[before_finite] - shared_shift)
        after[after_finite] = np.exp(after_logs[after_finite] - shared_shift)
        expected = _symmetric_power_rotation(rotation, ell=2) @ before
        scale = max(np.linalg.norm(after), np.linalg.norm(expected))
        if scale == 0.0:
            continue
        maximum = max(maximum, float(np.linalg.norm(after - expected) / scale))
        valid_probes += 1
    if valid_probes < checked_probes:
        raise RuntimeError(
            "could not obtain a valid nonzero rotation probe within the bounded "
            f"retry budget ({valid_probes}/{checked_probes})"
        )
    return maximum


def tower_ladder_residual(tower: Mapping[int, CFSeed]) -> float:
    """Check the particle--hole CG tensor against the exact total ``L_+`` action."""

    family = _validated_tower(tower)
    maximum = 0.0
    for total_m in range(-2, 2):
        raised: dict[tuple[int, int], float] = {}
        for term in family._couplings[total_m]:
            particle_m = term.particle_m
            hole_m = term.hole_m
            if particle_m < family.particle_l:
                target = (term.particle_twice_m + 2, term.hole_twice_m)
                raised[target] = raised.get(target, 0.0) + term.coefficient * math.sqrt(
                    (family.particle_l - particle_m)
                    * (family.particle_l + particle_m + 1.0)
                )
            if hole_m > -family.hole_l:
                target = (term.particle_twice_m, term.hole_twice_m - 2)
                raised[target] = raised.get(target, 0.0) - term.coefficient * math.sqrt(
                    (family.hole_l + hole_m)
                    * (family.hole_l - hole_m + 1.0)
                )
        factor = math.sqrt((2 - total_m) * (2 + total_m + 1))
        expected = {
            (term.particle_twice_m, term.hole_twice_m): factor * term.coefficient
            for term in family._couplings[total_m + 1]
        }
        keys = set(raised) | set(expected)
        difference = np.asarray(
            [raised.get(key, 0.0) - expected.get(key, 0.0) for key in keys]
        )
        reference = np.asarray([expected.get(key, 0.0) for key in keys])
        scale = max(np.linalg.norm(reference), np.finfo(float).tiny)
        maximum = max(maximum, float(np.linalg.norm(difference) / scale))
    return maximum


__all__ = [
    "CFSeed",
    "CFSeedCertificate",
    "JKCFSeedFamily",
    "finite_rotation_residual",
    "polynomial_seed_amplitude",
    "tower_ladder_residual",
]
