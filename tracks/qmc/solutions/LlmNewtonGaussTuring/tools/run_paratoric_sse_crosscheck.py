# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Compare ParaToric with direct SSE when dense ED is infeasible."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from run_paratoric_crosscheck import (
    CSV_FIELDS,
    OBSERVABLES,
    PARATORIC_COMMIT,
    PARATORIC_PATCH_SHA256,
    Case,
    block_means,
    executable_hash,
    parse_case,
    standard_error,
)


def run_paratoric(
    executable: Path, case: Case, mu: float, seed: int, thermal: int,
    samples: int, between: int, boost_lib: Path | None,
) -> tuple[list[dict[str, str]], list[str]]:
    environment = os.environ.copy()
    if boost_lib is not None:
        previous = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = (
            str(boost_lib) if not previous else f"{boost_lib}:{previous}"
        )
    command = [
        str(executable), case.lattice, str(case.size), f"{case.field:.17g}",
        f"{case.beta:.17g}", f"{mu:.17g}", str(seed), str(thermal),
        str(samples), str(between), "--no-ed",
    ]
    completed = subprocess.run(
        command, check=True, text=True, capture_output=True, env=environment
    )
    lines = completed.stdout.splitlines()
    try:
        header = next(index for index, line in enumerate(lines) if line.startswith("record,"))
    except StopIteration as error:
        raise ValueError("ParaToric output has no CSV header") from error
    rows = list(csv.DictReader(lines[header:]))
    if len(rows) != samples or any(row["record"] != "paratoric" for row in rows):
        raise ValueError(f"ParaToric returned {len(rows)} rows, expected {samples}")
    warnings = [line for line in lines[:header] if line.strip()]
    warnings.extend(line for line in completed.stderr.splitlines() if line.strip())
    return rows, warnings


def run_sse(
    executable: Path, case: Case, seed: int, start: str, thermal: int,
    bins: int, sweeps: int,
) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "sse.csv"
        command = [
            str(executable), case.lattice, str(case.size), f"{case.field:.17g}",
            f"{case.beta:.17g}", str(seed), start, str(thermal), str(bins),
            str(sweeps), str(output),
        ]
        subprocess.run(command, check=True, text=True, capture_output=True)
        with output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    if len(rows) != bins:
        raise ValueError(f"direct SSE returned {len(rows)} bins, expected {bins}")
    return rows


