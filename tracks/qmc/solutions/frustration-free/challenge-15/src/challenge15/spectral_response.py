"""Exact rank-two chiral spectra from stored angular-momentum eigensystems."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal, Mapping

import numpy as np
from scipy import sparse

from challenge15.angular import verify_ladder_multiplet
from challenge15.chiral_source import Helicity, lhyr_pair_reduced_source
from challenge15.fermions import DeterminantBasis
from challenge15.nqs_bridge import DeterminantState, mixed_transition_amplitude
from challenge15.oracle import (
    OracleResult,
    oracle_cache_payload,
    oracle_from_cache_payload,
    solve_required_target_sectors_sparse,
    solve_target_sectors,
)
from challenge15.response_operator import (
    ResponseFamily,
    adjoint_residual as response_adjoint_residual,
    build_response_family,
    monopole_reversal_residual,
    tensor_commutator_residuals,
)
from challenge15.spec import SphereSpec


_TENSOR_COMMUTATOR_TOLERANCE = 1e-10
_ADJOINT_TOLERANCE = 1e-12
_EIGENPAIR_TOLERANCE = 1e-10
_DEGENERACY_ABSOLUTE_TOLERANCE_E_C = 1e-10
_DEGENERACY_RELATIVE_TOLERANCE = 1e-9
_RECOVERED_SUM_RULE_FRACTION_MIN = 0.99
_MONOPOLE_REVERSAL_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class PoleGroup:
    energy: float
    degeneracy: int
    member_indices: tuple[int, ...]
    member_weights: tuple[float, ...]
    weight: float


@dataclass(frozen=True, slots=True)
class ChannelSpectrum:
    helicity: Helicity
    component_weights: Mapping[int, float]
    poles: tuple[PoleGroup, ...]
    total_weight: float
    direct_sum_weight: float
    recovered_fraction: float
    lowest_weight: float
    pole_fraction: float


@dataclass(frozen=True, slots=True)
class ChiralSpectrum:
    particles: int
    orientation: Literal[-1, 1]
    ground_energy: float
    channels: Mapping[Helicity, ChannelSpectrum]
    delta_weight: float
    contrast: float | None
    contrast_floor: float
    tensor_commutator_residual_max: float
    adjoint_residual: float
    reversal_residual_max: float
    eigenpair_residual_max: float
    initial_state_kind: str | None = None
    initial_coefficient_sha256: str | None = None
    estimator_scope: str | None = None
    oracle_cache_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "channels", MappingProxyType(dict(self.channels))
        )

    def to_payload(self) -> dict[str, object]:
        """Return the deterministic strict-JSON exact-response payload."""

        channels = {}
        for helicity in ("+", "-"):
            channel = self.channels[helicity]
            normalized_fractions = tuple(
                (
                    pole.weight / channel.total_weight
                    if channel.total_weight > 0.0
                    else 0.0
                )
                for pole in channel.poles
            )
            channels[helicity] = {
                "helicity": helicity,
                "raw_total_weight_E_C2": channel.total_weight,
                "raw_lowest_pole_weight_E_C2": channel.lowest_weight,
                "lowest_pole_fraction": channel.pole_fraction,
                "poles": [
                    {
                        "energy_E_C": pole.energy,
                        "degeneracy": pole.degeneracy,
                        "member_indices": list(pole.member_indices),
                        "member_weights": list(pole.member_weights),
                        "raw_weight_E_C2": pole.weight,
                        "normalized_fraction": normalized_fraction,
                    }
                    for pole, normalized_fraction in zip(
                        channel.poles, normalized_fractions, strict=True
                    )
                ],
                "component_weights_E_C2": {
                    str(component): weight
                    for component, weight in channel.component_weights.items()
                },
                "sum_rule": {
                    "spectral_weight_E_C2": channel.total_weight,
                    "direct_sum_weight_E_C2": channel.direct_sum_weight,
                    "recovered_fraction": channel.recovered_fraction,
                    "minimum_recovered_fraction": (
                        _RECOVERED_SUM_RULE_FRACTION_MIN
                    ),
                    "passed": (
                        channel.recovered_fraction
                        >= _RECOVERED_SUM_RULE_FRACTION_MIN
                    ),
                },
            }

        reversal_passed = (
            self.reversal_residual_max <= _MONOPOLE_REVERSAL_TOLERANCE
        )
        payload = {
            "schema": "challenge15.chiral-spectrum.v1",
            "particles": self.particles,
            "orientation": self.orientation,
            "units": {
                "energies": "E_C",
                "raw_weights": "E_C^2",
                "pole_fractions": "dimensionless",
            },
            "source_normalization": (
                "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6"
            ),
            "ground_energy_E_C": self.ground_energy,
            "channels": channels,
            "delta_weight_E_C2": self.delta_weight,
            "contrast": self.contrast,
            "chirality_resolved": (
                self.contrast is not None
                and self.delta_weight > 0.0
                and reversal_passed
            ),
            "tolerances": {
                "tensor_commutator": _TENSOR_COMMUTATOR_TOLERANCE,
                "adjoint": _ADJOINT_TOLERANCE,
                "eigenpair": _EIGENPAIR_TOLERANCE,
                "degeneracy_absolute_E_C": (
                    _DEGENERACY_ABSOLUTE_TOLERANCE_E_C
                ),
                "degeneracy_relative": _DEGENERACY_RELATIVE_TOLERANCE,
                "contrast_denominator_floor": self.contrast_floor,
                "recovered_sum_rule_fraction_min": (
                    _RECOVERED_SUM_RULE_FRACTION_MIN
                ),
                "monopole_reversal": _MONOPOLE_REVERSAL_TOLERANCE,
            },
            "diagnostics": {
                "tensor_commutator": {
                    "residual_max": self.tensor_commutator_residual_max,
                    "tolerance": _TENSOR_COMMUTATOR_TOLERANCE,
                    "passed": (
                        self.tensor_commutator_residual_max
                        <= _TENSOR_COMMUTATOR_TOLERANCE
                    ),
                },
                "adjoint": {
                    "residual": self.adjoint_residual,
                    "tolerance": _ADJOINT_TOLERANCE,
                    "passed": self.adjoint_residual <= _ADJOINT_TOLERANCE,
                },
                "monopole_reversal": {
                    "residual_max": self.reversal_residual_max,
                    "tolerance": _MONOPOLE_REVERSAL_TOLERANCE,
                    "passed": reversal_passed,
                },
                "sum_rules_passed": all(
                    channel.recovered_fraction
                    >= _RECOVERED_SUM_RULE_FRACTION_MIN
                    for channel in self.channels.values()
                ),
            },
        }
        if self.initial_state_kind is not None:
            payload["initial_state_kind"] = self.initial_state_kind
        if self.initial_coefficient_sha256 is not None:
            payload["initial_coefficient_sha256"] = (
                self.initial_coefficient_sha256
            )
        if self.estimator_scope is not None:
            payload["estimator_scope"] = self.estimator_scope
        return payload


def group_degenerate_poles(
    energies: np.ndarray,
    weights: np.ndarray,
    *,
    atol: float = 1e-10,
    rtol: float = 1e-9,
) -> tuple[PoleGroup, ...]:
    """Group nearby energies using a first-energy-anchored transitive policy."""

    energy_values = np.asarray(energies, dtype=np.float64)
    weight_values = np.asarray(weights, dtype=np.float64)
    if energy_values.ndim != 1 or weight_values.ndim != 1:
        raise ValueError("energies and weights must be one-dimensional")
    if energy_values.shape != weight_values.shape:
        raise ValueError("energies and weights must have equal shape")
    if not np.all(np.isfinite(energy_values)):
        raise ValueError("energies must be finite")
    if not np.all(np.isfinite(weight_values)) or np.any(weight_values < 0.0):
        raise ValueError("weights must be finite and nonnegative")
    if (
        not np.isfinite(atol)
        or not np.isfinite(rtol)
        or atol < 0.0
        or rtol < 0.0
    ):
        raise ValueError("grouping tolerances must be finite and nonnegative")
    if energy_values.size == 0:
        return ()

    original_indices = np.arange(energy_values.size, dtype=np.int64)
    order = np.lexsort((original_indices, energy_values))
    groups: list[PoleGroup] = []
    members: list[int] = []
    group_first = 0.0

    def finish_group() -> None:
        indices = tuple(members)
        with np.errstate(over="ignore", invalid="ignore"):
            group_energy = float(np.mean(energy_values[list(indices)]))
            group_weight = float(np.sum(weight_values[list(indices)]))
        if not np.isfinite(group_energy) or not np.isfinite(group_weight):
            raise ValueError("grouped pole outputs must be finite")
        groups.append(
            PoleGroup(
                energy=group_energy,
                degeneracy=len(indices),
                member_indices=indices,
                member_weights=tuple(float(weight_values[index]) for index in indices),
                weight=group_weight,
            )
        )

    for original_index in order:
        index = int(original_index)
        energy = float(energy_values[index])
        if not members:
            members = [index]
            group_first = energy
            continue
        tolerance = atol + rtol * max(abs(energy), abs(group_first))
        if abs(energy - group_first) > tolerance:
            finish_group()
            members = [index]
            group_first = energy
        else:
            members.append(index)
    finish_group()
    return tuple(groups)


def exact_chiral_spectrum(
    oracle: OracleResult,
    families: Mapping[Helicity, ResponseFamily],
    *,
    initial_sector_coefficients: np.ndarray | None = None,
    contrast_floor: float = 1e-14,
) -> ChiralSpectrum:
    """Contract all five tensor components with every stored L=2 eigenstate."""

    ground_sector = oracle.exact_sector(0)
    raw_coefficients = (
        ground_sector.eigenvectors[:, 0]
        if initial_sector_coefficients is None
        else initial_sector_coefficients
    )
    coefficients = _normalize_coefficients(
        raw_coefficients,
        expected_shape=(ground_sector.isometry.shape[1],),
    )

    ground = np.asarray(
        ground_sector.isometry @ coefficients, dtype=np.complex128
    )
    ground_energy = float(ground_sector.eigenvalues[0])
    if not np.all(np.isfinite(ground)) or not np.isfinite(ground_energy):
        raise ArithmeticError("ground state and energy must remain finite")
    initial = DeterminantState(
        basis=DeterminantBasis.with_two_m(oracle.spec, 0),
        coefficients=ground,
    )
    return _determinant_chiral_spectrum(
        oracle,
        families,
        initial,
        contrast_floor=contrast_floor,
    )


def nqs_mixed_chiral_spectrum(
    oracle: OracleResult,
    families: Mapping[Helicity, ResponseFamily],
    initial: DeterminantState,
    *,
    contrast_floor: float = 1e-14,
) -> ChiralSpectrum:
    """Use exact ED L=2 finals with a determinant-space NQS initial state.

    This is an exact finite-Hilbert-space contraction, not an unbiased
    coordinate-Monte-Carlo estimator.
    """

    if not isinstance(initial, DeterminantState):
        raise TypeError("initial must be a DeterminantState")
    expected_basis = DeterminantBasis.with_two_m(oracle.spec, 0)
    if initial.basis != expected_basis:
        raise ValueError("initial determinant basis must match the oracle M=0 sector")
    coefficient_sha256 = hashlib.sha256(
        initial.coefficients.tobytes(order="C")
    ).hexdigest()
    return _determinant_chiral_spectrum(
        oracle,
        families,
        initial,
        contrast_floor=contrast_floor,
        initial_state_kind="nqs-determinant",
        initial_coefficient_sha256=coefficient_sha256,
        estimator_scope=(
            "exact-finite-Hilbert contraction with exact-ED L=2 finals; "
            "not an unbiased coordinate-Monte-Carlo estimator"
        ),
    )


def _determinant_chiral_spectrum(
    oracle: OracleResult,
    families: Mapping[Helicity, ResponseFamily],
    initial: DeterminantState,
    *,
    contrast_floor: float,
    initial_state_kind: str | None = None,
    initial_coefficient_sha256: str | None = None,
    estimator_scope: str | None = None,
) -> ChiralSpectrum:
    """Run the shared exact-final determinant spectral engine."""

    if not np.isfinite(contrast_floor) or contrast_floor <= 0.0:
        raise ValueError("contrast_floor must be finite and positive")
    if set(families) != {"+", "-"}:
        raise ValueError("families must contain exactly '+' and '-'")
    tensor_residual, adjoint, reversal_residual = validate_response_families(
        oracle.spec, families
    )

    orientations = set()
    for helicity in ("+", "-"):
        family = families[helicity]
        if family.spec != oracle.spec:
            raise ValueError("response family and oracle SphereSpec must match")
        if family.helicity != helicity:
            raise ValueError("response family key must match its helicity")
        orientations.add(family.orientation)
    if len(orientations) != 1:
        raise ValueError("response families must have equal orientation")
    orientation = orientations.pop()

    expected_basis = DeterminantBasis.with_two_m(oracle.spec, 0)
    if initial.basis != expected_basis:
        raise ValueError("initial determinant basis must match the oracle M=0 sector")
    # Validate all state invariants before any spectral work.
    identity = sparse.identity(initial.basis.dimension, format="csr")
    mixed_transition_amplitude(
        initial.coefficients,
        identity,
        initial,
    )

    ground_energy = float(oracle.exact_sector(0).eigenvalues[0])
    if not np.isfinite(ground_energy):
        raise ArithmeticError("ground energy must remain finite")
    excited_sector = oracle.exact_sector(2)
    ladder = verify_ladder_multiplet(
        DeterminantBasis.with_two_m(oracle.spec, 0),
        target_l=2,
        isometry=excited_sector.isometry,
    )
    l2_states = {
        component_m: np.asarray(
            ladder["vectors"][2 * component_m] @ excited_sector.eigenvectors,
            dtype=np.complex128,
        )
        for component_m in range(-2, 3)
    }
    if any(not np.all(np.isfinite(states)) for states in l2_states.values()):
        raise ArithmeticError("L=2 determinant eigenstates must remain finite")

    channels: dict[Helicity, ChannelSpectrum] = {}
    pole_energies = excited_sector.eigenvalues - ground_energy
    if not np.all(np.isfinite(pole_energies)):
        raise ArithmeticError("pole energies must remain finite")
    for helicity in ("+", "-"):
        family = families[helicity]
        state_weights = np.zeros(
            excited_sector.eigenvalues.shape, dtype=np.float64
        )
        direct_sum_weight = 0.0
        component_direct_weights: dict[int, float] = {}
        sources = []
        for component_m in range(-2, 3):
            source = np.asarray(
                family.components[component_m] @ initial.coefficients,
                dtype=np.complex128,
            )
            sources.append(source)
            if not np.all(np.isfinite(source)):
                raise ArithmeticError("source vectors must remain finite")
            amplitudes = np.asarray(
                [
                    mixed_transition_amplitude(
                        l2_states[component_m][:, state_index],
                        family.components[component_m],
                        initial,
                    )
                    for state_index in range(
                        excited_sector.eigenvalues.size
                    )
                ],
                dtype=np.complex128,
            )
            if not np.all(np.isfinite(amplitudes)):
                raise ArithmeticError("spectral amplitudes must remain finite")
            with np.errstate(over="ignore", invalid="ignore"):
                component_weights = np.abs(amplitudes) ** 2
                component_direct = float(np.vdot(source, source).real)
                component_direct_weights[component_m] = component_direct
                state_weights += component_weights
                direct_sum_weight += component_direct
            if (
                not np.all(np.isfinite(component_weights))
                or not np.all(np.isfinite(state_weights))
                or not np.isfinite(component_direct)
                or not np.isfinite(direct_sum_weight)
            ):
                raise ArithmeticError("spectral weights must remain finite")

        poles = group_degenerate_poles(pole_energies, state_weights)
        total_weight = float(np.sum(state_weights))
        if not np.isfinite(total_weight):
            raise ArithmeticError("total spectral weight must remain finite")
        identically_zero_source = all(
            not np.any(source != 0.0) for source in sources
        )
        if direct_sum_weight <= 0.0:
            if not identically_zero_source:
                raise ArithmeticError(
                    "nonzero source has nonpositive direct sum weight"
                )
            recovered_fraction = 1.0
        else:
            recovered_fraction = total_weight / direct_sum_weight

        lowest_weight = poles[0].weight if poles else 0.0
        pole_fraction = (
            lowest_weight / total_weight if total_weight > 0.0 else 0.0
        )
        if (
            not np.isfinite(recovered_fraction)
            or not np.isfinite(lowest_weight)
            or not np.isfinite(pole_fraction)
        ):
            raise ArithmeticError("channel response scalars must remain finite")
        channels[helicity] = ChannelSpectrum(
            helicity=helicity,
            component_weights=MappingProxyType(component_direct_weights),
            poles=poles,
            total_weight=total_weight,
            direct_sum_weight=direct_sum_weight,
            recovered_fraction=recovered_fraction,
            lowest_weight=lowest_weight,
            pole_fraction=pole_fraction,
        )

    minus_weight = channels["-"].lowest_weight
    plus_weight = channels["+"].lowest_weight
    delta_weight = minus_weight - plus_weight
    contrast_denominator = minus_weight + plus_weight
    if not np.isfinite(delta_weight) or not np.isfinite(contrast_denominator):
        raise ArithmeticError("chiral response scalars must remain finite")
    contrast = (
        delta_weight / contrast_denominator
        if contrast_denominator >= contrast_floor
        else None
    )
    if contrast is not None and not np.isfinite(contrast):
        raise ArithmeticError("contrast must remain finite")
    eigenpair_residual = max(
        float(
            np.linalg.norm(
                sector.hamiltonian @ sector.eigenvectors
                - sector.eigenvectors * sector.eigenvalues
            )
            / max(np.linalg.norm(sector.eigenvectors), 1.0)
        )
        for sector in (oracle.exact_sector(0), oracle.exact_sector(2))
    )
    if not np.isfinite(eigenpair_residual):
        raise ArithmeticError("response eigenpair diagnostic must remain finite")
    if eigenpair_residual > _EIGENPAIR_TOLERANCE:
        raise ArithmeticError("response eigenpair diagnostic exceeds tolerance")
    return ChiralSpectrum(
        particles=oracle.spec.particles,
        orientation=orientation,
        ground_energy=ground_energy,
        channels=channels,
        delta_weight=delta_weight,
        contrast=contrast,
        contrast_floor=float(contrast_floor),
        tensor_commutator_residual_max=tensor_residual,
        adjoint_residual=adjoint,
        reversal_residual_max=reversal_residual,
        eigenpair_residual_max=eigenpair_residual,
        initial_state_kind=initial_state_kind,
        initial_coefficient_sha256=initial_coefficient_sha256,
        estimator_scope=estimator_scope,
    )


def exact_chiral_spectrum_for_size(particles: int) -> ChiralSpectrum:
    """Solve and contract the exact response on the supported size interval."""

    if (
        isinstance(particles, bool)
        or not isinstance(particles, int)
        or not 2 <= particles <= 8
    ):
        raise ValueError("exact chiral response requires 2 <= particles <= 8")
    spec = SphereSpec(particles)
    solver = (
        solve_target_sectors
        if particles <= 4
        else solve_required_target_sectors_sparse
    )
    oracle = solver(spec)
    families = {
        helicity: build_response_family(spec, helicity)
        for helicity in ("+", "-")
    }
    result = exact_chiral_spectrum(oracle, families)
    cache_payload = oracle_cache_payload(oracle)
    oracle_from_cache_payload(cache_payload)
    cache_bytes = json.dumps(
        cache_payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return replace(
        result,
        oracle_cache_sha256=hashlib.sha256(cache_bytes).hexdigest(),
    )


def validate_response_families(
    spec: SphereSpec,
    families: Mapping[Helicity, ResponseFamily],
) -> tuple[float, float, float]:
    """Fail closed on all operator-family gates before spectral contraction."""

    if set(families) != {"+", "-"}:
        raise ValueError("families must contain exactly '+' and '-'")
    for helicity in ("+", "-"):
        family = families[helicity]
        if family.spec != spec or family.helicity != helicity:
            raise ValueError("response family identity does not match the SphereSpec")
    tensor_residual = max(
        residual
        for family in families.values()
        for residual in tensor_commutator_residuals(family).values()
    )
    adjoint = response_adjoint_residual(families["+"], families["-"])
    reversal_residual = _reversal_residual_max(families)
    source_normalizations = {
        lhyr_pair_reduced_source(
            spec,
            helicity,
            orientation=families[helicity].orientation,
        ).normalization
        for helicity in ("+", "-")
    }
    diagnostics = (tensor_residual, adjoint, reversal_residual)
    if source_normalizations != {
        "raw-LHYR-planar-Coulomb-E_C-resolution-eq-5.6"
    }:
        raise ArithmeticError("response source normalization is not canonical")
    if not all(np.isfinite(value) for value in diagnostics):
        raise ArithmeticError("response diagnostics must remain finite")
    if tensor_residual > _TENSOR_COMMUTATOR_TOLERANCE:
        raise ArithmeticError("response tensor-commutator diagnostic exceeds tolerance")
    if adjoint > _ADJOINT_TOLERANCE:
        raise ArithmeticError("response adjoint diagnostic exceeds tolerance")
    if reversal_residual > _MONOPOLE_REVERSAL_TOLERANCE:
        raise ArithmeticError("response monopole-reversal diagnostic exceeds tolerance")
    return diagnostics


def _reversal_residual_max(
    families: Mapping[Helicity, ResponseFamily],
) -> float:
    orientation = families["+"].orientation
    residuals = []
    for helicity in ("+", "-"):
        opposite: Helicity = "-" if helicity == "+" else "+"
        if orientation == 1:
            positive = families[helicity]
            reversed_family = build_response_family(
                positive.spec,
                opposite,
                orientation=-1,
            )
        else:
            reversed_family = families[helicity]
            positive = build_response_family(
                reversed_family.spec,
                opposite,
                orientation=1,
            )
        residuals.append(
            monopole_reversal_residual(positive, reversed_family)
        )
    return max(residuals)


def _normalize_coefficients(
    coefficients: np.ndarray,
    *,
    expected_shape: tuple[int, ...],
) -> np.ndarray:
    """Return a unit vector without overflowing on large finite inputs."""

    values = np.asarray(coefficients, dtype=np.complex128)
    if values.shape != expected_shape:
        raise ValueError("initial coefficients must match the L=0 multiplicity")
    if not np.all(np.isfinite(values)):
        raise ValueError("initial coefficients must be finite")

    scale = float(
        max(
            np.max(np.abs(values.real), initial=0.0),
            np.max(np.abs(values.imag), initial=0.0),
        )
    )
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("initial coefficients must have a finite nonzero norm")
    scaled = values / scale
    scaled_norm = float(np.linalg.norm(scaled))
    if not np.isfinite(scaled_norm) or scaled_norm <= 0.0:
        raise ValueError("initial coefficients must have a finite nonzero norm")
    normalized = np.asarray(scaled / scaled_norm, dtype=np.complex128)
    if not np.all(np.isfinite(normalized)):
        raise ValueError("normalized initial coefficients must be finite")
    return normalized
