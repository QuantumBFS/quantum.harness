"""Core dynamics and black-box boundary for challenge #113.

The differentiable model is deliberately kept separate from ``BlackBoxDevice``.
Model-side code may use JAX gradients and Hessians.  Closed-loop optimizers only
receive the scalar returned by ``BlackBoxDevice.query``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Literal

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np
from jax.experimental import ode
from jax.scipy.linalg import expm


Array = jax.Array
Integrator = Literal["expm", "odeint"]


@dataclass(frozen=True)
class ControlProblem:
    """A Fourier-parameterized unitary gate-control problem."""

    h0: Array
    h_ctrl: Array
    target: Array
    initial_params: Array
    t_final: float
    n_basis: int
    seed: int

    @property
    def dim(self) -> int:
        return int(self.h0.shape[0])

    @property
    def n_ctrl(self) -> int:
        return int(self.h_ctrl.shape[0])

    @property
    def n_params(self) -> int:
        return self.n_ctrl * self.n_basis


@dataclass(frozen=True)
class QueryRecord:
    """One device query, including simulation-only latent diagnostics."""

    query: int
    reported_fidelity: float
    exact_fidelity: float
    params: np.ndarray


class BlackBoxDevice:
    """Query-only fidelity oracle with optional finite-shot noise.

    ``exact_fidelity_fn`` is private implementation detail.  Optimizers should
    only call ``query`` and inspect its scalar loss.  Exact fidelity is retained
    in ``history`` solely for offline simulation diagnostics.
    """

    def __init__(
        self,
        exact_fidelity_fn: Callable[[Array], Array],
        *,
        shots: int | None = None,
        seed: int = 0,
    ) -> None:
        if shots is not None and shots <= 0:
            raise ValueError("shots must be positive or None")
        self._exact_fidelity_fn = exact_fidelity_fn
        self.shots = shots
        self._rng = np.random.default_rng(seed)
        self.history: list[QueryRecord] = []

    @property
    def query_count(self) -> int:
        return len(self.history)

    @property
    def shot_count(self) -> int:
        return self.query_count * (self.shots or 0)

    def reset(self, *, seed: int | None = None) -> None:
        self.history.clear()
        if seed is not None:
            self._rng = np.random.default_rng(seed)

    def query(self, params: np.ndarray | Array) -> float:
        """Return reported infidelity and increment the device budget."""

        params_array = jnp.asarray(params, dtype=jnp.float64)
        exact = float(self._exact_fidelity_fn(params_array))
        exact = float(np.clip(exact, 0.0, 1.0))
        if self.shots is None:
            reported = exact
        else:
            reported = float(self._rng.binomial(self.shots, exact) / self.shots)
        self.history.append(
            QueryRecord(
                query=self.query_count + 1,
                reported_fidelity=reported,
                exact_fidelity=exact,
                params=np.asarray(params, dtype=np.float64).copy(),
            )
        )
        return 1.0 - reported


def _random_hermitian(key_real: Array, key_imag: Array, dim: int) -> Array:
    matrix = jax.random.normal(key_real, (dim, dim))
    matrix = matrix + 1j * jax.random.normal(key_imag, (dim, dim))
    return (matrix + matrix.conj().T) / 2.0


def cnot() -> Array:
    """Return the two-qubit CNOT target used by the starting notebook."""

    return jnp.asarray(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ],
        dtype=jnp.complex128,
    )


def pauli_x() -> Array:
    """Return the single-qubit Pauli-X target."""

    return jnp.asarray([[0, 1], [1, 0]], dtype=jnp.complex128)


def make_random_control_problem(
    *,
    dim: int,
    target: Array,
    seed: int = 42,
    n_ctrl: int = 4,
    n_basis: int = 10,
    t_final: float = 1.0,
) -> ControlProblem:
    """Construct a seeded over-parameterized random control problem."""

    if dim < 2:
        raise ValueError("dim must be at least two")
    target = jnp.asarray(target, dtype=jnp.complex128)
    if target.shape != (dim, dim):
        raise ValueError("target shape must match dim")
    key = jax.random.PRNGKey(seed)
    key, key_real, key_imag = jax.random.split(key, 3)
    h0 = _random_hermitian(key_real, key_imag, dim)

    controls = []
    for _ in range(n_ctrl):
        key, key_real, key_imag = jax.random.split(key, 3)
        controls.append(_random_hermitian(key_real, key_imag, dim))

    key, init_key = jax.random.split(key)
    initial_params = (
        jax.random.normal(init_key, (n_ctrl * n_basis,), dtype=jnp.float64) * 0.01
    )
    return ControlProblem(
        h0=h0,
        h_ctrl=jnp.stack(controls),
        target=target,
        initial_params=initial_params,
        t_final=t_final,
        n_basis=n_basis,
        seed=seed,
    )


def make_demo_problem(
    *,
    seed: int = 42,
    n_ctrl: int = 4,
    n_basis: int = 10,
    t_final: float = 1.0,
) -> ControlProblem:
    """Reproduce the random-Hamiltonian CNOT setup in the supplied notebook."""

    return make_random_control_problem(
        dim=4,
        target=cnot(),
        seed=seed,
        n_ctrl=n_ctrl,
        n_basis=n_basis,
        t_final=t_final,
    )


def make_single_qubit_problem(
    *,
    seed: int = 42,
    n_ctrl: int = 2,
    n_basis: int = 10,
    t_final: float = 1.0,
) -> ControlProblem:
    """Return an over-parameterized single-qubit Pauli-X control problem."""

    return make_random_control_problem(
        dim=2,
        target=pauli_x(),
        seed=seed,
        n_ctrl=n_ctrl,
        n_basis=n_basis,
        t_final=t_final,
    )


def fourier_controls(problem: ControlProblem, t: Array, params: Array) -> Array:
    """Evaluate all control amplitudes at time ``t``."""

    coefficients = jnp.reshape(params, (problem.n_ctrl, problem.n_basis))
    harmonics = jnp.arange(1, problem.n_basis + 1, dtype=jnp.float64)
    basis = jnp.sin(harmonics * jnp.pi * t / problem.t_final)
    return coefficients @ basis


def hamiltonian(problem: ControlProblem, t: Array, params: Array) -> Array:
    amplitudes = fourier_controls(problem, t, params)
    return problem.h0 + jnp.einsum("i,ijk->jk", amplitudes, problem.h_ctrl)


def propagate_expm(
    problem: ControlProblem,
    params: Array,
    *,
    n_steps: int = 100,
) -> Array:
    """Midpoint product-of-exponentials propagation.

    Each step is unitary up to matrix-exponential roundoff, making this the
    structure-preserving reference backend.
    """

    if n_steps <= 0:
        raise ValueError("n_steps must be positive")
    dt = problem.t_final / n_steps
    times = (jnp.arange(n_steps, dtype=jnp.float64) + 0.5) * dt
    identity = jnp.eye(problem.dim, dtype=jnp.complex128)

    def step(unitary: Array, time: Array) -> tuple[Array, None]:
        generator = -1j * hamiltonian(problem, time, params) * dt
        return expm(generator) @ unitary, None

    final, _ = jax.lax.scan(step, identity, times)
    return final


def propagate_odeint(
    problem: ControlProblem,
    params: Array,
    *,
    rtol: float = 1e-10,
    atol: float = 1e-10,
    mxstep: int = 4096,
) -> Array:
    """The generic ODE backend used by the supplied notebook."""

    def rhs(unitary: Array, time: Array, theta: Array) -> Array:
        return -1j * hamiltonian(problem, time, theta) @ unitary

    trajectory = ode.odeint(
        rhs,
        jnp.eye(problem.dim, dtype=jnp.complex128),
        jnp.asarray([0.0, problem.t_final], dtype=jnp.float64),
        params,
        rtol=rtol,
        atol=atol,
        mxstep=mxstep,
    )
    return trajectory[-1]


def make_propagator(
    problem: ControlProblem,
    *,
    integrator: Integrator = "expm",
    n_steps: int = 100,
    rtol: float = 1e-10,
    atol: float = 1e-10,
) -> Callable[[Array], Array]:
    if integrator == "expm":
        return lambda params: propagate_expm(problem, params, n_steps=n_steps)
    if integrator == "odeint":
        return lambda params: propagate_odeint(
            problem, params, rtol=rtol, atol=atol
        )
    raise ValueError(f"unknown integrator: {integrator}")


def gate_fidelity(unitary: Array, target: Array) -> Array:
    """Phase-insensitive trace fidelity used by the challenge notebook."""

    dim = target.shape[0]
    return jnp.abs(jnp.trace(unitary.conj().T @ target)) / dim


def make_fidelity(
    problem: ControlProblem,
    *,
    integrator: Integrator = "expm",
    n_steps: int = 100,
    rtol: float = 1e-10,
    atol: float = 1e-10,
) -> Callable[[Array], Array]:
    propagate = make_propagator(
        problem,
        integrator=integrator,
        n_steps=n_steps,
        rtol=rtol,
        atol=atol,
    )
    return lambda params: gate_fidelity(propagate(params), problem.target)


def make_loss(
    problem: ControlProblem,
    *,
    integrator: Integrator = "expm",
    n_steps: int = 100,
    rtol: float = 1e-10,
    atol: float = 1e-10,
) -> Callable[[Array], Array]:
    fidelity = make_fidelity(
        problem,
        integrator=integrator,
        n_steps=n_steps,
        rtol=rtol,
        atol=atol,
    )
    return lambda params: 1.0 - fidelity(params)


def unitarity_defect(unitary: Array) -> Array:
    identity = jnp.eye(unitary.shape[0], dtype=unitary.dtype)
    return jnp.linalg.norm(unitary.conj().T @ unitary - identity)


def phase_aligned_unitary_distance(left: Array, right: Array) -> Array:
    """Frobenius distance after removing the best global phase."""

    overlap = jnp.trace(left.conj().T @ right)
    aligned_right = right * jnp.exp(-1j * jnp.angle(overlap))
    return jnp.linalg.norm(left - aligned_right)


def make_drift_perturbation(
    problem: ControlProblem,
    *,
    seed: int = 113,
) -> Array:
    """Create a traceless Hermitian perturbation normalized to ``||H0||F``."""

    key = jax.random.PRNGKey(seed)
    key_real, key_imag = jax.random.split(key)
    perturbation = _random_hermitian(key_real, key_imag, problem.dim)
    perturbation = perturbation - (
        jnp.trace(perturbation) / problem.dim
    ) * jnp.eye(problem.dim, dtype=jnp.complex128)
    return perturbation * (
        jnp.linalg.norm(problem.h0) / jnp.linalg.norm(perturbation)
    )


def with_drift_mismatch(
    problem: ControlProblem,
    perturbation: Array,
    epsilon: float,
) -> ControlProblem:
    """Return a simulated true device with ``H0,true = H0 + epsilon V``."""

    return replace(problem, h0=problem.h0 + epsilon * perturbation)
