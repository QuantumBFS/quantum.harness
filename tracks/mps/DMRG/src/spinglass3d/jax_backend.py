"""Optional float64 JAX backend vectorized only over independent states."""

from __future__ import annotations

import copy
import time

import numpy as np

import jax
import jax.numpy as jnp

from .backend import BackendCase, _host_rss_bytes
from .tensor_train import LocalTensorTrain

jax.config.update("jax_enable_x64", True)


@jax.tree_util.register_pytree_node_class
class JaxTensorTrain:
    """Tensor-Train cores carried as an explicit JAX PyTree."""

    def __init__(self, cores: tuple[jax.Array, ...]) -> None:
        self.cores = tuple(cores)

    @classmethod
    def from_local(cls, model: LocalTensorTrain) -> "JaxTensorTrain":
        if not isinstance(model, LocalTensorTrain):
            raise TypeError("model must be LocalTensorTrain")
        return cls(tuple(jnp.asarray(core, dtype=jnp.float64) for core in model.cores))

    def tree_flatten(self) -> tuple[tuple[jax.Array, ...], None]:
        return self.cores, None

    @classmethod
    def tree_unflatten(
        cls,
        auxiliary: None,
        children: tuple[jax.Array, ...],
    ) -> "JaxTensorTrain":
        del auxiliary
        return cls(tuple(children))

    def value(self, tokens: jax.Array) -> jax.Array:
        state = jnp.ones((1,), dtype=jnp.float64)
        for core, token in zip(self.cores, tokens, strict=True):
            state = state @ core[:, jnp.where(token == -1, 0, 1), :]
        return state[0]


def _delta_grid(spins: jax.Array, bonds: jax.Array) -> jax.Array:
    local = jnp.zeros_like(spins, dtype=jnp.int64)
    for axis in range(3):
        local = local + bonds[..., axis] * jnp.roll(spins, -1, axis=axis)
        local = local + jnp.roll(bonds[..., axis], 1, axis=axis) * jnp.roll(
            spins,
            1,
            axis=axis,
        )
    return 2 * spins.astype(jnp.int64) * local


def _one_energy(spins: jax.Array, bonds: jax.Array) -> jax.Array:
    total = jnp.int64(0)
    for axis in range(3):
        total = total - jnp.sum(
            bonds[..., axis] * spins * jnp.roll(spins, -1, axis=axis),
            dtype=jnp.int64,
        )
    return total


def _temperature_swap_pass(
    spins: jax.Array,
    energies: jax.Array,
    replica_ids: jax.Array,
    betas: jax.Array,
    uniforms: jax.Array,
    *,
    parity: int,
) -> tuple[jax.Array, jax.Array, jax.Array, jax.Array]:
    accepted = jnp.zeros(uniforms.shape, dtype=jnp.bool_)
    for lower in range(parity, spins.shape[1] - 1, 2):
        upper = lower + 1
        delta = (betas[lower] - betas[upper]) * (
            energies[:, upper, :] - energies[:, lower, :]
        )
        take = jnp.log(uniforms[:, lower, :]) < jnp.minimum(0.0, -delta)
        mask = take[..., None, None, None]
        lower_spins = spins[:, lower, ...]
        upper_spins = spins[:, upper, ...]
        spins = spins.at[:, lower, ...].set(
            jnp.where(mask, upper_spins, lower_spins)
        )
        spins = spins.at[:, upper, ...].set(
            jnp.where(mask, lower_spins, upper_spins)
        )
        lower_energies = energies[:, lower, :]
        upper_energies = energies[:, upper, :]
        energies = energies.at[:, lower, :].set(
            jnp.where(take, upper_energies, lower_energies)
        )
        energies = energies.at[:, upper, :].set(
            jnp.where(take, lower_energies, upper_energies)
        )
        lower_ids = replica_ids[:, lower, :]
        upper_ids = replica_ids[:, upper, :]
        replica_ids = replica_ids.at[:, lower, :].set(
            jnp.where(take, upper_ids, lower_ids)
        )
        replica_ids = replica_ids.at[:, upper, :].set(
            jnp.where(take, lower_ids, upper_ids)
        )
        accepted = accepted.at[:, lower, :].set(take)
    return spins, energies, replica_ids, accepted


