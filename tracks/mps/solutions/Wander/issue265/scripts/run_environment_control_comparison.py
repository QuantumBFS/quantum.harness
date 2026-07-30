#!/usr/bin/env python3
"""Compare public high-temperature Delta=1 and Delta=2 walls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.environment_control import compare_public_environment_controls
from src.synthetic_data import load_npz


def _plot(summary: dict[str, object], path: Path) -> None:
    delta1 = summary["delta1"]
    delta2 = summary["delta2"]
    transfer = summary["transfer"]
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.8))

    axes[0].bar(
        [0, 1],
        [delta1["fit"]["a"], delta2["fit"]["a"]],
        color=["#386CB0", "#F2B134"],
    )
    axes[0].set_xticks([0, 1], labels=[r"$\Delta=1$", r"$\Delta=2$"])
    axes[0].set_ylabel("local fitted a")
    axes[0].set_title("Nonlinear coefficient")

    axes[1].bar(
        [0, 1],
        [
            delta1["width_power"]["exponent"],
            delta2["width_power"]["exponent"],
        ],
        color=["#386CB0", "#F2B134"],
    )
    axes[1].axhline(0.5, color="0.3", linestyle=":", label="diffusive 1/2")
    axes[1].axhline(
        2.0 / 3.0, color="0.3", linestyle="--", label="KPZ-like 2/3"
    )
    axes[1].set_xticks([0, 1], labels=[r"$\Delta=1$", r"$\Delta=2$"])
    axes[1].set_ylabel("width exponent")
    axes[1].set_title("Observed broadening")
    axes[1].legend(frameon=False, fontsize=8)

    values = np.array(
        [
            [
                delta1["self_forecast"]["integrated_relative_l2"],
                transfer["delta2_coefficients_on_delta1"][
                    "integrated_relative_l2"
                ],
            ],
            [
                transfer["delta1_coefficients_on_delta2"][
                    "integrated_relative_l2"
                ],
                delta2["self_forecast"]["integrated_relative_l2"],
            ],
        ]
    )
    image = axes[2].imshow(values, cmap="magma", aspect="equal")
    axes[2].set_xticks([0, 1], labels=[r"fit $\Delta=1$", r"fit $\Delta=2$"])
    axes[2].set_yticks(
        [0, 1], labels=[r"data $\Delta=1$", r"data $\Delta=2$"]
    )
    axes[2].set_title("No-refit profile error")
    figure.colorbar(image, ax=axes[2], fraction=0.046)
    figure.tight_layout()
    figure.savefig(path, dpi=190)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delta1",
        type=Path,
        default=ROOT / "data" / "kharkov_highT_delta1.npz",
    )
    parser.add_argument(
        "--delta2",
        type=Path,
        default=ROOT / "data" / "kharkov_highT_delta2.npz",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "public_environment_control",
    )
    args = parser.parse_args()
    summary = compare_public_environment_controls(
        load_npz(str(args.delta1)),
        load_npz(str(args.delta2)),
    )
    summary["sources"] = {
        "delta1": str(args.delta1.resolve()),
        "delta2": str(args.delta2.resolve()),
        "upstream": (
            "https://github.com/yourball/pde-many-body/tree/main/"
            "domain_wall_xxz/data"
        ),
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    _plot(summary, args.outdir / "environment_transfer.png")

    delta1 = summary["delta1"]
    delta2 = summary["delta2"]
    transfer = summary["transfer"]
    report = rf"""# Public environment control: Delta=1 versus Delta=2

Both public high-temperature walls admit accurate within-environment constant
Burgers surrogates, but they do not share coefficients or a width exponent.

| quantity | Delta=1 | Delta=2 |
|---|---:|---:|
| \(a\) | {delta1['fit']['a']:.8f} | {delta2['fit']['a']:.8f} |
| \(D\) | {delta1['fit']['D0']:.8f} | {delta2['fit']['D0']:.8f} |
| width exponent, \(t=80\!-\!190\) | {delta1['width_power']['exponent']:.6f} | {delta2['width_power']['exponent']:.6f} |
| self-forecast integrated error | {delta1['self_forecast']['integrated_relative_l2']:.6%} | {delta2['self_forecast']['integrated_relative_l2']:.6%} |

Moving the Delta=1 coefficients to Delta=2 without refitting increases the
error by a factor of
{transfer['delta1_to_delta2_error_ratio']:.2f}; moving the Delta=2
coefficients to Delta=1 increases it by
{transfer['delta2_to_delta1_error_ratio']:.2f}.

This is an exploratory public negative control, not one of the preregistered
Delta=0.8/1.2 production conditions. It shows that “constant Burgers fits a
finite window” is not equivalent to “the data are KPZ” and does not identify
universal microscopic coefficients.
"""
    (args.outdir / "REPORT.md").write_text(report)
    print(
        json.dumps(
            {
                "delta1_to_delta2_error_ratio": transfer[
                    "delta1_to_delta2_error_ratio"
                ],
                "delta2_to_delta1_error_ratio": transfer[
                    "delta2_to_delta1_error_ratio"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
