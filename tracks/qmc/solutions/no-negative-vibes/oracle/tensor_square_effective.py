"""Tensor-square Gaussian-HS models and exact effective transfer gates.

Let ``V = R^m`` and use ``V tensor V`` as the physical one-particle space.
For a real base matrix ``X``, the physical propagator is ``X tensor X``.
The representation property

``(X tensor X)(Y tensor Y) = (XY) tensor (XY)``

keeps an arbitrary auxiliary-field history inside the tensor-square image.
For the eigenvalues ``lambda_i`` of the final base product,

``det(I + X tensor X)
  = product_i (1 + lambda_i**2)
    * product_(i<j) (1 + lambda_i * lambda_j)**2 >= 0``.

The main model in this module is the continuous Gaussian-HS family

``H = K - 1/2 sum_a g_a Q_a**2``,

where ``K = dGamma(k tensor I + I tensor k)``,
``Q_a = dGamma(A_a tensor I + I tensor A_a)``, all ``k,A_a`` are real
symmetric, and ``g_a >= 0``.  A Gaussian field for ``Q_a**2`` produces the
one-particle factor

``exp(alpha A_a) tensor exp(alpha A_a)``.

The second model averages the two diagonal fields ``+u`` and ``-u``.  Its
exact occupation-basis transfer gate is ``cosh(Q_u)``, and its exact finite
step Hamiltonian is ``-log(cosh(Q_u)) / dt``.  A Mobius transform resolves
that diagonal Hamiltonian into one-body, two-body, and higher-body density
monomials.

These are exact algebraic constructions, not a claim of a new sign-free
Hamiltonian class.  In particular, the two-dimensional base case has a
known conformal split-orthogonal description, and the general construction
still requires comparison with Majorana and contraction-semigroup criteria.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy.linalg import expm

from oracle.tensor_square import tensor_square_history
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class TensorSquareDeterminantCertificate:
    """Numerical audit of the general tensor-square determinant identity."""

    base_product: np.ndarray
    lifted_product: np.ndarray
    closure_residual: float
    diagonal_spectral_factor: float
    pair_spectral_factor: float
    spectral_weight: float
    direct_weight: float


@dataclass(frozen=True)
class ContinuousGaussianHSModel:
    """Parameters of ``K - 1/2 sum_a g_a Q_a**2``."""

    base_kinetic: np.ndarray
    base_generators: tuple[np.ndarray, ...]
    bare_couplings: tuple[float, ...]
    effective_couplings: tuple[float, ...]
    kac_scale: float

    @property
    def base_dimension(self) -> int:
        return self.base_kinetic.shape[0]

    @property
    def physical_modes(self) -> int:
        return self.base_dimension**2


@dataclass(frozen=True)
class ContinuousGaussianHSSlice:
    """One sampled, ordered, finite-step Gaussian-HS slice."""

    gaussian_fields: tuple[float, ...]
    gaussian_density: float
    base_factors: tuple[np.ndarray, ...]
    base_product: np.ndarray
    lifted_product: np.ndarray


@dataclass(frozen=True)
class ContinuousGaussianHSHistory:
    """An arbitrary-depth HS history with its determinant certificate."""

    slices: tuple[ContinuousGaussianHSSlice, ...]
    gaussian_prefactor: float
    determinant_certificate: TensorSquareDeterminantCertificate

    @property
    def total_weight(self) -> float:
        return (
            self.gaussian_prefactor
            * self.determinant_certificate.direct_weight
        )


@dataclass(frozen=True)
class ContinuousFockHamiltonian:
    """Exact finite-Fock-space form of the continuous model."""

    kinetic_operator: np.ndarray
    collective_operators: tuple[np.ndarray, ...]
    hamiltonian: np.ndarray


@dataclass(frozen=True)
class BodyOrderSummary:
    """Magnitude summary for one occupation-polynomial body order."""

    body_order: int
    term_count: int
    nonzero_count: int
    maximum_absolute_coefficient: float
    l2_norm: float


@dataclass(frozen=True)
class OccupationMobiusDecomposition:
    """Diagonal values and their unique multilinear occupation polynomial."""

    modes: int
    diagonal_values: np.ndarray
    coefficients: np.ndarray
    reconstructed_values: np.ndarray
    body_orders: tuple[BodyOrderSummary, ...]


@dataclass(frozen=True)
class DiscreteCollectiveDensityGate:
    """Exact two-field ``cosh(Q)`` gate and its ``-log`` interaction."""

    time_step: float
    base_field: np.ndarray
    mode_charges: np.ndarray
    occupation_charges: np.ndarray
    transfer_diagonal: np.ndarray
    effective_energy_diagonal: np.ndarray
    mobius: OccupationMobiusDecomposition


@dataclass(frozen=True)
class DiscreteEffectiveTransferMWE:
    """Kinetic sandwich, positive transfer gate, and exact ``-log`` model."""

    density_gate: DiscreteCollectiveDensityGate
    base_half_kinetic: np.ndarray
    lifted_half_kinetic: np.ndarray
    fock_half_kinetic: np.ndarray
    lifted_field_propagators: tuple[np.ndarray, np.ndarray]
    fock_slice_transfers: tuple[np.ndarray, np.ndarray]
    transfer_gate: np.ndarray
    effective_hamiltonian: np.ndarray
    minimum_transfer_eigenvalue: float


def _square_float_matrix(matrix: np.ndarray, *, name: str) -> np.ndarray:
    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError(f"{name} must be square")
    if candidate.shape[0] < 1:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(candidate)):
        raise ValueError(f"{name} must have finite entries")
    return candidate


def _symmetric_float_matrix(
    matrix: np.ndarray,
    *,
    name: str,
    tolerance: float = 1e-12,
) -> np.ndarray:
    candidate = _square_float_matrix(matrix, name=name)
    if not np.allclose(candidate, candidate.T, rtol=0.0, atol=tolerance):
        raise ValueError(f"{name} must be real symmetric")
    return candidate


def lifted_one_body_generator(base_generator: np.ndarray) -> np.ndarray:
    """Return ``A tensor I + I tensor A``."""

    base = _square_float_matrix(base_generator, name="base_generator")
    identity = np.eye(base.shape[0])
    return np.kron(base, identity) + np.kron(identity, base)


def number_conserving_fock_generator(
    one_body_generator: np.ndarray,
) -> np.ndarray:
    """Return ``dGamma(h) = sum_ij h_ij c_i^dagger c_j``.

    Fock states use the bit-mask ordering shared by
    :func:`number_conserving_gaussian_fock_matrix`.  The dense MWE is
    deliberately limited to ten one-particle modes.
    """

    one_body = _square_float_matrix(
        one_body_generator,
        name="one_body_generator",
    )
    modes = one_body.shape[0]
    if modes > 10:
        raise ValueError("dense Fock generator is restricted to at most 10 modes")
    dimension = 1 << modes
    result = np.zeros((dimension, dimension), dtype=float)

    for source in range(dimension):
        for column in range(modes):
            column_mask = 1 << column
            if not source & column_mask:
                continue
            annihilation_sign = -1.0 if (
                source & (column_mask - 1)
            ).bit_count() % 2 else 1.0
            removed = source ^ column_mask
            for row in range(modes):
                row_mask = 1 << row
                if removed & row_mask:
                    continue
                creation_sign = -1.0 if (
                    removed & (row_mask - 1)
                ).bit_count() % 2 else 1.0
                target = removed | row_mask
                result[target, source] += (
                    one_body[row, column]
                    * annihilation_sign
                    * creation_sign
                )
    return result


def tensor_square_determinant_certificate(
    base_factors: Sequence[np.ndarray],
    *,
    tolerance: float = 1e-9,
) -> TensorSquareDeterminantCertificate:
    """Certify the tensor-square formula for a history of any finite depth."""

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    history = tensor_square_history(base_factors)
    eigenvalues = np.linalg.eigvals(history.base_product).astype(complex)

    diagonal_factor = np.prod(1.0 + eigenvalues**2)
    pair_factor = 1.0 + 0.0j
    for left in range(len(eigenvalues)):
        for right in range(left + 1, len(eigenvalues)):
            pair_factor *= 1.0 + eigenvalues[left] * eigenvalues[right]

    def real_scalar(value: complex, *, name: str) -> float:
        scale = max(1.0, abs(value.real))
        if abs(value.imag) > tolerance * scale:
            raise ArithmeticError(f"{name} did not evaluate to a real scalar")
        return float(value.real)

    diagonal_real = real_scalar(
        complex(diagonal_factor),
        name="diagonal spectral factor",
    )
    pair_real = real_scalar(
        complex(pair_factor),
        name="pair spectral factor",
    )
    spectral_weight = diagonal_real * pair_real**2
    direct_weight = history.weight
    closure_residual = float(
        np.linalg.norm(
            history.lifted_product
            - np.kron(history.base_product, history.base_product)
        )
    )
    scale = max(1.0, abs(direct_weight), abs(spectral_weight))
    if abs(direct_weight - spectral_weight) > tolerance * scale:
        raise ArithmeticError(
            "spectral and direct tensor-square weights disagree"
        )
    if diagonal_real < -tolerance or direct_weight < -tolerance:
        raise ArithmeticError("tensor-square positivity certificate failed")
    return TensorSquareDeterminantCertificate(
        base_product=history.base_product,
        lifted_product=history.lifted_product,
        closure_residual=closure_residual,
        diagonal_spectral_factor=max(0.0, diagonal_real),
        pair_spectral_factor=pair_real,
        spectral_weight=max(0.0, spectral_weight),
        direct_weight=max(0.0, direct_weight),
    )


def continuous_gaussian_hs_model(
    *,
    base_kinetic: np.ndarray,
    base_generators: Sequence[np.ndarray],
    couplings: Sequence[float],
    kac_normalize: bool = False,
) -> ContinuousGaussianHSModel:
    """Define the continuous attractive-square Hamiltonian.

    With ``kac_normalize=True``, every supplied coupling is divided by
    ``m**2``, the number of physical one-particle modes.  If the base
    generators have size-independent operator norm, this makes the square
    of an extensive collective operator contribute ``O(m**2)`` energy.
    """

    kinetic = _symmetric_float_matrix(
        base_kinetic,
        name="base_kinetic",
    )
    generators = tuple(
        _symmetric_float_matrix(generator, name="base generator")
        for generator in base_generators
    )
    strengths = tuple(float(coupling) for coupling in couplings)
    if len(generators) != len(strengths):
        raise ValueError("base_generators and couplings must have equal length")
    if not generators:
        raise ValueError("at least one interaction generator is required")
    if any(generator.shape != kinetic.shape for generator in generators):
        raise ValueError("all base matrices must have the same shape")
    if any(
        not math.isfinite(coupling) or coupling < 0.0
        for coupling in strengths
    ):
        raise ValueError("couplings must be nonnegative and finite")

    kac_scale = 1.0 / kinetic.shape[0] ** 2 if kac_normalize else 1.0
    return ContinuousGaussianHSModel(
        base_kinetic=kinetic,
        base_generators=generators,
        bare_couplings=strengths,
        effective_couplings=tuple(
            kac_scale * coupling for coupling in strengths
        ),
        kac_scale=kac_scale,
    )


def sample_continuous_gaussian_hs_slice(
    model: ContinuousGaussianHSModel,
    gaussian_fields: Sequence[float],
    *,
    time_step: float,
) -> ContinuousGaussianHSSlice:
    """Return one ordered Gaussian-HS slice.

    Different ``A_a`` need not commute.  The chosen product order is a
    first-order interaction Trotterization; changing that order changes the
    finite-step approximation but not tensor-square determinant positivity.
    """

    if not math.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("time_step must be positive and finite")
    fields = tuple(float(field) for field in gaussian_fields)
    if len(fields) != len(model.base_generators):
        raise ValueError(
            "gaussian_fields must match the interaction generators"
        )
    if any(not math.isfinite(field) for field in fields):
        raise ValueError("gaussian_fields must be finite")

    kinetic_half = expm(-0.5 * time_step * model.base_kinetic)
    interaction_factors = tuple(
        expm(
            field
            * math.sqrt(time_step * coupling)
            * generator
        )
        for field, coupling, generator in zip(
            fields,
            model.effective_couplings,
            model.base_generators,
            strict=True,
        )
    )
    base_factors = (kinetic_half,) + interaction_factors + (kinetic_half,)
    base_product = np.eye(model.base_dimension)
    for factor in base_factors:
        base_product = base_product @ factor
    gaussian_density = math.exp(
        -0.5 * sum(field**2 for field in fields)
    ) / (2.0 * math.pi) ** (0.5 * len(fields))
    return ContinuousGaussianHSSlice(
        gaussian_fields=fields,
        gaussian_density=gaussian_density,
        base_factors=base_factors,
        base_product=base_product,
        lifted_product=np.kron(base_product, base_product),
    )


def continuous_gaussian_hs_history(
    model: ContinuousGaussianHSModel,
    gaussian_history: Sequence[Sequence[float]],
    *,
    time_step: float,
) -> ContinuousGaussianHSHistory:
    """Evaluate an arbitrary-depth continuous Gaussian-HS history."""

    slices = tuple(
        sample_continuous_gaussian_hs_slice(
            model,
            fields,
            time_step=time_step,
        )
        for fields in gaussian_history
    )
    if not slices:
        raise ValueError("gaussian_history must contain at least one slice")
    certificate = tensor_square_determinant_certificate(
        tuple(slice_.base_product for slice_ in slices)
    )
    return ContinuousGaussianHSHistory(
        slices=slices,
        gaussian_prefactor=math.prod(
            slice_.gaussian_density for slice_ in slices
        ),
        determinant_certificate=certificate,
    )


def continuous_model_fock_hamiltonian(
    model: ContinuousGaussianHSModel,
) -> ContinuousFockHamiltonian:
    """Build ``K - 1/2 sum_a g_a Q_a**2`` on the full Fock space."""

    if model.physical_modes > 9:
        raise ValueError(
            "dense Fock Hamiltonian construction is restricted to at most "
            "nine physical modes"
        )
    kinetic = number_conserving_fock_generator(
        lifted_one_body_generator(model.base_kinetic)
    )
    collective = tuple(
        number_conserving_fock_generator(
            lifted_one_body_generator(generator)
        )
        for generator in model.base_generators
    )
    hamiltonian = kinetic.copy()
    for coupling, operator in zip(
        model.effective_couplings,
        collective,
        strict=True,
    ):
        hamiltonian -= 0.5 * coupling * (operator @ operator)
    return ContinuousFockHamiltonian(
        kinetic_operator=kinetic,
        collective_operators=collective,
        hamiltonian=hamiltonian,
    )


def coordinate_sum_charges(base_field: np.ndarray) -> np.ndarray:
    """Return ``q_(ij) = u_i + u_j`` in row-major product-lattice order."""

    field = np.asarray(base_field, dtype=float)
    if field.ndim != 1 or field.size < 1:
        raise ValueError("base_field must be a nonempty vector")
    if not np.all(np.isfinite(field)):
        raise ValueError("base_field must have finite entries")
    return np.add.outer(field, field).reshape(-1)


def occupation_linear_values(charges: np.ndarray) -> np.ndarray:
    """Evaluate ``sum_i charges_i n_i`` on every occupation bit mask."""

    values = np.asarray(charges, dtype=float)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("charges must be a nonempty vector")
    if not np.all(np.isfinite(values)):
        raise ValueError("charges must have finite entries")
    if values.size > 20:
        raise ValueError("occupation expansion is restricted to at most 20 modes")

    result = np.zeros(1 << values.size, dtype=float)
    for mask in range(1, result.size):
        lowest_bit = mask & -mask
        mode = lowest_bit.bit_length() - 1
        result[mask] = result[mask ^ lowest_bit] + values[mode]
    return result


def occupation_polynomial_values(coefficients: np.ndarray) -> np.ndarray:
    """Apply the subset zeta transform to occupation monomial coefficients."""

    result = np.asarray(coefficients, dtype=float).copy()
    if result.ndim != 1 or result.size < 1:
        raise ValueError("coefficients must be a nonempty vector")
    if result.size & (result.size - 1):
        raise ValueError("coefficient count must be a power of two")
    modes = result.size.bit_length() - 1
    for mode in range(modes):
        bit = 1 << mode
        for mask in range(result.size):
            if mask & bit:
                result[mask] += result[mask ^ bit]
    return result


def occupation_mobius_decomposition(
    diagonal_values: np.ndarray,
    *,
    tolerance: float = 1e-12,
) -> OccupationMobiusDecomposition:
    """Resolve a diagonal operator into products of occupation numbers."""

    values = np.asarray(diagonal_values, dtype=float)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("diagonal_values must be a nonempty vector")
    if values.size & (values.size - 1):
        raise ValueError("diagonal value count must be a power of two")
    if not np.all(np.isfinite(values)):
        raise ValueError("diagonal_values must have finite entries")
    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")

    modes = values.size.bit_length() - 1
    coefficients = values.copy()
    for mode in range(modes):
        bit = 1 << mode
        for mask in range(coefficients.size):
            if mask & bit:
                coefficients[mask] -= coefficients[mask ^ bit]
    reconstructed = occupation_polynomial_values(coefficients)

    summaries: list[BodyOrderSummary] = []
    for order in range(modes + 1):
        selected = np.asarray(
            [
                coefficients[mask]
                for mask in range(coefficients.size)
                if mask.bit_count() == order
            ],
            dtype=float,
        )
        summaries.append(
            BodyOrderSummary(
                body_order=order,
                term_count=selected.size,
                nonzero_count=int(
                    np.count_nonzero(np.abs(selected) > tolerance)
                ),
                maximum_absolute_coefficient=(
                    float(np.max(np.abs(selected))) if selected.size else 0.0
                ),
                l2_norm=float(np.linalg.norm(selected)),
            )
        )
    return OccupationMobiusDecomposition(
        modes=modes,
        diagonal_values=values.copy(),
        coefficients=coefficients,
        reconstructed_values=reconstructed,
        body_orders=tuple(summaries),
    )


def discrete_collective_density_gate(
    base_field: np.ndarray,
    *,
    time_step: float,
) -> DiscreteCollectiveDensityGate:
    """Return the exact two-field ``cosh(Q_u)`` interaction gate."""

    if not math.isfinite(time_step) or time_step <= 0.0:
        raise ValueError("time_step must be positive and finite")
    field = np.asarray(base_field, dtype=float)
    charges = coordinate_sum_charges(field)
    occupation_charges = occupation_linear_values(charges)
    transfer = np.cosh(occupation_charges)
    effective_energy = -np.log(transfer) / time_step
    mobius = occupation_mobius_decomposition(effective_energy)
    return DiscreteCollectiveDensityGate(
        time_step=time_step,
        base_field=field.copy(),
        mode_charges=charges,
        occupation_charges=occupation_charges,
        transfer_diagonal=transfer,
        effective_energy_diagonal=effective_energy,
        mobius=mobius,
    )


def _symmetric_positive_logarithm(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    candidate = _symmetric_float_matrix(matrix, name="matrix", tolerance=1e-10)
    eigenvalues, eigenvectors = np.linalg.eigh(candidate)
    minimum = float(np.min(eigenvalues))
    if minimum <= 0.0:
        raise ValueError("matrix must be positive definite")
    logarithm = (
        eigenvectors
        @ np.diag(np.log(eigenvalues))
        @ eigenvectors.T
    )
    return logarithm, minimum


def discrete_effective_transfer_mwe(
    *,
    base_kinetic: np.ndarray,
    base_field: np.ndarray,
    time_step: float,
) -> DiscreteEffectiveTransferMWE:
    """Build the exact positive transfer gate and ``-log`` Hamiltonian.

    The full dense Fock matrices scale as ``2**(m**2)`` and this MWE is
    intentionally restricted to ``m <= 3``.
    """

    kinetic = _symmetric_float_matrix(
        base_kinetic,
        name="base_kinetic",
    )
    field = np.asarray(base_field, dtype=float)
    if field.ndim != 1 or field.size != kinetic.shape[0]:
        raise ValueError("base_field must match the base dimension")
    if kinetic.shape[0] > 3:
        raise ValueError("dense effective-transfer MWE is restricted to m <= 3")
    density = discrete_collective_density_gate(
        field,
        time_step=time_step,
    )

    base_half = expm(-0.5 * time_step * kinetic)
    lifted_half = np.kron(base_half, base_half)
    fock_half = number_conserving_gaussian_fock_matrix(lifted_half)
    lifted_fields = tuple(
        np.diag(np.exp(sign * density.mode_charges))
        for sign in (1.0, -1.0)
    )
    field_fock = tuple(
        number_conserving_gaussian_fock_matrix(propagator)
        for propagator in lifted_fields
    )
    slice_transfers = tuple(
        fock_half @ field_gate @ fock_half
        for field_gate in field_fock
    )
    transfer = 0.5 * (slice_transfers[0] + slice_transfers[1])
    logarithm, minimum = _symmetric_positive_logarithm(transfer)
    effective = -logarithm / time_step
    return DiscreteEffectiveTransferMWE(
        density_gate=density,
        base_half_kinetic=base_half,
        lifted_half_kinetic=lifted_half,
        fock_half_kinetic=fock_half,
        lifted_field_propagators=lifted_fields,
        fock_slice_transfers=slice_transfers,
        transfer_gate=transfer,
        effective_hamiltonian=effective,
        minimum_transfer_eigenvalue=minimum,
    )
