#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

from challenge148.fss import (
    binder_summary,
    load_validated_extension_root,
    load_validated_production_root,
)

plt.rcParams["svg.hashsalt"] = "challenge148-report-v1"


def _summaries(points: list[dict[str, object]]) -> dict[tuple[str, int, int, float], float]:
    result: dict[tuple[str, int, int, float], float] = {}
    for point in points:
        chains = point["chains"]
        assert isinstance(chains, list)
        m2 = np.concatenate([np.asarray(chain["m2"], dtype=float) for chain in chains])
        m4 = np.concatenate([np.asarray(chain["m4"], dtype=float) for chain in chains])
        key = (
            str(point["lattice"]),
            int(point["beta_ratio"]),
            int(point["length"]),
            float(point["field"]),
        )
        result[key] = float(binder_summary(m2, m4)["mean"])
    return result


def _pilot_figure(
    base_root: Path, extension_root: Path, output: Path
) -> tuple[str, str, list[dict[str, object]]]:
    base_plan, base_points, _ = load_validated_production_root(base_root)
    extension_plan, extension_points, _ = load_validated_extension_root(
        extension_root
    )
    base = _summaries(base_points)
    extension = _summaries(extension_points)

    series = (
        ("Triangular, beta/L=1", "triangular", 1, 4, 6),
        ("Triangular, beta/L=2", "triangular", 2, 6, 8),
        ("Honeycomb, beta/L=1", "honeycomb", 1, 6, 8),
    )
    exported_series: list[dict[str, object]] = []
    figure, axes = plt.subplots(1, 3, figsize=(11.4, 3.45), constrained_layout=True)
    for axis, (title, lattice, beta_ratio, small, large) in zip(
        axes, series, strict=True
    ):
        small_fields = {
            key[3]
            for values in (base, extension)
            for key in values
            if key[:3] == (lattice, beta_ratio, small)
        }
        large_fields = {
            key[3]
            for values in (base, extension)
            for key in values
            if key[:3] == (lattice, beta_ratio, large)
        }
        fields = sorted(small_fields & large_fields)
        differences = []
        for field in fields:
            small_value = extension.get(
                (lattice, beta_ratio, small, field),
                base.get((lattice, beta_ratio, small, field)),
            )
            large_value = extension.get(
                (lattice, beta_ratio, large, field),
                base.get((lattice, beta_ratio, large, field)),
            )
            assert small_value is not None and large_value is not None
            differences.append(small_value - large_value)
        exported_series.append(
            {
                "beta_ratio": beta_ratio,
                "binder_difference": differences,
                "fields": fields,
                "large_length": large,
                "lattice": lattice,
                "small_length": small,
            }
        )
        axis.axhline(0.0, color="0.25", linewidth=0.9)
        axis.plot(fields, differences, marker="o", linewidth=1.5)
        axis.set_title(title, fontsize=10)
        axis.set_xlabel("Transverse field h/J")
        axis.set_ylabel(f"Q(L={small}) - Q(L={large})")
        axis.grid(alpha=0.22, linewidth=0.6)
    figure.suptitle(
        "Methodological pilot: observed Binder-ratio differences (not paper geometry)",
        fontsize=11,
    )
    figure.savefig(output, format="svg", metadata={"Date": None})
    plt.close(figure)
    return (
        str(base_plan["plan_sha256"]),
        str(extension_plan["plan_sha256"]),
        exported_series,
    )


def _workflow_figure(output: Path) -> None:
    figure, axis = plt.subplots(figsize=(11.4, 3.2))
    axis.set_xlim(0, 11.4)
    axis.set_ylim(0, 3.2)
    axis.axis("off")
    boxes = (
        (0.25, "Pinned sources\nand environments", "complete"),
        (2.55, "ED oracle +\ntwo QMC adapters", "implemented"),
        (4.85, "Immutable evidence\nand acceptance gate", "implemented"),
        (7.15, "72 + 24 cell\nmethod pilots", "complete"),
        (9.45, "140-cell paper\nproduction", "not run"),
    )
    for index, (x, label, status) in enumerate(boxes):
        face = "0.94" if status != "not run" else "white"
        rectangle = Rectangle(
            (x, 1.05),
            1.7,
            1.15,
            facecolor=face,
            edgecolor="0.2",
            linewidth=1.0,
        )
        axis.add_patch(rectangle)
        axis.text(x + 0.85, 1.65, label, ha="center", va="center", fontsize=9)
        axis.text(
            x + 0.85,
            0.78,
            status,
            ha="center",
            va="center",
            fontsize=8,
            color="0.3",
        )
        if index < len(boxes) - 1:
            axis.add_patch(
                FancyArrowPatch(
                    (x + 1.72, 1.62),
                    (boxes[index + 1][0] - 0.03, 1.62),
                    arrowstyle="-|>",
                    mutation_scale=11,
                    linewidth=1.0,
                    color="0.25",
                )
            )
    axis.text(
        5.7,
        2.75,
        "Challenge 148 evidence pipeline and current stopping point",
        ha="center",
        va="center",
        fontsize=12,
    )
    figure.savefig(
        output, format="svg", bbox_inches="tight", metadata={"Date": None}
    )
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", required=True, type=Path)
    parser.add_argument("--extension-root", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    arguments = parser.parse_args()
    arguments.output_directory.mkdir(parents=True, exist_ok=True)
    base_plan_sha256, extension_plan_sha256, exported_series = _pilot_figure(
        arguments.base_root,
        arguments.extension_root,
        arguments.output_directory / "challenge148-pilot-binder.svg",
    )
    (
        arguments.output_directory / "challenge148-pilot-binder.json"
    ).write_text(
        json.dumps(
            {
                "base_plan_sha256": base_plan_sha256,
                "extension_plan_sha256": extension_plan_sha256,
                "notice": (
                    "Methodological pilot only: beta/L and sizes do not match "
                    "the paper-aligned final design."
                ),
                "series": exported_series,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _workflow_figure(
        arguments.output_directory / "challenge148-workflow.svg"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
