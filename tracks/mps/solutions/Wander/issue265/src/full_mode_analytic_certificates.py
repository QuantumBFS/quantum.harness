"""Analytic certificates for finite-cutoff fluctuating GHD.

The routines in this module do not sample stochastic trajectories.  They use
the finite-cutoff GHD generator, its static covariance, and the physical spin
projection to compute three objects exactly (up to matrix arithmetic):

* Ornstein--Uhlenbeck covariance propagation;
* the scalar Mori kernel obtained after eliminating every non-spin mode;
* the static-metric decomposition of an initial perturbation into the spin
  tangent and its orthogonal complement.

These identities remain finite-cutoff statements.  A separate joint
``h -> 0``, string, and rapidity convergence certificate is required before
they can be promoted to the isotropic zero-field limit.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
from scipy.linalg import expm


Array = np.ndarray


def linear_ghd_generator(
    wave_number: float,
    velocity: Array,
    diffusion: Array,
    *,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> Array:
    r"""Return the retained-mode linear GHD generator.

    With no symbol supplied this is the continuum generator
    ``L_k=-ik v-k^2 D/2``.  Supplying ``lattice_wave_number`` replaces *both*
    occurrences of momentum by the same signed lattice derivative symbol.
    For the bond-centred nearest-neighbour convention this is
    ``khat=2 sin(k/2)``.  Applying the replacement inside the generator, and
    not merely in a final continuity normalisation, is essential for a
    Brillouin-zone calculation.
    """

    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    if velocity.ndim != 1 or diffusion.shape != (velocity.size, velocity.size):
        raise ValueError("velocity and diffusion dimensions do not agree")
    if not np.isfinite(wave_number) or np.any(~np.isfinite(diffusion + velocity[:, None])):
        raise ValueError("generator inputs must be finite")
    effective_wave = (
        float(wave_number)
        if lattice_wave_number is None
        else float(lattice_wave_number(float(wave_number)))
    )
    if not np.isfinite(effective_wave):
        raise ValueError("lattice wave-number symbol must be finite")
    return (
        -1j * effective_wave * np.diag(velocity)
        - 0.5 * effective_wave**2 * diffusion
    )


def exact_ou_covariance(
    generator: Array,
    equilibrium_covariance: Array,
    initial_covariance: Array,
    times: Array,
) -> dict[str, Array | float]:
    r"""Propagate the complete linear fluctuating-GHD covariance.

    If the FDT noise is chosen so that ``C`` is stationary, the Lyapunov
    solution is

    ``Sigma(t)=C+exp(Lt)[Sigma(0)-C]exp(L^dagger t)``.

    The corresponding accumulated noise covariance is

    ``C-exp(Lt) C exp(L^dagger t)``.

    This evaluates the stochastic covariance exactly without Monte Carlo.
    """

    generator = np.asarray(generator, dtype=complex)
    equilibrium = np.asarray(equilibrium_covariance, dtype=complex)
    initial = np.asarray(initial_covariance, dtype=complex)
    times = np.asarray(times, dtype=float)
    size = generator.shape[0]
    if generator.shape != (size, size) or equilibrium.shape != (size, size):
        raise ValueError("generator and equilibrium covariance must be square")
    if initial.shape != equilibrium.shape:
        raise ValueError("initial covariance has the wrong shape")
    if times.ndim != 1 or np.any(times < 0.0) or np.any(np.diff(times) < 0.0):
        raise ValueError("times must be a non-negative increasing vector")

    propagated: list[Array] = []
    innovations: list[Array] = []
    transitions: list[Array] = []
    hermiticity = 0.0
    for time in times:
        transition = expm(float(time) * generator)
        innovation = equilibrium - transition @ equilibrium @ transition.conj().T
        covariance = equilibrium + transition @ (initial - equilibrium) @ transition.conj().T
        covariance = 0.5 * (covariance + covariance.conj().T)
        innovation = 0.5 * (innovation + innovation.conj().T)
        hermiticity = max(
            hermiticity,
            float(np.linalg.norm(covariance - covariance.conj().T)),
        )
        transitions.append(transition)
        innovations.append(innovation)
        propagated.append(covariance)
    return {
        "times": times,
        "transitions": np.asarray(transitions),
        "covariances": np.asarray(propagated),
        "accumulated_noise_covariances": np.asarray(innovations),
        "maximum_hermiticity_residual": hermiticity,
    }


def full_fdt_noise_covariance(
    generator: Array,
    equilibrium_covariance: Array,
) -> dict[str, Array | float | bool]:
    r"""Return the complete additive-noise covariance fixed by FDT.

    For ``du=L u dt+B dW`` stationarity of ``C`` requires

    ``Q=B B^dagger=-(L C+C L^dagger)``.

    No diagonal approximation is made.  In Fourier-space fluctuating GHD the
    Euler part cancels in this identity (in the thermodynamic metric), while
    the complete non-diagonal diffusion operator fixes ``Q``.  A negative
    eigenvalue beyond roundoff signals an inconsistent discretization rather
    than something that may be clipped silently.
    """

    generator = np.asarray(generator, dtype=complex)
    covariance = np.asarray(equilibrium_covariance, dtype=complex)
    if generator.ndim != 2 or generator.shape[0] != generator.shape[1]:
        raise ValueError("generator must be square")
    if covariance.shape != generator.shape:
        raise ValueError("equilibrium covariance must match generator")
    noise = -(generator @ covariance + covariance @ generator.conj().T)
    noise = 0.5 * (noise + noise.conj().T)
    eigenvalues = np.linalg.eigvalsh(noise)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    minimum = float(np.min(eigenvalues))
    residual = float(
        np.linalg.norm(
            generator @ covariance
            + covariance @ generator.conj().T
            + noise
        )
        / max(np.linalg.norm(noise), np.finfo(float).tiny)
    )
    return {
        "noise_covariance": noise,
        "minimum_eigenvalue": minimum,
        "positive_semidefinite_within_roundoff": bool(
            minimum >= -1.0e-11 * scale
        ),
        "relative_lyapunov_residual": residual,
    }


def propagate_matrix_mori_volterra(
    generator: Array,
    equilibrium_covariance: Array,
    times: Array,
    force_covariance_memory: Array,
) -> dict[str, Array | float]:
    r"""Propagate one full matrix Mori/Dyson closure on a uniform grid.

    The retained-mode response obeys

    ``dG/dt=L G-integral_0^t M(t-s) C^-1 G(s) ds``, ``G(0)=I``.

    Here ``M(t)=<F(t)F(0)^dagger>`` is the *matrix* orthogonal-force
    covariance.  The function never diagonalizes ``D``, ``C`` or the memory.
    The local linear evolution is applied exactly with ``exp(L dt)`` and the
    convolution is trapezoidal.  This is a first-order exponential-product
    quadrature in the outer time step; convergence in ``dt`` must therefore
    be checked by the caller.  Supplying a one-loop ``M`` produces one matrix
    Dyson update, not the exact nonlinear fluctuating-GHD solution.
    """

    generator = np.asarray(generator, dtype=complex)
    covariance = np.asarray(equilibrium_covariance, dtype=complex)
    times = np.asarray(times, dtype=float)
    force_memory = np.asarray(force_covariance_memory, dtype=complex)
    modes = generator.shape[0]
    if generator.shape != (modes, modes) or covariance.shape != (modes, modes):
        raise ValueError("generator and covariance must be matching square matrices")
    if times.ndim != 1 or times.size < 2 or times[0] != 0.0:
        raise ValueError("times must be a vector beginning at zero")
    steps = np.diff(times)
    if np.any(steps <= 0.0) or not np.allclose(
        steps, steps[0], rtol=1.0e-11, atol=1.0e-14
    ):
        raise ValueError("matrix Volterra propagation requires a uniform grid")
    if force_memory.shape != (times.size, modes, modes):
        raise ValueError("force memory must have shape (time, mode, mode)")
    hermitian_covariance = 0.5 * (covariance + covariance.conj().T)
    covariance_eigenvalues = np.linalg.eigvalsh(hermitian_covariance)
    if float(np.min(covariance_eigenvalues)) <= 0.0:
        raise ValueError("equilibrium covariance must be positive definite")

    # Right multiplication by C^{-1}, implemented without forming an inverse.
    memory_kernel = np.linalg.solve(
        covariance.T, force_memory.transpose(0, 2, 1)
    ).transpose(0, 2, 1)
    dt = float(steps[0])
    transition = expm(dt * generator)
    response = np.zeros((times.size, modes, modes), dtype=complex)
    response[0] = np.eye(modes, dtype=complex)
    for time_index in range(times.size - 1):
        if time_index == 0:
            convolution = np.zeros((modes, modes), dtype=complex)
        else:
            convolution = 0.5 * (
                memory_kernel[time_index] @ response[0]
                + memory_kernel[0] @ response[time_index]
            )
            for history_index in range(1, time_index):
                convolution += (
                    memory_kernel[time_index - history_index]
                    @ response[history_index]
                )
            convolution *= dt
        response[time_index + 1] = transition @ (
            response[time_index] - dt * convolution
        )
    two_time_covariance = response @ covariance
    return {
        "times": times,
        "response": response,
        "two_time_covariance": two_time_covariance,
        "force_covariance_memory": force_memory,
        "memory_kernel": memory_kernel,
        "time_step": dt,
        "initial_response_residual": float(
            np.linalg.norm(response[0] - np.eye(modes))
        ),
    }


def propagate_low_rank_matrix_mori_actions(
    generator: Array,
    equilibrium_covariance: Array,
    times: Array,
    memory_left_factors: Array,
    memory_right_factors: Array,
    source_vectors: Array,
) -> dict[str, Array | float]:
    r"""Propagate selected response columns with a low-rank matrix memory.

    At each lag the force covariance is represented exactly as

    ``M(t_n)=L_n R_n^dagger``.

    The routine solves the same Volterra equation as
    :func:`propagate_matrix_mori_volterra`, but only for ``G(t) X`` and applies
    the Mori kernel as

    ``M C^-1 Y=L [R^dagger (C^-1 Y)]``.

    This reduces stored nonlinear memory from ``O(N_mode^2 N_t)`` to
    ``O(N_mode R N_t)``.  It is the required representation when the Wick
    estimator itself supplies a sum of rank-one force outer products.  The
    linear transition remains dense in this implementation.
    """

    generator = np.asarray(generator, dtype=complex)
    covariance = np.asarray(equilibrium_covariance, dtype=complex)
    times = np.asarray(times, dtype=float)
    left = np.asarray(memory_left_factors, dtype=complex)
    right = np.asarray(memory_right_factors, dtype=complex)
    sources = np.asarray(source_vectors, dtype=complex)
    modes = generator.shape[0]
    if generator.shape != (modes, modes) or covariance.shape != (modes, modes):
        raise ValueError("generator and covariance must be matching square matrices")
    if times.ndim != 1 or times.size < 2 or times[0] != 0.0:
        raise ValueError("times must begin at zero")
    steps = np.diff(times)
    if np.any(steps <= 0.0) or not np.allclose(
        steps, steps[0], rtol=1.0e-11, atol=1.0e-14
    ):
        raise ValueError("low-rank Volterra propagation requires a uniform grid")
    if left.ndim != 3 or right.shape != left.shape:
        raise ValueError("left and right memory factors must have equal rank-three shape")
    if left.shape[0] != times.size or left.shape[1] != modes:
        raise ValueError("memory factors must have shape (time, mode, rank)")
    if sources.ndim == 1:
        sources = sources[:, None]
    if sources.ndim != 2 or sources.shape[0] != modes:
        raise ValueError("source vectors must have shape (mode, source)")
    covariance_eigenvalues = np.linalg.eigvalsh(
        0.5 * (covariance + covariance.conj().T)
    )
    if float(np.min(covariance_eigenvalues)) <= 0.0:
        raise ValueError("equilibrium covariance must be positive definite")

    inverse_sources = np.empty_like(sources)
    actions = np.zeros(
        (times.size, modes, sources.shape[1]), dtype=complex
    )
    actions[0] = sources
    dt = float(steps[0])
    transition = expm(dt * generator)

    def memory_action(lag_index: int, vectors: Array) -> Array:
        inverse_sources[:] = np.linalg.solve(covariance, vectors)
        coefficients = right[lag_index].conj().T @ inverse_sources
        return left[lag_index] @ coefficients

    for time_index in range(times.size - 1):
        if time_index == 0:
            convolution = np.zeros_like(sources)
        else:
            convolution = 0.5 * (
                memory_action(time_index, actions[0])
                + memory_action(0, actions[time_index])
            )
            for history_index in range(1, time_index):
                convolution += memory_action(
                    time_index - history_index, actions[history_index]
                )
            convolution *= dt
        actions[time_index + 1] = transition @ (
            actions[time_index] - dt * convolution
        )
    return {
        "times": times,
        "response_actions": actions,
        "source_vectors": sources,
        "memory_rank": int(left.shape[2]),
        "time_step": dt,
        "dense_memory_stored": False,
        "initial_action_residual": float(np.linalg.norm(actions[0] - sources)),
    }


def projected_two_time_structure(
    generator: Array,
    covariance: Array,
    projection: Array,
    times: Array,
) -> Array:
    r"""Return ``p^T exp(L_k t) C p / (p^T C p)``."""

    generator = np.asarray(generator, dtype=complex)
    covariance = np.asarray(covariance, dtype=complex)
    projection = np.asarray(projection, dtype=complex)
    times = np.asarray(times, dtype=float)
    if covariance.shape != generator.shape or projection.shape != (generator.shape[0],):
        raise ValueError("projection dimensions do not agree with the generator")
    normalization = projection.conj() @ covariance @ projection
    if not float(np.real(normalization)) > 0.0:
        raise ValueError("projected static susceptibility is non-positive")
    return np.asarray(
        [
            projection.conj()
            @ expm(float(time) * generator)
            @ covariance
            @ projection
            / normalization
            for time in times
        ]
    )


def projected_mori_kernel(
    generator: Array,
    covariance: Array,
    projection: Array,
    wave_number: float,
    laplace_values: Array,
    *,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float]:
    r"""Eliminate all non-spin modes and return the exact scalar Mori kernel.

    The projected resolvent is

    ``F_tilde(k,z)=p^dagger (z-L_k)^(-1) C p/(p^dagger C p)``.

    The continuity-equation Mori identity then gives

    ``K_tilde=(1/F_tilde-z)/khat^2``.

    This is algebraically identical to the Schur complement of the full GHD
    generator, but avoids choosing a basis for the eliminated subspace.
    """

    generator = np.asarray(generator, dtype=complex)
    covariance = np.asarray(covariance, dtype=complex)
    projection = np.asarray(projection, dtype=complex)
    laplace_values = np.asarray(laplace_values, dtype=float)
    size = generator.shape[0]
    if generator.shape != (size, size) or covariance.shape != generator.shape:
        raise ValueError("generator and covariance dimensions do not agree")
    if projection.shape != (size,):
        raise ValueError("projection has the wrong dimension")
    if laplace_values.ndim != 1 or np.any(laplace_values <= 0.0):
        raise ValueError("Laplace values must be a positive vector")
    normalization = projection.conj() @ covariance @ projection
    if not float(np.real(normalization)) > 0.0:
        raise ValueError("projected static susceptibility is non-positive")
    khat = (
        float(wave_number)
        if lattice_wave_number is None
        else float(lattice_wave_number(float(wave_number)))
    )
    if khat == 0.0:
        raise ValueError("the Mori kernel requires a non-zero wave number")
    source = covariance @ projection
    identity = np.eye(size, dtype=complex)
    resolvent = np.empty(laplace_values.size, dtype=complex)
    for index, laplace in enumerate(laplace_values):
        response = np.linalg.solve(laplace * identity - generator, source)
        resolvent[index] = projection.conj() @ response / normalization
    kernel = (1.0 / resolvent - laplace_values) / khat**2
    return {
        "laplace_values": laplace_values,
        "projected_resolvent": resolvent,
        "mori_kernel": kernel,
        "projected_static_susceptibility": float(np.real(normalization)),
        "maximum_resolvent_inversion_residual": float(
            np.max(np.abs((laplace_values + khat**2 * kernel) * resolvent - 1.0))
        ),
    }


def static_metric_projection(
    perturbation: Array,
    physical_tangent: Array,
    covariance: Array,
) -> dict[str, Array | float]:
    r"""Decompose an initial perturbation in the thermodynamic ``C^-1`` metric.

    The coefficient and residual are

    ``alpha=<r,u>_(C^-1)/<r,r>_(C^-1)``, ``u_perp=u-alpha*r``.

    A scalar hydrodynamic closure is initially controlled only when the
    returned orthogonal fraction is small in the same metric used by the
    fluctuation theory.
    """

    perturbation = np.asarray(perturbation, dtype=float)
    tangent = np.asarray(physical_tangent, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    if perturbation.ndim != 1 or tangent.shape != perturbation.shape:
        raise ValueError("perturbation and tangent must be equal-length vectors")
    if covariance.shape != (perturbation.size, perturbation.size):
        raise ValueError("covariance has the wrong shape")
    inverse_u = np.linalg.solve(covariance, perturbation)
    inverse_r = np.linalg.solve(covariance, tangent)
    denominator = float(tangent @ inverse_r)
    if denominator <= 0.0:
        raise ValueError("physical tangent has non-positive static norm")
    coefficient = float(tangent @ inverse_u / denominator)
    parallel = coefficient * tangent
    perpendicular = perturbation - parallel
    total_norm = float(perturbation @ inverse_u)
    perpendicular_norm = float(
        perpendicular @ np.linalg.solve(covariance, perpendicular)
    )
    orthogonality = float(tangent @ np.linalg.solve(covariance, perpendicular))
    return {
        "coefficient": coefficient,
        "parallel": parallel,
        "perpendicular": perpendicular,
        "total_static_norm_squared": total_norm,
        "perpendicular_static_norm_squared": perpendicular_norm,
        "orthogonal_fraction": perpendicular_norm / total_norm if total_norm > 0.0 else 0.0,
        "orthogonality_residual": orthogonality,
    }


def magnetic_local_gge_wall_tangent(
    field_profile: Array,
    covariance: Array,
    spin_projection: Array,
) -> dict[str, Array | float | str]:
    r"""Map a weak magnetic wall into all GHD modes by static response.

    For a local GGE perturbed by ``-h(x) q_spin``, thermodynamic linear
    response gives the mode-space tangent exactly:

    ``delta u_A(x)=C_AB p_B h(x)+O(h^2)``.

    Consequently the initial perturbation is parallel to the physical spin
    tangent at linear order.  Orthogonal modes can still be generated by the
    finite-amplitude remainder, by an initial state that is not a local GGE,
    or dynamically through the nonlinear velocity vertex.
    """

    profile = np.asarray(field_profile, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    spin = np.asarray(spin_projection, dtype=float)
    if profile.ndim != 1 or spin.ndim != 1:
        raise ValueError("field profile and spin projection must be vectors")
    if covariance.shape != (spin.size, spin.size):
        raise ValueError("covariance has the wrong shape")
    tangent = covariance @ spin
    mode_profile = tangent[:, None] * profile[None, :]
    susceptibility = float(spin @ tangent)
    if susceptibility <= 0.0:
        raise ValueError("spin susceptibility is non-positive")
    return {
        "physical_tangent": tangent,
        "mode_profile_linear_response": mode_profile,
        "spin_susceptibility": susceptibility,
        "linear_order_orthogonal_fraction": 0.0,
        "finite_amplitude_remainder_order": "O(max|h|^2) before spin-flip pairing",
        "non_local_gge_initial_slip_controlled": False,
        "zero_field_finite_string_representation_singular": True,
    }


def zero_field_magnetic_wall_string_certificate(
    species: Array,
    field_amplitude: float,
    *,
    physical_susceptibility: float = 0.25,
) -> dict[str, Array | float | bool | str]:
    r"""Expose the singular finite-string representation of a zero-field wall.

    At infinite temperature the magnetic-GGE fillings are

    ``n_s(h)=[sinh(h)/sinh((s+1)h)]^2``.

    They are even in ``h``.  Hence every fixed finite string has zero linear
    response at the symmetric point although the physical spin susceptibility
    is nonzero.  The missing signed magnetization is carried by the SU(2)
    orientation/giant-string boundary at ``s=O(1/|h|)``.  A fixed string
    cutoff therefore cannot map an opposite-sign zero-field domain wall,
    regardless of rapidity resolution.
    """

    strings = np.asarray(species, dtype=int)
    amplitude = float(field_amplitude)
    susceptibility = float(physical_susceptibility)
    if (
        strings.ndim != 1
        or strings.size == 0
        or np.any(strings < 1)
        or amplitude <= 0.0
        or not np.isfinite(amplitude)
        or susceptibility <= 0.0
    ):
        raise ValueError("need positive strings, amplitude and susceptibility")
    positive = (
        np.sinh(amplitude) / np.sinh((strings.astype(float) + 1.0) * amplitude)
    ) ** 2
    negative = (
        np.sinh(-amplitude) / np.sinh(-(strings.astype(float) + 1.0) * amplitude)
    ) ** 2
    zero = 1.0 / (strings.astype(float) + 1.0) ** 2
    quadratic = -zero * (((strings.astype(float) + 1.0) ** 2 - 1.0) / 3.0)
    return {
        "species": strings,
        "positive_field_fillings": positive,
        "negative_field_fillings": negative,
        "opposite_wall_filling_difference": positive - negative,
        "zero_field_fillings": zero,
        "fixed_string_linear_derivative_at_zero": np.zeros_like(zero),
        "fixed_string_quadratic_coefficient": quadratic,
        "maximum_orientation_difference_at_finite_cutoff": float(
            np.max(np.abs(positive - negative))
        ),
        "physical_susceptibility": susceptibility,
        "finite_string_linear_spin_weight_captured_fraction": 0.0,
        "missing_linear_spin_weight_fraction": 1.0,
        "finite_string_linear_response_matches_physical_spin": False,
        "crossover_string_scale": float(1.0 / amplitude),
        "required_extra_coordinate": (
            "signed SU(2) orientation / giant-string boundary mode"
        ),
        "augmented_local_gge_mapping": (
            "n_s(x)=n_s(|h(x)|), sigma(x)=sign(h(x)); "
            "m(x)=sigma(x) m(|h(x)|)"
        ),
        "augmented_mapping_linear_orthogonal_fraction": 0.0,
        "gradient_remainder": "O(a/L_wall) after local-equilibrium initialization",
        "sharp_product_wall_initial_slip_controlled": False,
        "limits_commute": False,
    }


def sharp_product_wall_mori_certificate(amplitudes: Array) -> dict[str, object]:
    r"""Certify the linear initial condition of an infinite-temperature wall.

    For a product preparation

    ``rho_sigma(mu) propto exp[sigma*mu*sum_j f_j S_j^z]``,

    the orientation-odd normalized density matrix starts with

    ``[rho_+(mu)-rho_-(mu)]/(2 mu)=sum_j f_j S_j^z+O(mu^2)``.

    The leading operator is exactly a superposition of the physical spin
    density Fourier modes.  A Mori projector retaining every ``S_k^z``
    therefore has zero initial-slip source at linear order, independently of
    whether the profile is smooth or sharp.  Opposite orientations remove
    even response terms; a fit through ``mu^4`` leaves an ``O(mu^6)``
    normalized-amplitude remainder.
    """

    mu = np.asarray(amplitudes, dtype=float)
    if (
        mu.ndim != 1
        or mu.size < 4
        or np.any(~np.isfinite(mu))
        or np.any(mu <= 0.0)
        or np.unique(mu).size != mu.size
    ):
        raise ValueError("need at least four distinct positive amplitudes")
    return {
        "amplitudes": mu,
        "linear_orientation_odd_operator": "sum_j f_j S_j^z",
        "linear_operator_inside_spin_density_mori_subspace": True,
        "linear_mori_initial_slip": 0.0,
        "profile_smoothness_required_for_linear_mori_statement": False,
        "profile_smoothness_required_for_local_GGE_GHD_mapping": True,
        "paired_normalized_response_expansion": (
            "R(mu)=R0+R2 mu^2+R4 mu^4+O(mu^6)"
        ),
        "four_amplitude_fit_remainder_order": "O(mu_max^6)",
        "maximum_bare_power_mu6": float(np.max(mu) ** 6),
        "finite_amplitude_remainder_coefficient_bounded": False,
    }


def symmetrized_occupation_vertex(
    velocity_vertex: Array,
    output_mode: int,
    internal_wave_number: float,
    complementary_wave_number: float,
    *,
    fourier_points: int,
) -> Array:
    r"""Return the symmetric Fourier vertex of ``-V_ab u_b d_x u_a``.

    With an orthonormal discrete Fourier transform and ``p+q=k``, the
    quadratic force is written

    ``N_a(k)=sum_p Gamma[a,b,c](k,p,q) u_b(p) u_c(q)``.

    Symmetrising the two dummy incoming legs gives

    ``Gamma[a,b,c]=-i[q V_ab delta_ac+p V_ac delta_ab]/(2 sqrt(Nx))``.

    ``output_mode`` selects the component ``a`` and keeps this helper small
    enough for algebraic unit tests.  The deterministic one-loop contraction
    below uses the equivalent expanded formula and never constructs the full
    rank-three tensor for a production GHD operator.
    """

    vertex = np.asarray(velocity_vertex, dtype=float)
    if vertex.ndim != 2 or vertex.shape[0] != vertex.shape[1]:
        raise ValueError("velocity vertex must be square")
    if not 0 <= output_mode < vertex.shape[0]:
        raise ValueError("output mode is outside the retained basis")
    if fourier_points <= 0:
        raise ValueError("fourier_points must be positive")
    modes = vertex.shape[0]
    gamma = np.zeros((modes, modes), dtype=complex)
    a = int(output_mode)
    normalization = 2.0 * np.sqrt(float(fourier_points))
    for b in range(modes):
        gamma[b, a] += (
            -1j * float(complementary_wave_number) * vertex[a, b] / normalization
        )
        gamma[a, b] += (
            -1j * float(internal_wave_number) * vertex[a, b] / normalization
        )
    return gamma


def one_loop_occupation_force_memory(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_vertex: Array,
    projection: Array,
    times: Array,
    *,
    lattice_wave_number: Callable[[float], float] | None = None,
    spatial_cell_length: float = 1.0,
) -> dict[str, Array | float | str | bool]:
    r"""Evaluate the Gaussian one-loop memory of the nonlinear GHD force.

    This is a deterministic Wick contraction, not a trajectory estimate.  For
    the quadratic occupation force

    ``N_a=-V_ab u_b d_x u_a``, the first correction to a two-point function is
    zero because it contains an odd Gaussian moment.  The first non-vanishing
    term is therefore quadratic in ``V``.  If

    ``S_p(t)=exp(L_p t) C``, its force covariance is

    ``M_ad(k,t)=2 sum_p Gamma[a,bc] S_p[b,e] S_q[c,f] Gamma[d,ef]^*``,

    where ``q=k-p`` modulo the Fourier grid.  The implementation expands the
    sparse vertex, reducing the contraction to matrix products and Hadamard
    products.  It returns both ``p^dagger M p/chi`` and the corresponding
    continuity-normalised kernel divided by ``khat^2``.

    Scope is deliberately narrow: it includes the exact dressed-velocity
    vertex at the supplied finite cutoff.  State derivatives of diffusion and
    noise, higher occupation vertices, and the quadratic observable Hessian
    are separate contributions to the complete physical ``F1_perp``.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    vertex = np.asarray(velocity_vertex, dtype=float)
    projection = np.asarray(projection, dtype=complex)
    times = np.asarray(times, dtype=float)
    mode_count = velocity.size
    if waves.ndim != 1 or waves.size < 2:
        raise ValueError("wave_numbers must contain a Fourier grid")
    if not 0 <= external_index < waves.size:
        raise ValueError("external Fourier index is outside the grid")
    if diffusion.shape != (mode_count, mode_count):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or vertex.shape != diffusion.shape:
        raise ValueError("covariance and velocity vertex must match diffusion")
    if projection.shape != (mode_count,):
        raise ValueError("projection has the wrong shape")
    if times.ndim != 1 or np.any(times < 0.0) or np.any(np.diff(times) < 0.0):
        raise ValueError("times must be a non-negative increasing vector")
    if not np.isfinite(spatial_cell_length) or spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    # A Fourier amplitude of a cell-averaged field has covariance C/dx.
    # Keeping this factor explicit exposes the expected UV/coarse-graining
    # dependence of an unrenormalized one-loop hydrodynamic calculation.
    fourier_covariance = covariance / float(spatial_cell_length)

    external_wave = float(waves[external_index])
    khat = (
        external_wave
        if lattice_wave_number is None
        else float(lattice_wave_number(external_wave))
    )
    if khat == 0.0:
        raise ValueError("one-loop continuity normalisation requires k != 0")
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")

    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]
    force_covariances: list[Array] = []
    projected_force: list[complex] = []
    grid_size = waves.size
    for time in times:
        cross_covariances = [
            expm(float(time) * generator) @ fourier_covariance
            for generator in generators
        ]
        total = np.zeros((mode_count, mode_count), dtype=complex)
        for p_index, p_wave in enumerate(waves):
            q_index = (external_index - p_index) % grid_size
            q_wave = float(waves[q_index])
            p_symbol = (
                float(p_wave)
                if lattice_wave_number is None
                else float(lattice_wave_number(float(p_wave)))
            )
            q_symbol = (
                q_wave
                if lattice_wave_number is None
                else float(lattice_wave_number(q_wave))
            )
            s_p = cross_covariances[p_index]
            s_q = cross_covariances[q_index]
            vspv = vertex @ s_p @ vertex.conj().T
            vsqv = vertex @ s_q @ vertex.conj().T
            # Expansion of 2 Gamma (S_p tensor S_q) Gamma^dagger.
            contraction = (
                q_symbol**2 * vspv * s_q
                + q_symbol * p_symbol * (vertex @ s_p) * (s_q @ vertex.conj().T)
                + p_symbol * q_symbol * (s_p @ vertex.conj().T) * (vertex @ s_q)
                + p_symbol**2 * s_p * vsqv
            )
            total += contraction / (2.0 * float(grid_size))
        total = 0.5 * (total + total.conj().T) if time == 0.0 else total
        force_covariances.append(total)
        projected_force.append(
            projection.conj() @ total @ projection / susceptibility
        )
    projected = np.asarray(projected_force)
    continuity_memory = projected / khat**2
    running_markov_correction = np.zeros_like(continuity_memory)
    if times.size > 1:
        increments = 0.5 * (
            continuity_memory[1:] + continuity_memory[:-1]
        ) * np.diff(times)
        running_markov_correction[1:] = np.cumsum(increments)
    zero_time_minimum = float(
        np.min(np.linalg.eigvalsh(np.asarray(force_covariances[0])))
    )
    return {
        "times": times,
        "force_covariances": np.asarray(force_covariances),
        "projected_force_memory": projected,
        "continuity_normalized_memory": continuity_memory,
        "running_markov_diffusion_correction": running_markov_correction,
        "projected_static_susceptibility": float(np.real(susceptibility)),
        "spatial_cell_length": float(spatial_cell_length),
        "unrenormalized_uv_cutoff_dependent": True,
        "zero_time_minimum_eigenvalue": zero_time_minimum,
        "first_order_two_point_correction": 0.0,
        "first_nonzero_velocity_vertex_order": "O(V^2)",
        "trajectory_sampling_used": False,
        "complete_physical_F1_perp": False,
        "omitted_vertices": (
            "state derivatives of diffusion/noise, higher occupation vertices, "
            "and quadratic-observable insertions"
        ),
    }


