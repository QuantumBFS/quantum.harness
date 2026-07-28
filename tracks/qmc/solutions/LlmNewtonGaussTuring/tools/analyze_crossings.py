# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Stage 3 crossing analysis for the square-lattice TFIM benchmark.

Reads raw bin-level SSE data and locates the (L, sL) crossings of the
registered dimensionless observables Q_L = <m^2>^2/<m^4> and xi_L/L, with
uncertainties from a bootstrap over bins (Stage 0 protocol 4.2 / 7.4: the
nonlinear estimator is recomputed inside each resample, never propagated from
terminal averages).
"""

import sys
from collections import defaultdict

import numpy as np

H_REF = 3.04438  # published square-lattice h_c/J, Blote-Deng (2002)
N_BOOT = 2000
RNG = np.random.default_rng(20260728)


def load(path):
    raw = np.genfromtxt(path, delimiter=",", names=True)
    cells = defaultdict(list)  # (L, h) -> list of per-bin rows
    for r in raw:
        cells[(int(r["L"]), round(float(r["h"]), 5))].append(
            (r["m2"], r["m4"], r["S0"], r["Sq"])
        )
    return {k: np.asarray(v) for k, v in cells.items()}


def q_of(bins):
    """Q_L = <m^2>^2 / <m^4> from bin averages."""
    m2, m4 = bins[:, 0].mean(), bins[:, 1].mean()
    return m2 * m2 / m4 if m4 > 1e-30 else 0.0


def xi_of(bins, L):
    """Second-moment xi_L/L from S(0) and S(q_min); q_min = 2*pi/L."""
    s0, sq = bins[:, 2].mean(), bins[:, 3].mean()
    if sq <= 1e-30:
        return 0.0
    qmin = 2.0 * np.pi / L
    denom = 4.0 * np.sin(qmin / 2.0) ** 2
    xi2 = (s0 / sq - 1.0) / denom
    return np.sqrt(xi2) / L if xi2 > 0 else 0.0


def curve(cells, L, hs, est, boot_idx=None):
    """Observable vs h for one L; boot_idx selects a bootstrap resample."""
    out = []
    for h in hs:
        b = cells[(L, h)]
        bb = b if boot_idx is None else b[boot_idx[(L, h)]]
        out.append(est(bb, L) if est is xi_of else est(bb))
    return np.array(out)


def crossing(hs, y1, y2):
    """First h where y1 - y2 changes sign, by linear interpolation."""
    d = y1 - y2
    for k in range(len(hs) - 1):
        if d[k] == 0:
            return hs[k]
        if d[k] * d[k + 1] < 0:
            t = d[k] / (d[k] - d[k + 1])
            return hs[k] + t * (hs[k + 1] - hs[k])
    return np.nan


def main(path):
    cells = load(path)
    Ls = sorted({L for L, _ in cells})
    hs = sorted({h for _, h in cells})
    # narrow window around the published value: curvature makes a wide-window
    # linear fit unreliable
    win = [h for h in hs if abs(h - H_REF) <= 0.045]

    print(f"sizes  = {Ls}")
    print(f"window = {win}\n")

    for name, est in (("Q_L", q_of), ("xi_L/L", xi_of)):
        print(f"--- {name} crossings (bootstrap over bins, n={N_BOOT}) ---")
        for a, b in zip(Ls, Ls[1:]):
            y1 = curve(cells, a, win, est)
            y2 = curve(cells, b, win, est)
            hx = crossing(np.array(win), y1, y2)

            samples = []
            for _ in range(N_BOOT):
                idx = {}
                for L in (a, b):
                    for h in win:
                        n = len(cells[(L, h)])
                        idx[(L, h)] = RNG.integers(0, n, n)
                s1 = curve(cells, a, win, est, idx)
                s2 = curve(cells, b, win, est, idx)
                x = crossing(np.array(win), s1, s2)
                if np.isfinite(x):
                    samples.append(x)
            samples = np.array(samples)
            err = samples.std(ddof=1) if len(samples) > 1 else np.nan
            fail = N_BOOT - len(samples)
            dev = (hx - H_REF) / err if err and np.isfinite(err) else np.nan
            print(
                f"  L={a:2d} vs {b:2d}:  h_x = {hx:.5f} +/- {err:.5f}"
                f"   dev from published = {hx - H_REF:+.5f} ({dev:+.1f} sigma)"
                + (f"   [{fail} failed resamples]" if fail else "")
            )
        print()

    # value of each observable at the published h_c, vs L
    print("--- observables at the published h_c (interpolated) ---")
    print(f"{'L':>4} {'Q(h_c)':>10} {'xi/L(h_c)':>12}")
    for L in Ls:
        qs = curve(cells, L, win, q_of)
        xs = curve(cells, L, win, xi_of)
        q = np.interp(H_REF, win, qs)
        x = np.interp(H_REF, win, xs)
        print(f"{L:>4} {q:>10.5f} {x:>12.5f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "square_bins.csv")
