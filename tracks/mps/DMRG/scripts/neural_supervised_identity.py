"""Direct supervised representability test for the 13-term identity RG.

For an identity block transformation and a uniform VMCRG reference,
``V_min = -H + constant``.  This experiment removes Monte Carlo sampling from
training and asks whether the pure multiscale neural energy can learn that
known bias directly from independent uniform Ising patches.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vmcrg_ref.hybrid_neural import Adam
from vmcrg_ref.neural_energy import D4EvenLocalMLP, MLPGradient
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis, OperatorShape

from scripts.neural_challenge import fit_operator_projection, read_json, write_json


PRESETS = {
    "smoke": dict(steps=50, batch=256, evaluation_samples=2000, projection_samples=2000),
    "pilot": dict(steps=1500, batch=512, evaluation_samples=10000, projection_samples=10000),
    "formal": dict(steps=6000, batch=1024, evaluation_samples=20000, projection_samples=20000),
}

ABSOLUTE_COUPLING_TOLERANCE = 0.001
RELATIVE_L2_TOLERANCE = 0.005


def d4_transforms(x: int, y: int) -> tuple[tuple[int, int], ...]:
    return (
        (x, y),
        (-y, x),
        (-x, -y),
        (y, -x),
        (-x, y),
        (x, -y),
        (y, x),
        (-y, -x),
    )


def _best_integer_anchor(vertices: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    xs = tuple(x for x, _ in vertices)
    ys = tuple(y for _, y in vertices)
    candidates = []
    for anchor_x in range(min(xs), max(xs) + 1):
        for anchor_y in range(min(ys), max(ys) + 1):
            radius = max(
                max(abs(x - anchor_x), abs(y - anchor_y)) for x, y in vertices
            )
            candidates.append(
                (radius, (anchor_x, anchor_y) != (0, 0), abs(anchor_x) + abs(anchor_y), anchor_x, anchor_y)
            )
    _, _, _, anchor_x, anchor_y = min(candidates)
    return anchor_x, anchor_y


def anchored_d4_orbit(shape: OperatorShape) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return a D4-invariant local decomposition compatible with multiscale features.

    Pair terms stay anchored at one endpoint.  Their D4 orbit is a centre spin
    times a complete outer shell sum, which is retained exactly by the pooled
    shell features.  Four-spin terms use the smallest integer-centred patch;
    all six published geometries then lie in the exact inner 3x3 features.
    """

    if len(shape.vertices) == 2:
        anchor_x, anchor_y = (0, 0)
    else:
        anchor_x, anchor_y = _best_integer_anchor(shape.vertices)
    centered = tuple((x - anchor_x, y - anchor_y) for x, y in shape.vertices)
    orbit = {
        tuple(sorted(d4_transforms(x, y)[transform] for x, y in centered))
        for transform in range(8)
    }
    return tuple(sorted(orbit))


def local_decomposition(
    length: int = 15,
) -> tuple[tuple[tuple[tuple[int, int], ...], ...], np.ndarray]:
    """Build and exactly verify local orbits and their counting multiplicities."""

    basis = OperatorBasis(length, EVEN_SHAPES)
    all_orbits = []
    multiplicities = []
    for shape, instances in zip(EVEN_SHAPES, basis.instances):
        orbit = anchored_d4_orbit(shape)
        expected = {tuple(int(site) for site in row): 0 for row in instances}
        for x in range(length):
            for y in range(length):
                for orientation in orbit:
                    sites = tuple(
                        sorted(
                            ((x + dx) % length) * length + ((y + dy) % length)
                            for dx, dy in orientation
                        )
                    )
                    if sites not in expected:
                        raise AssertionError(
                            f"local decomposition generated an extra {shape.name} instance"
                        )
                    expected[sites] += 1
        counts = set(expected.values())
        if len(counts) != 1 or next(iter(counts)) <= 0:
            raise AssertionError(
                f"local decomposition has nonuniform multiplicity for {shape.name}"
            )
        all_orbits.append(orbit)
        multiplicities.append(next(iter(counts)))
    return tuple(all_orbits), np.asarray(multiplicities, dtype=np.float64)


