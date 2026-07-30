"""Locked root-cause diagnostic for the frozen 2D hybrid-neural VMCRG models."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
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

from scripts.neural_challenge import context, sampler
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.neural_energy import D4EvenLocalMLP, LocalEnergyCache


EXPECTED_REQUIREMENTS: dict[str, int | float] = {
    "length": 45,
    "model_repeats": 10,
    "chains_per_repeat": 4,
    "thermal_sweeps": 500,
    "measurements_per_chain": 500,
    "sweeps_per_measurement": 1,
    "bootstrap_samples": 10000,
    "small_neural_delta_rms_ratio_threshold": 0.1,
    "small_acceptance_probability_change_threshold": 0.01,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zero_neural_model(model: D4EvenLocalMLP) -> D4EvenLocalMLP:
    result = model.copy()
    result.weight_in.fill(0.0)
    result.bias_hidden.fill(0.0)
    result.weight_out.fill(0.0)
    return result


def validate_protocol(protocol: dict, archive: Path, three_arm: Path) -> list[dict]:
    if protocol.get("locked") is not True:
        raise ValueError("root-cause protocol must be locked")
    requirements = protocol.get("formal_requirements", {})
    for key, expected in EXPECTED_REQUIREMENTS.items():
        if requirements.get(key) != expected:
            raise ValueError(f"locked root-cause requirement changed: {key}")
    records = protocol.get("repeat_sources")
    if not isinstance(records, list) or len(records) != 10:
        raise ValueError("root-cause diagnostic requires exactly ten models")
    if [int(record["repeat"]) for record in records] != list(range(1, 11)):
        raise ValueError("repeat identifiers must be ordered 1 through 10")
    paths = [str(record["path"]) for record in records]
    if len(paths) != len(set(paths)):
        raise ValueError("frozen model paths must be unique")

    streams = [int(record["seed"]) for record in records]
    streams.extend(int(value) for value in protocol["bootstrap_seeds"].values())
    if len(streams) != len(set(streams)):
        raise ValueError("root-cause random streams must be unique")

    previous_streams: set[int] = set()
    for name in (
        "neural_confirmation_v1.json",
        "neural_confirmation_independent_v2.json",
    ):
        previous = read_json(archive / "protocols" / name)
        for repeat in previous["repeat_seeds"]:
            previous_streams.update(int(value) for value in repeat.values())
        previous_streams.update(
            int(value) for value in previous["bootstrap_seeds"].values()
        )
    three_protocol = read_json(ROOT / "config" / "neural_three_arm_v1.json")
    previous_streams.update(int(record["seed"]) for record in three_protocol["repeat_sources"])
    previous_streams.update(
        int(value) for value in three_protocol["bootstrap_seeds"].values()
    )
    overlap = previous_streams.intersection(streams)
    if overlap:
        raise ValueError(f"root-cause streams overlap previous experiments: {sorted(overlap)}")

    if read_json(archive / "combined_report.json").get("status") != "PASS":
        raise ValueError("frozen source archive has not passed")
    if read_json(archive / "verification" / "copy_verification.json").get("status") != "PASS":
        raise ValueError("frozen source archive copy has not passed")
    source_report = read_json(three_arm / "three_arm_report.json")
    if source_report.get("status") != "FAIL":
        raise ValueError("root-cause diagnostic requires the frozen failed attribution result")
    return records


def manifest_hashes(archive: Path) -> dict[str, str]:
    manifest = read_json(archive / "file_manifest.json")
    return {str(item["path"]): str(item["sha256"]) for item in manifest["files"]}


def verify_source(
    archive: Path, record: dict, hashes: dict[str, str]
) -> tuple[Path, dict[str, str]]:
    source = (archive / str(record["path"])).resolve()
    required = (
        "config.json",
        "bias_model.npz",
        "validation_formal.json",
        "projection_13.json",
        "neural_residual_ablation_formal.json",
    )
    verified: dict[str, str] = {}
    for name in required:
        relative = f"{record['path']}/{name}"
        path = archive / relative
        expected = hashes.get(relative)
        if expected is None or not path.is_file() or sha256(path) != expected:
            raise ValueError(f"frozen input failed hash verification: {relative}")
        verified[relative] = expected
    config = read_json(source / "config.json")
    if int(config["length"]) != 45:
        raise ValueError("root-cause input must be L=45")
    return source, verified


def walsh_degree_power(model: D4EvenLocalMLP) -> dict:
    """Exactly decompose the 3x3 local density into Ising monomials."""

    if model.feature_mode != "patch" or model.radius != 1 or model.n_features != 9:
        raise ValueError("exact root-cause spectrum requires a radius-1 patch model")
    values = np.asarray(model.density_lookup_table(), dtype=np.float64)
    if values.shape != (512,):
        raise ValueError("radius-1 patch lookup must have 512 states")
    indices = np.arange(512, dtype=np.int64)
    states = 2.0 * ((indices[:, None] >> np.arange(9)) & 1) - 1.0
    characters = np.ones((512, 512), dtype=np.float64)
    degrees = np.empty(512, dtype=np.int64)
    for subset in range(512):
        selected = [bit for bit in range(9) if (subset >> bit) & 1]
        degrees[subset] = len(selected)
        if selected:
            characters[:, subset] = np.prod(states[:, selected], axis=1)
    coefficients = characters.T @ values / 512.0
    power = {
        str(degree): float(np.sum(coefficients[degrees == degree] ** 2))
        for degree in range(10)
    }
    nonconstant = float(np.sum(coefficients[1:] ** 2))
    odd = float(np.sum(coefficients[degrees % 2 == 1] ** 2))
    even_nonconstant = float(
        np.sum(coefficients[(degrees % 2 == 0) & (degrees > 0)] ** 2)
    )
    return {
        "constant": float(coefficients[0]),
        "lookup_mean": float(values.mean()),
        "lookup_standard_deviation": float(values.std()),
        "lookup_centered_max_abs": float(np.max(np.abs(values - values.mean()))),
        "power_by_degree": power,
        "nonconstant_power": nonconstant,
        "odd_power_fraction": odd / max(nonconstant, np.finfo(float).tiny),
        "degree_2_power_fraction": float(power["2"]) / max(even_nonconstant, np.finfo(float).tiny),
        "degree_4_power_fraction": float(power["4"]) / max(even_nonconstant, np.finfo(float).tiny),
        "degree_6_plus_power_fraction": float(
            power["6"] + power["8"]
        )
        / max(even_nonconstant, np.finfo(float).tiny),
        "coefficients": coefficients,
    }


def metropolis_probability(delta: float) -> float:
    return 1.0 if delta <= 0.0 else float(np.exp(-min(delta, 745.0)))


def synchronize_cache(cache: LocalEnergyCache, target: np.ndarray) -> None:
    changed = np.argwhere(cache.spins != target)
    for bx, by in changed:
        proposal = cache.proposal(int(bx), int(by))
        cache.commit(proposal)
        cache.spins[int(bx), int(by)] *= -1
    np.testing.assert_array_equal(cache.spins, target)


def eligible_micro_sites(run) -> np.ndarray:
    sites: list[tuple[int, int]] = []
    block_size = int(run.block_size)
    for bx, by in np.argwhere(np.abs(run.block_sums) == 1):
        majority = 1 if run.block_sums[int(bx), int(by)] > 0 else -1
        x0, y0 = int(bx) * block_size, int(by) * block_size
        patch = run.lattice.spins[x0 : x0 + block_size, y0 : y0 + block_size]
        for dx, dy in np.argwhere(patch == majority):
            sites.append((x0 + int(dx), y0 + int(dy)))
    return np.asarray(sites, dtype=np.int32)


def probe_chain(
    source: Path,
    seed_sequence: np.random.SeedSequence,
    requirements: dict,
) -> dict[str, np.ndarray | float]:
    config, model, micro_basis, block_basis = context(source)
    rng = np.random.default_rng(seed_sequence)
    run = sampler(
        config,
        zero_neural_model(model),
        IsingLattice.random(int(config["length"]), rng),
        rng,
        micro_basis,
        block_basis,
    )
    run.run_sweeps(int(requirements["thermal_sweeps"]))
    neural_cache = LocalEnergyCache(model, run.block_spins.copy())
    count = int(requirements["measurements_per_chain"])
    arrays = {
        "neural_delta": np.empty(count, dtype=np.float64),
        "linear_delta": np.empty(count, dtype=np.float64),
        "micro_delta": np.empty(count, dtype=np.float64),
        "acceptance_probability_change": np.empty(count, dtype=np.float64),
        "signed_acceptance_probability_change": np.empty(count, dtype=np.float64),
    }
    for index in range(count):
        run.run_sweeps(int(requirements["sweeps_per_measurement"]))
        synchronize_cache(neural_cache, run.block_spins)
        sites = eligible_micro_sites(run)
        if sites.shape[0] == 0:
            raise RuntimeError("linear ensemble produced no majority-changing proposal")
        x, y = sites[int(rng.integers(sites.shape[0]))]
        proposal = run.proposal_delta(int(x), int(y))
        if proposal.new_block_spin == int(run.block_spins[int(x) // 3, int(y) // 3]):
            raise AssertionError("selected proposal does not change the block spin")
        neural = neural_cache.proposal(int(x) // 3, int(y) // 3).delta_energy
        linear = float(np.dot(run.linear_bias, proposal.delta_linear_bias))
        micro = float(np.dot(run.couplings, proposal.delta_micro))
        p_linear = metropolis_probability(micro + linear)
        p_hybrid = metropolis_probability(micro + linear + neural)
        arrays["neural_delta"][index] = neural
        arrays["linear_delta"][index] = linear
        arrays["micro_delta"][index] = micro
        arrays["acceptance_probability_change"][index] = abs(p_hybrid - p_linear)
        arrays["signed_acceptance_probability_change"][index] = p_hybrid - p_linear
    synchronize_cache(neural_cache, run.block_spins)
    neural_cache.assert_consistent()
    run.assert_cache_consistent()
    neural_rms = float(np.sqrt(np.mean(arrays["neural_delta"] ** 2)))
    linear_rms = float(np.sqrt(np.mean(arrays["linear_delta"] ** 2)))
    return {
        **arrays,
        "neural_delta_rms": neural_rms,
        "linear_delta_rms": linear_rms,
        "neural_delta_rms_ratio": neural_rms / linear_rms,
        "mean_abs_acceptance_probability_change": float(
            arrays["acceptance_probability_change"].mean()
        ),
        "mean_signed_acceptance_probability_change": float(
            arrays["signed_acceptance_probability_change"].mean()
        ),
        "neural_linear_delta_correlation": float(
            np.corrcoef(arrays["neural_delta"], arrays["linear_delta"])[0, 1]
        ),
        "linear_sampler_acceptance_rate": float(run.acceptance_rate),
    }


def hierarchical_summary(
    groups: list[np.ndarray], *, seed: int, samples: int, multiplier: float = 2.0
) -> dict:
    arrays = [np.asarray(group, dtype=np.float64) for group in groups]
    repeat_means = np.asarray([group.mean() for group in arrays])
    point = float(repeat_means.mean())
    rng = np.random.default_rng(seed)
    draws = np.empty(samples, dtype=np.float64)
    for sample in range(samples):
        chosen = rng.integers(0, len(arrays), size=len(arrays))
        means = []
        for group_index in chosen:
            group = arrays[int(group_index)]
            means.append(float(group[rng.integers(0, group.size, group.size)].mean()))
        draws[sample] = float(np.mean(means))
    error = float(draws.std(ddof=1))
    return {
        "mean": point,
        "hierarchical_bootstrap_standard_error": error,
        "lower_bound": point - multiplier * error,
        "upper_bound": point + multiplier * error,
        "percentile_interval": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
        "repeat_means": repeat_means.tolist(),
        "bootstrap_samples": samples,
        "bootstrap_seed": seed,
    }


def ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    result = np.empty(values.size, dtype=np.float64)
    result[order] = np.arange(values.size, dtype=np.float64)
    return result


def correlation(x: np.ndarray, y: np.ndarray) -> dict:
    return {
        "pearson": float(np.corrcoef(x, y)[0, 1]),
        "spearman": float(np.corrcoef(ranks(x), ranks(y))[0, 1]),
        "sample_size": int(x.size),
        "confirmatory": False,
    }


def run(output: Path, protocol_path: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    protocol = read_json(protocol_path)
    archive = (ROOT / str(protocol["source_archive"])).resolve()
    three_arm = (ROOT / str(protocol["source_three_arm"])).resolve()
    records = validate_protocol(protocol, archive, three_arm)
    requirements = protocol["formal_requirements"]
    frozen_hashes = manifest_hashes(archive)

    code_paths = (
        ROOT / "reproduce.py",
        ROOT / "scripts" / "diagnose_neural_root_cause.py",
        ROOT / "scripts" / "neural_challenge.py",
        ROOT / "src" / "vmcrg_ref" / "hybrid_neural.py",
        ROOT / "src" / "vmcrg_ref" / "neural_energy.py",
    )
    manifest = {
        "protocol": protocol,
        "protocol_source": str(protocol_path),
        "protocol_sha256": sha256(protocol_path),
        "source_archive_manifest_sha256": sha256(archive / "file_manifest.json"),
        "source_three_arm_report_sha256": sha256(three_arm / "three_arm_report.json"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in code_paths},
    }
    write_json(output / "run_manifest.json", manifest)

    spectra: list[dict] = []
    chain_records: list[list[dict[str, np.ndarray | float]]] = []
    model_records: list[dict] = []
    coefficient_rows: list[np.ndarray] = []
    raw = {
        "neural_delta": [],
        "linear_delta": [],
        "micro_delta": [],
        "acceptance_probability_change": [],
        "signed_acceptance_probability_change": [],
    }

    for record in records:
        source, input_hashes = verify_source(archive, record, frozen_hashes)
        _, model, _, _ = context(source)
        spectrum = walsh_degree_power(model)
        coefficient_rows.append(np.asarray(spectrum.pop("coefficients")))
        spectra.append(spectrum)
        sequences = np.random.SeedSequence(int(record["seed"])).spawn(
            int(requirements["chains_per_repeat"])
        )
        with ThreadPoolExecutor(max_workers=int(requirements["chains_per_repeat"])) as executor:
            chains = list(
                executor.map(
                    lambda sequence: probe_chain(source, sequence, requirements),
                    sequences,
                )
            )
        chain_records.append(chains)
        for name in raw:
            raw[name].append(np.stack([np.asarray(chain[name]) for chain in chains]))
        ablation = read_json(source / "neural_residual_ablation_formal.json")
        projection = read_json(source / "projection_13.json")
        stage2 = read_json(
            three_arm / f"repeat_{int(record['repeat'])}" / "three_arm.json"
        )
        model_records.append(
            {
                "repeat": int(record["repeat"]),
                "batch": str(record["batch"]),
                "batch_repeat": int(record["batch_repeat"]),
                "seed": int(record["seed"]),
                "input_hashes": input_hashes,
                "ablation_status": ablation["status"],
                "delta_omega_per_block_site_mean": float(
                    ablation["delta_omega_per_block_site_mean"]
                ),
                "projection_validation_r_squared": float(
                    projection["validation_r_squared"]
                ),
                "projection_validation_rmse_per_site": float(
                    projection["validation_rmse_per_site"]
                ),
                "stage2_tau_hybrid_over_linear": float(
                    stage2["ratio_mean"]["hybrid_over_linear"]
                ),
                "stage2_acceptance_hybrid_minus_linear": float(
                    stage2["acceptance_rate_mean"]["hybrid"]
                    - stage2["acceptance_rate_mean"]["linear"]
                ),
                "spectrum": spectrum,
                "dynamic_chain_metrics": [
                    {
                        key: float(chain[key])
                        for key in (
                            "neural_delta_rms",
                            "linear_delta_rms",
                            "neural_delta_rms_ratio",
                            "mean_abs_acceptance_probability_change",
                            "mean_signed_acceptance_probability_change",
                            "neural_linear_delta_correlation",
                            "linear_sampler_acceptance_rate",
                        )
                    }
                    for chain in chains
                ],
            }
        )
        print(f"root-cause repeat {record['repeat']}/10 complete", flush=True)

    ratio_groups = [
        np.asarray([chain["neural_delta_rms_ratio"] for chain in chains])
        for chains in chain_records
    ]
    probability_groups = [
        np.asarray(
            [chain["mean_abs_acceptance_probability_change"] for chain in chains]
        )
        for chains in chain_records
    ]
    ratio_summary = hierarchical_summary(
        ratio_groups,
        seed=int(protocol["bootstrap_seeds"]["neural_delta_rms_ratio"]),
        samples=int(requirements["bootstrap_samples"]),
    )
    probability_summary = hierarchical_summary(
        probability_groups,
        seed=int(protocol["bootstrap_seeds"]["acceptance_probability_change"]),
        samples=int(requirements["bootstrap_samples"]),
    )
    gates = {
        "neural_delta_scale_is_small": ratio_summary["upper_bound"]
        < float(requirements["small_neural_delta_rms_ratio_threshold"]),
        "acceptance_probability_effect_is_small": probability_summary["upper_bound"]
        < float(requirements["small_acceptance_probability_change_threshold"]),
    }
    classification = (
        "NEURAL_DYNAMIC_PERTURBATION_TOO_SMALL"
        if all(gates.values())
        else "ROOT_CAUSE_INCONCLUSIVE"
    )

    delta_omega = np.asarray(
        [record["delta_omega_per_block_site_mean"] for record in model_records]
    )
    projection_r2 = np.asarray(
        [record["projection_validation_r_squared"] for record in model_records]
    )
    stage2_ratio = np.asarray(
        [record["stage2_tau_hybrid_over_linear"] for record in model_records]
    )
    stage2_acceptance = np.asarray(
        [record["stage2_acceptance_hybrid_minus_linear"] for record in model_records]
    )
    aggregate = {
        "status": "COMPLETE",
        "classification": classification,
        "classification_gates": gates,
        "dynamic_scale": {
            "neural_delta_rms_over_linear_delta_rms": ratio_summary,
            "mean_abs_acceptance_probability_change": probability_summary,
            "thresholds": {
                "neural_delta_rms_ratio": requirements[
                    "small_neural_delta_rms_ratio_threshold"
                ],
                "acceptance_probability_change": requirements[
                    "small_acceptance_probability_change_threshold"
                ],
            },
        },
        "static_spectrum_across_models": {
            key: {
                "mean": float(np.mean([spectrum[key] for spectrum in spectra])),
                "minimum": float(np.min([spectrum[key] for spectrum in spectra])),
                "maximum": float(np.max([spectrum[key] for spectrum in spectra])),
            }
            for key in (
                "lookup_standard_deviation",
                "lookup_centered_max_abs",
                "odd_power_fraction",
                "degree_2_power_fraction",
                "degree_4_power_fraction",
                "degree_6_plus_power_fraction",
            )
        },
        "frozen_projection_across_models": {
            "validation_r_squared_mean": float(projection_r2.mean()),
            "validation_r_squared_range": [
                float(projection_r2.min()),
                float(projection_r2.max()),
            ],
        },
        "exploratory_correlations": {
            "delta_omega_vs_stage2_tau_ratio": correlation(delta_omega, stage2_ratio),
            "projection_r2_vs_stage2_tau_ratio": correlation(projection_r2, stage2_ratio),
            "stage2_acceptance_change_vs_tau_ratio": correlation(
                stage2_acceptance, stage2_ratio
            ),
        },
        "model_records": model_records,
        "interpretation_boundary": {
            "does_not_change_stage2_fail": True,
            "does_not_test_pure_neural_replacement": True,
            "does_not_test_table1": True,
            "does_not_support_3d_claims": True,
        },
    }
    write_json(output / "root_cause_report.json", aggregate)
    np.savez_compressed(
        output / "root_cause_raw.npz",
        coefficients=np.stack(coefficient_rows),
        **{name: np.stack(values) for name, values in raw.items()},
    )
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.protocol.resolve())
    print(json.dumps({
        "status": result["status"],
        "classification": result["classification"],
        "classification_gates": result["classification_gates"],
        "dynamic_scale": result["dynamic_scale"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
