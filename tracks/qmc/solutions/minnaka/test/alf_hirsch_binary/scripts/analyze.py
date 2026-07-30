#!/usr/bin/env python3
"""Merge six independent ALF chains and write the binary-Hirsch result summary."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALF_ROOT = PROJECT_ROOT / "ALF"
PRODUCTION_ROOT = PROJECT_ROOT / "run" / "binary" / "production"
RESULTS_ROOT = PROJECT_ROOT / "results"
OBSERVABLE_FILES = {
    "total_energy": "Ener_scal",
    "kinetic_energy": "Kin_scal",
    "interaction_energy": "Pot_scal",
    "particle_number": "Part_scal",
}
EXPECTED_CHAINS = 6
EXPECTED_BINS_PER_CHAIN = 7
SKIP_BINS_PER_CHAIN = 1
NSWEEP = 2000
N_SITES = 16
N_TIME_SLICES = 420
REFERENCE_ENERGY = -13.618
REFERENCE_ERROR = 0.002
EXACT_ENERGY = -13.6224

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
SCALAR_LINE = re.compile(
    rf"^\s*(\d+)\s+\(\s*({FLOAT})\s*,\s*({FLOAT})\s*\)\s+({FLOAT})\s*$"
)


def as_float(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def parse_scalar_file(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = SCALAR_LINE.match(line)
        if match is None:
            raise RuntimeError(f"cannot parse {path}:{line_number}: {line}")
        n_values = int(match.group(1))
        if n_values != 2:
            raise RuntimeError(f"unexpected scalar width {n_values} in {path}")
        observable = as_float(match.group(2))
        imaginary = as_float(match.group(3))
        sign = as_float(match.group(4))
        if abs(imaginary) > 1.0e-12:
            raise RuntimeError(f"non-real scalar observable in {path}")
        if not math.isfinite(observable) or not math.isfinite(sign):
            raise RuntimeError(f"non-finite scalar observable in {path}")
        rows.append((observable, sign))
    return rows


def jackknife_ratio(
    weighted_observable: Iterable[float], signs: Iterable[float]
) -> tuple[float, float]:
    observable = list(weighted_observable)
    phase = list(signs)
    if len(observable) != len(phase) or len(observable) < 2:
        raise RuntimeError("jackknife requires matching samples and at least two bins")
    observable_sum = sum(observable)
    phase_sum = sum(phase)
    if abs(phase_sum) < 1.0e-15:
        raise RuntimeError("mean sign vanishes")
    leave_one_out = []
    for value, sign in zip(observable, phase):
        denominator = phase_sum - sign
        if abs(denominator) < 1.0e-15:
            raise RuntimeError("jackknife leave-one-out sign vanishes")
        leave_one_out.append((observable_sum - value) / denominator)
    center = sum(leave_one_out) / len(leave_one_out)
    # Match ALF 2.4 ERRORS::ERRCALC_JS_F exactly.  ALF computes the
    # population error of the leave-one-out values and then multiplies it by
    # the number of bins, which reduces to the expression below.
    squared_deviations = sum(
        (value - center) ** 2 for value in leave_one_out
    )
    return center, math.sqrt(max(0.0, squared_deviations))


def jackknife_mean(values: Iterable[float]) -> tuple[float, float]:
    samples = list(values)
    if len(samples) < 2:
        raise RuntimeError("jackknife requires at least two bins")
    total = sum(samples)
    leave_one_out = [
        (total - value) / (len(samples) - 1) for value in samples
    ]
    center = sum(leave_one_out) / len(leave_one_out)
    error = math.sqrt(
        sum((value - center) ** 2 for value in leave_one_out)
    )
    return center, error


def parse_info_scalar(info: str, label: str) -> float:
    match = re.search(
        rf"(?m)^\s*{re.escape(label)}\s*:\s*({FLOAT})",
        info,
    )
    if match is None:
        raise RuntimeError(f"missing '{label}' in info")
    return as_float(match.group(1))


def parse_two_info_scalars(info: str, label: str) -> tuple[float, float]:
    match = re.search(
        rf"(?m)^\s*{re.escape(label)}\s*:\s*({FLOAT})\s+({FLOAT})",
        info,
    )
    if match is None:
        raise RuntimeError(f"missing '{label}' in info")
    return as_float(match.group(1)), as_float(match.group(2))


def parse_wall_seconds(log: str) -> float:
    match = re.search(r"(?m)^WALL_SECONDS=([0-9.]+)\s*$", log)
    if match is None:
        raise RuntimeError("missing WALL_SECONDS in run log")
    return float(match.group(1))


def parse_seed(info: str) -> int:
    match = re.search(
        r"(?m)^\s*No initial configuration,\s*Seed_in\s+(\d+)\s*$",
        info,
    )
    if match is None:
        raise RuntimeError("missing initial seed in info")
    return int(match.group(1))


def command_output(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return completed.stdout.strip()


def oneapi_version(command: str) -> str:
    script = (
        "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1; "
        f"{command} --version 2>/dev/null | head -1"
    )
    return command_output(["bash", "-lc", script])


def validate_configuration(info: str, chain: int) -> float:
    required = (
        "HS transformation: binary Hirsch spin",
        "Projective version",
    )
    for marker in required:
        if marker not in info:
            raise RuntimeError(f"chain {chain}: missing info marker '{marker}'")
    expected = {
        "L1": 4.0,
        "L2": 4.0,
        "# of particles": 8.0,
        "Theta": 10.0,
        "Tau_max": 1.0,
        "Ham_U": 4.0,
        "Sweeps": float(NSWEEP),
        "Bins": float(EXPECTED_BINS_PER_CHAIN),
        "Number of mpi-processes": 1.0,
    }
    for label, target in expected.items():
        value = parse_info_scalar(info, label)
        if value != target:
            raise RuntimeError(
                f"chain {chain}: {label}={value}, expected {target}"
            )
    dtau_match = re.search(
        rf"(?m)^\s*dtau,Ltrot_eff\s*:\s*({FLOAT})\s+(\d+)",
        info,
    )
    if dtau_match is None:
        raise RuntimeError(f"chain {chain}: missing dtau,Ltrot_eff")
    if abs(as_float(dtau_match.group(1)) - 0.05) > 1.0e-15:
        raise RuntimeError(f"chain {chain}: unexpected Dtau")
    if int(dtau_match.group(2)) != N_TIME_SLICES:
        raise RuntimeError(f"chain {chain}: unexpected Ltrot")
    lam = parse_info_scalar(info, "Hirsch lambda")
    if abs(math.cosh(lam) - math.exp(0.05 * 4.0 / 2.0)) > 2.0e-14:
        raise RuntimeError(f"chain {chain}: inconsistent Hirsch lambda")
    return lam


def validate_binary_fields(path: Path) -> None:
    values = [int(value) for value in path.read_text(encoding="utf-8").split()]
    if len(values) <= 2:
        raise RuntimeError(f"empty field configuration in {path}")
    fields = set(values[2:])
    if fields != {-1, 1}:
        raise RuntimeError(f"non-binary field values {sorted(fields)} in {path}")


def run_alf_analysis_crosscheck(
    observables: dict[str, dict[str, float]]
) -> tuple[dict[str, dict[str, float]], str]:
    analysis_executable = (
        PROJECT_ROOT / "run" / "binary" / "bin" / "ana.binary.out"
    )
    filenames = list(OBSERVABLE_FILES.values())
    with tempfile.TemporaryDirectory(prefix="alf-analysis-check-") as tmp:
        tmp_path = Path(tmp)
        parameters = (
            PRODUCTION_ROOT / "chain_0" / "parameters"
        ).read_text(encoding="utf-8")
        parameters, replacements = re.subn(
            r"(?mi)^(\s*n_skip\s*=\s*)[^!\n]*",
            rf"\g<1>{EXPECTED_CHAINS} ",
            parameters,
            count=1,
        )
        if replacements != 1:
            raise RuntimeError("could not set n_skip for ALF cross-check")
        (tmp_path / "parameters").write_text(
            parameters, encoding="utf-8"
        )
        for filename in filenames:
            per_chain = [
                (
                    PRODUCTION_ROOT / f"chain_{chain}" / filename
                ).read_text(encoding="utf-8").splitlines()
                for chain in range(EXPECTED_CHAINS)
            ]
            ordered = [
                per_chain[chain][bin_index]
                for bin_index in range(EXPECTED_BINS_PER_CHAIN)
                for chain in range(EXPECTED_CHAINS)
            ]
            (tmp_path / filename).write_text(
                "\n".join(ordered) + "\n", encoding="utf-8"
            )
        shell = (
            "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1; "
            'exec "$@"'
        )
        completed = subprocess.run(
            [
                "bash",
                "-lc",
                shell,
                "bash",
                str(analysis_executable),
                *filenames,
            ],
            cwd=tmp_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        crosscheck = {}
        details = [completed.stdout.rstrip()]
        for observable, filename in OBSERVABLE_FILES.items():
            output = (tmp_path / f"{filename}J").read_text(
                encoding="utf-8"
            )
            details.append(f"\n===== {filename}J =====\n{output.rstrip()}")
            match = re.search(
                rf"(?m)^\s*1\s+({FLOAT})\s+({FLOAT})\s*$",
                output,
            )
            if match is None:
                raise RuntimeError(f"cannot parse ALF analysis for {filename}")
            mean = as_float(match.group(1))
            error = as_float(match.group(2))
            expected = observables[observable]
            if abs(mean - expected["mean"]) > 5.0e-12:
                raise RuntimeError(
                    f"ALF/Python mean mismatch for {observable}"
                )
            if abs(error - expected["error"]) > 5.0e-12:
                raise RuntimeError(
                    f"ALF/Python error mismatch for {observable}"
                )
            crosscheck[observable] = {"mean": mean, "error": error}
        return crosscheck, "\n".join(details) + "\n"


def collect_data() -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    diagnostics = []
    lambdas = []
    chain_wall_seconds = []
    for chain in range(EXPECTED_CHAINS):
        run_dir = PRODUCTION_ROOT / f"chain_{chain}"
        observable_data = {
            name: parse_scalar_file(run_dir / filename)
            for name, filename in OBSERVABLE_FILES.items()
        }
        lengths = {len(values) for values in observable_data.values()}
        if lengths != {EXPECTED_BINS_PER_CHAIN}:
            raise RuntimeError(
                f"chain {chain}: expected {EXPECTED_BINS_PER_CHAIN} complete bins, "
                f"found {sorted(lengths)}"
            )
        info = (run_dir / "info").read_text(encoding="utf-8")
        lambdas.append(validate_configuration(info, chain))
        validate_binary_fields(run_dir / "confout_0")
        green_mean, green_max = parse_two_info_scalars(
            info, "Precision Green  Mean, Max"
        )
        diagnostics.append(
            {
                "chain": chain,
                "seed": parse_seed(info),
                "green_precision_mean": green_mean,
                "green_precision_max": green_max,
                "phase_precision_max": parse_info_scalar(
                    info, "Precision Phase, Max"
                ),
                "acceptance": parse_info_scalar(info, "Acceptance"),
                "effective_acceptance": parse_info_scalar(
                    info, "Effective Acceptance"
                ),
                "cpu_seconds": parse_info_scalar(info, "CPU Time"),
            }
        )
        run_log = (run_dir / "run.log").read_text(encoding="utf-8")
        chain_wall_seconds.append(parse_wall_seconds(run_log))
        for bin_index in range(EXPECTED_BINS_PER_CHAIN):
            row: dict[str, object] = {
                "chain": chain,
                "bin": bin_index + 1,
                "included": bin_index >= SKIP_BINS_PER_CHAIN,
            }
            signs = []
            for observable, values in observable_data.items():
                row[observable] = values[bin_index][0]
                signs.append(values[bin_index][1])
            if max(signs) - min(signs) > 1.0e-12:
                raise RuntimeError(f"chain {chain}, bin {bin_index + 1}: sign mismatch")
            row["sign"] = signs[0]
            energy_residual = abs(
                float(row["total_energy"])
                - float(row["kinetic_energy"])
                - float(row["interaction_energy"])
            )
            if energy_residual > 1.0e-10:
                raise RuntimeError(
                    f"chain {chain}, bin {bin_index + 1}: "
                    f"E-(K+V)={energy_residual}"
                )
            if abs(float(row["particle_number"]) - 16.0) > 1.0e-10:
                raise RuntimeError(
                    f"chain {chain}, bin {bin_index + 1}: "
                    f"particle number is {row['particle_number']}"
                )
            rows.append(row)
    if max(lambdas) - min(lambdas) > 1.0e-15:
        raise RuntimeError("inconsistent Hirsch lambda across chains")
    return rows, {
        "per_chain": diagnostics,
        "hirsch_lambda": lambdas[0],
        "chain_wall_seconds": chain_wall_seconds,
    }


def write_csv(rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "chain",
        "bin",
        "included",
        "total_energy",
        "kinetic_energy",
        "interaction_energy",
        "particle_number",
        "sign",
    ]
    with (RESULTS_ROOT / "energy_bins.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows, raw_diagnostics = collect_data()
    included = [row for row in rows if bool(row["included"])]
    signs = [float(row["sign"]) for row in included]
    observables = {}
    for observable in OBSERVABLE_FILES:
        values = [float(row[observable]) for row in included]
        mean, error = jackknife_ratio(values, signs)
        observables[observable] = {"mean": mean, "error": error}
    mean_sign, sign_error = jackknife_mean(signs)
    alf_crosscheck, alf_crosscheck_text = run_alf_analysis_crosscheck(
        observables
    )

    master_log = (
        PRODUCTION_ROOT / "production.master.log"
    ).read_text(encoding="utf-8")
    master_status_match = re.search(r"(?m)^EXIT_STATUS=(\d+)\s*$", master_log)
    if master_status_match is None or int(master_status_match.group(1)) != 0:
        raise RuntimeError("production runner did not finish successfully")
    wall_seconds = parse_wall_seconds(master_log)
    aggregate_sweeps = (
        EXPECTED_CHAINS * EXPECTED_BINS_PER_CHAIN * NSWEEP
    )
    aggregate_field_updates = (
        aggregate_sweeps * 2 * N_SITES * N_TIME_SLICES
    )

    per_chain = list(raw_diagnostics["per_chain"])
    diagnostics = {
        "mean_sign": mean_sign,
        "mean_sign_error": sign_error,
        "acceptance_mean": sum(
            float(item["acceptance"]) for item in per_chain
        )
        / len(per_chain),
        "effective_acceptance_mean": sum(
            float(item["effective_acceptance"]) for item in per_chain
        )
        / len(per_chain),
        "green_precision_mean": sum(
            float(item["green_precision_mean"]) for item in per_chain
        )
        / len(per_chain),
        "green_precision_max": max(
            float(item["green_precision_max"]) for item in per_chain
        ),
        "phase_precision_max": max(
            float(item["phase_precision_max"]) for item in per_chain
        ),
        "cpu_seconds_sum": sum(
            float(item["cpu_seconds"]) for item in per_chain
        ),
        "wall_seconds": wall_seconds,
        "chain_wall_seconds": raw_diagnostics["chain_wall_seconds"],
        "aggregate_field_updates": aggregate_field_updates,
        "field_updates_per_second": aggregate_field_updates / wall_seconds,
        "per_chain": per_chain,
    }

    energy = observables["total_energy"]["mean"]
    energy_error = observables["total_energy"]["error"]
    uncertainty_limit = 2.0 * math.sqrt(
        energy_error**2 + REFERENCE_ERROR**2
    )
    criteria = {
        "energy_error_at_most_0.004": energy_error <= 0.004,
        "matches_alf_reference": abs(energy - REFERENCE_ENERGY)
        <= uncertainty_limit,
        "mean_sign_is_one": abs(mean_sign - 1.0) <= 1.0e-12,
        "complete_raw_bins": len(rows) == 42,
        "distinct_chain_seeds": len(
            {int(item["seed"]) for item in per_chain}
        )
        == EXPECTED_CHAINS,
        "all_finite": all(
            math.isfinite(float(row[name]))
            for row in rows
            for name in (*OBSERVABLE_FILES, "sign")
        ),
    }
    criteria["accepted"] = all(criteria.values())
    iid_required_included_bins = math.ceil(
        len(included) * (energy_error / 0.004) ** 2
    )
    iid_required_retained_per_chain = math.ceil(
        iid_required_included_bins / EXPECTED_CHAINS
    )
    iid_fresh_bins_per_chain = (
        iid_required_retained_per_chain + SKIP_BINS_PER_CHAIN
    )
    statistics_extension = {
        "assumption": "inverse-square error scaling with independent bins",
        "estimated_required_included_bins": iid_required_included_bins,
        "estimated_required_bins_per_chain_for_fresh_run": (
            iid_fresh_bins_per_chain
        ),
        "estimated_aggregate_sweeps_for_fresh_run": (
            EXPECTED_CHAINS
            * iid_fresh_bins_per_chain
            * NSWEEP
        ),
        "estimated_local_wall_seconds_for_fresh_run": (
            wall_seconds
            * iid_fresh_bins_per_chain
            / EXPECTED_BINS_PER_CHAIN
        ),
    }

    source_diff = command_output(
        ["git", "diff", "--binary"], cwd=ALF_ROOT
    ).encode("utf-8")
    patch_path = PROJECT_ROOT / "patches" / "hirsch-binary.patch"
    patch_sha256 = (
        hashlib.sha256(patch_path.read_bytes()).hexdigest()
        if patch_path.is_file()
        else None
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "physical_setup": {
            "model": "repulsive Hubbard",
            "lattice": "4x4 square",
            "boundary_conditions": "periodic in both directions",
            "t": 1.0,
            "U": 4.0,
            "N_up": 8,
            "N_down": 8,
            "projector": True,
            "Theta": 10.0,
            "Beta_measurement_window": 1.0,
            "Dtau": 0.05,
            "Ltrot": N_TIME_SLICES,
            "symmetric_trotter": True,
            "trial_state": "stock real noninteracting determinant, Delta=0.01",
            "hs_transformation": "binary Hirsch spin",
            "hirsch_lambda": raw_diagnostics["hirsch_lambda"],
        },
        "sampling": {
            "chains": EXPECTED_CHAINS,
            "mpi_ranks_per_chain": 1,
            "threads_per_rank": 1,
            "bins_per_chain": EXPECTED_BINS_PER_CHAIN,
            "sweeps_per_bin": NSWEEP,
            "raw_bins": len(rows),
            "skipped_bins_per_chain": SKIP_BINS_PER_CHAIN,
            "included_bins": len(included),
            "aggregate_sweeps": aggregate_sweeps,
        },
        "observables": observables,
        "diagnostics": diagnostics,
        "comparison": {
            "alf_reference_energy": REFERENCE_ENERGY,
            "alf_reference_error": REFERENCE_ERROR,
            "difference_from_alf_reference": energy - REFERENCE_ENERGY,
            "combined_two_sigma_limit": uncertainty_limit,
            "exact_finite_size_energy": EXACT_ENERGY,
            "difference_from_exact": energy - EXACT_ENERGY,
        },
        "acceptance_criteria": criteria,
        "alf_analysis_crosscheck": alf_crosscheck,
        "statistics_extension_estimate": statistics_extension,
        "provenance": {
            "alf_repository": "https://github.com/ALF-QMC/ALF.git",
            "alf_commit": command_output(
                ["git", "rev-parse", "HEAD"], cwd=ALF_ROOT
            ),
            "alf_branch": command_output(
                ["git", "branch", "--show-current"], cwd=ALF_ROOT
            ),
            "source_diff_sha256": hashlib.sha256(source_diff).hexdigest(),
            "patch_sha256": patch_sha256,
            "binary_sha256": hashlib.sha256(
                (
                    PROJECT_ROOT
                    / "run"
                    / "binary"
                    / "bin"
                    / "ALF.binary.out"
                ).read_bytes()
            ).hexdigest(),
            "analysis_binary_sha256": hashlib.sha256(
                (
                    PROJECT_ROOT
                    / "run"
                    / "binary"
                    / "bin"
                    / "ana.binary.out"
                ).read_bytes()
            ).hexdigest(),
            "compiler": oneapi_version("ifort"),
            "mpi": oneapi_version("mpirun"),
        },
    }

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    write_csv(rows)
    (RESULTS_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    kinetic = observables["kinetic_energy"]
    interaction = observables["interaction_energy"]
    summary_markdown = f"""# Binary Hirsch ALF projector-QMC result

