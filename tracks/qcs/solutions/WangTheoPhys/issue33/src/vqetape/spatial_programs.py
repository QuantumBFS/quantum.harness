"""Exact spatial-transfer VQE runtime programs."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil
from typing import NamedTuple

import jax
import jax.numpy as jnp
from jax import Array

from vqetape.explicit_vjp import (
    ExplicitContraction,
    build_explicit_contraction_vjp,
)
from vqetape.kernels import rx_matrix, rzz_schmidt_factors
from vqetape.spatial_plan import (
    SpatialColumnProgram,
    SpatialTransferProgram,
    plan_spatial_transfer,
)
from vqetape.spec import SpatialProgramConfig, TFIMVQESpec
from vqetape.symmetry import (
    Z2BoundarySector,
    compress_boundary,
    expand_boundary,
    z2_boundary_sector,
    z2_symmetry_applicability,
)
from vqetape.symmetry_programs import (
    Z2NativeExecutor,
    build_z2_native_contraction,
)
from vqetape.tfim_mpo import tfim_mpo_tensors

SpatialEnergyFunction = Callable[[Array], Array]
SpatialValueAndGradFunction = Callable[
    [Array],
    tuple[Array, Array],
]


class SpatialSiteParameters(NamedTuple):
    """The three depth-vectors needed by one physical site."""

    left_rzz: Array
    right_rzz: Array
    rx: Array


def _complex_dtype(spec: TFIMVQESpec):
    return (
        jnp.complex64
        if spec.dtype == "complex64"
        else jnp.complex128
    )


def _product_state_vector(spec: TFIMVQESpec) -> Array:
    dtype = _complex_dtype(spec)
    if spec.initial_state == "zero":
        return jnp.asarray([1, 0], dtype=dtype)
    amplitude = jnp.asarray(1 / jnp.sqrt(2), dtype=dtype)
    return jnp.asarray([amplitude, amplitude], dtype=dtype)


def _site_parameters(
    theta: Array,
    site: int,
    spec: TFIMVQESpec,
) -> SpatialSiteParameters:
    if tuple(theta.shape) != spec.parameter_shape:
        raise ValueError(
            f"theta shape must be {spec.parameter_shape}, "
            f"got {tuple(theta.shape)}"
        )
    if site < 0 or site >= spec.nqubits:
        raise ValueError("site lies outside the VQE chain")
    zeros = jnp.zeros((spec.depth,), dtype=theta.dtype)
    return SpatialSiteParameters(
        left_rzz=(
            theta[:, 0, site - 1] if site > 0 else zeros
        ),
        right_rzz=(
            theta[:, 0, site]
            if site < spec.nqubits - 1
            else zeros
        ),
        rx=theta[:, 1, site],
    )


def _validate_site_parameters(
    parameters: SpatialSiteParameters,
    spec: TFIMVQESpec,
) -> None:
    expected = (spec.depth,)
    for name, value in zip(
        SpatialSiteParameters._fields,
        parameters,
        strict=True,
    ):
        if tuple(value.shape) != expected:
            raise ValueError(
                f"{name} shape must be {expected}, "
                f"got {tuple(value.shape)}"
            )


def bind_spatial_column(
    program: SpatialColumnProgram,
    parameters: SpatialSiteParameters,
    spec: TFIMVQESpec,
) -> tuple[Array, ...]:
    """Bind one width-one spatial program."""

    _validate_site_parameters(parameters, spec)
    if program.width != 1:
        raise ValueError(
            "bind_spatial_column requires a width-one program"
        )
    return _bind_spatial_program(
        program,
        lambda _: parameters,
        spec,
    )


def _bind_spatial_program(
    program: SpatialColumnProgram,
    parameters_at: Callable[[int], SpatialSiteParameters],
    spec: TFIMVQESpec,
) -> tuple[Array, ...]:
    """Bind local tensors using one parameter view per site offset."""

    dtype = _complex_dtype(spec)
    product_state = _product_state_vector(spec)
    mpo_tensors = tfim_mpo_tensors(spec)

    tensors: list[Array] = []
    for slot in program.slots:
        parameters = parameters_at(slot.site_offset)
        if slot.kind == "initial_ket":
            tensor = product_state
        elif slot.kind == "initial_bra":
            tensor = jnp.conj(product_state)
        elif slot.kind in ("ket_rx", "bra_rx"):
            assert slot.layer is not None
            tensor = rx_matrix(parameters.rx[slot.layer], dtype)
            if slot.kind == "bra_rx":
                tensor = jnp.conj(tensor)
        elif slot.kind in ("ket_rzz_left", "bra_rzz_left"):
            assert slot.layer is not None
            tensor, _ = rzz_schmidt_factors(
                parameters.right_rzz[slot.layer],
                dtype,
            )
            if slot.kind == "bra_rzz_left":
                tensor = jnp.conj(tensor)
        elif slot.kind in ("ket_rzz_right", "bra_rzz_right"):
            assert slot.layer is not None
            _, tensor = rzz_schmidt_factors(
                parameters.left_rzz[slot.layer],
                dtype,
            )
            if slot.kind == "bra_rzz_right":
                tensor = jnp.conj(tensor)
        elif slot.kind.startswith("hamiltonian_mpo_"):
            if slot.kind == "hamiltonian_mpo_first":
                tensor = mpo_tensors[0]
            elif slot.kind == "hamiltonian_mpo_bulk":
                if spec.nqubits < 3:
                    raise ValueError(
                        "bulk MPO tensor requires at least "
                        "three qubits"
                    )
                tensor = mpo_tensors[1]
            else:
                tensor = mpo_tensors[-1]
        else:
            raise ValueError(
                f"unsupported spatial slot kind: {slot.kind}"
            )
        if tuple(tensor.shape) != slot.shape:
            raise ValueError(
                f"bound tensor shape {tuple(tensor.shape)} "
                f"does not match slot shape {slot.shape}"
            )
        tensors.append(tensor)
    return tuple(tensors)


def bind_spatial_block(
    program: SpatialColumnProgram,
    packed_sites: Array,
    spec: TFIMVQESpec,
) -> tuple[Array, ...]:
    """Bind all site-local tensors for one static-width spatial block."""

    expected = (program.width, 3, spec.depth)
    if tuple(packed_sites.shape) != expected:
        raise ValueError(
            f"packed block shape must be {expected}, "
            f"got {tuple(packed_sites.shape)}"
        )

    def parameters_at(
        site_offset: int,
    ) -> SpatialSiteParameters:
        site_values = packed_sites[site_offset]
        return SpatialSiteParameters(
            left_rzz=site_values[0],
            right_rzz=site_values[1],
            rx=site_values[2],
        )

    return _bind_spatial_program(
        program,
        parameters_at,
        spec,
    )


def execute_spatial_column(
    program: SpatialColumnProgram,
    carry: Array | None,
    tensors: tuple[Array, ...],
    explicit_executor: ExplicitContraction | None = None,
) -> Array:
    """Execute one explicit carry-fused column contraction."""

    if len(tensors) != len(program.slots):
        raise ValueError("tensor count does not match spatial column")
    operands = list(tensors)
    if program.carry_is_input:
        if carry is None:
            raise ValueError("column requires a boundary carry")
        if tuple(carry.shape) != program.left_boundary_shape:
            raise ValueError(
                "boundary carry shape does not match column: "
                f"expected {program.left_boundary_shape}, "
                f"got {tuple(carry.shape)}"
            )
        operands.insert(0, carry)
    elif carry is not None:
        raise ValueError("first column does not accept a boundary carry")

    if tuple(value.shape for value in operands) != program.input_shapes:
        raise ValueError("bound inputs do not match spatial program shapes")
    if explicit_executor is not None:
        result = explicit_executor(*operands)
    else:
        for step in program.steps:
            selected = [
                operands.pop(position)
                for position in step.positions
            ]
            contracted = jnp.einsum(
                step.einsum,
                *selected,
                optimize=True,
            )
            operands.append(contracted)
        if len(operands) != 1:
            raise RuntimeError(
                "spatial column did not produce one output"
            )
        result = operands[0]
    if tuple(result.shape) != program.right_boundary_shape:
        raise RuntimeError(
            "spatial column output shape does not match program"
        )
    return result


def spatial_energy_unrolled(
    theta: Array,
    program: SpatialTransferProgram,
) -> Array:
    """Execute the spatial recurrence with a Python-unrolled site loop."""

    spec = program.spec
    if tuple(theta.shape) != spec.parameter_shape:
        raise ValueError(
            f"theta shape must be {spec.parameter_shape}, "
            f"got {tuple(theta.shape)}"
        )
    carry = execute_spatial_column(
        program.first,
        None,
        bind_spatial_column(
            program.first,
            _site_parameters(theta, 0, spec),
            spec,
        ),
    )
    for site in range(1, spec.nqubits - 1):
        assert program.bulk is not None
        carry = execute_spatial_column(
            program.bulk,
            carry,
            bind_spatial_column(
                program.bulk,
                _site_parameters(theta, site, spec),
                spec,
            ),
        )
    energy = execute_spatial_column(
        program.last,
        carry,
        bind_spatial_column(
            program.last,
            _site_parameters(theta, spec.nqubits - 1, spec),
            spec,
        ),
    )
    return jnp.real(energy)


def _bulk_parameters(theta: Array) -> Array:
    """Pack left-bond, right-bond, and RX depth vectors by bulk site."""

    return jnp.stack(
        (
            theta[:, 0, 0:-2].T,
            theta[:, 0, 1:-1].T,
            theta[:, 1, 1:-1].T,
        ),
        axis=1,
    )


def _bulk_transition(
    carry: Array,
    packed_site: Array,
    *,
    spec: TFIMVQESpec,
    program: SpatialColumnProgram,
) -> Array:
    parameters = SpatialSiteParameters(
        left_rzz=packed_site[0],
        right_rzz=packed_site[1],
        rx=packed_site[2],
    )
    tensors = bind_spatial_column(program, parameters, spec)
    return execute_spatial_column(program, carry, tensors)


def _bulk_block_transition(
    carry: Array,
    packed_block: Array,
    *,
    spec: TFIMVQESpec,
    program: SpatialColumnProgram,
    explicit_executor: ExplicitContraction | None = None,
    native_executor: Z2NativeExecutor | None = None,
) -> Array:
    """Apply one carry-fused multi-site spatial block."""

    tensors = bind_spatial_block(program, packed_block, spec)
    if native_executor is not None:
        return native_executor(carry, tensors)
    return execute_spatial_column(
        program,
        carry,
        tensors,
        explicit_executor,
    )


def _first_boundary(
    theta: Array,
    transfer: SpatialTransferProgram,
    explicit_executor: ExplicitContraction | None = None,
) -> Array:
    spec = transfer.spec
    return execute_spatial_column(
        transfer.first,
        None,
        bind_spatial_column(
            transfer.first,
            _site_parameters(theta, 0, spec),
            spec,
        ),
        explicit_executor,
    )


def _last_energy(
    theta: Array,
    carry: Array,
    transfer: SpatialTransferProgram,
    explicit_executor: ExplicitContraction | None = None,
) -> Array:
    spec = transfer.spec
    result = execute_spatial_column(
        transfer.last,
        carry,
        bind_spatial_column(
            transfer.last,
            _site_parameters(theta, spec.nqubits - 1, spec),
            spec,
        ),
        explicit_executor,
    )
    return jnp.real(result)


def modeled_spatial_checkpoint_count(
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
) -> int:
    """Return the boundary-count model for one reverse schedule."""

    unit_count = (
        (spec.nqubits - 2) // config.block_width
    )
    if config.adjoint == "segmented":
        assert config.segment_length is not None
        return (
            ceil(unit_count / config.segment_length)
            + config.segment_length
        )
    return unit_count


def _build_segmented_bulk(
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
    transfer: SpatialTransferProgram,
    symmetry_sector: Z2BoundarySector | None = None,
    native_executor: Z2NativeExecutor | None = None,
) -> Callable[[Array, Array], Array]:
    """Build a sparse-checkpoint custom VJP for the bulk recurrence."""

    if transfer.bulk is None:
        raise ValueError(
            "segmented spatial adjoint requires bulk columns"
        )
    assert config.segment_length is not None
    segment_length = config.segment_length
    unit_count = transfer.bulk_block_count
    unit_width = transfer.block_width
    segment_count = ceil(unit_count / segment_length)
    padded_count = segment_count * segment_length
    padding = padded_count - unit_count
    segment_unroll = min(config.unroll, segment_length)

    def prepare_segments(
        packed_bulk: Array,
    ) -> tuple[Array, Array]:
        expected = (
            unit_count,
            unit_width,
            3,
            spec.depth,
        )
        if tuple(packed_bulk.shape) != expected:
            raise ValueError(
                f"bulk parameter shape must be {expected}, "
                f"got {tuple(packed_bulk.shape)}"
            )
        if padding:
            packed_bulk = jnp.pad(
                packed_bulk,
                (
                    (0, padding),
                    (0, 0),
                    (0, 0),
                    (0, 0),
                ),
            )
        mask = jnp.arange(padded_count) < unit_count
        return (
            packed_bulk.reshape(
                segment_count,
                segment_length,
                unit_width,
                3,
                spec.depth,
            ),
            mask.reshape(segment_count, segment_length),
        )

    def run_segment(
        boundary: Array,
        packed_segment: Array,
        mask_segment: Array,
    ) -> Array:
        def step(
            carry: Array,
            inputs: tuple[Array, Array],
        ) -> tuple[Array, None]:
            packed_block, valid = inputs
            dense_carry = (
                expand_boundary(carry, symmetry_sector)
                if symmetry_sector is not None
                else carry
            )
            next_dense = _bulk_block_transition(
                dense_carry,
                packed_block,
                spec=spec,
                program=transfer.bulk,
                native_executor=native_executor,
            )
            next_carry = (
                compress_boundary(
                    next_dense,
                    symmetry_sector,
                )
                if symmetry_sector is not None
                else next_dense
            )
            return jnp.where(valid, next_carry, carry), None

        final, _ = jax.lax.scan(
            step,
            boundary,
            (packed_segment, mask_segment),
            unroll=segment_unroll,
        )
        return final

    def evolve_with_checkpoints(
        initial_boundary: Array,
        packed_bulk: Array,
    ) -> tuple[Array, tuple[Array, Array, Array]]:
        segments, masks = prepare_segments(packed_bulk)

        def segment_body(
            boundary: Array,
            inputs: tuple[Array, Array],
        ) -> tuple[Array, Array]:
            packed_segment, mask_segment = inputs
            next_boundary = run_segment(
                boundary,
                packed_segment,
                mask_segment,
            )
            return next_boundary, boundary

        final, checkpoints = jax.lax.scan(
            segment_body,
            initial_boundary,
            (segments, masks),
        )
        return final, (segments, masks, checkpoints)

    @jax.custom_vjp
    def segmented_bulk(
        initial_boundary: Array,
        packed_bulk: Array,
    ) -> Array:
        final, _ = evolve_with_checkpoints(
            initial_boundary,
            packed_bulk,
        )
        return final

    def segmented_bulk_fwd(
        initial_boundary: Array,
        packed_bulk: Array,
    ) -> tuple[Array, tuple[Array, Array, Array]]:
        return evolve_with_checkpoints(initial_boundary, packed_bulk)

    def segmented_bulk_bwd(
        residual: tuple[Array, Array, Array],
        final_cotangent: Array,
    ) -> tuple[Array, Array]:
        segments, masks, checkpoints = residual

        def reverse_segment(
            boundary_cotangent: Array,
            inputs: tuple[Array, Array, Array],
        ) -> tuple[Array, Array]:
            packed_segment, mask_segment, left_boundary = inputs
            _, pullback = jax.vjp(
                lambda boundary, values: run_segment(
                    boundary,
                    values,
                    mask_segment,
                ),
                left_boundary,
                packed_segment,
            )
            left_cotangent, packed_cotangent = pullback(
                boundary_cotangent
            )
            return left_cotangent, packed_cotangent

        left_cotangent, segment_cotangents = jax.lax.scan(
            reverse_segment,
            final_cotangent,
            (segments, masks, checkpoints),
            reverse=True,
        )
        packed_cotangent = segment_cotangents.reshape(
            padded_count,
            unit_width,
            3,
            spec.depth,
        )[:unit_count]
        return left_cotangent, packed_cotangent

    segmented_bulk.defvjp(
        segmented_bulk_fwd,
        segmented_bulk_bwd,
    )
    return segmented_bulk


def build_spatial_energy(
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
) -> SpatialEnergyFunction:
    """Build one exact rolled spatial-transfer energy function."""

    transfer = plan_spatial_transfer(
        spec,
        config.path_strategy,
        explicit_paths=config.column_paths,
        block_width=config.block_width,
    )
    symmetry_sector = None
    if config.symmetry != "none":
        applicable, reason = z2_symmetry_applicability(spec)
        if not applicable:
            raise ValueError(
                f"Z2 symmetry compression is not applicable: {reason}"
            )
        symmetry_sector = z2_boundary_sector(
            transfer.boundary_shape
        )
    if (
        config.symmetry == "z2-native"
        and config.adjoint == "explicit"
    ):
        raise ValueError(
            "z2-native does not yet support the explicit "
            "contraction adjoint"
        )
    native_first = (
        build_z2_native_contraction(
            transfer.first,
            symmetry_sector,
            dtype=_complex_dtype(spec),
            strategy=config.path_strategy,
        )
        if config.symmetry == "z2-native"
        else None
    )
    native_bulk = (
        build_z2_native_contraction(
            transfer.bulk,
            symmetry_sector,
            dtype=_complex_dtype(spec),
            strategy=config.path_strategy,
        )
        if (
            config.symmetry == "z2-native"
            and transfer.bulk is not None
        )
        else None
    )
    native_tail = (
        build_z2_native_contraction(
            transfer.tail,
            symmetry_sector,
            dtype=_complex_dtype(spec),
            strategy=config.path_strategy,
        )
        if (
            config.symmetry == "z2-native"
            and transfer.tail is not None
        )
        else None
    )
    native_last = (
        build_z2_native_contraction(
            transfer.last,
            symmetry_sector,
            dtype=_complex_dtype(spec),
            strategy=config.path_strategy,
        )
        if config.symmetry == "z2-native"
        else None
    )
    segmented_bulk = (
        _build_segmented_bulk(
            spec,
            config,
            transfer,
            (
                symmetry_sector
                if config.symmetry == "z2-reference"
                else None
            ),
            (
                native_bulk.executor
                if native_bulk is not None
                else None
            ),
        )
        if config.adjoint == "segmented"
        else None
    )
    explicit_first = (
        build_explicit_contraction_vjp(
            transfer.first.input_shapes,
            transfer.first.steps,
        )
        if config.adjoint == "explicit"
        else None
    )
    explicit_bulk = (
        build_explicit_contraction_vjp(
            transfer.bulk.input_shapes,
            transfer.bulk.steps,
        )
        if (
            config.adjoint == "explicit"
            and transfer.bulk is not None
        )
        else None
    )
    explicit_tail = (
        build_explicit_contraction_vjp(
            transfer.tail.input_shapes,
            transfer.tail.steps,
        )
        if (
            config.adjoint == "explicit"
            and transfer.tail is not None
        )
        else None
    )
    explicit_last = (
        build_explicit_contraction_vjp(
            transfer.last.input_shapes,
            transfer.last.steps,
        )
        if config.adjoint == "explicit"
        else None
    )

    def energy(theta: Array) -> Array:
        if tuple(theta.shape) != spec.parameter_shape:
            raise ValueError(
                f"theta shape must be {spec.parameter_shape}, "
                f"got {tuple(theta.shape)}"
            )
        if native_first is not None:
            carry = native_first.executor(
                None,
                bind_spatial_column(
                    transfer.first,
                    _site_parameters(theta, 0, spec),
                    spec,
                ),
            )
        else:
            carry = _first_boundary(
                theta,
                transfer,
                explicit_first,
            )
        if config.symmetry == "z2-reference":
            carry = compress_boundary(
                carry,
                symmetry_sector,
            )
        interior_count = spec.nqubits - 2
        if interior_count:
            packed_interior = _bulk_parameters(theta)
            if segmented_bulk is not None:
                full_site_count = (
                    transfer.bulk_block_count
                    * transfer.block_width
                )
                packed_blocks = packed_interior[
                    :full_site_count
                ].reshape(
                    transfer.bulk_block_count,
                    transfer.block_width,
                    3,
                    spec.depth,
                )
                carry = segmented_bulk(
                    carry,
                    packed_blocks,
                )
            elif transfer.bulk is not None:
                full_site_count = (
                    transfer.bulk_block_count
                    * transfer.block_width
                )
                packed_blocks = packed_interior[
                    :full_site_count
                ].reshape(
                    transfer.bulk_block_count,
                    transfer.block_width,
                    3,
                    spec.depth,
                )

                def transition(
                    boundary: Array,
                    packed_block: Array,
                ) -> Array:
                    assert transfer.bulk is not None
                    dense_boundary = (
                        expand_boundary(
                            boundary,
                            symmetry_sector,
                        )
                        if config.symmetry == "z2-reference"
                        else boundary
                    )
                    dense_result = _bulk_block_transition(
                        dense_boundary,
                        packed_block,
                        spec=spec,
                        program=transfer.bulk,
                        explicit_executor=explicit_bulk,
                        native_executor=(
                            native_bulk.executor
                            if native_bulk is not None
                            else None
                        ),
                    )
                    return (
                        compress_boundary(
                            dense_result,
                            symmetry_sector,
                        )
                        if config.symmetry == "z2-reference"
                        else dense_result
                    )

                if config.adjoint == "remat":
                    transition = jax.checkpoint(transition)

                def body(
                    boundary: Array,
                    packed_block: Array,
                ) -> tuple[Array, None]:
                    return (
                        transition(boundary, packed_block),
                        None,
                    )

                carry, _ = jax.lax.scan(
                    body,
                    carry,
                    packed_blocks,
                    unroll=min(
                        config.unroll,
                        transfer.bulk_block_count,
                    ),
                )
            if transfer.tail is not None:
                tail_start = (
                    transfer.bulk_block_count
                    * transfer.block_width
                )
                packed_tail = packed_interior[tail_start:]

                def tail_transition(
                    boundary: Array,
                    values: Array,
                ) -> Array:
                    assert transfer.tail is not None
                    dense_boundary = (
                        expand_boundary(
                            boundary,
                            symmetry_sector,
                        )
                        if config.symmetry == "z2-reference"
                        else boundary
                    )
                    dense_result = _bulk_block_transition(
                        dense_boundary,
                        values,
                        spec=spec,
                        program=transfer.tail,
                        explicit_executor=explicit_tail,
                        native_executor=(
                            native_tail.executor
                            if native_tail is not None
                            else None
                        ),
                    )
                    return (
                        compress_boundary(
                            dense_result,
                            symmetry_sector,
                        )
                        if config.symmetry == "z2-reference"
                        else dense_result
                    )

                if config.adjoint == "remat":
                    tail_transition = jax.checkpoint(
                        tail_transition
                    )
                carry = tail_transition(carry, packed_tail)
        if native_last is not None:
            return jnp.real(
                native_last.executor(
                    carry,
                    bind_spatial_column(
                        transfer.last,
                        _site_parameters(
                            theta,
                            spec.nqubits - 1,
                            spec,
                        ),
                        spec,
                    ),
                )
            )
        dense_carry = (
            expand_boundary(carry, symmetry_sector)
            if config.symmetry == "z2-reference"
            else carry
        )
        return _last_energy(
            theta,
            dense_carry,
            transfer,
            explicit_last,
        )

    return energy


def build_spatial_value_and_grad(
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
) -> SpatialValueAndGradFunction:
    """Build a JIT-compiled exact spatial energy and full gradient."""

    return jax.jit(
        jax.value_and_grad(build_spatial_energy(spec, config))
    )
