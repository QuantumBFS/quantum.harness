#!/usr/bin/env python
"""Powder-XRD fit reward for challenge #68 (team ForwardXRD).

Milestone 1: wire the reward and prove it peaks at the true structure.

The reward is the cosine similarity between the powder pattern simulated from a
candidate structure and a fixed target pattern:

    r(X) = <I_sim(X), I_target> / (||I_sim(X)|| ||I_target||)   in [0, 1]

Discrete Bragg peaks from pymatgen's ``XRDCalculator`` are convolved with a
pseudo-Voigt profile onto a fixed 2-theta grid, so two structures are always
compared on the same axis. The reward is a plain black-box scalar -- NumPy in,
float out, no gradients -- which is exactly what the RL loop in
``crystalformer/reinforce/reward.py`` needs from a host callback.

Off-skill: no harness QMB method card covers powder diffraction, so this is not
harness-verified. Verification is the challenge's own criterion, implemented in
``validate()``: the reward must peak at the true structure and must fall under
deliberate corruption of it.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.core import Lattice, Structure

# --------------------------------------------------------------------------
# pattern simulation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternSpec:
    """Everything that fixes the 2-theta axis and the peak shape.

    The target and every candidate must share one spec; a reward comparing
    curves built on different grids or broadenings is meaningless.
    """

    wavelength: str = "CuKa"
    two_theta_min: float = 10.0
    two_theta_max: float = 90.0
    n_points: int = 4096
    fwhm: float = 0.25  # degrees
    eta: float = 0.5  # pseudo-Voigt mix: 0 = pure Gaussian, 1 = pure Lorentzian

    @property
    def grid(self) -> np.ndarray:
        return np.linspace(self.two_theta_min, self.two_theta_max, self.n_points)


def _pseudo_voigt(grid: np.ndarray, center: float, fwhm: float, eta: float) -> np.ndarray:
    """Unit-area pseudo-Voigt centred at ``center``."""
    dx = grid - center
    gauss = (
        (2.0 / fwhm)
        * math.sqrt(math.log(2.0) / math.pi)
        * np.exp(-4.0 * math.log(2.0) * dx**2 / fwhm**2)
    )
    lorentz = (2.0 / (math.pi * fwhm)) / (1.0 + 4.0 * dx**2 / fwhm**2)
    return eta * lorentz + (1.0 - eta) * gauss


def simulate_pattern(structure: Structure, spec: PatternSpec = PatternSpec()) -> np.ndarray:
    """Structure -> continuous powder pattern on ``spec.grid``."""
    calc = XRDCalculator(wavelength=spec.wavelength)
    peaks = calc.get_pattern(
        structure, two_theta_range=(spec.two_theta_min, spec.two_theta_max)
    )
    grid = spec.grid
    curve = np.zeros_like(grid)
    for two_theta, intensity in zip(peaks.x, peaks.y):
        curve += intensity * _pseudo_voigt(grid, two_theta, spec.fwhm, spec.eta)
    return curve


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def make_xrd_reward_fn(target: np.ndarray, spec: PatternSpec = PatternSpec()):
    """Return ``reward(structure) -> float`` against a fixed target pattern.

    Named to match ``make_prop_reward_fn`` in CrystalFormer's reward module,
    which is where this drops in.
    """

    def reward(structure: Structure) -> float:
        return cosine_similarity(simulate_pattern(structure, spec), target)

    return reward


# --------------------------------------------------------------------------
# deliberate corruptions -- the negative controls
# --------------------------------------------------------------------------


def strained(structure: Structure, eps: float) -> Structure:
    """Isotropic lattice strain: shifts every peak, keeps the motif."""
    s = structure.copy()
    s.apply_strain(eps)
    return s


def displaced(structure: Structure, sigma: float, seed: int = 0) -> Structure:
    """Gaussian rattle of every site by ``sigma`` angstrom: redistributes intensity."""
    rng = np.random.default_rng(seed)
    s = structure.copy()
    for i in range(len(s)):
        s.translate_sites(i, rng.normal(0.0, sigma, 3), frac_coords=False)
    return s


def substituted(structure: Structure, old: str, new: str) -> Structure:
    """Swap a species: same geometry, different scattering factors."""
    s = structure.copy()
    s.replace_species({old: new})
    return s


# --------------------------------------------------------------------------
# reference structures (built offline -- no Materials Project API key needed)
# --------------------------------------------------------------------------


def nacl(a: float = 5.6402) -> Structure:
    return Structure.from_spacegroup(
        "Fm-3m", Lattice.cubic(a), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]
    )


def silicon(a: float = 5.4309) -> Structure:
    return Structure.from_spacegroup(
        "Fd-3m", Lattice.cubic(a), ["Si"], [[0.125, 0.125, 0.125]]
    )


CASES = {"NaCl": nacl, "Si": silicon}


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def validate(name: str, spec: PatternSpec, strain_scan_max: float = 0.10, n_scan: int = 401):
    """Run the negative-control suite for one known structure."""
    truth = CASES[name]()
    target = simulate_pattern(truth, spec)
    reward = make_xrd_reward_fn(target, spec)

    controls = [("true structure (positive control)", reward(truth))]
    for eps in (0.005, 0.01, 0.02, 0.05):
        controls.append((f"lattice strain {eps:+.1%}", reward(strained(truth, eps))))
    for sigma in (0.05, 0.10, 0.20):
        controls.append((f"atomic rattle sigma={sigma:.2f} A", reward(displaced(truth, sigma))))
    if name == "NaCl":
        controls.append(("species swap Na->K", reward(substituted(truth, "Na", "K"))))
        controls.append(("wrong compound (Si)", reward(silicon())))
    else:
        controls.append(("species swap Si->Ge", reward(substituted(truth, "Si", "Ge"))))
        controls.append(("wrong compound (NaCl)", reward(nacl())))

    # fine strain scan: exposes the look-alike local minima the challenge is about
    eps_grid = np.linspace(-strain_scan_max, strain_scan_max, n_scan)
    strain_curve = np.array([reward(strained(truth, e)) for e in eps_grid])

    sigma_grid = np.linspace(0.0, 0.5, 26)
    rattle_curve = np.array([reward(displaced(truth, s)) if s > 0 else 1.0 for s in sigma_grid])

    return {
        "name": name,
        "formula": truth.composition.reduced_formula,
        "spacegroup": truth.get_space_group_info()[0],
        "n_sites": len(truth),
        "target": target,
        "truth": truth,
        "controls": controls,
        "eps_grid": eps_grid,
        "strain_curve": strain_curve,
        "sigma_grid": sigma_grid,
        "rattle_curve": rattle_curve,
        "reward": reward,
    }


def make_figure(results, spec: PatternSpec, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(results)
    fig, axes = plt.subplots(n, 3, figsize=(16.5, 4.4 * n), squeeze=False)

    for row, res in enumerate(results):
        grid = spec.grid
        truth = res["truth"]

        # -- panel 1: pattern overlay --------------------------------------
        ax = axes[row][0]
        ax.plot(grid, res["target"], lw=1.6, label=f"{res['name']} (target)", color="#1f77b4")
        ax.plot(
            grid,
            simulate_pattern(strained(truth, 0.02), spec),
            lw=1.1,
            ls="--",
            color="#d62728",
            label="+2% strain",
        )
        ax.plot(
            grid,
            simulate_pattern(displaced(truth, 0.20), spec),
            lw=1.1,
            ls=":",
            color="#2ca02c",
            label="rattle 0.20 A",
        )
        ax.set_xlabel(r"$2\theta$ (deg)")
        ax.set_ylabel("intensity (arb.)")
        ax.set_title(f"{res['name']} — {res['formula']}, {res['spacegroup']}")
        ax.legend(fontsize=8)

        # -- panel 2: reward vs strain -------------------------------------
        ax = axes[row][1]
        ax.plot(res["eps_grid"] * 100, res["strain_curve"], lw=1.4, color="#1f77b4")
        ax.axvline(0.0, color="k", lw=0.8, ls="--")
        ax.axhline(1.0, color="grey", lw=0.6, ls=":")
        ax.set_xlabel("isotropic lattice strain (%)")
        ax.set_ylabel("reward  r(X)")
        ax.set_title("peaks at the true structure")
        ax.set_ylim(-0.02, 1.05)

        # -- panel 3: reward vs rattle -------------------------------------
        ax = axes[row][2]
        ax.plot(res["sigma_grid"], res["rattle_curve"], lw=1.4, marker="o", ms=3, color="#ff7f0e")
        ax.axhline(1.0, color="grey", lw=0.6, ls=":")
        ax.set_xlabel(r"atomic displacement $\sigma$ ($\AA$)")
        ax.set_ylabel("reward  r(X)")
        ax.set_title("decays under corruption")
        ax.set_ylim(-0.02, 1.05)

    fig.suptitle(
        "ForwardXRD milestone 1 — powder-XRD cosine reward: positive control + negative controls",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="tracks/other/results/m1-reward-validation")
    ap.add_argument("--fwhm", type=float, default=PatternSpec.fwhm)
    ap.add_argument("--two-theta-min", type=float, default=PatternSpec.two_theta_min)
    ap.add_argument("--two-theta-max", type=float, default=PatternSpec.two_theta_max)
    ap.add_argument("--n-points", type=int, default=PatternSpec.n_points)
    ap.add_argument("--eta", type=float, default=PatternSpec.eta)
    args = ap.parse_args()

    spec = PatternSpec(
        two_theta_min=args.two_theta_min,
        two_theta_max=args.two_theta_max,
        n_points=args.n_points,
        fwhm=args.fwhm,
        eta=args.eta,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    results = [validate(name, spec) for name in CASES]

    # ---- console table ---------------------------------------------------
    passed = True
    report_lines = []
    for res in results:
        header = f"\n{res['name']}  ({res['formula']}, {res['spacegroup']}, {res['n_sites']} sites)"
        print(header)
        print(f"  {'control':<38} {'reward':>8}")
        report_lines.append(header)
        report_lines.append(f"  {'control':<38} {'reward':>8}")
        for label, value in res["controls"]:
            line = f"  {label:<38} {value:>8.4f}"
            print(line)
            report_lines.append(line)

        truth_r = res["controls"][0][1]
        worst_corrupt = max(v for _, v in res["controls"][1:])
        if not (truth_r > 0.999 and truth_r > worst_corrupt):
            passed = False

    # global max of the strain scan must sit at zero strain
    for res in results:
        i_max = int(np.argmax(res["strain_curve"]))
        if abs(res["eps_grid"][i_max]) > 1e-9:
            passed = False

    verdict = "PASS" if passed else "FAIL"
    print(f"\nMilestone 1 verdict: {verdict}")
    print("  reward peaks at the true structure and falls for every corruption"
          if passed else "  reward did NOT peak uniquely at the true structure")

    # ---- artifacts -------------------------------------------------------
    fig_path = out / "reward_validation.png"
    make_figure(results, spec, fig_path)

    run = {
        "run": "m1-reward-validation",
        "challenge": "QuantumBFS/quantum.harness#68",
        "team": "ForwardXRD",
        "milestone": "1 — wire the pymatgen XRD reward, confirm it peaks at the true structure",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pattern_spec": asdict(spec),
        "verdict": verdict,
        "cases": [
            {
                "name": r["name"],
                "formula": r["formula"],
                "spacegroup": r["spacegroup"],
                "n_sites": r["n_sites"],
                "controls": {label: round(v, 6) for label, v in r["controls"]},
                "strain_scan_argmax_percent": round(
                    float(r["eps_grid"][int(np.argmax(r["strain_curve"]))] * 100), 6
                ),
                "strain_scan_n_local_maxima": int(
                    sum(
                        1
                        for i in range(1, len(r["strain_curve"]) - 1)
                        if r["strain_curve"][i] > r["strain_curve"][i - 1]
                        and r["strain_curve"][i] > r["strain_curve"][i + 1]
                    )
                ),
            }
            for r in results
        ],
        "artifacts": [str(fig_path)],
        "verified_by": "self-contained negative controls; not harness method-card verified",
    }
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    (out / "report.txt").write_text("\n".join(report_lines) + f"\n\nverdict: {verdict}\n")

    print(f"\nwrote {fig_path}")
    print(f"wrote {out / 'run.json'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
