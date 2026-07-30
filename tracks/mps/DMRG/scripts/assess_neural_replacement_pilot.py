"""Paired zero-bias baseline and GO/NO-GO assessment for the pure-neural pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.neural_challenge import PRESETS, context, patch_histogram, sampler
from vmcrg_ref.ising import IsingLattice
from vmcrg_ref.neural_energy import D4EvenLocalMLP


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def zero_model() -> D4EvenLocalMLP:
    model = D4EvenLocalMLP.random(1, 1, 202677000, feature_mode="patch")
    model.weight_in.fill(0.0)
    model.bias_hidden.fill(0.0)
    model.weight_out.fill(0.0)
    return model


def measure_zero_validation(root: Path) -> dict:
    config, _, micro_basis, block_basis = context(root)
    pure_validation = read_json(root / "validation_pilot.json")
    settings = dict(PRESETS["pilot"]["validation"])
    seed = int(pure_validation["seed"])
    normalizers = np.asarray(block_basis.instance_counts, dtype=np.float64)
    chain_means, patch_probabilities, target_probabilities = [], [], []
    sequences = np.random.SeedSequence(seed).spawn(settings["chains"] * 2)
    coarse = block_basis.length
    model = zero_model()
    linear_bias = np.zeros(13, dtype=np.float64)
    acceptances = []
    for chain in range(settings["chains"]):
        rng = np.random.default_rng(sequences[2 * chain])
        target_rng = np.random.default_rng(sequences[2 * chain + 1])
        run = sampler(
            config,
            model,
            IsingLattice.random(int(config["length"]), rng),
            rng,
            micro_basis,
            block_basis,
            linear_bias,
        )
        run.run_sweeps(settings["thermal"])
        attempted, accepted = run.attempted, run.accepted
        samples = []
        observed = np.zeros(512, dtype=np.int64)
        target = np.zeros(512, dtype=np.int64)
        for _ in range(settings["measurements"]):
            run.run_sweeps(settings["spacing"])
            samples.append(block_basis.values(run.block_spins) / normalizers)
            observed += patch_histogram(run.block_spins)
            uniform = target_rng.choice(
                np.array([-1, 1], dtype=np.int8), size=(coarse, coarse)
            )
            target += patch_histogram(uniform)
        chain_means.append(np.mean(samples, axis=0))
        patch_probabilities.append(observed / observed.sum())
        target_probabilities.append(target / target.sum())
        acceptances.append((run.accepted - accepted) / (run.attempted - attempted))
        run.assert_cache_consistent()
        print(f"zero baseline {chain + 1}/{settings['chains']}", flush=True)
    chains = np.asarray(chain_means)
    means = chains.mean(axis=0)
    errors = chains.std(axis=0, ddof=1) / np.sqrt(settings["chains"])
    bounds = np.abs(means) + 2.0 * errors
    uniform = 1.0 / 512.0
    observed_tv = 0.5 * np.sum(
        np.abs(np.asarray(patch_probabilities) - uniform), axis=1
    )
    target_tv = 0.5 * np.sum(
        np.abs(np.asarray(target_probabilities) - uniform), axis=1
    )
    excess = observed_tv - target_tv
    return {
        "seed": seed,
        **settings,
        "max_operator_bound": float(bounds.max()),
        "excess_patch_tv_upper_bound": float(
            excess.mean() + 2.0 * excess.std(ddof=1) / np.sqrt(settings["chains"])
        ),
        "mean_acceptance_rate": float(np.mean(acceptances)),
        "operator_means_by_chain": chains.tolist(),
        "operator_mean": means.tolist(),
        "operator_standard_error": errors.tolist(),
        "operator_bounds": bounds.tolist(),
        "observed_patch_tv_by_chain": observed_tv.tolist(),
        "target_patch_tv_by_chain": target_tv.tolist(),
        "excess_patch_tv_by_chain": excess.tolist(),
        "acceptance_rate_by_chain": [float(value) for value in acceptances],
    }


def assess_metrics(
    pure_validation: dict,
    zero_validation: dict,
    projection: dict,
    zero_linf: float,
    ablation: dict,
    autocorrelation: dict,
) -> dict:
    gates = {
        "operator_distribution_moves_toward_target": float(
            pure_validation["max_equivalence_bound"]
        )
        < float(zero_validation["max_operator_bound"]),
        "patch_distribution_moves_toward_target": float(
            pure_validation["excess_patch_tv_upper_bound"]
        )
        < float(zero_validation["excess_patch_tv_upper_bound"]),
        "projected_couplings_move_toward_fixed_point": float(
            projection["fixed_point_linf_residual"]
        )
        < zero_linf,
        "heldout_variational_objective_improves": float(
            ablation["delta_omega_per_block_site_upper_bound"]
        )
        < 0.0,
        "autocorrelation_improves": float(
            autocorrelation["paired_ratio_upper_bound"]
        )
        < 1.0,
    }
    return {
        "status": "GO_FORMAL_PROTOCOL_DESIGN" if all(gates.values()) else "NO_GO",
        "gates": gates,
    }


def run(root: Path, output: Path) -> dict:
    config = read_json(root / "config.json")
    if config.get("preset") != "pilot" or config.get("length") != 45:
        raise ValueError("assessment requires an L45 pilot")
    if (
        config.get("representation")
        != "pure_d4_z2_radius3_multiscale_neural_energy"
    ):
        raise ValueError("assessment requires the multiscale pure-neural representation")
    pure_validation = read_json(root / "validation_pilot.json")
    projection = read_json(root / "projection_13.json")
    ablation = read_json(root / "neural_residual_ablation_pilot.json")
    autocorrelation = read_json(root / "autocorrelation_pilot.json")
    zero_validation = measure_zero_validation(root)
    zero_linf = float(np.max(np.abs(np.asarray(config["microscopic_couplings"]))))
    decision = assess_metrics(
        pure_validation,
        zero_validation,
        projection,
        zero_linf,
        ablation,
        autocorrelation,
    )
    result = {
        **decision,
        "scope": "L45_pure_neural_replacement_pilot_go_no_go",
        "pure_validation": {
            "max_operator_bound": pure_validation["max_equivalence_bound"],
            "excess_patch_tv_upper_bound": pure_validation[
                "excess_patch_tv_upper_bound"
            ],
        },
        "zero_bias_validation": zero_validation,
        "projection": {
            "pure_linf_residual": projection["fixed_point_linf_residual"],
            "zero_linf_residual": zero_linf,
        },
        "heldout_delta_omega_upper_bound": ablation[
            "delta_omega_per_block_site_upper_bound"
        ],
        "autocorrelation_ratio_upper_bound": autocorrelation[
            "paired_ratio_upper_bound"
        ],
        "boundary": (
            "GO permits preregistration of a formal multi-seed protocol; it is not "
            "evidence that the pure-neural challenge has passed."
        ),
    }
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.input.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else root / "pilot_assessment.json"
    )
    run(root, output)


if __name__ == "__main__":
    main()
