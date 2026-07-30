"""Whole-disorder VMCRG sampling over JAX biased-pair backends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy

import numpy as np

from .bias import OverlapBias
from .jax_biased_backend import JaxBiasedPairBackend
from .templates import TemplateEncoder
from .vmcrg import VMCRGBatch


_AUDIT_COUNTER_NAMES = (
    "adapter_sweep_count",
    "retained_biased_draws",
    "generated_target_draws",
)
_AUDIT_COUNTER_KEYS = frozenset(_AUDIT_COUNTER_NAMES)


def select_equal_per_j_rows(
    raw_pools: Sequence[np.ndarray],
    indices_by_j: Sequence[np.ndarray],
) -> np.ndarray:
    """Select the same number of token rows from each disorder pool."""

    if len(raw_pools) != len(indices_by_j) or not raw_pools:
        raise ValueError("one index vector is required per nonempty J pool")
    selected = [
        np.asarray(pool)[np.asarray(indices, dtype=np.int64)]
        for pool, indices in zip(raw_pools, indices_by_j, strict=True)
    ]
    try:
        return np.stack(selected, axis=0)
    except ValueError as error:
        raise ValueError("selected J pools must have one common draw schema") from error


def build_uniform_target_tokens(
    biased_tokens: np.ndarray,
    q_token_indices: Sequence[int],
    rng: np.random.Generator,
) -> np.ndarray:
    values = np.asarray(biased_tokens)
    if values.ndim < 2 or not np.all((values == -1) | (values == 1)):
        raise ValueError("biased tokens must be a binary token array")
    if not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a NumPy Generator")
    indices = tuple(int(index) for index in q_token_indices)
    if (
        not indices
        or len(indices) != len(set(indices))
        or any(index < 0 or index >= values.shape[-1] for index in indices)
    ):
        raise ValueError("q token indices must be unique and inside the token axis")
    target = values.astype(np.int8, copy=True)
    target[..., indices] = rng.choice(
        np.array([-1, 1], dtype=np.int8),
        size=values.shape[:-1] + (len(indices),),
    )
    return target


def decode_token_codes(codes: np.ndarray, token_count: int) -> np.ndarray:
    values = np.asarray(codes)
    if isinstance(token_count, bool) or not isinstance(
        token_count, (int, np.integer)
    ):
        raise TypeError("token_count must be an integer")
    count = int(token_count)
    if count < 1:
        raise ValueError("token_count must be positive")
    if not np.issubdtype(values.dtype, np.integer):
        raise TypeError("token codes must be integers")
    if np.any(values < 0) or np.any(values >= (1 << count)):
        raise ValueError("token code is outside the declared token width")
    bits = np.bitwise_and(
        np.right_shift(values[..., None], np.arange(count, dtype=np.int64)),
        1,
    )
    return np.where(bits == 1, 1, -1).astype(np.int8)


class JaxVMCRGSamplingBackend:
    def __init__(
        self,
        *,
        j_ids: Sequence[str],
        backends: Sequence[JaxBiasedPairBackend],
        draw_count: int,
        target_temperature_index: int,
        sweeps_per_batch: int,
        seed: int,
    ) -> None:
        if isinstance(j_ids, (str, bytes)):
            raise TypeError("J IDs must be a sequence, not a bare string")
        self._j_ids = tuple(j_ids)
        self._backends = tuple(backends)
        if not self._j_ids or len(self._j_ids) != len(self._backends):
            raise ValueError("one JAX backend is required per ordered J ID")
        if (
            any(not isinstance(value, str) or not value for value in self._j_ids)
            or len(set(self._j_ids)) != len(self._j_ids)
        ):
            raise ValueError("ordered J IDs must be unique nonempty strings")
        if any(not isinstance(value, JaxBiasedPairBackend) for value in self._backends):
            raise TypeError("backends must contain JaxBiasedPairBackend instances")
        if isinstance(draw_count, bool) or not isinstance(
            draw_count, (int, np.integer)
        ):
            raise TypeError("draw_count must be an integer")
        if int(draw_count) < 1:
            raise ValueError("draw_count must be a positive integer")
        if isinstance(sweeps_per_batch, bool) or not isinstance(
            sweeps_per_batch, (int, np.integer)
        ):
            raise TypeError("sweeps_per_batch must be an integer")
        if int(sweeps_per_batch) < 0:
            raise ValueError("sweeps_per_batch must be a nonnegative integer")
        if isinstance(target_temperature_index, bool) or not isinstance(
            target_temperature_index, (int, np.integer)
        ):
            raise TypeError("target_temperature_index must be an integer")
        self._draw_count = int(draw_count)
        self._target_temperature_index = int(target_temperature_index)
        if not 0 <= self._target_temperature_index < self._backends[0].temperature_count:
            raise ValueError("target_temperature_index is outside the beta ladder")
        self._sweeps_per_batch = int(sweeps_per_batch)

        first = self._backends[0]
        first_signatures = first.bias_signatures
        if len(set(first_signatures)) != 1:
            raise ValueError("temperature slots must share one bias signature")
        schema = (
            first.sample_count,
            first.temperature_count,
            first.pair_count,
            first.length,
            first.coarse_length,
            first.token_count,
            first.encoder.metadata(),
            first.route,
            first.rank,
            first.required_platform,
            first.platform,
        )
        betas = first.betas
        shared_signature = first_signatures[0]
        for backend in self._backends[1:]:
            signatures = backend.bias_signatures
            if len(set(signatures)) != 1:
                raise ValueError("temperature slots must share one bias signature")
            if signatures[0] != shared_signature:
                raise ValueError("all J backends require one shared bias signature")
            candidate_schema = (
                backend.sample_count,
                backend.temperature_count,
                backend.pair_count,
                backend.length,
                backend.coarse_length,
                backend.token_count,
                backend.encoder.metadata(),
                backend.route,
                backend.rank,
                backend.required_platform,
                backend.platform,
            )
            if candidate_schema != schema:
                raise ValueError("JAX backends must share one raw sampling schema")
            if not np.array_equal(backend.betas, betas):
                raise ValueError("JAX backends must share one beta ladder")
        self._encoder = self._backends[0].encoder
        self._token_count = self._backends[0].token_count
        self._betas = betas.copy()
        self._target_beta = float(betas[self._target_temperature_index])
        self._bias_signature = shared_signature
        self._raw_schema = {
            "sample_count": first.sample_count,
            "temperature_count": first.temperature_count,
            "pair_count": first.pair_count,
            "length": first.length,
            "coarse_length": first.coarse_length,
            "token_count": first.token_count,
            "encoder": copy.deepcopy(first.encoder.metadata()),
            "route": first.route.value,
            "rank": first.rank,
            "required_platform": first.required_platform,
            "platform": first.platform,
        }
        self._context_signatures = tuple(
            backend.context_signature for backend in self._backends
        )
        self._rng = np.random.default_rng(seed)
        self._batches_emitted = 0
        self._draws_emitted = 0
        self._per_j_counters = {
            j_id: {name: 0 for name in _AUDIT_COUNTER_NAMES}
            for j_id in self.j_ids
        }

    @property
    def j_ids(self) -> tuple[str, ...]:
        return self._j_ids

    @property
    def draw_count(self) -> int:
        return self._draw_count

    @property
    def token_count(self) -> int:
        return self._token_count

    @property
    def encoder(self) -> TemplateEncoder:
        return self._encoder

    @property
    def target_temperature_index(self) -> int:
        return self._target_temperature_index

    @property
    def target_beta(self) -> float:
        return self._target_beta

    @property
    def bias_signature(self) -> str:
        return self._bias_signature

    def _assert_live_contract(self) -> None:
        for j_id, expected_context, backend in zip(
            self.j_ids,
            self._context_signatures,
            self._backends,
            strict=True,
        ):
            if backend.context_signature != expected_context:
                raise RuntimeError(
                    f"JAX VMCRG live contract context changed for {j_id}"
                )
            live_schema = {
                "sample_count": backend.sample_count,
                "temperature_count": backend.temperature_count,
                "pair_count": backend.pair_count,
                "length": backend.length,
                "coarse_length": backend.coarse_length,
                "token_count": backend.token_count,
                "encoder": backend.encoder.metadata(),
                "route": backend.route.value,
                "rank": backend.rank,
                "required_platform": backend.required_platform,
                "platform": backend.platform,
            }
            if live_schema != self._raw_schema:
                raise RuntimeError(
                    f"JAX VMCRG live contract schema changed for {j_id}"
                )
            if not np.array_equal(backend.betas, self._betas):
                raise RuntimeError(
                    f"JAX VMCRG live contract beta ladder changed for {j_id}"
                )
            signatures = backend.bias_signatures
            if (
                len(signatures) != backend.temperature_count
                or len(set(signatures)) != 1
                or signatures[0] != self.bias_signature
            ):
                raise RuntimeError(
                    f"JAX VMCRG live contract bias signature changed for {j_id}"
                )

    def next_batch(self) -> VMCRGBatch:
        self._assert_live_contract()
        before = self.checkpoint_state()
        try:
            for backend in self._backends:
                backend.run_sweeps(self._sweeps_per_batch)
            raw_pools = tuple(
                decode_token_codes(
                    backend.token_codes[
                        :, self._target_temperature_index, :
                    ].reshape(-1),
                    self.token_count,
                )
                for backend in self._backends
            )
            indices = tuple(
                self._rng.integers(0, pool.shape[0], size=self.draw_count)
                for pool in raw_pools
            )
            biased = select_equal_per_j_rows(raw_pools, indices)
            target = build_uniform_target_tokens(
                biased,
                self.encoder.q_token_indices,
                self._rng,
            )
            batch = VMCRGBatch(
                target_tokens=target,
                biased_tokens=biased,
                j_ids=self.j_ids,
            )
            for counters in self._per_j_counters.values():
                counters["adapter_sweep_count"] += self._sweeps_per_batch
                counters["retained_biased_draws"] += self.draw_count
                counters["generated_target_draws"] += self.draw_count
            self._batches_emitted += 1
            self._draws_emitted += len(self.j_ids) * self.draw_count
            return batch
        except Exception:
            try:
                self.restore_state(before)
            except Exception as rollback_error:
                raise RuntimeError("JAX VMCRG batch rollback failed") from rollback_error
            raise

    def refresh_bias(self, bias: OverlapBias) -> None:
        """Atomically install one newly trained shared bias on every J sampler."""

        if not isinstance(bias, OverlapBias):
            raise TypeError("refreshed VMCRG bias must be an OverlapBias")
        self._assert_live_contract()
        before = self.checkpoint_state()
        old_models = tuple(backend.bias_models for backend in self._backends)
        changed = 0
        try:
            prepared: np.ndarray | None = None
            for backend in self._backends:
                backend.refresh_biases(bias, _prepared_lookups=prepared)
                if prepared is None:
                    prepared = backend.lookup_tables
                changed += 1
            signatures = tuple(
                backend.bias_signatures[0] for backend in self._backends
            )
            if len(set(signatures)) != 1:
                raise RuntimeError("refreshed J samplers do not share one bias")
            self._bias_signature = signatures[0]
            self._assert_live_contract()
        except Exception:
            rollback_errors: list[BaseException] = []
            for index, backend in enumerate(self._backends):
                if index < changed:
                    try:
                        backend.refresh_biases(old_models[index])
                    except Exception as error:
                        rollback_errors.append(error)
            self._bias_signature = str(before["bias_signature"])
            for backend, entry in zip(
                self._backends,
                before["per_j_states"],
                strict=True,
            ):
                try:
                    backend.restore_checkpoint_state(entry["state"])
                except Exception as error:
                    rollback_errors.append(error)
            if rollback_errors:
                raise RuntimeError("JAX VMCRG bias refresh rollback failed") from rollback_errors[0]
            raise

    def checkpoint_state(self) -> dict[str, object]:
        self._assert_live_contract()
        per_j_states = tuple(
            {
                "j_id": j_id,
                "context_signature": context_signature,
                "adapter_counters": self._per_j_counters[j_id].copy(),
                "state": backend.checkpoint_state(),
            }
            for j_id, context_signature, backend in zip(
                self.j_ids,
                self._context_signatures,
                self._backends,
                strict=True,
            )
        )
        return {
            "schema_version": 1,
            "j_ids": self.j_ids,
            "draw_count": self.draw_count,
            "token_count": self.token_count,
            "target_temperature_index": self.target_temperature_index,
            "target_beta": self.target_beta,
            "betas": self._betas.copy(),
            "sweeps_per_batch": self._sweeps_per_batch,
            "bias_signature": self.bias_signature,
            "raw_schema": copy.deepcopy(self._raw_schema),
            "context_signatures": tuple(
                zip(self.j_ids, self._context_signatures, strict=True)
            ),
            "batches_emitted": self._batches_emitted,
            "draws_emitted": self._draws_emitted,
            "rng_state": self._rng_payload(per_j_states),
            "per_j_states": per_j_states,
        }

    def restore_state(self, state: Mapping[str, object]) -> None:
        if not isinstance(state, Mapping):
            raise TypeError("adapter checkpoint state must be a Mapping")
        self._assert_live_contract()
        restored = copy.deepcopy(dict(state))
        current = self.checkpoint_state()
        expected = set(current)
        if set(restored) != expected or restored.get("schema_version") != 1:
            raise ValueError("adapter checkpoint inventory is incomplete")
        if tuple(restored["j_ids"]) != self.j_ids:
            raise ValueError("adapter checkpoint ordered J IDs do not match")
        if (
            restored["draw_count"] != self.draw_count
            or restored["token_count"] != self.token_count
            or restored["sweeps_per_batch"] != self._sweeps_per_batch
            or restored["raw_schema"] != self._raw_schema
        ):
            raise ValueError("adapter checkpoint sampling schema does not match")
        if (
            restored["target_temperature_index"] != self.target_temperature_index
            or restored["target_beta"] != self.target_beta
            or not np.array_equal(restored["betas"], self._betas)
        ):
            raise ValueError("adapter checkpoint target beta ladder does not match")
        if restored["bias_signature"] != self.bias_signature:
            raise ValueError("adapter checkpoint shared bias signature mismatch")
        expected_contexts = tuple(
            zip(self.j_ids, self._context_signatures, strict=True)
        )
        if restored["context_signatures"] != expected_contexts:
            raise ValueError("adapter checkpoint ordered J context does not match")

        per_j_states = tuple(restored["per_j_states"])
        if len(per_j_states) != len(self.j_ids):
            raise ValueError("adapter checkpoint J state inventory is incomplete")
        candidate_per_j_counters = {}
        for expected_j_id, expected_context, entry in zip(
            self.j_ids,
            self._context_signatures,
            per_j_states,
            strict=True,
        ):
            if not isinstance(entry, Mapping) or entry.get("j_id") != expected_j_id:
                raise ValueError("adapter checkpoint J state order does not match")
            if entry.get("context_signature") != expected_context:
                raise ValueError("adapter checkpoint per-J context does not match")
            audit = entry.get("adapter_counters")
            if not isinstance(audit, Mapping) or set(audit) != _AUDIT_COUNTER_KEYS:
                raise ValueError("adapter checkpoint per-J audit inventory is incomplete")
            if any(
                isinstance(audit[name], (bool, np.bool_))
                or not isinstance(audit[name], (int, np.integer))
                or int(audit[name]) < 0
                for name in _AUDIT_COUNTER_NAMES
            ):
                raise ValueError("adapter checkpoint per-J audit counters are invalid")
            candidate_per_j_counters[expected_j_id] = {
                name: int(audit[name]) for name in _AUDIT_COUNTER_NAMES
            }

        rng_payload = restored["rng_state"]
        if not isinstance(rng_payload, Mapping):
            raise TypeError("adapter checkpoint rng_state must be a Mapping")
        expected_rng = self._rng_payload(per_j_states)
        if set(rng_payload) != set(expected_rng):
            raise ValueError("adapter checkpoint RNG inventory is incomplete")
        raw_rng = tuple(rng_payload["per_j"])
        if len(raw_rng) != len(per_j_states):
            raise ValueError("adapter checkpoint per-J RNG inventory is incomplete")
        for expected_j_id, rng_entry, state_entry in zip(
            self.j_ids,
            raw_rng,
            per_j_states,
            strict=True,
        ):
            if not isinstance(rng_entry, Mapping) or rng_entry.get("j_id") != expected_j_id:
                raise ValueError("adapter checkpoint per-J RNG order does not match")
            if rng_entry.get("context_signature") != state_entry["context_signature"]:
                raise ValueError("adapter checkpoint RNG context is inconsistent")
            raw_state = state_entry["state"]
            for key in ("local_key", "swap_key", "global_key"):
                if not np.array_equal(rng_entry.get(key), raw_state[key]):
                    raise ValueError("adapter checkpoint raw RNG evidence is inconsistent")
        candidate_rng = np.random.default_rng()
        candidate_rng.bit_generator.state = copy.deepcopy(rng_payload["adapter_rng"])

        counters = (restored["batches_emitted"], restored["draws_emitted"])
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, np.integer))
            or int(value) < 0
            for value in counters
        ):
            raise ValueError("adapter checkpoint counters are invalid")
        batches_emitted = int(counters[0])
        draws_emitted = int(counters[1])
        expected_per_j = {
            "adapter_sweep_count": batches_emitted * self._sweeps_per_batch,
            "retained_biased_draws": batches_emitted * self.draw_count,
            "generated_target_draws": batches_emitted * self.draw_count,
        }
        if (
            draws_emitted != batches_emitted * len(self.j_ids) * self.draw_count
            or any(
                audit != expected_per_j
                for audit in candidate_per_j_counters.values()
            )
        ):
            raise ValueError("adapter checkpoint audit counters are inconsistent")
        for backend, entry in zip(self._backends, per_j_states, strict=True):
            backend.validate_checkpoint_state(entry["state"])

        try:
            for backend, entry in zip(self._backends, per_j_states, strict=True):
                backend.restore_checkpoint_state(entry["state"])
            self._rng = candidate_rng
            self._batches_emitted = batches_emitted
            self._draws_emitted = draws_emitted
            self._per_j_counters = copy.deepcopy(candidate_per_j_counters)
        except Exception:
            try:
                for backend, entry in zip(
                    self._backends,
                    current["per_j_states"],
                    strict=True,
                ):
                    backend.restore_checkpoint_state(entry["state"])
            except Exception as rollback_error:
                raise RuntimeError("JAX VMCRG restore rollback failed") from rollback_error
            raise

    def training_rng_state(self) -> dict[str, object]:
        self._assert_live_contract()
        per_j_states = tuple(
            {
                "j_id": j_id,
                "context_signature": context_signature,
                "state": backend.checkpoint_state(),
            }
            for j_id, context_signature, backend in zip(
                self.j_ids,
                self._context_signatures,
                self._backends,
                strict=True,
            )
        )
        return self._rng_payload(per_j_states)

    def resource_snapshot(self) -> dict[str, object]:
        self._assert_live_contract()
        per_j = {}
        for j_id, context_signature, backend in zip(
            self.j_ids,
            self._context_signatures,
            self._backends,
            strict=True,
        ):
            record = backend.resource_snapshot()
            record["context_signature"] = context_signature
            record.update(self._per_j_counters[j_id])
            per_j[j_id] = record
        records = tuple(per_j.values())
        aggregate_adapter_sweeps = sum(
            int(record["adapter_sweep_count"]) for record in records
        )
        aggregate_retained = sum(
            int(record["retained_biased_draws"]) for record in records
        )
        aggregate_generated = sum(
            int(record["generated_target_draws"]) for record in records
        )
        raw_lifetime_proposals = sum(
            backend.proposed_changes for backend in self._backends
        )
        raw_lifetime_accepted = sum(
            backend.accepted_changes for backend in self._backends
        )
        return {
            "backend": "jax-vmcrg-sampling-adapter",
            "backend_provenance": "JaxBiasedPairBackend",
            "j_count": len(self.j_ids),
            "draw_count": self.draw_count,
            "batches_emitted": self._batches_emitted,
            "draws_emitted": self._draws_emitted,
            "sweeps_per_batch": self._sweeps_per_batch,
            "aggregate_sweeps": aggregate_adapter_sweeps,
            "aggregate_retained_biased_draws": aggregate_retained,
            "aggregate_generated_target_draws": aggregate_generated,
            "aggregate_raw_lifetime_sweeps": sum(
                backend.sweep_count for backend in self._backends
            ),
            "aggregate_raw_lifetime_proposals": raw_lifetime_proposals,
            "aggregate_raw_lifetime_accepted": raw_lifetime_accepted,
            "aggregate_proposals": raw_lifetime_proposals,
            "aggregate_accepted": raw_lifetime_accepted,
            "target_temperature_index": self.target_temperature_index,
            "target_beta": self.target_beta,
            "bias_signature": self.bias_signature,
            "context_signatures": dict(
                zip(self.j_ids, self._context_signatures, strict=True)
            ),
            "host_peak_bytes": max(int(record["host_rss_bytes"]) for record in records),
            "device_peak_bytes": max(
                int(record["device_memory_bytes"]) for record in records
            ),
            "compile_seconds": sum(
                float(record["compile_seconds"]) for record in records
            ),
            "lookup_build_seconds": sum(
                float(record["lookup_build_seconds"]) for record in records
            ),
            "per_j": per_j,
        }

    def _rng_payload(
        self,
        per_j_states: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        return {
            "adapter_rng": copy.deepcopy(self._rng.bit_generator.state),
            "per_j": tuple(
                {
                    "j_id": entry["j_id"],
                    "context_signature": entry["context_signature"],
                    "local_key": np.asarray(entry["state"]["local_key"]).copy(),
                    "swap_key": np.asarray(entry["state"]["swap_key"]).copy(),
                    "global_key": np.asarray(entry["state"]["global_key"]).copy(),
                }
                for entry in per_j_states
            ),
        }
