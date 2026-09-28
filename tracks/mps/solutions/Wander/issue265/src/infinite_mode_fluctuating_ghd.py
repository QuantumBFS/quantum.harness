"""Regulated infinite-mode fluctuating GHD in a physical-spin basis.

The zero-field magnetic tangent of the isotropic XXX chain is singular in any
fixed finite-string occupation basis.  This module therefore never identifies
one finite cutoff with the infinite theory.  At each positive field it

1. whitens *all* retained occupation modes with their exact static covariance,
2. rotates the first whitened coordinate onto physical magnetization, and
3. retains the complete orthogonal complement and every non-diagonal block of
   the diffusion and FDT-noise operators.

The resulting finite-field objects are regulators.  A physical zero-field
claim requires a joint ``h -> 0``, ``s_max h -> infinity``, rapidity and spatial
cutoff limit.  No auxiliary pole or two-mode closure is introduced here.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm
from scipy.sparse.linalg import LinearOperator, expm_multiply, gmres


Array = np.ndarray


def _whitened_spin_data(
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    velocity: Array,
) -> tuple[Array, Array, Array, float]:
    """Return ``(A, D, Q, e_m)`` data without constructing a complement.

    ``A`` is diagonal and is returned as its diagonal vector.  ``D`` and ``Q``
    are the full operators in the covariance-whitened occupation basis.  The
    final array is the unit physical-spin direction.  Keeping this helper
    private makes the normalization identical in dense-rotation and Krylov
    paths.
    """

    diffusion = np.asarray(diffusion, dtype=float)
    noise_covariance = np.asarray(noise_covariance, dtype=float)
    projection = np.asarray(spin_projection, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    diagonal = _positive_diagonal(static_covariance)
    count = diagonal.size
    if diffusion.shape != (count, count) or noise_covariance.shape != (
        count,
        count,
    ):
        raise ValueError("diffusion and noise must match the covariance")
    if projection.shape != (count,) or velocity.shape != (count,):
        raise ValueError("spin projection and velocity must match the modes")
    square_root = np.sqrt(diagonal)
    inverse_root = 1.0 / square_root
    susceptibility = float(np.dot(projection * diagonal, projection))
    if susceptibility <= 0.0 or not np.isfinite(susceptibility):
        raise ValueError("projected spin susceptibility must be positive")
    direction = square_root * projection / np.sqrt(susceptibility)
    whitened_diffusion = inverse_root[:, None] * diffusion * square_root[None, :]
    whitened_noise = (
        inverse_root[:, None] * noise_covariance * inverse_root[None, :]
    )
    return velocity, whitened_diffusion, whitened_noise, direction


def _positive_diagonal(matrix: Array) -> Array:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("static covariance must be square")
    diagonal = np.diag(matrix)
    if not np.allclose(matrix, np.diag(diagonal), rtol=0.0, atol=1.0e-13):
        raise ValueError("occupation covariance must be diagonal")
    if np.any(~np.isfinite(diagonal)) or np.any(diagonal <= 0.0):
        raise ValueError("static covariance must be positive")
    return diagonal


def _orthogonal_first_column(direction: Array) -> Array:
    """Return an orthogonal matrix whose first column is ``direction``.

    A Householder reflector is used so the complement is deterministic.  The
    complement itself has no physical interpretation; all reported projected
    quantities are invariant under a further rotation inside that complement.
    """

    direction = np.asarray(direction, dtype=float)
    norm = float(np.linalg.norm(direction))
    if direction.ndim != 1 or not np.isfinite(norm) or norm == 0.0:
        raise ValueError("spin direction must be a non-zero finite vector")
    unit = direction / norm
    first = np.zeros_like(unit)
    first[0] = 1.0
    if np.linalg.norm(unit - first) < 1.0e-14:
        return np.eye(unit.size)
    vector = first - unit
    reflector = np.eye(unit.size) - 2.0 * np.outer(vector, vector) / np.dot(
        vector, vector
    )
    # H e_0 = unit, so the first column is the physical spin direction.
    return reflector


def physical_spin_basis(
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    *,
    velocity: Array | None = None,
) -> dict[str, Array | float]:
    r"""Whiten and rotate the full operator onto physical magnetization.

    Raw occupation fluctuations obey ``Cov(delta n)=C`` and physical spin is
    ``m=g^T delta n``.  With ``delta n=C^(1/2)y`` the whitened covariance is
    the identity and the normalized spin direction is

    ``e_m=C^(1/2)g/sqrt(g^T C g)``.

    The returned first coordinate is exactly ``m/sqrt(chi)``.  Every other
    coordinate is retained; in particular the spin--orthogonal diffusion and
    noise blocks are not discarded.
    """

    diffusion = np.asarray(diffusion, dtype=float)
    noise_covariance = np.asarray(noise_covariance, dtype=float)
    projection = np.asarray(spin_projection, dtype=float)
    diagonal = _positive_diagonal(static_covariance)
    count = diagonal.size
    if diffusion.shape != (count, count) or noise_covariance.shape != (
        count,
        count,
    ):
        raise ValueError("diffusion and noise must match the covariance")
    if projection.shape != (count,):
        raise ValueError("spin projection must match the mode count")

    square_root = np.sqrt(diagonal)
    inverse_root = 1.0 / square_root
    susceptibility = float(np.dot(projection * diagonal, projection))
    if susceptibility <= 0.0 or not np.isfinite(susceptibility):
        raise ValueError("projected spin susceptibility must be positive")
    spin_direction = square_root * projection / np.sqrt(susceptibility)
    rotation = _orthogonal_first_column(spin_direction)

    whitened_diffusion = (
        inverse_root[:, None] * diffusion * square_root[None, :]
    )
    whitened_noise = (
        inverse_root[:, None] * noise_covariance * inverse_root[None, :]
    )
    rotated_diffusion = rotation.T @ whitened_diffusion @ rotation
    rotated_noise = rotation.T @ whitened_noise @ rotation
    fdt_target = 0.5 * (rotated_diffusion + rotated_diffusion.T)

    result: dict[str, Array | float] = {
        "susceptibility": susceptibility,
        "spin_direction_raw_whitened": spin_direction,
        "rotation": rotation,
        "diffusion": rotated_diffusion,
        "noise_covariance": rotated_noise,
        "fdt_residual": float(
            np.linalg.norm(rotated_noise - fdt_target)
            / max(np.linalg.norm(fdt_target), np.finfo(float).tiny)
        ),
        "spin_diffusion": float(rotated_diffusion[0, 0]),
        "spin_noise": float(rotated_noise[0, 0]),
        "spin_to_orthogonal_diffusion_norm": float(
            np.linalg.norm(rotated_diffusion[1:, 0])
        ),
        "orthogonal_to_spin_diffusion_norm": float(
            np.linalg.norm(rotated_diffusion[0, 1:])
        ),
        "spin_orthogonal_noise_norm": float(
            np.linalg.norm(rotated_noise[0, 1:])
        ),
    }
    if velocity is not None:
        velocity = np.asarray(velocity, dtype=float)
        if velocity.shape != (count,):
            raise ValueError("velocity must match the mode count")
        rotated_velocity = rotation.T @ np.diag(velocity) @ rotation
        result["velocity"] = rotated_velocity
        result["spin_velocity"] = float(rotated_velocity[0, 0])
        result["spin_orthogonal_velocity_norm"] = float(
            np.linalg.norm(rotated_velocity[0, 1:])
        )
    return result


def physical_spin_invariants(
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    *,
    velocity: Array | None = None,
) -> dict[str, float]:
    """Basis-independent spin/complement norms without forming a complement.

    This evaluates exactly the scalar block and the Euclidean norms of both
    off-diagonal blocks in the whitened metric.  It is algebraically identical
    to :func:`physical_spin_basis` but avoids dense Householder rotations and
    cubic work, enabling regulator audits with several thousand modes.
    """

    diffusion = np.asarray(diffusion, dtype=float)
    noise_covariance = np.asarray(noise_covariance, dtype=float)
    projection = np.asarray(spin_projection, dtype=float)
    diagonal = _positive_diagonal(static_covariance)
    count = diagonal.size
    if diffusion.shape != (count, count) or noise_covariance.shape != (
        count,
        count,
    ):
        raise ValueError("diffusion and noise must match the covariance")
    square_root = np.sqrt(diagonal)
    inverse_root = 1.0 / square_root
    susceptibility = float(np.dot(projection * diagonal, projection))
    direction = square_root * projection / np.sqrt(susceptibility)
    whitened_diffusion = (
        inverse_root[:, None] * diffusion * square_root[None, :]
    )
    whitened_noise = (
        inverse_root[:, None] * noise_covariance * inverse_root[None, :]
    )
    d_right = whitened_diffusion @ direction
    d_left = direction @ whitened_diffusion
    d_mm = float(direction @ d_right)
    q_right = whitened_noise @ direction
    q_left = direction @ whitened_noise
    q_mm = float(direction @ q_right)
    fdt_target = 0.5 * (whitened_diffusion + whitened_diffusion.T)
    result = {
        "susceptibility": susceptibility,
        "fdt_residual": float(
            np.linalg.norm(whitened_noise - fdt_target)
            / max(np.linalg.norm(fdt_target), np.finfo(float).tiny)
        ),
        "spin_diffusion": d_mm,
        "spin_noise": q_mm,
        "spin_to_orthogonal_diffusion_norm": float(
            np.sqrt(max(np.vdot(d_right, d_right).real - d_mm**2, 0.0))
        ),
        "orthogonal_to_spin_diffusion_norm": float(
            np.sqrt(max(np.vdot(d_left, d_left).real - d_mm**2, 0.0))
        ),
        "spin_orthogonal_noise_norm": float(
            np.sqrt(max(np.vdot(q_right, q_right).real - q_mm**2, 0.0))
        ),
    }
    if velocity is not None:
        velocity = np.asarray(velocity, dtype=float)
        if velocity.shape != (count,):
            raise ValueError("velocity must match the mode count")
        v_direction = velocity * direction
        v_mm = float(direction @ v_direction)
        result["spin_velocity"] = v_mm
        result["spin_orthogonal_velocity_norm"] = float(
            np.sqrt(max(np.vdot(v_direction, v_direction).real - v_mm**2, 0.0))
        )
    return result


def stationary_spin_structure_factor(
    velocity: Array,
    diffusion: Array,
    noise_covariance: Array,
    wave_number: float,
    times: Array,
    *,
    lattice_wave_number: bool = True,
) -> dict[str, Array | float]:
    r"""Propagate all modes and return ``S_m(k,t)/chi``.

    For the conservative linear SPDE the Fourier generator is

    ``L=-i k A-k^2 D/2``

    and the equilibrium two-time covariance is ``exp(L t)`` in the whitened
    basis.  The FDT noise is retained and independently checked through the
    Lyapunov identity ``L+L^dagger+k^2 Q=0``.  The first basis coordinate is
    assumed to be normalized physical spin.
    """

    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    noise_covariance = np.asarray(noise_covariance, dtype=float)
    times = np.asarray(times, dtype=float)
    if velocity.shape != diffusion.shape or diffusion.shape != noise_covariance.shape:
        raise ValueError("all operators must have the same square shape")
    if times.ndim != 1 or np.any(times < 0.0):
        raise ValueError("times must be a non-negative vector")
    khat = (
        2.0 * np.sin(0.5 * float(wave_number))
        if lattice_wave_number
        else float(wave_number)
    )
    generator = -1j * khat * velocity - 0.5 * khat**2 * diffusion
    lyapunov = generator + generator.conj().T + khat**2 * noise_covariance
    denominator = max(np.linalg.norm(generator), np.finfo(float).tiny)
    structure = np.asarray([expm(generator * time)[0, 0] for time in times])
    return {
        "times": times,
        "structure_factor_over_susceptibility": structure,
        "generator": generator,
        "stationarity_residual": float(np.linalg.norm(lyapunov) / denominator),
        "khat": float(khat),
    }


def exact_spin_mori_resolvent(
    velocity: Array,
    diffusion: Array,
    wave_number: float,
    laplace_frequency: complex,
    *,
    lattice_wave_number: bool = True,
) -> dict[str, complex | float]:
    r"""Eliminate the complete orthogonal sector by an exact Schur complement.

    This is the finite-regulator version of the infinite-mode Mori kernel.  If
    ``L`` is partitioned into normalized spin and its full complement, then

    ``Sigma_m(z)=L_mperp (z-L_perpperp)^(-1) L_perpm``

    is retained without replacing the complement by poles.  With
    ``Ftilde=[z-L_mm-Sigma_m]^-1``, the continuity-normalized memory is
    ``Ktilde=(1/Ftilde-z)/khat^2``.
    """

    velocity = np.asarray(velocity, dtype=float)
    diffusion = np.asarray(diffusion, dtype=float)
    if velocity.shape != diffusion.shape or velocity.ndim != 2:
        raise ValueError("velocity and diffusion must be matching square matrices")
    z = complex(laplace_frequency)
    if z.real <= 0.0:
        raise ValueError("Laplace frequency must have positive real part")
    khat = (
        2.0 * np.sin(0.5 * float(wave_number))
        if lattice_wave_number
        else float(wave_number)
    )
    generator = -1j * khat * velocity - 0.5 * khat**2 * diffusion
    complement = generator[1:, 1:]
    self_energy = generator[0, 1:] @ np.linalg.solve(
        z * np.eye(complement.shape[0]) - complement, generator[1:, 0]
    )
    inverse_resolvent = z - generator[0, 0] - self_energy
    structure_resolvent = 1.0 / inverse_resolvent
    memory = (inverse_resolvent - z) / khat**2
    return {
        "khat": float(khat),
        "spin_structure_resolvent": complex(structure_resolvent),
        "orthogonal_self_energy": complex(self_energy),
        "continuity_memory": complex(memory),
        "bare_spin_memory": complex(-generator[0, 0] / khat**2),
        "orthogonal_memory_correction": complex(-self_energy / khat**2),
    }


def krylov_spin_structure_factor(
    velocity: Array,
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    wave_number: float,
    times: Array,
    *,
    lattice_wave_number: bool = True,
) -> dict[str, Array | float]:
    r"""Propagate the physical spin through every retained GHD mode.

    This is the complement-free equivalent of
    :func:`stationary_spin_structure_factor`.  It evaluates

    ``F_m(k,t)=e_m^T exp[L(k)t] e_m``

    with the complete dense non-diagonal diffusion operator.  Krylov actions
    avoid an explicit complement basis and never replace its spectrum by a
    finite set of poles.  The complete noise covariance enters an independent
    Lyapunov/FDT check; at equilibrium it fixes the equal-time covariance to
    the identity in the whitened basis.
    """

    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or np.any(times < 0.0):
        raise ValueError("times must be a non-negative vector")
    a_diag, d_white, q_white, direction = _whitened_spin_data(
        diffusion,
        static_covariance,
        noise_covariance,
        spin_projection,
        velocity,
    )
    khat = (
        2.0 * np.sin(0.5 * float(wave_number))
        if lattice_wave_number
        else float(wave_number)
    )
    generator = -1j * khat * np.diag(a_diag) - 0.5 * khat**2 * d_white
    lyapunov = generator + generator.conj().T + khat**2 * q_white
    denominator = max(np.linalg.norm(generator), np.finfo(float).tiny)

    # A single interval Krylov calculation reuses its Arnoldi construction
    # when the requested grid is uniform.  The fallback remains exact up to
    # scipy's declared expm_multiply tolerance for arbitrary time samples.
    if times.size > 1 and np.allclose(
        np.diff(times), np.diff(times)[0], rtol=1.0e-12, atol=1.0e-14
    ):
        evolved = expm_multiply(
            generator,
            direction,
            start=float(times[0]),
            stop=float(times[-1]),
            num=int(times.size),
            endpoint=True,
        )
        adjoint_evolved = expm_multiply(
            generator.conj().T,
            direction,
            start=float(times[0]),
            stop=float(times[-1]),
            num=int(times.size),
            endpoint=True,
        )
    else:
        evolved = np.stack(
            [expm_multiply(generator * float(time), direction) for time in times]
        )
        adjoint_evolved = np.stack(
            [
                expm_multiply(generator.conj().T * float(time), direction)
                for time in times
            ]
        )
    structure = np.asarray(evolved @ direction, dtype=complex)
    initial_covariance = np.einsum(
        "ti,ti->t", adjoint_evolved.conj(), adjoint_evolved
    ).real
    # In the whitened equilibrium metric Sigma_eq=I.  The exact Lyapunov
    # solution gives the integrated contribution of the *full* Q operator as
    # I-E E^dagger, so the following is not a scalar-noise replacement.
    accumulated_noise = 1.0 - initial_covariance
    return {
        "times": times,
        "structure_factor_over_susceptibility": structure,
        "equal_time_covariance_from_initial_state": initial_covariance,
        "equal_time_covariance_from_accumulated_full_noise": accumulated_noise,
        "total_equal_time_covariance": initial_covariance + accumulated_noise,
        "stationarity_residual": float(np.linalg.norm(lyapunov) / denominator),
        "khat": float(khat),
        "method": "full_mode_krylov_without_complement_closure",
    }


def direct_full_noise_spin_covariance(
    velocity: Array,
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    wave_number: float,
    times: Array,
    *,
    lattice_wave_number: bool = True,
    quadrature_order: int = 8,
) -> dict[str, Array | float | str]:
    r"""Directly propagate the complete non-diagonal FDT noise operator.

    In the covariance-whitened occupation basis the conservative linear SPDE
    has generator ``L=-i khat A-khat**2 D/2`` and noise rate
    ``khat**2 Q``.  Its contribution to the normalized physical-spin
    covariance is evaluated without diagonalising or scalarising ``Q``:

    ``C_noise(t)=khat**2 integral_0^t ds v(s)^dagger Q v(s)``,

    where ``v(s)=exp(L^dagger s)e_m``.  Gauss--Legendre quadrature is applied
    independently on every requested time interval.  The returned FDT
    identity value is an *independent* check, not an input to the direct
    integral.

    This routine reports the projected physical-spin covariance.  It still
    contracts every entry of the full dense ``Q`` at each quadrature node; no
    diagonal-noise, scalar-noise, auxiliary-mode, or pole closure is used.
    """

    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or np.any(~np.isfinite(times)) or np.any(times < 0.0):
        raise ValueError("times must be a finite non-negative vector")
    if np.any(np.diff(times) < 0.0):
        raise ValueError("times must be sorted")
    if quadrature_order < 2:
        raise ValueError("quadrature_order must be at least two")
    a_diag, d_white, q_white, direction = _whitened_spin_data(
        diffusion,
        static_covariance,
        noise_covariance,
        spin_projection,
        velocity,
    )
    khat = (
        2.0 * np.sin(0.5 * float(wave_number))
        if lattice_wave_number
        else float(wave_number)
    )
    generator = -1j * khat * np.diag(a_diag) - 0.5 * khat**2 * d_white
    nodes, weights = np.polynomial.legendre.leggauss(int(quadrature_order))
    accumulated = np.zeros(times.size, dtype=float)
    accumulated_diagonal = np.zeros(times.size, dtype=float)
    accumulated_offdiagonal = np.zeros(times.size, dtype=float)
    q_diagonal = np.diag(q_white)
    previous = 0.0
    total = 0.0
    diagonal_total = 0.0
    offdiagonal_total = 0.0
    for index, stop in enumerate(times):
        width = float(stop - previous)
        if width > 0.0 and abs(khat) > 0.0:
            samples = previous + 0.5 * width * (nodes + 1.0)
            integrand = np.empty(nodes.size, dtype=float)
            diagonal_integrand = np.empty(nodes.size, dtype=float)
            for sample_index, sample in enumerate(samples):
                vector = expm_multiply(
                    generator.conj().T * float(sample), direction
                )
                integrand[sample_index] = float(
                    np.vdot(vector, q_white @ vector).real
                )
                diagonal_integrand[sample_index] = float(
                    np.sum(q_diagonal * np.abs(vector) ** 2)
                )
            interval_scale = khat**2 * 0.5 * width
            interval_total = interval_scale * float(weights @ integrand)
            interval_diagonal = interval_scale * float(
                weights @ diagonal_integrand
            )
            total += interval_total
            diagonal_total += interval_diagonal
            offdiagonal_total += interval_total - interval_diagonal
        accumulated[index] = total
        accumulated_diagonal[index] = diagonal_total
        accumulated_offdiagonal[index] = offdiagonal_total
        previous = float(stop)

    adjoint_at_times = np.stack(
        [
            expm_multiply(generator.conj().T * float(time), direction)
            for time in times
        ]
    )
    initial = np.einsum(
        "ti,ti->t", adjoint_at_times.conj(), adjoint_at_times
    ).real
    fdt_identity = 1.0 - initial
    scale = np.maximum(np.abs(fdt_identity), 1.0e-14)
    return {
        "times": times,
        "equal_time_covariance_from_initial_state": initial,
        "equal_time_covariance_from_direct_full_noise": accumulated,
        "equal_time_covariance_from_diagonal_noise_only": accumulated_diagonal,
        "equal_time_covariance_from_offdiagonal_noise": accumulated_offdiagonal,
        "equal_time_covariance_from_fdt_identity": fdt_identity,
        "total_equal_time_covariance_direct": initial + accumulated,
        "direct_vs_fdt_absolute_residual": np.abs(accumulated - fdt_identity),
        "direct_vs_fdt_relative_residual": np.abs(accumulated - fdt_identity)
        / scale,
        "maximum_direct_vs_fdt_absolute_residual": float(
            np.max(np.abs(accumulated - fdt_identity), initial=0.0)
        ),
        "quadrature_order_per_requested_interval": int(quadrature_order),
        "khat": float(khat),
        "method": "direct_full_dense_nondiagonal_noise_quadrature",
    }


def krylov_spin_mori_resolvent(
    velocity: Array,
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    wave_number: float,
    laplace_frequency: complex,
    *,
    lattice_wave_number: bool = True,
    relative_tolerance: float = 1.0e-10,
    maximum_iterations: int | None = None,
) -> dict[str, complex | float | int | str]:
    r"""Return the exact full-complement Mori resolvent by a Krylov solve.

    The scalar resolvent ``Ftilde=e_m^T(z-L)^(-1)e_m`` uniquely fixes the
    Schur complement of *all* orthogonal modes.  Consequently

    ``Ktilde=(1/Ftilde-z)/khat^2``

    is identical to explicit complement elimination but remains usable for
    several-thousand-mode adaptive regulators.  ``gmres_info != 0`` is a hard
    non-convergence signal and is reported rather than silently accepted.
    """

    z = complex(laplace_frequency)
    if z.real <= 0.0:
        raise ValueError("Laplace frequency must have positive real part")
    if relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be positive")
    a_diag, d_white, q_white, direction = _whitened_spin_data(
        diffusion,
        static_covariance,
        noise_covariance,
        spin_projection,
        velocity,
    )
    khat = (
        2.0 * np.sin(0.5 * float(wave_number))
        if lattice_wave_number
        else float(wave_number)
    )
    generator = -1j * khat * np.diag(a_diag) - 0.5 * khat**2 * d_white
    dimension = direction.size
    shifted = LinearOperator(
        (dimension, dimension),
        matvec=lambda vector: z * vector - generator @ vector,
        rmatvec=lambda vector: np.conj(z) * vector - generator.conj().T @ vector,
        dtype=complex,
    )
    iterations = 0

    def count_iteration(_residual) -> None:
        nonlocal iterations
        iterations += 1

    solution, info = gmres(
        shifted,
        direction.astype(complex),
        rtol=relative_tolerance,
        atol=0.0,
        maxiter=maximum_iterations,
        callback=count_iteration,
        callback_type="pr_norm",
    )
    residual = float(
        np.linalg.norm(shifted @ solution - direction)
        / max(np.linalg.norm(direction), np.finfo(float).tiny)
    )
    structure_resolvent = complex(direction @ solution)
    inverse_resolvent = 1.0 / structure_resolvent
    memory = (inverse_resolvent - z) / khat**2
    bare_generator = complex(direction @ (generator @ direction))
    bare_memory = -bare_generator / khat**2
    q_fdt = 0.5 * (d_white + d_white.T)
    fdt_residual = float(
        np.linalg.norm(q_white - q_fdt)
        / max(np.linalg.norm(q_fdt), np.finfo(float).tiny)
    )
    return {
        "khat": float(khat),
        "spin_structure_resolvent": structure_resolvent,
        "continuity_memory": complex(memory),
        "bare_spin_memory": complex(bare_memory),
        "orthogonal_memory_correction": complex(memory - bare_memory),
        "linear_solve_relative_residual": residual,
        "gmres_info": int(info),
        "gmres_iterations": int(iterations),
        "fdt_residual": fdt_residual,
        "method": "full_mode_krylov_schur_complement_without_poles",
    }


def joint_scaled_spin_structure_grid(
    velocity: Array,
    diffusion: Array,
    static_covariance: Array,
    noise_covariance: Array,
    spin_projection: Array,
    field: float,
    scaled_wave_numbers: Array,
    scaled_time: float,
    *,
    lattice_wave_number: bool = True,
) -> dict[str, Array | float | str]:
    r"""Evaluate ``F_h(q,tau)`` on the giant-string joint scaling grid.

    The physical variables are ``k=q*h^2`` and ``t=tau/h^3``.  Whitening is
    performed once and the complete non-diagonal generator is then applied at
    every requested ``q``.  This is substantially cheaper than repeatedly
    constructing the physical-spin basis and makes a direct inverse Fourier
    wall reconstruction practical.
    """

    h = float(field)
    tau = float(scaled_time)
    q = np.asarray(scaled_wave_numbers, dtype=float)
    if h <= 0.0 or tau < 0.0 or q.ndim != 1 or np.any(q < 0.0):
        raise ValueError("require h>0, tau>=0, and a non-negative q vector")
    a_diag, d_white, q_white, direction = _whitened_spin_data(
        diffusion,
        static_covariance,
        noise_covariance,
        spin_projection,
        velocity,
    )
    fdt_target = 0.5 * (d_white + d_white.T)
    fdt_residual = float(
        np.linalg.norm(q_white - fdt_target)
        / max(np.linalg.norm(fdt_target), np.finfo(float).tiny)
    )
    physical_time = tau / h**3
    values = np.empty(q.size, dtype=complex)
    for index, scaled_wave in enumerate(q):
        wave = float(scaled_wave) * h**2
        khat = 2.0 * np.sin(0.5 * wave) if lattice_wave_number else wave
        if abs(khat) < 1.0e-15 or physical_time == 0.0:
            values[index] = 1.0
            continue
        generator = -1j * khat * np.diag(a_diag) - 0.5 * khat**2 * d_white
        evolved = expm_multiply(generator * physical_time, direction)
        values[index] = direction @ evolved
    return {
        "scaled_wave_numbers_q": q,
        "scaled_time_tau": tau,
        "physical_wave_numbers": q * h**2,
        "physical_time": physical_time,
        "structure_factor_over_susceptibility": values,
        "fdt_residual": fdt_residual,
        "method": "full_mode_joint_scaled_krylov_grid",
    }


def complement_invariants(
    operator: Array, *, spectrum_maximum_dimension: int = 1024
) -> dict[str, Array | float | dict[str, int] | str]:
    """Basis-independent diagnostics of spin coupling to all other modes."""

    operator = np.asarray(operator)
    if operator.ndim != 2 or operator.shape[0] != operator.shape[1]:
        raise ValueError("operator must be square")
    left = operator[0, 1:]
    right = operator[1:, 0]
    complement = operator[1:, 1:]
    total = float(np.linalg.norm(complement) ** 2)
    if complement.shape[0] <= spectrum_maximum_dimension:
        singular_values = np.linalg.svd(complement, compute_uv=False)
        squared = singular_values**2
        cumulative = np.cumsum(squared) / max(total, np.finfo(float).tiny)
        retained_ranks = {
            str(fraction): int(np.searchsorted(cumulative, fraction) + 1)
            for fraction in (0.9, 0.99, 0.999)
        }
        spectrum_status = "exact"
    else:
        singular_values = np.asarray([], dtype=float)
        retained_ranks = {}
        spectrum_status = (
            "omitted_above_declared_dimension_to_avoid_an_uncontrolled_"
            "low_rank_approximation"
        )
    return {
        "spin_to_complement_norm": float(np.linalg.norm(right)),
        "complement_to_spin_norm": float(np.linalg.norm(left)),
        "round_trip_scalar": complex(left @ right),
        "complement_frobenius_norm": float(np.sqrt(total)),
        "complement_leading_singular_values": singular_values[:16],
        "complement_energy_retained_ranks": retained_ranks,
        "complement_spectrum_status": spectrum_status,
    }