def _one_random_sequential_sweep(
    spins: jax.Array,
    bonds: jax.Array,
    beta: jax.Array,
    key: jax.Array,
) -> tuple[jax.Array, jax.Array]:
    length = spins.shape[0]
    n_sites = length**3
    order_key, uniform_key = jax.random.split(key)
    order = jax.random.permutation(order_key, n_sites)
    uniforms = jax.random.uniform(
        uniform_key,
        shape=(n_sites,),
        dtype=jnp.float64,
        minval=jnp.finfo(jnp.float64).tiny,
        maxval=1.0,
    )

    def update(
        carry: tuple[jax.Array, jax.Array],
        item: tuple[jax.Array, jax.Array],
    ) -> tuple[tuple[jax.Array, jax.Array], None]:
        state, accepted = carry
        flat_site, uniform = item
        x = flat_site // (length * length)
        remainder = flat_site % (length * length)
        y = remainder // length
        z = remainder % length
        spin = state[x, y, z]
        local = jnp.int64(0)
        coordinates = (x, y, z)
        for axis in range(3):
            plus = list(coordinates)
            minus = list(coordinates)
            plus[axis] = (plus[axis] + 1) % length
            minus[axis] = (minus[axis] - 1) % length
            local = local + bonds[x, y, z, axis] * state[tuple(plus)]
            local = local + bonds[tuple(minus) + (axis,)] * state[tuple(minus)]
        difference = 2 * spin * local
        take = jnp.log(uniform) < jnp.minimum(0.0, -beta * difference)
        state = state.at[x, y, z].set(jnp.where(take, -spin, spin))
        return (state, accepted + take.astype(jnp.int64)), None

    (result, accepted), _ = jax.lax.scan(
        update,
        (spins, jnp.int64(0)),
        (order, uniforms),
    )
    return result, accepted


_batched_deltas = jax.jit(jax.vmap(_delta_grid, in_axes=(0, 0)))
_batched_energies = jax.jit(jax.vmap(_one_energy, in_axes=(0, 0)))
_batched_sweep = jax.jit(
    jax.vmap(_one_random_sequential_sweep, in_axes=(0, 0, 0, 0))
)
_temperature_swap_even = jax.jit(
    lambda spins, energies, replica_ids, betas, uniforms: _temperature_swap_pass(
        spins,
        energies,
        replica_ids,
        betas,
        uniforms,
        parity=0,
    )
)
_temperature_swap_odd = jax.jit(
    lambda spins, energies, replica_ids, betas, uniforms: _temperature_swap_pass(
        spins,
        energies,
        replica_ids,
        betas,
        uniforms,
        parity=1,
    )
)


