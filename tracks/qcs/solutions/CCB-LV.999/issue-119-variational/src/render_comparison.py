from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .result_schema import validate_result_document


def _signed(value: float, digits: int = 9) -> str:
    return f"{value:+.{digits}f}".replace("-", "−")


def render_ordering_comparison(
    run_dirs: list[str | Path],
    output_dir: str | Path,
) -> tuple[Path, Path]:
    if len(run_dirs) < 2:
        raise ValueError("at least two ordering runs are required")
    results = [
        validate_result_document(
            json.loads((Path(run_dir) / "result.json").read_text(encoding="utf-8"))
        )
        for run_dir in run_dirs
    ]
    first = results[0]
    for result in results[1:]:
        if result["instance"] != first["instance"]:
            raise ValueError("comparison requires one instance")
        if result["input"]["sha256"] != first["input"]["sha256"]:
            raise ValueError("comparison requires byte-identical FCIDUMP inputs")
        if result["sector"] != first["sector"]:
            raise ValueError("comparison requires the same conserved sector")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output_path / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter

    skqd = float(first.get("references", {}).get("skqd"))
    cas4 = first.get("references", {}).get("cas4")
    colors = {"fiedler": "#3b6fb6", "ga": "#d1495b"}
    figure, (energy_axis, difference_axis) = plt.subplots(
        1,
        2,
        figsize=(10.8, 4.4),
        constrained_layout=True,
    )
    for result in results:
        method = result["ordering"]["method"]
        dimensions = [stage["bond_dimension"] for stage in result["stages"]]
        energies = [stage["energy_hartree"] for stage in result["stages"]]
        color = colors.get(method)
        energy_axis.plot(
            dimensions,
            energies,
            "o-",
            lw=2.0,
            ms=6,
            label=method,
            color=color,
        )
        difference_axis.plot(
            dimensions,
            [(energy - skqd) * 1000.0 for energy in energies],
            "o-",
            lw=2.0,
            ms=6,
            label=method,
            color=color,
        )

    energy_axis.axhline(
        skqd,
        color="#222222",
        ls="--",
        lw=1.2,
        label="verified SKQD",
    )
    if cas4 is not None:
        energy_axis.axhline(
            float(cas4),
            color="#777777",
            ls=":",
            lw=1.2,
            label="CAS(4)",
        )
    energy_axis.set_xlabel("Bond dimension M")
    energy_axis.set_ylabel("Energy (Eₕ)")
    energy_axis.set_title("Anderson ordering comparison")
    energy_axis.yaxis.set_major_formatter(FormatStrFormatter("%.3f"))
    energy_axis.grid(alpha=0.25)
    energy_axis.legend(frameon=False, fontsize=8)

    difference_axis.axhline(0.0, color="#222222", ls="--", lw=1.2)
    difference_axis.set_yscale("symlog", linthresh=10.0, linscale=1.0)
    difference_axis.set_xlabel("Bond dimension M")
    difference_axis.set_ylabel("E − E_SKQD (mEₕ)")
    difference_axis.set_title("Negative values beat SKQD")
    difference_axis.grid(alpha=0.25)
    difference_axis.legend(frameon=False, fontsize=8)
    for result in results:
        method = result["ordering"]["method"]
        headline = result["headline"]
        difference = (float(headline["energy_hartree"]) - skqd) * 1000.0
        difference_axis.annotate(
            f"{method}: {difference:+.2f}",
            (headline["bond_dimension"], difference),
            xytext=(-6, 8 if difference >= 0 else -14),
            textcoords="offset points",
            ha="right",
            fontsize=8,
            color=colors.get(method),
        )

    plot_path = output_path / "ordering-comparison.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)

    rows = []
    for result in results:
        headline = result["headline"]
        delta = float(headline["energy_hartree"]) - skqd
        rows.append(
            "| "
            + " | ".join(
                [
                    result["ordering"]["method"],
                    str(headline["bond_dimension"]),
                    f"{headline['energy_hartree']:.12f}".replace("-", "−"),
                    _signed(delta * 1000.0),
                    f"{result['stages'][-1].get('discarded_weight', float('nan')):.3e}",
                    f"{result['stages'][-1].get('wall_time_s', float('nan')):.3f}",
                    f"{result['stages'][-1].get('rss_mb', float('nan')):.3f}",
                ]
            )
            + " |"
        )
    report_path = output_path / "ORDERING_COMPARISON.md"
    report_path.write_text(
        "\n".join(
            [
                "# Anderson orbital-ordering comparison",
                "",
                (
                    f"Input SHA-256: `{first['input']['sha256']}`; "
                    f"NORB={first['sector']['norb']}, "
                    f"NELEC={first['sector']['nelec']}, "
                    f"MS2={first['sector']['ms2']}, spin={first['sector']['spin']}."
                ),
                "",
                "| Ordering | M | Saved-MPS E (Eₕ) | E−SKQD (mEₕ) | DW | DMRG wall (s) | RSS (MB) |",
                "|---|---:|---:|---:|---:|---:|---:|",
                *rows,
                "",
                (
                    "The headline values are finite-M saved-MPS expectations. "
                    "A negative E−SKQD value is a lower classical variational upper bound."
                ),
                "",
                "![Ordering comparison](ordering-comparison.png)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return plot_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Anderson ordering runs")
    parser.add_argument("--run-dir", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    plot, report = render_ordering_comparison(args.run_dir, args.output_dir)
    print(f"plot: {plot}", flush=True)
    print(f"report: {report}", flush=True)


if __name__ == "__main__":
    main()
