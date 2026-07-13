"""Triangular-lattice classical Ising oracle: H = -J sum_<ij> s_i s_j, s = +-1.

Classical statistical model on the triangular net (each site has 6 neighbours:
horizontal + two diagonal bond families). Conventions: k_B = 1, beta = 1/T;
Z = sum_{s} exp(-beta H); free energy per site f = -T (ln Z)/N. Both signs of J
are physically distinct here: the triangular lattice is NOT bipartite, so the
ferro (J>0) and antiferro (J<0) models are not related by a sublattice gauge.

Exact results:
  * FM (J>0): ordering transition at kT_c/J = 4/ln 3 (Wannier 1950).
  * AFM (J<0): geometric frustration -> NO finite-T transition (T_c = 0) and a
    macroscopic ground-state degeneracy with residual entropy per site
    s0 = (2/pi) int_0^{pi/3} ln(2 cos x) dx = Cl_2(pi/3)/pi ~ 0.32306595, where
    Cl_2 is the Clausen function (Wannier 1950; value corrected in the 1973
    erratum). This is a genuine T=0 residual entropy, not an approximation.

Ground truth: the row-to-row transfer matrix of a width-W triangular torus,
cross-checked against brute-force enumeration over all 2^{L*W} configurations
(the 4x4 torus, both signs of J). ln Z is evaluated in log space (a scaled
matrix power) to avoid overflow. The transfer matrix is non-symmetric because
the diagonal bonds point one way along a row, so its Perron eigenvalue is real
and positive while the rest come in complex-conjugate pairs; tr(T^L) is real.
"""
import sys
from pathlib import Path

import numpy as np
from scipy import integrate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.cli import oracle_main  # noqa: E402

# Clausen function Cl_2(pi/3) = max of the Clausen integral (Gieseking's
# constant). The AFM residual entropy is s0 = Cl_2(pi/3)/pi exactly. This is the
# value corrected in Wannier's 1973 erratum (his 1950 paper misquoted 0.3383);
# the correct modern value is 0.3230659472..., NOT 0.3230659669.
CL2_PI3 = 1.0149416064096536
S0_AFM = CL2_PI3 / np.pi  # 0.32306594721942...


def tc_ferro(J=1.0):
    """FM triangular-Ising critical temperature kT_c/J = 4/ln 3 (Wannier 1950)."""
    return 4.0 * J / np.log(3.0)


def _res_entropy_quad():
    """s0 by adaptive quadrature (scipy.integrate.quad) of the Wannier integral."""
    integrand = lambda x: np.log(2.0 * np.cos(x))
    val, _ = integrate.quad(integrand, 0.0, np.pi / 3.0, epsabs=1e-13, epsrel=1e-13)
    return (2.0 / np.pi) * val


def _res_entropy_gauss(order=256):
    """s0 by a high-order Gauss-Legendre fixed rule (independent quadrature)."""
    x, w = np.polynomial.legendre.leggauss(order)
    a, b = 0.0, np.pi / 3.0
    xm = 0.5 * (b - a) * x + 0.5 * (b + a)
    val = 0.5 * (b - a) * np.sum(w * np.log(2.0 * np.cos(xm)))
    return (2.0 / np.pi) * val


def residual_entropy_afm():
    """AFM (J<0) ground-state residual entropy per site s0 = Cl_2(pi/3)/pi.

    s0 = (2/pi) int_0^{pi/3} ln(2 cos x) dx ~ 0.3230659472. Nonzero because the
    frustrated triangular AFM has a macroscopically degenerate ground manifold.
    """
    return _res_entropy_quad()


# ---- triangular-torus transfer matrix (ground truth vs enumeration) ----

def _row_spins(W):
    """All 2^W row configurations as +-1 spin rows, shape (2^W, W)."""
    idx = np.arange(2 ** W)
    bits = (idx[:, None] >> np.arange(W)[None, :]) & 1
    return (1 - 2 * bits).astype(float)


def _log_transfer(W, beta, J):
    """log of the width-W triangular-row transfer matrix (non-symmetric).

    Bond families per site: horizontal (in-row j->j+1), vertical (row i->i+1,
    same column), diagonal (row i->i+1, column j->j+1); all PBC. Half of each
    row's intra-row (horizontal) energy is assigned to each of its two
    appearances as top/bottom row, so Z on an L-row torus is tr(T^L).
    """
    s = _row_spins(W)
    e_row = -J * np.sum(s * np.roll(s, -1, axis=1), axis=1)      # horizontal
    vert = s @ s.T                                               # a_j b_j
    diag = s @ np.roll(s, -1, axis=1).T                         # a_j b_{j+1}
    e_inter = -J * (vert + diag)
    return -beta * (0.5 * e_row[:, None] + 0.5 * e_row[None, :] + e_inter)


