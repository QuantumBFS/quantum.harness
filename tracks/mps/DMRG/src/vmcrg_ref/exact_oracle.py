"""Exact small-lattice VMCRG blocking and objective oracle.

The 3 x 6 rectangle is deliberately separate from the square neural identity
oracle: it is the smallest periodic lattice that contains two independent
3 x 3 majority blocks while still permitting complete enumeration.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
import time
from typing import Any

import numpy as np

from .neural_energy import D4EvenLocalMLP, MLPGradient


def _validate_rectangular_spins(spins: np.ndarray) -> np.ndarray:
    values = np.asarray(spins, dtype=np.int8)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise ValueError("spins must be a nonempty rectangular 2D array")
    if not np.all((values == -1) | (values == 1)):
        raise ValueError("spins must contain only -1 and +1")
    return values


def rectangular_ising_energy(spins: np.ndarray, coupling: float) -> float:
    values = _validate_rectangular_spins(spins)
    right = np.roll(values, -1, axis=1)
    down = np.roll(values, -1, axis=0)
    snn = -int(np.sum(values * (right + down), dtype=np.int64))
    return float(coupling) * snn


def exact_local_energy_delta(
    spins: np.ndarray,
    x: int,
    y: int,
    coupling: float,
    *,
    direct_only: bool = False,
) -> float:
    """Return a one-flip delta, or the direct energy when ``direct_only``."""
    values = _validate_rectangular_spins(spins)
    rows, cols = values.shape
    x %= rows
    y %= cols
    if direct_only:
        return rectangular_ising_energy(values, coupling)
    spin = int(values[x, y])
    neighbors = int(
        values[(x - 1) % rows, y]
        + values[(x + 1) % rows, y]
        + values[x, (y - 1) % cols]
        + values[x, (y + 1) % cols]
    )
    return float(coupling) * float(2 * spin * neighbors)


@dataclass(frozen=True)
class ExactBlockingResult:
    rows: int
    cols: int
    block_size: int
    coupling: float
    microstate_count: int
    coarse_shape: tuple[int, int]
    coarse_states: np.ndarray
    coarse_probability: np.ndarray
    coarse_nn: np.ndarray
    shifted_log_weight: float

    def __post_init__(self) -> None:
        for value in (
            self.coarse_states,
            self.coarse_probability,
            self.coarse_nn,
        ):
            value.setflags(write=False)

    @property
    def coarse_state_count(self) -> int:
        return int(self.coarse_probability.size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "block_size": self.block_size,
            "coupling": self.coupling,
            "microstate_count": self.microstate_count,
            "coarse_shape": list(self.coarse_shape),
            "coarse_state_count": self.coarse_state_count,
            "coarse_probability": self.coarse_probability.tolist(),
            "coarse_nn": self.coarse_nn.tolist(),
            "shifted_log_weight": self.shifted_log_weight,
        }


def _enumerate_coarse_states(rows: int, cols: int) -> np.ndarray:
    count = rows * cols
    labels = np.arange(1 << count, dtype=np.uint64)[:, None]
    bits = ((labels >> np.arange(count, dtype=np.uint64)) & 1).astype(np.int8)
    return (2 * bits - 1).reshape(-1, rows, cols)


def _coarse_indices(spins: np.ndarray, block_size: int) -> tuple[np.ndarray, np.ndarray]:
    batch, rows, cols = spins.shape
    coarse_rows = rows // block_size
    coarse_cols = cols // block_size
    reshaped = spins.reshape(batch, coarse_rows, block_size, coarse_cols, block_size)
    sums = reshaped.sum(axis=(2, 4), dtype=np.int64)
    if np.any(sums == 0):
        raise AssertionError("odd majority blocks cannot have a tied sum")
    coarse = np.where(sums > 0, 1, -1).astype(np.int8)
    flat = ((coarse.reshape(batch, -1) > 0).astype(np.uint64))
    shifts = np.arange(flat.shape[1], dtype=np.uint64)
    indices = np.sum(flat << shifts, axis=1, dtype=np.uint64).astype(np.int64)
    return indices, coarse


def _rectangular_snn_batch(spins: np.ndarray) -> np.ndarray:
    return -np.sum(
        spins * (np.roll(spins, -1, axis=2) + np.roll(spins, -1, axis=1)),
        axis=(1, 2),
        dtype=np.int64,
    )


def _coarse_nn_values(states: np.ndarray) -> np.ndarray:
    return _rectangular_snn_batch(states)


def enumerate_rectangular_blocking(
    rows: int,
    cols: int,
    block_size: int,
    coupling: float,
    *,
    chunk_size: int = 1 << 16,
) -> ExactBlockingResult:
    """Enumerate all microscopic states and aggregate their exact coarse law."""
    rows, cols, block_size = int(rows), int(cols), int(block_size)
    coupling = float(coupling)
    if rows <= 0 or cols <= 0:
        raise ValueError("lattice dimensions must be positive")
    if block_size <= 0 or block_size % 2 == 0:
        raise ValueError("block_size must be a positive odd integer")
    if rows % block_size or cols % block_size:
        raise ValueError("lattice dimensions must be divisible by block_size")
    if not np.isfinite(coupling):
        raise ValueError("coupling must be finite")
    n_sites = rows * cols
    if n_sites > 62:
        raise ValueError("exact enumeration is limited to at most 62 spins")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    coarse_rows, coarse_cols = rows // block_size, cols // block_size
    coarse_count = coarse_rows * coarse_cols
    microstate_count = 1 << n_sites
    coarse_weights = np.zeros(1 << coarse_count, dtype=np.float64)
    max_log_weight = -np.inf
    # First pass obtains a common shift without retaining microscopic states.
    for start in range(0, microstate_count, chunk_size):
        stop = min(microstate_count, start + chunk_size)
        labels = np.arange(start, stop, dtype=np.uint64)[:, None]
        bits = ((labels >> np.arange(n_sites, dtype=np.uint64)) & 1).astype(np.int8)
        spins = (2 * bits - 1).reshape(-1, rows, cols)
        energies = coupling * _rectangular_snn_batch(spins)
        max_log_weight = max(max_log_weight, float(np.max(-energies)))

    for start in range(0, microstate_count, chunk_size):
        stop = min(microstate_count, start + chunk_size)
        labels = np.arange(start, stop, dtype=np.uint64)[:, None]
        bits = ((labels >> np.arange(n_sites, dtype=np.uint64)) & 1).astype(np.int8)
        spins = (2 * bits - 1).reshape(-1, rows, cols)
        snn = _rectangular_snn_batch(spins).astype(np.float64)
        log_weight = -coupling * snn - max_log_weight
        indices, _ = _coarse_indices(spins, block_size)
        np.add.at(coarse_weights, indices, np.exp(log_weight))

    total = float(coarse_weights.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise FloatingPointError("exact coarse weights are not finite")
    coarse_states = _enumerate_coarse_states(coarse_rows, coarse_cols)
    probability = coarse_weights / total
    return ExactBlockingResult(
        rows=rows,
        cols=cols,
        block_size=block_size,
        coupling=coupling,
        microstate_count=microstate_count,
        coarse_shape=(coarse_rows, coarse_cols),
        coarse_states=coarse_states,
        coarse_probability=probability,
        coarse_nn=_coarse_nn_values(coarse_states),
        shifted_log_weight=max_log_weight,
    )


def _validate_probability(probability: np.ndarray, expected: int, name: str) -> np.ndarray:
    values = np.asarray(probability, dtype=np.float64)
    if values.ndim != 1 or values.size != expected:
        raise ValueError(f"{name} probability has the wrong shape")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError(f"{name} probability must be finite and nonnegative")
    if not np.isclose(float(values.sum()), 1.0, atol=1e-12, rtol=0.0):
        raise ValueError(f"{name} probability must sum to one")
    return values


def target_distribution_distances(
    probability: np.ndarray,
    target_probability: np.ndarray,
) -> dict[str, float]:
    p = _validate_probability(probability, len(probability), "coarse")
    q = _validate_probability(target_probability, p.size, "target")
    mixture = 0.5 * (p + q)
    positive_p = p > 0.0
    positive_q = q > 0.0
    kl_pq = float(np.sum(p[positive_p] * np.log(p[positive_p] / q[positive_p]))) if np.all(q[positive_p] > 0) else float("inf")
    kl_qp = float(np.sum(q[positive_q] * np.log(q[positive_q] / p[positive_q]))) if np.all(p[positive_q] > 0) else float("inf")
    js = 0.5 * (
        float(np.sum(p[positive_p] * np.log(p[positive_p] / mixture[positive_p])))
        + float(np.sum(q[positive_q] * np.log(q[positive_q] / mixture[positive_q])))
    )
    return {
        "total_variation": 0.5 * float(np.sum(np.abs(p - q))),
        "jensen_shannon": js,
        "kl_coarse_target": kl_pq,
        "kl_target_coarse": kl_qp,
    }


def exact_objective(
    result: ExactBlockingResult,
    bias_energy: np.ndarray,
    target_probability: np.ndarray,
) -> float:
    """Return log E_p[exp(-V)] + E_target[V] for total energies."""
    bias = np.asarray(bias_energy, dtype=np.float64)
    if bias.ndim != 1 or bias.size != result.coarse_state_count:
        raise ValueError("bias energy has the wrong shape")
    if not np.all(np.isfinite(bias)):
        raise ValueError("bias energy must be finite")
    target = _validate_probability(
        target_probability,
        result.coarse_state_count,
        "target",
    )
    log_terms = np.log(result.coarse_probability) - bias
    maximum = float(np.max(log_terms))
    log_ratio = maximum + float(np.log(np.exp(log_terms - maximum).sum()))
    return log_ratio + float(target @ bias)


def exact_objective_per_site(
    result: ExactBlockingResult,
    bias_energy: np.ndarray,
    target_probability: np.ndarray,
) -> float:
    coarse_sites = result.coarse_shape[0] * result.coarse_shape[1]
    return exact_objective(result, bias_energy, target_probability) / float(
        coarse_sites
    )


def exact_parameter_gradient(
    result: ExactBlockingResult,
    features: np.ndarray,
    parameters: np.ndarray,
    target_probability: np.ndarray,
) -> np.ndarray:
    design = np.asarray(features, dtype=np.float64)
    theta = np.asarray(parameters, dtype=np.float64)
    if design.ndim != 2 or design.shape[0] != result.coarse_state_count:
        raise ValueError("features have the wrong shape")
    if theta.ndim != 1 or theta.size != design.shape[1]:
        raise ValueError("parameters have the wrong shape")
    if not np.all(np.isfinite(design)) or not np.all(np.isfinite(theta)):
        raise ValueError("features and parameters must be finite")
    target = _validate_probability(
        target_probability,
        result.coarse_state_count,
        "target",
    )
    bias = design @ theta
    log_terms = np.log(result.coarse_probability) - bias
    maximum = float(np.max(log_terms))
    tilted = np.exp(log_terms - maximum)
    tilted /= tilted.sum()
    return target @ design - tilted @ design


def exact_handoff_energy(bias_energy: np.ndarray) -> np.ndarray:
    values = np.asarray(bias_energy, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("bias energy must be finite")
    return -values.copy()


def flatten_mlp_gradient(gradient: MLPGradient) -> np.ndarray:
    """Flatten gradients in the checkpoint order used by the neural model."""
    return np.concatenate(
        (
            np.asarray(gradient.weight_in, dtype=np.float64).reshape(-1),
            np.asarray(gradient.bias_hidden, dtype=np.float64).reshape(-1),
            np.asarray(gradient.weight_out, dtype=np.float64).reshape(-1),
        )
    )


def _load_jax() -> tuple[Any, Any]:
    try:
        import jax
        import jax.numpy as jnp
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise ImportError(
            "JAX is required for the N0 automatic-differentiation oracle; "
            "run `make install jax EXTRA=cpu`"
        ) from error
    jax.config.update("jax_enable_x64", True)
    return jax, jnp


def _jax_total_energies(
    states: Any,
    parameters: tuple[Any, Any, Any],
    model: D4EvenLocalMLP,
    jnp: Any,
) -> Any:
    if model.feature_mode != "shell":
        raise ValueError("the N0 JAX oracle currently uses the shell feature mode")
    values = jnp.asarray(states, dtype=jnp.float64)
    if values.ndim != 3:
        raise ValueError("JAX states must have shape (batch, length, length)")
    batch, length, width = values.shape
    if length != width or length < 2 * model.radius + 1:
        raise ValueError("JAX states are incompatible with the model radius")
    feature_count = model.n_features
    features = jnp.zeros((batch, length, width, feature_count), dtype=jnp.float64)
    for ix, dx in enumerate(range(-model.radius, model.radius + 1)):
        for iy, dy in enumerate(range(-model.radius, model.radius + 1)):
            feature = int(model.offset_feature[ix, iy])
            shifted = jnp.roll(values, shift=(-dx, -dy), axis=(1, 2))
            features = features.at[:, :, :, feature].add(shifted)
    features = features / jnp.asarray(model.shell_counts, dtype=jnp.float64).reshape(
        1, 1, 1, -1
    )
    weight_in, bias_hidden, weight_out = parameters
    flat = features.reshape(-1, feature_count)
    density = jnp.zeros((flat.shape[0],), dtype=jnp.float64)
    for permutation in model.feature_permutations:
        transformed = flat[:, jnp.asarray(permutation)]
        plus = jnp.tanh(transformed @ weight_in.T + bias_hidden)
        minus = jnp.tanh(-transformed @ weight_in.T + bias_hidden)
        density = density + 0.5 * (plus + minus) @ weight_out
    density = density / float(model.feature_permutations.shape[0])
    return density.reshape(batch, length, width).sum(axis=(1, 2))


def jax_exact_neural_gradient(
    states: np.ndarray,
    probabilities: np.ndarray,
    target_states: np.ndarray,
    model: D4EvenLocalMLP,
) -> np.ndarray:
    """Differentiate the exact total-energy objective with JAX in float64."""
    jax, jnp = _load_jax()
    state_values = np.asarray(states, dtype=np.int8)
    target_values = np.asarray(target_states, dtype=np.int8)
    probabilities = np.asarray(probabilities, dtype=np.float64)
    if state_values.ndim != 3 or target_values.ndim != 3:
        raise ValueError("states and target_states must be rank-three arrays")
    if probabilities.ndim != 1 or probabilities.size != state_values.shape[0]:
        raise ValueError("probabilities have the wrong shape")
    if not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0.0):
        raise ValueError("probabilities must be finite and nonnegative")
    if not np.isclose(probabilities.sum(), 1.0, atol=1e-12, rtol=0.0):
        raise ValueError("probabilities must sum to one")
    if state_values.shape[1:] != target_values.shape[1:]:
        raise ValueError("states and target_states have incompatible lattice shapes")
    parameters = tuple(
        jnp.asarray(value, dtype=jnp.float64)
        for value in (model.weight_in, model.bias_hidden, model.weight_out)
    )
    jax_states = jnp.asarray(state_values, dtype=jnp.float64)
    jax_target = jnp.asarray(target_values, dtype=jnp.float64)
    jax_probabilities = jnp.asarray(probabilities, dtype=jnp.float64)

    def objective(params: tuple[Any, Any, Any]) -> Any:
        state_energy = _jax_total_energies(jax_states, params, model, jnp)
        target_energy = _jax_total_energies(jax_target, params, model, jnp)
        return jax.scipy.special.logsumexp(
            jnp.log(jax_probabilities) - state_energy
        ) + jnp.mean(target_energy)

    gradients = jax.grad(objective)(parameters)
    return np.concatenate([np.asarray(value, dtype=np.float64).reshape(-1) for value in gradients])


def _numpy_model_objective(
    states: np.ndarray,
    probabilities: np.ndarray,
    target_states: np.ndarray,
    model: D4EvenLocalMLP,
) -> float:
    energies = np.asarray([model.energy(state) for state in states], dtype=np.float64)
    target_energies = np.asarray(
        [model.energy(state) for state in target_states], dtype=np.float64
    )
    log_terms = np.log(probabilities) - energies
    maximum = float(np.max(log_terms))
    return maximum + float(np.log(np.exp(log_terms - maximum).sum())) + float(
        target_energies.mean()
    )


def _model_from_flat(model: D4EvenLocalMLP, flat: np.ndarray) -> D4EvenLocalMLP:
    flat = np.asarray(flat, dtype=np.float64)
    first = model.weight_in.size
    second = first + model.bias_hidden.size
    return D4EvenLocalMLP(
        model.radius,
        model.hidden,
        flat[:first].reshape(model.weight_in.shape),
        flat[first:second].copy(),
        flat[second:].copy(),
        feature_mode=model.feature_mode,
    )


def _analytic_neural_objective_gradient(
    states: np.ndarray,
    probabilities: np.ndarray,
    target_states: np.ndarray,
    model: D4EvenLocalMLP,
) -> tuple[np.ndarray, np.ndarray]:
    energies = np.asarray([model.energy(state) for state in states], dtype=np.float64)
    target_gradients = np.stack(
        [flatten_mlp_gradient(model.gradient(state)) for state in target_states]
    )
    state_gradients = np.stack(
        [flatten_mlp_gradient(model.gradient(state)) for state in states]
    )
    log_terms = np.log(probabilities) - energies
    maximum = float(np.max(log_terms))
    tilted = np.exp(log_terms - maximum)
    tilted /= tilted.sum()
    exact = target_gradients.mean(axis=0) - tilted @ state_gradients
    return exact, tilted


def compare_small_neural_gradients(
    length: int,
    radius: int,
    hidden: int,
    seed: int,
) -> dict[str, Any]:
    """Compare JAX, analytic, finite-difference, exact, and MC gradients."""
    if length != 3 or radius != 1:
        raise ValueError("the frozen small neural oracle uses length=3 and radius=1")
    rng = np.random.default_rng(seed)
    model = D4EvenLocalMLP.random(
        radius=radius,
        hidden=hidden,
        seed=seed,
        feature_mode="shell",
    )
    model.weight_out[:] = rng.normal(0.0, 0.08, model.hidden)
    labels = np.arange(1 << (length * length), dtype=np.uint64)[:, None]
    bits = ((labels >> np.arange(length * length, dtype=np.uint64)) & 1).astype(np.int8)
    states = (2 * bits - 1).reshape(-1, length, length)
    snn = -np.sum(
        states * (np.roll(states, -1, axis=2) + np.roll(states, -1, axis=1)),
        axis=(1, 2),
        dtype=np.int64,
    )
    microscopic_log_weight = -0.21 * snn.astype(np.float64)
    microscopic_log_weight -= microscopic_log_weight.max()
    probabilities = np.exp(microscopic_log_weight)
    probabilities /= probabilities.sum()
    target_states = states.copy()
    exact, tilted = _analytic_neural_objective_gradient(
        states,
        probabilities,
        target_states,
        model,
    )
    started = time.perf_counter()
    jax_gradient = jax_exact_neural_gradient(
        states,
        probabilities,
        target_states,
        model,
    )
    compile_seconds = time.perf_counter() - started
    # A second call is the steady-state timing, excluding first compilation.
    started = time.perf_counter()
    _ = jax_exact_neural_gradient(states, probabilities, target_states, model)
    steady_seconds = time.perf_counter() - started

    flat = flatten_mlp_gradient(
        MLPGradient(model.weight_in, model.bias_hidden, model.weight_out)
    )
    finite_difference = np.empty_like(flat)
    epsilon = 1e-6
    for index in range(flat.size):
        plus = flat.copy()
        minus = flat.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        finite_difference[index] = (
            _numpy_model_objective(states, probabilities, target_states, _model_from_flat(model, plus))
            - _numpy_model_objective(states, probabilities, target_states, _model_from_flat(model, minus))
        ) / (2.0 * epsilon)

    sample_count = 100_000
    sample_indices = rng.choice(states.shape[0], size=sample_count, p=tilted)
    state_gradients = np.stack(
        [flatten_mlp_gradient(model.gradient(state)) for state in states]
    )
    target_gradient = state_gradients.mean(axis=0)
    mc_gradient = target_gradient - state_gradients[sample_indices].mean(axis=0)
    sample_variance = state_gradients[sample_indices].var(axis=0, ddof=1)
    standard_error = np.sqrt(sample_variance / sample_count)
    z = np.divide(
        mc_gradient - exact,
        standard_error,
        out=np.zeros_like(exact),
        where=standard_error > 0.0,
    )
    jax, _ = _load_jax()
    family_alpha = 0.05
    critical_abs_z = NormalDist().inv_cdf(
        1.0 - family_alpha / (2.0 * flat.size)
    )

    return {
        "length": length,
        "radius": radius,
        "hidden": hidden,
        "parameter_count": int(flat.size),
        "jax_devices": [str(device) for device in jax.devices()],
        "jax_platform": str(jax.default_backend()),
        "jax_enable_x64": True,
        "jax_compile_seconds": compile_seconds,
        "jax_steady_state_seconds": steady_seconds,
        "jax_gradient": jax_gradient.tolist(),
        "analytic_gradient": exact.tolist(),
        "finite_difference_gradient": finite_difference.tolist(),
        "mc_gradient": mc_gradient.tolist(),
        "mc_z_scores": z.tolist(),
        "mc_sample_count": sample_count,
        "mc_family_alpha": family_alpha,
        "mc_multiple_testing_method": "two_sided_bonferroni",
        "mc_bonferroni_critical_abs_z": critical_abs_z,
        "jax_vs_analytic_linf": float(np.max(np.abs(jax_gradient - exact))),
        "jax_vs_finite_difference_linf": float(
            np.max(np.abs(jax_gradient - finite_difference))
        ),
        "exact_vs_mc_max_abs_z": float(np.max(np.abs(z))),
        "exact_vs_mc_all_z_below": bool(np.max(np.abs(z)) <= critical_abs_z),
    }
