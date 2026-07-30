from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble the paper-level VMCRG report")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--jacobian", type=Path, required=True)
    parser.add_argument("--autocorrelation", type=Path, required=True)
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _round_number(path: Path) -> int:
    match = re.fullmatch(r"rg(\d+)", path.name)
    if match is None:
        raise ValueError(f"invalid RG directory name: {path.name}")
    return int(match.group(1))


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    jacobian_path = args.jacobian.resolve()
    autocorrelation_path = args.autocorrelation.resolve()
    output = (args.output or root / "paper_report.json").resolve()
    figure_output = output.with_name("paper_results.png")
    if output.exists() or figure_output.exists():
        raise FileExistsError(f"refusing to overwrite paper report: {output}")

    rg_directories = sorted(
        (path for path in root.glob("rg*") if path.is_dir()), key=_round_number
    )
    if len(rg_directories) < 2:
        raise ValueError("at least two RG rounds are required for a paper report")
    rounds = []
    for directory in rg_directories:
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        convergence = json.loads(
            (directory / "convergence.json").read_text(encoding="utf-8")
        )
        validation_path = directory / "frozen_validation.json"
        validation = (
            json.loads(validation_path.read_text(encoding="utf-8"))
            if validation_path.exists()
            else None
        )
        rounds.append(
            {
                "round": _round_number(directory),
                "directory": str(directory),
                "nearest_neighbor_coupling": float(
                    summary["final_renormalized_couplings"][0]
                ),
                "all_couplings": summary["final_renormalized_couplings"],
                "max_abs_coupling_drift_90_to_100_percent": convergence[
                    "max_abs_coupling_drift_90_to_100_percent"
                ],
                "late_statistics_status": convergence["late_statistics_status"],
                "covariance_status": convergence["covariance_status"],
                "frozen_validation_max_abs_z": (
                    validation["max_abs_z"] if validation is not None else None
                ),
            }
        )

    jacobian = json.loads(jacobian_path.read_text(encoding="utf-8"))
    autocorrelation = json.loads(autocorrelation_path.read_text(encoding="utf-8"))
    frozen_z_threshold = 3.0
    all_frozen_validations_pass = all(
        item["frozen_validation_max_abs_z"] is not None
        and item["frozen_validation_max_abs_z"] <= frozen_z_threshold
        for item in rounds
    )
    all_convergence_statistics_available = all(
        item["late_statistics_status"] == "ESTIMATED_FROM_LATE_WINDOW_CHUNKS"
        for item in rounds
    )
    paper_even = 3.045
    paper_odd = 7.858
    even_interval = jacobian["even"]["bootstrap"]
    odd_interval = jacobian["odd"]["bootstrap"]
    paper_even_in_ci95 = bool(
        even_interval["ci95_low"] <= paper_even <= even_interval["ci95_high"]
    )
    paper_odd_in_ci95 = bool(
        odd_interval["ci95_low"] <= paper_odd <= odd_interval["ci95_high"]
    )
    acceptance_gates = {
        "criteria_source": "implementation_acceptance_criteria_not_paper_published",
        "all_convergence_statistics_available": all_convergence_statistics_available,
        "frozen_uniform_target_max_abs_z_threshold": frozen_z_threshold,
        "all_frozen_validations_pass": all_frozen_validations_pass,
        "jacobian_bootstrap_numerically_stable": (
            jacobian["status"] == "NUMERICALLY_STABLE"
        ),
        "paper_L45_even_eigenvalue_inside_own_ci95": paper_even_in_ci95,
        "paper_L45_odd_eigenvalue_inside_own_ci95": paper_odd_in_ci95,
        "biased_autocorrelation_reduction_pass": (
            autocorrelation["status"] == "PASS"
        ),
    }
    all_acceptance_gates_pass = all(
        value
        for key, value in acceptance_gates.items()
        if key not in {
            "criteria_source",
            "frozen_uniform_target_max_abs_z_threshold",
        }
    )
    acceptance_gates["all_pass"] = all_acceptance_gates_pass
    if args.mode == "smoke":
        status = "SMOKE_PIPELINE_COMPLETED_NOT_A_SCIENTIFIC_RESULT"
    elif all_acceptance_gates_pass:
        status = "FORMAL_PUBLISHED_13_PLUS_5_WORKFLOW_GATES_PASSED"
    else:
        status = "FORMAL_PIPELINE_COMPLETED_ACCEPTANCE_GATES_FAILED"
    report = {
        "status": status,
        "mode": args.mode,
        "paper": "Wu and Carrasquilla, Phys. Rev. Lett. 119, 220602 (2017)",
        "scope": "published_13_even_and_5_odd_operator_workflow",
        "excluded_claim": "original_26_to_13_strict_reproduction",
        "rg_rounds": rounds,
        "jacobian_file": str(jacobian_path),
        "jacobian_status": jacobian["status"],
        "lambda_even": jacobian["even"]["leading_eigenvalue"],
        "lambda_odd": jacobian["odd"]["leading_eigenvalue"],
        "critical_exponents": jacobian["critical_exponents"],
        "autocorrelation_file": str(autocorrelation_path),
        "autocorrelation_status": autocorrelation["status"],
        "biased_tau_mean": autocorrelation["biased_tau_mean"],
        "unbiased_tau_mean": autocorrelation["unbiased_tau_mean"],
        "acceptance_gates": acceptance_gates,
        "paper_reference": {
            "biased_L45_lambda_even": paper_even,
            "biased_L45_lambda_odd": paper_odd,
            "exact_lambda_even": 3.0,
            "exact_lambda_odd": float(3.0 ** (15.0 / 8.0)),
        },
        "claim_boundary": (
            "Formal mode means the predeclared computation completed. Agreement with the "
            "paper must still be assessed from confidence intervals and documented unknowns."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    autocorrelation_arrays = np.load(autocorrelation_path.with_suffix(".npz"))
    biased_acf = autocorrelation_arrays["biased_acf"]
    unbiased_acf = autocorrelation_arrays["unbiased_acf"]
    lags = np.arange(biased_acf.shape[1])
    biased_mean = biased_acf.mean(axis=0)
    unbiased_mean = unbiased_acf.mean(axis=0)
    biased_se = biased_acf.std(axis=0, ddof=1) / np.sqrt(biased_acf.shape[0])
    unbiased_se = unbiased_acf.std(axis=0, ddof=1) / np.sqrt(unbiased_acf.shape[0])

    figure, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    axes[0].plot(
        [item["round"] for item in rounds],
        [item["nearest_neighbor_coupling"] for item in rounds],
        marker="o",
    )
    axes[0].set_xlabel("RG iteration")
    axes[0].set_ylabel("renormalized nearest-neighbor coupling")
    axes[0].set_title("RG flow")

    positions = np.arange(2)
    measured = [jacobian["even"]["leading_eigenvalue"], jacobian["odd"]["leading_eigenvalue"]]
    paper_values = [3.045, 7.858]
    axes[1].bar(positions - 0.18, measured, width=0.36, label="this run")
    axes[1].bar(positions + 0.18, paper_values, width=0.36, label="paper L=45 biased")
    axes[1].set_xticks(positions, ["even", "odd"])
    axes[1].set_ylabel("leading eigenvalue")
    axes[1].set_title("RG Jacobian")
    axes[1].legend()

    axes[2].plot(lags, biased_mean, label="biased")
    axes[2].fill_between(lags, biased_mean - biased_se, biased_mean + biased_se, alpha=0.2)
    axes[2].plot(lags, unbiased_mean, label="unbiased")
    axes[2].fill_between(
        lags, unbiased_mean - unbiased_se, unbiased_mean + unbiased_se, alpha=0.2
    )
    axes[2].axhline(0.0, color="black", linewidth=0.6)
    axes[2].set_xlabel("lag (measurements)")
    axes[2].set_ylabel("connected autocorrelation")
    axes[2].set_title("Critical slowing down")
    axes[2].legend()
    figure.tight_layout()
    figure.savefig(figure_output, dpi=180)
    plt.close(figure)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
