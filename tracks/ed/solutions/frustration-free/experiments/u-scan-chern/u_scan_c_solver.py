#!/usr/bin/env python3
"""U_scan_C_solver: many-body Chern number C(U) for the spinful Rice-Mele-Hubbard model.

Fixed unbiased pump path:
    delta(phi) = delta0 * cos(phi),   Delta(phi) = Delta0 * sin(phi)
with delta0 = 0.9, Delta0 = 3.0, and Delta_offset = 0.

Scans U from attractive to repulsive, computing C(U) via the FHS discrete
gauge method on a (theta, phi) torus.  Produces CSV tables, Berry-curvature
maps, and publication-quality figures.

Usage:
    python u_scan_c_solver.py                # full scan (cluster)
    python u_scan_c_solver.py --smoke        # fast smoke test
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Sequence

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian

# ---------------------------------------------------------------------------
# Reuse the validated FHS machinery from the existing U=0 Chern experiment
# ---------------------------------------------------------------------------
_EXPERIMENTS_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _EXPERIMENTS_ROOT.parent
_IMPORT_PATH = _EXPERIMENTS_ROOT / "rice-mele-chern"
sys.path.insert(0, str(_IMPORT_PATH))
from run_rice_mele_chern import (  # noqa: E402
    FHSDiagnostics,
    compute_fhs,
    verify_gauge_invariance,
)


# ===========================================================================
# Physical parameters (fixed for this experiment)
# ===========================================================================
T = 1.0
DELTA0 = 0.9
CAPITAL_DELTA0 = 3.0

# Coarse U grid (per spec Section 4)
U_COARSE = [
    -32, -24, -16, -12, -8, -6, -4, -2,
    0, 2, 4, 5, 5.5, 5.8, 6.0, 6.2, 6.5, 7, 8, 10, 12, 16, 24, 32,
]

# U values for grid-convergence checks (per spec Section 7)
GRID_CONVERGENCE_U = [-16, 0, 5.5, 6.0, 6.5, 10]

# Grid sizes for convergence check
GRID_CONVERGENCE_SIZES = (5, 9, 11)

# ---------- helper --------------------------------------------------------


def _build_filename_stem(U: float, L: int, N_theta: int, N_phi: int) -> str:
    """Deterministic filename stem encoding all scan parameters."""
    U_str = f"U_{U:+.6f}".replace("+", "p").replace("-", "neg").replace(".", "d")
    return f"scan_{U_str}_L{L}_Ntheta{N_theta}_Nphi{N_phi}"


# ===========================================================================
# Dataclasses
# ===========================================================================


@dataclass
class VertexResult:
    """Cached result for a single (theta, phi) grid point."""
    state: np.ndarray
    energies: tuple[float, float]
    gap: float
    hermiticity_error: float
    residual: float


@dataclass
class ScanResult:
    """Complete diagnostics for a single U value on one (N_theta, N_phi) grid."""
    U: float
    L: int
    N_theta: int
    N_phi: int
    C_raw: float
    C_rounded: int
    chern_error: float
    gap_min: float
    theta_gap_min: float
    phi_gap_min: float
    min_link_overlap: float
    max_abs_berry_curvature: float
    solver_residual: float
    converged: bool
    berry_curvature_map: np.ndarray
    ground_state_energies: np.ndarray
    first_excited_energies: np.ndarray
    hermiticity_errors: np.ndarray
    diagonalization_count: int
    wall_time_s: float

    def as_dict(self) -> dict:
        return {
            "U": self.U,
            "L": self.L,
            "N_theta": self.N_theta,
            "N_phi": self.N_phi,
            "C_raw": self.C_raw,
            "C_rounded": self.C_rounded,
            "chern_error": self.chern_error,
            "gap_min": self.gap_min,
            "theta_gap_min": self.theta_gap_min,
            "phi_gap_min": self.phi_gap_min,
            "min_link_overlap": self.min_link_overlap,
            "max_abs_berry_curvature": self.max_abs_berry_curvature,
            "solver_residual": self.solver_residual,
            "converged": self.converged,
            "diagonalization_count": self.diagonalization_count,
            "wall_time_s": self.wall_time_s,
        }


# ===========================================================================
# Rice-Mele-Hubbard Chern solver
# ===========================================================================


class RiceMeleHubbardSolver:
    """Cached exact-diagonalisation scan over a (theta, phi) torus for one U.

    Parameters
    ----------
    L : int
        Number of sites (must be even, half-filling).
    U : float
        Hubbard interaction strength.
    t : float
        Bare hopping amplitude (default 1.0).
    delta0 : float
        Staggered-hopping amplitude δ₀ (default 0.9).
    Delta0 : float
        Staggered-potential amplitude Δ₀ (default 3.0).
    """

    def __init__(
        self,
        L: int = 6,
        U: float = 0.0,
        t: float = T,
        delta0: float = DELTA0,
        Delta0: float = CAPITAL_DELTA0,
    ) -> None:
        if L % 2:
            raise ValueError(f"L must be even, got {L}")
        self.L = L
        self.U = U
        self.t = t
        self.delta0 = delta0
        self.Delta0 = Delta0
        particles_per_spin = L // 2
        self.basis = spinful_fermion_basis_1d(L, Nf=(particles_per_spin, particles_per_spin))
        self._cache: dict[tuple[Fraction, Fraction], VertexResult] = {}
        self._diag_count = 0

    # ------------------------------------------------------------------ Hamiltonian

    def build_hamiltonian(self, phi: float, theta: float):
        """Return QuSpin Hamiltonian at pump phase `phi` and twist `theta`.

        Conventions (spec §1-2):
            H = -Σ_{j,σ} [t + (-1)^j δ(φ)] (c†_{jσ}c_{j+1,σ} + h.c.)
                + Δ(φ) Σ_{j,σ} (-1)^j n_{jσ}
                + U Σ_j n_{j↑} n_{j↓}
            δ(φ) = δ₀ cos φ,   Δ(φ) = Δ₀ sin φ
            c_{L,σ} = e^{iθ} c_{0,σ}   (spin-independent twist)
        """
        delta = self.delta0 * np.cos(phi)
        Delta = self.Delta0 * np.sin(phi)

        up_hopping: list = []
        down_hopping: list = []

        # bulk bonds j=0 … L-2
        for j in range(self.L - 1):
            coeff = -(self.t + ((-1) ** j) * delta)
            up_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])
            down_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])

        # boundary bond (L-1) ↔ 0 with twist e^{iθ}
        boundary_coeff = -(self.t + ((-1) ** (self.L - 1)) * delta)
        fwd = boundary_coeff * np.exp(1j * theta)
        bwd = boundary_coeff * np.exp(-1j * theta)
        up_hopping.extend([[fwd, self.L - 1, 0], [bwd, 0, self.L - 1]])
        down_hopping.extend([[fwd, self.L - 1, 0], [bwd, 0, self.L - 1]])

        # staggered onsite  (spec uses (-1)^j)
        onsite = [[Delta * ((-1) ** j), j] for j in range(self.L)]

        static: list = [
            ["+-|", up_hopping],
            ["|+-", down_hopping],
            ["n|", onsite],
            ["|n", onsite],
        ]

        # Hubbard U term
        if self.U != 0.0:
            static.append(["n|n", [[self.U, j, j] for j in range(self.L)]])

        return hamiltonian(
            static, [], basis=self.basis, dtype=np.complex128,
            check_herm=False, check_symm=False, check_pcon=False,
        )

    # ------------------------------------------------------------------ Vertex

    def _vertex(self, key: tuple[Fraction, Fraction]) -> VertexResult:
        """Return (cached) ground state and diagnostics for one grid point."""
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        theta_frac, phi_frac = key
        theta = 2.0 * np.pi * float(theta_frac)
        phi = 2.0 * np.pi * float(phi_frac)

        H = self.build_hamiltonian(phi, theta)

        # Sparse eigsh first (fast for L ≥ 8); fall back to dense eigh on
        # non-convergence (e.g. near-degenerate ground state at strong U).
        try:
            energies, vectors = H.eigsh(
                k=2, which="SA", maxiter=200000, tol=1e-8,
            )
            order = np.argsort(energies)
            e0 = float(energies[order[0]].real)
            e1 = float(energies[order[1]].real)
            state = np.asarray(vectors[:, order[0]], dtype=np.complex128)
            state /= np.linalg.norm(state)
            matrix = H.toarray()
            herm_error = float(np.max(np.abs(matrix - matrix.conj().T)))
        except Exception:
            matrix = H.toarray()
            herm_error = float(np.max(np.abs(matrix - matrix.conj().T)))
            if herm_error >= 1e-12:
                raise RuntimeError(f"H not Hermitian: error={herm_error:.3e}")
            energies, vectors = np.linalg.eigh(matrix)
            e0, e1 = float(energies[0].real), float(energies[1].real)
            state = np.asarray(vectors[:, 0], dtype=np.complex128)

        if herm_error >= 1e-12:
            raise RuntimeError(f"H not Hermitian: error={herm_error:.3e}")

        # Residual  || H|ψ⟩ - E₀|ψ⟩ ||
        Hpsi = matrix @ state
        residual = float(np.linalg.norm(Hpsi - e0 * state))

        result = VertexResult(
            state=state,
            energies=(e0, e1),
            gap=e1 - e0,
            hermiticity_error=herm_error,
            residual=residual,
        )
        self._cache[key] = result
        self._diag_count += 1
        return result

    # ------------------------------------------------------------------ Grid scan

    def scan_grid(self, N_theta: int, N_phi: int) -> ScanResult:
        """Diagonalise on an (N_theta × N_phi) grid and compute FHS Chern number.

        States are indexed as ``(theta_idx, phi_idx)`` so that ``compute_fhs``
        (which treats axis-0 as "phi" and axis-1 as "theta") sees swapped axes,
        yielding the spec convention C = +2 at U = 0.
        """
        if N_theta < 2 or N_phi < 2:
            raise ValueError("grid dimensions must be ≥ 2")

        t0 = time.perf_counter()
        before = self._diag_count

        # Build grid: states[theta_idx, phi_idx, :]
        states = np.empty((N_theta, N_phi, self.basis.Ns), dtype=np.complex128)
        e0_map = np.empty((N_theta, N_phi))
        e1_map = np.empty((N_theta, N_phi))
        gaps = np.empty((N_theta, N_phi))
        herm_errors = np.empty((N_theta, N_phi))
        residuals = np.empty((N_theta, N_phi))

        for m in range(N_theta):
            for n in range(N_phi):
                v = self._vertex((Fraction(m, N_theta), Fraction(n, N_phi)))
                states[m, n] = v.state
                e0_map[m, n] = v.energies[0]
                e1_map[m, n] = v.energies[1]
                gaps[m, n] = v.gap
                herm_errors[m, n] = v.hermiticity_error
                residuals[m, n] = v.residual

        # FHS Chern number  (states indexed [theta, phi] → accepted sign)
        fhs = compute_fhs(states)

        # Locate gap minimum
        gap_min_idx = np.unravel_index(np.argmin(gaps), gaps.shape)
        theta_gap_min = 2.0 * np.pi * float(gap_min_idx[0]) / N_theta
        phi_gap_min = 2.0 * np.pi * float(gap_min_idx[1]) / N_phi

        chern_error = abs(fhs.chern_raw - fhs.chern_integer)
        wall_t = time.perf_counter() - t0

        return ScanResult(
            U=self.U,
            L=self.L,
            N_theta=N_theta,
            N_phi=N_phi,
            C_raw=fhs.chern_raw,
            C_rounded=fhs.chern_integer,
            chern_error=chern_error,
            gap_min=float(np.min(gaps)),
            theta_gap_min=float(theta_gap_min),
            phi_gap_min=float(phi_gap_min),
            min_link_overlap=fhs.minimum_overlap,
            max_abs_berry_curvature=fhs.maximum_absolute_flux,
            solver_residual=float(np.max(residuals)),
            converged=chern_error < 1e-3,
            berry_curvature_map=fhs.flux,
            ground_state_energies=e0_map,
            first_excited_energies=e1_map,
            hermiticity_errors=herm_errors,
            diagonalization_count=self._diag_count - before,
            wall_time_s=wall_t,
        )


# ===========================================================================
# U-scan orchestration
# ===========================================================================

RESULTS = _PROJECT_ROOT / "results" / "u-scan-chern"
BERRY_DIR = RESULTS / "berry_curvature"
FIG_DIR = RESULTS / "figures"


def _ensure_dirs() -> None:
    for d in (RESULTS, BERRY_DIR, FIG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _write_csv(results: Sequence[ScanResult], path: Path) -> None:
    """Write a list of ScanResult rows to CSV."""
    if not results:
        return
    fields = [
        "U", "L", "N_theta", "N_phi", "C_raw", "C_rounded", "chern_error",
        "gap_min", "theta_gap_min", "phi_gap_min", "min_link_overlap",
        "max_abs_berry_curvature", "solver_residual", "converged",
        "diagonalization_count", "wall_time_s",
    ]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(r.as_dict())


def _read_csv(path: Path) -> list[dict]:
    """Read CSV back as list of dicts (for U_c detection etc.)."""
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------ Coarse scan


def run_coarse_scan(u_list: Sequence[float] | None = None) -> list[ScanResult]:
    """Coarse scan: L=6, N_theta=N_phi=5 over *u_list* (default U_COARSE)."""
    if u_list is None:
        u_list = U_COARSE
    print("=" * 64)
    print("COARSE SCAN  L=6  N_theta=N_phi=5")
    print("=" * 64)
    results: list[ScanResult] = []
    for U in u_list:
        print(f"  U = {U:+.1f} … ", end="", flush=True)
        solver = RiceMeleHubbardSolver(L=6, U=U)
        r = solver.scan_grid(5, 5)
        tag = "CONVERGED" if r.converged else "NOT CONVERGED"
        print(
            f"C_raw={r.C_raw:+.8f}  C={r.C_rounded:>+2d}  "
            f"gap_min={r.gap_min:.6f}  overlap={r.min_link_overlap:.6f}  "
            f"res={r.solver_residual:.2e}  [{tag}]  {r.wall_time_s:.1f}s"
        )
        results.append(r)
    return results


# ------------------------------------------------------------------ U_c detection


def detect_Uc(results: list[ScanResult]) -> float | None:
    """Find the repulsive (U > 0) transition where C drops 2 → 0.

    Returns the midpoint between the last U with C_rounded == 2 and the first
    U with C_rounded == 0.  Returns None if no clear transition is found.
    """
    positive = sorted([r for r in results if r.U >= 0], key=lambda r: r.U)
    last_two = None
    first_zero = None
    for r in positive:
        if r.C_rounded == 2:
            last_two = r.U
        if r.C_rounded == 0 and first_zero is None:
            first_zero = r.U
    if last_two is not None and first_zero is not None:
        Uc = (last_two + first_zero) / 2.0
        print(f"\nDetected U_c ≈ {Uc:.3f}  (last C=2 at U={last_two}, first C=0 at U={first_zero})")
        return Uc
    print("\nWarning: could not detect clear 2→0 transition in coarse scan")
    return None


# ------------------------------------------------------------------ Refined scan


def _build_refined_u_list(Uc: float, du: float = 0.1) -> list[float]:
    """Build U list: [Uc-1, Uc+1] at step *du*, plus negative checkpoints."""
    u_vals: list[float] = []
    u = Uc - 1.0
    while u <= Uc + 1.0 + 1e-12:
        u_vals.append(round(u, 10))
        u += du
    # negative-U checkpoints
    for neg in [-32, -24, -16, -8]:
        if neg not in u_vals:
            u_vals.append(neg)
    return sorted(u_vals)


def run_refined_scan(
    u_list: list[float],
    L: int = 6,
    N_theta: int = 9,
    N_phi: int = 9,
    label: str = "refined",
) -> list[ScanResult]:
    """Refined scan at given L and grid size."""
    print(f"\n{'=' * 64}")
    print(f"REFINED SCAN  L={L}  N_theta={N_theta}  N_phi={N_phi}")
    print(f"{'=' * 64}")
    results: list[ScanResult] = []
    for U in u_list:
        print(f"  U = {U:+.1f} … ", end="", flush=True)
        solver = RiceMeleHubbardSolver(L=L, U=U)
        r = solver.scan_grid(N_theta, N_phi)
        tag = "CONVERGED" if r.converged else "NOT CONVERGED"
        print(
            f"C_raw={r.C_raw:+.8f}  C={r.C_rounded:>+2d}  "
            f"gap_min={r.gap_min:.6f}  overlap={r.min_link_overlap:.6f}  "
            f"res={r.solver_residual:.2e}  [{tag}]  {r.wall_time_s:.1f}s"
        )
        results.append(r)

        # Save Berry curvature for key U values
        if U in GRID_CONVERGENCE_U or abs(U - 6.0) < 1e-12:
            stem = _build_filename_stem(U, L, N_theta, N_phi)
            np.save(BERRY_DIR / f"berry_{stem}.npy", r.berry_curvature_map)
    return results


# ------------------------------------------------------------------ Grid convergence


def check_grid_convergence() -> list[ScanResult]:
    """Grid-convergence check at representative U values (spec §7)."""
    print(f"\n{'=' * 64}")
    print("GRID CONVERGENCE  L=6  (5×5 vs 9×9 vs 11×11)")
    print(f"{'=' * 64}")
    all_results: list[ScanResult] = []
    for U in GRID_CONVERGENCE_U:
        for N in GRID_CONVERGENCE_SIZES:
            print(f"  U={U:+.1f}  {N}×{N} … ", end="", flush=True)
            solver = RiceMeleHubbardSolver(L=6, U=U)
            r = solver.scan_grid(N, N)
            print(f"C_raw={r.C_raw:+.8f}  gap_min={r.gap_min:.6f}  overlap={r.min_link_overlap:.6f}")
            all_results.append(r)
    return all_results


# ------------------------------------------------------------------ Size comparison


def check_size_dependence(
    u_list: list[float], N_theta: int = 9, N_phi: int = 9
) -> tuple[list[ScanResult], list[ScanResult]]:
    """Compare L=6 vs L=8 (spec §7)."""
    l6 = run_refined_scan(u_list, L=6, N_theta=N_theta, N_phi=N_phi, label="size_L6")
    l8 = run_refined_scan(u_list, L=8, N_theta=N_theta, N_phi=N_phi, label="size_L8")
    return l6, l8


# ------------------------------------------------------------------ Path reversal


def check_path_reversal(u_list: Sequence[float] | None = None) -> list[dict]:
    """Verify C(-φ) = -C(+φ) at representative U (spec §7)."""
    if u_list is None:
        u_list = [-16, 0, 6.0, 10]
    print(f"\n{'=' * 64}")
    print("PATH REVERSAL CHECK  (φ → -φ)")
    print(f"{'=' * 64}")
    rows: list[dict] = []
    for U in u_list:
        # forward path:  delta(phi) = delta0*cos(phi), Delta(phi) = Delta0*sin(phi)
        solver_fwd = RiceMeleHubbardSolver(L=6, U=U)
        r_fwd = solver_fwd.scan_grid(5, 5)

        # reversed path:  delta(-phi) = delta0*cos(-phi) = delta0*cos(phi) = same delta
        #                  Delta(-phi) = Delta0*sin(-phi) = -Delta0*sin(phi) = -Delta
        # So we need a solver with Delta0 → -Delta0
        solver_rev = RiceMeleHubbardSolver(L=6, U=U, Delta0=-CAPITAL_DELTA0)
        r_rev = solver_rev.scan_grid(5, 5)

        ok = abs(r_fwd.C_raw + r_rev.C_raw) < 1e-10
        print(
            f"  U={U:+.1f}  C_fwd={r_fwd.C_raw:+.8f}  C_rev={r_rev.C_raw:+.8f}  "
            f"sum={r_fwd.C_raw + r_rev.C_raw:.2e}  {'PASS' if ok else 'FAIL'}"
        )
        rows.append({
            "U": U, "C_forward": r_fwd.C_raw, "C_reverse": r_rev.C_raw,
            "sum": r_fwd.C_raw + r_rev.C_raw, "pass": ok,
        })
    return rows


# ===========================================================================
# Plotting
# ===========================================================================


def _try_import_mpl():
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        return True
    except ImportError:
        return False


def make_plots(
    coarse: list[ScanResult],
    refined_l6: list[ScanResult],
    refined_l8: list[ScanResult],
) -> None:
    """Generate all figures (spec §9)."""
    if not _try_import_mpl():
        print("matplotlib not available — skipping figures")
        return
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 150,
        "font.size": 10,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
    })

    # --- helper: sort by U ---
    def _sorted(rows):
        return sorted(rows, key=lambda r: r.U)

    coarse_s = _sorted(coarse)
    l6_s = _sorted(refined_l6) if refined_l6 else []
    l8_s = _sorted(refined_l8) if refined_l8 else []

    # ---- 1. C(U) ----
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(2, color="gray", ls="--", lw=0.8, label="C=2")
    ax.axhline(0, color="gray", ls=":", lw=0.8, label="C=0")
    if coarse_s:
        us = [r.U for r in coarse_s]
        ax.plot(us, [r.C_raw for r in coarse_s], "ko-", ms=4, label="coarse L=6 N=5")
    if l6_s:
        us = [r.U for r in l6_s]
        ax.plot(us, [r.C_raw for r in l6_s], "s-", ms=4, label="refined L=6 N=9")
    if l8_s:
        us = [r.U for r in l8_s]
        ax.plot(us, [r.C_raw for r in l8_s], "^-", ms=4, label="refined L=8 N=9")
    ax.set_xlabel("U")
    ax.set_ylabel("C_raw")
    ax.set_title("Many-body Chern number $C(U)$")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "C_vs_U.png")
    plt.close(fig)

    # ---- 2. gap_min(U) ----
    fig, ax = plt.subplots(figsize=(8, 5))
    if coarse_s:
        ax.semilogy([r.U for r in coarse_s], [r.gap_min for r in coarse_s], "ko-", ms=4, label="coarse")
    if l6_s:
        ax.semilogy([r.U for r in l6_s], [r.gap_min for r in l6_s], "s-", ms=4, label="L=6 N=9")
    if l8_s:
        ax.semilogy([r.U for r in l8_s], [r.gap_min for r in l8_s], "^-", ms=4, label="L=8 N=9")
    ax.set_xlabel("U")
    ax.set_ylabel("min $\\Delta_{\\rm mb}$")
    ax.set_title("Minimum many-body gap $\\Delta_{\\rm mb}^{\\min}(U)$")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "gap_vs_U.png")
    plt.close(fig)

    # ---- 3. min_link_overlap(U) ----
    fig, ax = plt.subplots(figsize=(8, 5))
    if coarse_s:
        ax.plot([r.U for r in coarse_s], [r.min_link_overlap for r in coarse_s], "ko-", ms=4, label="coarse")
    if l6_s:
        ax.plot([r.U for r in l6_s], [r.min_link_overlap for r in l6_s], "s-", ms=4, label="L=6 N=9")
    if l8_s:
        ax.plot([r.U for r in l8_s], [r.min_link_overlap for r in l8_s], "^-", ms=4, label="L=8 N=9")
    ax.set_xlabel("U")
    ax.set_ylabel("min link overlap")
    ax.set_title("Minimum neighbour overlap $O_{\\min}(U)$")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "min_overlap_vs_U.png")
    plt.close(fig)

    # ---- 4. chern_error(U) ----
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(1e-3, color="red", ls="--", lw=0.8, label="convergence threshold")
    if coarse_s:
        ax.semilogy([r.U for r in coarse_s], [r.chern_error for r in coarse_s], "ko-", ms=4, label="coarse")
    if l6_s:
        ax.semilogy([r.U for r in l6_s], [r.chern_error for r in l6_s], "s-", ms=4, label="L=6 N=9")
    if l8_s:
        ax.semilogy([r.U for r in l8_s], [r.chern_error for r in l8_s], "^-", ms=4, label="L=8 N=9")
    ax.set_xlabel("U")
    ax.set_ylabel("$|C_{\\rm raw} - C_{\\rm rounded}|$")
    ax.set_title("Chern number deviation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "chern_error_vs_U.png")
    plt.close(fig)

    # ---- 5. L6 vs L8 comparison (C(U) and gap on same figure) ----
    if l6_s and l8_s:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        us6 = [r.U for r in l6_s]
        us8 = [r.U for r in l8_s]
        ax1.plot(us6, [r.C_raw for r in l6_s], "s-", label="L=6")
        ax1.plot(us8, [r.C_raw for r in l8_s], "^-", label="L=8")
        ax1.set_xlabel("U"); ax1.set_ylabel("C_raw"); ax1.set_title("C(U) size comparison")
        ax1.legend()
        ax2.semilogy(us6, [r.gap_min for r in l6_s], "s-", label="L=6")
        ax2.semilogy(us8, [r.gap_min for r in l8_s], "^-", label="L=8")
        ax2.set_xlabel("U"); ax2.set_ylabel("min gap"); ax2.set_title("Gap size comparison")
        ax2.legend()
        fig.tight_layout()
        fig.savefig(FIG_DIR / "L6_vs_L8_comparison.png")
        plt.close(fig)

    # ---- 6. Berry-curvature heatmaps for key U ----
    berry_files = sorted(BERRY_DIR.glob("berry_*.npy"))
    for bf in berry_files:
        flux = np.load(bf)
        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(flux.T, origin="lower", cmap="RdBu_r",
                       extent=[0, 2 * np.pi, 0, 2 * np.pi], aspect="equal")
        ax.set_xlabel("$\\theta$"); ax.set_ylabel("$\\phi$")
        ax.set_title(f"Berry curvature  {bf.stem}")
        plt.colorbar(im, ax=ax, label="$F_{mn}$")
        fig.tight_layout()
        fig.savefig(FIG_DIR / f"{bf.stem}.png")
        plt.close(fig)

    # ---- 7. Critical-region zoom (positive U near transition) ----
    critical = [r for r in (l6_s + l8_s) if 4 <= r.U <= 12]
    if critical:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        for lbl, rows in [("L=6", [r for r in critical if r.L == 6]),
                           ("L=8", [r for r in critical if r.L == 8])]:
            if not rows:
                continue
            rows_s = sorted(rows, key=lambda r: r.U)
            us = [r.U for r in rows_s]
            ax1.plot(us, [r.C_raw for r in rows_s], "o-", ms=4, label=lbl)
            ax2.semilogy(us, [r.gap_min for r in rows_s], "o-", ms=4, label=lbl)
        ax1.set_xlabel("U"); ax1.set_ylabel("C_raw"); ax1.set_title("Critical region: C(U)")
        ax1.legend()
        ax2.set_xlabel("U"); ax2.set_ylabel("min $\\Delta_{\\rm mb}$")
        ax2.set_title("Critical region: gap")
        ax2.legend()
        fig.tight_layout()
        fig.savefig(FIG_DIR / "critical_region_zoom.png")
        plt.close(fig)

    print(f"Figures saved to {FIG_DIR}/")


# ===========================================================================
# Main
# ===========================================================================


def main(smoke: bool = False) -> None:
    """Run the full U-scan pipeline (or a fast smoke test)."""
    _ensure_dirs()
    t_total = time.perf_counter()

    if smoke:
        print("=== SMOKE TEST: 3 U points, L=6, N=5 ===\n")
        u_list = [-16, 0, 8]
        coarse_results = run_coarse_scan(u_list)
        _write_csv(coarse_results, RESULTS / "coarse_scan_L6.csv")
        # quick path-reversal check
        rev_rows = check_path_reversal([0])
        with open(RESULTS / "path_reversal_check.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["U", "C_forward", "C_reverse", "sum", "pass"])
            w.writeheader()
            w.writerows(rev_rows)
    else:
        # ----- Coarse scan -----
        coarse_results = run_coarse_scan()
        _write_csv(coarse_results, RESULTS / "coarse_scan_L6.csv")

        # ----- Detect U_c -----
        Uc = detect_Uc(coarse_results)
        if Uc is None:
            Uc = 6.0  # fallback from atomic-limit estimate
            print(f"Using fallback U_c ≈ {Uc}")

        # ----- Refined scans -----
        refined_u = _build_refined_u_list(Uc, du=0.1)

        refined_l6 = run_refined_scan(refined_u, L=6, N_theta=9, N_phi=9)
        _write_csv(refined_l6, RESULTS / "refined_scan_L6.csv")

        refined_l8 = run_refined_scan(refined_u, L=8, N_theta=9, N_phi=9)
        _write_csv(refined_l8, RESULTS / "refined_scan_L8.csv")

        # ----- Grid convergence -----
        grid_conv = check_grid_convergence()
        _write_csv(grid_conv, RESULTS / "grid_convergence.csv")

        # ----- Size dependence -----
        size_u = [u for u in refined_u if u >= 4]
        size_l6, size_l8 = check_size_dependence(size_u, N_theta=9, N_phi=9)
        _write_csv(size_l6, RESULTS / "size_comparison_L6.csv")
        _write_csv(size_l8, RESULTS / "size_comparison_L8.csv")

        # ----- Path reversal -----
        rev_rows = check_path_reversal()
        with open(RESULTS / "path_reversal_check.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["U", "C_forward", "C_reverse", "sum", "pass"])
            w.writeheader()
            w.writerows(rev_rows)

        # ----- metadata.json -----
        metadata = {
            "parameters": {
                "t": T, "delta0": DELTA0, "Delta0": CAPITAL_DELTA0,
                "Delta_offset": 0.0, "path": "unbiased_centered",
            },
            "U_coarse": U_COARSE,
            "detected_Uc": Uc,
            "refined_u_list": refined_u,
            "grid_convergence_U": GRID_CONVERGENCE_U,
            "grid_convergence_sizes": list(GRID_CONVERGENCE_SIZES),
        }
        (RESULTS / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

        # ----- Plots -----
        make_plots(coarse_results, refined_l6, refined_l8)

    elapsed = time.perf_counter() - t_total
    print(f"\nTotal wall time: {elapsed:.1f}s  ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="U-scan many-body Chern number solver")
    parser.add_argument("--smoke", action="store_true", help="Fast smoke test (3 U points)")
    args = parser.parse_args()
    main(smoke=args.smoke)