def summarize(
    chains: list[list[dict[str, str]]], observable: str,
) -> tuple[float, float, dict[str, object]]:
    series = [np.asarray([float(row[observable]) for row in chain]) for chain in chains]
    if len({len(values) for values in series}) != 1 or len(series[0]) < 40:
        raise ValueError("each chain must contain the same count of at least 40 samples")
    if not all(np.all(np.isfinite(values)) for values in series):
        raise ValueError(f"{observable} contains a non-finite value")
    base = max(1, len(series[0]) // 20)
    doubled = 2 * base
    base_error = standard_error(np.concatenate([block_means(x, base) for x in series]))
    doubled_error = standard_error(
        np.concatenate([block_means(x, doubled) for x in series])
    )
    means = np.asarray([values.mean() for values in series])
    chain_error = standard_error(means)
    error = max(base_error, doubled_error, chain_error, 1e-12)
    return float(means.mean()), error, {
        "base_block": float(base), "base_error": base_error,
        "doubled_error": doubled_error, "chain_error": chain_error,
        "block_error_ratio": doubled_error / max(base_error, 1e-300),
        "chain_means": means.tolist(),
    }


def independent_difference_z(first: np.ndarray, second: np.ndarray) -> float:
    if len(first) < 2 or len(second) < 2:
        return float("inf")
    variance = np.var(first, ddof=1) / len(first)
    variance += np.var(second, ddof=1) / len(second)
    difference = abs(float(np.mean(first) - np.mean(second)))
    if variance <= 0.0:
        return 0.0 if difference == 0.0 else float("inf")
    return difference / float(np.sqrt(variance))


def compare_case(
    pexe: Path, sexe: Path, case: Case, args: argparse.Namespace, seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, str]],
           list[dict[str, str]], dict[str, object]]:
    if args.chains < 4 or args.chains % 2:
        raise ValueError("an even chain count of at least four is required")
    pchains, schains, pwarnings = [], [], []
    for chain in range(args.chains):
        samples, warnings = run_paratoric(
            pexe, case, args.mu, seed + chain, args.p_thermal,
            args.p_samples, args.p_between, args.boost_lib,
        )
        pchains.append(samples)
        pwarnings.extend(warnings)
        start = "hot" if chain % 2 == 0 else "cold"
        schains.append(run_sse(
            sexe, case, seed + 500_000 + chain, start, args.sse_thermal,
            args.sse_bins, args.sse_sweeps,
        ))

    rows: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {
        "instance": case.instance, "lattice": case.lattice, "size": case.size,
        "field": case.field, "beta": case.beta, "mu": args.mu,
        "chains": args.chains, "paratoric_thermalization": args.p_thermal,
        "paratoric_samples_per_chain": args.p_samples,
        "paratoric_between_samples": args.p_between,
        "sse_thermalization": args.sse_thermal,
        "sse_bins_per_chain": args.sse_bins,
        "sse_sweeps_per_bin": args.sse_sweeps,
        "sse_initial_states": [
            "hot" if chain % 2 == 0 else "cold" for chain in range(args.chains)
        ],
        "paratoric_warnings": pwarnings,
        "paratoric_warning_gate": not pwarnings,
        "charge_pair_acceptance_bound": float(
            np.exp(-case.beta * (4 * args.mu - 2))
        ),
    }
    start_gates = []
    for observable in OBSERVABLES:
        pvalue, perror, pdiag = summarize(pchains, observable)
        svalue, serror, sdiag = summarize(schains, observable)
        chain_means = np.asarray(sdiag["chain_means"], dtype=float)
        hot_cold_z = independent_difference_z(chain_means[::2], chain_means[1::2])
        sdiag["hot_cold_z"] = hot_cold_z
        sdiag["hot_cold_gate"] = bool(hot_cold_z <= 5.0)
        start_gates.append(bool(sdiag["hot_cold_gate"]))
        combined = float(np.hypot(perror, serror))
        difference = abs(pvalue - svalue)
        budget = 5.0 * combined
        tag = "Agreement" if difference <= budget else "Disagreement"
        for method, value, uncertainty in (
            ("ParaToric-CTQMC", pvalue, perror),
            ("direct-SSE", svalue, serror),
        ):
            rows.append({
                "method": method, "observable": observable, "value": value,
                "uncertainty": uncertainty, "instance": case.instance,
                "tag": tag, "comparison_budget": budget,
                "absolute_difference": difference,
                "z_score": difference / max(combined, 1e-300),
            })
        diagnostics[observable] = {
            "absolute_difference": difference, "comparison_budget": budget,
            "tag": tag,
            "paratoric": {"value": pvalue, "uncertainty": perror, **pdiag},
            "direct_sse": {"value": svalue, "uncertainty": serror, **sdiag},
        }

    stars = np.concatenate([
        np.asarray([float(row["star_x"]) for row in chain]) for chain in pchains
    ])
    signs = np.concatenate([
        np.asarray([float(row["sign_avg"]) for row in chain]) for chain in schains
    ])
    diagnostics["max_star_defect"] = float(np.max(np.abs(1.0 - stars)))
    diagnostics["charge_sector_gate"] = diagnostics["max_star_defect"] <= 1e-12
    diagnostics["sse_sign_gate"] = bool(np.all(np.abs(signs - 1.0) <= 1e-12))
    diagnostics["sse_hot_cold_gate"] = all(start_gates)
    identity_chains = [[{
        "delta": str(float(row["component_total"]) - float(row["expansion_total"]))
    } for row in chain] for chain in schains]
    identity_value, identity_error, identity_diag = summarize(identity_chains, "delta")
    diagnostics["sse_component_identity"] = {
        "value": identity_value, "uncertainty": identity_error,
        "budget": 5.0 * identity_error,
        "gate": abs(identity_value) <= 5.0 * identity_error,
        **identity_diag,
    }
    if (not diagnostics["charge_sector_gate"]
            or not diagnostics["sse_sign_gate"]
            or not diagnostics["paratoric_warning_gate"]
            or not diagnostics["sse_component_identity"]["gate"]):
        for row in rows:
            row["tag"] = "Disagreement"

    praw = [{**row, "chain": str(i)} for i, chain in enumerate(pchains) for row in chain]
    sraw = [{**row, "chain": str(i)} for i, chain in enumerate(schains) for row in chain]
    return rows, praw, sraw, diagnostics


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_provenance() -> dict[str, object]:
    root = Path(__file__).resolve().parents[5]
    solution = Path("tracks/qmc/solutions/LlmNewtonGaussTuring")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True,
        capture_output=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", str(solution)],
        cwd=root, check=True, text=True, capture_output=True,
    ).stdout.strip().splitlines()
    return {"source_commit": commit, "source_dirty": bool(status), "source_status": status}


