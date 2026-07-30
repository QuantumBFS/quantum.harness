#!/usr/bin/env python3
"""Spin-charge spectrum separation in the Rice-Mele-Hubbard model.

Fixed (U, Delta), scan dimerisation delta, compute many-body spectrum
and doublon number for each eigenstate.  Generates spectrum-landscape
plots coloured by ΔD_n and extracts spin/charge spectral edges.

Usage:
    python spin_charge_spectrum.py                 # full scan (L=6,8)
    python spin_charge_spectrum.py --smoke          # fast smoke test
    python spin_charge_spectrum.py --L 6            # L=6 only
    python spin_charge_spectrum.py --L 8 --method sparse  # L=8 sparse
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian

# ---------------------------------------------------------------------------
# Physical parameters (fixed for this experiment)
# ---------------------------------------------------------------------------
T = 1.0
U_FIXED = 12.0
DELTA_FIXED = 2.0  # staggered potential amplitude
DELTA_RANGE = (-0.5, 0.5)
N_DELTA = 41

# Charge energy scale (atomic limit)
CHARGE_SCALE = U_FIXED - 2 * abs(DELTA_FIXED)  # = 8.0

# Doublon thresholds for charge-like classification
D_THRESHOLDS = (0.2, 0.3, 0.4)

# Sparse solver defaults
K_LOW_DEFAULT = 100
K_CHARGE_DEFAULT = 50

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results" / "spin-charge"
FIG_DIR = RESULTS_DIR / "figures"


# ===========================================================================
# Dataclasses
# ===========================================================================


@dataclass
class SpectrumResult:
    """Eigenspectrum and doublon diagnostics at a single (L, U, Delta, delta)."""
    L: int
    U: float
    Delta: float
    delta: float
    N_up: int
    N_down: int
    dim: int
    eigenvalues: np.ndarray       # shape (n_states,), sorted ascending
    doublons: np.ndarray          # shape (n_states,)
    delta_doublons: np.ndarray    # shape (n_states,), D_n - D_0
    method: str                   # "full_ed" | "sparse_lanczos"
    residual: float
    wall_time_s: float

    @property
    def n_states(self) -> int:
        return len(self.eigenvalues)

    @property
    def e0(self) -> float:
        return float(self.eigenvalues[0])

    @property
    def d0(self) -> float:
        return float(self.doublons[0])

    def excitation_energies(self) -> np.ndarray:
        return self.eigenvalues - self.e0


# ===========================================================================
# Core solver
# ===========================================================================


class RMHSpectrumSolver:
    """Rice-Mele-Hubbard spectrum solver for fixed (L, U, Delta, delta).

    Constructs the Hamiltonian in the fixed-(N_up, N_down) sector with
    periodic boundary conditions (no twist), builds the doublon operator,
    and provides both dense full-diagonalisation and sparse Lanczos +
    shift-invert routes.

    Parameters
    ----------
    L : int
        Number of sites (must be even, half-filling).
    U : float
        Hubbard interaction strength.
    Delta : float
        Staggered-potential amplitude Δ.
    delta : float
        Staggered-hopping (dimerisation) parameter δ.
    t : float
        Bare hopping amplitude (default 1.0).
    """

    def __init__(
        self,
        L: int,
        U: float,
        Delta: float,
        delta: float,
        t: float = T,
    ) -> None:
        if L % 2 != 0:
            raise ValueError(f"L must be even, got {L}")
        self.L = L
        self.U = U
        self.Delta = Delta
        self.delta = delta
        self.t = t
        self.N_up = L // 2
        self.N_down = L // 2

        self.basis = spinful_fermion_basis_1d(
            L, Nf=(self.N_up, self.N_down),
        )
        self._H = self._build_hamiltonian()
        self._H_dense: np.ndarray | None = None
        self._D_op = self._build_doublon_operator()
        self._D_dense: np.ndarray | None = None

    # ------------------------------------------------------------------ Hamiltonian

    def _build_hamiltonian(self):
        """Build the Rice-Mele-Hubbard Hamiltonian with PBC (no twist).

        H = -Σ_{j,σ} [t + (-1)^j δ] (c†_{jσ}c_{j+1,σ} + h.c.)
            + Δ Σ_{j,σ} (-1)^j n_{jσ}
            + U Σ_j n_{j↑} n_{j↓}
        with c_{L,σ} = c_{0,σ}.
        """
        up_hopping: list = []
        down_hopping: list = []

        # bulk bonds j = 0 … L-2
        for j in range(self.L - 1):
            coeff = -(self.t + ((-1) ** j) * self.delta)
            up_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])
            down_hopping.extend([[coeff, j, j + 1], [coeff, j + 1, j]])

        # boundary bond (L-1) ↔ 0, no twist
        boundary_coeff = -(self.t + ((-1) ** (self.L - 1)) * self.delta)
        up_hopping.extend([[boundary_coeff, self.L - 1, 0],
                            [boundary_coeff, 0, self.L - 1]])
        down_hopping.extend([[boundary_coeff, self.L - 1, 0],
                              [boundary_coeff, 0, self.L - 1]])

        # staggered onsite potential
        onsite = [[self.Delta * ((-1) ** j), j] for j in range(self.L)]

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

    # ------------------------------------------------------------------ Doublon operator

    def _build_doublon_operator(self):
        """D = Σ_j n_{j↑} n_{j↓}."""
        return hamiltonian(
            [["n|n", [[1.0, j, j] for j in range(self.L)]]],
            [], basis=self.basis, dtype=np.float64,
            check_herm=False, check_symm=False, check_pcon=False,
        )

    # ------------------------------------------------------------------ Dense matrices (lazy)

    @property
    def H_dense(self) -> np.ndarray:
        if self._H_dense is None:
            self._H_dense = self._H.toarray()
        return self._H_dense

    @property
    def D_dense(self) -> np.ndarray:
        if self._D_dense is None:
            self._D_dense = self._D_op.toarray()
        return self._D_dense

    # ------------------------------------------------------------------ Hermiticity

    def hermiticity_error(self) -> float:
        H = self.H_dense
        return float(np.max(np.abs(H - H.conj().T)))

    def validate_hermiticity(self, tolerance: float = 1e-12) -> None:
        err = self.hermiticity_error()
        if err >= tolerance:
            raise RuntimeError(f"H not Hermitian: error={err:.3e}")

    # ------------------------------------------------------------------ Doublon expectations

    def _compute_doublons(self, eigenvectors: np.ndarray) -> np.ndarray:
        """Compute ⟨ψ_n| D |ψ_n⟩ for all eigenvectors.

        eigenvectors shape: (dim, n_states)
        """
        D_psi = self.D_dense @ eigenvectors
        return np.real(np.sum(eigenvectors.conj() * D_psi, axis=0))

    # ------------------------------------------------------------------ Full ED

    def solve_full_ed(self) -> SpectrumResult:
        """Dense full diagonalisation — all eigenpairs."""
        t0 = time.perf_counter()
        self.validate_hermiticity()

        eigenvalues, eigenvectors = np.linalg.eigh(self.H_dense)
        order = np.argsort(eigenvalues)
        eigenvalues = np.asarray(eigenvalues[order].real)
        eigenvectors = np.asarray(eigenvectors[:, order])

        doublons = self._compute_doublons(eigenvectors)
        delta_doublons = doublons - doublons[0]

        # Residual check: max ||Hψ_n - E_n ψ_n||
        Hpsi = self.H_dense @ eigenvectors
        residuals = np.linalg.norm(Hpsi - eigenvectors * eigenvalues[None, :], axis=0)
        max_residual = float(np.max(residuals))

        elapsed = time.perf_counter() - t0

        return SpectrumResult(
            L=self.L, U=self.U, Delta=self.Delta, delta=self.delta,
            N_up=self.N_up, N_down=self.N_down, dim=self.basis.Ns,
            eigenvalues=eigenvalues, doublons=doublons,
            delta_doublons=delta_doublons,
            method="full_ed", residual=max_residual, wall_time_s=elapsed,
        )

    # ------------------------------------------------------------------ Sparse Lanczos + shift-invert

    def solve_sparse(
        self,
        k_low: int = K_LOW_DEFAULT,
        k_charge: int = K_CHARGE_DEFAULT,
        sigma_charge: float | None = None,
    ) -> SpectrumResult:
        """Sparse Lanczos for low-E states + shift-invert for charge band.

        Parameters
        ----------
        k_low : int
            Number of low-energy eigenpairs to extract.
        k_charge : int
            Number of eigenpairs near the charge band to extract.
        sigma_charge : float or None
            Shift-invert target energy.  Defaults to U - 2|Δ|.
        """
        t0 = time.perf_counter()
        self.validate_hermiticity()
        dim = self.basis.Ns

        if sigma_charge is None:
            sigma_charge = self.U - 2 * abs(self.Delta)

        # --- low-energy Lanczos ---
        n_low = min(k_low, dim - 2)
        Elow, Vlow = self._H.eigsh(k=n_low, which="SA", maxiter=200000, tol=1e-8)
        order_low = np.argsort(Elow)
        Elow = np.asarray(Elow[order_low].real)
        Vlow = np.asarray(Vlow[:, order_low])

        # --- shift-invert for charge band ---
        n_charge = min(k_charge, dim - 2)
        try:
            Echarge, Vcharge = self._H.eigsh(
                k=n_charge, sigma=sigma_charge, which="LM",
                maxiter=200000, tol=1e-8,
            )
            order_ch = np.argsort(Echarge)
            Echarge = np.asarray(Echarge[order_ch].real)
            Vcharge = np.asarray(Vcharge[:, order_ch])
        except Exception:
            # shift-invert may fail; fall back to empty
            Echarge = np.array([], dtype=np.float64)
            Vcharge = np.empty((dim, 0), dtype=np.complex128)

        # --- merge & deduplicate ---
        all_E = np.concatenate([Elow, Echarge])
        all_V = np.concatenate([Vlow, Vcharge], axis=1)

        # sort by energy
        order = np.argsort(all_E)
        all_E = all_E[order]
        all_V = all_V[:, order]

        # remove near-degenerate duplicates
        keep = np.ones(len(all_E), dtype=bool)
        for i in range(1, len(all_E)):
            if abs(all_E[i] - all_E[i - 1]) < 1e-10:
                keep[i] = False
        eigenvalues = all_E[keep]
        eigenvectors = all_V[:, keep]

        doublons = self._compute_doublons(eigenvectors)
        delta_doublons = doublons - doublons[0]

        # Residual check
        Hpsi = self.H_dense @ eigenvectors
        residuals = np.linalg.norm(Hpsi - eigenvectors * eigenvalues[None, :], axis=0)
        max_residual = float(np.max(residuals))

        elapsed = time.perf_counter() - t0

        return SpectrumResult(
            L=self.L, U=self.U, Delta=self.Delta, delta=self.delta,
            N_up=self.N_up, N_down=self.N_down, dim=dim,
            eigenvalues=eigenvalues, doublons=doublons,
            delta_doublons=delta_doublons,
            method=f"sparse_lanczos(k_low={n_low},k_charge={n_charge})",
            residual=max_residual, wall_time_s=elapsed,
        )


# ===========================================================================
# Delta scan
# ===========================================================================


def build_delta_values(n: int = N_DELTA, dmin: float = -0.5, dmax: float = 0.5) -> np.ndarray:
    return np.linspace(dmin, dmax, n)


def scan_delta(
    L: int,
    U: float,
    Delta: float,
    delta_values: np.ndarray,
    method: str = "auto",
) -> list[SpectrumResult]:
    """Scan dimerisation δ and compute spectrum at each point.

    Parameters
    ----------
    method : str
        "full_ed" - dense diagonalisation.
        "sparse"  - Lanczos + shift-invert.
        "auto"    - full_ed for L ≤ 8 (D ≤ 4900), sparse for L ≥ 10.
    """
    if method == "auto":
        method = "full_ed" if L <= 8 else "sparse"

    results: list[SpectrumResult] = []
    n_total = len(delta_values)

    for idx, delta in enumerate(delta_values):
        print(f"  δ = {delta:+.6f}  [{idx+1}/{n_total}] … ", end="", flush=True)
        solver = RMHSpectrumSolver(L=L, U=U, Delta=Delta, delta=delta)

        if method == "full_ed":
            r = solver.solve_full_ed()
        else:
            r = solver.solve_sparse()

        n_st = r.n_states
        print(
            f"dim={r.dim}  n_states={n_st}  "
            f"E₀={r.e0:.6f}  D₀={r.d0:.4f}  "
            f"res={r.residual:.2e}  {r.wall_time_s:.1f}s"
        )
        results.append(r)

    return results


# ===========================================================================
# Spin / charge edge extraction
# ===========================================================================


def extract_edges(
    results: Sequence[SpectrumResult],
    d_thresholds: tuple[float, ...] = D_THRESHOLDS,
) -> dict[float, dict[str, np.ndarray]]:
    """Extract Δ_s(δ) and E_ch^min(δ) for each doublon threshold.

    Returns
    -------
    dict mapping d_th → {
        "delta": ndarray,
        "Delta_s": ndarray,       # min spin-like excitation energy
        "E_ch_min": ndarray,       # min charge-like excitation energy
    }
    """
    delta_arr = np.array([r.delta for r in results])
    out: dict[float, dict[str, np.ndarray]] = {}

    for d_th in d_thresholds:
        Delta_s = np.empty(len(results))
        E_ch_min = np.empty(len(results))

        for i, r in enumerate(results):
            de = r.excitation_energies()
            dd = r.delta_doublons

            # spin-like: ΔD_n < d_th, n > 0
            spin_mask = (dd < d_th) & (np.arange(len(dd)) > 0)
            if np.any(spin_mask):
                Delta_s[i] = float(np.min(de[spin_mask]))
            else:
                Delta_s[i] = np.nan

            # charge-like: ΔD_n > d_th
            charge_mask = dd > d_th
            if np.any(charge_mask):
                E_ch_min[i] = float(np.min(de[charge_mask]))
            else:
                E_ch_min[i] = np.nan

        out[d_th] = {
            "delta": delta_arr,
            "Delta_s": Delta_s,
            "E_ch_min": E_ch_min,
        }

    return out


# ===========================================================================
# Data output
# ===========================================================================


def save_csv(results: Sequence[SpectrumResult], path: Path) -> None:
    """Save all eigenstate data as CSV (one row per eigenstate)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "L", "U", "Delta", "delta", "n", "E_n", "E_n_minus_E0",
            "D_n", "Delta_D_n", "method",
        ])
        for r in results:
            de = r.excitation_energies()
            for n in range(r.n_states):
                writer.writerow([
                    r.L, r.U, r.Delta, r.delta, n,
                    r.eigenvalues[n], de[n],
                    r.doublons[n], r.delta_doublons[n],
                    r.method,
                ])


