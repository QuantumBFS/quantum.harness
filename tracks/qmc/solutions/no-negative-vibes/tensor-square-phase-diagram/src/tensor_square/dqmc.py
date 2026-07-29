"""Auditable continuous-Gaussian auxiliary-field DQMC prototype."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from .algebra import exterior_square, kron_sum
from .ed import approved_channels


@dataclass(frozen=True)
class DQMCConfig:
    m: int
    beta: float
    dt: float
    t: float
    g_b_over_g_a: float
    mu: float = 0.0
    v_asymmetry: float = 0.0
    g_a: float = 1.0
    proposal_scale: float = 0.75

    @property
    def slices(self) -> int:
        value = self.beta / self.dt
        rounded = int(round(value))
        if abs(value - rounded) > 1.0e-10:
            raise ValueError("beta/dt must be integral")
        return rounded

    def as_dict(self) -> dict[str, float | int]:
        return {**asdict(self), "slices": self.slices}


@dataclass(frozen=True)
class OneBodyModel:
    m: int
    k: np.ndarray
    channels: tuple[np.ndarray, ...]
    couplings: tuple[float, ...]
    group_a: tuple[int, ...]
    group_b: tuple[int, ...]
    nematic: np.ndarray


@dataclass(frozen=True)
class StabilizedProduct:
    u: np.ndarray
    log_singular_values: np.ndarray
    vt: np.ndarray


def make_one_body_model(config: DQMCConfig) -> OneBodyModel:
    channels, group_a, group_b = approved_channels(config.m, "noncommuting")
    adjacency = sum(channels, start=np.zeros((config.m, config.m)))
    k = -config.t * adjacency - 0.5 * config.mu * np.eye(config.m)
    if config.m == 3:
        k = k + config.v_asymmetry * np.diag([-1.0, 0.0, 1.0])
        nematic = np.diag([1.0, -2.0, 1.0])
    else:
        nematic = np.diag(
            [1.0 if index % 2 == 0 else -1.0 for index in range(config.m)]
        )
    couplings = tuple(
        config.g_a if index in group_a else config.g_a * config.g_b_over_g_a
        for index in range(len(channels))
    )
    return OneBodyModel(
        m=config.m,
        k=k,
        channels=tuple(channels),
        couplings=couplings,
        group_a=tuple(group_a),
        group_b=tuple(group_b),
        nematic=nematic,
    )


def slice_matrix(
    fields: np.ndarray,
    *,
    model: OneBodyModel,
    dt: float,
    kinetic_half: np.ndarray | None = None,
) -> np.ndarray:
    if kinetic_half is None:
        kinetic_half = expm(-0.5 * dt * model.k)
    result = kinetic_half.copy()
    for field, channel, coupling in zip(
        fields, model.channels, model.couplings, strict=True
    ):
        if coupling > 0.0:
            alpha = np.sqrt(dt * coupling / model.m)
            result = expm(alpha * field * channel) @ result
    return kinetic_half @ result


def history_product(slice_matrices: list[np.ndarray]) -> np.ndarray:
    m = slice_matrices[0].shape[0]
    result = np.eye(m)
    for matrix in slice_matrices:
        result = matrix @ result
    return result


def stabilized_history_product(
    slice_matrices: list[np.ndarray],
) -> StabilizedProduct:
    m = slice_matrices[0].shape[0]
    u = np.eye(m)
    log_singular_values = np.zeros(m)
    vt = np.eye(m)
    for matrix in slice_matrices:
        shift = float(np.max(log_singular_values))
        scaled = np.exp(log_singular_values - shift)
        left = matrix @ (u * scaled[None, :])
        u_new, singular_values, rotation_t = np.linalg.svd(
            left, full_matrices=False
        )
        if np.any(singular_values <= 0.0):
            raise np.linalg.LinAlgError("slice product lost rank")
        u = u_new
        log_singular_values = np.log(singular_values) + shift
        vt = rotation_t @ vt
    return StabilizedProduct(u, log_singular_values, vt)


def _stable_identity_plus(
    product: StabilizedProduct,
    coefficient: complex | float = 1.0,
    *,
    return_inverse: bool = False,
) -> tuple[complex, float, np.ndarray | None]:
    u = product.u
    vt = product.vt
    logs = product.log_singular_values
    v = vt.T
    c_matrix = u.T @ v
    log_scale = np.maximum(0.0, logs)
    inverse_scale = np.exp(-log_scale)
    scaled_singular = np.exp(logs - log_scale)
    reduced = inverse_scale[:, None] * c_matrix
    reduced = reduced.astype(np.result_type(reduced.dtype, coefficient))
    diagonal = np.diag_indices_from(reduced)
    reduced[diagonal] += coefficient * scaled_singular
    sign_reduced, log_reduced = np.linalg.slogdet(reduced)
    orientation = np.linalg.det(u) * np.linalg.det(vt)
    sign = orientation * sign_reduced
    log_absolute = float(np.sum(log_scale) + log_reduced)
    inverse = None
    if return_inverse:
        middle_inverse = np.linalg.solve(reduced, np.diag(inverse_scale))
        inverse = v @ middle_inverse @ u.T
    return sign, log_absolute, inverse


def _tensor_representation(
    product: StabilizedProduct,
) -> StabilizedProduct:
    logs = (
        product.log_singular_values[:, None]
        + product.log_singular_values[None, :]
    ).reshape(-1)
    return StabilizedProduct(
        np.kron(product.u, product.u),
        logs,
        np.kron(product.vt, product.vt),
    )


def _exterior_representation(
    product: StabilizedProduct,
) -> StabilizedProduct:
    logs = np.asarray(
        [
            product.log_singular_values[i]
            + product.log_singular_values[j]
            for i, j in combinations(range(len(product.log_singular_values)), 2)
        ]
    )
    return StabilizedProduct(
        exterior_square(product.u),
        logs,
        exterior_square(product.vt.T).T,
    )


def stabilized_direct_log_weight(
    product: StabilizedProduct,
) -> tuple[float, float]:
    sign, log_weight, _ = _stable_identity_plus(
        _tensor_representation(product)
    )
    real_sign = float(np.real_if_close(sign).real)
    return float(np.sign(real_sign)), log_weight


def stabilized_structured_log_weight(product: StabilizedProduct) -> float:
    _, complex_log, _ = _stable_identity_plus(product, 1j)
    _, wedge_log, _ = _stable_identity_plus(
        _exterior_representation(product), 1.0
    )
    return float(2.0 * complex_log + 2.0 * wedge_log)


def stabilized_density_matrix(product: StabilizedProduct) -> np.ndarray:
    _, _, green = _stable_identity_plus(
        _tensor_representation(product), return_inverse=True
    )
    assert green is not None
    return np.eye(green.shape[0]) - green.T


def structured_log_weight(x: np.ndarray) -> float:
    m = x.shape[0]
    sign_complex, log_complex = np.linalg.slogdet(np.eye(m) + 1j * x)
    wedge = exterior_square(x)
    sign_wedge, log_wedge = np.linalg.slogdet(
        np.eye(wedge.shape[0]) + wedge
    )
    if abs(sign_complex) == 0.0 or sign_wedge == 0.0:
        return float("-inf")
    return float(2.0 * log_complex + 2.0 * log_wedge)


def direct_log_weight(x: np.ndarray) -> tuple[float, float]:
    full = np.eye(x.size) + np.kron(x, x)
    sign, log_weight = np.linalg.slogdet(full)
    return float(sign), float(log_weight)


def density_matrix_from_history(x: np.ndarray) -> np.ndarray:
    full_history = np.kron(x, x)
    green = np.linalg.inv(np.eye(x.size) + full_history)
    return np.eye(x.size) - green.T


def wick_product(m_left: np.ndarray, m_right: np.ndarray, rho: np.ndarray) -> float:
    """⟨dΓ(M)dΓ(N)⟩ for a number-conserving Gaussian state."""
    value = (
        np.trace(m_left @ m_right @ rho)
        + np.trace(m_left @ rho) * np.trace(m_right @ rho)
        - np.trace(m_left @ rho @ m_right @ rho)
    )
    return float(np.real_if_close(value).real)


def measure_configuration(
    x: np.ndarray | StabilizedProduct, model: OneBodyModel
) -> dict[str, float]:
    if isinstance(x, StabilizedProduct):
        rho = stabilized_density_matrix(x)
        sign, direct_log = stabilized_direct_log_weight(x)
        structured_log = stabilized_structured_log_weight(x)
    else:
        rho = density_matrix_from_history(x)
        sign, direct_log = direct_log_weight(x)
        structured_log = structured_log_weight(x)
    modes = model.m * model.m
    one_body_h = kron_sum(model.k)
    energy_kinetic = float(np.trace(one_body_h @ rho).real)
    q_matrices = [kron_sum(channel) for channel in model.channels]
    q_squares = [
        wick_product(matrix, matrix, rho) for matrix in q_matrices
    ]
    energy_interaction = -sum(
        coupling * q_square / (2.0 * model.m)
        for coupling, q_square in zip(
            model.couplings, q_squares, strict=True
        )
    )
    q_a = sum(
        (q_matrices[index] for index in model.group_a),
        start=np.zeros((modes, modes)),
    )
    q_b = sum(
        (q_matrices[index] for index in model.group_b),
        start=np.zeros((modes, modes)),
    )
    qa2 = wick_product(q_a, q_a, rho) / (len(model.group_a) * modes)
    qb2 = wick_product(q_b, q_b, rho) / (len(model.group_b) * modes)
    nematic = kron_sum(model.nematic)
    return {
        "energy": energy_kinetic + energy_interaction,
        "energy_kinetic": energy_kinetic,
        "energy_interaction": energy_interaction,
        "density": float(np.trace(rho).real / modes),
        "q_a_sq": qa2,
        "q_b_sq": qb2,
        "q_combined": 0.5 * (qa2 + qb2),
        "channel_balance": (qb2 - qa2) / max(1.0e-14, qb2 + qa2),
        "nematic_sq": wick_product(nematic, nematic, rho) / (modes * modes),
        "direct_sign": sign,
        "weight_log_error": abs(direct_log - structured_log),
    }


def integrated_autocorrelation(values: np.ndarray) -> float:
    data = np.asarray(values, dtype=np.float64)
    if len(data) < 8 or np.var(data) == 0.0:
        return 0.5
    centered = data - np.mean(data)
    variance = np.dot(centered, centered) / len(centered)
    tau = 0.5
    for lag in range(1, min(len(data) // 2, 200)):
        correlation = (
            np.dot(centered[:-lag], centered[lag:])
            / (len(data) - lag)
            / variance
        )
        if correlation <= 0.0:
            break
        tau += correlation
        if lag > 6.0 * tau:
            break
    return float(max(0.5, tau))


def summarize_measurements(
    measurements: list[dict[str, float]],
) -> dict[str, float | int]:
    keys = measurements[0].keys()
    summary: dict[str, float | int] = {"measurements": len(measurements)}
    for key in keys:
        values = np.asarray([measurement[key] for measurement in measurements])
        tau = integrated_autocorrelation(values)
        effective = max(1.0, len(values) / (2.0 * tau))
        summary[f"{key}_mean"] = float(np.mean(values))
        summary[f"{key}_stderr"] = float(
            np.std(values, ddof=1) / np.sqrt(effective)
            if len(values) > 1
            else 0.0
        )
        if key in {"energy", "density", "q_a_sq"}:
            summary[f"{key}_tau_int"] = tau
    return summary


def run_chain(
    config: DQMCConfig,
    *,
    seed: int,
    warmup_sweeps: int,
    measurement_sweeps: int,
    measure_every: int,
    progress_every: int = 20,
    checkpoint_path: Path | None = None,
    checkpoint_every: int = 40,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    model = make_one_body_model(config)
    kinetic_half = expm(-0.5 * config.dt * model.k)
    fields = rng.normal(size=(config.slices, len(model.channels)))
    start_sweep = 0
    accepted = 0
    proposed = 0
    measurements: list[dict[str, float]] = []
    if checkpoint_path is not None and checkpoint_path.exists():
        with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
            stored_config = json.loads(str(checkpoint["config_json"].item()))
            if stored_config != config.as_dict():
                raise ValueError("checkpoint config does not match requested config")
            fields = checkpoint["fields"]
            start_sweep = int(checkpoint["completed_sweeps"].item())
            accepted = int(checkpoint["accepted"].item())
            proposed = int(checkpoint["proposed"].item())
            measurements = json.loads(
                str(checkpoint["measurements_json"].item())
            )
            rng.bit_generator.state = json.loads(
                str(checkpoint["rng_state_json"].item())
            )
    slices = [
        slice_matrix(
            fields[index],
            model=model,
            dt=config.dt,
            kinetic_half=kinetic_half,
        )
        for index in range(config.slices)
    ]
    use_stabilization = config.beta >= 6.0
    total = (
        stabilized_history_product(slices)
        if use_stabilization
        else history_product(slices)
    )
    log_weight = (
        stabilized_structured_log_weight(total)
        if use_stabilization
        else structured_log_weight(total)
    )
    total_sweeps = warmup_sweeps + measurement_sweeps
    contraction = np.sqrt(1.0 - config.proposal_scale**2)
    for sweep in range(start_sweep, total_sweeps):
        for time_slice in rng.permutation(config.slices):
            proposed_fields = (
                contraction * fields[time_slice]
                + config.proposal_scale
                * rng.normal(size=len(model.channels))
            )
            proposed_slice = slice_matrix(
                proposed_fields,
                model=model,
                dt=config.dt,
                kinetic_half=kinetic_half,
            )
            old_slice = slices[time_slice]
            slices[time_slice] = proposed_slice
            proposed_total = (
                stabilized_history_product(slices)
                if use_stabilization
                else history_product(slices)
            )
            proposed_log_weight = (
                stabilized_structured_log_weight(proposed_total)
                if use_stabilization
                else structured_log_weight(proposed_total)
            )
            proposed += 1
            if np.log(rng.random()) < min(
                0.0, proposed_log_weight - log_weight
            ):
                fields[time_slice] = proposed_fields
                total = proposed_total
                log_weight = proposed_log_weight
                accepted += 1
            else:
                slices[time_slice] = old_slice
        if (
            sweep >= warmup_sweeps
            and (sweep - warmup_sweeps) % measure_every == 0
        ):
            measurements.append(measure_configuration(total, model))
        if (sweep + 1) % progress_every == 0 or sweep + 1 == total_sweeps:
            print(
                f"seed={seed} sweep={sweep + 1}/{total_sweeps} "
                f"accept={accepted / max(1, proposed):.3f} "
                f"measurements={len(measurements)}",
                flush=True,
            )
        if checkpoint_path is not None and (
            (sweep + 1) % checkpoint_every == 0
            or sweep + 1 == total_sweeps
        ):
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = checkpoint_path.with_suffix(".tmp.npz")
            np.savez_compressed(
                temporary,
                config_json=json.dumps(config.as_dict(), sort_keys=True),
                fields=fields,
                completed_sweeps=sweep + 1,
                accepted=accepted,
                proposed=proposed,
                measurements_json=json.dumps(measurements),
                rng_state_json=json.dumps(rng.bit_generator.state),
            )
            temporary.replace(checkpoint_path)
    summary = summarize_measurements(measurements)
    summary.update(
        {
            "seed": seed,
            "acceptance": accepted / max(1, proposed),
            "accepted": accepted,
            "proposed": proposed,
            "config": config.as_dict(),
            "stabilized": use_stabilization,
        }
    )
    return summary
