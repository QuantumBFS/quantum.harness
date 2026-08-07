"""Frozen three-arm attribution test for the 2D L=45 hybrid-neural VMCRG bias.

The three arms are sampled from the same initial microscopic configuration in
each chain, with independent random-number streams:

1. microscopic Hamiltonian only (unbiased),
2. the frozen 13-operator linear bias,
3. the same linear bias plus the frozen neural residual.

The single confirmatory endpoint is the hierarchical-bootstrap upper bound of
``tau_hybrid / tau_linear``.  The protocol is locked before execution; failure
is reported directly and is never repaired by changing thresholds afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.neural_challenge import (
    autocorrelation,
    context,
    integrated_time,
    sampler,
    write_json,
)
from scripts.neural_confirmation import hierarchical_summary
from vmcrg_ref.ising import IsingLattice, nearest_neighbor_operator
from vmcrg_ref.neural_energy import D4EvenLocalMLP


EXPECTED_REQUIREMENTS: dict[str, int | float | str] = {
    "length": 45,
    "model_repeats": 10,
    "chains_per_repeat": 8,
    "thermal_sweeps": 1000,
    "measurements": 5000,
    "sweeps_per_measurement": 1,
    "maximum_lag": 1000,
    "bootstrap_samples": 10000,
    "confidence_multiplier": 2.0,
    "primary_ratio": "hybrid_tau_over_linear_tau",
    "primary_upper_bound_threshold": 1.0,
    "minimum_improved_repeat_means": 8,
    "diagnostic_biased_over_unbiased_threshold": 0.5,
}

ARMS = ("hybrid", "linear", "unbiased")


def read_json(path: Path) -> dict:
    """Read both ordinary UTF-8 and Windows UTF-8-with-BOM JSON artifacts."""

    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zero_neural_model(model: D4EvenLocalMLP) -> D4EvenLocalMLP:
    """Return a structurally identical model whose energy is exactly zero."""

    result = model.copy()
    result.weight_in.fill(0.0)
    result.bias_hidden.fill(0.0)
    result.weight_out.fill(0.0)
    return result


def _seed_streams(protocol: dict) -> list[int]:
    streams = [int(record["seed"]) for record in protocol["repeat_sources"]]
    streams.extend(int(value) for value in protocol["bootstrap_seeds"].values())
    return streams


def validate_protocol(protocol: dict, archive: Path) -> list[dict]:
    if protocol.get("locked") is not True:
        raise ValueError("three-arm protocol must be locked before execution")
    requirements = protocol.get("formal_requirements", {})
    for key, expected in EXPECTED_REQUIREMENTS.items():
        if requirements.get(key) != expected:
            raise ValueError(f"locked three-arm requirement changed: {key}")

    records = protocol.get("repeat_sources")
    if not isinstance(records, list) or len(records) != 10:
        raise ValueError("three-arm confirmation requires exactly ten frozen models")
    if [int(record["repeat"]) for record in records] != list(range(1, 11)):
        raise ValueError("three-arm repeat identifiers must be ordered 1 through 10")
    paths = [str(record["path"]) for record in records]
    if len(paths) != len(set(paths)):
        raise ValueError("frozen model paths must be unique")

    streams = _seed_streams(protocol)
    if len(streams) != len(set(streams)):
        raise ValueError("measurement and bootstrap seeds must be unique")

    previous_streams: set[int] = set()
    for name in (
        "neural_confirmation_v1.json",
        "neural_confirmation_independent_v2.json",
    ):
        previous = read_json(archive / "protocols" / name)
        for repeat in previous["repeat_seeds"]:
            previous_streams.update(
                int(repeat[key])
                for key in (
                    "model",
                    "optimizer",
                    "validation",
                    "projection",
                    "ablation",
                    "autocorrelation",
                )
            )
        previous_streams.update(
            int(value) for value in previous["bootstrap_seeds"].values()
        )
    overlap = previous_streams.intersection(streams)
    if overlap:
        raise ValueError(f"three-arm streams overlap frozen experiments: {sorted(overlap)}")

    combined = read_json(archive / "combined_report.json")
    copy_check = read_json(archive / "verification" / "copy_verification.json")
    if combined.get("status") != "PASS" or copy_check.get("status") != "PASS":
        raise ValueError("source archive has not passed its integrity gates")
    return records


def _manifest_hashes(archive: Path) -> dict[str, str]:
    manifest = read_json(archive / "file_manifest.json")
    return {str(item["path"]): str(item["sha256"]) for item in manifest["files"]}


def verify_frozen_source(
    archive: Path, record: dict, expected_hashes: dict[str, str]
) -> tuple[Path, dict[str, str]]:
    source = (archive / str(record["path"])).resolve()
    if not source.is_relative_to(archive.resolve()):
        raise ValueError("frozen model path escaped the source archive")
    required = (
        "config.json",
        "bias_model.npz",
        "validation_formal.json",
        "projection_13.json",
        "neural_residual_ablation_formal.json",
    )
    verified: dict[str, str] = {}
    for name in required:
        path = source / name
        relative = path.relative_to(archive).as_posix()
        if not path.is_file() or relative not in expected_hashes:
            raise FileNotFoundError(f"frozen source is incomplete: {relative}")
        actual = file_sha256(path)
        if actual != expected_hashes[relative]:
            raise ValueError(f"frozen source hash mismatch: {relative}")
        verified[relative] = actual

    config = read_json(source / "config.json")
    validation = read_json(source / "validation_formal.json")
    projection = read_json(source / "projection_13.json")
    ablation = read_json(source / "neural_residual_ablation_formal.json")
    if int(config["length"]) != 45:
        raise ValueError("three-arm input must be an L=45 model")
    if validation.get("status") != "PASS" or projection.get("status") != "PASS":
        raise ValueError("three-arm input failed its distribution or projection gate")
    if ablation.get("status") not in {"PASS", "FAIL"}:
        raise ValueError("three-arm input has an invalid frozen ablation status")
    return source, verified


def _measure_series(run, requirements: dict) -> tuple[np.ndarray, np.ndarray, float]:
    run.run_sweeps(int(requirements["thermal_sweeps"]))
    values = np.empty(int(requirements["measurements"]), dtype=np.float64)
    for index in range(values.size):
        run.run_sweeps(int(requirements["sweeps_per_measurement"]))
        micro = nearest_neighbor_operator(run.lattice.spins) / run.lattice.n_sites
        block = nearest_neighbor_operator(run.block_spins) / run.block_spins.size
        values[index] = micro * block
    acf = autocorrelation(values, int(requirements["maximum_lag"]))
    tau = integrated_time(acf)
    run.assert_cache_consistent()
    return values, acf, float(tau)


def measure_repeat(
    source: Path,
    destination: Path,
    record: dict,
    requirements: dict,
    input_hashes: dict[str, str],
) -> dict:
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    config, model, micro_basis, block_basis = context(source)
    zero_model = zero_neural_model(model)
    zero_bias = np.zeros(13, dtype=np.float64)
    chains = int(requirements["chains_per_repeat"])
    sequences = np.random.SeedSequence(int(record["seed"])).spawn(chains * 4)
    taus = {arm: [] for arm in ARMS}
    acfs = {arm: [] for arm in ARMS}
    acceptance = {arm: [] for arm in ARMS}

    for chain in range(chains):
        initial_rng = np.random.default_rng(sequences[4 * chain])
        initial = IsingLattice.random(int(config["length"]), initial_rng).spins
        runs = {
            "hybrid": sampler(
                config,
                model,
                IsingLattice(initial.copy()),
                np.random.default_rng(sequences[4 * chain + 1]),
                micro_basis,
                block_basis,
            ),
            "linear": sampler(
                config,
                zero_model,
                IsingLattice(initial.copy()),
                np.random.default_rng(sequences[4 * chain + 2]),
                micro_basis,
                block_basis,
            ),
            "unbiased": sampler(
                config,
                zero_model,
                IsingLattice(initial.copy()),
                np.random.default_rng(sequences[4 * chain + 3]),
                micro_basis,
                block_basis,
                zero_bias,
            ),
        }
        for arm in ARMS:
            _, acf, tau = _measure_series(runs[arm], requirements)
            taus[arm].append(tau)
            acfs[arm].append(acf)
            acceptance[arm].append(runs[arm].acceptance_rate)
        print(
            f"repeat {record['repeat']}/10 chain {chain + 1}/{chains}", flush=True
        )

    arrays = {arm: np.asarray(taus[arm], dtype=np.float64) for arm in ARMS}
    if any(np.any(values <= 0.0) or not np.all(np.isfinite(values)) for values in arrays.values()):
        raise ValueError("integrated autocorrelation times must be positive and finite")
    ratios = {
        "hybrid_over_linear": arrays["hybrid"] / arrays["linear"],
        "linear_over_unbiased": arrays["linear"] / arrays["unbiased"],
        "hybrid_over_unbiased": arrays["hybrid"] / arrays["unbiased"],
    }
    result = {
        "status": "COMPLETE",
        "repeat": int(record["repeat"]),
        "batch": str(record["batch"]),
        "batch_repeat": int(record["batch_repeat"]),
        "source": str(source),
        "source_hashes": input_hashes,
        "seed": int(record["seed"]),
        "schedule": {
            key: requirements[key]
            for key in (
                "length",
                "chains_per_repeat",
                "thermal_sweeps",
                "measurements",
                "sweeps_per_measurement",
                "maximum_lag",
            )
        },
        "tau_mean": {arm: float(arrays[arm].mean()) for arm in ARMS},
        "tau_by_chain": {arm: arrays[arm].tolist() for arm in ARMS},
        "acceptance_rate_mean": {
            arm: float(np.mean(acceptance[arm])) for arm in ARMS
        },
        "ratio_mean": {
            name: float(values.mean()) for name, values in ratios.items()
        },
        "ratio_by_chain": {
            name: values.tolist() for name, values in ratios.items()
        },
    }
    write_json(destination / "three_arm.json", result)
    np.savez_compressed(
        destination / "three_arm.npz",
        hybrid_acf=np.asarray(acfs["hybrid"]),
        linear_acf=np.asarray(acfs["linear"]),
        unbiased_acf=np.asarray(acfs["unbiased"]),
        hybrid_tau=arrays["hybrid"],
        linear_tau=arrays["linear"],
        unbiased_tau=arrays["unbiased"],
    )
    return result


def assess_results(results: Iterable[dict], protocol: dict) -> dict:
    records = list(results)
    requirements = protocol["formal_requirements"]
    groups = {
        name: [
            np.asarray(record["ratio_by_chain"][name], dtype=np.float64)
            for record in records
        ]
        for name in (
            "hybrid_over_linear",
            "linear_over_unbiased",
            "hybrid_over_unbiased",
        )
    }
    summaries = {
        name: hierarchical_summary(
            values,
            seed=int(protocol["bootstrap_seeds"][name]),
            samples=int(requirements["bootstrap_samples"]),
            multiplier=float(requirements["confidence_multiplier"]),
        )
        for name, values in groups.items()
    }
    primary = summaries["hybrid_over_linear"]
    improved_repeats = int(sum(value < 1.0 for value in primary["repeat_means"]))
    gates = {
        "ten_frozen_models_present": len(records) == 10,
        "all_measurements_complete": all(
            record.get("status") == "COMPLETE" for record in records
        ),
        "at_least_eight_repeat_means_improve": improved_repeats
        >= int(requirements["minimum_improved_repeat_means"]),
        "hierarchical_hybrid_over_linear_upper_below_one": primary["upper_bound"]
        < float(requirements["primary_upper_bound_threshold"]),
    }
    threshold = float(requirements["diagnostic_biased_over_unbiased_threshold"])
    status = "PASS" if all(gates.values()) else "FAIL"
    all_tau = {
        arm: np.concatenate(
            [np.asarray(record["tau_by_chain"][arm], dtype=np.float64) for record in records]
        )
        for arm in ARMS
    }
    return {
        "status": status,
        "scope": protocol["scope"],
        "protocol": protocol["protocol"],
        "primary_endpoint": requirements["primary_ratio"],
        "gates": gates,
        "improved_repeat_means": improved_repeats,
        "hierarchical_ratios": summaries,
        "tau_mean_all_chains": {
            arm: float(values.mean()) for arm, values in all_tau.items()
        },
        "diagnostics": {
            "linear_over_unbiased_upper_below_0_5": summaries[
                "linear_over_unbiased"
            ]["upper_bound"]
            < threshold,
            "hybrid_over_unbiased_upper_below_0_5": summaries[
                "hybrid_over_unbiased"
            ]["upper_bound"]
            < threshold,
            "threshold": threshold,
        },
        "interpretation_boundary": (
            "PASS attributes an additional autocorrelation reduction to the frozen "
            "neural residual beyond the same frozen 13-operator bias."
        ),
        "not_claimed": [
            "pure_neural_replacement",
            "exact_multi_round_hybrid_fixed_point",
            "neural_Table_I_eigenvalues",
            "3D_spin_glass_transition",
        ],
    }


def run(output_root: Path, protocol_path: Path) -> dict:
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory: {output_root}")
    protocol = read_json(protocol_path)
    archive = (ROOT / str(protocol["source_archive"])).resolve()
    records = validate_protocol(protocol, archive)
    expected_hashes = _manifest_hashes(archive)
    verified_sources = [
        verify_frozen_source(archive, record, expected_hashes) for record in records
    ]
    output_root.mkdir(parents=True, exist_ok=True)
    code_paths = (
        ROOT / "reproduce.py",
        ROOT / "scripts/neural_challenge.py",
        ROOT / "scripts/neural_confirmation.py",
        ROOT / "scripts/neural_three_arm.py",
        *sorted((ROOT / "src/vmcrg_ref").glob("*.py")),
    )
    write_json(
        output_root / "run_manifest.json",
        {
            "protocol": protocol,
            "protocol_source": str(protocol_path),
            "protocol_sha256": file_sha256(protocol_path),
            "source_archive": str(archive),
            "source_archive_manifest_sha256": file_sha256(
                archive / "file_manifest.json"
            ),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "code_sha256": {
                str(path.relative_to(ROOT)): file_sha256(path) for path in code_paths
            },
        },
    )
    results = []
    for record, (source, hashes) in zip(records, verified_sources):
        results.append(
            measure_repeat(
                source,
                output_root / f"repeat_{int(record['repeat'])}",
                record,
                protocol["formal_requirements"],
                hashes,
            )
        )
    report = assess_results(results, protocol)
    write_json(output_root / "three_arm_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    if report["status"] != "PASS":
        raise RuntimeError("formal three-arm neural attribution gate failed")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    run(args.output_root.resolve(), args.protocol.resolve())


if __name__ == "__main__":
    main()