def logZ_finite(L, beta, J, W=None):
    """ln Z of the L x W triangular torus via tr(T^L) (log space, W defaults to L).

    Computed as L*max(logT) + ln tr(Ts^L) with Ts the transfer matrix rescaled
    by its largest log-entry, so no intermediate overflows even at large beta.
    """
    if W is None:
        W = L
    lT = _log_transfer(W, beta, J)
    m = lT.max()
    Ts = np.exp(lT - m)
    Z = np.trace(np.linalg.matrix_power(Ts, L))
    return L * m + np.log(Z)


def free_energy_per_site(T, J, W=6):
    """Free energy per site from the width-W transfer-matrix Perron eigenvalue.

    f = -T ln(lambda_max)/W. This is the exact free energy of an infinitely long
    strip of width W (semi-1D), NOT the 2D thermodynamic limit: it is width-
    limited and converges to the bulk value only as W -> infinity. Documented as
    such for regime honesty.
    """
    beta = 1.0 / T
    lam = np.linalg.eigvals(np.exp(_log_transfer(W, beta, J)))
    lam_max = lam[np.argmax(lam.real)].real  # Perron eigenvalue (real, positive)
    return -T * np.log(lam_max) / W


def _enumerate_logZ(L, W, beta, J):
    """Ground-truth ln Z by direct sum over all 2^{L*W} configurations."""
    from scipy.special import logsumexp
    N = L * W
    bits = (np.arange(2 ** N)[:, None] >> np.arange(N)[None, :]) & 1
    s = (1 - 2 * bits).reshape(-1, L, W)
    h = (s * np.roll(s, -1, axis=2)).sum(axis=(1, 2))                 # horizontal
    v = (s * np.roll(s, -1, axis=1)).sum(axis=(1, 2))                 # vertical
    d = (s * np.roll(np.roll(s, -1, axis=1), -1, axis=2)).sum(axis=(1, 2))  # diag
    return logsumexp(beta * J * (h + v + d))


def compute(T=2.0, J=1.0, L=4):
    """Triangular Ising exact quantities: FM T_c, AFM residual entropy, finite-torus ln Z."""
    beta = 1.0 / T
    return {
        "tc_ferro": tc_ferro(),
        "residual_entropy_afm": residual_entropy_afm(),
        "logZ_finite": logZ_finite(L, beta, J),
        "free_energy_per_site_width6": free_energy_per_site(T, J, W=6),
    }


def self_test():
    # anchor 1: FM critical temperature closed form kT_c/J = 4/ln 3
    assert abs(tc_ferro() - 4.0 / np.log(3.0)) < 1e-12
    assert abs(tc_ferro() - 3.6409569065073493) < 1e-12
    # anchor 2: AFM residual entropy -- two independent quadratures agree, and
    # both match the closed form Cl_2(pi/3)/pi (the correct post-erratum value)
    q, g = _res_entropy_quad(), _res_entropy_gauss()
    assert abs(q - g) < 1e-10, (q, g)
    assert abs(q - S0_AFM) < 1e-9, (q, S0_AFM)
    assert abs(S0_AFM - 0.3230659472194255) < 1e-12
    # anchor 3: GROUND TRUTH -- transfer-matrix ln Z equals brute-force
    # enumeration on the 4x4 torus, both signs of J, at two temperatures
    for J in (1.0, -1.0):
        for beta in (0.3, 0.8):
            t = logZ_finite(4, beta, J, W=4)
            e = _enumerate_logZ(4, 4, beta, J)
            assert abs(t - e) <= 1e-10 * abs(e), (J, beta, t, e)
    # width-limited free energy is finite, real, and lower for FM than AFM at T=2
    f_fm = free_energy_per_site(2.0, 1.0, W=6)
    f_afm = free_energy_per_site(2.0, -1.0, W=6)
    assert np.isfinite(f_fm) and np.isfinite(f_afm) and f_fm < f_afm


if __name__ == "__main__":
    oracle_main(compute, {"T": (float, 2.0), "J": (float, 1.0), "L": (int, 4)})
