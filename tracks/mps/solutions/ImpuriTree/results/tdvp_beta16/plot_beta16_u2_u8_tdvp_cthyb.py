from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np


root = Path(__file__).parent
fig, axes = plt.subplots(2, 2, figsize=(12, 9))

with h5py.File(root / "comparison_data.h5") as archive:
    beta = archive.attrs["beta"]
    for row, interaction in enumerate((2, 8)):
        group = archive[f"u{interaction}"]
        fine = group["fine_tau"][:]
        aligned = group["aligned_tau"][:]
        tau = aligned["tau"]
        mps = aligned["mps_G_tau"]
        raw = np.interp(tau, fine["tau"], fine["ctqmc_G_tau"])
        ph = 0.5 * (
            raw
            + np.interp(beta - tau, fine["tau"], fine["ctqmc_G_tau"])
        )
        delta_raw = mps - raw
        delta_ph = mps - ph

        weights = np.ones(tau.size)
        weights[1:-1:2] = 4
        weights[2:-1:2] = 2
        squared_error = np.dot(weights, delta_ph**2)
        rms = np.sqrt((tau[1] - tau[0]) * squared_error / (3 * beta))
        relative_l2 = np.sqrt(squared_error / np.dot(weights, ph**2))

        axis = axes[row, 0]
        axis.fill_between(
            fine["tau"],
            -(fine["ctqmc_G_tau"] + fine["ctqmc_stderr"]),
            -(fine["ctqmc_G_tau"] - fine["ctqmc_stderr"]),
            color="#4c78a8",
            alpha=0.22,
            linewidth=0,
            label="CTQMC between-chain SE",
        )
        axis.plot(
            fine["tau"],
            -fine["ctqmc_G_tau"],
            color="#4c78a8",
            linewidth=1.6,
            label="CTQMC, continuous bath",
        )
        axis.plot(
            tau,
            -mps,
            "o-",
            color="#e45756",
            markersize=3.5,
            linewidth=1.2,
            label="ESPRIT9 + TDVP2, 9 bath/spin",
        )
        axis.set(
            xlabel=r"$\tau$",
            ylabel=r"$-G(\tau)$",
            title=f"({'a' if row == 0 else 'c'}) U={interaction}",
        )
        axis.legend(frameon=False, fontsize=8)

        axis = axes[row, 1]
        axis.axhline(0, color="black", linewidth=0.8)
        axis.fill_between(
            tau,
            -aligned["ctqmc_ph_stderr"],
            aligned["ctqmc_ph_stderr"],
            color="#4c78a8",
            alpha=0.22,
            linewidth=0,
            label=r"$\pm$ PH-symmetrized CTQMC SE",
        )
        axis.plot(
            tau,
            delta_raw,
            "o-",
            color="#e45756",
            markersize=3.5,
            linewidth=1.2,
            label="MPS - raw CTQMC",
        )
        axis.plot(
            tau,
            delta_ph,
            "s--",
            color="#72b7b2",
            markersize=2.8,
            linewidth=1,
            label="MPS - PH-symmetrized CTQMC",
        )
        axis.set(
            xlabel=r"$\tau$",
            ylabel=r"$\Delta G(\tau)$",
            title=(
                f"({'b' if row == 0 else 'd'}) U={interaction} residual: "
                f"RMS={rms:.4g}, rel-L2={100 * relative_l2:.2f}%"
            ),
        )
        axis.legend(frameon=False, fontsize=8)

fig.suptitle(r"ESPRIT9/TDVP2 MPS vs CTQMC at $\beta=16$")
fig.tight_layout()
fig.savefig(root / "comparison_overview.png", dpi=220)
