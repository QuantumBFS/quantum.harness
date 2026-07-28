# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Run the pinned ParaToric route against parity-resolved ED on small tori.

The comparison is deliberately energy-component based.  A nondegenerate
square-torus audit shows that ParaToric's periodic trace matches the full TFIM
thermal trace.  The even spin-flip sector is retained as a diagnostic to
prevent accidentally changing the finite-volume ensemble.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


OBSERVABLES = ("exchange_energy", "field_energy")
PARATORIC_COMMIT = "e7bc78446ba083aeeae1ada9c883fa03bf205890"
PARATORIC_PATCH_SHA256 = "3bd7a5231c38f048035f13f23bb20162b6f6e1f2264270dbeb61e2ce35073d30"
CSV_FIELDS = (
    "method",
    "observable",
    "value",
    "uncertainty",
    "instance",
    "tag",
    "comparison_budget",
    "absolute_difference",
    "z_score",
)


@dataclass(frozen=True)
class Case:
    lattice: str
    size: int
    field: float
    beta: float

    @property
    def instance(self) -> str:
        gauge = {
            "square": "square",
            "triangular": "honeycomb",
            "honeycomb": "triangular",
        }[self.lattice]
        return f"{self.lattice}->{gauge}-gauge,L={self.size},beta={self.beta:.17g},trace=full"


def parse_case(text: str) -> Case:
    parts = text.split(":")
    if len(parts) not in (3, 4) or parts[0] not in {"square", "triangular", "honeycomb"}:
        raise ValueError("case must be lattice:L:field[:beta]")
    size = int(parts[1])
    field = float(parts[2])
    beta = size / field if len(parts) == 3 else float(parts[3])
    if size < 2 or not np.isfinite(field) or field <= 0 or not np.isfinite(beta) or beta <= 0:
        raise ValueError("case size, field, and beta must be positive and finite")
    return Case(parts[0], size, field, beta)


def executable_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_chain(
    executable: Path,
    case: Case,
    mu: float,
    seed: int,
    thermal: int,
    samples: int,
    between: int,
    boost_lib: Path | None,
) -> list[dict[str, str]]:
    environment = os.environ.copy()
    if boost_lib is not None:
        old_path = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = (
            str(boost_lib) if not old_path else f"{boost_lib}:{old_path}"
        )
    command = [
        str(executable),
        case.lattice,
        str(case.size),
        f"{case.field:.17g}",
        f"{case.beta:.17g}",
        f"{mu:.17g}",
        str(seed),
        str(thermal),
        str(samples),
        str(between),
    ]
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        env=environment,
    )
    lines = completed.stdout.splitlines()
    try:
        header = next(index for index, line in enumerate(lines) if line.startswith("record,"))
    except StopIteration as error:
        raise ValueError("ParaToric output has no CSV header") from error
    warnings = [line for line in lines[:header] if line.strip()]
    warnings.extend(line for line in completed.stderr.splitlines() if line.strip())
    if warnings:
        raise ValueError(f"ParaToric warning gate failed: {warnings}")
    rows = list(csv.DictReader(lines[header:]))
    expected = 2 + samples
    if len(rows) != expected or rows[0]["record"] != "exact_full":
        raise ValueError(f"ParaToric returned {len(rows)} rows, expected {expected}")
    return rows