class JaxBatchedBackend:
    def __init__(self, case: BackendCase) -> None:
        if not isinstance(case, BackendCase):
            raise TypeError("case must be BackendCase")
        self.case = case
        samples, temperatures, walkers = case.spins.shape[:3]
        length = case.spins.shape[-1]
        self._state_shape = (samples, temperatures, walkers)
        self._flat_spins = jnp.asarray(
            case.spins.reshape(-1, length, length, length),
            dtype=jnp.int8,
        )
        broadcast_bonds = np.broadcast_to(
            case.bonds[:, None, None, ...],
            (samples, temperatures, walkers, length, length, length, 3),
        )
        self._flat_bonds = jnp.asarray(
            broadcast_bonds.reshape(-1, length, length, length, 3),
            dtype=jnp.int8,
        )
        broadcast_betas = np.broadcast_to(
            case.betas[None, :, None],
            (samples, temperatures, walkers),
        )
        self._flat_betas = jnp.asarray(broadcast_betas.reshape(-1), dtype=jnp.float64)
        self._key = jax.random.PRNGKey(case.seed + 2_000_003)
        self.accepted_changes = 0
        self.proposed_changes = 0
        self.compile_seconds = 0.0
        self._compiled_deltas = False
        self._compiled_sweep = False

    @property
    def spins(self) -> np.ndarray:
        length = self.case.spins.shape[-1]
        return np.asarray(self._flat_spins).reshape(
            self._state_shape + (length, length, length)
        )

    def all_proposal_deltas(self) -> np.ndarray:
        started = time.perf_counter()
        result = _batched_deltas(self._flat_spins, self._flat_bonds)
        result.block_until_ready()
        if not self._compiled_deltas:
            self.compile_seconds += time.perf_counter() - started
            self._compiled_deltas = True
        length = self.case.spins.shape[-1]
        return np.asarray(result).reshape(
            self._state_shape + (length, length, length)
        )

    def accept_decisions(self, uniforms: np.ndarray) -> np.ndarray:
        values = np.asarray(uniforms, dtype=np.float64)
        if values.shape != self.case.spins.shape or np.any(values <= 0.0) or np.any(values >= 1.0):
            raise ValueError("uniforms must lie strictly inside (0,1) with spin shape")
        deltas = self.all_proposal_deltas().astype(np.float64)
        beta_shape = (1, self.case.betas.size, 1, 1, 1, 1)
        return np.log(values) < np.minimum(
            0.0,
            -deltas * self.case.betas.reshape(beta_shape),
        )

    def sweeps(self, count: int) -> None:
        if count < 0:
            raise ValueError("sweep count must be nonnegative")
        n_states = self._flat_spins.shape[0]
        n_sites = self.case.spins.shape[-1] ** 3
        for _ in range(count):
            self._key, sweep_key = jax.random.split(self._key)
            keys = jax.random.split(sweep_key, n_states)
            started = time.perf_counter()
            spins, accepted = _batched_sweep(
                self._flat_spins,
                self._flat_bonds,
                self._flat_betas,
                keys,
            )
            spins.block_until_ready()
            if not self._compiled_sweep:
                self.compile_seconds += time.perf_counter() - started
                self._compiled_sweep = True
            self._flat_spins = spins
            self.accepted_changes += int(np.asarray(accepted).sum())
            self.proposed_changes += int(n_states * n_sites)

    def measure(self) -> dict[str, np.ndarray]:
        values = _batched_energies(
            self._flat_spins,
            self._flat_bonds,
        )
        return {"energy": np.asarray(values).reshape(self._state_shape)}

    def checkpoint_state(self) -> dict[str, object]:
        return {
            "spins": self.spins.copy(),
            "jax_key": np.asarray(self._key).copy(),
            "accepted_changes": self.accepted_changes,
            "proposed_changes": self.proposed_changes,
        }

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
            "backend": "jax-batched",
            "host_rss_bytes": _host_rss_bytes(),
            "device_memory_bytes": device_bytes,
            "device": str(device),
            "float64_enabled": bool(jax.config.jax_enable_x64),
            "compile_seconds": self.compile_seconds,
        }


