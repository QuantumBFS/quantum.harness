"""Pre-registered multi-seed confirmation for the L=45 hybrid-neural challenge."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.neural_challenge import (
    AUTOCORRELATION_RATIO_TOLERANCE,
    CONFIDENCE_MULTIPLIER,
    EQUIVALENCE_TOLERANCE,
    FIXED_POINT_ABSOLUTE_TOLERANCE,
    FIXED_POINT_RELATIVE_TOLERANCE,
    PRESETS,
    ablate,
    compare_autocorrelation,
    project,
    read_json,
    train,
    validate,
    write_json,
)


STAGES = (
    "model",
    "optimizer",
    "validation",
    "projection",
    "ablation",
    "autocorrelation",
)

REPRESENTATION_MODES = {
    "13_operator_skip_plus_d4_z2_patch_residual": "hybrid",
    "pure_d4_z2_radius3_shell_neural_energy": "pure_shell_v1",
    "pure_d4_z2_radius3_multiscale_neural_energy": "pure",
}


def protocol_representation_mode(protocol: dict) -> str:
    representation = protocol.get("representation")
    if representation not in REPRESENTATION_MODES:
        raise ValueError("confirmation protocol has an unsupported representation")
    return REPRESENTATION_MODES[representation]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_protocol(protocol: dict, preset: str) -> list[dict]:
    if protocol.get("locked") is not True:
        raise ValueError("confirmation protocol must be locked before execution")
    representation_mode = protocol_representation_mode(protocol)
    repeats = protocol.get("repeat_seeds")
    if not isinstance(repeats, list) or not repeats:
        raise ValueError("confirmation protocol has no repeat seed records")
    identifiers = [int(record["repeat"]) for record in repeats]
    if identifiers != list(range(1, len(repeats) + 1)):
        raise ValueError("repeat identifiers must be consecutive and ordered")
    streams = [int(record[stage]) for record in repeats for stage in STAGES]
    streams.extend(int(value) for value in protocol["bootstrap_seeds"].values())
    if len(streams) != len(set(streams)):
        raise ValueError("all training, validation, and bootstrap seeds must be unique")

    if preset == "formal":
        requirements = protocol["formal_requirements"]
        training = PRESETS["formal"]["train"]
        expected = {
            "repeats": len(repeats),
            "length": training["length"],
            "training_steps": training["steps"],
            "walkers": training["walkers"],
            "sweeps_per_step": training["sweeps"],
            "target_samples_per_step": training["targets"],
            "validation_chains_per_repeat": PRESETS["formal"]["validation"]["chains"],
            "validation_thermal_sweeps": PRESETS["formal"]["validation"]["thermal"],
            "validation_measurements": PRESETS["formal"]["validation"]["measurements"],
            "validation_spacing_sweeps": PRESETS["formal"]["validation"]["spacing"],
            "projection_samples": PRESETS["formal"]["projection_samples"],
            "ablation_thermal_sweeps": PRESETS["formal"]["ablation"]["thermal"],
            "ablation_measurements": PRESETS["formal"]["ablation"]["measurements"],
            "ablation_spacing_sweeps": PRESETS["formal"]["ablation"]["spacing"],
            "autocorrelation_chains_per_repeat": PRESETS["formal"]["autocorrelation"]["chains"],
            "autocorrelation_thermal_sweeps": PRESETS["formal"]["autocorrelation"]["thermal"],
            "autocorrelation_measurements": PRESETS["formal"]["autocorrelation"]["measurements"],
            "autocorrelation_max_lag": PRESETS["formal"]["autocorrelation"]["lag"],
        }
        for key, value in expected.items():
            if int(requirements[key]) != int(value):
                raise ValueError(f"formal protocol mismatch for {key}")
        if len(repeats) != 5:
            raise ValueError("formal confirmation requires exactly five training seeds")
        if int(requirements["ablation_chains_per_repeat"]) != 32:
            raise ValueError("formal confirmation requires 32 ablation chains per repeat")
        if int(requirements["hidden_units"]) != 32:
            raise ValueError("formal confirmation requires 32 hidden units")
        if float(requirements["learning_rate"]) != 5e-4:
            raise ValueError("formal confirmation learning rate changed")
        if int(requirements["averaging_start"]) != 1500:
            raise ValueError("formal confirmation averaging start changed")
        if int(requirements["minimum_negative_repeat_means"]) != 4:
            raise ValueError("formal confirmation requires at least four negative repeat means")
        if int(requirements["bootstrap_samples"]) < 10_000:
            raise ValueError("formal confirmation requires at least 10000 bootstrap samples")
        if float(requirements["confidence_multiplier"]) != CONFIDENCE_MULTIPLIER:
            raise ValueError("formal confirmation confidence multiplier changed")
        if (
            float(requirements["autocorrelation_ratio_threshold"])
            != AUTOCORRELATION_RATIO_TOLERANCE
        ):
            raise ValueError("formal autocorrelation threshold changed")
        if representation_mode in {"pure", "pure_shell_v1"}:
            if float(requirements["equivalence_tolerance"]) != EQUIVALENCE_TOLERANCE:
                raise ValueError("formal distribution tolerance changed")
            if (
                float(requirements["fixed_point_absolute_tolerance"])
                != FIXED_POINT_ABSOLUTE_TOLERANCE
            ):
                raise ValueError("formal fixed-point absolute tolerance changed")
            if (
                float(requirements["fixed_point_relative_l2_tolerance"])
                != FIXED_POINT_RELATIVE_TOLERANCE
            ):
                raise ValueError("formal fixed-point relative tolerance changed")
            if protocol.get("scope") != "2D_L45_pure_neural_VMCRG_replacement":
                raise ValueError("pure-neural confirmation scope changed")
            if int(requirements["neural_radius"]) != 3:
                raise ValueError("pure-neural confirmation requires radius three")
            expected_feature_mode = (
                "multiscale" if representation_mode == "pure" else "shell"
            )
            if requirements["neural_feature_mode"] != expected_feature_mode:
                raise ValueError(
                    f"pure-neural confirmation requires {expected_feature_mode} features"
                )
            if float(requirements["fixed_linear_bias_linf"]) != 0.0:
                raise ValueError("pure-neural confirmation requires zero linear bias")
            if protocol.get("early_stop_after_pre_autocorrelation_failure") is not True:
                raise ValueError("pure-neural formal early-stop rule is not locked")
    return repeats


def hierarchical_summary(
    groups: list[np.ndarray],
    *,
    seed: int,
    samples: int,
    multiplier: float,
) -> dict:
    arrays = [np.asarray(group, dtype=np.float64) for group in groups]
    if len(arrays) < 2 or any(group.ndim != 1 or group.size < 2 for group in arrays):
        raise ValueError("hierarchical bootstrap needs at least two groups of two values")
    if any(not np.all(np.isfinite(group)) for group in arrays):
        raise ValueError("hierarchical bootstrap inputs must be finite")
    if samples <= 1:
        raise ValueError("bootstrap samples must be greater than one")
    repeat_means = np.asarray([group.mean() for group in arrays])
    point = float(repeat_means.mean())
    rng = np.random.default_rng(seed)
    bootstrapped = np.empty(samples, dtype=np.float64)
    group_count = len(arrays)
    for sample in range(samples):
        selected = rng.integers(0, group_count, size=group_count)
        means = []
        for index in selected:
            group = arrays[int(index)]
            resampled = group[rng.integers(0, group.size, size=group.size)]
            means.append(float(resampled.mean()))
        bootstrapped[sample] = float(np.mean(means))
    standard_error = float(bootstrapped.std(ddof=1))
    return {
        "mean": point,
        "hierarchical_bootstrap_standard_error": standard_error,
        "lower_bound": point - multiplier * standard_error,
        "upper_bound": point + multiplier * standard_error,
        "repeat_means": repeat_means.tolist(),
        "bootstrap_percentile_interval": [
            float(np.quantile(bootstrapped, 0.025)),
            float(np.quantile(bootstrapped, 0.975)),
        ],
        "bootstrap_samples": samples,
        "bootstrap_seed": seed,
        "confidence_multiplier": multiplier,
    }


def repeat_directory(root: Path, repeat: int) -> Path:
    return root / f"repeat_{repeat}"


def run_repeat(
    root: Path,
    preset: str,
    fixed_point_map: Path,
    seeds: dict,
    ablation_chains: int,
    representation_mode: str,
) -> None:
    destination = repeat_directory(root, int(seeds["repeat"]))
    train(
        destination,
        preset,
        fixed_point_map,
        model_seed=int(seeds["model"]),
        optimizer_seed=int(seeds["optimizer"]),
        representation=representation_mode,
    )
    validate(
        destination,
        preset,
        seed=int(seeds["validation"]),
        enforce_formal_gate=False,
    )
    project(
        destination,
        preset,
        seed=int(seeds["projection"]),
        enforce_formal_gate=False,
    )
    ablate(
        destination,
        preset,
        seed=int(seeds["ablation"]),
        chains_override=ablation_chains,
        enforce_formal_gate=False,
    )


def verify_repeat(
    root: Path,
    preset: str,
    seeds: dict,
    ablation_chains: int,
    requirements: dict,
    representation: str,
) -> dict:
    destination = repeat_directory(root, int(seeds["repeat"]))
    config = read_json(destination / "config.json")
    validation_result = read_json(destination / f"validation_{preset}.json")
    projection_result = read_json(destination / "projection_13.json")
    ablation_result = read_json(
        destination / f"neural_residual_ablation_{preset}.json"
    )
    expected_seeds = {
        "model_seed": int(seeds["model"]),
        "optimizer_seed": int(seeds["optimizer"]),
    }
    for key, value in expected_seeds.items():
        if int(config[key]) != value:
            raise ValueError(f"repeat {seeds['repeat']} has a mismatched {key}")
    if config.get("representation") != representation:
        raise ValueError(f"repeat {seeds['repeat']} has a mismatched representation")
    if representation in {
        "pure_d4_z2_radius3_shell_neural_energy",
        "pure_d4_z2_radius3_multiscale_neural_energy",
    }:
        if int(config["neural_radius"]) != int(requirements["neural_radius"]):
            raise ValueError(f"repeat {seeds['repeat']} has the wrong neural radius")
        if config["neural_feature_mode"] != requirements["neural_feature_mode"]:
            raise ValueError(f"repeat {seeds['repeat']} has the wrong feature mode")
        if float(np.max(np.abs(np.asarray(config["fixed_linear_bias"])))) != float(
            requirements["fixed_linear_bias_linf"]
        ):
            raise ValueError(f"repeat {seeds['repeat']} has a nonzero linear bias")
    for result, stage in (
        (validation_result, "validation"),
        (projection_result, "projection"),
        (ablation_result, "ablation"),
    ):
        if int(result["seed"]) != int(seeds[stage]):
            raise ValueError(f"repeat {seeds['repeat']} has a mismatched {stage} seed")
    if int(ablation_result["chains"]) != ablation_chains:
        raise ValueError(f"repeat {seeds['repeat']} has the wrong ablation chain count")
    if preset == "formal":
        schedule = {
            "validation chains": (
                validation_result["chains"],
                requirements["validation_chains_per_repeat"],
            ),
            "validation thermal": (
                validation_result["thermal"],
                requirements["validation_thermal_sweeps"],
            ),
            "validation measurements": (
                validation_result["measurements"],
                requirements["validation_measurements"],
            ),
            "validation spacing": (
                validation_result["spacing"],
                requirements["validation_spacing_sweeps"],
            ),
            "projection samples": (
                projection_result["samples"],
                requirements["projection_samples"],
            ),
            "ablation thermal": (
                ablation_result["thermal"],
                requirements["ablation_thermal_sweeps"],
            ),
            "ablation measurements": (
                ablation_result["measurements"],
                requirements["ablation_measurements"],
            ),
            "ablation spacing": (
                ablation_result["spacing"],
                requirements["ablation_spacing_sweeps"],
            ),
        }
        for name, (actual, expected) in schedule.items():
            if int(actual) != int(expected):
                raise ValueError(f"repeat {seeds['repeat']} has a mismatched {name}")
    return {
        "repeat": int(seeds["repeat"]),
        "training": config,
        "validation": validation_result,
        "projection": projection_result,
        "ablation": ablation_result,
    }


def assess_pre_autocorrelation(
    root: Path, preset: str, protocol: dict, repeats: list[dict]
) -> dict:
    requirements = protocol["formal_requirements"]
    ablation_chains = (
        int(requirements["ablation_chains_per_repeat"])
        if preset == "formal"
        else int(PRESETS[preset]["ablation"]["chains"])
    )
    records = [
        verify_repeat(
            root,
            preset,
            seeds,
            ablation_chains,
            requirements,
            protocol["representation"],
        )
        for seeds in repeats
    ]
    formal_training = all(
        int(record["training"]["length"]) == 45
        and int(record["training"]["steps"]) == 3000
        and int(record["training"]["walkers"]) == 16
        and int(record["training"]["sweeps"]) == 20
        and int(record["training"]["target_samples"]) == 32
        and int(record["training"]["hidden"]) == 32
        and float(record["training"]["learning_rate"]) == 5e-4
        and int(record["training"]["averaging_start"]) == 1500
        and record["training"]["representation"] == protocol["representation"]
        for record in records
    )
    validations_pass = all(record["validation"]["status"] == "PASS" for record in records)
    projections_pass = all(record["projection"]["status"] == "PASS" for record in records)
    groups = [
        np.asarray(record["ablation"]["delta_omega_by_chain"], dtype=np.float64)
        for record in records
    ]
    bootstrap = hierarchical_summary(
        groups,
        seed=int(protocol["bootstrap_seeds"]["ablation"]),
        samples=int(requirements["bootstrap_samples"]),
        multiplier=float(requirements["confidence_multiplier"]),
    )
    negative_count = int(sum(value < 0.0 for value in bootstrap["repeat_means"]))
    gates = {
        "five_predeclared_training_repeats_present": len(records) == 5,
        "formal_l45_training_budget": formal_training,
        "all_frozen_distribution_gates": validations_pass,
        "all_fixed_point_projection_gates": projections_pass,
        "at_least_four_negative_repeat_means": negative_count
        >= int(requirements["minimum_negative_repeat_means"]),
        "hierarchical_ablation_upper_bound_below_zero": bootstrap["upper_bound"]
        < 0.0,
    }
    passed = all(gates.values())
    result = {
        "status": "PASS" if passed else ("FAIL" if preset == "formal" else "NOT_FORMAL"),
        "preset": preset,
        "representation": protocol["representation"],
        "gates": gates,
        "negative_repeat_means": negative_count,
        "ablation": bootstrap,
        "repeat_status": [
            {
                "repeat": record["repeat"],
                "validation": record["validation"]["status"],
                "projection": record["projection"]["status"],
                "ablation_point_estimate": record["ablation"][
                    "delta_omega_per_block_site_mean"
                ],
            }
            for record in records
        ],
    }
    write_json(root / "pre_autocorrelation_assessment.json", result)
    return result


def run_autocorrelations(root: Path, preset: str, repeats: list[dict]) -> None:
    for seeds in repeats:
        compare_autocorrelation(
            repeat_directory(root, int(seeds["repeat"])),
            preset,
            seed=int(seeds["autocorrelation"]),
            enforce_formal_gate=False,
        )


def assess_final(root: Path, preset: str, protocol: dict, repeats: list[dict]) -> dict:
    requirements = protocol["formal_requirements"]
    pre = read_json(root / "pre_autocorrelation_assessment.json")
    results = []
    groups = []
    for seeds in repeats:
        result = read_json(
            repeat_directory(root, int(seeds["repeat"]))
            / f"autocorrelation_{preset}.json"
        )
        if int(result["seed"]) != int(seeds["autocorrelation"]):
            raise ValueError(f"repeat {seeds['repeat']} has a mismatched autocorrelation seed")
        if preset == "formal":
            schedule = {
                "chains": requirements["autocorrelation_chains_per_repeat"],
                "thermal": requirements["autocorrelation_thermal_sweeps"],
                "measurements": requirements["autocorrelation_measurements"],
                "lag": requirements["autocorrelation_max_lag"],
            }
            for key, expected in schedule.items():
                if int(result[key]) != int(expected):
                    raise ValueError(
                        f"repeat {seeds['repeat']} has a mismatched autocorrelation {key}"
                    )
        results.append(result)
        groups.append(
            np.asarray(result["biased_tau_by_chain"], dtype=np.float64)
            / np.asarray(result["unbiased_tau_by_chain"], dtype=np.float64)
        )
    bootstrap = hierarchical_summary(
        groups,
        seed=int(protocol["bootstrap_seeds"]["autocorrelation"]),
        samples=int(requirements["bootstrap_samples"]),
        multiplier=float(requirements["confidence_multiplier"]),
    )
    threshold = float(requirements["autocorrelation_ratio_threshold"])
    gates = {
        "pre_autocorrelation_confirmation": pre["status"] == "PASS",
        "all_repeat_autocorrelation_gates": all(
            result["status"] == "PASS" for result in results
        ),
        "hierarchical_autocorrelation_upper_bound_below_threshold": bootstrap[
            "upper_bound"
        ]
        <= threshold,
    }
    passed = all(gates.values())
    report = {
        "status": "PASS" if passed else ("FAIL" if preset == "formal" else "NOT_FORMAL"),
        "scope": (
            "2D_L45_pure_neural_VMCRG_multi_seed_confirmation"
            if protocol_representation_mode(protocol) == "pure"
            else "2D_L45_hybrid_neural_VMCRG_multi_seed_confirmation"
        ),
        "preset": preset,
        "protocol": protocol["protocol"],
        "representation": protocol["representation"],
        "gates": {**pre["gates"], **gates},
        "ablation": pre["ablation"],
        "autocorrelation_ratio": {**bootstrap, "threshold": threshold},
        "not_claimed": (
            [
                "neural_Table_I_eigenvalues",
                "3D_spin_glass_transition",
            ]
            if protocol_representation_mode(protocol) == "pure" and passed
            else [
                "pure_neural_replacement",
                "neural_Table_I_eigenvalues",
                "3D_spin_glass_transition",
            ]
            if protocol_representation_mode(protocol) == "pure"
            else [
                "pure_neural_replacement",
                "exact_multi_round_hybrid_fixed_point",
                "3D_spin_glass_transition",
            ]
        ),
    }
    write_json(root / "confirmation_report.json", report)
    return report


def run(root: Path, preset: str, fixed_point_map: Path, protocol_path: Path) -> dict:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory: {root}")
    protocol = read_json(protocol_path)
    repeats = validate_protocol(protocol, preset)
    representation_mode = protocol_representation_mode(protocol)
    root.mkdir(parents=True, exist_ok=True)
    code_paths = (
        ROOT / "reproduce.py",
        ROOT / "scripts/neural_challenge.py",
        ROOT / "scripts/neural_confirmation.py",
        *sorted((ROOT / "src/vmcrg_ref").glob("*.py")),
    )
    write_json(
        root / "run_manifest.json",
        {
            "protocol": protocol,
            "protocol_source": str(protocol_path),
            "protocol_sha256": file_sha256(protocol_path),
            "fixed_point_map": str(fixed_point_map),
            "fixed_point_map_sha256": file_sha256(fixed_point_map),
            "preset": preset,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "code_sha256": {str(path.relative_to(ROOT)): file_sha256(path) for path in code_paths},
        },
    )
    ablation_chains = (
        int(protocol["formal_requirements"]["ablation_chains_per_repeat"])
        if preset == "formal"
        else int(PRESETS[preset]["ablation"]["chains"])
    )
    for seeds in repeats:
        run_repeat(
            root,
            preset,
            fixed_point_map,
            seeds,
            ablation_chains,
            representation_mode,
        )
    pre = assess_pre_autocorrelation(root, preset, protocol, repeats)
    if preset == "formal" and pre["status"] != "PASS":
        raise RuntimeError("formal multi-seed neural ablation confirmation failed")
    run_autocorrelations(root, preset, repeats)
    report = assess_final(root, preset, protocol, repeats)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    if preset == "formal" and report["status"] != "PASS":
        raise RuntimeError("formal multi-seed neural confirmation failed")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=tuple(PRESETS), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--fixed-point-map", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.output_root.resolve(),
        args.preset,
        args.fixed_point_map.resolve(),
        args.protocol.resolve(),
    )


if __name__ == "__main__":
    main()