def block_means(values: np.ndarray, block_size: int) -> np.ndarray:
    usable = (len(values) // block_size) * block_size
    if usable < block_size:
        raise ValueError("not enough samples for one uncertainty block")
    return values[:usable].reshape(-1, block_size).mean(axis=1)


def standard_error(values: np.ndarray) -> float:
    if len(values) < 2:
        raise ValueError("at least two independent blocks are required")
    return float(np.std(values, ddof=1) / np.sqrt(len(values)))


def summarize_chains(
    chains: list[list[dict[str, str]]],
    observable: str,
) -> tuple[float, float, dict[str, float]]:
    samples = [np.asarray([float(row[observable]) for row in chain[2:]]) for chain in chains]
    if len({len(values) for values in samples}) != 1:
        raise ValueError("independent chains have different sample counts")
    sample_count = len(samples[0])
    base = max(1, sample_count // 20)
    doubled = 2 * base
    base_blocks = np.concatenate([block_means(values, base) for values in samples])
    doubled_blocks = np.concatenate([block_means(values, doubled) for values in samples])
    chain_means = np.asarray([values.mean() for values in samples])
    mean = float(chain_means.mean())
    base_error = standard_error(base_blocks)
    doubled_error = standard_error(doubled_blocks)
    chain_error = standard_error(chain_means)
    error = max(base_error, doubled_error, chain_error, 1e-12)
    return mean, error, {
        "base_block": float(base),
        "base_error": base_error,
        "doubled_error": doubled_error,
        "chain_error": chain_error,
        "block_error_ratio": doubled_error / max(base_error, 1e-300),
    }


def compare_case(
    executable: Path,
    case: Case,
    chains: int,
    seed_base: int,
    mu: float,
    thermal: int,
    samples: int,
    between: int,
    boost_lib: Path | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if chains < 2:
        raise ValueError("at least two independent chains are required")
    chain_rows = []
    for chain_index in range(chains):
        seed = seed_base + chain_index
        if seed == 0:
            seed += 1
        chain_rows.append(
            run_chain(executable, case, mu, seed, thermal, samples, between, boost_lib)
        )
    exact = chain_rows[0][0]
    exact_even = chain_rows[0][1]
    for rows in chain_rows[1:]:
        for column in ("exchange_energy", "field_energy", "even_partition_fraction"):
            if not np.isclose(float(rows[0][column]), float(exact[column]), rtol=0, atol=1e-12):
                raise ValueError("independent chains disagree on exact ED metadata")

    exact_values = {
        "exchange_energy": float(exact["exchange_energy"]),
        "field_energy": float(exact["field_energy"]),
    }
    rows: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {
        "instance": case.instance,
        "lattice": case.lattice,
        "size": case.size,
        "field": case.field,
        "beta": case.beta,
        "mu": mu,
        "even_partition_fraction": float(exact["even_partition_fraction"]),
        "even_sector_exchange": float(exact_even["exchange_energy"]),
        "even_sector_field": float(exact_even["field_energy"]),
        "sector_shift_exchange": float(exact_even["exchange_energy"]) - exact_values["exchange_energy"],
        "sector_shift_field": float(exact_even["field_energy"]) - exact_values["field_energy"],
        "charge_pair_acceptance_bound": float(np.exp(-case.beta * (4 * mu - 2))),
        "chains": chains,
        "samples_per_chain": samples,
        "thermalization": thermal,
        "between_samples": between,
    }
    for observable in OBSERVABLES:
        mean, uncertainty, uncertainty_diag = summarize_chains(chain_rows, observable)
        difference = abs(mean - exact_values[observable])
        budget = 5.0 * np.hypot(uncertainty, 1e-10)
        tag = "Agreement" if difference <= budget else "Disagreement"
        z_score = difference / max(np.hypot(uncertainty, 1e-10), 1e-300)
        rows.extend(
            [
                {
                    "method": "ED-full",
                    "observable": observable,
                    "value": exact_values[observable],
                    "uncertainty": 1e-10,
                    "instance": case.instance,
                    "tag": tag,
                    "comparison_budget": budget,
                    "absolute_difference": difference,
                    "z_score": z_score,
                },
                {
                    "method": "ParaToric-CTQMC",
                    "observable": observable,
                    "value": mean,
                    "uncertainty": uncertainty,
                    "instance": case.instance,
                    "tag": tag,
                    "comparison_budget": budget,
                    "absolute_difference": difference,
                    "z_score": z_score,
                },
            ]
        )
        diagnostics[observable] = {"value": mean, "uncertainty": uncertainty, **uncertainty_diag}

    star_values = np.concatenate(
        [np.asarray([float(row["star_x"]) for row in chain[2:]]) for chain in chain_rows]
    )
    diagnostics["max_star_defect"] = float(np.max(np.abs(1.0 - star_values)))
    diagnostics["charge_sector_gate"] = bool(diagnostics["max_star_defect"] <= 1e-12)
    if not diagnostics["charge_sector_gate"]:
        for row in rows:
            row["tag"] = "Disagreement"
    return rows, [dict(row) for chain in chain_rows for row in chain], diagnostics


def write_outputs(
    output: Path,
    rows: list[dict[str, object]],
    raw_rows: list[dict[str, str]],
    diagnostics: list[dict[str, object]],
    executable: Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "cross-method-check.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if raw_rows:
        raw_fields = list(raw_rows[0])
        with (output / "paratoric-raw.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=raw_fields)
            writer.writeheader()
            writer.writerows(raw_rows)
    metadata = {
        "executable": str(executable),
        "executable_sha256": executable_hash(executable),
        "driver_sha256": executable_hash(Path(__file__).resolve()),
        "paratoric_commit": PARATORIC_COMMIT,
        "paratoric_external_patch_sha256": PARATORIC_PATCH_SHA256,
        "uncertainty_rule": "max(base-block, doubled-block, independent-chain SEM); comparison budget = 5 combined SEM",
        "ed_uncertainty": 1e-10,
        "cases": diagnostics,
        "artifacts": {
            "cross-method-check.csv": {
                "sha256": executable_hash(output / "cross-method-check.csv"),
                "bytes": (output / "cross-method-check.csv").stat().st_size,
            },
            "paratoric-raw.csv": {
                "sha256": executable_hash(output / "paratoric-raw.csv"),
                "bytes": (output / "paratoric-raw.csv").stat().st_size,
            },
        },
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True, help="lattice:L:field[:beta]")
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--seed-base", type=int, default=148200)
    parser.add_argument("--mu", type=float, default=64.0)
    parser.add_argument("--thermal", type=int, default=5000)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--between", type=int, default=20)
    parser.add_argument("--boost-lib", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"missing executable: {executable}")
    cases = [parse_case(text) for text in args.case]
    comparison_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, str]] = []
    diagnostics: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        rows, raw, case_diagnostics = compare_case(
            executable,
            case,
            args.chains,
            args.seed_base + index * 1000,
            args.mu,
            args.thermal,
            args.samples,
            args.between,
            args.boost_lib,
        )
        comparison_rows.extend(rows)
        raw_rows.extend(raw)
        diagnostics.append(case_diagnostics)
    write_outputs(args.output, comparison_rows, raw_rows, diagnostics, executable)
    print(json.dumps({"cases": len(cases), "output": str(args.output), "rows": len(comparison_rows)}))


if __name__ == "__main__":
    main()
