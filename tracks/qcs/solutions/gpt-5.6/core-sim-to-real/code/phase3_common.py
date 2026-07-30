#!/usr/bin/env python3
"""Shared, audited machinery for QL1F research attempts 11--20.

The model side may use derivatives of the nominal simulator.  A calibration
algorithm receives only ``query(parameters, shots=None) -> fidelity``.  Truth
derivatives in this module are diagnostics and must be evaluated only after a
black-box calibration run has completed.
"""

from __future__ import annotations

import hashlib
import math
import os
import platform
from dataclasses import dataclass
from typing import Any, Callable

os.environ.setdefault("JAX_PLATFORMS", "cpu")

DIMENSION = 4
N_CONTROLS = 4
N_BASIS = 10
PARAMETER_COUNT = N_CONTROLS * N_BASIS
T_FINAL = 1.0
NOMINAL_SEED = 42
TARGET = 1.0e-3
TARGET_LADDER = (1.0e-3, 3.0e-4, 1.0e-4, 3.0e-5)
CYCLES = 2
POINTS_PER_LINE = 5
TARGET_LINE_INFIDELITY = 1.0e-3
MIN_SCAN_HALF_WIDTH = 1.0e-2
MAX_SCAN_HALF_WIDTH = 2.5e-1

DEVELOPMENT_TRUTH_SEEDS = tuple(range(260605, 260613))
CONFIRMATION_TRUTH_SEEDS = tuple(range(260613, 260621))
SECOND_CONFIRMATION_TRUTH_SEEDS = tuple(range(260621, 260629))
TRUTH_SEEDS = (
    DEVELOPMENT_TRUTH_SEEDS
    + CONFIRMATION_TRUTH_SEEDS
    + SECOND_CONFIRMATION_TRUTH_SEEDS
)
TRUTH_EPSILONS = (0.005, 0.02, 0.05, 0.10)
TRUTH_FAMILIES = ("control-map", "drift", "combined")


def array_sha256(value: Any) -> str:
    import numpy as np

    array = np.ascontiguousarray(value, dtype="<f8")
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def infer_spectral_gap_rank(eigenvalues_ascending: Any) -> dict[str, Any]:
    import numpy as np

    eigenvalues = np.asarray(eigenvalues_ascending, dtype=np.float64)
    radius = float(np.max(np.abs(eigenvalues)))
    tolerance = math.sqrt(float(np.finfo(np.float64).eps)) * radius
    positive = eigenvalues[eigenvalues > tolerance]
    if positive.size < 2:
        return {
            "candidate_effective_rank": int(positive.size),
            "positive_eigenvalue_tolerance": tolerance,
            "ratio": None,
        }
    ratios = positive[1:] / positive[:-1]
    gap_index = int(np.argmax(ratios))
    upper = float(positive[gap_index + 1])
    return {
        "candidate_effective_rank": int(np.count_nonzero(eigenvalues >= upper)),
        "lower_eigenvalue": float(positive[gap_index]),
        "positive_eigenvalue_tolerance": tolerance,
        "ratio": float(ratios[gap_index]),
        "upper_eigenvalue": upper,
    }


@dataclass
class NominalModel:
    """Numerical model and its model-only local geometry."""

    target: Any
    h_drift: Any
    h_controls: Any
    initial_parameters: Any
    optimized_parameters: Any
    hessian: Any
    eigenvalues: Any
    eigenvectors: Any
    inferred_rank: int
    optimizer_summary: dict[str, Any]
    average_fidelity: Callable[..., Any]
    infidelity_value_and_grad: Callable[..., Any]
    infidelity_hessian: Callable[..., Any]


