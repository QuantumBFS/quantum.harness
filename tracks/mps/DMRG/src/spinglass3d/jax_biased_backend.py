"""Float64 JAX parallel tempering for TT-biased replica pairs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import math
import time
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from .backend import BackendCase, _host_rss_bytes
from .bias import BiasRoute, OverlapBias
from .model import EABonds, delta_energy, energy
from .templates import TemplateEncoder, TemplateKind


jax.config.update("jax_enable_x64", True)

_SUPPORTED_RANKS = frozenset({2, 4, 8})


def metropolis_accept(delta_action: float, uniform: float) -> bool:
    """Return one Metropolis decision after validating both scalar inputs."""

    delta = float(delta_action)
    value = float(uniform)
    if not math.isfinite(delta):
        raise FloatingPointError("Metropolis action difference is not finite")
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError("Metropolis uniform must lie strictly inside (0,1)")
    return math.log(value) < min(0.0, -delta)


@dataclass(frozen=True)
class BiasedSweepResult:
    delta_action: np.ndarray
    accepted: np.ndarray
    jitted: bool = True

    def __post_init__(self) -> None:
        delta = np.asarray(self.delta_action, dtype=np.float64)
        accepted = np.asarray(self.accepted, dtype=bool)
        if delta.shape != accepted.shape or not np.all(np.isfinite(delta)):
            raise ValueError("biased sweep result arrays are invalid")
        object.__setattr__(self, "delta_action", delta.copy())
        object.__setattr__(self, "accepted", accepted.copy())


def _one_biased_pair_sweep(
    pair_spins: jax.Array,
    pair_energies: jax.Array,
    block_sums: jax.Array,
    q_prime: jax.Array,
    token_codes: jax.Array,
    bias_value: jax.Array,
    bonds: jax.Array,
    beta: jax.Array,
    lookup: jax.Array,
    affected_centers: jax.Array,
    affected_masks: jax.Array,
    micro_to_coarse: jax.Array,
    order: jax.Array,
    uniforms: jax.Array,
) -> tuple[
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
]:
    length = pair_spins.shape[-1]
    n_sites = length**3

    def update(
        carry: tuple[
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
        ],
        item: tuple[jax.Array, jax.Array],
    ) -> tuple[
        tuple[
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
            jax.Array,
        ],
        tuple[jax.Array, jax.Array],
    ]:
        spins, energies, sums, coarse_q, codes, current_bias = carry
        encoded, uniform = item
        replica = encoded // n_sites
        flat_site = encoded % n_sites
        x = flat_site // (length * length)
        remainder = flat_site % (length * length)
        y = remainder // length
        z = remainder % length
        selected = spins[replica]
        spin = selected[x, y, z]
        local = jnp.int64(0)
        coordinates = (x, y, z)
        for axis in range(3):
            plus = list(coordinates)
            minus = list(coordinates)
            plus[axis] = (plus[axis] + 1) % length
            minus[axis] = (minus[axis] - 1) % length
            local = local + bonds[x, y, z, axis] * selected[tuple(plus)]
            local = local + bonds[tuple(minus) + (axis,)] * selected[tuple(minus)]
        delta_energy_value = 2 * spin.astype(jnp.int64) * local

        old_q = spins[0, x, y, z] * spins[1, x, y, z]
        coarse_site = micro_to_coarse[flat_site]
        old_sum = sums[coarse_site]
        new_sum = old_sum - 2 * old_q.astype(jnp.int16)
        old_coarse = coarse_q[coarse_site]
        new_coarse = jnp.where(new_sum > 0, jnp.int8(1), jnp.int8(-1))
        coarse_changed = old_coarse != new_coarse
        centers = affected_centers[coarse_site]
        old_center_codes = codes[centers]
        new_center_codes = jnp.bitwise_xor(
            old_center_codes,
            affected_masks[coarse_site],
        )
        local_bias_delta = jnp.sum(
            lookup[new_center_codes] - lookup[old_center_codes],
            dtype=jnp.float64,
        )
        candidate_bias = jnp.where(
            coarse_changed,
            current_bias + local_bias_delta,
            current_bias,
        )
        delta_bias = candidate_bias - current_bias
        delta_action = beta * delta_energy_value.astype(jnp.float64) + delta_bias
        take = jnp.log(uniform) < jnp.minimum(0.0, -delta_action)

        spins = spins.at[replica, x, y, z].set(
            jnp.where(take, -spin, spin)
        )
        energies = energies.at[replica].add(
            jnp.where(take, delta_energy_value, jnp.int64(0))
        )
        sums = sums.at[coarse_site].set(
            jnp.where(take, new_sum, old_sum)
        )
        coarse_q = coarse_q.at[coarse_site].set(
            jnp.where(take, new_coarse, old_coarse)
        )
        accepted_center_codes = jnp.where(
            take & coarse_changed,
            new_center_codes,
            old_center_codes,
        )
        codes = codes.at[centers].set(accepted_center_codes)
        current_bias = jnp.where(take, candidate_bias, current_bias)
        return (
            spins,
            energies,
            sums,
            coarse_q,
            codes,
            current_bias,
        ), (delta_action, take)

    final, history = jax.lax.scan(
        update,
        (
            pair_spins,
            pair_energies,
            block_sums,
            q_prime,
            token_codes,
            bias_value,
        ),
        (order, uniforms),
    )
    return (*final, history[0], history[1])


_batched_biased_sweep = jax.jit(
    jax.vmap(
        _one_biased_pair_sweep,
        in_axes=(0, 0, 0, 0, 0, 0, None, 0, 0, None, None, None, 0, 0),
    )
)


def _swap_slots(
    values: jax.Array,
    lower: int,
    upper: int,
    take: jax.Array,
) -> jax.Array:
    lower_value = values[:, lower, ...]
    upper_value = values[:, upper, ...]
    mask = take.reshape((take.shape[0],) + (1,) * (values.ndim - 2))
    values = values.at[:, lower, ...].set(
        jnp.where(mask, upper_value, lower_value)
    )
    values = values.at[:, upper, ...].set(
        jnp.where(mask, lower_value, upper_value)
    )
    return values


def _biased_swap_pass(
    spins: jax.Array,
    energies: jax.Array,
    block_sums: jax.Array,
    q_prime: jax.Array,
    token_codes: jax.Array,
    bias_values: jax.Array,
    replica_ids: jax.Array,
    betas: jax.Array,
    lookups: jax.Array,
    uniforms: jax.Array,
    *,
    parity: int,
) -> tuple[
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
    jax.Array,
]:
    accepted = jnp.zeros(uniforms.shape, dtype=jnp.bool_)
    for lower in range(parity, spins.shape[1] - 1, 2):
        upper = lower + 1
        energy_lower = jnp.sum(energies[:, lower, :], axis=1, dtype=jnp.int64)
        energy_upper = jnp.sum(energies[:, upper, :], axis=1, dtype=jnp.int64)
        bias_lower_upper = jnp.sum(
            lookups[lower][token_codes[:, upper, :]],
            axis=1,
            dtype=jnp.float64,
        )
        bias_upper_lower = jnp.sum(
            lookups[upper][token_codes[:, lower, :]],
            axis=1,
            dtype=jnp.float64,
        )
        delta = (
            betas[lower] * energy_upper.astype(jnp.float64)
            + bias_lower_upper
            + betas[upper] * energy_lower.astype(jnp.float64)
            + bias_upper_lower
            - betas[lower] * energy_lower.astype(jnp.float64)
            - bias_values[:, lower]
            - betas[upper] * energy_upper.astype(jnp.float64)
            - bias_values[:, upper]
        )
        take = jnp.log(uniforms[:, lower]) < jnp.minimum(0.0, -delta)
        spins = _swap_slots(spins, lower, upper, take)
        energies = _swap_slots(energies, lower, upper, take)
        block_sums = _swap_slots(block_sums, lower, upper, take)
        q_prime = _swap_slots(q_prime, lower, upper, take)
        token_codes = _swap_slots(token_codes, lower, upper, take)
        replica_ids = _swap_slots(replica_ids, lower, upper, take)
        old_lower_bias = bias_values[:, lower]
        old_upper_bias = bias_values[:, upper]
        bias_values = bias_values.at[:, lower].set(
            jnp.where(take, bias_lower_upper, old_lower_bias)
        )
        bias_values = bias_values.at[:, upper].set(
            jnp.where(take, bias_upper_lower, old_upper_bias)
        )
        accepted = accepted.at[:, lower].set(take)
    return (
        spins,
        energies,
        block_sums,
        q_prime,
        token_codes,
        bias_values,
        replica_ids,
        accepted,
    )


_biased_swap_even = jax.jit(
    lambda spins, energies, block_sums, q_prime, token_codes, bias_values,
    replica_ids, betas, lookups, uniforms: _biased_swap_pass(
        spins,
        energies,
        block_sums,
        q_prime,
        token_codes,
        bias_values,
        replica_ids,
        betas,
        lookups,
        uniforms,
        parity=0,
    )
)
_biased_swap_odd = jax.jit(
    lambda spins, energies, block_sums, q_prime, token_codes, bias_values,
    replica_ids, betas, lookups, uniforms: _biased_swap_pass(
        spins,
        energies,
        block_sums,
        q_prime,
        token_codes,
        bias_values,
        replica_ids,
        betas,
        lookups,
        uniforms,
        parity=1,
    )
)


def _single_bias_signature(bias: OverlapBias) -> str:
    digest = hashlib.sha256()
    digest.update(bias.route.value.encode("ascii"))
    digest.update(repr(sorted(bias.tt.encoder.metadata().items())).encode("ascii"))
    digest.update(str(bias.tt.model.chi).encode("ascii"))
    for core in bias.tt.model.cores:
        values = np.asarray(core, dtype=np.float64)
        digest.update(str(values.shape).encode("ascii"))
        digest.update(values.tobytes())
    digest.update(np.asarray(bias.coefficients, dtype=np.float64).tobytes())
    if bias.basis is not None:
        digest.update(repr(bias.basis.names).encode("ascii"))
    return digest.hexdigest()


def _combined_bias_signature(biases: Sequence[OverlapBias]) -> str:
    digest = hashlib.sha256()
    for bias in biases:
        digest.update(_single_bias_signature(bias).encode("ascii"))
    return digest.hexdigest()


def _checkpoint_integer_array(
    value: object,
    *,
    dtype: np.dtype,
    label: str,
) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in {"i", "u"}:
        raise TypeError(f"biased PT checkpoint {label} must use an integer dtype")
    converted = raw.astype(dtype, copy=True)
    if not np.array_equal(raw, converted):
        raise ValueError(
            f"biased PT checkpoint {label} values exceed the supported integer domain"
        )
    return converted


def _checkpoint_binary_array(
    value: object,
    *,
    dtype: np.dtype,
    label: str,
) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in {"i", "u"}:
        raise TypeError(
            f"biased PT checkpoint binary {label} must use an integer dtype"
        )
    if not np.all((raw == -1) | (raw == 1)):
        raise ValueError(f"biased PT checkpoint binary {label} has invalid values")
    return raw.astype(dtype, copy=True)


class JaxBiasedPairBackend:
    """Joint-pair PT with exact cube TT lookups and incremental RG caches."""

    update_mode = "random_sequential"

    def __init__(
        self,
        case: BackendCase,
        biases: OverlapBias | Sequence[OverlapBias],
        *,
        required_platform: str,
    ) -> None:
        if not isinstance(case, BackendCase):
            raise TypeError("case must be BackendCase")
        if required_platform not in {"cpu", "gpu"}:
            raise ValueError("required_platform must be cpu or gpu")
        devices = jax.devices()
        if (
            jax.default_backend() != required_platform
            or not devices
            or any(device.platform != required_platform for device in devices)
        ):
            raise RuntimeError(
                f"required JAX platform {required_platform!r}, got "
                f"backend={jax.default_backend()!r} devices={devices!r}"
            )
        if not bool(jax.config.jax_enable_x64):
            raise RuntimeError("JAX float64 mode is required")
        if bool(jax.config.jax_disable_jit):
            raise RuntimeError("JAX JIT must be enabled for the biased backend")
        samples, temperatures, walkers = case.spins.shape[:3]
        length = case.spins.shape[-1]
        if samples != 1:
            raise ValueError("one biased backend instance requires exactly one J sample")
        if temperatures < 2 or np.any(np.diff(case.betas) <= 0.0):
            raise ValueError("biased PT betas must be strictly increasing")
        if walkers < 2 or walkers % 2:
            raise ValueError("biased PT requires an even number of replica walkers")
        if length < 3 or length % 3:
            raise ValueError("biased one-RG lattices must be divisible by three")

        self.case = case
        self.required_platform = required_platform
        self._temperatures = temperatures
        self._pairs = walkers // 2
        self._length = length
        self._coarse_length = length // 3
        self._coarse_sites = self._coarse_length**3
        self._bonds_host = EABonds(case.bonds[0])
        self._bonds = jnp.asarray(case.bonds[0], dtype=jnp.int8)
        self._betas = jnp.asarray(case.betas, dtype=jnp.float64)
        self._biases = self._validated_biases(biases)
        self._encoder = self._biases[0].tt.encoder
        self._context_signature = self._build_context_signature()
        (
            self._base_codes,
            self._q_gather,
            self._q_weights,
            self._affected_centers_host,
            self._affected_masks_host,
            self._micro_to_coarse_host,
        ) = self._build_token_geometry()
        self._affected_centers = jnp.asarray(
            self._affected_centers_host,
            dtype=jnp.int32,
        )
        self._affected_masks = jnp.asarray(
            self._affected_masks_host,
            dtype=jnp.int32,
        )
        self._micro_to_coarse = jnp.asarray(
            self._micro_to_coarse_host,
            dtype=jnp.int32,
        )

        spins = case.spins[0].reshape(
            temperatures,
            self._pairs,
            2,
            length,
            length,
            length,
        ).transpose(1, 0, 2, 3, 4, 5)
        self._spins = jnp.asarray(spins, dtype=jnp.int8)
        lookup_started = time.perf_counter()
        self._lookups_host = self._build_lookups(self._biases)
        self.lookup_build_seconds = time.perf_counter() - lookup_started
        self._lookups = jnp.asarray(self._lookups_host, dtype=jnp.float64)
        energies, sums, q_prime, codes, bias_values = self._host_cache(spins)
        self._energies = jnp.asarray(energies, dtype=jnp.int64)
        self._block_sums = jnp.asarray(sums, dtype=jnp.int16)
        self._q_prime = jnp.asarray(q_prime, dtype=jnp.int8)
        self._token_codes = jnp.asarray(codes, dtype=jnp.int32)
        self._bias_values = jnp.asarray(bias_values, dtype=jnp.float64)
        ids = np.broadcast_to(
            np.arange(temperatures, dtype=np.int64)[None, :],
            (self._pairs, temperatures),
        ).copy()
        self._replica_ids = jnp.asarray(ids, dtype=jnp.int64)
        tracker_shape = (self._pairs, temperatures)
        self._round_trip_phase = np.zeros(tracker_shape, dtype=np.int8)
        self._round_trips = np.zeros(tracker_shape, dtype=np.int64)
        self._time_since_endpoint = np.zeros(tracker_shape, dtype=np.int64)
        self._update_round_trip_state()

        self._local_key = jax.random.PRNGKey(case.seed + 4_000_003)
        self._swap_key = jax.random.PRNGKey(case.seed + 5_000_003)
        self._global_key = jax.random.PRNGKey(case.seed + 6_000_003)
        self.accepted_changes = 0
        self.proposed_changes = 0
        self.global_flip_attempts = 0
        self.swap_attempts = np.zeros(temperatures - 1, dtype=np.int64)
        self.swap_accepts = np.zeros(temperatures - 1, dtype=np.int64)
        self.sweep_count = 0
        self.compile_seconds = 0.0
        self._compiled_local = False
        self._compiled_swap = False
        self._generation = 0
        self._bias_signature = _combined_bias_signature(self._biases)
        self.assert_cache_consistent()

    def _build_context_signature(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"JaxBiasedPairBackend/context/v1")
        for label, value in (
            ("bonds", self.case.bonds),
            ("betas", self.case.betas),
        ):
            array = np.asarray(value)
            digest.update(label.encode("ascii"))
            digest.update(str(array.shape).encode("ascii"))
            digest.update(array.dtype.str.encode("ascii"))
            digest.update(np.ascontiguousarray(array).tobytes())
        identity = {
            "case_seed": self.case.seed,
            "sample_count": 1,
            "temperature_count": self._temperatures,
            "pair_count": self._pairs,
            "length": self._length,
            "coarse_length": self._coarse_length,
            "encoder": self._encoder.metadata(),
        }
        digest.update(repr(identity).encode("utf-8"))
        return digest.hexdigest()

    def _validated_biases(
        self,
        biases: OverlapBias | Sequence[OverlapBias],
    ) -> tuple[OverlapBias, ...]:
        if isinstance(biases, OverlapBias):
            selected = (biases,) * self._temperatures
        else:
            selected = tuple(biases)
        if len(selected) != self._temperatures or any(
            not isinstance(value, OverlapBias) for value in selected
        ):
            raise ValueError("one OverlapBias is required per temperature")
        for bias in selected:
            encoder = bias.tt.encoder
            if (
                encoder.kind not in {TemplateKind.CUBE, TemplateKind.CROSS}
                or not encoder.conditioned
                or encoder.rg_level != 1
            ):
                raise ValueError(
                    "JAX biased PT supports conditioned one-RG cube/cross templates"
                )
            if bias.route not in {
                BiasRoute.B_CONDITIONED_TT,
                BiasRoute.C_LINEAR_PLUS_TT,
            }:
                raise ValueError("JAX biased PT supports only Route B or Route C")
            if bias.tt.model.chi not in _SUPPORTED_RANKS:
                raise ValueError(
                    f"unsupported TT rank {bias.tt.model.chi}; supported ranks are 2,4,8"
                )
            if any(
                not np.all(np.isfinite(np.asarray(core, dtype=np.float64)))
                for core in bias.tt.model.cores
            ) or not np.all(np.isfinite(np.asarray(bias.coefficients))):
                raise ValueError("bias contains non-finite TT or linear parameters")
        reference = selected[0].tt.encoder.metadata()
        if any(bias.tt.encoder.metadata() != reference for bias in selected[1:]):
            raise ValueError("all temperature biases must share one token encoding")
        return selected

    def _build_token_geometry(
        self,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        centers = tuple(np.ndindex((self._coarse_length,) * 3))
        dummy = -np.ones((self._coarse_length,) * 3, dtype=np.int8)
        q_positions = tuple(self._encoder.q_token_indices)
        q_position_set = set(q_positions)
        q_weights = np.left_shift(
            np.int32(1),
            np.asarray(q_positions, dtype=np.int32),
        )
        base_codes = np.zeros(self._coarse_sites, dtype=np.int32)
        q_gather = np.empty(
            (self._coarse_sites, self._encoder.q_token_count),
            dtype=np.int32,
        )
        for center_index, center in enumerate(centers):
            tokens = self._encoder.encode(dummy, self._bonds_host, center)
            code = 0
            for token_index, token in enumerate(tokens):
                if token_index not in q_position_set and int(token) == 1:
                    code |= 1 << token_index
            base_codes[center_index] = code
            for q_index, offset in enumerate(self._encoder.offsets):
                represented = tuple(
                    (center[axis] + offset[axis]) % self._coarse_length
                    for axis in range(3)
                )
                q_gather[center_index, q_index] = np.ravel_multi_index(
                    represented,
                    (self._coarse_length,) * 3,
                )
        affected: list[list[tuple[int, int]]] = []
        for coarse_site in range(self._coarse_sites):
            entries: list[tuple[int, int]] = []
            for center in range(self._coarse_sites):
                mask = 0
                for q_index, represented in enumerate(q_gather[center]):
                    if int(represented) == coarse_site:
                        mask |= int(q_weights[q_index])
                if mask:
                    entries.append((center, mask))
            affected.append(entries)
        widths = {len(entries) for entries in affected}
        if len(widths) != 1 or not widths or next(iter(widths)) < 1:
            raise AssertionError("cube reverse incidence must have fixed positive width")
        affected_centers = np.asarray(
            [[center for center, _ in entries] for entries in affected],
            dtype=np.int32,
        )
        affected_masks = np.asarray(
            [[mask for _, mask in entries] for entries in affected],
            dtype=np.int32,
        )
        micro_to_coarse = np.empty(self._length**3, dtype=np.int32)
        for flat_site, site in enumerate(np.ndindex((self._length,) * 3)):
            coarse = tuple(value // 3 for value in site)
            micro_to_coarse[flat_site] = np.ravel_multi_index(
                coarse,
                (self._coarse_length,) * 3,
            )
        return (
            base_codes,
            q_gather,
            q_weights,
            affected_centers,
            affected_masks,
            micro_to_coarse,
        )

    @staticmethod
    def _build_lookups(biases: Sequence[OverlapBias]) -> np.ndarray:
        cached: dict[str, np.ndarray] = {}
        result: list[np.ndarray] = []
        for bias in biases:
            signature = _single_bias_signature(bias)
            if signature not in cached:
                lookup = np.asarray(
                    bias.build_lookup(bias.tt.encoder),
                    dtype=np.float64,
                )
                expected = (1 << bias.tt.encoder.token_count,)
                if lookup.shape != expected or not np.all(np.isfinite(lookup)):
                    raise ValueError("bias lookup is incomplete or non-finite")
                cached[signature] = lookup.copy()
            result.append(cached[signature])
        return np.asarray(result, dtype=np.float64)

    def _codes_from_q_prime(self, q_prime: np.ndarray) -> np.ndarray:
        values = np.asarray(q_prime, dtype=np.int8)
        expected = (
            self._pairs,
            self._temperatures,
            self._coarse_length,
            self._coarse_length,
            self._coarse_length,
        )
        if values.shape != expected or not np.all((values == -1) | (values == 1)):
            raise ValueError("q-prime cache has invalid shape or values")
        flat = values.reshape(self._pairs, self._temperatures, self._coarse_sites)
        gathered = flat[:, :, self._q_gather]
        q_bits = np.sum(
            (gathered > 0).astype(np.int32) * self._q_weights,
            axis=-1,
            dtype=np.int32,
        )
        return self._base_codes[None, None, :] + q_bits

    def _host_cache(
        self,
        spins: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        states = np.asarray(spins, dtype=np.int8)
        expected = (
            self._pairs,
            self._temperatures,
            2,
            self._length,
            self._length,
            self._length,
        )
        if states.shape != expected or not np.all((states == -1) | (states == 1)):
            raise ValueError("paired spin state has invalid shape or values")
        energies = np.empty((self._pairs, self._temperatures, 2), dtype=np.int64)
        for pair in range(self._pairs):
            for temperature in range(self._temperatures):
                for replica in range(2):
                    energies[pair, temperature, replica] = energy(
                        states[pair, temperature, replica],
                        self._bonds_host,
                    )
        overlap = np.multiply(states[:, :, 0], states[:, :, 1], dtype=np.int8)
        blocked = overlap.reshape(
            self._pairs,
            self._temperatures,
            self._coarse_length,
            3,
            self._coarse_length,
            3,
            self._coarse_length,
            3,
        )
        sums = np.sum(blocked, axis=(3, 5, 7), dtype=np.int16)
        if np.any(sums == 0):
            raise AssertionError("odd 3x3x3 overlap blocks cannot tie")
        q_prime = np.where(sums > 0, 1, -1).astype(np.int8)
        codes = self._codes_from_q_prime(q_prime)
        bias_values = np.empty((self._pairs, self._temperatures), dtype=np.float64)
        for pair in range(self._pairs):
            for temperature in range(self._temperatures):
                bias_values[pair, temperature] = np.sum(
                    self._lookups_host[temperature, codes[pair, temperature]],
                    dtype=np.float64,
                )
        if not np.all(np.isfinite(bias_values)):
            raise FloatingPointError("cached bias values are non-finite")
        return energies, sums, q_prime, codes, bias_values

    def _assert_bias_parameters_current(self) -> None:
        if _combined_bias_signature(self._biases) != self._bias_signature:
            raise RuntimeError(
                "stale bias parameters: call refresh_biases before sampling"
            )

    @property
    def sample_count(self) -> int:
        return 1

    @property
    def temperature_count(self) -> int:
        return self._temperatures

    @property
    def pair_count(self) -> int:
        return self._pairs

    @property
    def length(self) -> int:
        return self._length

    @property
    def coarse_length(self) -> int:
        return self._coarse_length

    @property
    def betas(self) -> np.ndarray:
        return np.asarray(self._betas, dtype=np.float64).copy()

    @property
    def encoder(self) -> TemplateEncoder:
        return self._encoder

    @property
    def token_count(self) -> int:
        return self._encoder.token_count

    @property
    def route(self) -> BiasRoute:
        return self._biases[0].route

    @property
    def rank(self) -> int:
        return self._biases[0].tt.model.chi

    @property
    def bias_signatures(self) -> tuple[str, ...]:
        return tuple(_single_bias_signature(bias) for bias in self._biases)

    @property
    def bias_signature(self) -> str:
        return self._bias_signature

    @property
    def bias_models(self) -> tuple[OverlapBias, ...]:
        """Return the active models for transactional adapter refresh."""

        return tuple(self._biases)

    @property
    def platform(self) -> str:
        return jax.default_backend()

    @property
    def context_signature(self) -> str:
        return self._context_signature

    @property
    def spins(self) -> np.ndarray:
        return np.asarray(self._spins).copy()

    @property
    def energies(self) -> np.ndarray:
        return np.asarray(self._energies).copy()

    @property
    def block_sums(self) -> np.ndarray:
        return np.asarray(self._block_sums).copy()

    @property
    def q_prime(self) -> np.ndarray:
        return np.asarray(self._q_prime).copy()

    @property
    def token_codes(self) -> np.ndarray:
        return np.asarray(self._token_codes).copy()

    @property
    def bias_values(self) -> np.ndarray:
        return np.asarray(self._bias_values).copy()

    @property
    def replica_ids(self) -> np.ndarray:
        return np.asarray(self._replica_ids).copy()

    @property
    def round_trips(self) -> np.ndarray:
        return self._round_trips.copy()

    def overlap_fields(self) -> np.ndarray:
        states = self.spins
        return np.multiply(states[:, :, 0], states[:, :, 1], dtype=np.int8)

    def assert_cache_consistent(self) -> None:
        self._assert_bias_parameters_current()
        expected = self._host_cache(self.spins)
        actual = (
            self.energies,
            self.block_sums,
            self.q_prime,
            self.token_codes,
            self.bias_values,
        )
        names = ("energy", "block sums", "q-prime", "token", "bias")
        for name, observed, wanted in zip(names, actual, expected, strict=True):
            if name == "bias":
                matches = np.allclose(observed, wanted, atol=2e-10, rtol=0.0)
            else:
                matches = np.array_equal(observed, wanted)
            if not matches:
                raise RuntimeError(f"stale cache: {name} state differs from full recompute")

    def refresh_biases(
        self,
        biases: OverlapBias | Sequence[OverlapBias] | None = None,
        *,
        _prepared_lookups: np.ndarray | None = None,
    ) -> None:
        selected = self._biases if biases is None else self._validated_biases(biases)
        if _prepared_lookups is None:
            lookups = self._build_lookups(selected)
        else:
            lookups = np.asarray(_prepared_lookups, dtype=np.float64)
            expected = (
                self._temperatures,
                1 << selected[0].tt.encoder.token_count,
            )
            if lookups.shape != expected or not np.all(np.isfinite(lookups)):
                raise ValueError("prepared bias lookup tables are incompatible")
            lookups = lookups.copy()
        codes = self.token_codes
        values = np.empty((self._pairs, self._temperatures), dtype=np.float64)
        for pair in range(self._pairs):
            for temperature in range(self._temperatures):
                values[pair, temperature] = np.sum(
                    lookups[temperature, codes[pair, temperature]],
                    dtype=np.float64,
                )
        if not np.all(np.isfinite(values)):
            raise FloatingPointError("refreshed bias cache is non-finite")
        self._biases = tuple(selected)
        self._lookups_host = lookups
        self._lookups = jnp.asarray(lookups, dtype=jnp.float64)
        self._bias_values = jnp.asarray(values, dtype=jnp.float64)
        self._bias_signature = _combined_bias_signature(self._biases)
        self._generation += 1
        self.assert_cache_consistent()

    @property
    def lookup_tables(self) -> np.ndarray:
        """Return a detached copy for shared-bias multi-J installation."""

        return self._lookups_host.copy()

    def _validate_pair_temperature(self, pair: int, temperature: int) -> tuple[int, int]:
        selected_pair, selected_temperature = int(pair), int(temperature)
        if not 0 <= selected_pair < self._pairs:
            raise ValueError("pair index is outside the backend")
        if not 0 <= selected_temperature < self._temperatures:
            raise ValueError("temperature index is outside the backend")
        return selected_pair, selected_temperature

    def _validate_site(self, site: tuple[int, int, int]) -> tuple[int, int, int]:
        selected = tuple(int(value) for value in site)
        if len(selected) != 3 or any(not 0 <= value < self._length for value in selected):
            raise ValueError("site is outside the microscopic lattice")
        return selected

    def cached_local_bias_delta(
        self,
        pair: int,
        temperature: int,
        site: tuple[int, int, int],
    ) -> float:
        self.assert_cache_consistent()
        selected_pair, selected_temperature = self._validate_pair_temperature(
            pair,
            temperature,
        )
        selected_site = self._validate_site(site)
        flat_site = int(np.ravel_multi_index(selected_site, (self._length,) * 3))
        coarse_site = int(self._micro_to_coarse_host[flat_site])
        overlap = self.overlap_fields()
        old_q = int(overlap[(selected_pair, selected_temperature) + selected_site])
        old_sum = int(
            self.block_sums.reshape(
                self._pairs,
                self._temperatures,
                self._coarse_sites,
            )[selected_pair, selected_temperature, coarse_site]
        )
        new_sum = old_sum - 2 * old_q
        old_coarse = 1 if old_sum > 0 else -1
        new_coarse = 1 if new_sum > 0 else -1
        if new_coarse == old_coarse:
            return 0.0
        codes = self.token_codes[selected_pair, selected_temperature]
        centers = self._affected_centers_host[coarse_site]
        old_center_codes = codes[centers]
        changed = np.bitwise_xor(
            old_center_codes,
            self._affected_masks_host[coarse_site],
        )
        lookup = self._lookups_host[selected_temperature]
        delta = float(
            np.sum(
                lookup[changed] - lookup[old_center_codes],
                dtype=np.float64,
            )
        )
        if not math.isfinite(delta):
            raise FloatingPointError("cached local bias delta is not finite")
        return delta

    def cached_local_action_delta(
        self,
        pair: int,
        temperature: int,
        replica: int,
        site: tuple[int, int, int],
    ) -> float:
        selected_pair, selected_temperature = self._validate_pair_temperature(
            pair,
            temperature,
        )
        selected_replica = int(replica)
        if selected_replica not in (0, 1):
            raise ValueError("replica index must be zero or one")
        selected_site = self._validate_site(site)
        difference = delta_energy(
            self.spins[selected_pair, selected_temperature, selected_replica],
            self._bonds_host,
            selected_site,
        )
        result = float(
            self.case.betas[selected_temperature] * difference
            + self.cached_local_bias_delta(
                selected_pair,
                selected_temperature,
                selected_site,
            )
        )
        if not math.isfinite(result):
            raise FloatingPointError("cached local action delta is not finite")
        return result

    def full_pair_action(
        self,
        pair: int,
        temperature: int,
        *,
        states: np.ndarray | None = None,
    ) -> float:
        self._assert_bias_parameters_current()
        selected_pair, selected_temperature = self._validate_pair_temperature(
            pair,
            temperature,
        )
        values = (
            self.spins[selected_pair, selected_temperature]
            if states is None
            else np.asarray(states, dtype=np.int8)
        )
        expected = (2, self._length, self._length, self._length)
        if values.shape != expected or not np.all((values == -1) | (values == 1)):
            raise ValueError("pair states have invalid shape or values")
        overlap = np.multiply(values[0], values[1], dtype=np.int8)
        blocked = overlap.reshape(
            self._coarse_length,
            3,
            self._coarse_length,
            3,
            self._coarse_length,
            3,
        )
        sums = np.sum(blocked, axis=(1, 3, 5), dtype=np.int16)
        q_prime = np.where(sums > 0, 1, -1).astype(np.int8)
        bias = self._biases[selected_temperature]
        result = float(
            self.case.betas[selected_temperature]
            * (
                energy(values[0], self._bonds_host)
                + energy(values[1], self._bonds_host)
            )
            + bias.value(q_prime, self._bonds_host, bias.tt.encoder)
        )
        if not math.isfinite(result):
            raise FloatingPointError("full pair action is not finite")
        return result

    def full_local_action_delta(
        self,
        pair: int,
        temperature: int,
        replica: int,
        site: tuple[int, int, int],
    ) -> float:
        selected_pair, selected_temperature = self._validate_pair_temperature(
            pair,
            temperature,
        )
        selected_replica = int(replica)
        if selected_replica not in (0, 1):
            raise ValueError("replica index must be zero or one")
        selected_site = self._validate_site(site)
        states = self.spins[selected_pair, selected_temperature]
        before = self.full_pair_action(
            selected_pair,
            selected_temperature,
            states=states,
        )
        changed = states.copy()
        changed[(selected_replica,) + selected_site] *= -1
        after = self.full_pair_action(
            selected_pair,
            selected_temperature,
            states=changed,
        )
        return float(after - before)

    def _random_local_schedule(self) -> tuple[np.ndarray, np.ndarray]:
        self._local_key, selected_key = jax.random.split(self._local_key)
        count = self._pairs * self._temperatures
        keys = jax.random.split(selected_key, count)
        n_proposals = 2 * self._length**3

        def one_schedule(key: jax.Array) -> tuple[jax.Array, jax.Array]:
            order_key, uniform_key = jax.random.split(key)
            return (
                jax.random.permutation(order_key, n_proposals),
                jax.random.uniform(
                    uniform_key,
                    shape=(n_proposals,),
                    dtype=jnp.float64,
                    minval=jnp.finfo(jnp.float64).tiny,
                    maxval=1.0,
                ),
            )

        order, uniform = jax.vmap(one_schedule)(keys)
        shape = (self._pairs, self._temperatures, n_proposals)
        return np.asarray(order).reshape(shape), np.asarray(uniform).reshape(shape)

    def _validated_local_schedule(
        self,
        orders: np.ndarray | None,
        uniforms: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if orders is None and uniforms is None:
            return self._random_local_schedule()
        if orders is None or uniforms is None:
            raise ValueError("orders and uniforms must be supplied together")
        n_proposals = 2 * self._length**3
        expected = (self._pairs, self._temperatures, n_proposals)
        selected_orders = np.asarray(orders)
        selected_uniforms = np.asarray(uniforms, dtype=np.float64)
        if selected_orders.shape != expected or selected_uniforms.shape != expected:
            raise ValueError(f"local schedules must have shape {expected}")
        target = np.arange(n_proposals)
        if any(
            not np.array_equal(np.sort(row), target)
            for row in selected_orders.reshape(-1, n_proposals)
        ):
            raise ValueError("every local order must be one complete permutation")
        if not np.all(np.isfinite(selected_uniforms)) or np.any(
            (selected_uniforms <= 0.0) | (selected_uniforms >= 1.0)
        ):
            raise ValueError("local uniforms must lie strictly inside (0,1)")
        return selected_orders.astype(np.int32), selected_uniforms

    def _attempt_local(
        self,
        *,
        orders: np.ndarray | None,
        uniforms: np.ndarray | None,
        validate: bool,
    ) -> BiasedSweepResult:
        if validate:
            self.assert_cache_consistent()
        selected_orders, selected_uniforms = self._validated_local_schedule(
            orders,
            uniforms,
        )
        states = self._pairs * self._temperatures
        betas = np.broadcast_to(
            np.asarray(self._betas)[None, :],
            (self._pairs, self._temperatures),
        ).reshape(states)
        lookup_size = 1 << self.token_count
        lookups = np.broadcast_to(
            self._lookups_host[None, :, :],
            (self._pairs, self._temperatures, lookup_size),
        ).reshape(states, lookup_size)
        started = time.perf_counter()
        result = _batched_biased_sweep(
            self._spins.reshape((states,) + self._spins.shape[2:]),
            self._energies.reshape((states, 2)),
            self._block_sums.reshape((states, self._coarse_sites)),
            self._q_prime.reshape((states, self._coarse_sites)),
            self._token_codes.reshape((states, self._coarse_sites)),
            self._bias_values.reshape((states,)),
            self._bonds,
            jnp.asarray(betas, dtype=jnp.float64),
            jnp.asarray(lookups, dtype=jnp.float64),
            self._affected_centers,
            self._affected_masks,
            self._micro_to_coarse,
            jnp.asarray(selected_orders.reshape(states, -1), dtype=jnp.int32),
            jnp.asarray(selected_uniforms.reshape(states, -1), dtype=jnp.float64),
        )
        result[0].block_until_ready()
        elapsed = time.perf_counter() - started
        if not self._compiled_local:
            self.compile_seconds += elapsed
            self._compiled_local = True
        deltas = np.asarray(result[6]).reshape(selected_orders.shape)
        accepted = np.asarray(result[7]).reshape(selected_orders.shape)
        if not np.all(np.isfinite(deltas)):
            raise FloatingPointError("JIT local kernel produced non-finite action deltas")
        self._spins = result[0].reshape(self._spins.shape)
        self._energies = result[1].reshape(self._energies.shape)
        self._block_sums = result[2].reshape(self._block_sums.shape)
        self._q_prime = result[3].reshape(self._q_prime.shape)
        self._token_codes = result[4].reshape(self._token_codes.shape)
        self._bias_values = result[5].reshape(self._bias_values.shape)
        attempts = int(accepted.size)
        accepts = int(np.sum(accepted))
        self.proposed_changes += attempts
        self.accepted_changes += accepts
        if accepts:
            self._generation += 1
        if validate:
            self.assert_cache_consistent()
        return BiasedSweepResult(deltas, accepted)

    def attempt_local(
        self,
        *,
        orders: np.ndarray | None = None,
        uniforms: np.ndarray | None = None,
    ) -> BiasedSweepResult:
        return self._attempt_local(
            orders=orders,
            uniforms=uniforms,
            validate=True,
        )

    def swap_action_delta(self, pair: int, lower: int) -> float:
        self.assert_cache_consistent()
        selected_pair = int(pair)
        selected_lower = int(lower)
        if not 0 <= selected_pair < self._pairs or not 0 <= selected_lower < self._temperatures - 1:
            raise ValueError("swap edge lies outside the PT ladder")
        upper = selected_lower + 1
        states = self.spins[selected_pair]
        result = float(
            self.full_pair_action(selected_pair, selected_lower, states=states[upper])
            + self.full_pair_action(selected_pair, upper, states=states[selected_lower])
            - self.full_pair_action(selected_pair, selected_lower, states=states[selected_lower])
            - self.full_pair_action(selected_pair, upper, states=states[upper])
        )
        if not math.isfinite(result):
            raise FloatingPointError("swap action delta is not finite")
        return result

    def _validated_swap_uniforms(self, uniforms: np.ndarray | None) -> np.ndarray:
        expected = (self._pairs, self._temperatures - 1)
        if uniforms is None:
            self._swap_key, selected_key = jax.random.split(self._swap_key)
            return np.asarray(
                jax.random.uniform(
                    selected_key,
                    shape=expected,
                    dtype=jnp.float64,
                    minval=jnp.finfo(jnp.float64).tiny,
                    maxval=1.0,
                )
            )
        values = np.asarray(uniforms, dtype=np.float64)
        if (
            values.shape != expected
            or not np.all(np.isfinite(values))
            or np.any((values <= 0.0) | (values >= 1.0))
        ):
            raise ValueError(
                f"swap uniforms must be finite in (0,1) with shape {expected}"
            )
        return values

    def _attempt_swaps(
        self,
        parity: int,
        *,
        uniforms: np.ndarray | None,
        validate: bool,
    ) -> np.ndarray:
        if validate:
            self.assert_cache_consistent()
        selected_parity = int(parity) % 2
        random_values = self._validated_swap_uniforms(uniforms)
        kernel = _biased_swap_even if selected_parity == 0 else _biased_swap_odd
        started = time.perf_counter()
        result = kernel(
            self._spins,
            self._energies,
            self._block_sums,
            self._q_prime,
            self._token_codes,
            self._bias_values,
            self._replica_ids,
            self._betas,
            self._lookups,
            jnp.asarray(random_values, dtype=jnp.float64),
        )
        result[0].block_until_ready()
        elapsed = time.perf_counter() - started
        if not self._compiled_swap:
            self.compile_seconds += elapsed
            self._compiled_swap = True
        self._spins = result[0]
        self._energies = result[1]
        self._block_sums = result[2]
        self._q_prime = result[3]
        self._token_codes = result[4]
        self._bias_values = result[5]
        self._replica_ids = result[6]
        accepted = np.asarray(result[7])
        for edge in range(selected_parity, self._temperatures - 1, 2):
            self.swap_attempts[edge] += self._pairs
            self.swap_accepts[edge] += int(np.sum(accepted[:, edge]))
        if np.any(accepted):
            self._generation += 1
        self._update_round_trip_state()
        if validate:
            self.assert_cache_consistent()
        return accepted

    def attempt_swaps(
        self,
        parity: int,
        *,
        uniforms: np.ndarray | None = None,
    ) -> np.ndarray:
        return self._attempt_swaps(
            parity,
            uniforms=uniforms,
            validate=True,
        )

    def _update_round_trip_state(self) -> None:
        positions = np.argsort(self.replica_ids, axis=1)
        at_low = positions == 0
        at_high = positions == self._temperatures - 1
        at_endpoint = at_low | at_high
        self._time_since_endpoint = np.where(
            at_endpoint,
            0,
            self._time_since_endpoint + 1,
        )
        low_started = (self._round_trip_phase == 0) & at_low
        high_reached = (self._round_trip_phase == 1) & at_high
        low_returned = (self._round_trip_phase == 2) & at_low
        self._round_trip_phase[low_started] = 1
        self._round_trip_phase[high_reached] = 2
        self._round_trips[low_returned] += 1
        self._round_trip_phase[low_returned] = 1

    def _attempt_global_q_flip(
        self,
        pair: int,
        temperature: int,
        *,
        replica: int,
        validate: bool,
    ) -> bool:
        if validate:
            self.assert_cache_consistent()
        selected_pair, selected_temperature = self._validate_pair_temperature(
            pair,
            temperature,
        )
        selected_replica = int(replica)
        if selected_replica not in (0, 1):
            raise ValueError("replica index must be zero or one")
        before = self.full_pair_action(selected_pair, selected_temperature)
        spins = self.spins
        spins[selected_pair, selected_temperature, selected_replica] *= -1
        after = self.full_pair_action(
            selected_pair,
            selected_temperature,
            states=spins[selected_pair, selected_temperature],
        )
        if not math.isclose(after, before, rel_tol=0.0, abs_tol=3e-10):
            raise ValueError("single-replica global flip is not an exact q symmetry")
        energies, sums, q_prime, codes, bias_values = self._host_cache(spins)
        self._spins = jnp.asarray(spins, dtype=jnp.int8)
        self._energies = jnp.asarray(energies, dtype=jnp.int64)
        self._block_sums = jnp.asarray(sums, dtype=jnp.int16)
        self._q_prime = jnp.asarray(q_prime, dtype=jnp.int8)
        self._token_codes = jnp.asarray(codes, dtype=jnp.int32)
        self._bias_values = jnp.asarray(bias_values, dtype=jnp.float64)
        self._global_key, _ = jax.random.split(self._global_key)
        self.global_flip_attempts += 1
        self._generation += 1
        if validate:
            self.assert_cache_consistent()
        return True

    def attempt_global_q_flip(
        self,
        pair: int,
        temperature: int,
        *,
        replica: int,
    ) -> bool:
        return self._attempt_global_q_flip(
            pair,
            temperature,
            replica=replica,
            validate=True,
        )

    def run_sweeps(self, sweeps: int, progress_every: int | None = None) -> None:
        if isinstance(sweeps, (bool, np.bool_)) or not isinstance(
            sweeps,
            (int, np.integer),
        ) or int(sweeps) < 0:
            raise ValueError("sweeps must be a nonnegative integer")
        if progress_every is not None and int(progress_every) < 1:
            raise ValueError("progress_every must be positive")
        self.assert_cache_consistent()
        for completed in range(1, int(sweeps) + 1):
            self._attempt_local(orders=None, uniforms=None, validate=False)
            self._attempt_swaps(
                self.sweep_count % 2,
                uniforms=None,
                validate=False,
            )
            self._global_key, choice_key = jax.random.split(self._global_key)
            pair_key, temperature_key, replica_key = jax.random.split(choice_key, 3)
            pair = int(jax.random.randint(pair_key, (), 0, self._pairs))
            temperature = int(
                jax.random.randint(temperature_key, (), 0, self._temperatures)
            )
            replica = int(jax.random.randint(replica_key, (), 0, 2))
            self._attempt_global_q_flip(
                pair,
                temperature,
                replica=replica,
                validate=False,
            )
            self.sweep_count += 1
            if progress_every and completed % int(progress_every) == 0:
                attempted = self.swap_attempts > 0
                swap_min = (
                    float(
                        np.min(
                            self.swap_accepts[attempted]
                            / self.swap_attempts[attempted]
                        )
                    )
                    if np.any(attempted)
                    else 0.0
                )
                print(
                    f"jax biased PT sweep={completed}/{sweeps} "
                    f"local_accept={self.accepted_changes}/{self.proposed_changes} "
                    f"swap_min={swap_min:.6g}",
                    flush=True,
                )
        self.assert_cache_consistent()

    def measure(self) -> dict[str, np.ndarray]:
        return {
            "energy": self.energies,
            "pair_energy": np.sum(self.energies, axis=2, dtype=np.int64),
            "bias": self.bias_values,
            "q_prime": self.q_prime,
        }

    def checkpoint_state(self) -> dict[str, Any]:
        self.assert_cache_consistent()
        return {
            "schema_version": 1,
            "bias_signature": self._bias_signature,
            "spins": self.spins,
            "energies": self.energies,
            "block_sums": self.block_sums,
            "q_prime": self.q_prime,
            "token_codes": self.token_codes,
            "bias_values": self.bias_values,
            "replica_ids": self.replica_ids,
            "local_key": np.asarray(self._local_key).copy(),
            "swap_key": np.asarray(self._swap_key).copy(),
            "global_key": np.asarray(self._global_key).copy(),
            "accepted_changes": self.accepted_changes,
            "proposed_changes": self.proposed_changes,
            "global_flip_attempts": self.global_flip_attempts,
            "swap_attempts": self.swap_attempts.copy(),
            "swap_accepts": self.swap_accepts.copy(),
            "round_trip_phase": self._round_trip_phase.copy(),
            "round_trips": self._round_trips.copy(),
            "time_since_endpoint": self._time_since_endpoint.copy(),
            "sweep_count": self.sweep_count,
            "generation": self._generation,
        }

    def _validated_checkpoint_state(self, state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(state, dict):
            raise TypeError("checkpoint state must be a dictionary")
        expected = set(self.checkpoint_state())
        version = state.get("schema_version")
        if (
            set(state) != expected
            or isinstance(version, (bool, np.bool_))
            or not isinstance(version, (int, np.integer))
            or int(version) != 1
        ):
            raise ValueError("biased PT checkpoint inventory is incomplete")
        self._assert_bias_parameters_current()
        if state.get("bias_signature") != self._bias_signature:
            raise ValueError("biased PT checkpoint bias signature mismatch")
        spins = _checkpoint_binary_array(
            state["spins"],
            dtype=np.dtype(np.int8),
            label="spins",
        )
        recomputed = self._host_cache(spins)
        bias_raw = np.asarray(state["bias_values"])
        if bias_raw.dtype.kind not in {"i", "u", "f"}:
            raise TypeError("biased PT checkpoint bias values must be numeric")
        bias_values = bias_raw.astype(np.float64, copy=True)
        if not np.all(np.isfinite(bias_values)):
            raise ValueError("biased PT checkpoint bias values must be finite")
        supplied = (
            _checkpoint_integer_array(
                state["energies"],
                dtype=np.dtype(np.int64),
                label="energies",
            ),
            _checkpoint_integer_array(
                state["block_sums"],
                dtype=np.dtype(np.int16),
                label="block sums",
            ),
            _checkpoint_binary_array(
                state["q_prime"],
                dtype=np.dtype(np.int8),
                label="q-prime",
            ),
            _checkpoint_integer_array(
                state["token_codes"],
                dtype=np.dtype(np.int32),
                label="token codes",
            ),
            bias_values,
        )
        for index, (observed, wanted) in enumerate(zip(supplied, recomputed, strict=True)):
            matches = (
                np.allclose(observed, wanted, atol=2e-10, rtol=0.0)
                if index == 4
                else np.array_equal(observed, wanted)
            )
            if not matches:
                raise RuntimeError("stale cache in biased PT checkpoint")
        keys = [np.asarray(state[name]) for name in (
            "local_key", "swap_key", "global_key"
        )]
        if any(key.dtype != np.dtype(np.uint32) for key in keys):
            raise TypeError("biased PT checkpoint RNG keys must have dtype uint32")
        if any(key.shape != (2,) for key in keys):
            raise ValueError("biased PT checkpoint RNG keys are invalid")
        keys = [key.copy() for key in keys]
        replica_ids = _checkpoint_integer_array(
            state["replica_ids"],
            dtype=np.dtype(np.int64),
            label="replica IDs",
        )
        expected_ids = np.arange(self._temperatures)
        if replica_ids.shape != (self._pairs, self._temperatures) or any(
            not np.array_equal(np.sort(row), expected_ids) for row in replica_ids
        ):
            raise ValueError("biased PT checkpoint replica IDs are invalid")
        swap_attempts = _checkpoint_integer_array(
            state["swap_attempts"],
            dtype=np.dtype(np.int64),
            label="swap attempts",
        )
        swap_accepts = _checkpoint_integer_array(
            state["swap_accepts"],
            dtype=np.dtype(np.int64),
            label="swap accepts",
        )
        tracker_shape = (self._pairs, self._temperatures)
        phase = _checkpoint_integer_array(
            state["round_trip_phase"],
            dtype=np.dtype(np.int8),
            label="round-trip phase",
        )
        trips = _checkpoint_integer_array(
            state["round_trips"],
            dtype=np.dtype(np.int64),
            label="round trips",
        )
        since = _checkpoint_integer_array(
            state["time_since_endpoint"],
            dtype=np.dtype(np.int64),
            label="time-since-endpoint",
        )
        if phase.shape == tracker_shape and np.any((phase < 0) | (phase > 2)):
            raise ValueError("biased PT checkpoint round-trip phase is invalid")
        counter_names = (
            "accepted_changes",
            "proposed_changes",
            "global_flip_attempts",
            "sweep_count",
            "generation",
        )
        if any(
            isinstance(state[name], (bool, np.bool_))
            or not isinstance(state[name], (int, np.integer))
            for name in counter_names
        ):
            raise TypeError("biased PT checkpoint counters must be integer scalars")
        counters = [int(state[name]) for name in counter_names]
        if (
            swap_attempts.shape != (self._temperatures - 1,)
            or swap_accepts.shape != swap_attempts.shape
            or phase.shape != tracker_shape
            or trips.shape != tracker_shape
            or since.shape != tracker_shape
            or any(value < 0 for value in counters)
            or counters[0] > counters[1]
            or np.any(swap_attempts < 0)
            or np.any(swap_accepts < 0)
            or np.any(swap_accepts > swap_attempts)
            or np.any(trips < 0)
            or np.any(since < 0)
        ):
            raise ValueError("biased PT checkpoint counters are invalid")
        return {
            "spins": spins,
            "supplied": supplied,
            "keys": keys,
            "replica_ids": replica_ids,
            "counters": counters,
            "swap_attempts": swap_attempts,
            "swap_accepts": swap_accepts,
            "phase": phase,
            "trips": trips,
            "since": since,
        }

    def validate_checkpoint_state(self, state: dict[str, Any]) -> None:
        """Validate a complete checkpoint without mutating sampler state."""

        self._validated_checkpoint_state(state)

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        validated = self._validated_checkpoint_state(state)
        supplied = validated["supplied"]
        keys = validated["keys"]
        counters = validated["counters"]
        self._spins = jnp.asarray(validated["spins"], dtype=jnp.int8)
        self._energies = jnp.asarray(supplied[0], dtype=jnp.int64)
        self._block_sums = jnp.asarray(supplied[1], dtype=jnp.int16)
        self._q_prime = jnp.asarray(supplied[2], dtype=jnp.int8)
        self._token_codes = jnp.asarray(supplied[3], dtype=jnp.int32)
        self._bias_values = jnp.asarray(supplied[4], dtype=jnp.float64)
        self._replica_ids = jnp.asarray(validated["replica_ids"], dtype=jnp.int64)
        self._local_key = jnp.asarray(keys[0], dtype=jnp.uint32)
        self._swap_key = jnp.asarray(keys[1], dtype=jnp.uint32)
        self._global_key = jnp.asarray(keys[2], dtype=jnp.uint32)
        self.accepted_changes = counters[0]
        self.proposed_changes = counters[1]
        self.global_flip_attempts = counters[2]
        self.sweep_count = counters[3]
        self._generation = counters[4]
        self.swap_attempts = validated["swap_attempts"].copy()
        self.swap_accepts = validated["swap_accepts"].copy()
        self._round_trip_phase = validated["phase"].copy()
        self._round_trips = validated["trips"].copy()
        self._time_since_endpoint = validated["since"].copy()
        self.assert_cache_consistent()

    def resource_snapshot(self) -> dict[str, object]:
        device = jax.devices()[0]
        statistics = device.memory_stats() or {}
        device_bytes = int(
            statistics.get(
                "peak_bytes_in_use",
                statistics.get("bytes_in_use", 0),
            )
        )
        return {
            "backend": "jax-biased-pair-pt",
            "required_platform": self.required_platform,
            "platform": jax.default_backend(),
            "device": str(device),
            "float64_enabled": bool(jax.config.jax_enable_x64),
            "jit_disabled": bool(jax.config.jax_disable_jit),
            "host_rss_bytes": _host_rss_bytes(),
            "device_memory_bytes": device_bytes,
            "compile_seconds": self.compile_seconds,
            "lookup_build_seconds": self.lookup_build_seconds,
            "local_bias_centers_per_proposal": int(
                self._affected_centers_host.shape[1]
            ),
            "local_bias_geometry_entries": int(self._affected_centers_host.size),
            "spin_proposals": self.proposed_changes,
            "accepted_changes": self.accepted_changes,
            "sweep_count": self.sweep_count,
            "generation": self._generation,
            "context_signature": self.context_signature,
            "route": self._biases[0].route.value,
            "template": self._encoder.kind.value,
            "rank": self._biases[0].tt.model.chi,
            "bias_signature": self._bias_signature,
        }