def one_loop_physical_spin_corrections(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_vertex: Array,
    diffusion_derivative: Array,
    noise_root_derivative: Array,
    spin_projection: Array,
    spin_hessian: Array,
    times: Array,
    *,
    noise_covariance: Array | None = None,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | str]:
    r"""Wick-contract all currently known quadratic physical-spin vertices.

    The force vertex contains the dressed-velocity and state-dependent
    diffusion pieces.  The quadratic spin observable is contracted
    separately.  The derivative of the symmetric FDT noise root gives the
    instantaneous multiplicative-noise memory.  No stochastic trajectories
    or target transport coefficients enter.

    This is still a bare hydrodynamic one-loop object: cancellation of its UV
    dependence and matching to the microscopic Mori moments must be checked,
    not assumed.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    velocity_vertex = np.asarray(velocity_vertex, dtype=float)
    diffusion_derivative = np.asarray(diffusion_derivative, dtype=float)
    noise_root_derivative = np.asarray(noise_root_derivative, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    hessian = np.asarray(spin_hessian, dtype=float)
    times = np.asarray(times, dtype=float)
    supplied_noise = (
        None
        if noise_covariance is None
        else np.asarray(noise_covariance, dtype=complex)
    )
    modes = velocity.size
    if diffusion.shape != (modes, modes):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or velocity_vertex.shape != diffusion.shape:
        raise ValueError("linear matrices have incompatible shapes")
    if diffusion_derivative.shape != (modes, modes, modes):
        raise ValueError("diffusion derivative must have shape (l,i,j)")
    if noise_root_derivative.shape != (modes, modes, modes):
        raise ValueError("noise-root derivative must have shape (l,i,j)")
    if projection.shape != (modes,) or hessian.shape != (modes, modes):
        raise ValueError("spin observable has incompatible dimensions")
    if supplied_noise is not None and supplied_noise.shape != diffusion.shape:
        raise ValueError("noise covariance has the wrong shape")
    if not 0 <= external_index < waves.size or waves.size < 2:
        raise ValueError("external index is outside the Fourier grid")
    if np.any(times < 0.0) or np.any(np.diff(times) < 0.0):
        raise ValueError("times must be non-negative and increasing")
    if spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    grid_size = waves.size
    external_wave = float(waves[external_index])
    khat = (
        external_wave
        if lattice_wave_number is None
        else float(lattice_wave_number(external_wave))
    )
    if khat == 0.0:
        raise ValueError("external wave number must be non-zero")
    fourier_covariance = covariance / float(spatial_cell_length)
    fdt_expected = 0.5 * (
        diffusion @ covariance + covariance @ diffusion.T
    )
    if supplied_noise is None:
        fdt_residual = float("nan")
        full_fdt_retained = False
    else:
        fdt_residual = float(
            np.linalg.norm(supplied_noise - fdt_expected)
            / max(np.linalg.norm(fdt_expected), np.finfo(float).tiny)
        )
        full_fdt_retained = bool(fdt_residual <= 1.0e-10)
        if not full_fdt_retained:
            raise ValueError("noise covariance violates the full FDT identity")
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")

    # R[j,l] = p_a (d D_a,j / d n_l), and Z[l,r] = p_a dB_a,r/dn_l.
    projected_diffusion = np.einsum(
        "a,laj->jl", projection, diffusion_derivative
    )
    projected_noise = np.einsum(
        "a,lar->lr", projection, noise_root_derivative
    )
    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]

    def wick_pair(
        incoming_vertex: Array, s_p: Array, s_q: Array
    ) -> complex:
        left = s_p.T @ incoming_vertex
        right = incoming_vertex.conj() @ s_q.T
        return complex(2.0 * np.sum(left * right))

    velocity_force = []
    diffusion_force = []
    cross_force = []
    total_force = []
    observable = []
    normalization = np.sqrt(float(grid_size))
    observable_vertex = 0.5 * hessian / normalization
    for time in times:
        propagators = [
            expm(float(time) * generator) @ fourier_covariance
            for generator in generators
        ]
        velocity_sum = 0.0j
        diffusion_sum = 0.0j
        cross_sum = 0.0j
        observable_sum = 0.0j
        for p_index, p_wave in enumerate(waves):
            q_index = (external_index - p_index) % grid_size
            q_wave = float(waves[q_index])
            p_symbol = (
                float(p_wave)
                if lattice_wave_number is None
                else float(lattice_wave_number(float(p_wave)))
            )
            q_symbol = (
                q_wave
                if lattice_wave_number is None
                else float(lattice_wave_number(q_wave))
            )
            s_p = propagators[p_index]
            s_q = propagators[q_index]
            velocity_gamma = -0.5j / normalization * (
                q_symbol
                * velocity_vertex.T
                * projection[None, :]
                + p_symbol
                * velocity_vertex
                * projection[:, None]
            )
            diffusion_gamma = -0.25 / normalization * (
                q_symbol**2 * projected_diffusion.T
                + p_symbol**2 * projected_diffusion
            )
            velocity_piece = wick_pair(velocity_gamma, s_p, s_q)
            diffusion_piece = wick_pair(diffusion_gamma, s_p, s_q)
            combined_piece = wick_pair(
                velocity_gamma + diffusion_gamma, s_p, s_q
            )
            velocity_sum += velocity_piece
            diffusion_sum += diffusion_piece
            cross_sum += combined_piece - velocity_piece - diffusion_piece
            observable_sum += wick_pair(observable_vertex, s_p, s_q)
        velocity_force.append(velocity_sum / susceptibility)
        diffusion_force.append(diffusion_sum / susceptibility)
        cross_force.append(cross_sum / susceptibility)
        total_force.append(
            (velocity_sum + diffusion_sum + cross_sum) / susceptibility
        )
        observable.append(observable_sum / susceptibility)

    velocity_force = np.asarray(velocity_force)
    diffusion_force = np.asarray(diffusion_force)
    cross_force = np.asarray(cross_force)
    total_force = np.asarray(total_force)
    observable = np.asarray(observable)
    # The multiplicative-noise vertex is white in time.  This coefficient
    # multiplies delta(t) in the continuity-normalised Mori kernel.
    noise_markov = np.einsum(
        "lr,lm,mr->",
        projected_noise,
        fourier_covariance,
        projected_noise.conj(),
    ) / (float(spatial_cell_length) * susceptibility)
    return {
        "times": times,
        "velocity_force_memory": velocity_force,
        "diffusion_force_memory": diffusion_force,
        "velocity_diffusion_cross_memory": cross_force,
        "total_colored_force_memory": total_force,
        "velocity_continuity_memory": velocity_force / khat**2,
        "diffusion_continuity_memory": diffusion_force / khat**2,
        "cross_continuity_memory": cross_force / khat**2,
        "total_colored_continuity_memory": total_force / khat**2,
        "multiplicative_noise_delta_memory": complex(noise_markov),
        "quadratic_observable_structure_correction": observable,
        "projected_static_susceptibility": float(np.real(susceptibility)),
        "spatial_cell_length": float(spatial_cell_length),
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
        "full_off_diagonal_diffusion_retained": True,
        "full_fdt_noise_covariance_retained": full_fdt_retained,
        "fdt_noise_covariance_relative_residual": fdt_residual,
        "internal_lattice_wave_number_retained": lattice_wave_number is not None,
        "bare_uv_matched_to_microscopic_mori": False,
        "complete_physical_F1_perp": False,
    }


def randomized_diffusion_wick_pair(
    vertex_action: Callable[[Array], Array],
    covariance: Array,
    propagator_p: Array,
    propagator_q: Array,
    p_symbol: float,
    q_symbol: float,
    *,
    fourier_normalization: float,
    samples: int,
    seed: int,
    trace_distribution: str = "gaussian",
) -> dict[str, complex | float | int | str]:
    r"""Estimate one full diffusion-vertex Wick contraction matrix-free.

    Let ``R[j,l]=p_a dD[l,a,j]`` be the physical projected diffusion vertex.
    Only the action ``x -> R x`` is required.  For independent Gaussian or
    Rademacher trace vectors ``x,y`` with equal-time covariance ``C`` and propagated vectors
    ``E_p x,E_q y``, the scalar quadratic force is

    ``f=-1/(4 sqrt(Nx)) [q^2 (R x).T y + p^2 x.T (R y)]``.

    The identity

    ``2 E[f(t) f(0)^*] = 2 sum[(S_p.T Gamma)*(Gamma^* S_q.T)]``

    is exactly the deterministic Wick contraction used by
    :func:`one_loop_physical_spin_corrections`.  Consequently this randomized
    trace estimator avoids both the explicit ``R`` matrix and the rank-three
    ``dD[l,a,j]`` tensor.  Sampling is over auxiliary randomized trace vectors,
    not spin-chain trajectories or target transport data.
    """

    covariance = np.asarray(covariance)
    e_p = np.asarray(propagator_p)
    e_q = np.asarray(propagator_q)
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be square")
    modes = covariance.shape[0]
    if e_p.shape != (modes, modes) or e_q.shape != (modes, modes):
        raise ValueError("propagators must match the covariance")
    if samples < 2:
        raise ValueError("at least two randomized samples are required")
    if not np.isfinite(fourier_normalization) or fourier_normalization <= 0.0:
        raise ValueError("fourier_normalization must be positive")
    if trace_distribution not in {"gaussian", "rademacher"}:
        raise ValueError("trace_distribution must be gaussian or rademacher")
    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    root = (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ (
        eigenvectors.conj().T
    )
    rng = np.random.default_rng(seed)
    if trace_distribution == "gaussian":
        x_trace = rng.normal(size=(modes, samples))
        y_trace = rng.normal(size=(modes, samples))
    else:
        x_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
        y_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
    x_zero = root @ x_trace
    y_zero = root @ y_trace
    x_time = e_p @ x_zero
    y_time = e_q @ y_zero
    coefficient = -0.25 / float(fourier_normalization)

    def forces(left: Array, right: Array) -> Array:
        values = np.empty(samples, dtype=complex)
        for sample in range(samples):
            x = left[:, sample]
            y = right[:, sample]
            r_x = np.asarray(vertex_action(x))
            r_y = np.asarray(vertex_action(y))
            if r_x.shape != (modes,) or r_y.shape != (modes,):
                raise ValueError("vertex_action returned a vector of wrong shape")
            values[sample] = coefficient * (
                float(q_symbol) ** 2 * np.dot(r_x, y)
                + float(p_symbol) ** 2 * np.dot(x, r_y)
            )
        return values

    force_zero = forces(x_zero, y_zero)
    force_time = forces(x_time, y_time)
    products = 2.0 * force_time * force_zero.conj()
    estimate = complex(np.mean(products))
    centered = products - estimate
    standard_error = float(
        np.sqrt(
            np.mean(centered.real**2 + centered.imag**2)
            / float(samples)
        )
    )
    return {
        "estimate": estimate,
        "standard_error_complex_norm": standard_error,
        "samples": int(samples),
        "seed": int(seed),
        "trace_distribution": trace_distribution,
        "method": "matrix_free_randomized_wick_trace",
    }


def randomized_noise_contact_trace(
    vertex_transpose_action: Callable[[Array], Array],
    covariance: Array,
    *,
    samples: int,
    seed: int,
    trace_distribution: str = "rademacher",
) -> dict[str, float | int | str]:
    r"""Estimate ``Tr[Z^dagger C Z]`` from ``x -> Z.T x`` actions.

    This is the matrix-free contraction entering the instantaneous
    multiplicative-FDT-noise memory.  Only second moments of the independent
    auxiliary trace vectors are used, so Gaussian and Rademacher choices are
    both unbiased.  The result is the raw trace; hydrodynamic cell-length and
    susceptibility normalizations remain the caller's responsibility.
    """

    covariance = np.asarray(covariance)
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be square")
    if samples < 2:
        raise ValueError("at least two randomized samples are required")
    if trace_distribution not in {"gaussian", "rademacher"}:
        raise ValueError("trace_distribution must be gaussian or rademacher")
    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    root = (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ (
        eigenvectors.conj().T
    )
    rng = np.random.default_rng(seed)
    if trace_distribution == "gaussian":
        trace = rng.normal(size=(covariance.shape[0], samples))
    else:
        trace = 2.0 * rng.integers(
            0, 2, size=(covariance.shape[0], samples)
        ) - 1.0
    vectors = root @ trace
    values = np.empty(samples, dtype=float)
    for sample in range(samples):
        image = np.asarray(vertex_transpose_action(vectors[:, sample]))
        values[sample] = float(np.vdot(image, image).real)
    estimate = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / np.sqrt(samples))
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "samples": int(samples),
        "seed": int(seed),
        "trace_distribution": trace_distribution,
        "method": "matrix_free_randomized_multiplicative_noise_contact",
    }


def randomized_full_vector_multiplicative_noise_contact(
    noise_root_directional_action: Callable[[Array], Array],
    covariance: Array,
    *,
    samples: int,
    seed: int,
    trace_distribution: str = "rademacher",
) -> dict[str, object]:
    r"""Estimate the full mode-space contact from ``dB[u] xi``.

    ``noise_root_directional_action(u)`` returns the complete matrix
    directional derivative of the symmetric FDT root ``B``.  An auxiliary
    vector ``u`` with covariance ``C`` and exact contraction of the white-noise
    index give

    ``N_contact=E[(dB[u] xi)(dB[u] xi)^dagger]``.

    Thus ``g^dagger N_contact g`` is exactly the projected trace
    ``E[||dB[u]^dagger g||^2]``.  The estimator retains the full output mode
    matrix and streams its outer products, so no rank-three ``dB`` tensor or
    ``samples x N x N`` array is stored.  Hydrodynamic cell, wave-number, and
    microscopic Mori contact normalizations remain the caller's responsibility.
    """

    covariance = np.asarray(covariance)
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be square")
    modes = covariance.shape[0]
    if samples < 2:
        raise ValueError("at least two randomized samples are required")
    if trace_distribution not in {"gaussian", "rademacher"}:
        raise ValueError("trace_distribution must be gaussian or rademacher")
    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    root = (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ (
        eigenvectors.conj().T
    )
    rng = np.random.default_rng(seed)
    if trace_distribution == "gaussian":
        occupation_trace = rng.normal(size=(modes, samples))
    else:
        occupation_trace = 2.0 * rng.integers(
            0, 2, size=(modes, samples)
        ) - 1.0
    occupations = root @ occupation_trace
    contact_sum = np.zeros((modes, modes), dtype=complex)
    squared_frobenius_sum = 0.0
    for sample in range(samples):
        derivative = np.asarray(
            noise_root_directional_action(occupations[:, sample])
        )
        if derivative.shape != (modes, modes):
            raise ValueError("noise-root directional action returned a wrong matrix")
        # Contract the white-noise index analytically.  Sampling it would add
        # variance without reducing the directional-derivative cost.
        product = derivative @ derivative.conj().T
        contact_sum += product
        squared_frobenius_sum += float(np.vdot(product, product).real)
    estimate = contact_sum / float(samples)
    centered_sum = max(
        0.0,
        squared_frobenius_sum
        - float(samples) * float(np.vdot(estimate, estimate).real),
    )
    return {
        "matrix_estimate": estimate,
        "frobenius_standard_error": float(
            np.sqrt(centered_sum) / float(samples)
        ),
        "samples": int(samples),
        "seed": int(seed),
        "trace_distribution": trace_distribution,
        "rank_three_noise_root_vertex_stored": False,
        "method": "matrix_free_randomized_full_vector_noise_contact",
    }


def randomized_velocity_diffusion_wick_pair(
    velocity_vertex_action: Callable[[Array], Array],
    diffusion_vertex_action: Callable[[Array], Array],
    covariance: Array,
    propagator_p: Array,
    propagator_q: Array,
    p_symbol: float,
    q_symbol: float,
    *,
    fourier_normalization: float,
    samples: int,
    seed: int,
    trace_distribution: str = "rademacher",
) -> dict[str, object]:
    r"""Estimate velocity, diffusion, and cross Wick memories together.

    ``velocity_vertex_action`` applies ``M=diag(projection) V`` and
    ``diffusion_vertex_action`` applies the projected derivative ``R``.  The
    same independent trace-vector pairs are used for all four returned
    contractions, so the velocity--diffusion cross term is obtained without
    subtracting statistically independent noisy estimates.
    """

    covariance = np.asarray(covariance)
    propagator_p = np.asarray(propagator_p)
    propagator_q = np.asarray(propagator_q)
    modes = covariance.shape[0]
    if covariance.shape != (modes, modes):
        raise ValueError("covariance must be square")
    if propagator_p.shape != covariance.shape or propagator_q.shape != covariance.shape:
        raise ValueError("propagators must match covariance")
    if samples < 2:
        raise ValueError("at least two randomized samples are required")
    if trace_distribution not in {"gaussian", "rademacher"}:
        raise ValueError("trace_distribution must be gaussian or rademacher")
    if fourier_normalization <= 0.0:
        raise ValueError("fourier_normalization must be positive")

    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    root = (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ eigenvectors.conj().T
    rng = np.random.default_rng(seed)
    if trace_distribution == "gaussian":
        x_trace = rng.normal(size=(modes, samples))
        y_trace = rng.normal(size=(modes, samples))
    else:
        x_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
        y_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
    x_zero = root @ x_trace
    y_zero = root @ y_trace
    x_time = propagator_p @ x_zero
    y_time = propagator_q @ y_zero
    velocity_coefficient = -0.5j / float(fourier_normalization)
    diffusion_coefficient = -0.25 / float(fourier_normalization)

    def forces(left: Array, right: Array) -> tuple[Array, Array]:
        velocity_force = np.empty(samples, dtype=complex)
        diffusion_force = np.empty(samples, dtype=complex)
        for sample in range(samples):
            x = left[:, sample]
            y = right[:, sample]
            v_x = np.asarray(velocity_vertex_action(x))
            v_y = np.asarray(velocity_vertex_action(y))
            d_x = np.asarray(diffusion_vertex_action(x))
            d_y = np.asarray(diffusion_vertex_action(y))
            if any(image.shape != (modes,) for image in (v_x, v_y, d_x, d_y)):
                raise ValueError("vertex action returned a vector of wrong shape")
            velocity_force[sample] = velocity_coefficient * (
                float(q_symbol) * np.dot(v_x, y)
                + float(p_symbol) * np.dot(x, v_y)
            )
            diffusion_force[sample] = diffusion_coefficient * (
                float(q_symbol) ** 2 * np.dot(d_x, y)
                + float(p_symbol) ** 2 * np.dot(x, d_y)
            )
        return velocity_force, diffusion_force

    velocity_zero, diffusion_zero = forces(x_zero, y_zero)
    velocity_time, diffusion_time = forces(x_time, y_time)
    products = {
        "velocity": 2.0 * velocity_time * velocity_zero.conj(),
        "diffusion": 2.0 * diffusion_time * diffusion_zero.conj(),
        "cross": 2.0
        * (
            velocity_time * diffusion_zero.conj()
            + diffusion_time * velocity_zero.conj()
        ),
    }
    products["total"] = products["velocity"] + products["diffusion"] + products["cross"]
    estimates: dict[str, complex] = {}
    errors: dict[str, float] = {}
    for name, values in products.items():
        estimate = complex(np.mean(values))
        centered = values - estimate
        estimates[name] = estimate
        errors[name] = float(
            np.sqrt(np.mean(centered.real**2 + centered.imag**2) / float(samples))
        )
    return {
        "estimates": estimates,
        "standard_error_complex_norms": errors,
        "samples": int(samples),
        "seed": int(seed),
        "trace_distribution": trace_distribution,
        "method": "matrix_free_randomized_velocity_diffusion_wick_trace",
    }


def randomized_full_vector_velocity_diffusion_wick_pair(
    velocity_vertex: Array,
    diffusion_directional_action: Callable[[Array], Array],
    covariance: Array,
    propagator_p: Array,
    propagator_q: Array,
    p_symbol: float,
    q_symbol: float,
    *,
    fourier_normalization: float,
    samples: int,
    seed: int,
    trace_distribution: str = "rademacher",
    return_low_rank_factors: bool = False,
) -> dict[str, object]:
    r"""Estimate the complete mode-space quadratic-force covariance.

    Unlike :func:`randomized_velocity_diffusion_wick_pair`, no physical-spin
    output projection is taken.  For incoming occupation vectors ``x,y`` the
    vector-valued forces are

    ``fV_a=-i/(2 sqrt(Nx))[q (Vx)_a y_a+p x_a(Vy)_a]``

    and

    ``fD=-1/(4 sqrt(Nx))[q^2 dD[x] y+p^2 dD[y] x]``.

    Averaging ``2 f(t) f(0)^dagger`` gives the full matrix needed by a
    matrix-valued Dyson/mode-coupling equation.  Each directional derivative
    stores only one dense ``N_mode x N_mode`` matrix; the rank-three diffusion
    vertex is never formed.
    """

    vertex = np.asarray(velocity_vertex)
    covariance = np.asarray(covariance)
    propagator_p = np.asarray(propagator_p)
    propagator_q = np.asarray(propagator_q)
    modes = covariance.shape[0]
    if any(
        array.shape != (modes, modes)
        for array in (vertex, covariance, propagator_p, propagator_q)
    ):
        raise ValueError("velocity, covariance, and propagators must be square and matching")
    if samples < 2 or fourier_normalization <= 0.0:
        raise ValueError("need at least two samples and positive Fourier normalization")
    if trace_distribution not in {"gaussian", "rademacher"}:
        raise ValueError("trace_distribution must be gaussian or rademacher")

    hermitian = 0.5 * (covariance + covariance.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    if float(np.min(eigenvalues)) < -1.0e-11 * scale:
        raise ValueError("covariance must be positive semidefinite")
    root = (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ (
        eigenvectors.conj().T
    )
    rng = np.random.default_rng(seed)
    if trace_distribution == "gaussian":
        x_trace = rng.normal(size=(modes, samples))
        y_trace = rng.normal(size=(modes, samples))
    else:
        x_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
        y_trace = 2.0 * rng.integers(0, 2, size=(modes, samples)) - 1.0
    x_zero = root @ x_trace
    y_zero = root @ y_trace
    x_time = propagator_p @ x_zero
    y_time = propagator_q @ y_zero
    velocity_coefficient = -0.5j / float(fourier_normalization)
    diffusion_coefficient = -0.25 / float(fourier_normalization)

    def forces(left: Array, right: Array) -> tuple[Array, Array]:
        velocity_force = np.empty((modes, samples), dtype=complex)
        diffusion_force = np.empty((modes, samples), dtype=complex)
        for sample in range(samples):
            x = left[:, sample]
            y = right[:, sample]
            d_x = np.asarray(diffusion_directional_action(x))
            d_y = np.asarray(diffusion_directional_action(y))
            if d_x.shape != (modes, modes) or d_y.shape != (modes, modes):
                raise ValueError("diffusion directional action returned a wrong matrix")
            velocity_force[:, sample] = velocity_coefficient * (
                float(q_symbol) * (vertex @ x) * y
                + float(p_symbol) * x * (vertex @ y)
            )
            diffusion_force[:, sample] = diffusion_coefficient * (
                float(q_symbol) ** 2 * (d_x @ y)
                + float(p_symbol) ** 2 * (d_y @ x)
            )
        return velocity_force, diffusion_force

    velocity_zero, diffusion_zero = forces(x_zero, y_zero)
    velocity_time, diffusion_time = forces(x_time, y_time)
    components = {
        "velocity": (velocity_time, velocity_zero),
        "diffusion": (diffusion_time, diffusion_zero),
        "total": (
            velocity_time + diffusion_time,
            velocity_zero + diffusion_zero,
        ),
    }
    matrices = {}
    frobenius_standard_errors = {}

    def streamed_outer_statistics(
        left: Array, right: Array
    ) -> tuple[Array, float]:
        # Accumulate only an N x N matrix and a scalar second moment.  Forming
        # samples x N x N products would defeat the matrix-free construction
        # for the hundreds of modes needed in the giant-string limit.
        product_sum = np.zeros((modes, modes), dtype=complex)
        squared_frobenius_sum = 0.0
        for sample in range(samples):
            product = 2.0 * np.outer(
                left[:, sample], right[:, sample].conj()
            )
            product_sum += product
            squared_frobenius_sum += float(np.vdot(product, product).real)
        estimate = product_sum / float(samples)
        centered_sum = max(
            0.0,
            squared_frobenius_sum
            - float(samples) * float(np.vdot(estimate, estimate).real),
        )
        return estimate, float(np.sqrt(centered_sum) / float(samples))

    for name, (time_force, zero_force) in components.items():
        estimate, standard_error = streamed_outer_statistics(
            time_force, zero_force
        )
        matrices[name] = estimate
        frobenius_standard_errors[name] = standard_error
    matrices["cross"] = matrices["total"] - matrices["velocity"] - matrices["diffusion"]
    # The cross error is not obtained by subtracting independent estimators;
    # all components share the same samples.  Accumulate the paired cross
    # products directly, again without a samples x N x N temporary.
    cross_sum = np.zeros((modes, modes), dtype=complex)
    cross_squared_frobenius_sum = 0.0
    for sample in range(samples):
        product = 2.0 * (
            np.outer(
                velocity_time[:, sample], diffusion_zero[:, sample].conj()
            )
            + np.outer(
                diffusion_time[:, sample], velocity_zero[:, sample].conj()
            )
        )
        cross_sum += product
        cross_squared_frobenius_sum += float(np.vdot(product, product).real)
    cross_estimate = cross_sum / float(samples)
    matrices["cross"] = cross_estimate
    cross_centered_sum = max(
        0.0,
        cross_squared_frobenius_sum
        - float(samples) * float(np.vdot(cross_estimate, cross_estimate).real),
    )
    frobenius_standard_errors["cross"] = float(
        np.sqrt(cross_centered_sum) / float(samples)
    )
    result = {
        "matrix_estimates": matrices,
        "frobenius_standard_errors": frobenius_standard_errors,
        "samples": int(samples),
        "seed": int(seed),
        "trace_distribution": trace_distribution,
        "rank_three_diffusion_vertex_stored": False,
        "method": "matrix_free_randomized_full_vector_velocity_diffusion_wick",
    }
    if return_low_rank_factors:
        scale_factor = np.sqrt(2.0 / float(samples))
        result["total_low_rank_left_factor"] = scale_factor * (
            velocity_time + diffusion_time
        )
        result["total_low_rank_right_factor"] = scale_factor * (
            velocity_zero + diffusion_zero
        )
    return result


def randomized_symmetric_quadratic_wick_pair(
    hessian_action: Callable[[Array], Array],
    covariance: Array,
    propagator_p: Array,
    propagator_q: Array,
    *,
    fourier_normalization: float,
    samples: int,
    seed: int,
    trace_distribution: str = "rademacher",
) -> dict[str, float | int | str | complex]:
    r"""Estimate the Wick pair of ``u.T H u/(2 sqrt(Nx))``.

    For symmetric ``H`` this is algebraically the diffusion trace estimator
    with both wave-number factors set to one.  Its force convention differs by
    an overall sign, which cancels in the two-vertex correlation.
    """

    result = randomized_diffusion_wick_pair(
        hessian_action,
        covariance,
        propagator_p,
        propagator_q,
        1.0,
        1.0,
        fourier_normalization=fourier_normalization,
        samples=samples,
        seed=seed,
        trace_distribution=trace_distribution,
    )
    result["method"] = "matrix_free_randomized_symmetric_quadratic_wick_trace"
    return result


def one_loop_colored_memory_derivatives_at_zero(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_vertex: Array,
    diffusion_derivative: Array,
    spin_projection: Array,
    *,
    maximum_order: int,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | int]:
    r"""Return exact zero-time derivatives of the colored one-loop memory.

    For each loop momentum, the Gaussian contraction is bilinear in
    ``S_p(t)=exp(L_p t) C`` and ``S_q(t)=exp(L_q t) C``.  Leibniz' rule gives

    ``M^(n)(0)=sum_r binomial(n,r) W[L_p^r C,L_q^(n-r) C]``.

    Matrix powers are evaluated directly, so no finite-difference time fit is
    used.  The white ``B'B' delta(t)`` contact is deliberately excluded; its
    large-``z`` constant must be cancelled separately when matching to a
    regular microscopic Mori kernel.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    vertex = np.asarray(velocity_vertex, dtype=float)
    diffusion_derivative = np.asarray(diffusion_derivative, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    modes = velocity.size
    if not isinstance(maximum_order, (int, np.integer)) or maximum_order < 0:
        raise ValueError("maximum_order must be a non-negative integer")
    if waves.ndim != 1 or waves.size < 2 or not 0 <= external_index < waves.size:
        raise ValueError("invalid Fourier grid or external index")
    if diffusion.shape != (modes, modes):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or vertex.shape != diffusion.shape:
        raise ValueError("linear matrices have incompatible shapes")
    if diffusion_derivative.shape != (modes, modes, modes):
        raise ValueError("diffusion derivative must have shape (l,i,j)")
    if projection.shape != (modes,):
        raise ValueError("spin projection has the wrong shape")
    if spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    external_wave = float(waves[external_index])
    khat = (
        external_wave
        if lattice_wave_number is None
        else float(lattice_wave_number(external_wave))
    )
    if khat == 0.0:
        raise ValueError("external wave number must be non-zero")
    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")
    projected_diffusion = np.einsum(
        "a,laj->jl", projection, diffusion_derivative
    )
    normalization = np.sqrt(float(waves.size))
    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]
    propagated_powers: list[list[Array]] = []
    for generator in generators:
        sequence = [fourier_covariance]
        for _ in range(maximum_order):
            sequence.append(generator @ sequence[-1])
        propagated_powers.append(sequence)

    def wick_pair(gamma: Array, left_covariance: Array, right_covariance: Array) -> complex:
        left = left_covariance.T @ gamma
        right = gamma.conj() @ right_covariance.T
        return complex(2.0 * np.sum(left * right))

    derivatives = np.zeros(maximum_order + 1, dtype=complex)
    for p_index, p_wave in enumerate(waves):
        q_index = (external_index - p_index) % waves.size
        q_wave = float(waves[q_index])
        p_symbol = (
            float(p_wave)
            if lattice_wave_number is None
            else float(lattice_wave_number(float(p_wave)))
        )
        q_symbol = (
            q_wave
            if lattice_wave_number is None
            else float(lattice_wave_number(q_wave))
        )
        velocity_gamma = -0.5j / normalization * (
            q_symbol * vertex.T * projection[None, :]
            + p_symbol * vertex * projection[:, None]
        )
        diffusion_gamma = -0.25 / normalization * (
            q_symbol**2 * projected_diffusion.T
            + p_symbol**2 * projected_diffusion
        )
        gamma = velocity_gamma + diffusion_gamma
        for order in range(maximum_order + 1):
            value = 0.0j
            for left_order in range(order + 1):
                value += math.comb(order, left_order) * wick_pair(
                    gamma,
                    propagated_powers[p_index][left_order],
                    propagated_powers[q_index][order - left_order],
                )
            derivatives[order] += value / susceptibility
    return {
        "maximum_order": int(maximum_order),
        "total_colored_force_derivatives": derivatives,
        "total_colored_continuity_derivatives": derivatives / khat**2,
        "white_noise_contact_included": False,
        "analytic_matrix_power_evaluation": True,
        "internal_lattice_wave_number_retained": lattice_wave_number is not None,
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
    }


