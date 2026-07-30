from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import sqrt
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np
from flax import linen as nn
from flax.core import FrozenDict, freeze, unfreeze

from challenge15.carriers import batched_carrier_amplitudes, carrier_amplitudes
from challenge15.projector import ProjectionGrid, project_m0, project_multiplet
from challenge15.spec import SphereSpec


class BatchedLogAmplitude(NamedTuple):
    log_amplitude: jax.Array
    finite_nonzero: jax.Array


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Shape-static configuration for the shared carrier hypernetwork."""

    rank: int = 2
    hidden_width: int = 32
    depth: int = 2
    token_width: int = 8
    fourier_order: int = 4
    block_size: int = 64

    def __post_init__(self) -> None:
        _positive_integer("rank", self.rank)
        _positive_integer("hidden_width", self.hidden_width)
        if not isinstance(self.depth, int) or isinstance(self.depth, bool) or self.depth < 0:
            raise ValueError("depth must be a nonnegative Python integer")
        _positive_integer("token_width", self.token_width)
        _positive_integer("fourier_order", self.fourier_order)
        _positive_integer("block_size", self.block_size)


class ProjectedPfaffianNQS(nn.Module):
    """One sector-conditioned parameter tree projected into exact SU(2) irreps."""

    config: ModelConfig

    def setup(self) -> None:
        token_initializer = nn.initializers.normal(stddev=0.2)
        gate_initializer = nn.initializers.normal(stddev=0.2)
        self.carrier_tokens = self.param(
            "carrier_tokens",
            token_initializer,
            (self.config.rank, self.config.token_width),
            jnp.float64,
        )
        self.carrier_gates = self.param(
            "carrier_gates",
            gate_initializer,
            (self.config.rank, 2),
            jnp.float64,
        )
        self.input_layer = nn.Dense(
            self.config.hidden_width,
            dtype=jnp.float64,
            param_dtype=jnp.float64,
            name="shared_input",
        )
        self.residual_layers = tuple(
            nn.Dense(
                self.config.hidden_width,
                dtype=jnp.float64,
                param_dtype=jnp.float64,
                name=f"shared_residual_{index}",
            )
            for index in range(self.config.depth)
        )
        self.reduced_output = nn.Dense(
            2,
            dtype=jnp.float64,
            param_dtype=jnp.float64,
            name="shared_reduced_output",
        )

    def __call__(
        self,
        spec: SphereSpec,
        spinors,
        target_l: int,
        *,
        grid: ProjectionGrid | None = None,
    ) -> jax.Array:
        """Evaluate the M=0 member of the requested L=0 or L=2 sector."""

        _validate_sector(spec, target_l)
        weights, borders = self._reduced_carriers(spec, target_l)
        gates = _as_complex(self.carrier_gates)
        terms = []
        for carrier_index in range(self.config.rank):
            amplitude = _carrier_callable(
                spec, weights[carrier_index], borders[carrier_index]
            )
            projected = project_m0(
                amplitude,
                spinors,
                spec,
                target_l,
                grid=grid,
                block_size=self.config.block_size,
            )
            terms.append(gated_carrier(gates[carrier_index], projected))
        return scaled_complex_sum(jnp.stack(terms))

    def multiplet(
        self,
        spec: SphereSpec,
        spinors,
        target_l: int,
        *,
        grid: ProjectionGrid | None = None,
    ) -> dict[int, jax.Array]:
        """Evaluate all M components using fixed projector kernels only."""

        _validate_sector(spec, target_l)
        weights, borders = self._reduced_carriers(spec, target_l)
        gates = _as_complex(self.carrier_gates)
        terms = {
            m: []
            for m in range(-target_l, target_l + 1)
        }
        for carrier_index in range(self.config.rank):
            amplitude = _carrier_callable(
                spec, weights[carrier_index], borders[carrier_index]
            )
            projected = project_multiplet(
                amplitude,
                spinors,
                spec,
                target_l,
                grid=grid,
                block_size=self.config.block_size,
            )
            for m in terms:
                terms[m].append(gated_carrier(
                    gates[carrier_index], projected[m]
                ))
        return {
            m: scaled_complex_sum(jnp.stack(values))
            for m, values in terms.items()
        }

    def apply_multiplet(
        self,
        variables,
        spec: SphereSpec,
        spinors,
        target_l: int,
        *,
        grid: ProjectionGrid | None = None,
    ) -> dict[int, jax.Array]:
        """Convenience wrapper around ``Module.apply(..., method=multiplet)``."""

        return self.apply(
            variables,
            spec,
            spinors,
            target_l,
            grid=grid,
            method=self.multiplet,
        )

    def batched(
        self,
        spec: SphereSpec,
        spinors,
        sectors,
        valid_walkers,
        carrier_block: int,
        quadrature_block: int,
    ) -> BatchedLogAmplitude:
        """Evaluate both production sectors with static blocked kernels."""

        walkers = jnp.asarray(spinors, dtype=jnp.complex128)
        valid = jnp.asarray(valid_walkers, dtype=jnp.bool_)
        checked_sectors = jax.pure_callback(
            _checked_sector_values,
            jax.ShapeDtypeStruct((2,), jnp.int32),
            sectors,
        )
        safe_walkers = jnp.where(
            valid[:, None, None], walkers, jnp.zeros_like(walkers)
        )
        gates = _as_complex(self.carrier_gates)
        canonical_amplitudes = []
        for target_l in (0, 2):
            weights, borders = self._reduced_carriers(spec, target_l)
            canonical_amplitudes.append(
                _blocked_sector_amplitudes(
                    safe_walkers,
                    spec,
                    weights,
                    borders,
                    gates,
                    target_l=target_l,
                    carrier_block=carrier_block,
                    quadrature_block=quadrature_block,
                )
            )
        amplitudes = jnp.stack(canonical_amplitudes, axis=-1)
        requested = jnp.take(
            amplitudes, checked_sectors // 2, axis=1
        )
        finite_nonzero = (
            valid[:, None]
            & jnp.isfinite(requested.real)
            & jnp.isfinite(requested.imag)
            & (requested != 0)
        )
        safe_requested = jnp.where(
            finite_nonzero, requested, jnp.ones_like(requested)
        )
        safe_magnitude = jnp.abs(safe_requested)
        log_magnitude = jnp.where(
            finite_nonzero, jnp.log(safe_magnitude), -jnp.inf
        )
        phase = jnp.where(
            finite_nonzero, _canonical_principal_phase(safe_requested), 0.0
        )
        return BatchedLogAmplitude(
            log_amplitude=jnp.asarray(
                log_magnitude + 1j * phase, dtype=jnp.complex128
            ),
            finite_nonzero=finite_nonzero,
        )

    def apply_batched(
        self,
        variables,
        spec: SphereSpec,
        spinors,
        sectors,
        valid_walkers,
        carrier_block: int,
        quadrature_block: int,
    ) -> BatchedLogAmplitude:
        spinors_array = jnp.asarray(spinors)
        sectors_array = jnp.asarray(sectors)
        valid_array = jnp.asarray(valid_walkers)
        if (
            spinors_array.ndim != 3
            or spinors_array.shape[1:] != (spec.particles, 2)
        ):
            raise ValueError("spinors must have shape (walkers, spec.particles, 2)")
        if sectors_array.shape != (2,) or sectors_array.dtype != jnp.int32:
            raise ValueError("sectors must have shape (2,) and dtype int32")
        if not isinstance(sectors_array, jax.core.Tracer):
            sector_values = tuple(int(value) for value in np.asarray(sectors_array))
            if set(sector_values) != {0, 2}:
                raise ValueError("sectors must contain L=0 and L=2 exactly once")
        if (
            valid_array.shape != (spinors_array.shape[0],)
            or valid_array.dtype != jnp.bool_
        ):
            raise ValueError("valid_walkers must be bool with shape (walkers,)")
        _positive_integer("carrier_block", carrier_block)
        _positive_integer("quadrature_block", quadrature_block)
        return self.apply(
            variables,
            spec,
            spinors_array,
            sectors_array,
            valid_array,
            carrier_block,
            quadrature_block,
            method=self.batched,
        )

    def _reduced_carriers(
        self, spec: SphereSpec, target_l: int
    ) -> tuple[jax.Array, jax.Array]:
        positive_two_m = tuple(two_m for two_m in spec.two_m_values if two_m > 0)
        reduced_coordinates = jnp.asarray(
            (*positive_two_m, 0), dtype=jnp.float64
        ) / float(spec.two_q)
        fixed_features = _fixed_features(
            reduced_coordinates, target_l, self.config.fourier_order
        )
        row_count = fixed_features.shape[0]
        residual_scale = 1.0 / sqrt(max(self.config.depth, 1))
        components_by_carrier = []
        for carrier_index in range(self.config.rank):
            token_rows = jnp.broadcast_to(
                self.carrier_tokens[carrier_index],
                (row_count, self.config.token_width),
            )
            inputs = jnp.concatenate((fixed_features, token_rows), axis=-1)
            hidden = nn.tanh(self.input_layer(inputs))
            for layer in self.residual_layers:
                hidden = hidden + residual_scale * nn.tanh(layer(hidden))
            components_by_carrier.append(self.reduced_output(hidden))
        components = jnp.stack(components_by_carrier)
        complex_outputs = _as_complex(components)
        return complex_outputs[:, :-1], complex_outputs[:, -1]


def embed_rank(
    variables,
    old_rank: int,
    new_rank: int,
    *,
    key: jax.Array,
):
    """Grow a params subtree or complete variables tree without implicit RNG."""

    _positive_integer("old_rank", old_rank)
    _positive_integer("new_rank", new_rank)
    if new_rank <= old_rank:
        raise ValueError("new_rank must be greater than old_rank")
    mutable = unfreeze(variables)
    params = _params_subtree(mutable)
    try:
        old_tokens = jnp.asarray(params["carrier_tokens"])
        old_gates = jnp.asarray(params["carrier_gates"])
    except KeyError as error:
        raise ValueError("variables do not contain model carrier parameters") from error
    if old_tokens.ndim != 2 or old_tokens.shape[0] != old_rank:
        raise ValueError("old_rank does not match carrier_tokens")
    if old_gates.shape != (old_rank, 2):
        raise ValueError("old_rank does not match carrier_gates")

    growth = new_rank - old_rank
    new_tokens = 0.2 * jax.random.normal(
        key, (growth, old_tokens.shape[1]), dtype=old_tokens.dtype
    )
    new_gates = jnp.zeros((growth, 2), dtype=old_gates.dtype)
    params["carrier_tokens"] = jnp.concatenate(
        (old_tokens, new_tokens), axis=0
    )
    params["carrier_gates"] = jnp.concatenate(
        (old_gates, new_gates), axis=0
    )
    return freeze(mutable) if isinstance(variables, FrozenDict) else mutable


def embed_adam_state(
    state,
    expanded_params,
    *,
    old_rank: int,
    new_rank: int,
):
    """Embed Optax Adam moments for rank-grown params and preserve its count."""

    _positive_integer("old_rank", old_rank)
    _positive_integer("new_rank", new_rank)
    if new_rank <= old_rank:
        raise ValueError("new_rank must be greater than old_rank")
    target_params = _params_subtree(expanded_params)
    found_adam_state = False

    def embed_node(node):
        nonlocal found_adam_state
        if all(hasattr(node, field) for field in ("count", "mu", "nu")):
            found_adam_state = True
            return node._replace(
                mu=_embed_moments(
                    node.mu, target_params, old_rank=old_rank, new_rank=new_rank
                ),
                nu=_embed_moments(
                    node.nu, target_params, old_rank=old_rank, new_rank=new_rank
                ),
            )
        if isinstance(node, tuple) and hasattr(node, "_fields"):
            return type(node)(*(embed_node(value) for value in node))
        if isinstance(node, tuple):
            return tuple(embed_node(value) for value in node)
        if isinstance(node, list):
            return [embed_node(value) for value in node]
        return node

    embedded = embed_node(state)
    if not found_adam_state:
        raise ValueError("optimizer state does not contain Adam moments")
    return embedded


def scaled_complex_sum(terms: jax.Array) -> jax.Array:
    """Neumaier-sum complex terms after stop-gradient magnitude scaling."""

    values = jnp.asarray(terms, dtype=jnp.complex128)
    if values.ndim < 1 or values.shape[0] == 0:
        raise ValueError("scaled complex summation requires at least one term")
    all_finite = jnp.all(jnp.isfinite(values), axis=0)
    scale = jax.lax.stop_gradient(
        jnp.max(jnp.where(jnp.isfinite(values), jnp.abs(values), 0.0), axis=0)
    )
    safe_scale = jnp.where(scale > 0, scale, jnp.ones_like(scale))
    normalized = values / safe_scale

    def add(carry, value):
        total, compensation = carry
        updated = total + value
        correction = jnp.where(
            jnp.abs(total) >= jnp.abs(value),
            (total - updated) + value,
            (value - updated) + total,
        )
        return (updated, compensation + correction), None

    initial = (jnp.zeros_like(normalized[0]), jnp.zeros_like(normalized[0]))
    (total, compensation), _ = jax.lax.scan(add, initial, normalized)
    stable = jnp.where(scale > 0, (total + compensation) * scale, 0j)
    return jnp.where(all_finite, stable, jnp.sum(values, axis=0))


def _blocked_sector_amplitudes(
    walkers: jax.Array,
    spec: SphereSpec,
    weights: jax.Array,
    borders: jax.Array,
    gates: jax.Array,
    *,
    target_l: int,
    carrier_block: int,
    quadrature_block: int,
) -> jax.Array:
    rank = int(weights.shape[0])
    carrier_tree_size = 1 << (rank - 1).bit_length()
    carrier_level_count = carrier_tree_size.bit_length()
    walker_count = int(walkers.shape[0])
    carrier_levels = jnp.zeros(
        (carrier_level_count, walker_count), dtype=jnp.complex128
    )
    carrier_occupied = jnp.zeros((carrier_level_count,), dtype=jnp.bool_)
    padded_size = (
        (carrier_tree_size + carrier_block - 1) // carrier_block
    ) * carrier_block
    channel_count = int(weights.shape[1])
    padded_weights = jnp.zeros(
        (padded_size, channel_count), dtype=jnp.complex128
    ).at[:rank].set(weights)
    padded_borders = jnp.zeros((padded_size,), dtype=jnp.complex128).at[:rank].set(
        borders
    )
    padded_gates = jnp.zeros((padded_size,), dtype=jnp.complex128).at[:rank].set(
        gates
    )
    block_count = padded_size // carrier_block
    carrier_valid = (jnp.arange(padded_size) < rank).reshape(
        block_count, carrier_block
    )
    tree_valid = (jnp.arange(padded_size) < carrier_tree_size).reshape(
        block_count, carrier_block
    )

    def reduce_carrier_block(carry, block):
        levels, occupied = carry
        block_weights, block_borders, block_gates, block_valid, block_tree = block
        projected = _blocked_project_carriers(
            walkers,
            spec,
            block_weights,
            block_borders,
            target_l=target_l,
            quadrature_block=quadrature_block,
        )
        terms = gated_carrier(block_gates[None, :], projected)
        for local_index in range(carrier_block):
            value = jnp.where(
                block_valid[local_index],
                terms[:, local_index],
                jnp.zeros((walker_count,), dtype=jnp.complex128),
            )
            levels, occupied = _pairwise_insert(
                levels,
                occupied,
                value,
                block_tree[local_index],
            )
        return (levels, occupied), None

    (carrier_levels, _), _ = jax.lax.scan(
        jax.checkpoint(reduce_carrier_block),
        (carrier_levels, carrier_occupied),
        (
            padded_weights.reshape(block_count, carrier_block, channel_count),
            padded_borders.reshape(block_count, carrier_block),
            padded_gates.reshape(block_count, carrier_block),
            carrier_valid,
            tree_valid,
        ),
    )
    return carrier_levels[-1]


def _blocked_project_carriers(
    walkers: jax.Array,
    spec: SphereSpec,
    weights: jax.Array,
    borders: jax.Array,
    *,
    target_l: int,
    quadrature_block: int,
) -> jax.Array:
    grid = ProjectionGrid.exact(spec, target_l)
    blocks = grid.static_blocks(quadrature_block)
    tree_size = 1 << (grid.n_alpha * grid.n_beta - 1).bit_length()
    level_count = tree_size.bit_length()
    walker_count = int(walkers.shape[0])
    carrier_count = int(weights.shape[0])
    initial_levels = jnp.zeros(
        (level_count, walker_count, carrier_count), dtype=jnp.complex128
    )
    initial_occupied = jnp.zeros((level_count,), dtype=jnp.bool_)
    prefactor = (2 * target_l + 1) / (4.0 * np.pi)

    def reduce_block(carry, block):
        levels, occupied = carry
        alpha, beta_node, block_weights, node_valid, tree_valid = block
        half_alpha = alpha / 2.0
        beta = jnp.arccos(beta_node)
        cosine = jnp.cos(beta / 2.0)
        sine = jnp.sin(beta / 2.0)
        first_phase = jnp.exp(-1j * half_alpha)
        second_phase = jnp.exp(1j * half_alpha)
        rotations = jnp.stack(
            (
                jnp.stack(
                    (cosine * first_phase, sine * second_phase), axis=-1
                ),
                jnp.stack(
                    (-sine * first_phase, cosine * second_phase), axis=-1
                ),
            ),
            axis=-2,
        )
        rotated = jnp.einsum("qab,wib->qwia", rotations, walkers)
        amplitudes = jax.vmap(
            lambda node_walkers: batched_carrier_amplitudes(
                node_walkers,
                spec,
                weights,
                border_weight=borders,
            )
        )(rotated)
        polynomial = (
            jnp.ones_like(beta_node)
            if target_l == 0
            else 0.5 * (3.0 * beta_node**2 - 1.0)
        )
        kernel = prefactor * block_weights * polynomial
        contributions = jnp.where(
            node_valid[:, None, None],
            kernel[:, None, None] * amplitudes,
            jnp.zeros_like(amplitudes),
        )
        for index in range(quadrature_block):
            levels, occupied = _pairwise_insert(
                levels,
                occupied,
                contributions[index],
                tree_valid[index],
            )
        return (levels, occupied), None

    (levels, _), _ = jax.lax.scan(
        jax.checkpoint(reduce_block),
        (initial_levels, initial_occupied),
        (
            jnp.asarray(blocks.alpha_nodes, dtype=jnp.float64),
            jnp.asarray(blocks.beta_nodes, dtype=jnp.float64),
            jnp.asarray(blocks.weights, dtype=jnp.complex128),
            jnp.asarray(blocks.node_valid, dtype=jnp.bool_),
            jnp.asarray(blocks.tree_valid, dtype=jnp.bool_),
        ),
    )
    return levels[-1]


def _pairwise_insert(
    levels: jax.Array,
    occupied: jax.Array,
    value: jax.Array,
    active: jax.Array,
) -> tuple[jax.Array, jax.Array]:
    carry = value
    propagating = jnp.asarray(active, dtype=jnp.bool_)
    for level in range(levels.shape[0]):
        level_occupied = occupied[level]
        combine = propagating & level_occupied
        store = propagating & ~level_occupied
        prior = levels[level]
        levels = levels.at[level].set(
            jnp.where(
                store,
                carry,
                jnp.where(combine, jnp.zeros_like(prior), prior),
            )
        )
        occupied = occupied.at[level].set(
            jnp.where(propagating, ~level_occupied, level_occupied)
        )
        carry = jnp.where(combine, prior + carry, carry)
        propagating = combine
    return levels, occupied


@jax.custom_jvp
def gated_carrier(gate: jax.Array, carrier: jax.Array) -> jax.Array:
    """Multiply one carrier by its gate with explicit inactive semantics.

    Forward: an exactly zero complex gate returns exact finite zero even when
    the already-evaluated carrier is NaN or Inf. A nonzero gate uses the normal
    product, so active nonfinite carriers remain visible.

    Gradient: at a zero gate, a finite carrier is the gate derivative and the
    carrier derivative is zero, allowing newly added carriers to activate.
    A nonfinite inactive carrier has zero derivatives so it cannot contaminate
    the rest of the model. At nonzero gates, the ordinary product rule applies.
    """

    gate_array = jnp.asarray(gate)
    carrier_array = jnp.asarray(carrier)
    product = gate_array * carrier_array
    return jnp.where(gate_array == 0, jnp.zeros_like(product), product)


@gated_carrier.defjvp
def _gated_carrier_jvp(primals, tangents):
    gate, carrier = primals
    gate_tangent, carrier_tangent = tangents
    value = gated_carrier(gate, carrier)
    inactive = gate == 0
    safe_carrier = jnp.where(
        jnp.isfinite(carrier), carrier, jnp.zeros_like(carrier)
    )
    effective_carrier = jnp.where(inactive, safe_carrier, carrier)
    carrier_term = jnp.where(
        inactive, jnp.zeros_like(carrier_tangent), gate * carrier_tangent
    )
    tangent = gate_tangent * effective_carrier + carrier_term
    return value, tangent


def _embed_moments(moment_tree, target_params, *, old_rank: int, new_rank: int):
    if jax.tree.structure(moment_tree) != jax.tree.structure(target_params):
        raise ValueError("Adam moment tree does not match expanded parameters")
    mutable = unfreeze(moment_tree)
    for name in ("carrier_tokens", "carrier_gates"):
        old_value = jnp.asarray(mutable[name])
        target_value = jnp.asarray(target_params[name])
        if old_value.shape[0] != old_rank:
            raise ValueError(f"old_rank does not match Adam {name} moments")
        if target_value.shape[0] != new_rank or target_value.shape[1:] != old_value.shape[1:]:
            raise ValueError(f"expanded {name} shape does not match Adam moments")
        zeros = jnp.zeros(
            (new_rank - old_rank, *old_value.shape[1:]), dtype=old_value.dtype
        )
        mutable[name] = jnp.concatenate((old_value, zeros), axis=0)

    old_named = dict(_named_leaves(moment_tree))
    target_named = dict(_named_leaves(target_params))
    if old_named.keys() != target_named.keys():
        raise ValueError("Adam moment tree does not match expanded parameters")
    for path, old_leaf in old_named.items():
        if path in {"carrier_tokens", "carrier_gates"}:
            continue
        target_leaf = target_named[path]
        if old_leaf.shape != target_leaf.shape:
            raise ValueError("non-rank Adam moment shape changed during embedding")
    return freeze(mutable) if isinstance(moment_tree, FrozenDict) else mutable


def _named_leaves(tree, prefix=""):
    if isinstance(tree, Mapping):
        for name, value in tree.items():
            path = f"{prefix}/{name}" if prefix else str(name)
            yield from _named_leaves(value, path)
    else:
        yield prefix, jnp.asarray(tree)


def _params_subtree(tree):
    if "carrier_tokens" in tree and "carrier_gates" in tree:
        return tree
    try:
        return tree["params"]
    except (KeyError, TypeError) as error:
        raise ValueError("expected a params subtree or complete variables tree") from error


def _fixed_features(
    reduced_coordinates: jax.Array, target_l: int, fourier_order: int
) -> jax.Array:
    frequencies = jnp.arange(1, fourier_order + 1, dtype=jnp.float64)
    angles = 2.0 * jnp.pi * reduced_coordinates[:, None] * frequencies[None, :]
    sector = jnp.asarray(
        [float(target_l == 0), float(target_l == 2)], dtype=jnp.float64
    )
    sector_bank = jnp.broadcast_to(sector, (reduced_coordinates.shape[0], 2))
    return jnp.concatenate(
        (
            reduced_coordinates[:, None],
            jnp.sin(angles),
            jnp.cos(angles),
            sector_bank,
        ),
        axis=-1,
    )


def _carrier_callable(
    spec: SphereSpec, pair_weights: jax.Array, border_weight: jax.Array
):
    return lambda rotated: carrier_amplitudes(
        rotated, spec, pair_weights, border_weight=border_weight
    )


def _as_complex(components: jax.Array) -> jax.Array:
    array = jnp.asarray(components, dtype=jnp.float64)
    if array.shape[-1] != 2:
        raise ValueError("complex components must have a final axis of length two")
    return array[..., 0] + 1j * array[..., 1]


def _canonical_principal_phase(values: jax.Array) -> jax.Array:
    phase = jnp.angle(values)
    return jnp.where(phase == -jnp.pi, jnp.pi, phase)


def _checked_sector_values(sectors) -> np.ndarray:
    values = np.asarray(sectors)
    if (
        values.shape != (2,)
        or values.dtype != np.int32
        or set(values.tolist()) != {0, 2}
    ):
        raise ValueError("sectors must contain L=0 and L=2 exactly once")
    return values


def _validate_sector(spec: SphereSpec, target_l: int) -> None:
    if target_l not in (0, 2):
        raise ValueError("target_l must be one of the shared sectors L=0 or L=2")
    if target_l > spec.l_max:
        raise ValueError("target_l exceeds the finite many-body band")


def _positive_integer(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive Python integer")
