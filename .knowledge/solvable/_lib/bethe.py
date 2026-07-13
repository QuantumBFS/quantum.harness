"""Coordinate Bethe-ansatz solver for the spin-1/2 XXX Heisenberg chain.

Convention: H = J sum_i S_i . S_{i+1} with S^a = sigma^a/2, J = 1, PBC.
The antiferromagnetic ground state lives in the S^z = 0 sector (M = N/2 down
spins over the ferromagnetic reference |up...up>) and is described by N/2 REAL
Bethe roots {lambda_j} — the "1-string" solution (no bound states).

Rapidity Bethe equations (logarithmic form):

    2 arctan(2 lambda_j) = (2 pi / N) I_j + (2 / N) sum_k arctan(lambda_j - lambda_k)

with ground-state quantum numbers I_j = {-(M-1)/2, ..., +(M-1)/2} (M = N/2),
consecutive with unit spacing; they are integers when M is odd and half-integers
when M is even (parity fixed automatically by the -(M-1)/2 offset).

Each root contributes energy epsilon(lambda) = -2 / (4 lambda^2 + 1) above the
ferromagnetic reference (whose energy is N/4), so

    E = N/4 - sum_j 2 / (4 lambda_j^2 + 1).

Both are pinned to brute-force ED at 1e-10 in tests/test_lib.py.
"""
import numpy as np


def _ground_quantum_numbers(N):
    """Ground-state Bethe quantum numbers I_j for M = N/2 magnons.

    I_j = -(M-1)/2 + (j-1), j = 1..M — consecutive, symmetric about 0, with the
    integer/half-integer parity fixed by M mod 2.
    """
    M = N // 2
    return np.arange(M) - (M - 1) / 2.0


def xxx_ground_roots(N, tol=1e-14, max_iter=100000, damping=0.5):
    """Real Bethe roots of the XXX antiferromagnetic ground state (S^z=0 sector).

    Solves the logarithmic Bethe equations by damped fixed-point iteration,
    seeding from the interaction-free (single-root density) positions
    lambda_j^(0) = (1/2) tan(pi I_j / N).  Iterates to `tol` residual.

    Returns an array of N/2 real roots (N must be even).
    """
    if N % 2 != 0:
        raise ValueError("N must be even (S^z=0 sector needs N/2 magnons)")
    I = _ground_quantum_numbers(N)

    # Interaction-free seed: drop the sum term.
    lam = 0.5 * np.tan(np.pi * I / N)

    for _ in range(max_iter):
        # rhs_j = pi I_j / N + (1/N) sum_k arctan(lambda_j - lambda_k)
        diff = lam[:, None] - lam[None, :]
        rhs = np.pi * I / N + np.arctan(diff).sum(axis=1) / N
        new = 0.5 * np.tan(rhs)
        # damped update stabilises the tan() fixed point
        upd = (1 - damping) * lam + damping * new
        if np.max(np.abs(upd - lam)) < tol:
            lam = upd
            break
        lam = upd
    else:  # pragma: no cover - convergence failure guard
        raise RuntimeError(f"Bethe roots did not converge for N={N}")

    # residual check against the defining equation
    diff = lam[:, None] - lam[None, :]
    res = 2 * np.arctan(2 * lam) - (2 * np.pi * I / N
                                    + 2 * np.arctan(diff).sum(axis=1) / N)
    if np.max(np.abs(res)) > 1e-10:  # pragma: no cover
        raise RuntimeError(f"Bethe residual too large for N={N}: "
                           f"{np.max(np.abs(res)):.2e}")
    return lam


def xxx_energy(roots, N):
    """Ground-state energy E = N/4 - sum_j 2/(4 lambda_j^2 + 1) (J=1, S-convention)."""
    roots = np.asarray(roots, dtype=float)
    return N / 4.0 - np.sum(2.0 / (4.0 * roots ** 2 + 1.0))