def build_nominal_model(verbose: bool = True) -> NominalModel:
    """Reproduce the seed-42 notebook model and nominal BFGS solution."""

    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import numpy as np
    from jax.experimental import ode
    from scipy import optimize

    target = jnp.array(
        [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
        dtype=jnp.complex128,
    )
    key = jax.random.PRNGKey(NOMINAL_SEED)
    key, *subkeys = jax.random.split(key, 3)
    h_drift = jax.random.normal(subkeys[0], (DIMENSION, DIMENSION))
    h_drift = h_drift + 1j * jax.random.normal(
        subkeys[1], (DIMENSION, DIMENSION)
    )
    h_drift = (h_drift + h_drift.conj().T) / 2

    controls = []
    for _ in range(N_CONTROLS):
        key, *subkeys = jax.random.split(key, 3)
        operator = jax.random.normal(subkeys[0], (DIMENSION, DIMENSION))
        operator = operator + 1j * jax.random.normal(
            subkeys[1], (DIMENSION, DIMENSION)
        )
        controls.append((operator + operator.conj().T) / 2)
    h_controls = jnp.stack(controls)
    key, initial_key = jax.random.split(key)
    initial_parameters = (
        jax.random.normal(initial_key, (PARAMETER_COUNT,)) * 0.01
    )
    mode_numbers = jnp.arange(N_BASIS) + 1

    def rhs(unitary: Any, t: Any, parameters: Any, drift: Any, ctrls: Any) -> Any:
        coefficient_matrix = parameters.reshape(N_CONTROLS, N_BASIS)
        sine_values = jnp.sin(mode_numbers * jnp.pi * t / T_FINAL)
        amplitudes = coefficient_matrix @ sine_values
        hamiltonian = drift + jnp.einsum("i,iab->ab", amplitudes, ctrls)
        return -1j * hamiltonian @ unitary

    def average_fidelity(
        parameters: Any, drift: Any, ctrls: Any
    ) -> Any:
        trajectory = ode.odeint(
            rhs,
            jnp.eye(DIMENSION, dtype=jnp.complex128),
            jnp.array([0.0, T_FINAL]),
            parameters,
            drift,
            ctrls,
        )
        overlap = jnp.trace(target.conj().T @ trajectory[-1])
        return (jnp.abs(overlap) ** 2 + DIMENSION) / (
            DIMENSION * (DIMENSION + 1)
        )

    average_fidelity_jit = jax.jit(average_fidelity)

    def infidelity(parameters: Any, drift: Any, ctrls: Any) -> Any:
        return 1.0 - average_fidelity(parameters, drift, ctrls)

    value_and_grad = jax.jit(jax.value_and_grad(infidelity, argnums=0))
    # odeint exposes a custom VJP and therefore cannot be differentiated with
    # the forward-over-reverse implementation selected by jax.hessian.
    hessian = jax.jit(
        jax.jacrev(jax.jacrev(infidelity, argnums=0), argnums=0)
    )

    calls = 0

    def objective(parameters: Any) -> tuple[float, Any]:
        nonlocal calls
        calls += 1
        value, gradient = value_and_grad(
            jnp.asarray(parameters), h_drift, h_controls
        )
        return float(np.asarray(value)), np.asarray(gradient, dtype=np.float64)

    if verbose:
        print("[phase3] optimizing notebook-exact nominal model", flush=True)
    result = optimize.minimize(
        objective,
        np.asarray(initial_parameters, dtype=np.float64),
        jac=True,
        method="BFGS",
    )
    optimized = np.asarray(result.x, dtype=np.float64)
    raw_hessian = np.asarray(
        hessian(jnp.asarray(optimized), h_drift, h_controls),
        dtype=np.float64,
    )
    symmetric_hessian = 0.5 * (raw_hessian + raw_hessian.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric_hessian)
    gap = infer_spectral_gap_rank(eigenvalues)
    inferred_rank = int(gap["candidate_effective_rank"])
    if verbose:
        print(
            f"[phase3] nominal infidelity={float(result.fun):.3e}; "
            f"rank={inferred_rank}; hash={array_sha256(optimized)[:12]}",
            flush=True,
        )
    return NominalModel(
        target=target,
        h_drift=h_drift,
        h_controls=h_controls,
        initial_parameters=np.asarray(initial_parameters, dtype=np.float64),
        optimized_parameters=optimized,
        hessian=symmetric_hessian,
        eigenvalues=eigenvalues,
        eigenvectors=eigenvectors,
        inferred_rank=inferred_rank,
        optimizer_summary={
            "success": bool(result.success),
            "status": int(result.status),
            "iterations": int(result.nit),
            "function_calls": calls,
            "final_infidelity": float(result.fun),
            "gradient_norm": float(np.linalg.norm(result.jac)),
            "parameter_sha256": array_sha256(optimized),
            "spectral_gap": gap,
        },
        average_fidelity=average_fidelity_jit,
        infidelity_value_and_grad=value_and_grad,
        infidelity_hessian=hessian,
    )


def _hermitian_unit_frobenius(rng: Any) -> Any:
    import numpy as np

    raw = rng.normal(size=(DIMENSION, DIMENSION)) + 1j * rng.normal(
        size=(DIMENSION, DIMENSION)
    )
    hermitian = (raw + raw.conj().T) / 2
    hermitian -= np.trace(hermitian) * np.eye(DIMENSION) / DIMENSION
    return hermitian / np.linalg.norm(hermitian, ord="fro")


def make_truth(
    model: NominalModel, family: str, epsilon: float, seed: int
) -> tuple[Any, Any, dict[str, Any]]:
    """Create paired deterministic mismatch components for a truth cell."""

    import numpy as np

    if family not in TRUTH_FAMILIES:
        raise ValueError(f"unknown truth family {family!r}")
    if epsilon not in TRUTH_EPSILONS:
        raise ValueError(f"epsilon {epsilon!r} is not frozen")
    if seed not in TRUTH_SEEDS:
        raise ValueError(f"seed {seed!r} is not frozen")

    seed_sequence = np.random.SeedSequence([113, 11, int(seed)])
    map_ss, drift_ss = seed_sequence.spawn(2)
    map_rng = np.random.default_rng(map_ss)
    drift_rng = np.random.default_rng(drift_ss)

    mismatch = map_rng.normal(size=(N_CONTROLS, N_CONTROLS))
    mismatch /= np.linalg.norm(mismatch, ord=2)
    control_map = np.eye(N_CONTROLS) + float(epsilon) * mismatch

    drift_direction = _hermitian_unit_frobenius(drift_rng)
    nominal_drift = np.asarray(model.h_drift, dtype=np.complex128)
    nominal_controls = np.asarray(model.h_controls, dtype=np.complex128)
    drift_scale = np.linalg.norm(nominal_drift, ord="fro")

    true_drift = np.array(nominal_drift, copy=True)
    true_controls = np.array(nominal_controls, copy=True)
    if family in ("drift", "combined"):
        true_drift += float(epsilon) * drift_scale * drift_direction
    if family in ("control-map", "combined"):
        true_controls = np.einsum(
            "ij,jab->iab", control_map, nominal_controls
        )
    metadata = {
        "family": family,
        "epsilon": float(epsilon),
        "seed": int(seed),
        "paired_seed_sequence": [113, 11, int(seed)],
        "control_map_minus_identity_spectral_norm": float(
            np.linalg.norm(control_map - np.eye(N_CONTROLS), ord=2)
        ),
        "relative_drift_frobenius_norm": float(
            np.linalg.norm(true_drift - nominal_drift, ord="fro") / drift_scale
        ),
        "true_drift_sha256": hashlib.sha256(
            np.ascontiguousarray(true_drift).view(np.float64).tobytes()
        ).hexdigest(),
        "true_controls_sha256": hashlib.sha256(
            np.ascontiguousarray(true_controls).view(np.float64).tobytes()
        ).hexdigest(),
    }
    return true_drift, true_controls, metadata


def model_bases(model: NominalModel) -> tuple[dict[str, tuple[Any, Any]], dict[str, Any]]:
    """Construct all attempt-11 search bases from nominal information only."""

    import numpy as np
    from scipy import linalg

    raw = np.eye(PARAMETER_COUNT, dtype=np.float64)
    descending = np.argsort(model.eigenvalues)[::-1]

    def principal(k: int) -> Any:
        directions = model.eigenvectors[:, descending[:k]].T.copy()
        directions /= np.linalg.norm(directions, axis=1, keepdims=True)
        return directions

    bases = {
        "raw-40": raw,
        "principal-8": principal(8),
        "principal-15": principal(15),
        "principal-20": principal(20),
    }
    p15 = bases["principal-15"]
    projector = p15.T @ p15
    leverage = np.diag(projector)
    _, _, pivots = linalg.qr(p15, mode="economic", pivoting=True)
    spanning = [int(value) for value in pivots[:15]]
    remaining = sorted(
        (index for index in range(PARAMETER_COUNT) if index not in spanning),
        key=lambda index: (-float(leverage[index]), index),
    )
    selected = spanning + remaining[:5]
    frame = np.asarray(
        [projector[:, i] / math.sqrt(float(leverage[i])) for i in selected],
        dtype=np.float64,
    )
    bases["frame-20"] = frame

    method_specs: dict[str, tuple[Any, Any]] = {}
    for name, directions in bases.items():
        curvatures = np.einsum(
            "ni,ij,nj->n", directions, model.hessian, directions
        )
        method_specs[name] = (directions, curvatures)

    coefficients = frame @ p15.T
    frame_spectrum = np.linalg.eigvalsh(coefficients.T @ coefficients)
    audit = {
        "frame_selected_raw_coordinate_indices": selected,
        "frame_rank": int(np.linalg.matrix_rank(coefficients, tol=1.0e-12)),
        "frame_operator_eigenvalues": [float(x) for x in frame_spectrum],
        "frame_operator_condition_number": float(
            frame_spectrum[-1] / frame_spectrum[0]
        ),
        "frame_projection_max_abs_residual": float(
            np.max(np.abs(frame - frame @ projector))
        ),
        "method_direction_hashes": {
            name: array_sha256(spec[0]) for name, spec in method_specs.items()
        },
    }
    return method_specs, audit


def scan_widths(curvatures: Any) -> Any:
    import numpy as np

    widths = []
    for curvature in np.asarray(curvatures, dtype=np.float64):
        if math.isfinite(float(curvature)) and curvature > 0:
            width = math.sqrt(TARGET_LINE_INFIDELITY * 2 / float(curvature))
        else:
            width = math.inf
        widths.append(
            float(np.clip(width, MIN_SCAN_HALF_WIDTH, MAX_SCAN_HALF_WIDTH))
        )
    return np.asarray(widths, dtype=np.float64)


def exact_coordinate_scan(
    exact_fidelity: Callable[[Any], float],
    start: Any,
    directions: Any,
    curvatures: Any,
) -> tuple[Any, dict[str, Any]]:
    """Fixed black-box coordinate scan with exact, explicit query accounting."""

    import numpy as np

    current = np.asarray(start, dtype=np.float64).copy()
    directions = np.asarray(directions, dtype=np.float64)
    curvatures = np.asarray(curvatures, dtype=np.float64)
    widths = scan_widths(curvatures)
    norms = np.linalg.norm(directions, axis=1)
    if directions.shape[1] != PARAMETER_COUNT or not np.allclose(
        norms, 1, atol=1e-12, rtol=0
    ):
        raise ValueError("invalid normalized search basis")

    query_count = 0
    first_hits: dict[str, int | None] = {
        f"{threshold:.0e}": None for threshold in TARGET_LADDER
    }
    best_fidelity = -math.inf
    accepted_history = []

    def query(parameters: Any) -> float:
        nonlocal query_count, best_fidelity
        fidelity = float(exact_fidelity(np.asarray(parameters, dtype=np.float64)))
        if not math.isfinite(fidelity):
            raise FloatingPointError("non-finite black-box response")
        query_count += 1
        best_fidelity = max(best_fidelity, fidelity)
        for threshold in TARGET_LADDER:
            key = f"{threshold:.0e}"
            if first_hits[key] is None and 1.0 - fidelity <= threshold:
                first_hits[key] = query_count
        return fidelity

    initial_fidelity = query(current)
    for cycle in range(CYCLES):
        for index, direction in enumerate(directions):
            offsets = np.linspace(-widths[index], widths[index], POINTS_PER_LINE)
            infidelities = np.asarray(
                [1.0 - query(current + offset * direction) for offset in offsets]
            )
            design = np.column_stack(
                [offsets**2, offsets, np.ones_like(offsets)]
            )
            decision = "best-measured"
            try:
                coefficients, _, rank, _ = np.linalg.lstsq(
                    design, infidelities, rcond=None
                )
                if (
                    rank == 3
                    and np.all(np.isfinite(coefficients))
                    and coefficients[0] > 0
                ):
                    chosen = float(
                        np.clip(
                            -coefficients[1] / (2 * coefficients[0]),
                            -widths[index],
                            widths[index],
                        )
                    )
                    decision = "quadratic-fit"
                else:
                    chosen = float(offsets[int(np.argmin(infidelities))])
            except np.linalg.LinAlgError:
                chosen = float(offsets[int(np.argmin(infidelities))])
            current += chosen * direction
            # This is deliberately post-decision and counted as the next line's
            # normal zero-offset query, except for this diagnostic exact run.
            accepted_history.append(
                {
                    "cycle": cycle + 1,
                    "direction": index,
                    "selected_offset": chosen,
                    "decision": decision,
                }
            )
    final_fidelity = query(current)
    expected = 2 + CYCLES * directions.shape[0] * POINTS_PER_LINE
    if query_count != expected:
        raise AssertionError((query_count, expected))
    return current, {
        "initial_infidelity": float(1.0 - initial_fidelity),
        "final_infidelity": float(1.0 - final_fidelity),
        "best_queried_infidelity": float(1.0 - best_fidelity),
        "query_count": query_count,
        "expected_query_count": expected,
        "first_query_to_threshold": first_hits,
        "final_parameter_sha256": array_sha256(current),
        "accepted_decisions": accepted_history,
    }


def truth_diagnostics(
    model: NominalModel, true_drift: Any, true_controls: Any
) -> dict[str, Any]:
    """Post-hoc local truth geometry; never call before calibration."""

    import jax.numpy as jnp
    import numpy as np
    from scipy.linalg import subspace_angles

    parameters = jnp.asarray(model.optimized_parameters)
    value, gradient = model.infidelity_value_and_grad(
        parameters, jnp.asarray(true_drift), jnp.asarray(true_controls)
    )
    raw_hessian = np.asarray(
        model.infidelity_hessian(
            parameters, jnp.asarray(true_drift), jnp.asarray(true_controls)
        ),
        dtype=np.float64,
    )
    hessian = 0.5 * (raw_hessian + raw_hessian.T)
    values, vectors = np.linalg.eigh(hessian)
    gap = infer_spectral_gap_rank(values)
    truth_rank = max(1, int(gap["candidate_effective_rank"]))

    nominal_descending = np.argsort(model.eigenvalues)[::-1]
    truth_descending = np.argsort(values)[::-1]
    p15 = model.eigenvectors[:, nominal_descending[:15]]
    truth_p15 = vectors[:, truth_descending[:15]]
    grad = np.asarray(gradient, dtype=np.float64)
    grad_norm_sq = float(grad @ grad)
    energy = (
        float(np.linalg.norm(p15.T @ grad) ** 2 / grad_norm_sq)
        if grad_norm_sq > 0
        else 1.0
    )
    angles = np.degrees(subspace_angles(p15, truth_p15))
    nominal_curvature = np.einsum(
        "ni,ij,nj->n", p15.T, model.hessian, p15.T
    )
    truth_curvature = np.einsum("ni,ij,nj->n", p15.T, hessian, p15.T)
    safe = np.maximum(np.abs(nominal_curvature), 1.0e-15)
    relative_curvature_error = np.abs(truth_curvature - nominal_curvature) / safe
    return {
        "warm_infidelity": float(np.asarray(value)),
        "truth_gradient_norm": float(math.sqrt(grad_norm_sq)),
        "truth_gradient_energy_in_nominal_rank15": energy,
        "truth_hessian_gap": gap,
        "truth_hessian_inferred_rank": truth_rank,
        "nominal_truth_rank15_angles_degrees": [float(x) for x in angles],
        "rank15_angle_max_degrees": float(np.max(angles)),
        "rank15_angle_rms_degrees": float(np.sqrt(np.mean(angles**2))),
        "rank15_curvature_relative_error_median": float(
            np.median(relative_curvature_error)
        ),
        "rank15_curvature_relative_error_max": float(
            np.max(relative_curvature_error)
        ),
        "truth_hessian_sha256": array_sha256(hessian),
    }


def environment_summary() -> dict[str, Any]:
    import jax
    import jaxlib
    import numpy
    import scipy

    return {
        "python": platform.python_version(),
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "backend": jax.default_backend(),
        "x64": bool(jax.config.jax_enable_x64),
    }
