from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .result_schema import validate_result_document


def _number(value: float) -> str:
    return f"{value:.12f}".replace("-", "−")


def render_run(run_dir: str | Path) -> tuple[Path, Path]:
    run_path = Path(run_dir)
    result_path = run_path / "result.json"
    result = validate_result_document(
        json.loads(result_path.read_text(encoding="utf-8"))
    )

    os.environ.setdefault("MPLCONFIGDIR", str(run_path / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stages = result["stages"]
    bond_dimensions = [stage["bond_dimension"] for stage in stages]
    energies = [stage["energy_hartree"] for stage in stages]
    discarded_weights = [stage.get("discarded_weight") for stage in stages]

    figure, (energy_axis, weight_axis) = plt.subplots(
        1,
        2,
        figsize=(10.5, 4.2),
        constrained_layout=True,
    )
    energy_axis.plot(bond_dimensions, energies, "o-", color="#205493", lw=1.8)
    for name, reference in result.get("references", {}).items():
        energy_axis.axhline(
            reference,
            ls="--",
            lw=1.0,
            alpha=0.7,
            label=name,
        )
    energy_axis.set_xlabel("Bond dimension M")
    energy_axis.set_ylabel("Energy (Eₕ)")
    energy_axis.set_title(f"{result['instance']}: finite-M energy")
    energy_axis.grid(alpha=0.25)
    if result.get("references"):
        energy_axis.legend(frameon=False, fontsize=8)

    usable_weights = [
        (bond_dimension, weight)
        for bond_dimension, weight in zip(bond_dimensions, discarded_weights)
        if weight is not None and weight > 0
    ]
    if usable_weights:
        weight_axis.semilogy(
            [value[0] for value in usable_weights],
            [value[1] for value in usable_weights],
            "o-",
            color="#d95f02",
            lw=1.8,
        )
    else:
        weight_axis.text(
            0.5,
            0.5,
            "No positive discarded weights",
            ha="center",
            va="center",
            transform=weight_axis.transAxes,
        )
    weight_axis.set_xlabel("Bond dimension M")
    weight_axis.set_ylabel("Discarded weight")
    weight_axis.set_title("Truncation diagnostic")
    weight_axis.grid(alpha=0.25)

    plot_path = run_path / "convergence.png"
    figure.savefig(plot_path, dpi=180)
    plt.close(figure)

    comparison_path = None
    if "skqd" in result.get("references", {}):
        skqd = float(result["references"]["skqd"])
        differences = [(energy - skqd) * 1000.0 for energy in energies]
        comparison_figure, comparison_axis = plt.subplots(
            figsize=(6.8, 4.2),
            constrained_layout=True,
        )
        comparison_axis.plot(
            bond_dimensions,
            differences,
            "o-",
            color="#205493",
            lw=2.0,
        )
        comparison_axis.axhline(
            0.0,
            color="#222222",
            ls="--",
            lw=1.2,
            label="SKQD",
        )
        for bond_dimension, difference in zip(bond_dimensions, differences):
            comparison_axis.annotate(
                f"{difference:+.3f}",
                (bond_dimension, difference),
                xytext=(0, 8 if difference >= 0 else -15),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )
        comparison_axis.set_xlabel("Bond dimension M")
        comparison_axis.set_ylabel("E(M) − E_SKQD (mEₕ)")
        comparison_axis.set_title("Finite-M energy relative to SKQD")
        comparison_axis.margins(x=0.05, y=0.18)
        comparison_axis.grid(alpha=0.25)
        comparison_axis.legend(frameon=False)
        comparison_path = run_path / "skqd-comparison.png"
        comparison_figure.savefig(comparison_path, dpi=180)
        plt.close(comparison_figure)

    headline = result["headline"]
    report_path = run_path / "REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                f"# {result['instance']} run report",
                "",
                (
                    f"Headline: E = {_number(headline['energy_hartree'])} Eₕ at "
                    f"M={headline['bond_dimension']} (finite-M MPS expectation)."
                ),
                "",
                (
                    f"Sector: NORB={result['sector']['norb']}, "
                    f"NELEC={result['sector']['nelec']}, "
                    f"MS2={result['sector']['ms2']}, "
                    f"SU(2) spin={result['sector']['spin']}."
                ),
                "",
                (
                    f"Input SHA-256: `{result['input']['sha256']}`. "
                    f"Ordering: {result['ordering']['method']}."
                ),
                "",
                (
                    "Verification: input integrity and result schema passed; "
                    "convergence or cross-method verification is not implied."
                ),
                "",
                "![Convergence](convergence.png)",
                "",
                *(
                    ["![SKQD comparison](skqd-comparison.png)", ""]
                    if comparison_path is not None
                    else []
                ),
            ]
        ),
        encoding="utf-8",
    )
    return plot_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render DMRG convergence artifacts")
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    plot, report = render_run(args.run_dir)
    print(f"plot: {plot}", flush=True)
    print(f"report: {report}", flush=True)


if __name__ == "__main__":
    main()
