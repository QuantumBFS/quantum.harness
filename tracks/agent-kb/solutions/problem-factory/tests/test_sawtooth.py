"""Anchor tests for the sawtooth-chain builder (issue #112 day-1 battery).

Run: python3 tests/test_sawtooth.py   (plain asserts, no pytest needed)

Anchors (all closed-form, from issue #112):
  1. flat band at J2=2*J1: lowest one-magnon band exactly flat at eps = -4*J1
  2. Monti-Suto point J2=J1, h=0: exactly 2-fold degenerate ground state
     (a DIFFERENT special point from J2=2*J1 — the issue's flagged trap)
  3. magnetization jump: at h_sat=4*J1 the ground-state energy is identical
     in every magnon sector, so magnons cost nothing -> jump dM = M_sat/2
  4. degeneracy + residual entropy: total GS degeneracy at h_sat equals the
     Lucas number L(N/2); for N=12, L(6)=18, and ln(18)/12 = 0.2409 ~ 0.2406
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pf import ed

J1, J2, H_SAT = 1.0, 2.0, 4.0  # flat-band point and its saturation field


def dense_all(H):
    return np.linalg.eigvalsh(H.toarray())


def polarized_energy(N, j1, j2, h):
    nc = N // 2  # N_c J1 bonds + 2*N_c J2 bonds, each contributing J/4
    return (j1 + 2 * j2) * nc / 4 - h * N / 2


def test_flat_band():
    N = 12
    H = ed.sawtooth_hamiltonian(N, j2=J2, j1=J1, h=0.0, n_up=N - 1)
    band = dense_all(H)[: N // 2] - polarized_energy(N, J1, J2, 0.0)
    assert np.allclose(band, -4 * J1, atol=1e-10), f"band not flat: {band}"


def test_monti_suto_twofold():
    N = 12
    H = ed.sawtooth_hamiltonian(N, j2=1.0, j1=J1, h=0.0, n_up=N // 2)
    w = dense_all(H)
    assert w[1] - w[0] < 1e-10, f"not twofold degenerate: {w[:3]}"
    assert w[2] - w[0] > 1e-3, f"no gap above the doublet: {w[:3]}"


def test_jump_sector_energies_equal():
    # Localized magnons obey a hard-dimer constraint: at most N/4 fit on N/2
    # cells. So at h_sat the GS energy is flat for k <= N/4 (zero-cost magnons
    # -> the jump dM = M_sat/2) and must RISE once magnons overlap.
    N = 12
    e = np.array([
        dense_all(ed.sawtooth_hamiltonian(N, j2=J2, j1=J1, h=H_SAT, n_up=N - k))[0]
        for k in range(N // 2 + 1)
    ])
    k_flat = N // 4
    assert np.allclose(e[: k_flat + 1], e[0], atol=1e-8), f"not flat: {e[:k_flat+1]}"
    assert all(e[k] - e[0] > 1e-3 for k in range(k_flat + 1, N // 2 + 1)), \
        f"no cost for overlapping magnons: {e}"


def test_degeneracy_lucas_and_entropy():
    N = 12
    e0 = polarized_energy(N, J1, J2, H_SAT)
    total = sum(
        int(np.sum(np.abs(dense_all(
            ed.sawtooth_hamiltonian(N, j2=J2, j1=J1, h=H_SAT, n_up=N - k)) - e0) < 1e-8))
        for k in range(N // 2 + 1)
    )
    assert total == 18, f"expected Lucas(6)=18, got {total}"
    assert abs(np.log(total) / N - 0.2406) < 1e-3, f"S/N = {np.log(total)/N}"


def test_static_fire_registry():
    from pf import static_fire
    ok, detail = static_fire.CHECKS["sawtooth_flat_band"]()
    assert ok, detail
    ok, detail = static_fire.CHECKS["sawtooth_hsat_degeneracy"]()
    assert ok, detail


def test_magnetization_jump():
    # At the flat-band point the m=1/4 crystal is the GS right up to h_sat,
    # then saturation arrives in ONE jump of dM = 1/4 = M_sat/2 (issue #112).
    from pf import sawtooth
    N = 12
    e = sawtooth.sector_energies(N, j2=2.0, j1=1.0)
    k_below = sawtooth.gs_sector(e, h=3.999)
    k_above = sawtooth.gs_sector(e, h=4.001)
    assert k_below == N // 4, f"expected m=1/4 crystal below h_sat, got k={k_below}"
    assert k_above == 0, f"expected saturation above h_sat, got k={k_above}"
    assert (k_below - k_above) / N == 0.25  # jump height = M_sat/2


if __name__ == "__main__":
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        fn()
        print(f"[pass] {name}", flush=True)
    print("all anchors green")