- Total energy: `{energy:.8f} +/- {energy_error:.8f}`
- Kinetic energy: `{kinetic['mean']:.8f} +/- {kinetic['error']:.8f}`
- Interaction energy: `{interaction['mean']:.8f} +/- {interaction['error']:.8f}`
- Mean sign: `{mean_sign:.12f}`
- Acceptance: `{diagnostics['acceptance_mean']:.6f}`
- Green precision mean: `{diagnostics['green_precision_mean']:.3e}`
- Green precision max: `{diagnostics['green_precision_max']:.3e}`
- Raw / retained bins: `{len(rows)} / {len(included)}`
- Wall time: `{wall_seconds:.2f} s`
- Acceptance criteria: `{'PASS' if criteria['accepted'] else 'FAIL'}`

The first bin from each independent chain is omitted.  The result differs from
the ALF reference `{REFERENCE_ENERGY:.3f} +/- {REFERENCE_ERROR:.3f}` by
`{energy - REFERENCE_ENERGY:+.8f}` and from the finite-size exact value
`{EXACT_ENERGY:.4f}` by `{energy - EXACT_ENERGY:+.8f}`.

Under ideal inverse-square error scaling, reaching `sigma_E <= 0.004` would
require about `{iid_required_included_bins}` retained bins, or a fresh run
with about `{iid_fresh_bins_per_chain}` bins per chain
(`{statistics_extension['estimated_local_wall_seconds_for_fresh_run'] / 60:.1f}`
local minutes at the measured rate).  This is a planning estimate, not a
convergence guarantee.
"""
    (RESULTS_ROOT / "summary.md").write_text(
        summary_markdown, encoding="utf-8"
    )

    combined_log = [master_log.rstrip()]
    for chain in range(EXPECTED_CHAINS):
        run_log = (
            PRODUCTION_ROOT / f"chain_{chain}" / "run.log"
        ).read_text(encoding="utf-8")
        combined_log.append(f"\n===== chain_{chain} =====\n{run_log.rstrip()}")
    (RESULTS_ROOT / "run.log").write_text(
        "\n".join(combined_log) + "\n", encoding="utf-8"
    )
    (RESULTS_ROOT / "alf_analysis_crosscheck.txt").write_text(
        alf_crosscheck_text, encoding="utf-8"
    )
    provenance = summary["provenance"]
    provenance_text = "\n".join(
        f"{key}={value}" for key, value in provenance.items()
    )
    (RESULTS_ROOT / "provenance.txt").write_text(
        provenance_text + "\n", encoding="utf-8"
    )
    command_output(
        ["/usr/bin/python3", str(PROJECT_ROOT / "scripts" / "plot_energy.py")]
    )
    print(
        f"E = {energy:.8f} +/- {energy_error:.8f}; "
        f"sign = {mean_sign:.12f}; "
        f"criteria = {'PASS' if criteria['accepted'] else 'FAIL'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
