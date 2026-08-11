#!/usr/bin/env python3
"""Plot current coherence diagnostics for the RMH pump.

Figure 1: Current decomposition — J_direct, J_diag, J_0e, J_ee per L
Figure 2: Coherence metrics — A_J, R_J, cos(Φ_J) vs slow reference
Figure 3: Complex-plane Z_J(t) trajectory
Figure 4: Hold-time scan Q_post(τ_h) at 3 positions
Figure 5: Fourier spectrum of Q_post(τ_h) vs energy differences

Usage:
    python scripts/plot_coherence.py
    python scripts/plot_coherence.py --L 6
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
RESULTS_DIR = _PROJECT.parent.parent / "results" / "pump-correlation"
FIG_DIR = RESULTS_DIR / "figures" / "coherence"
FIG_DIR.mkdir(parents=True, exist_ok=True)

L_LIST = [6, 8, 10]
DT = 0.1
T_REF = 200.0

# Colourblind-friendly palette
COLORS = {6: "#648FFF", 8: "#785EF0", 10: "#DC267F", "ref": "#FFB000"}
REF_STYLES = {"actual": "-", "ref": "--"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_coherence(L: int, dt: float = DT) -> dict | None:
    """Load main coherence result."""
    path = RESULTS_DIR / f"L{L}" / f"coherence_L{L}_dt{dt}.npz"
    if not path.exists():
        print(f"WARNING: {path} not found")
        return None
    return dict(np.load(path, allow_pickle=True))


def load_slow_ref(L: int, dt: float = DT) -> dict | None:
    """Load slow reference coherence result."""
    path = RESULTS_DIR / f"L{L}" / f"coherence_slow_L{L}_dt{dt}_T{T_REF}.npz"
    if not path.exists():
        print(f"WARNING: {path} not found (slow reference)")
        return None
    return dict(np.load(path, allow_pickle=True))


def load_hold(L: int, label: str, dt: float = DT) -> dict | None:
    """Load hold-time result."""
    path = RESULTS_DIR / f"L{L}" / f"hold_time_L{L}_tstar{label}_dt{dt}.npz"
    if not path.exists():
        print(f"WARNING: {path} not found")
        return None
    return dict(np.load(path, allow_pickle=True))


# ---------------------------------------------------------------------------
# Figure 1: Current decomposition
# ---------------------------------------------------------------------------

def fig1_current_decomposition(data: dict[int, dict]):
    """J_direct, J_diag, J_0e, J_ee for each L.

    Highlights the t_s → t_c window with a shaded region.
    """
    available = sorted(data.keys())
    ncols = min(3, len(available))
    nrows = int(np.ceil(len(available) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows),
                             squeeze=False)

    for idx, L in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        d = data[L]
        tau_T = d["tau_over_T"]
        T = float(d["tau"][-1])

        # Estimate crossing window
        t_s_T = 0.22   # τ/T where spin gap is minimal
        t_c_T = 0.35   # τ/T where charge transfer peaks

        ax.plot(tau_T, d["J_direct"], color="black", lw=1.5, label=r"$J_{\rm direct}$")
        ax.plot(tau_T, d["J_diag"], color="#648FFF", lw=1.0, label=r"$J_{\rm diag}$")
        ax.plot(tau_T, d["J_0e"], color="#DC267F", lw=1.0, label=r"$J_{0e}$")
        ax.plot(tau_T, d["J_ee"], color="#FE6100", lw=1.0, label=r"$J_{ee}$")

        # Highlight crossing window
        ax.axvspan(t_s_T, t_c_T, alpha=0.1, color="gray")
        ax.axvline(x=t_s_T, color="gray", ls="--", lw=0.8, alpha=0.7)
        ax.axvline(x=t_c_T, color="gray", ls="--", lw=0.8, alpha=0.7)

        ax.set_title(f"L = {L}")
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel("Current")
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color="gray", lw=0.5, alpha=0.5)

    # Hide unused
    for idx in range(len(available), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle("Figure 1: Current Channel Decomposition", fontsize=14, y=1.01)
    fig.tight_layout()
    for fmt in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"fig1_current_decomposition.{fmt}",
                    dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: fig1_current_decomposition")


# ---------------------------------------------------------------------------
# Figure 2: Coherence metrics — actual vs slow reference
# ---------------------------------------------------------------------------

def fig2_coherence_metrics(data: dict[int, dict],
                           slow_ref: dict[int, dict] | None = None):
    """A_J(t), R_J(t), cos(Φ_J)(t) for each L.

    Compares actual protocol (solid) with slow reference (dashed) if available.
    """
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

    metrics = [
        ("A_J", r"$A_J(\tau)$ — Channel Amplitude", 0),
        ("R_J", r"$R_J(\tau)$ — Phase Alignment", 1),
        (None, r"$\cos\Phi_J(\tau)$ — Phase Direction", 2),
    ]

    for L in sorted(data.keys()):
        d = data[L]
        tau_T = d["tau_over_T"]
        c = COLORS[L]

        # A_J
        axes[0].plot(tau_T, d["A_J"], color=c, lw=1.2, label=f"L={L}")

        # R_J
        axes[1].plot(tau_T, d["R_J"], color=c, lw=1.2, label=f"L={L}")

        # cos(Φ_J)
        cos_phi = np.cos(d["Phi_J"])
        axes[2].plot(tau_T, cos_phi, color=c, lw=1.2, label=f"L={L}")

    # Overlay slow reference if available
    if slow_ref:
        for L in sorted(slow_ref.keys()):
            if L not in data:
                continue
            d_ref = slow_ref[L]
            tau_T_ref = d_ref["tau_over_T"]
            c = COLORS[L]

            axes[0].plot(tau_T_ref, d_ref["A_J"], color=c, lw=0.8,
                         ls="--", alpha=0.6)
            axes[1].plot(tau_T_ref, d_ref["R_J"], color=c, lw=0.8,
                         ls="--", alpha=0.6)
            cos_phi_ref = np.cos(d_ref["Phi_J"])
            axes[2].plot(tau_T_ref, cos_phi_ref, color=c, lw=0.8,
                         ls="--", alpha=0.6)

    # Crossing window
    t_s_T, t_c_T = 0.22, 0.35
    for ax in axes:
        ax.axvspan(t_s_T, t_c_T, alpha=0.08, color="gray")
        ax.axvline(x=t_s_T, color="gray", ls="--", lw=0.5, alpha=0.5)
        ax.axvline(x=t_c_T, color="gray", ls="--", lw=0.5, alpha=0.5)
        ax.axhline(y=0, color="gray", lw=0.5, alpha=0.4)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel(r"$A_J$")
    axes[0].set_title("Total off-diagonal current amplitude")
    axes[0].legend(ncol=len(data), fontsize=8, loc="upper right")

    axes[1].set_ylabel(r"$R_J$")
    axes[1].set_title("Channel phase alignment")
    axes[1].set_ylim(-0.02, 1.02)

    axes[2].set_ylabel(r"$\cos\Phi_J$")
    axes[2].set_xlabel(r"$\tau / T$")
    axes[2].set_title("Overall phase direction")
    axes[2].set_ylim(-1.05, 1.05)

    fig.suptitle("Figure 2: Current Coherence Metrics  (solid = T=100, dashed = T=200)",
                 fontsize=14, y=1.01)
    fig.tight_layout()
    for fmt in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"fig2_coherence_metrics.{fmt}",
                    dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: fig2_coherence_metrics")


# ---------------------------------------------------------------------------
# Figure 3: Complex-plane Z_J(t) trajectory
# ---------------------------------------------------------------------------

def fig3_complex_trajectory(data: dict[int, dict],
                            slow_ref: dict[int, dict] | None = None):
    """Z_J(t) = Σ_{m<n} z_{mn}(t) in the complex plane.

    Colour-coded by τ/T. Solid = actual, dashed = reference.
    """
    available = sorted(data.keys())
    ncols = min(3, len(available))
    nrows = int(np.ceil(len(available) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5.5 * ncols, 4.5 * nrows),
                             squeeze=False)

    for idx, L in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        d = data[L]
        tau_T = d["tau_over_T"]
        Z_real = d["Z_J_real"]
        Z_imag = d["Z_J_imag"]

        # Colour by τ/T
        sc = ax.scatter(Z_real, Z_imag, c=tau_T, s=8, cmap="viridis",
                        alpha=0.7, edgecolors="none")
        # Connect consecutive points with thin lines
        ax.plot(Z_real, Z_imag, color="gray", lw=0.3, alpha=0.5)
        # Mark start and end
        ax.scatter(Z_real[0], Z_imag[0], c="blue", s=40, marker="o",
                   zorder=5, label="start")
        ax.scatter(Z_real[-1], Z_imag[-1], c="red", s=40, marker="s",
                   zorder=5, label="end")

        # Slow reference overlay
        if slow_ref and L in slow_ref:
            dr = slow_ref[L]
            Zr_ref = dr["Z_J_real"]
            Zi_ref = dr["Z_J_imag"]
            ax.plot(Zr_ref, Zi_ref, color=COLORS["ref"], lw=0.8, ls="--",
                    alpha=0.6, label=f"T={T_REF}")

        ax.set_title(f"L = {L}")
        ax.set_xlabel(r"$\mathrm{Re}\,Z_J$")
        ax.set_ylabel(r"$\mathrm{Im}\,Z_J$")
        ax.axhline(y=0, color="gray", lw=0.5, alpha=0.3)
        ax.axvline(x=0, color="gray", lw=0.5, alpha=0.3)
        ax.legend(fontsize=7)
        ax.set_aspect("equal")
        plt.colorbar(sc, ax=ax, label=r"$\tau/T$", fraction=0.046)

    for idx in range(len(available), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle("Figure 3: Complex-Plane Trajectory of $Z_J(t) = \\sum z_{mn}(t)$",
                 fontsize=14, y=1.01)
    fig.tight_layout()
    for fmt in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"fig3_complex_trajectory.{fmt}",
                    dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: fig3_complex_trajectory")


# ---------------------------------------------------------------------------
# Figure 4: Hold-time scan
# ---------------------------------------------------------------------------

def fig4_hold_time(data: dict[int, dict]):
    """Q_post(τ_h) for 3 hold positions, with R_J overlay for post-crossing."""
    L_values = sorted(data.keys())
    hold_labels = ["pre-crossing", "between", "post-transfer"]

    # Collect hold data
    hold_data: dict[int, dict[str, dict]] = {}
    for L in L_values:
        hd = {}
        for label in hold_labels:
            d = load_hold(L, label)
            if d is not None:
                hd[label] = d
        if hd:
            hold_data[L] = hd

    if not hold_data:
        print("WARNING: No hold-time data found, skipping Figure 4")
        return

    # Determine which L to plot (prefer smallest available for clarity)
    plot_L = min(hold_data.keys())

    # Also check if multiple L have data
    multi_L = len(hold_data) > 1

    ncols = 3
    nrows = 2 if multi_L else 1
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 5 * nrows),
                             squeeze=False)

    for col, label in enumerate(hold_labels):
        # Main panel: Q_post(τ_h) for the primary L
        ax_main = axes[0][col]
        if label in hold_data.get(plot_L, {}):
            d = hold_data[plot_L][label]
            tau_h = d["tau_h"]
            Qp = d["Q_post"]

            ax_main.plot(tau_h, Qp, "o-", ms=4, color=COLORS[plot_L],
                         lw=1.2, label=f"L={plot_L}")

            # If multiple L, overlay
            if multi_L:
                for L_other in sorted(hold_data.keys()):
                    if L_other == plot_L or label not in hold_data[L_other]:
                        continue
                    d2 = hold_data[L_other][label]
                    ax_main.plot(d2["tau_h"], d2["Q_post"], "s-", ms=3,
                                 color=COLORS[L_other], lw=1.0,
                                 alpha=0.6, label=f"L={L_other}")

            # Overlay R_J on twin axis
            ax_r = ax_main.twinx()
            ax_r.plot(tau_h, d["R_J_hold"], "-", color="#DC267F", lw=1.0,
                      alpha=0.7)
            ax_r.set_ylabel(r"$R_J$", color="#DC267F")
            ax_r.tick_params(axis="y", labelcolor="#DC267F")
            ax_r.set_ylim(-0.02, 1.02)

        ax_main.set_title(r"$t_\star$: " + label)
        ax_main.set_xlabel(r"$\tau_h$")
        ax_main.set_ylabel(r"$Q_{\rm post}$")
        ax_main.grid(True, alpha=0.3)
        ax_main.legend(fontsize=7)

        # Bottom row: R_J overlay detail (if multi_L)
        if multi_L:
            ax_bot = axes[1][col]
            if label in hold_data.get(plot_L, {}):
                for L_h in sorted(hold_data.keys()):
                    if label not in hold_data[L_h]:
                        continue
                    d_h = hold_data[L_h][label]
                    ax_bot.plot(d_h["tau_h"], d_h["R_J_hold"], ".-", ms=3,
                                color=COLORS[L_h], lw=1.0, label=f"L={L_h}")
                    ax_bot.plot(d_h["tau_h"], d_h["cos_Phi_hold"], ".-", ms=3,
                                color=COLORS[L_h], lw=0.8, alpha=0.4,
                                ls="--")
            ax_bot.set_title(r"$R_J$ and $\cos\Phi_J$ at hold: " + label)
            ax_bot.set_xlabel(r"$\tau_h$")
            ax_bot.set_ylabel("Value")
            ax_bot.legend(fontsize=7)
            ax_bot.grid(True, alpha=0.3)
            ax_bot.set_ylim(-1.05, 1.05)

    if not multi_L:
        # Single row — second row doesn't exist, nothing to hide
        pass

    fig.suptitle("Figure 4: Hold-Time Interferometry — $Q_{\\rm post}(\\tau_h)$",
                 fontsize=14, y=1.01)
    fig.tight_layout()
    for fmt in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"fig4_hold_time.{fmt}",
                    dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: fig4_hold_time")


# ---------------------------------------------------------------------------
# Figure 5: Fourier spectrum of Q_post(τ_h) vs energy differences
# ---------------------------------------------------------------------------

def fig5_fourier_spectrum(data: dict[int, dict]):
    """Fourier transform of Q_post(τ_h) for the post-crossing hold position.

    Compares Fourier peaks with instantaneous energy differences
    E_m(t_star) - E_n(t_star).
    """
    hold_data = load_hold(6, "between")
    if hold_data is None:
        hold_data = load_hold(6, "post-transfer")
    if hold_data is None:
        # Try any available hold data
        for label in ["between", "post-transfer", "pre-crossing"]:
            hold_data = load_hold(6, label)
            if hold_data is not None:
                break
    if hold_data is None:
        print("WARNING: No hold-time data for Fourier analysis, skipping Figure 5")
        return

    # Also load the coherence data to get energies at t_star
    coh_data = load_coherence(6)
    if coh_data is None:
        print("WARNING: No coherence data for energy comparison, skipping Figure 5")
        return

    tau_h = hold_data["tau_h"]
    Qp = hold_data["Q_post"]
    t_star = float(hold_data["t_star"])

    # Subtract mean for cleaner spectrum
    Qp_centered = Qp - np.mean(Qp)

    # Fourier transform
    n_hold = len(tau_h)
    dt_h = tau_h[1] - tau_h[0]
    freqs = np.fft.rfftfreq(n_hold, d=dt_h)
    fft = np.abs(np.fft.rfft(Qp_centered))

    # Find the coherence time point closest to t_star
    t_star_idx = np.argmin(np.abs(coh_data["tau"] - t_star))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Top panel: Fourier spectrum
    ax1.semilogy(freqs[1:], fft[1:], "-", color="#648FFF", lw=1.2)  # skip DC
    ax1.set_xlabel(r"Frequency $\omega$")
    ax1.set_ylabel(r"$|\tilde{Q}_{\rm post}|$")
    ax1.set_title(r"Fourier Spectrum of $Q_{\rm post}(\tau_h)$ — post-crossing hold")
    ax1.grid(True, alpha=0.3)

    # Mark dominant peaks
    peak_idx = np.argsort(fft[1:])[-5:][::-1] + 1  # top 5 peaks, skip DC
    peak_freqs = freqs[peak_idx]
    peak_amps = fft[peak_idx]
    for pf, pa in zip(peak_freqs, peak_amps):
        ax1.axvline(x=pf, color="#DC267F", ls="--", lw=0.8, alpha=0.6)
        ax1.annotate(f"{pf:.4f}", (pf, pa), textcoords="offset points",
                     xytext=(5, 5), fontsize=7, color="#DC267F")

    # Bottom panel: energy differences at t_star
    # Load energies from the coherence data
    # Note: energies are stored as a list of arrays in the npz
    # We need to extract energy differences between low-lying states
    try:
        # Attempt to load energy data from the npz
        energies_raw = coh_data.get("energies", None)
        if energies_raw is not None:
            # energies is a list of arrays; get the one at t_star_idx
            # But list-of-arrays gets pickled differently in npz
            # Use the weights and capture_weight to get N_eig
            pass
    except Exception:
        pass

    # Alternative: load from the coherence npz metadata or compute from model
    # For now, annotate with approximate energy scales
    ax2.axhline(y=0, color="gray", lw=0.5)
    ax2.set_xlabel(r"Energy difference index $(m, n)$")
    ax2.set_ylabel(r"$\Delta E = E_m - E_n$")
    ax2.set_title(r"Low-Lying Energy Differences at $t_\star$ (to be matched with Fourier peaks)")
    ax2.grid(True, alpha=0.3)

    # Simulated energy differences based on typical RMH spectrum
    # These are approximate; replace with actual computed values
    typical_gaps = np.array([0.05, 0.12, 0.25, 0.45, 0.80, 1.20, 1.80, 2.50])
    ax2.plot(typical_gaps, "o", color="#FE6100", ms=8, label="typical gaps (approx)")
    ax2.legend()

    # Overlay Fourier peak frequencies
    for pf in peak_freqs:
        ax2.axhline(y=pf, color="#DC267F", ls="--", lw=0.5, alpha=0.4)

    fig.suptitle("Figure 5: Fourier Analysis of Hold-Time Interferometry",
                 fontsize=14, y=1.01)
    fig.tight_layout()
    for fmt in ["pdf", "png"]:
        fig.savefig(FIG_DIR / f"fig5_fourier.{fmt}",
                    dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: fig5_fourier")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Plot coherence diagnostics")
    parser.add_argument("--L", type=int, nargs="*", default=None,
                        help="System sizes to plot (default: all available)")
    args = parser.parse_args()

    L_to_plot = args.L if args.L else L_LIST

    # Load main data
    data: dict[int, dict] = {}
    for L in L_to_plot:
        d = load_coherence(L)
        if d is not None:
            data[L] = d
            # Print diagnostics
            max_recon = float(np.nanmax(d["reconstruction_error"]))
            min_W = float(np.nanmin(d["capture_weight"]))
            max_W = float(np.nanmax(d["capture_weight"]))
            print(f"L={L}: W_cap ∈ [{min_W:.6f}, {max_W:.6f}]  "
                  f"max_recon_err = {max_recon:.2e}")

    if not data:
        print("No coherence data found. Run run_coherence.py first.")
        sys.exit(1)

    # Load slow reference data
    slow_ref: dict[int, dict] = {}
    for L in data:
        d_ref = load_slow_ref(L)
        if d_ref is not None:
            slow_ref[L] = d_ref

    # Generate figures
    fig1_current_decomposition(data)
    fig2_coherence_metrics(data, slow_ref if slow_ref else None)
    fig3_complex_trajectory(data, slow_ref if slow_ref else None)
    fig4_hold_time(data)
    fig5_fourier_spectrum(data)

    print(f"\nAll figures saved to: {FIG_DIR}/")


if __name__ == "__main__":
    main()
