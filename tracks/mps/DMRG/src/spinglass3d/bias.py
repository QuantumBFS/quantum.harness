"""Route composition and incremental local overlap-bias cache."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from .linear_bias import LinearFeatureBasis
from .model import EABonds
from .symmetry import cubic_transforms
from .templates import TemplateEncoder, TemplateKind
from .tensor_train import SymmetricLocalTT


class BiasRoute(str, Enum):
    A_Q_ONLY = "A"
    B_CONDITIONED_TT = "B"
    C_LINEAR_PLUS_TT = "C"


@dataclass(frozen=True)
class ResidualProjection:
    coefficients: np.ndarray
    residual_norm: float
    rank: int

    def __post_init__(self) -> None:
        values = np.asarray(self.coefficients, dtype=np.float64).copy()
        values.setflags(write=False)
        object.__setattr__(self, "coefficients", values)


def _token_code(tokens: np.ndarray) -> int:
    code = 0
    for index, token in enumerate(np.asarray(tokens)):
        if token == 1:
            code |= 1 << index
    return code


def _tokens_from_code(code: int, count: int) -> np.ndarray:
    bits = ((code >> np.arange(count, dtype=np.int64)) & 1).astype(np.int8)
    return 2 * bits - 1


def _all_tt_values(
    tt: SymmetricLocalTT,
    *,
    batch_size: int = 32768,
) -> np.ndarray:
    """Evaluate the raw TT on every binary code with bounded temporary memory."""

    token_count = tt.encoder.token_count
    state_count = 1 << token_count
    powers = np.arange(token_count, dtype=np.uint32)
    result = np.empty(state_count, dtype=np.float64)
    for start in range(0, state_count, batch_size):
        stop = min(state_count, start + batch_size)
        codes = np.arange(start, stop, dtype=np.uint32)
        bits = np.bitwise_and(
            np.right_shift(codes[:, None], powers[None, :]),
            np.uint32(1),
        )
        state = np.ones((codes.size, 1), dtype=np.float64)
        for position, core in enumerate(tt.model.cores):
            matrices = np.moveaxis(core[:, bits[:, position], :], 1, 0)
            state = np.einsum("bi,bij->bj", state, matrices, optimize=True)
        result[start:stop] = state[:, 0]
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("exhaustive TT values are non-finite")
    return result


def _permutation_for_transform(
    encoder: TemplateEncoder,
    transform: object,
) -> np.ndarray:
    """Recover a signed-token permutation for a plaquette-flux template."""

    count = encoder.token_count
    baseline = -np.ones(count, dtype=np.int8)
    transformed_baseline = encoder.transform_tokens(baseline, transform)
    if not np.array_equal(transformed_baseline, baseline):
        raise ValueError("template transform is not a binary token permutation")
    output_to_input = np.full(count, -1, dtype=np.int64)
    for input_position in range(count):
        probe = baseline.copy()
        probe[input_position] = 1
        transformed = encoder.transform_tokens(probe, transform)
        changed = np.flatnonzero(transformed != transformed_baseline)
        if changed.size != 1 or transformed[changed[0]] != 1:
            raise ValueError("template transform contains a nonlinear token map")
        output_to_input[int(changed[0])] = input_position
    if set(int(value) for value in output_to_input) != set(range(count)):
        raise ValueError("template transform token permutation is incomplete")
    return output_to_input


def _large_symmetric_lookup(tt: SymmetricLocalTT) -> np.ndarray:
    """Build exact O_h x Z2 values for a 19-token cross without Python rows."""

    encoder = tt.encoder
    if encoder.kind is not TemplateKind.CROSS or encoder.token_count != 19:
        raise ValueError("large exact lookup is implemented only for conditioned cross")
    count = encoder.token_count
    state_count = 1 << count
    codes = np.arange(state_count, dtype=np.uint32)
    bit_positions = np.arange(count, dtype=np.uint32)
    bits = np.bitwise_and(
        np.right_shift(codes[:, None], bit_positions[None, :]),
        np.uint32(1),
    )
    powers = np.left_shift(np.uint32(1), bit_positions)
    raw = _all_tt_values(tt)
    symmetric = np.zeros(state_count, dtype=np.float64)
    q_mask = np.sum(
        powers[np.asarray(encoder.q_token_indices, dtype=np.int64)],
        dtype=np.uint32,
    )
    transforms = cubic_transforms()
    for transform in transforms:
        permutation = _permutation_for_transform(encoder, transform)
        transformed_codes = np.sum(
            bits[:, permutation] * powers[None, :],
            axis=1,
            dtype=np.uint32,
        )
        symmetric += raw[transformed_codes]
        symmetric += raw[np.bitwise_xor(transformed_codes, q_mask)]
    symmetric /= float(2 * len(transforms))

    q_positions = set(encoder.q_token_indices)
    disorder_positions = tuple(
        index for index in range(count) if index not in q_positions
    )
    disorder_key = np.zeros(state_count, dtype=np.uint16)
    for output_position, token_position in enumerate(disorder_positions):
        disorder_key |= (
            bits[:, token_position].astype(np.uint16)
            << np.uint16(output_position)
        )
    group_count = 1 << len(disorder_positions)
    counts = np.bincount(disorder_key, minlength=group_count)
    sums = np.bincount(disorder_key, weights=symmetric, minlength=group_count)
    if np.any(counts == 0):
        raise AssertionError("cross disorder lookup groups are incomplete")
    lookup = symmetric - (sums / counts)[disorder_key]
    if not np.all(np.isfinite(lookup)):
        raise FloatingPointError("cross lookup contains non-finite values")
    lookup.setflags(write=False)
    return lookup


class OverlapBias:
    def __init__(
        self,
        route: BiasRoute | str,
        basis: LinearFeatureBasis | None,
        coefficients: np.ndarray,
        tt: SymmetricLocalTT,
    ) -> None:
        self.route = BiasRoute(route)
        if not isinstance(tt, SymmetricLocalTT):
            raise TypeError("tt must be a SymmetricLocalTT")
        self.tt = tt
        values = np.asarray(coefficients, dtype=np.float64)
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError("coefficients must be a finite vector")
        if self.route is BiasRoute.C_LINEAR_PLUS_TT:
            if not isinstance(basis, LinearFeatureBasis) or not basis.is_primary_comparator:
                raise ValueError("Route C requires the primary finite basis")
            if values.shape != (len(basis.features),):
                raise ValueError("Route C coefficient count does not match basis")
            if not tt.encoder.conditioned:
                raise ValueError("Route C requires conditioned TT tokens")
        else:
            if basis is not None or values.size:
                raise ValueError("Routes A/B contain no linear branch")
            if self.route is BiasRoute.A_Q_ONLY and tt.encoder.conditioned:
                raise ValueError("Route A must not contain disorder tokens")
            if self.route is BiasRoute.B_CONDITIONED_TT and not tt.encoder.conditioned:
                raise ValueError("Route B requires conditioned TT tokens")
        self.basis = basis
        self.coefficients = values.copy()

    def local_value(self, tokens: np.ndarray) -> float:
        value = self.tt.centered_value(tokens)
        if self.route is BiasRoute.C_LINEAR_PLUS_TT:
            assert self.basis is not None
            value += float(
                self.coefficients @ self.basis.local_features(tokens, self.tt.encoder)
            )
        if not math.isfinite(value):
            raise FloatingPointError("local bias value is not finite")
        return value

    def value(
        self,
        q: np.ndarray,
        bonds: EABonds,
        encoder: TemplateEncoder,
    ) -> float:
        if encoder.kind is not self.tt.encoder.kind or encoder.conditioned != self.tt.encoder.conditioned:
            raise ValueError("encoder does not match bias TT")
        return float(
            sum(
                self.local_value(encoder.encode(q, bonds, center))
                for center in np.ndindex(np.asarray(q).shape)
            )
        )

    def build_lookup(self, encoder: TemplateEncoder) -> np.ndarray:
        if encoder.token_count > 19:
            raise ValueError("exact frozen lookup is restricted to at most 19 tokens")
        if encoder.token_count > 13:
            if self.route is BiasRoute.C_LINEAR_PLUS_TT:
                raise ValueError("the conditioned linear comparator is cube-specific")
            return _large_symmetric_lookup(self.tt)
        state_count = 1 << encoder.token_count
        lookup = np.full(state_count, np.nan, dtype=np.float64)
        raw_tt = np.full(state_count, np.nan, dtype=np.float64)
        linear = np.zeros(state_count, dtype=np.float64)
        for code in range(state_count):
            if np.isfinite(raw_tt[code]):
                continue
            tokens = _tokens_from_code(code, encoder.token_count)
            orbit_codes: set[int] = set()
            for image in encoder.symmetry_images(tokens):
                orbit_codes.add(_token_code(image))
                orbit_codes.add(_token_code(encoder.flip_q_tokens(image)))
            tt_value = self.tt.value(tokens)
            if self.route is BiasRoute.C_LINEAR_PLUS_TT:
                assert self.basis is not None
                feature_value = float(
                    self.coefficients @ self.basis.local_features(tokens, encoder)
                )
            else:
                feature_value = 0.0
            for member in orbit_codes:
                raw_tt[member] = tt_value
                linear[member] = feature_value
        if not np.all(np.isfinite(raw_tt)):
            raise AssertionError("symmetry orbits did not cover the lookup")

        q_positions = set(encoder.q_token_indices)
        disorder_positions = [
            index for index in range(encoder.token_count) if index not in q_positions
        ]
        groups: dict[int, list[int]] = {}
        for code in range(state_count):
            tokens = _tokens_from_code(code, encoder.token_count)
            key = _token_code(tokens[disorder_positions]) if disorder_positions else 0
            groups.setdefault(key, []).append(code)
        for members in groups.values():
            mean = float(np.mean(raw_tt[members], dtype=np.float64))
            lookup[members] = raw_tt[members] - mean + linear[members]
        if not np.all(np.isfinite(lookup)):
            raise FloatingPointError("lookup contains nonfinite values")
        lookup.setflags(write=False)
        return lookup

    def residual_projection(self, tokens: np.ndarray) -> ResidualProjection:
        if self.route is not BiasRoute.C_LINEAR_PLUS_TT or self.basis is None:
            raise ValueError("residual projection is defined only for Route C")
        batch = np.asarray(tokens)
        if batch.ndim != 2 or batch.shape[1] != self.tt.encoder.token_count:
            raise ValueError("projection tokens have the wrong shape")
        matrix = np.asarray(
            [self.basis.local_features(row, self.tt.encoder) for row in batch],
            dtype=np.float64,
        )
        residual = np.asarray(
            [self.tt.centered_value(row) for row in batch],
            dtype=np.float64,
        )
        coefficients, _, rank, _ = np.linalg.lstsq(matrix, residual, rcond=None)
        remainder = residual - matrix @ coefficients
        return ResidualProjection(
            coefficients=coefficients,
            residual_norm=float(np.linalg.norm(remainder)),
            rank=int(rank),
        )


@dataclass(frozen=True)
class BiasProposal:
    site: tuple[int, int, int]
    old_q: int
    new_q: int
    generation: int
    centers: tuple[tuple[int, int, int], ...]
    old_tokens: tuple[np.ndarray, ...]
    new_tokens: tuple[np.ndarray, ...]
    old_values: tuple[float, ...]
    new_values: tuple[float, ...]
    delta: float


class LocalBiasCache:
    def __init__(
        self,
        q: np.ndarray,
        bonds: EABonds,
        encoder: TemplateEncoder,
        bias: OverlapBias,
    ) -> None:
        field = np.asarray(q)
        if field.ndim != 3 or field.shape[0] != field.shape[1] or field.shape[1] != field.shape[2]:
            raise ValueError("q must be cubic")
        if not np.all((field == -1) | (field == 1)):
            raise ValueError("q must contain only -1 and +1")
        if encoder.kind is not bias.tt.encoder.kind or encoder.conditioned != bias.tt.encoder.conditioned:
            raise ValueError("encoder and bias must match")
        self._q = field.astype(np.int8, copy=True)
        self.bonds = bonds
        self.encoder = encoder
        self.bias = bias
        self._reverse = encoder.reverse_q_incidence(field.shape[0])
        self._generation = 0
        self._lookup: np.ndarray | None = None
        self.rebuild_lookup()
        self._tokens: dict[tuple[int, int, int], np.ndarray] = {}
        self._values: dict[tuple[int, int, int], float] = {}
        for center in np.ndindex(field.shape):
            tokens = encoder.encode(self._q, bonds, center)
            self._tokens[center] = tokens
            self._values[center] = self._local_value(tokens)
        self._total = float(sum(self._values.values()))

    @property
    def lookup_size(self) -> int:
        return 0 if self._lookup is None else int(self._lookup.size)

    @property
    def lookup_complete(self) -> bool:
        return self._lookup is not None and bool(np.all(np.isfinite(self._lookup)))

    @property
    def total_value(self) -> float:
        return self._total

    def rebuild_lookup(self) -> None:
        if self.encoder.kind is TemplateKind.CUBE and self.encoder.token_count <= 13:
            lookup = self.bias.build_lookup(self.encoder)
        else:
            lookup = None
        if hasattr(self, "_tokens"):
            values = {
                center: (
                    float(lookup[_token_code(tokens)])
                    if lookup is not None
                    else self.bias.local_value(tokens)
                )
                for center, tokens in self._tokens.items()
            }
            total = float(sum(values.values()))
            self._values = values
            self._total = total
        self._lookup = lookup
        self._generation += 1

    def _local_value(self, tokens: np.ndarray) -> float:
        if self._lookup is not None:
            return float(self._lookup[_token_code(tokens)])
        return self.bias.local_value(tokens)

    def _flipped_tokens(
        self,
        center: tuple[int, int, int],
        site: tuple[int, int, int],
    ) -> np.ndarray:
        tokens = self._tokens[center].copy()
        length = self._q.shape[0]
        for q_index, offset in enumerate(self.encoder.offsets):
            represented = tuple(
                (center[axis] + offset[axis]) % length for axis in range(3)
            )
            if represented == site:
                tokens[self.encoder.q_token_indices[q_index]] *= -1
        return tokens

    def proposal(self, site: tuple[int, int, int]) -> BiasProposal:
        selected = tuple(int(value) for value in site)
        if len(selected) != 3 or any(
            value < 0 or value >= self._q.shape[0] for value in selected
        ):
            raise ValueError("site lies outside q")
        centers = tuple(sorted(set(self._reverse[selected])))
        old_tokens = tuple(self._tokens[center].copy() for center in centers)
        new_tokens = tuple(self._flipped_tokens(center, selected) for center in centers)
        old_values = tuple(self._values[center] for center in centers)
        new_values = tuple(self._local_value(tokens) for tokens in new_tokens)
        delta = float(sum(new_values) - sum(old_values))
        return BiasProposal(
            site=selected,
            old_q=int(self._q[selected]),
            new_q=-int(self._q[selected]),
            generation=self._generation,
            centers=centers,
            old_tokens=old_tokens,
            new_tokens=new_tokens,
            old_values=old_values,
            new_values=new_values,
            delta=delta,
        )

    def commit(self, proposal: BiasProposal) -> None:
        if proposal.generation != self._generation or int(self._q[proposal.site]) != proposal.old_q:
            raise RuntimeError("stale bias proposal")
        for center, tokens, value in zip(
            proposal.centers,
            proposal.old_tokens,
            proposal.old_values,
            strict=True,
        ):
            if not np.array_equal(self._tokens[center], tokens) or self._values[center] != value:
                raise RuntimeError("stale bias proposal")
        self._q[proposal.site] = proposal.new_q
        for center, tokens, value in zip(
            proposal.centers,
            proposal.new_tokens,
            proposal.new_values,
            strict=True,
        ):
            self._tokens[center] = tokens.copy()
            self._values[center] = value
        self._total += proposal.delta

    def full_delta(self, site: tuple[int, int, int]) -> float:
        changed = self._q.copy()
        changed[site] *= -1
        total = 0.0
        for center in np.ndindex(changed.shape):
            total += self._local_value(self.encoder.encode(changed, self.bonds, center))
        return float(total - self._total)

    def assert_consistent(self) -> None:
        total = 0.0
        for center in np.ndindex(self._q.shape):
            tokens = self.encoder.encode(self._q, self.bonds, center)
            value = self._local_value(tokens)
            np.testing.assert_array_equal(self._tokens[center], tokens)
            np.testing.assert_allclose(self._values[center], value, atol=1e-12, rtol=0.0)
            total += value
        np.testing.assert_allclose(self._total, total, atol=1e-10, rtol=0.0)
