"""1D Anderson-localization oracle: H = -t sum (c^dag c + h.c.) + sum eps_i n_i,
eps_i ~ U[-W/2, W/2] i.i.d., t = 1 (PBC/OBC-independent for the bulk
Lyapunov exponent).

Transfer-matrix solution: the tight-binding eigenvalue equation
    -t(psi_{i+1} + psi_{i-1}) + eps_i psi_i = E psi_i
gives, with t = 1,
    (psi_{i+1}, psi_i)^T = T_i (psi_i, psi_{i-1})^T,   T_i = [[E - eps_i, -1], [1, 0]].
Each T_i has det = 1 (SL(2,R)), so the two Lyapunov exponents of the ordered
product T_N...T_1 are +-gamma. gamma is estimated by the standard QR
(Benettin) algorithm: multiply raw matrices for a short batch, then
re-orthogonalize and accumulate log|R_00| (the growing direction). Batches
of ~10 raw multiplications between QR steps keep the running product from
over/underflowing over n_steps = 10**6 site steps.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402


def lyapunov_exponent(E, W, n_steps, seed, qr_interval=10):
    """Largest Lyapunov exponent of the 1D Anderson transfer-matrix product,
    via QR-renormalized products (Benettin/Bennettin-style algorithm).
    Plain-float 2x2 arithmetic (no numpy per-step calls) for speed at
    n_steps ~ 1e6.
    """
    rng = np.random.default_rng(seed)
    eps = rng.uniform(-W / 2.0, W / 2.0, size=n_steps)

    # running orthonormal frame Q, columns (q00,q10) and (q01,q11); starts as I
    q00, q10, q01, q11 = 1.0, 0.0, 0.0, 1.0
    log_r00_sum = 0.0

    i = 0
    while i < n_steps:
        batch = min(qr_interval, n_steps - i)
        m00, m10, m01, m11 = q00, q10, q01, q11
        for j in range(batch):
            a = E - eps[i + j]
            # T @ M, T = [[a, -1], [1, 0]]
            m00, m10 = a * m00 - m10, m00
            m01, m11 = a * m01 - m11, m01
        i += batch

        # QR (Gram-Schmidt) of M = [[m00, m01], [m10, m11]]
        norm0 = math.hypot(m00, m10)
        nq00, nq10 = m00 / norm0, m10 / norm0
        r01 = nq00 * m01 + nq10 * m11
        u01 = m01 - r01 * nq00
        u11 = m11 - r01 * nq10
        norm1 = math.hypot(u01, u11)
        nq01, nq11 = u01 / norm1, u11 / norm1

        log_r00_sum += math.log(abs(norm0))
        q00, q10, q01, q11 = nq00, nq10, nq01, nq11

    return log_r00_sum / n_steps


def thouless_perturbative(E, W):
    """Weak-disorder (2nd-order Born) Lyapunov exponent, box disorder of
    width W: gamma(E) = sigma^2 / (8 sin^2 k), E = 2 cos k, sigma^2 = W^2/12
    -> gamma(E) = W^2 / (96 (1 - (E/2)^2)) [@Thouless1972]. Diverges as
    E -> +-2 (band edge) and is *not* valid at E = 0 (band-center anomaly,
    see ORACLE.md).
    """
    return W ** 2 / (96.0 * (1.0 - (E / 2.0) ** 2))


def compute(E=0.5, W=1.0, n_steps=10 ** 6, seed=1):
    """1D Anderson model, box disorder: transfer-matrix Lyapunov exponent."""
    gamma = lyapunov_exponent(E, W, n_steps, seed)
    return {
        "lyapunov": gamma,
        "xi_loc": 1.0 / gamma,
        "thouless_perturbative": thouless_perturbative(E, W),
    }


def self_test():
    # anchor 1: away from the band-center anomaly (E=0.5), the numerically
    # exact Lyapunov exponent tracks the weak-disorder Thouless formula
    r = compute(E=0.5, W=1.0, n_steps=10 ** 6, seed=1)
    assert 0.7 * r["thouless_perturbative"] < r["lyapunov"] < 1.4 * r["thouless_perturbative"]
    # anchor 2: stronger disorder localizes harder (larger gamma, smaller xi)
    r2 = compute(E=0.5, W=2.0, seed=1)
    assert r2["lyapunov"] > r["lyapunov"]
    assert r2["xi_loc"] < r["xi_loc"]
    # anchor 3: reproducibility -- fixed seed gives an exactly identical result
    r3 = compute(E=0.5, W=1.0, seed=1)
    assert r3["lyapunov"] == r["lyapunov"]


if __name__ == "__main__":
    oracle_main(compute, {
        "E": (float, 0.5),
        "W": (float, 1.0),
        "n_steps": (int, 10 ** 6),
        "seed": (int, 1),
    })
