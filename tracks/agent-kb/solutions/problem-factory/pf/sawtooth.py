"""Magnetization physics of the sawtooth chain (issue #112 erosion axis).

Ground-state energies e0(k) per magnon sector at h=0 are computed once;
the magnetization curve then follows exactly, because the field only adds
-h*Sz:  k*(h) = argmin_k [ e0(k) - h*(N/2 - k) ].

Erosion observables vs detuning delta = J2/J1 - 2:
  W(delta)   - width of the m=1/4 plateau (the localized-magnon crystal)
  dM(delta)  - largest single-step magnetization jump at saturation
  Gamma(delta) - field window over which the dM=M_sat/2 jump is smeared
The one-magnon bandwidth of the detuned flat band is the single-particle
scale Gamma should track if interactions stay irrelevant.
"""

import numpy as np
import scipy.sparse.linalg as sla

from . import ed

H_SAT = 4.0  # at j2 = 2*j1, j1 = 1


def sector_energies(N, j2, j1=1.0):
    """e0(k) at h=0 for k = 0..N/2 (k = number of down spins / magnons)."""
    e = []
    for k in range(N // 2 + 1):
        H = ed.sawtooth_hamiltonian(N, j2=j2, j1=j1, h=0.0, n_up=N - k)
        if H.shape[0] < 64:
            e.append(np.linalg.eigvalsh(H.toarray())[0])
        else:
            e.append(sla.eigsh(H, k=1, which="SA", tol=1e-12,
                               return_eigenvectors=False)[0])
    return np.array(e)


def gs_sector(e0, h):
    """Winning sector k*(h) = argmin_k e0(k) - h*(N/2 - k)."""
    N = 2 * (len(e0) - 1)
    sz = N / 2 - np.arange(len(e0))
    return int(np.argmin(e0 - h * sz))


def magnetization_curve(e0, h_grid):
    N = 2 * (len(e0) - 1)
    return np.array([(N / 2 - gs_sector(e0, h)) / N for h in h_grid])


def one_magnon_band(N, j2, j1=1.0):
    """Lowest one-magnon band (exact, dim-N sector). Returns min and max."""
    w = np.linalg.eigvalsh(ed.sawtooth_hamiltonian(N, j2=j2, j1=j1, h=0.0, n_up=N - 1).toarray())
    band = w[: N // 2]
    return float(band.min()), float(band.max())


def erosion_metrics(N, j2, j1=1.0, h_grid=None):
    """W, dM, Gamma from the magnetization staircase at detuning j2/j1 - 2."""
    if h_grid is None:
        h_grid = np.linspace(2.0, 6.0, 1601)
    e0 = sector_energies(N, j2, j1)
    m = magnetization_curve(e0, h_grid)

    plateau = h_grid[np.isclose(m, 0.25, atol=0.5 / N)]
    W = float(plateau.max() - plateau.min()) if len(plateau) else 0.0

    jumps = np.diff(m) / (h_grid[1] - h_grid[0])
    i_main = int(np.argmax(jumps))
    dM = float(m[i_main + 1] - m[i_main])

    near_sat = h_grid[(m > 0.25 + 0.5 / N) & (m < 0.5 - 0.5 / N)]
    Gamma = float(near_sat.max() - near_sat.min()) if len(near_sat) else 0.0

    lo, hi = one_magnon_band(N, j2, j1)
    return {"W": W, "dM": dM, "Gamma": Gamma, "bandwidth": hi - lo,
            "e0": e0.tolist(), "h": h_grid.tolist(), "m": m.tolist()}
