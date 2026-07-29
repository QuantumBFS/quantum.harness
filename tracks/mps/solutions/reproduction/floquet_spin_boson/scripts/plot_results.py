#!/usr/bin/env python3
"""Strict, deterministic visual checkpoints for the Floquet reproduction."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FIG3_POINTS = {
    "longitudinal": (10.0, 5.0, 2.5),
    "transversal": (2.0, 1.5, 1.0),
}
COLORS = ("#0C7BDC", "#fb6d72", "#00bf7d")


def _structured_csv(path: Path, required: tuple[str, ...]) -> np.ndarray:
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    table = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    table = np.atleast_1d(table)
    names = table.dtype.names or ()
    missing = sorted(set(required).difference(names))
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    return table


def plot_fig2(args: argparse.Namespace) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
    for axis, frequency in zip(axes, (2.5, 10.0)):
        path = args.result_root / f"ours_omega_d_{frequency}.csv"
        if not path.is_file():
            raise ValueError(f"missing Fig. 2 point: ωd={frequency:g}")
        table = np.atleast_2d(np.loadtxt(path))
        if table.shape[1] != 3 or not np.all(np.isfinite(table)):
            raise ValueError(f"{path}: expected finite time/exact/Redfield columns")
        axis.plot(table[:, 0], table[:, 1], color=COLORS[0], label="uniTEMPO")
        axis.plot(
            table[:, 0], table[:, 2], color=COLORS[1], linestyle="--",
            label="Redfield–Magnus"
        )
        axis.set_title(f"ωd={frequency:g} Ω")
        axis.set_xlabel("time Ωt")
        axis.set_ylabel("⟨σz(t)⟩")
        axis.set_ylim(-1.0, 1.0)
        axis.grid(alpha=0.16)
        axis.legend(frameon=False)
    figure.suptitle("Fig. 2 transient checkpoint")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)


def _reference_file(root: Path, drive: str, frequency: float) -> Path:
    matches = sorted(root.glob(f"heat_current_{drive}_*ω_d_{frequency:g}_*.csv"))
    if len(matches) != 1:
        raise ValueError(
            f"expected one Fig. 3 reference for {drive} ωd={frequency:g}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _fig3_point(root: Path, drive: str, frequency: float) -> Path | None:
    candidates = (root / drive / str(frequency), root / drive / f"{frequency:g}")
    return next(
        (
            path
            for path in candidates
            if (path / "continuous_heat_current.csv").is_file()
            and (path / "delta_peaks.csv").is_file()
        ),
        None,
    )


def plot_fig3(args: argparse.Namespace) -> None:
    result_root = args.result_root
    reference_root = args.reference_root
    present: dict[str, list[float]] = {}
    for drive, frequencies in FIG3_POINTS.items():
        present[drive] = [
            frequency
            for frequency in frequencies
            if _fig3_point(result_root, drive, frequency) is not None
        ]
        if not args.allow_validation_subset:
            missing = [
                frequency
                for frequency in frequencies
                if frequency not in present[drive]
            ]
            if missing:
                raise ValueError(
                    f"missing Fig. 3 point: {drive} ωd={missing[0]:g}"
                )
    if not any(present.values()):
        raise ValueError("missing Fig. 3 point: result root contains no paper point")

    figure, axes = plt.subplots(
        2, 2, figsize=(11, 6.8), sharex="col",
        gridspec_kw={"height_ratios": (3.2, 1.0)}, constrained_layout=True
    )
    for column, drive in enumerate(("longitudinal", "transversal")):
        spectrum_axis = axes[0, column]
        delta_axis = axes[1, column]
        for color, frequency in zip(COLORS, FIG3_POINTS[drive]):
            if frequency not in present[drive]:
                continue
            point = _fig3_point(result_root, drive, frequency)
            assert point is not None
            ours = _structured_csv(
                point / "continuous_heat_current.csv", ("omega", "current")
            )
            reference = np.loadtxt(_reference_file(reference_root, drive, frequency))
            reference = np.atleast_1d(reference).astype(float)
            reference_omega = 0.005 * np.arange(1, len(reference) + 1)
            spectrum_axis.plot(
                reference_omega, reference, color=color, linestyle="--",
                linewidth=1.1, alpha=0.75
            )
            spectrum_axis.plot(
                ours["omega"], ours["current"], color=color, linewidth=1.5,
                label=f"ωd={frequency:g}"
            )
            peaks = _structured_csv(
                point / "delta_peaks.csv",
                ("n", "omega", "integrated_weight"),
            )
            if len(peaks):
                delta_axis.vlines(
                    peaks["omega"], 0.0, peaks["integrated_weight"],
                    color=color, linewidth=1.5
                )
        spectrum_axis.set_title(f"{drive} drive")
        spectrum_axis.set_ylabel("continuous heat current density")
        spectrum_axis.grid(alpha=0.16)
        handles, labels = spectrum_axis.get_legend_handles_labels()
        if handles:
            spectrum_axis.legend(handles, labels, frameon=False)
        delta_axis.set_xlabel("bath frequency ω/Ω")
        delta_axis.set_ylabel("delta weight")
        delta_axis.grid(alpha=0.16)
    figure.suptitle("Fig. 3 checkpoint — solid: ours; dashed: Zenodo")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)


def _single_reference(root: Path, drive: str) -> Path:
    matches = sorted(root.glob(f"*{drive}*.csv"))
    if len(matches) != 1:
        raise ValueError(
            f"expected one Fig. 5 reference for {drive}, found {len(matches)}"
        )
    return matches[0]


def plot_fig5(args: argparse.Namespace) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    for color, drive in zip(COLORS, ("longitudinal", "transversal")):
        table = _structured_csv(
            args.result_root / f"total_current_{drive}.csv",
            ("omega_d", "status", "total_current"),
        )
        bad = np.flatnonzero(table["status"] != "complete")
        if len(bad):
            frequency = float(table["omega_d"][bad[0]])
            raise ValueError(
                f"non-complete Fig. 5 point: {drive} ωd={frequency:g}"
            )
        current = table["total_current"].astype(float)
        if not np.all(np.isfinite(current)):
            raise ValueError(f"non-finite Fig. 5 current: {drive}")
        reference = np.atleast_1d(
            np.loadtxt(_single_reference(args.reference_root, drive))
        ).astype(float)
        if len(reference) != len(table):
            raise ValueError(
                f"Fig. 5 reference length mismatch for {drive}: "
                f"{len(reference)} != {len(table)}"
            )
        axis.plot(
            table["omega_d"], reference, color=color, linestyle="--",
            linewidth=1.1, alpha=0.75
        )
        axis.plot(
            table["omega_d"], current, color=color, linewidth=1.5, label=drive
        )
    axis.set_xlabel("driving frequency ωd/Ω")
    axis.set_ylabel("total heat current")
    axis.grid(alpha=0.16)
    axis.legend(frameon=False)
    axis.set_title("Fig. 5 checkpoint — solid: ours; dashed: Zenodo")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="figure", required=True)
    for name, handler in (
        ("fig2", plot_fig2),
        ("fig3", plot_fig3),
        ("fig5", plot_fig5),
    ):
        command = subparsers.add_parser(name)
        command.add_argument("--result-root", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name in ("fig3", "fig5"):
            command.add_argument("--reference-root", type=Path, required=True)
        if name == "fig3":
            command.add_argument("--allow-validation-subset", action="store_true")
        command.set_defaults(handler=handler)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
