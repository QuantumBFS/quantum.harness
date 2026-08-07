#!/usr/bin/env python3
"""Launch the issue #148 card: is h_c(triangular)/h_c(honeycomb) = sqrt(5)?

Reconnaissance-scale flight of cards/round3/tfim-ratio-sqrt5-001.yaml through
the full pipeline: registry gate -> static fire -> hop (Binder crossings on
small PBC clusters) -> three-state verdict -> telemetry + heuristics + figures.

  python3 run_sqrt5.py

Outputs: results/telemetry_sqrt5.jsonl, results/report_sqrt5.md,
heuristics/tfim-ratio-sqrt5-001.yaml, briefs/data/sqrt5.json,
briefs/figures/binder_crossings.png
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from pf import heuristics, static_fire, tfim2d, verdict

SOLVERS = ["xxz_j2_chain", "sawtooth_chain", "tfim_2d"]  # registry, INTERFACE.md §4
SQ5 = 2.23606797749979
LITERATURE = {"triangular": (4.76811, 9e-5), "honeycomb": (2.13250, 4e-5),
              "square": (3.04438, 2e-5)}  # Blöte & Deng, PRE 66, 066110 (2002)


def hop(card):
    """Binder-cumulant crossings per lattice; ratio vs sqrt(5). Returns (metrics, raw)."""
    s = card["setup"]
    raw = {}
    for lat in ("triangular", "honeycomb"):
        lo, hi = s["params"][f"h_{lat}"]
        grid = np.round(np.arange(lo, hi + 1e-9, 0.1), 6)
        shapes = [tuple(sh) for sh in s["lattices"][lat]]
        pairs, curves = tfim2d.hc_from_crossings(lat, shapes, grid)
        n_mean = [np.sqrt((2 if lat == "honeycomb" else 1) * a[0] * a[1]
                          * (2 if lat == "honeycomb" else 1) * b[0] * b[1])
                  for a, b, _ in pairs]
        raw[lat] = {"grid": list(grid), "curves": {str(k): v for k, v in curves.items()},
                    "pairs": [(str(a), str(b), hc) for a, b, hc in pairs],
                    "n_mean": n_mean}
    est = {lat: [hc for _, _, hc in raw[lat]["pairs"]] for lat in raw}
    hc_t, hc_h = np.mean(est["triangular"]), np.mean(est["honeycomb"])
    s_t, s_h = np.std(est["triangular"]), np.std(est["honeycomb"])
    ratio = hc_t / hc_h
    sigma = ratio * np.sqrt((s_t / hc_t) ** 2 + (s_h / hc_h) ** 2)
    metrics = {
        "decisiveness": float(abs(ratio - SQ5) / sigma),
        "gradient_vs_L": float(np.polyfit(raw["triangular"]["n_mean"],
                                          est["triangular"], 1)[0]),
        "effect": float(abs(ratio - SQ5)),
        "noise": float(sigma),
        "ratio": float(ratio),
        "hc_triangular": [float(hc_t), float(s_t)],
        "hc_honeycomb": [float(hc_h), float(s_h)],
    }
    return metrics, raw


def main():
    card = yaml.safe_load(open("cards/round3/tfim-ratio-sqrt5-001.yaml"))
    records = []

    if card["model"] not in SOLVERS:
        records.append(verdict.record(card, "dead", f"no_solver: {card['model']}", {}))
    else:
        ok, detail = static_fire.run(card)
        if not ok:
            records.append(verdict.record(card, "dead", f"setup_error: {detail}", {}))
        else:
            print(f"static fire: {detail}", flush=True)
            m, raw = hop(card)
            v, reason = verdict.judge(card, m)
            reason += (f" — R = {m['ratio']:.5f} ± {m['noise']:.5f} vs sqrt(5); "
                       f"h_c tri {m['hc_triangular'][0]:.3f}±{m['hc_triangular'][1]:.3f}, "
                       f"honey {m['hc_honeycomb'][0]:.3f}±{m['hc_honeycomb'][1]:.3f} "
                       f"(lit 4.76811(9), 2.13250(4)); need sigma_R <= "
                       f"{card['gate']['target_precision']:.1e} -> route to sign-free QMC")
            records.append(verdict.record(card, v, reason, m))
            print(f"[{v}] {card['id']}  {reason}", flush=True)

            out = Path("briefs/data"); out.mkdir(parents=True, exist_ok=True)
            with open(out / "sqrt5.json", "w") as f:
                json.dump({"card": card["id"], "metrics": m, "raw": raw,
                           "literature": LITERATURE}, f, indent=1)
            plot(raw, m)

    out = Path("results"); out.mkdir(exist_ok=True)
    with open(out / "telemetry_sqrt5.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = heuristics.dump(records, "heuristics")
    print(f"deposited {n} heuristics entries; telemetry in results/telemetry_sqrt5.jsonl")


def plot(raw, m):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, lat, title in [(axes[0], "triangular", "triangular (z=6)"),
                           (axes[1], "honeycomb", "honeycomb (z=3)")]:
        for shape, curve in raw[lat]["curves"].items():
            n = eval(shape)[0] * eval(shape)[1] * (2 if lat == "honeycomb" else 1)
            ax.plot(raw[lat]["grid"], curve, ".-", ms=3, label=f"N={n}")
        hc, err = LITERATURE[lat]
        ax.axvline(hc, color="k", ls="--", lw=1, label=f"Blöte–Deng {hc}")
        ax.set_xlabel("h / J"); ax.set_ylabel("Binder cumulant U")
        ax.set_title(f"TFIM {title}"); ax.legend(fontsize=8)
    fig.suptitle(f"R = h_c(tri)/h_c(honey) = {m['ratio']:.4f} ± {m['noise']:.4f} "
                 f"vs √5 = {SQ5:.4f} — decisiveness {m['decisiveness']:.2f}")
    fig.tight_layout()
    out = Path("briefs/figures"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "binder_crossings.png", dpi=150)
    print("wrote briefs/figures/binder_crossings.png")


if __name__ == "__main__":
    main()