def uniform_patches(
    rng: np.random.Generator, samples: int, radius: int = 3
) -> np.ndarray:
    values = rng.integers(
        0, 2, size=(samples, 2 * radius + 1, 2 * radius + 1), dtype=np.int8
    )
    return 2 * values - 1


def features_from_patches(model: D4EvenLocalMLP, patches: np.ndarray) -> np.ndarray:
    patches = np.asarray(patches, dtype=np.int8)
    width = 2 * model.radius + 1
    if patches.ndim != 3 or patches.shape[1:] != (width, width):
        raise ValueError("patches have the wrong shape")
    flat = patches.reshape(patches.shape[0], -1)
    assignments = model.offset_feature.reshape(-1)
    features = np.empty((patches.shape[0], model.n_features), dtype=np.float64)
    for feature in range(model.n_features):
        features[:, feature] = flat[:, assignments == feature].mean(axis=1)
    return features


def local_hamiltonian_density(
    patches: np.ndarray,
    couplings: np.ndarray,
    orbits: tuple[tuple[tuple[tuple[int, int], ...], ...], ...],
    multiplicities: np.ndarray,
) -> np.ndarray:
    """Return the exact local density whose lattice sum is ``K dot S``."""

    patches = np.asarray(patches, dtype=np.int8)
    couplings = np.asarray(couplings, dtype=np.float64)
    if couplings.shape != (len(EVEN_SHAPES),):
        raise ValueError("couplings must contain 13 values")
    radius = (patches.shape[1] - 1) // 2
    result = np.zeros(patches.shape[0], dtype=np.float64)
    for coupling, orbit, multiplicity in zip(couplings, orbits, multiplicities):
        orbit_sum = np.zeros(patches.shape[0], dtype=np.float64)
        for orientation in orbit:
            product = np.ones(patches.shape[0], dtype=np.float64)
            for dx, dy in orientation:
                if abs(dx) > radius or abs(dy) > radius:
                    raise ValueError("local decomposition exceeds the supplied patch")
                product *= patches[:, radius + dx, radius + dy]
            orbit_sum += product
        result -= coupling * orbit_sum / multiplicity
    return result