class JaxParallelTemperingBackend:
    """Full-ladder unbiased PT over independent disorder/walker batches."""

    def __init__(self, case: BackendCase) -> None:
        if not isinstance(case, BackendCase):
            raise TypeError("case must be BackendCase")
        samples, temperatures, walkers = case.spins.shape[:3]
        if temperatures < 2:
            raise ValueError("parallel tempering needs at least two temperatures")
        if walkers < 2 or walkers % 2:
            raise ValueError("overlap PT requires an even number of walkers")
        self.case = case
        self._local = JaxBatchedBackend(case)
        self._samples = samples
        self._temperatures = temperatures
        self._walkers = walkers
        ids = np.broadcast_to(
            np.arange(temperatures, dtype=np.int64)[None, :, None],
            (samples, temperatures, walkers),
        ).copy()
        self._replica_ids = jnp.asarray(ids, dtype=jnp.int64)
        self._swap_key = jax.random.PRNGKey(case.seed + 3_000_003)
        self.swap_attempts = np.zeros(temperatures - 1, dtype=np.int64)
        self.swap_accepts = np.zeros(temperatures - 1, dtype=np.int64)
        self.sweep_count = 0
        tracker_shape = (samples, walkers, temperatures)
        self._round_trip_phase = np.zeros(tracker_shape, dtype=np.int8)
        self._round_trips = np.zeros(tracker_shape, dtype=np.int64)
        self._time_since_endpoint = np.zeros(tracker_shape, dtype=np.int64)
        self._update_round_trip_state()

    @property
    def spins(self) -> np.ndarray:
        return self._local.spins

    @property
    def replica_ids(self) -> np.ndarray:
        return np.asarray(self._replica_ids).copy()

    @property
    def round_trips(self) -> np.ndarray:
        return self._round_trips.copy()

    @property
    def time_since_endpoint(self) -> np.ndarray:
        return self._time_since_endpoint.copy()

    @property
    def accepted_changes(self) -> int:
        return self._local.accepted_changes

    @property
    def proposed_changes(self) -> int:
        return self._local.proposed_changes

    def _shaped_device_spins(self) -> jax.Array:
        length = self.case.spins.shape[-1]
        return self._local._flat_spins.reshape(  # noqa: SLF001
            self._samples,
            self._temperatures,
            self._walkers,
            length,
            length,
            length,
        )

    def _shaped_device_bonds(self) -> jax.Array:
        length = self.case.spins.shape[-1]
        return self._local._flat_bonds.reshape(  # noqa: SLF001
            self._samples,
            self._temperatures,
            self._walkers,
            length,
            length,
            length,
            3,
        )

    def _update_round_trip_state(self) -> None:
        labels = self.replica_ids
        positions = np.argsort(labels, axis=1).transpose(0, 2, 1)
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

    def attempt_swaps(
        self,
        parity: int,
        uniforms: np.ndarray | None = None,
    ) -> np.ndarray:
        selected_parity = int(parity) % 2
        spins = self._shaped_device_spins()
        bonds = self._shaped_device_bonds()
        flat_energies = _batched_energies(
            spins.reshape((-1,) + spins.shape[-3:]),
            bonds.reshape((-1,) + bonds.shape[-4:]),
        )
        energies = flat_energies.reshape(
            self._samples,
            self._temperatures,
            self._walkers,
        )
        expected_shape = (
            self._samples,
            self._temperatures - 1,
            self._walkers,
        )
        if uniforms is None:
            self._swap_key, selected_key = jax.random.split(self._swap_key)
            random_values = jax.random.uniform(
                selected_key,
                shape=expected_shape,
                dtype=jnp.float64,
                minval=jnp.finfo(jnp.float64).tiny,
                maxval=1.0,
            )
        else:
            values = np.asarray(uniforms, dtype=np.float64)
            if (
                values.shape != expected_shape
                or np.any(values <= 0.0)
                or np.any(values >= 1.0)
            ):
                raise ValueError(
                    f"swap uniforms must lie in (0,1) with shape {expected_shape}"
                )
            random_values = jnp.asarray(values, dtype=jnp.float64)
        kernel = _temperature_swap_even if selected_parity == 0 else _temperature_swap_odd
        spins, _, replica_ids, accepted = kernel(
            spins,
            energies,
            self._replica_ids,
            self._local._flat_betas.reshape(  # noqa: SLF001
                self._samples,
                self._temperatures,
                self._walkers,
            )[0, :, 0],
            random_values,
        )
        spins.block_until_ready()
        self._local._flat_spins = spins.reshape(self._local._flat_spins.shape)  # noqa: SLF001
        self._replica_ids = replica_ids
        accepted_host = np.asarray(accepted)
        attempted_edges = np.arange(
            selected_parity,
            self._temperatures - 1,
            2,
        )
        for edge in attempted_edges:
            self.swap_attempts[edge] += self._samples * self._walkers
            self.swap_accepts[edge] += int(np.sum(accepted_host[:, edge, :]))
        self._update_round_trip_state()
        return accepted_host

    def run_sweeps(self, sweeps: int, progress_every: int | None = None) -> None:
        if isinstance(sweeps, bool) or not isinstance(sweeps, (int, np.integer)):
            raise ValueError("sweeps must be an integer")
        if int(sweeps) < 0:
            raise ValueError("sweeps must be nonnegative")
        for completed in range(1, int(sweeps) + 1):
            self._local.sweeps(1)
            self.attempt_swaps(self.sweep_count % 2)
            self.sweep_count += 1
            if progress_every and completed % progress_every == 0:
                attempted = self.swap_attempts > 0
                minimum = (
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
                    f"jax PT sweep={completed}/{sweeps} "
                    f"swap_min={minimum:.6g} "
                    f"round_trips_min={int(np.min(self._round_trips))}",
                    flush=True,
                )

    def measure(self) -> dict[str, np.ndarray]:
        return self._local.measure()

    def overlap_fields(self) -> np.ndarray:
        states = self.spins
        paired = states.reshape(
            self._samples,
            self._temperatures,
            self._walkers // 2,
            2,
            *states.shape[-3:],
        )
        return np.multiply(paired[:, :, :, 0], paired[:, :, :, 1], dtype=np.int8)

    def checkpoint_state(self) -> dict[str, object]:
        return {
            "sampler": self._local.checkpoint_state(),
            "swap_key": np.asarray(self._swap_key).copy(),
            "replica_ids": self.replica_ids,
            "swap_attempts": self.swap_attempts.copy(),
            "swap_accepts": self.swap_accepts.copy(),
            "sweep_count": self.sweep_count,
            "round_trip_phase": self._round_trip_phase.copy(),
            "round_trips": self._round_trips.copy(),
            "time_since_endpoint": self._time_since_endpoint.copy(),
        }

    def _validated_checkpoint_state(
        self,
        state: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(state, dict):
            raise TypeError("checkpoint state must be a dictionary")
        expected = {
            "sampler",
            "swap_key",
            "replica_ids",
            "swap_attempts",
            "swap_accepts",
            "sweep_count",
            "round_trip_phase",
            "round_trips",
            "time_since_endpoint",
        }
        if set(state) != expected or not isinstance(state["sampler"], dict):
            raise ValueError("parallel-tempering checkpoint is incomplete")
        sampler = state["sampler"]
        if set(sampler) != {
            "spins",
            "jax_key",
            "accepted_changes",
            "proposed_changes",
        }:
            raise ValueError("parallel-tempering sampler checkpoint is incomplete")
        spins = np.asarray(sampler["spins"])
        if (
            spins.dtype != np.dtype(np.int8)
            or spins.shape != self.case.spins.shape
            or not np.all(
            (spins == -1) | (spins == 1)
            )
        ):
            raise ValueError("checkpoint spins are invalid")
        local_key = np.asarray(sampler["jax_key"])
        swap_key = np.asarray(state["swap_key"])
        if (
            local_key.dtype != np.dtype(np.uint32)
            or swap_key.dtype != np.dtype(np.uint32)
        ):
            raise TypeError("checkpoint JAX keys must have dtype uint32")
        if local_key.shape != (2,) or swap_key.shape != (2,):
            raise ValueError("checkpoint JAX keys are invalid")
        labels = np.asarray(state["replica_ids"])
        expected_labels = (self._samples, self._temperatures, self._walkers)
        sorted_labels = np.sort(labels, axis=1) if labels.shape == expected_labels else None
        wanted_labels = np.broadcast_to(
            np.arange(self._temperatures, dtype=np.int64)[None, :, None],
            expected_labels,
        )
        if (
            labels.dtype != np.dtype(np.int64)
            or labels.shape != expected_labels
            or not np.array_equal(sorted_labels, wanted_labels)
        ):
            raise ValueError("checkpoint replica IDs are invalid")
        edge_shape = (self._temperatures - 1,)
        attempts = np.asarray(state["swap_attempts"])
        accepts = np.asarray(state["swap_accepts"])
        tracker_shape = (self._samples, self._walkers, self._temperatures)
        phase = np.asarray(state["round_trip_phase"])
        trips = np.asarray(state["round_trips"])
        since = np.asarray(state["time_since_endpoint"])
        if (
            attempts.dtype != np.dtype(np.int64)
            or accepts.dtype != np.dtype(np.int64)
            or attempts.shape != edge_shape
            or accepts.shape != edge_shape
        ):
            raise ValueError("checkpoint swap counters are invalid")
        if (
            phase.dtype != np.dtype(np.int8)
            or trips.dtype != np.dtype(np.int64)
            or since.dtype != np.dtype(np.int64)
            or phase.shape != tracker_shape
            or trips.shape != tracker_shape
            or since.shape != tracker_shape
        ):
            raise ValueError("checkpoint round-trip state is invalid")
        if np.any((phase < 0) | (phase > 2)):
            raise ValueError("checkpoint round-trip phase is invalid")
        counter_values = (
            state["sweep_count"],
            sampler["accepted_changes"],
            sampler["proposed_changes"],
        )
        if any(
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, np.integer))
            for value in counter_values
        ):
            raise TypeError("checkpoint counters must be integer scalars")
        sweep_count, local_accepts, local_proposals = (
            int(value) for value in counter_values
        )
        expected_proposals = sweep_count * self.case.spins.size
        edge_indices = np.arange(self._temperatures - 1, dtype=np.int64)
        expected_attempts = np.where(
            edge_indices % 2 == 0,
            (sweep_count + 1) // 2,
            sweep_count // 2,
        ) * self._samples * self._walkers
        maximum_round_trips = sweep_count // (2 * (self._temperatures - 1))
        if (
            sweep_count < 0
            or local_accepts < 0
            or local_proposals < 0
            or local_proposals != expected_proposals
            or local_accepts > local_proposals
            or np.any(attempts < 0)
            or not np.array_equal(attempts, expected_attempts)
            or np.any(accepts < 0)
            or np.any(accepts > attempts)
            or np.any(trips < 0)
            or np.any(trips > maximum_round_trips)
            or np.any(since < 0)
            or np.any(since > sweep_count + 1)
        ):
            raise ValueError("checkpoint counters are invalid")
        return {
            "spins": spins.copy(),
            "local_key": local_key.copy(),
            "swap_key": swap_key.copy(),
            "labels": labels.copy(),
            "attempts": attempts.copy(),
            "accepts": accepts.copy(),
            "sweep_count": sweep_count,
            "local_accepts": local_accepts,
            "local_proposals": local_proposals,
            "phase": phase.copy(),
            "trips": trips.copy(),
            "since": since.copy(),
        }

    def validate_checkpoint_state(self, state: dict[str, object]) -> None:
        """Validate a complete checkpoint without mutating sampler state."""

        self._validated_checkpoint_state(state)

    def restore_checkpoint_state(self, state: dict[str, object]) -> None:
        validated = self._validated_checkpoint_state(state)
        self._local._flat_spins = jnp.asarray(  # noqa: SLF001
            validated["spins"].reshape(self._local._flat_spins.shape),  # noqa: SLF001
            dtype=jnp.int8,
        )
        self._local._key = jnp.asarray(  # noqa: SLF001
            validated["local_key"], dtype=jnp.uint32
        )
        self._local.accepted_changes = validated["local_accepts"]
        self._local.proposed_changes = validated["local_proposals"]
        self._swap_key = jnp.asarray(validated["swap_key"], dtype=jnp.uint32)
        self._replica_ids = jnp.asarray(validated["labels"], dtype=jnp.int64)
        self.swap_attempts = validated["attempts"].copy()
        self.swap_accepts = validated["accepts"].copy()
        self.sweep_count = validated["sweep_count"]
        self._round_trip_phase = validated["phase"].copy()
        self._round_trips = validated["trips"].copy()
        self._time_since_endpoint = validated["since"].copy()

    def resource_snapshot(self) -> dict[str, object]:
        result = dict(self._local.resource_snapshot())
        result.update(
            {
                "backend": "jax-parallel-tempering",
                "sweep_count": self.sweep_count,
                "swap_attempts": self.swap_attempts.copy(),
                "swap_accepts": self.swap_accepts.copy(),
            }
        )
        return result
