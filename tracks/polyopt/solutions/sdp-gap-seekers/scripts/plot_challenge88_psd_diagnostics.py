#!/usr/bin/env python3

import argparse
import hashlib
import pathlib
import tomllib

import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot reconstructed PSD-block minima for Challenge 88."
    )
    parser.add_argument("--gamma-zero", required=True, type=pathlib.Path)
    parser.add_argument("--gamma-half", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    return parser.parse_args()


def load_minima(path: pathlib.Path) -> dict[str, float]:
    with path.open("rb") as stream:
        result = tomllib.load(stream)
    diagnostics = result["solution_diagnostics"]
    if not diagnostics["passed"]:
        raise ValueError(f"diagnostic audit did not pass: {path}")
    return {
        name: float(block["minimum_eigenvalue"])
        for name, block in diagnostics["psd_blocks"].items()
    }


def short_label(name: str) -> str:
    return (
        name.removesuffix("_psd")
        .replace("positive_", "pos ")
        .replace("gap_gap_active_", "gap ")
        .replace("_rx", "\nrx")
        .replace("_ry", " ry")
    )


def main() -> None:
    options = parse_args()
    gamma_zero = load_minima(options.gamma_zero)
    gamma_half = load_minima(options.gamma_half)
    if gamma_zero.keys() != gamma_half.keys():
        raise ValueError("PSD block inventories differ")

    names = sorted(gamma_zero)
    x_values = list(range(len(names)))
    figure, axis = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    axis.plot(
        x_values,
        [gamma_zero[name] for name in names],
        marker="o",
        linewidth=1.8,
        label="gamma = 0",
    )
    axis.plot(
        x_values,
        [gamma_half[name] for name in names],
        marker="s",
        linewidth=1.8,
        label="gamma = 1/2",
    )
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_xticks(x_values, [short_label(name) for name in names])
    axis.set_ylabel("minimum reconstructed eigenvalue")
    axis.set_title(
        "Challenge 88: all 11 exact-reduction PSD blocks remain feasible"
    )
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    options.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(options.output, dpi=180)
    plt.close(figure)
    digest = hashlib.sha256(options.output.read_bytes()).hexdigest()
    (options.output.parent / "SHA256SUMS").write_text(
        f"{digest}  {options.output.name}\n",
        encoding="utf-8",
    )
    print(options.output, flush=True)


if __name__ == "__main__":
    main()