def save_npz(results: Sequence[SpectrumResult], path: Path) -> None:
    """Save all results as compressed NPZ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, np.ndarray] = {}
    for i, r in enumerate(results):
        prefix = f"delta_{i:03d}"
        data[f"{prefix}_eigenvalues"] = r.eigenvalues
        data[f"{prefix}_doublons"] = r.doublons
        data[f"{prefix}_delta_doublons"] = r.delta_doublons
    # metadata
    data["delta_values"] = np.array([r.delta for r in results])
    data["L"] = np.array([results[0].L])
    data["U"] = np.array([results[0].U])
    data["Delta"] = np.array([results[0].Delta])
    np.savez_compressed(path, **data)


# ===========================================================================
# Plotting
# ===========================================================================


def _try_import_mpl() -> bool:
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        return True
    except ImportError:
        return False


def make_plots(
    results_l6: list[SpectrumResult],
    results_l8: list[SpectrumResult],
    edge_data_l6: dict[float, dict[str, np.ndarray]],
    edge_data_l8: dict[float, dict[str, np.ndarray]],
    out_dir: Path,
) -> None:
    """Generate all figures."""
    if not _try_import_mpl():
        print("matplotlib not available — skipping figures")
        return
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 9,
        "axes.labelsize": 11, "axes.titlesize": 12,
    })

    # --- helper: consistent colour normalisation ---
    vmin, vmax = -0.1, 1.2

    def _plot_landscape(results: list[SpectrumResult], L: int, ymax: float | None = None):
        """Single spectrum landscape panel."""
        fig, ax = plt.subplots(figsize=(10, 7))
        for r in results:
            de = r.excitation_energies()
            dd = r.delta_doublons
            scatter = ax.scatter(
                np.full(len(de), r.delta), de,
                c=dd, cmap="viridis", norm=Normalize(vmin=vmin, vmax=vmax),
                s=2.0, linewidths=0, alpha=0.7, rasterized=True,
            )
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$E_n - E_0$")
        ax.set_title(f"Spectrum landscape  $L={L}$  $U={U_FIXED}$  $\\Delta={DELTA_FIXED}$")
        if ymax is not None:
            ax.set_ylim(-0.05, ymax)
        cbar = fig.colorbar(scatter, ax=ax, label=r"$\Delta D_n$")
        return fig, ax

    # ---- Full-range landscapes ----
    for L, results in [(6, results_l6), (8, results_l8)]:
        if not results:
            continue
        fig, ax = _plot_landscape(results, L, ymax=12.0)
        ax.axhline(CHARGE_SCALE, color="red", ls="--", lw=1.0,
                   label=f"$U-2|\\Delta|={CHARGE_SCALE}$")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"spectrum_landscape_L{L}.png")
        plt.close(fig)
        print(f"Saved: spectrum_landscape_L{L}.png")

    # ---- Low-energy zooms ----
    for L, results in [(6, results_l6), (8, results_l8)]:
        if not results:
            continue
        fig, ax = _plot_landscape(results, L, ymax=4.0)
        ax.axhline(0, color="gray", ls=":", lw=0.5)
        fig.tight_layout()
        fig.savefig(out_dir / f"spectrum_low_energy_L{L}.png")
        plt.close(fig)
        print(f"Saved: spectrum_low_energy_L{L}.png")

    # ---- Spin / charge edges ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    colors = {0.2: "blue", 0.3: "green", 0.4: "red"}
    for L, edge_data, ax in [(6, edge_data_l6, axes[0]), (8, edge_data_l8, axes[1])]:
        for d_th, ed in edge_data.items():
            c = colors.get(d_th, "black")
            ax.plot(ed["delta"], ed["Delta_s"], "o-", ms=3, color=c,
                    label=rf"$\Delta_s$ ($d_{{\rm th}}={d_th}$)")
            ax.plot(ed["delta"], ed["E_ch_min"], "s--", ms=3, color=c,
                    label=rf"$E_{{\rm ch}}^{{\min}}$ ($d_{{\rm th}}={d_th}$)")
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel("Excitation energy")
        ax.set_title(f"Spin/charge edges  $L={L}$")
        ax.legend(fontsize=7)
        ax.set_ylim(-0.05, 12)
        ax.axhline(CHARGE_SCALE, color="gray", ls=":", lw=0.8)
    fig.tight_layout()
    fig.savefig(out_dir / "spin_charge_edges.png")
    plt.close(fig)
    print("Saved: spin_charge_edges.png")

    # ---- ΔD_n histogram at δ=0 (closest point) ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for L, results, ax in [(6, results_l6, axes[0]), (8, results_l8, axes[1])]:
        if not results:
            continue
        # find δ ≈ 0
        idx0 = np.argmin([abs(r.delta) for r in results])
        r0 = results[idx0]
        ax.hist(r0.delta_doublons, bins=40, color="steelblue", edgecolor="white", alpha=0.8)
        ax.axvline(0, color="gray", ls="--", lw=0.8)
        ax.axvline(1, color="red", ls=":", lw=0.8, label=r"$\Delta D_n=1$")
        ax.set_xlabel(r"$\Delta D_n$")
        ax.set_ylabel("Count")
        ax.set_title(f"Doublon histogram  $L={L}$  $\\delta={r0.delta:.4f}$")
        ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "doublon_histogram.png")
    plt.close(fig)
    print("Saved: doublon_histogram.png")


# ===========================================================================
# Validation
# ===========================================================================


def validate_l6_full_vs_sparse(
    delta_values: np.ndarray,
    n_check: int = 5,
) -> None:
    """Cross-check sparse vs full ED at a few δ points for L=6."""
    print("\n" + "=" * 64)
    print("VALIDATION: L=6 sparse vs full ED")
    print("=" * 64)
    indices = np.linspace(0, len(delta_values) - 1, n_check, dtype=int)
    for idx in indices:
        delta = float(delta_values[idx])
        solver = RMHSpectrumSolver(L=6, U=U_FIXED, Delta=DELTA_FIXED, delta=delta)
        r_full = solver.solve_full_ed()
        r_sparse = solver.solve_sparse(k_low=50, k_charge=30)

        # compare overlapping eigenvalues
        n_compare = min(r_sparse.n_states, r_full.n_states)
        e_diff = np.max(np.abs(r_sparse.eigenvalues[:n_compare] -
                                r_full.eigenvalues[:n_compare]))
        d_diff = np.max(np.abs(r_sparse.doublons[:n_compare] -
                                r_full.doublons[:n_compare]))
        status = "PASS" if e_diff < 1e-8 and d_diff < 1e-8 else "FAIL"
        print(f"  δ={delta:+.4f}  max|ΔE|={e_diff:.2e}  max|ΔD|={d_diff:.2e}  [{status}]")


# ===========================================================================
# Main
# ===========================================================================


def main(smoke: bool = False, L_val: int | None = None,
         method: str = "auto") -> None:
    """Run the spin-charge spectrum scan."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t_total = time.perf_counter()

    L_list = [L_val] if L_val is not None else [6, 8]
    delta_values = build_delta_values(n=5 if smoke else N_DELTA)

    print("=" * 64)
    print("SPIN-CHARGE SPECTRUM SEPARATION")
    print(f"U={U_FIXED}  Δ={DELTA_FIXED}  δ ∈ [{delta_values[0]:.4f}, {delta_values[-1]:.4f}]")
    print(f"L ∈ {L_list}  n_δ={len(delta_values)}  method={method}")
    print(f"Charge scale U-2|Δ| = {CHARGE_SCALE}")
    if smoke:
        print("*** SMOKE TEST MODE ***")
    print("=" * 64)

    all_results: dict[int, list[SpectrumResult]] = {}
    all_edges: dict[int, dict[float, dict[str, np.ndarray]]] = {}

    for L in L_list:
        print(f"\n--- L = {L} ---")
        results = scan_delta(L, U_FIXED, DELTA_FIXED, delta_values, method=method)
        all_results[L] = results

        # Save data
        save_csv(results, RESULTS_DIR / f"spectrum_data_L{L}.csv")
        save_npz(results, RESULTS_DIR / f"spectrum_data_L{L}.npz")
        print(f"Data saved: spectrum_data_L{L}.csv, spectrum_data_L{L}.npz")

        # Extract edges
        edges = extract_edges(results)
        all_edges[L] = edges

        # Print edge summary
        print(f"\n  Spin/charge edges at δ=0 (closest point):")
        idx0 = np.argmin([abs(r.delta) for r in results])
        for d_th in D_THRESHOLDS:
            ds = edges[d_th]["Delta_s"][idx0]
            ech = edges[d_th]["E_ch_min"][idx0]
            print(f"    d_th={d_th}: Δ_s={ds:.4f}  E_ch^min={ech:.4f}")

    # ---- Validation (L=6 sparse vs full) ----
    if 6 in L_list and not smoke:
        validate_l6_full_vs_sparse(delta_values, n_check=5)

    # ---- Plots ----
    results_l6 = all_results.get(6, [])
    results_l8 = all_results.get(8, [])
    edges_l6 = all_edges.get(6, {})
    edges_l8 = all_edges.get(8, {})
    make_plots(results_l6, results_l8, edges_l6, edges_l8, FIG_DIR)

    elapsed = time.perf_counter() - t_total
    print(f"\nTotal wall time: {elapsed:.1f}s  ({elapsed/60:.1f} min)")
    print(f"Results: {RESULTS_DIR}/")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Spin-charge spectrum separation in Rice-Mele-Hubbard model"
    )
    parser.add_argument("--smoke", action="store_true",
                        help="Fast smoke test (5 δ points)")
    parser.add_argument("--L", type=int, default=None,
                        help="System size (default: both 6 and 8)")
    parser.add_argument("--method", type=str, default="auto",
                        choices=["auto", "full_ed", "sparse"],
                        help="Diagonalisation method (default: auto)")
    args = parser.parse_args()
    main(smoke=args.smoke, L_val=args.L, method=args.method)