def write_outputs(
    output: Path, comparisons: list[dict[str, object]],
    praw: list[dict[str, str]], sraw: list[dict[str, str]],
    diagnostics: list[dict[str, object]], pexe: Path, sexe: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "cross-method-check.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(comparisons)
    write_csv(output / "paratoric-raw.csv", praw)
    write_csv(output / "sse-raw.csv", sraw)
    artifact_paths = {
        "cross-method-check.csv": output / "cross-method-check.csv",
        "paratoric-raw.csv": output / "paratoric-raw.csv",
        "sse-raw.csv": output / "sse-raw.csv",
    }
    metadata = {
        "paratoric_executable": str(pexe),
        "paratoric_executable_sha256": executable_hash(pexe),
        "sse_executable": str(sexe),
        "sse_executable_sha256": executable_hash(sexe),
        "driver_sha256": executable_hash(Path(__file__).resolve()),
        "paratoric_commit": PARATORIC_COMMIT,
        "paratoric_external_patch_sha256": PARATORIC_PATCH_SHA256,
        **source_provenance(),
        "uncertainty_rule": (
            "max(base-block, doubled-block, independent-chain SEM) per method; "
            "comparison budget = 5 combined SEM"
        ),
        "artifacts": {
            name: {"sha256": executable_hash(path), "bytes": path.stat().st_size}
            for name, path in artifact_paths.items()
        },
        "cases": diagnostics,
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paratoric-executable", type=Path, required=True)
    parser.add_argument("--sse-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--seed-base", type=int, default=149200)
    parser.add_argument("--mu", type=float, default=64.0)
    parser.add_argument("--p-thermal", type=int, default=5000)
    parser.add_argument("--p-samples", type=int, default=200)
    parser.add_argument("--p-between", type=int, default=20)
    parser.add_argument("--sse-thermal", type=int, default=5000)
    parser.add_argument("--sse-bins", type=int, default=200)
    parser.add_argument("--sse-sweeps", type=int, default=25)
    parser.add_argument("--boost-lib", type=Path)
    args = parser.parse_args()

    pexe = args.paratoric_executable.resolve()
    sexe = args.sse_executable.resolve()
    if not pexe.is_file() or not sexe.is_file():
        raise SystemExit("both ParaToric and direct-SSE executables must exist")
    comparisons, praw, sraw, diagnostics = [], [], [], []
    for index, case_text in enumerate(args.case):
        rows, p_raw, s_raw, diag = compare_case(
            pexe, sexe, parse_case(case_text), args, args.seed_base + index * 1000
        )
        comparisons.extend(rows)
        praw.extend(p_raw)
        sraw.extend(s_raw)
        diagnostics.append(diag)
    write_outputs(args.output, comparisons, praw, sraw, diagnostics, pexe, sexe)
    print(json.dumps({
        "cases": len(diagnostics), "output": str(args.output),
        "rows": len(comparisons),
    }))


if __name__ == "__main__":
    main()