def cubic_velocity_tadpole_counterterm(
    velocity_hessian: Array,
    covariance: Array,
    *,
    spatial_cell_length: float = 1.0,
) -> dict[str, Array | float | bool | str]:
    r"""Normal-order the cubic dressed-velocity force at equilibrium.

    Expanding ``v_A[u]`` through second order gives

    ``(1/2) W_A,BC u_B u_C partial_x u_A``.

    At a spatial cell the equal-point covariance is ``C/dx``.  The only
    one-cubic-vertex contribution to a two-point function is a Wick tadpole.
    For a parity-symmetric Fourier regulator the contractions containing
    ``<u_B partial_x u_A>`` vanish, leaving the diagonal velocity shift

    ``delta v_A = W_A,BC C_BC/(2 dx)``.

    Defining the hydrodynamic expansion in equilibrium Wick-ordered fields
    adds the equal and opposite linear counterterm.  The function returns both
    pieces rather than silently discarding either.  This closes the
    first-order cubic tadpole algebra at a finite regulator; it does not by
    itself perform the remaining microscopic UV matching of quadratic loops.
    """

    hessian = np.asarray(velocity_hessian, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    if hessian.ndim != 3 or hessian.shape[0] != hessian.shape[1]:
        raise ValueError("velocity hessian must have shape (A,B,C)")
    if hessian.shape[1] != hessian.shape[2]:
        raise ValueError("velocity hessian derivative axes are incompatible")
    if covariance.shape != hessian.shape[1:]:
        raise ValueError("covariance has incompatible dimensions")
    if spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")
    schwarz_residual = np.linalg.norm(hessian - np.swapaxes(hessian, 1, 2)) / max(
        np.linalg.norm(hessian), np.finfo(float).tiny
    )
    tadpole = 0.5 * np.einsum("abc,bc->a", hessian, covariance)
    tadpole /= float(spatial_cell_length)
    counterterm = -tadpole
    residual = tadpole + counterterm
    return {
        "bare_cubic_tadpole_velocity_shift": tadpole,
        "equilibrium_normal_ordering_counterterm": counterterm,
        "renormalized_first_order_velocity_shift": residual,
        "maximum_absolute_cancellation_residual": float(np.max(np.abs(residual))),
        "velocity_hessian_schwarz_relative_residual": float(schwarz_residual),
        "one_cubic_vertex_two_point_correction_after_normal_ordering": 0.0,
        "equilibrium_wick_ordering_used": True,
        "parity_symmetric_fourier_regulator_required": True,
        "microscopic_uv_matching_complete": False,
        "remaining_matching": (
            "moment-preserving matching of quadratic colored/contact diagrams "
            "and the joint zero-field giant-string limit"
        ),
    }


def cubic_diffusion_noise_tadpole_counterterms(
    diffusion_second_diagonal_derivative: Array,
    noise_root_second_diagonal_derivative: Array,
    covariance: Array,
    *,
    spatial_cell_length: float = 1.0,
) -> dict[str, Array | float | bool | str]:
    r"""Normal-order the cubic diffusion and conservative-noise vertices.

    With diagonal nodal equilibrium covariance, the contractions required by
    a single second-state-derivative vertex are

    ``delta D_AB = (1/(2 dx)) sum_c D''_{AB;cc} C_cc`` and
    ``delta B_Ar = (1/(2 dx)) sum_c B''_{Ar;cc} C_cc``.

    Equilibrium Wick ordering supplies their equal and opposite linear/additive
    counterterms.  The separate ``B' B'`` multiplicative-noise contact is not
    removed here; it is a genuine quadratic loop already included by
    :func:`one_loop_physical_spin_corrections`.
    """

    diffusion_second = np.asarray(diffusion_second_diagonal_derivative, dtype=float)
    noise_second = np.asarray(noise_root_second_diagonal_derivative, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    if diffusion_second.ndim != 3 or noise_second.ndim != 3:
        raise ValueError("second diagonal derivatives must be rank three")
    modes = covariance.shape[0]
    if covariance.shape != (modes, modes):
        raise ValueError("covariance must be square")
    if diffusion_second.shape != (modes, modes, modes):
        raise ValueError("diffusion second derivative has incompatible shape")
    if noise_second.shape[0] != modes or noise_second.shape[1] != modes:
        raise ValueError("noise-root second derivative has incompatible shape")
    if spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")
    weights = np.diag(covariance) / (2.0 * float(spatial_cell_length))
    diffusion_tadpole = np.einsum("c,cab->ab", weights, diffusion_second)
    noise_tadpole = np.einsum("c,car->ar", weights, noise_second)
    diffusion_counterterm = -diffusion_tadpole
    noise_counterterm = -noise_tadpole
    diffusion_residual = diffusion_tadpole + diffusion_counterterm
    noise_residual = noise_tadpole + noise_counterterm
    return {
        "bare_cubic_diffusion_tadpole": diffusion_tadpole,
        "diffusion_normal_ordering_counterterm": diffusion_counterterm,
        "renormalized_first_order_diffusion_shift": diffusion_residual,
        "bare_cubic_noise_root_tadpole": noise_tadpole,
        "noise_root_normal_ordering_counterterm": noise_counterterm,
        "renormalized_first_order_noise_root_shift": noise_residual,
        "maximum_diffusion_cancellation_residual": float(
            np.max(np.abs(diffusion_residual))
        ),
        "maximum_noise_root_cancellation_residual": float(
            np.max(np.abs(noise_residual))
        ),
        "multiplicative_Bprime_Bprime_contact_removed": False,
        "equilibrium_wick_ordering_used": True,
        "microscopic_uv_matching_complete": False,
    }


def normal_ordered_cubic_velocity_force_memory(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_hessian: Array,
    spin_projection: Array,
    times: Array,
    *,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | str]:
    r"""Wick-contract the first nonzero ``W^2`` cubic-force memory.

    The normal-ordered cubic advective force is generated by

    ``(1/2) W_A,BC u_B u_C partial_x u_A``.

    After projection onto physical spin its fully symmetric Fourier vertex is

    ``J_IJK=-i/(6 N_x) [r p_K W_K,IJ + q p_J W_J,IK + p p_I W_I,JK]``.

    One cubic vertex gives only the tadpole removed by equilibrium Wick
    ordering.  Two vertices give six cross-time Wick pairings and hence a
    genuine colored contribution.  The routine evaluates that deterministic
    six-point contraction without stochastic trajectories.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    hessian = np.asarray(velocity_hessian, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    times = np.asarray(times, dtype=float)
    modes = velocity.size
    grid_size = waves.size
    if diffusion.shape != (modes, modes) or covariance.shape != (modes, modes):
        raise ValueError("linear operators have incompatible shapes")
    if hessian.shape != (modes, modes, modes):
        raise ValueError("velocity hessian must have shape (A,B,C)")
    if projection.shape != (modes,):
        raise ValueError("spin projection has incompatible shape")
    if not 0 <= external_index < grid_size or grid_size < 2:
        raise ValueError("external index is outside Fourier grid")
    if np.any(times < 0.0) or np.any(np.diff(times) < 0.0):
        raise ValueError("times must be non-negative and increasing")
    if spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")
    khat = float(waves[external_index])
    if lattice_wave_number is not None:
        khat = float(lattice_wave_number(khat))
    if khat == 0.0:
        raise ValueError("external wave number must be non-zero")
    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")

    # Cache the symmetric cubic vertex for every ordered momentum triplet.
    vertices: dict[tuple[int, int], Array] = {}
    normalization = float(grid_size)
    for p_index, p_wave in enumerate(waves):
        for q_index, q_wave in enumerate(waves):
            r_index = (external_index - p_index - q_index) % grid_size
            r_wave = float(waves[r_index])
            # Remove wrapped cubic aliases.  Without this condition the
            # symmetrized derivative momenta need not add to the external
            # wave, and the three equivalent placements cease to be equal.
            if not np.isclose(
                float(p_wave) + float(q_wave) + r_wave,
                float(waves[external_index]),
                rtol=0.0,
                atol=1.0e-12,
            ):
                continue
            first = (
                r_wave
                * projection[:, None, None]
                * hessian.transpose(0, 1, 2)
            )
            # first[K,I,J] -> J[I,J,K]
            first = first.transpose(1, 2, 0)
            second = (
                q_wave
                * projection[None, :, None]
                * hessian.transpose(1, 0, 2)
            )
            # second[I,J,K] already has output J and derivative I,K.
            third = (
                p_wave
                * projection[:, None, None]
                * hessian
            )
            vertex_tensor = -1.0j * (first + second + third) / (6.0 * normalization)
            vertices[(p_index, q_index)] = vertex_tensor

    generators = [
        linear_ghd_generator(float(wave), velocity, diffusion) for wave in waves
    ]
    projected_memory = []
    for time in times:
        structures = [
            expm(float(time) * generator) @ fourier_covariance
            for generator in generators
        ]
        total = 0.0j
        for p_index, q_index in vertices:
            r_index = (external_index - p_index - q_index) % grid_size
            vertex_tensor = vertices[(p_index, q_index)]
            transformed = np.einsum(
                "ia,jb,kc,abc->ijk",
                structures[p_index],
                structures[q_index],
                structures[r_index],
                vertex_tensor.conj(),
                optimize=True,
            )
            total += 6.0 * np.einsum(
                "ijk,ijk->", vertex_tensor, transformed, optimize=True
            )
        projected_memory.append(total / susceptibility)
    projected_memory = np.asarray(projected_memory)
    return {
        "times": times,
        "projected_cubic_force_memory": projected_memory,
        "continuity_normalized_cubic_memory": projected_memory / khat**2,
        "zero_time_nonnegative": bool(np.real(projected_memory[0]) >= -1.0e-12),
        "first_order_cubic_correction_after_normal_ordering": 0.0,
        "first_nonzero_cubic_order": "O(W^2)",
        "wick_cross_pairings": 6,
        "dealiased_ordered_momentum_triplets": len(vertices),
        "wrapped_cubic_aliases_removed": True,
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
        "microscopic_uv_matching_complete": False,
    }


def mixed_quadratic_dynamics_observable_correction(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_vertex: Array,
    diffusion_derivative: Array,
    spin_projection: Array,
    spin_hessian: Array,
    integration_times: Array,
    output_times: Array,
    *,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | str]:
    r"""Evaluate the deterministic mixed ``Gamma H`` structure correction.

    Write the quadratic deterministic GHD vertex as
    ``Gamma=Gamma_V+Gamma_D`` and expand the Gaussian reference solution by
    Duhamel's formula,

    ``u2_k(t)=int_0^t G_k(t-s) sum_p Gamma(k,p,k-p)[u1_p,u1_k-p] ds``.

    For the physical observable
    ``m_k=p.u_k+(2 sqrt(N))^-1 sum_p H[u_p,u_k-p]+...``, all terms containing
    one ``Gamma`` and one ``H`` are

    ``<p.u2(t), H[u1,u1](0)/2> + <H[u1,u2](t), p.u1(0)>``.

    The routine performs the four-field Wick contractions and the remaining
    causal time integral exactly on a uniform supplied grid.  The quadratic
    force is normal ordered, so the zero-wave equilibrium tadpole is removed;
    that tadpole belongs to the cubic/counterterm matching problem.  State-
    dependent multiplicative-noise/observable contact diagrams are likewise
    not included here.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    vertex = np.asarray(velocity_vertex, dtype=float)
    diffusion_derivative = np.asarray(diffusion_derivative, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    hessian = np.asarray(spin_hessian, dtype=float)
    integration_times = np.asarray(integration_times, dtype=float)
    output_times = np.asarray(output_times, dtype=float)
    modes = velocity.size
    grid_size = waves.size
    if waves.ndim != 1 or grid_size < 2 or not 0 <= external_index < grid_size:
        raise ValueError("invalid Fourier grid or external index")
    if diffusion.shape != (modes, modes):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or vertex.shape != diffusion.shape:
        raise ValueError("linear matrices have incompatible shapes")
    if diffusion_derivative.shape != (modes, modes, modes):
        raise ValueError("diffusion derivative must have shape (l,i,j)")
    if projection.shape != (modes,) or hessian.shape != (modes, modes):
        raise ValueError("physical observable has incompatible dimensions")
    if not np.allclose(hessian, hessian.T, atol=1.0e-12):
        raise ValueError("spin Hessian must be symmetric")
    if (
        integration_times.ndim != 1
        or integration_times.size < 2
        or not np.isclose(integration_times[0], 0.0)
        or np.any(np.diff(integration_times) <= 0.0)
        or not np.allclose(
            np.diff(integration_times),
            integration_times[1] - integration_times[0],
            rtol=1.0e-10,
            atol=1.0e-14,
        )
    ):
        raise ValueError("integration_times must be a uniform grid from zero")
    if output_times.ndim != 1 or np.any(output_times < 0.0):
        raise ValueError("output_times must be a non-negative vector")
    step = float(integration_times[1] - integration_times[0])
    output_indices = np.rint(output_times / step).astype(int)
    if (
        np.any(output_indices < 0)
        or np.any(output_indices >= integration_times.size)
        or not np.allclose(output_times, integration_times[output_indices])
    ):
        raise ValueError("every output time must lie on the integration grid")
    if not np.isfinite(spatial_cell_length) or spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")
    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]
    transitions = np.asarray(
        [
            [expm(float(time) * generator) for generator in generators]
            for time in integration_times
        ]
    )
    cross = transitions @ fourier_covariance
    normalization = np.sqrt(float(grid_size))

    def wave_symbol(wave: float) -> float:
        return (
            float(wave)
            if lattice_wave_number is None
            else float(lattice_wave_number(float(wave)))
        )

    def projected_gamma(
        output_row: Array, p_wave: float, q_wave: float
    ) -> tuple[Array, Array]:
        velocity_gamma = -0.5j / normalization * (
            q_wave * vertex.T * output_row[None, :]
            + p_wave * vertex * output_row[:, None]
        )
        projected_diffusion = np.einsum(
            "a,laj->jl", output_row, diffusion_derivative
        )
        diffusion_gamma = -0.25 / normalization * (
            q_wave**2 * projected_diffusion.T
            + p_wave**2 * projected_diffusion
        )
        return velocity_gamma, diffusion_gamma

    def propagated_endpoint_contraction(
        propagated_hessian: Array,
        first_cross: Array,
        second_vector: Array,
        p_wave: float,
        q_wave: float,
    ) -> tuple[complex, complex]:
        # P[c,B]=sum_a <u_a(t)u_c(s)> H_ab G_bB(t-s).
        contracted = first_cross.T @ propagated_hessian
        velocity_value = -0.5j / normalization * (
            q_wave
            * np.einsum(
                "cB,Bc,B->", contracted, vertex, second_vector, optimize=True
            )
            + p_wave
            * np.diag(contracted)
            @ (vertex @ second_vector)
        )
        diffusion_value = -0.25 / normalization * (
            q_wave**2
            * np.einsum(
                "cB,cBd,d->",
                contracted,
                diffusion_derivative,
                second_vector,
                optimize=True,
            )
            + p_wave**2
            * np.einsum(
                "cB,dBc,d->",
                contracted,
                diffusion_derivative,
                second_vector,
                optimize=True,
            )
        )
        return complex(velocity_value), complex(diffusion_value)

    initial_endpoint_velocity = []
    initial_endpoint_diffusion = []
    final_endpoint_velocity = []
    final_endpoint_diffusion = []
    total_values = []
    external_wave = float(waves[external_index])
    for output_index in output_indices:
        if output_index == 0:
            initial_endpoint_velocity.append(0.0j)
            initial_endpoint_diffusion.append(0.0j)
            final_endpoint_velocity.append(0.0j)
            final_endpoint_diffusion.append(0.0j)
            total_values.append(0.0j)
            continue
        integrands = np.zeros((4, output_index + 1), dtype=complex)
        for s_index in range(output_index + 1):
            delay_index = output_index - s_index
            output_row = projection.conj() @ transitions[
                delay_index, external_index
            ]
            external_source = cross[s_index, external_index] @ projection
            for p_index, p_wave in enumerate(waves):
                q_index = (external_index - p_index) % grid_size
                q_wave = float(waves[q_index])
                gamma_velocity, gamma_diffusion = projected_gamma(
                    output_row, wave_symbol(float(p_wave)), wave_symbol(q_wave)
                )
                wick_matrix = (
                    cross[s_index, p_index]
                    @ hessian
                    @ cross[s_index, q_index].T
                )
                # The two Wick pairings cancel the 1/2 in the initial H vertex.
                integrands[0, s_index] += (
                    np.sum(gamma_velocity * wick_matrix) / normalization
                )
                integrands[1, s_index] += (
                    np.sum(gamma_diffusion * wick_matrix) / normalization
                )

                # At the final observable endpoint, the observable linear leg
                # has wave p and the quadratic force has wave k-p.  Normal
                # ordering removes the third (zero-wave tadpole) Wick pairing.
                force_index = q_index
                propagated_hessian = hessian @ transitions[
                    delay_index, force_index
                ]
                first_cross = cross[delay_index, p_index]
                minus_p_index = (-p_index) % grid_size
                pair_velocity, pair_diffusion = propagated_endpoint_contraction(
                    propagated_hessian,
                    first_cross,
                    external_source,
                    wave_symbol(float(waves[minus_p_index])),
                    wave_symbol(external_wave),
                )
                swapped_velocity, swapped_diffusion = (
                    propagated_endpoint_contraction(
                        propagated_hessian,
                        first_cross,
                        external_source,
                        wave_symbol(external_wave),
                        wave_symbol(float(waves[minus_p_index])),
                    )
                )
                integrands[2, s_index] += (
                    pair_velocity + swapped_velocity
                ) / normalization
                integrands[3, s_index] += (
                    pair_diffusion + swapped_diffusion
                ) / normalization
        integrated = np.trapezoid(integrands, dx=step, axis=1) / susceptibility
        initial_endpoint_velocity.append(integrated[0])
        initial_endpoint_diffusion.append(integrated[1])
        final_endpoint_velocity.append(integrated[2])
        final_endpoint_diffusion.append(integrated[3])
        total_values.append(np.sum(integrated))
    return {
        "output_times": output_times,
        "initial_observable_endpoint_velocity_H": np.asarray(
            initial_endpoint_velocity
        ),
        "initial_observable_endpoint_diffusion_H": np.asarray(
            initial_endpoint_diffusion
        ),
        "final_observable_endpoint_velocity_H": np.asarray(
            final_endpoint_velocity
        ),
        "final_observable_endpoint_diffusion_H": np.asarray(
            final_endpoint_diffusion
        ),
        "total_mixed_Gamma_H_structure_correction": np.asarray(total_values),
        "normal_ordered_quadratic_force": True,
        "equilibrium_zero_wave_tadpole_included": False,
        "multiplicative_noise_observable_contact_included": False,
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
        "internal_lattice_wave_number_retained": lattice_wave_number is not None,
        "complete_physical_F1_perp": False,
        "remaining_same_loop_order_terms": (
            "multiplicative-noise/observable contacts, cubic dynamical "
            "tadpoles/counterterms, and higher observable derivatives"
        ),
    }


def multiplicative_noise_observable_contact_correction(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    noise_root: Array,
    noise_root_derivative: Array,
    spin_projection: Array,
    spin_hessian: Array,
    integration_times: Array,
    output_times: Array,
    *,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | str]:
    r"""Evaluate the finite-cutoff multiplicative-noise--observable contact.

    In Fourier space the state-dependent conservative noise contains

    ``du_k = i k/sqrt(N) sum_{p+r=k} B'_{A C a} u_C(p) dW_a(r)``.

    Contracting its noise increment with the additive-noise part of the other
    leg of the quadratic observable

    ``m_H(k)=(2 sqrt(N))^-1 sum_q H_AB u_A(q)u_B(k-q)``

    leaves the external state leg ``u_C(k)``.  The resulting ``B' H`` term is
    therefore a causal one-time integral, not a new phenomenological vertex.
    Both observable-leg placements are retained explicitly.  The returned
    quantity is an Itô finite-cutoff structure-factor correction; changing
    stochastic convention moves a local term between this contact and the
    deterministic drift, and the final convention must be fixed by microscopic
    Mori matching.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    noise_root = np.asarray(noise_root, dtype=float)
    derivative = np.asarray(noise_root_derivative, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    hessian = np.asarray(spin_hessian, dtype=float)
    integration_times = np.asarray(integration_times, dtype=float)
    output_times = np.asarray(output_times, dtype=float)
    modes = velocity.size
    grid_size = waves.size
    if waves.ndim != 1 or grid_size < 2 or not 0 <= external_index < grid_size:
        raise ValueError("invalid Fourier grid or external index")
    if diffusion.shape != (modes, modes) or covariance.shape != diffusion.shape:
        raise ValueError("linear matrices have incompatible shapes")
    if noise_root.shape != (modes, modes):
        raise ValueError("noise root has the wrong shape")
    if derivative.shape != (modes, modes, modes):
        raise ValueError("noise-root derivative must have shape (l,i,r)")
    if projection.shape != (modes,) or hessian.shape != (modes, modes):
        raise ValueError("physical observable has incompatible dimensions")
    if not np.allclose(hessian, hessian.T, atol=1.0e-12):
        raise ValueError("spin Hessian must be symmetric")
    if (
        integration_times.ndim != 1
        or integration_times.size < 2
        or not np.isclose(integration_times[0], 0.0)
        or np.any(np.diff(integration_times) <= 0.0)
        or not np.allclose(
            np.diff(integration_times),
            integration_times[1] - integration_times[0],
            rtol=1.0e-10,
            atol=1.0e-14,
        )
    ):
        raise ValueError("integration_times must be a uniform grid from zero")
    if output_times.ndim != 1 or np.any(output_times < 0.0):
        raise ValueError("output_times must be a non-negative vector")
    step = float(integration_times[1] - integration_times[0])
    output_indices = np.rint(output_times / step).astype(int)
    if (
        np.any(output_indices < 0)
        or np.any(output_indices >= integration_times.size)
        or not np.allclose(output_times, integration_times[output_indices])
    ):
        raise ValueError("every output time must lie on the integration grid")
    if not np.isfinite(spatial_cell_length) or spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")
    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]
    transitions = np.asarray(
        [
            [expm(float(time) * generator) for generator in generators]
            for time in integration_times
        ]
    )
    cross = transitions @ fourier_covariance
    normalization = 2.0 * float(grid_size) * float(spatial_cell_length)
    corrections = []
    right_leg = []
    left_leg = []
    for output_index in output_indices:
        if output_index == 0:
            right_leg.append(0.0j)
            left_leg.append(0.0j)
            corrections.append(0.0j)
            continue
        integrands = np.zeros((2, output_index + 1), dtype=complex)
        for s_index in range(output_index + 1):
            delay_index = output_index - s_index
            external_source = cross[s_index, external_index] @ projection
            for q_index, q_wave in enumerate(waves):
                r_index = (external_index - q_index) % grid_size
                r_wave = float(waves[r_index])
                g_q = transitions[delay_index, q_index]
                g_r = transitions[delay_index, r_index]
                additive_q = g_q @ noise_root
                additive_r = g_r @ noise_root
                q_symbol = (
                    float(q_wave)
                    if lattice_wave_number is None
                    else float(lattice_wave_number(float(q_wave)))
                )
                r_symbol = (
                    r_wave
                    if lattice_wave_number is None
                    else float(lattice_wave_number(r_wave))
                )
                wave_factor = -q_symbol * r_symbol
                # Multiplicative correction on the B/right observable leg.
                integrands[0, s_index] += wave_factor * np.einsum(
                    "ab,ar,bd,cdr,c->",
                    hessian,
                    additive_q,
                    g_r,
                    derivative,
                    external_source,
                    optimize=True,
                )
                # Multiplicative correction on the A/left observable leg.
                integrands[1, s_index] += wave_factor * np.einsum(
                    "ab,ad,cdr,br,c->",
                    hessian,
                    g_q,
                    derivative,
                    additive_r,
                    external_source,
                    optimize=True,
                )
        integrated = (
            np.trapezoid(integrands, dx=step, axis=1)
            / (normalization * susceptibility)
        )
        right_leg.append(integrated[0])
        left_leg.append(integrated[1])
        corrections.append(np.sum(integrated))
    return {
        "output_times": output_times,
        "right_observable_leg_contact": np.asarray(right_leg),
        "left_observable_leg_contact": np.asarray(left_leg),
        "total_multiplicative_noise_H_structure_correction": np.asarray(
            corrections
        ),
        "stochastic_convention": "Ito",
        "both_observable_leg_placements_included": True,
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
        "internal_lattice_wave_number_retained": lattice_wave_number is not None,
        "bare_uv_matched_to_microscopic_mori": False,
        "complete_physical_F1_perp": False,
        "remaining_same_loop_order_terms": (
            "cubic dynamical tadpoles/counterterms, higher occupation and "
            "observable vertices, microscopic Mori UV matching, and the "
            "joint zero-field infinite-string limit"
        ),
    }


def matrix_free_multiplicative_noise_observable_contact_correction(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    noise_root: Array,
    noise_root_directional_action: Callable[[Array], Array],
    spin_projection: Array,
    spin_hessian: Array,
    integration_times: Array,
    output_times: Array,
    *,
    spatial_cell_length: float = 1.0,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | bool | str]:
    r"""Matrix-free form of the multiplicative-noise/observable contact.

    The dense formula needs ``dB[l,a,r]``.  At integration time ``s`` it only
    appears contracted with one external state vector, so this implementation
    requests the directional matrix ``dB[external_source]`` and never stores
    the rank-three root derivative.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    noise_root = np.asarray(noise_root, dtype=float)
    projection = np.asarray(spin_projection, dtype=complex)
    hessian = np.asarray(spin_hessian, dtype=float)
    integration_times = np.asarray(integration_times, dtype=float)
    output_times = np.asarray(output_times, dtype=float)
    modes = velocity.size
    grid_size = waves.size
    if waves.ndim != 1 or grid_size < 2 or not 0 <= external_index < grid_size:
        raise ValueError("invalid Fourier grid or external index")
    if diffusion.shape != (modes, modes) or covariance.shape != diffusion.shape:
        raise ValueError("linear matrices have incompatible shapes")
    if noise_root.shape != (modes, modes):
        raise ValueError("noise root has the wrong shape")
    if projection.shape != (modes,) or hessian.shape != (modes, modes):
        raise ValueError("physical observable has incompatible dimensions")
    if not np.allclose(hessian, hessian.T, atol=1.0e-12):
        raise ValueError("spin Hessian must be symmetric")
    if (
        integration_times.ndim != 1
        or integration_times.size < 2
        or not np.isclose(integration_times[0], 0.0)
        or np.any(np.diff(integration_times) <= 0.0)
        or not np.allclose(
            np.diff(integration_times),
            integration_times[1] - integration_times[0],
            rtol=1.0e-10,
            atol=1.0e-14,
        )
    ):
        raise ValueError("integration_times must be a uniform grid from zero")
    step = float(integration_times[1] - integration_times[0])
    output_indices = np.rint(output_times / step).astype(int)
    if (
        output_times.ndim != 1
        or np.any(output_indices < 0)
        or np.any(output_indices >= integration_times.size)
        or not np.allclose(output_times, integration_times[output_indices])
    ):
        raise ValueError("every output time must lie on the integration grid")
    if not np.isfinite(spatial_cell_length) or spatial_cell_length <= 0.0:
        raise ValueError("spatial_cell_length must be positive")

    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("projected susceptibility is non-positive")
    generators = [
        linear_ghd_generator(
            float(wave),
            velocity,
            diffusion,
            lattice_wave_number=lattice_wave_number,
        )
        for wave in waves
    ]
    transitions = np.asarray(
        [
            [expm(float(time) * generator) for generator in generators]
            for time in integration_times
        ]
    )
    cross = transitions @ fourier_covariance
    normalization = 2.0 * float(grid_size) * float(spatial_cell_length)
    corrections: list[complex] = []
    right_leg: list[complex] = []
    left_leg: list[complex] = []
    directional_actions = 0
    root_derivative_cache: dict[int, Array] = {}
    for output_index in output_indices:
        if output_index == 0:
            right_leg.append(0.0j)
            left_leg.append(0.0j)
            corrections.append(0.0j)
            continue
        integrands = np.zeros((2, output_index + 1), dtype=complex)
        for s_index in range(output_index + 1):
            delay_index = output_index - s_index
            external_source = cross[s_index, external_index] @ projection
            if s_index not in root_derivative_cache:
                root_derivative_cache[s_index] = np.asarray(
                    noise_root_directional_action(external_source)
                )
                directional_actions += 1
            root_derivative = root_derivative_cache[s_index]
            if root_derivative.shape != (modes, modes):
                raise ValueError("noise-root directional action has wrong shape")
            for q_index, q_wave in enumerate(waves):
                r_index = (external_index - q_index) % grid_size
                r_wave = float(waves[r_index])
                g_q = transitions[delay_index, q_index]
                g_r = transitions[delay_index, r_index]
                additive_q = g_q @ noise_root
                additive_r = g_r @ noise_root
                q_symbol = (
                    float(q_wave)
                    if lattice_wave_number is None
                    else float(lattice_wave_number(float(q_wave)))
                )
                r_symbol = (
                    r_wave
                    if lattice_wave_number is None
                    else float(lattice_wave_number(r_wave))
                )
                wave_factor = -q_symbol * r_symbol
                integrands[0, s_index] += wave_factor * np.einsum(
                    "ab,ar,bd,dr->",
                    hessian,
                    additive_q,
                    g_r,
                    root_derivative,
                    optimize=True,
                )
                integrands[1, s_index] += wave_factor * np.einsum(
                    "ab,ad,dr,br->",
                    hessian,
                    g_q,
                    root_derivative,
                    additive_r,
                    optimize=True,
                )
        integrated = (
            np.trapezoid(integrands, dx=step, axis=1)
            / (normalization * susceptibility)
        )
        right_leg.append(complex(integrated[0]))
        left_leg.append(complex(integrated[1]))
        corrections.append(complex(np.sum(integrated)))
    return {
        "output_times": output_times,
        "right_observable_leg_contact": np.asarray(right_leg),
        "left_observable_leg_contact": np.asarray(left_leg),
        "total_multiplicative_noise_H_structure_correction": np.asarray(
            corrections
        ),
        "noise_root_directional_action_calls": int(directional_actions),
        "rank_three_noise_root_derivative_stored": False,
        "stochastic_convention": "Ito",
        "both_observable_leg_placements_included": True,
        "trajectory_sampling_used": False,
        "target_coefficients_used": False,
        "internal_lattice_wave_number_retained": lattice_wave_number is not None,
        "bare_uv_matched_to_microscopic_mori": False,
        "complete_physical_F1_perp": False,
    }


def scalar_galerkin_coefficients(
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    velocity_vertex: Array,
    spin_projection: Array,
) -> dict[str, float | bool | str]:
    r"""Project finite-cutoff GHD onto the weak magnetic local-GGE tangent.

    Let ``r=C p`` and ``m=p^T u=chi phi`` for ``u=r phi``.  Direct projection
    of the occupation equation gives

    ``d_t m + c d_x m + A m d_x m = D d_x^2 m``

    with

    ``c=p^T(v*r)/chi``,
    ``D=p^T(Dmat*r)/(2 chi)``, and
    ``A=p^T[r*(V*r)]/chi^2``.

    The result is a Galerkin coefficient, not automatically a controlled
    closure.  The returned ``C^-1`` orthogonal fractions measure how much of
    each vector field points outside the scalar tangent.  Spin-flip symmetry
    forces the physical zero-field limit of ``A`` to vanish; a conditional
    one-sided normal-mode coefficient is a different object.
    """

    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    vertex = np.asarray(velocity_vertex, dtype=float)
    spin = np.asarray(spin_projection, dtype=float)
    modes = velocity.size
    if diffusion.shape != (modes, modes):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or vertex.shape != diffusion.shape:
        raise ValueError("covariance and velocity vertex have the wrong shape")
    if spin.shape != (modes,):
        raise ValueError("spin projection has the wrong shape")
    tangent = covariance @ spin
    susceptibility = float(spin @ tangent)
    if susceptibility <= 0.0:
        raise ValueError("spin susceptibility is non-positive")
    advective_vector = velocity * tangent
    diffusive_vector = 0.5 * diffusion @ tangent
    nonlinear_vector = tangent * (vertex @ tangent)
    advective_projection = static_metric_projection(
        advective_vector, tangent, covariance
    )
    diffusive_projection = static_metric_projection(
        diffusive_vector, tangent, covariance
    )
    nonlinear_projection = static_metric_projection(
        nonlinear_vector, tangent, covariance
    )
    return {
        "background_advection_c": float(spin @ advective_vector / susceptibility),
        "diffusion_D": float(spin @ diffusive_vector / susceptibility),
        "burgers_A_physical_galerkin": float(
            spin @ nonlinear_vector / susceptibility**2
        ),
        "advective_orthogonal_fraction": float(
            advective_projection["orthogonal_fraction"]
        ),
        "diffusive_orthogonal_fraction": float(
            diffusive_projection["orthogonal_fraction"]
        ),
        "nonlinear_orthogonal_fraction": float(
            nonlinear_projection["orthogonal_fraction"]
        ),
        "scalar_closure_controlled_by_projection_alone": bool(
            max(
                float(advective_projection["orthogonal_fraction"]),
                float(diffusive_projection["orthogonal_fraction"]),
                float(nonlinear_projection["orthogonal_fraction"]),
            )
            < 1.0e-2
        ),
        "zero_field_physical_A_constraint": "A(h=0)=0 by spin-flip symmetry",
        "conditional_normal_mode_A_is_different": True,
    }


def quadratic_observable_structure_correction(
    wave_numbers: Array,
    external_index: int,
    velocity: Array,
    diffusion: Array,
    covariance: Array,
    observable_hessian: Array,
    linear_projection: Array,
    times: Array,
    *,
    spatial_cell_length: float = 1.0,
) -> dict[str, Array | float | bool | str]:
    r"""Return the exact Gaussian ``H^2`` correction to a physical observable.

    For

    ``m(k)=p.u(k)+(2 sqrt(N))^-1 sum_q H_bc u_b(q)u_c(k-q)+...``,

    the linear--quadratic cross correlation vanishes by Gaussian parity.  The
    quadratic--quadratic contribution follows from Wick's theorem.  For a
    symmetric Hessian its two pairings are equal and give

    ``delta S_HH=(2N)^-1 sum_q H_bc S_q[b,e] H_ef S_k-q[c,f]``.

    The result is normalized by the linear static susceptibility.  It is an
    observable insertion, not a dynamical memory kernel; the mixed ``V H``
    diagrams and higher Hessians remain separate terms.
    """

    waves = np.asarray(wave_numbers, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    covariance = np.asarray(covariance, dtype=complex)
    hessian = np.asarray(observable_hessian, dtype=float)
    projection = np.asarray(linear_projection, dtype=complex)
    times = np.asarray(times, dtype=float)
    modes = velocity.size
    if waves.ndim != 1 or not 0 <= external_index < waves.size:
        raise ValueError("invalid Fourier grid or external index")
    if diffusion.shape != (modes, modes):
        raise ValueError("diffusion has the wrong shape")
    if covariance.shape != diffusion.shape or hessian.shape != diffusion.shape:
        raise ValueError("covariance and Hessian must match diffusion")
    if projection.shape != (modes,):
        raise ValueError("linear projection has the wrong shape")
    if not np.allclose(hessian, hessian.T, atol=1e-12):
        raise ValueError("observable Hessian must be symmetric")
    if times.ndim != 1 or np.any(times < 0.0) or np.any(np.diff(times) < 0.0):
        raise ValueError("times must be a non-negative increasing vector")
    if spatial_cell_length <= 0.0 or not np.isfinite(spatial_cell_length):
        raise ValueError("spatial_cell_length must be positive")
    fourier_covariance = covariance / float(spatial_cell_length)
    susceptibility = projection.conj() @ fourier_covariance @ projection
    if float(np.real(susceptibility)) <= 0.0:
        raise ValueError("linear susceptibility is non-positive")
    generators = [
        linear_ghd_generator(float(wave), velocity, diffusion) for wave in waves
    ]
    correction: list[complex] = []
    grid_size = waves.size
    for time in times:
        cross = [
            expm(float(time) * generator) @ fourier_covariance
            for generator in generators
        ]
        value = 0.0j
        for q_index in range(grid_size):
            complement = (external_index - q_index) % grid_size
            value += np.einsum(
                "bc,be,ef,cf->",
                hessian,
                cross[q_index],
                hessian,
                cross[complement],
                optimize=True,
            )
        correction.append(value / (2.0 * grid_size * susceptibility))
    values = np.asarray(correction)
    return {
        "times": times,
        "normalized_H2_structure_correction": values,
        "zero_time_correction": float(np.real(values[0])),
        "linear_quadratic_cross_correction": 0.0,
        "first_nonzero_hessian_order": "O(H^2)",
        "trajectory_sampling_used": False,
        "complete_physical_F1_perp": False,
        "omitted_observable_terms": "mixed O(V H) diagrams and higher Hessians",
    }


def perturbative_structure_from_memory(
    times: Array,
    leading_structure: Array,
    memory_correction: Array,
    wave_number: float,
    *,
    lattice_wave_number: Callable[[float], float] | None = None,
) -> dict[str, Array | float | str]:
    r"""Apply an ``O(memory)`` Mori correction to a projected structure factor.

    The Laplace-domain Dyson identity

    ``delta Ftilde=-khat^2 Ftilde0^2 delta Ktilde``

    becomes two causal convolutions in time.  This routine evaluates them by
    composite trapezoid quadrature on a uniform grid.  It is useful for
    converting the one-loop force memory into an actual shape correction;
    it does not cure any UV or omitted-vertex dependence of the supplied
    memory.
    """

    times = np.asarray(times, dtype=float)
    leading = np.asarray(leading_structure, dtype=complex)
    memory = np.asarray(memory_correction, dtype=complex)
    if (
        times.ndim != 1
        or leading.shape != times.shape
        or memory.shape != times.shape
        or times.size < 2
        or np.any(np.diff(times) <= 0.0)
        or not np.allclose(np.diff(times), times[1] - times[0], rtol=1e-10, atol=1e-14)
    ):
        raise ValueError("need equal-length arrays on a uniform increasing grid")
    if not np.isclose(times[0], 0.0):
        raise ValueError("time grid must begin at zero")
    khat = (
        float(wave_number)
        if lattice_wave_number is None
        else float(lattice_wave_number(float(wave_number)))
    )
    if khat == 0.0:
        raise ValueError("wave number must be non-zero")

    first = np.zeros_like(leading)
    second = np.zeros_like(leading)
    for index in range(1, times.size):
        lagged_leading = leading[index::-1]
        first[index] = np.trapezoid(
            lagged_leading * memory[: index + 1], times[: index + 1]
        )
    for index in range(1, times.size):
        lagged_leading = leading[index::-1]
        second[index] = -khat**2 * np.trapezoid(
            lagged_leading * first[: index + 1], times[: index + 1]
        )
    return {
        "times": times,
        "first_convolution_F0_K": first,
        "structure_correction": second,
        "corrected_structure": leading + second,
        "initial_value_residual": float(abs(second[0])),
        "laplace_identity": "delta F=-khat^2 F0^2 delta K",
    }


def spin_flip_projection_certificate() -> dict[str, object]:
    r"""Return the exact symmetry distinction used by the scalar projection.

    Global pi rotation maps ``m -> -m`` and ``j_m -> -j_m``.  Therefore the
    analytic physical current is odd in the physical magnetic field and its
    zero-field quadratic Kubo vertex vanishes.  A non-zero coefficient of a
    quadratic *basis function* in an orientation-conditioned normalized wall
    projection is a different, one-sided finite-window coordinate.
    """

    return {
        "physical_zero_field_quadratic_kubo_vertex": 0.0,
        "symmetry": "global_pi_spin_rotation",
        "analytic_current_parity": "j_m[h] = -j_m[-h]",
        "conditional_quadratic_basis_coordinate_may_be_nonzero": True,
        "required_order_of_limits": [
            "take the declared hydrodynamic size/time limit at fixed wall orientation",
            "then take the one-sided amplitude limit mu->0+",
        ],
        "objects_are_identical": False,
    }