def weighted_density_gradient(
    model: D4EvenLocalMLP, features: np.ndarray, weights: np.ndarray
) -> MLPGradient:
    """Gradient of ``sum_i weights[i] * density(features[i])``."""

    q = np.asarray(features, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != model.n_features:
        raise ValueError("features have the wrong shape")
    if weights.shape != (q.shape[0],):
        raise ValueError("weights have the wrong shape")
    grad_out = np.zeros_like(model.weight_out)
    grad_bias = np.zeros_like(model.bias_hidden)
    grad_in = np.zeros_like(model.weight_in)
    weighted = weights[:, None]
    for permutation in model.feature_permutations:
        transformed = q[:, permutation]
        z_plus = transformed @ model.weight_in.T + model.bias_hidden
        z_minus = -transformed @ model.weight_in.T + model.bias_hidden
        h_plus = np.tanh(z_plus)
        h_minus = np.tanh(z_minus)
        grad_out += (weighted * 0.5 * (h_plus + h_minus)).sum(axis=0)
        delta_plus = (1.0 - h_plus**2) * model.weight_out
        delta_minus = (1.0 - h_minus**2) * model.weight_out
        grad_bias += (weighted * 0.5 * (delta_plus + delta_minus)).sum(axis=0)
        grad_in += 0.5 * (
            (weighted * delta_plus).T @ transformed
            - (weighted * delta_minus).T @ transformed
        )
    symmetry_count = model.feature_permutations.shape[0]
    return MLPGradient(
        grad_in / symmetry_count,
        grad_bias / symmetry_count,
        grad_out / symmetry_count,
    )


def extract_patches(spins: np.ndarray, radius: int) -> np.ndarray:
    """Return one periodic raw patch per lattice site."""

    patches = []
    for x in range(spins.shape[0]):
        for y in range(spins.shape[1]):
            patch = np.empty((2 * radius + 1, 2 * radius + 1), dtype=np.int8)
            for ix, dx in enumerate(range(-radius, radius + 1)):
                for iy, dy in enumerate(range(-radius, radius + 1)):
                    patch[ix, iy] = spins[(x + dx) % spins.shape[0], (y + dy) % spins.shape[1]]
            patches.append(patch)
    return np.asarray(patches, dtype=np.int8)


def evaluate_local(
    model: D4EvenLocalMLP,
    rng: np.random.Generator,
    samples: int,
    couplings: np.ndarray,
    orbits: tuple[tuple[tuple[tuple[int, int], ...], ...], ...],
    multiplicities: np.ndarray,
) -> dict:
    squared_error = 0.0
    squared_target = 0.0
    maximum_error = 0.0
    count = 0
    chunk = 2000
    while count < samples:
        current = min(chunk, samples - count)
        patches = uniform_patches(rng, current, model.radius)
        features = features_from_patches(model, patches)
        target = -local_hamiltonian_density(patches, couplings, orbits, multiplicities)
        prediction = model.density_from_features(features)
        residual = prediction - target
        squared_error += float(np.dot(residual, residual))
        centered = target - target.mean()
        squared_target += float(np.dot(centered, centered))
        maximum_error = max(maximum_error, float(np.max(np.abs(residual))))
        count += current
    return {
        "samples": samples,
        "rmse": float(np.sqrt(squared_error / samples)),
        "maximum_absolute_error": maximum_error,
        "r_squared": 1.0 - squared_error / squared_target,
    }


def project_global_energy(
    model: D4EvenLocalMLP,
    rng: np.random.Generator,
    samples: int,
    length: int,
    couplings: np.ndarray,
) -> dict:
    basis = OperatorBasis(length, EVEN_SHAPES)
    n_sites = length**2
    x = np.empty((samples, len(EVEN_SHAPES)), dtype=np.float64)
    learned = np.empty(samples, dtype=np.float64)
    oracle = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(length, length))
        x[index] = basis.values(spins) / n_sites
        learned[index] = -model.energy(spins) / n_sites
        oracle[index] = float(x[index] @ couplings)
    order = rng.permutation(samples)
    training = order[: int(0.8 * samples)]
    validation = order[int(0.8 * samples) :]
    parameters, rank, singular = fit_operator_projection(x[training], learned[training])
    oracle_parameters, oracle_rank, _ = fit_operator_projection(x[training], oracle[training])
    prediction = parameters[0] + x[validation] @ parameters[1:]
    residual_energy = learned[validation] - prediction
    centered = learned[validation] - learned[validation].mean()
    projected = parameters[1:]
    residual = projected - couplings
    linf = float(np.max(np.abs(residual)))
    relative = float(np.linalg.norm(residual) / np.linalg.norm(couplings))
    passed = linf <= ABSOLUTE_COUPLING_TOLERANCE and relative <= RELATIVE_L2_TOLERANCE
    return {
        "status": "PASS" if passed else "FAIL",
        "samples": samples,
        "rank": int(rank),
        "condition_number": float(singular[0] / singular[-1]),
        "validation_r_squared": 1.0 - float(
            np.dot(residual_energy, residual_energy) / np.dot(centered, centered)
        ),
        "validation_rmse_per_site": float(np.sqrt(np.mean(residual_energy**2))),
        "projected_couplings": projected.tolist(),
        "coupling_residuals": residual.tolist(),
        "linf_residual": linf,
        "relative_l2_residual": relative,
        "absolute_tolerance": ABSOLUTE_COUPLING_TOLERANCE,
        "relative_l2_tolerance": RELATIVE_L2_TOLERANCE,
        "oracle_rank": int(oracle_rank),
        "oracle_linf_residual": float(
            np.max(np.abs(oracle_parameters[1:] - couplings))
        ),
    }


def run(
    output: Path,
    preset: str,
    fixed_point_map: Path,
    model_seed: int,
    training_seed: int,
    evaluation_seed: int,
    projection_seed: int,
) -> dict:
    settings = PRESETS[preset]
    source = read_json(fixed_point_map)
    couplings = np.asarray(source["input_couplings"], dtype=np.float64)
    if couplings.shape != (len(EVEN_SHAPES),):
        raise ValueError("fixed-point map must contain 13 input couplings")
    output.mkdir(parents=True, exist_ok=True)
    orbits, multiplicities = local_decomposition(15)
    model = D4EvenLocalMLP.random(
        radius=3, hidden=32, seed=model_seed, feature_mode="multiscale"
    )
    optimizer = Adam(model, learning_rate=0.002)
    rng = np.random.default_rng(training_seed)
    trajectory = []
    start = time.perf_counter()
    for step in range(1, int(settings["steps"]) + 1):
        patches = uniform_patches(rng, int(settings["batch"]), model.radius)
        features = features_from_patches(model, patches)
        target = -local_hamiltonian_density(patches, couplings, orbits, multiplicities)
        prediction = model.density_from_features(features)
        residual = prediction - target
        gradient = weighted_density_gradient(
            model, features, 2.0 * residual / residual.size
        )
        optimizer.update(model, gradient)
        if step == 1 or step % max(1, int(settings["steps"]) // 20) == 0:
            rmse = float(np.sqrt(np.mean(residual**2)))
            trajectory.append((step, rmse, gradient.norm()))
            print(
                f"supervised {step}/{settings['steps']} rmse={rmse:.8g} grad={gradient.norm():.8g}",
                flush=True,
            )
    elapsed = time.perf_counter() - start
    evaluation = evaluate_local(
        model,
        np.random.default_rng(evaluation_seed),
        int(settings["evaluation_samples"]),
        couplings,
        orbits,
        multiplicities,
    )
    projection = project_global_energy(
        model,
        np.random.default_rng(projection_seed),
        int(settings["projection_samples"]),
        15,
        couplings,
    )
    model.save(str(output / "supervised_model.npz"))
    np.savez_compressed(output / "trajectory.npz", records=np.asarray(trajectory))
    report = {
        "status": projection["status"],
        "experiment": "direct_supervised_identity_rg_13_term_representability",
        "target_relation": "V_theta=-H_for_identity_RG_uniform_reference",
        "preset": preset,
        "steps": int(settings["steps"]),
        "batch_size": int(settings["batch"]),
        "learning_rate": 0.002,
        "elapsed_seconds": elapsed,
        "model": "d4_z2_radius3_multiscale_mlp_hidden32",
        "couplings": couplings.tolist(),
        "operator_names": [shape.name for shape in EVEN_SHAPES],
        "local_orbit_multiplicities": multiplicities.astype(int).tolist(),
        "local_evaluation": evaluation,
        "global_projection": projection,
        "seeds": {
            "model": model_seed,
            "training": training_seed,
            "evaluation": evaluation_seed,
            "projection": projection_seed,
        },
    }
    write_json(output / "supervised_identity_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=tuple(PRESETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixed-point-map", type=Path, required=True)
    parser.add_argument("--model-seed", type=int, default=202607271)
    parser.add_argument("--training-seed", type=int, default=202607272)
    parser.add_argument("--evaluation-seed", type=int, default=202607273)
    parser.add_argument("--projection-seed", type=int, default=202607274)
    args = parser.parse_args()
    report = run(
        args.output.resolve(),
        args.preset,
        args.fixed_point_map.resolve(),
        args.model_seed,
        args.training_seed,
        args.evaluation_seed,
        args.projection_seed,
    )
    if args.preset == "formal" and report["status"] != "PASS":
        raise RuntimeError("formal direct-supervision representability gate failed")


if __name__ == "__main__":
    main()
