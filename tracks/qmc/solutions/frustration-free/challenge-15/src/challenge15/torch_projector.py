from __future__ import annotations

from collections.abc import Callable
from math import pi

import numpy as np
import torch
from torch.utils.checkpoint import checkpoint

from challenge15.projection_data import (
    ProjectionGrid,
    coordinate_euler_substitutions,
    wigner_d_m0,
)
from challenge15.spec import SphereSpec
from challenge15.torch_carriers import batched_carrier_amplitudes

TensorAmplitude = Callable[[torch.Tensor], torch.Tensor]


def project_m0(
    amplitude: TensorAmplitude,
    spinors: torch.Tensor,
    spec: SphereSpec,
    target_l: int,
    *,
    grid: ProjectionGrid | None = None,
    block_size: int = 64,
) -> torch.Tensor:
    """Evaluate the exact pointwise ``P^L_00`` projection."""

    return _project_components(
        amplitude,
        spinors,
        spec,
        target_l,
        components=(0,),
        grid=grid,
        block_size=block_size,
    )[0]


def project_multiplet(
    amplitude: TensorAmplitude,
    spinors: torch.Tensor,
    spec: SphereSpec,
    target_l: int,
    *,
    grid: ProjectionGrid | None = None,
    block_size: int = 64,
) -> dict[int, torch.Tensor]:
    """Evaluate every ``P^L_M0`` component from one carrier callable."""

    _validate_target_l(spec, target_l)
    components = tuple(range(-target_l, target_l + 1))
    values = _project_components(
        amplitude,
        spinors,
        spec,
        target_l,
        components=components,
        grid=grid,
        block_size=block_size,
    )
    return dict(zip(components, values, strict=True))


def project_carrier_block(
    spinors: torch.Tensor,
    spec: SphereSpec,
    weights: torch.Tensor,
    borders: torch.Tensor,
    *,
    target_l: int,
    quadrature_block: int,
) -> torch.Tensor:
    """Project a fixed walker/carrier block with shape ``[walker, carrier]``."""

    _validate_target_l(spec, target_l)
    _validate_block_size(quadrature_block, "quadrature_block")
    walkers = _validate_walker_batch(spinors, spec)
    carrier_weights, carrier_borders = _validate_carrier_bank(
        weights, borders, walkers.device
    )
    grid = ProjectionGrid.exact(spec, target_l)

    def evaluate(rotated: torch.Tensor) -> torch.Tensor:
        values = [
            batched_carrier_amplitudes(
                node_walkers,
                spec,
                carrier_weights,
                border_weight=carrier_borders,
            )
            for node_walkers in rotated.unbind(0)
        ]
        return torch.stack(values)

    return _blocked_projection(
        evaluate,
        walkers,
        grid,
        target_l,
        components=(0,),
        block_size=quadrature_block,
        output_shape=(walkers.shape[0], carrier_weights.shape[0]),
    )[0]


def _project_components(
    amplitude: TensorAmplitude,
    spinors: torch.Tensor,
    spec: SphereSpec,
    target_l: int,
    *,
    components: tuple[int, ...],
    grid: ProjectionGrid | None,
    block_size: int,
) -> tuple[torch.Tensor, ...]:
    _validate_target_l(spec, target_l)
    _validate_block_size(block_size, "block_size")
    values = _validate_single_walker(spinors, spec)
    active_grid = ProjectionGrid.exact(spec, target_l) if grid is None else grid
    _validate_grid(active_grid, spec, target_l)

    def evaluate(rotated: torch.Tensor) -> torch.Tensor:
        outputs = []
        for node_spinors in rotated.unbind(0):
            output = amplitude(node_spinors)
            if not isinstance(output, torch.Tensor):
                raise TypeError("amplitude must return a torch.Tensor")
            if output.dtype != torch.complex128:
                raise TypeError("amplitude must return dtype torch.complex128")
            if output.device != values.device:
                raise ValueError(
                    "amplitude output and spinors must use the same device"
                )
            if output.ndim != 0:
                raise ValueError("amplitude must return a scalar tensor")
            outputs.append(output)
        return torch.stack(outputs)

    return _blocked_projection(
        evaluate,
        values,
        active_grid,
        target_l,
        components=components,
        block_size=block_size,
        output_shape=(),
    )


def _blocked_projection(
    evaluator: Callable[[torch.Tensor], torch.Tensor],
    spinors: torch.Tensor,
    grid,
    target_l: int,
    *,
    components: tuple[int, ...],
    block_size: int,
    output_shape: tuple[int, ...],
) -> tuple[torch.Tensor, ...]:
    blocks = grid.static_blocks(block_size)
    node_count = grid.n_alpha * grid.n_beta
    tree_size = 1 << (node_count - 1).bit_length()
    level_count = tree_size.bit_length()
    levels = [
        [
            torch.zeros(output_shape, dtype=torch.complex128, device=spinors.device)
            for _ in range(level_count)
        ]
        for _ in components
    ]
    occupied = [[False] * level_count for _ in components]
    prefactor = (2 * target_l + 1) / (4.0 * pi)

    for block_index in range(blocks.alpha_nodes.shape[0]):
        alpha_numpy = blocks.alpha_nodes[block_index]
        beta_numpy = blocks.beta_nodes[block_index]
        node_valid_numpy = blocks.node_valid[block_index]
        tree_valid_numpy = blocks.tree_valid[block_index]
        safe_alpha_numpy = np.where(node_valid_numpy, alpha_numpy, 0.0)
        safe_beta_numpy = np.where(node_valid_numpy, beta_numpy, 1.0)
        rotations_numpy = coordinate_euler_substitutions(
            safe_alpha_numpy, safe_beta_numpy
        )
        rotations = torch.tensor(
            rotations_numpy, dtype=torch.complex128, device=spinors.device
        )
        rotated = torch.einsum("qab,...ib->q...ia", rotations, spinors)
        amplitudes = checkpoint(evaluator, rotated, use_reentrant=False)
        expected_shape = (block_size, *output_shape)
        if amplitudes.shape != expected_shape:
            raise ValueError(
                f"amplitude block must have shape {expected_shape}, "
                f"got {tuple(amplitudes.shape)}"
            )
        if amplitudes.dtype != torch.complex128:
            raise TypeError("amplitude block must have dtype torch.complex128")
        if amplitudes.device != spinors.device:
            raise ValueError("amplitude block and spinors must use the same device")

        node_valid = torch.tensor(
            node_valid_numpy, dtype=torch.bool, device=spinors.device
        )
        mask_shape = (block_size,) + (1,) * len(output_shape)
        safe_amplitudes = torch.where(
            node_valid.reshape(mask_shape),
            amplitudes,
            torch.zeros_like(amplitudes),
        )
        for component_index, m in enumerate(components):
            kernel_numpy = (
                prefactor
                * np.where(node_valid_numpy, blocks.weights[block_index], 0.0)
                * wigner_d_m0(target_l, m, safe_beta_numpy)
                * np.exp(1j * m * safe_alpha_numpy)
            )
            kernel = torch.tensor(
                kernel_numpy, dtype=torch.complex128, device=spinors.device
            )
            safe_kernel = torch.where(
                node_valid,
                kernel,
                torch.zeros_like(kernel),
            )
            contributions = safe_kernel.reshape(mask_shape) * safe_amplitudes
            for local_index in range(block_size):
                _pairwise_insert(
                    levels[component_index],
                    occupied[component_index],
                    contributions[local_index],
                    bool(tree_valid_numpy[local_index]),
                )

    return tuple(component_levels[-1] for component_levels in levels)


def _pairwise_insert(
    levels: list[torch.Tensor],
    occupied: list[bool],
    value: torch.Tensor,
    active: bool,
) -> None:
    if not active:
        return
    carry = value
    for level in range(len(levels)):
        if not occupied[level]:
            levels[level] = carry
            occupied[level] = True
            return
        carry = levels[level] + carry
        levels[level] = torch.zeros_like(levels[level])
        occupied[level] = False
    raise RuntimeError("pairwise reduction tree overflow")


def _validate_single_walker(spinors: torch.Tensor, spec: SphereSpec) -> torch.Tensor:
    if not isinstance(spinors, torch.Tensor):
        raise TypeError("spinors must be a torch.Tensor")
    if spinors.dtype != torch.complex128:
        raise TypeError("spinors must have dtype torch.complex128")
    if spinors.shape != (spec.particles, 2):
        raise ValueError("spinors must have shape (spec.particles, 2)")
    return spinors


def _validate_walker_batch(spinors: torch.Tensor, spec: SphereSpec) -> torch.Tensor:
    if not isinstance(spinors, torch.Tensor):
        raise TypeError("spinors must be a torch.Tensor")
    if spinors.dtype != torch.complex128:
        raise TypeError("spinors must have dtype torch.complex128")
    if spinors.ndim != 3 or spinors.shape[1:] != (spec.particles, 2):
        raise ValueError("walkers must have shape (walker, spec.particles, 2)")
    return spinors


def _validate_carrier_bank(
    weights: torch.Tensor,
    borders: torch.Tensor,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    if not isinstance(weights, torch.Tensor):
        raise TypeError("weights must be a torch.Tensor")
    if weights.dtype not in (torch.float64, torch.complex128):
        raise TypeError("weights must have dtype torch.float64 or complex128")
    if weights.ndim != 2:
        raise ValueError("weights must contain a leading carrier axis")
    if weights.device != device:
        raise ValueError("spinors, weights, and borders must use the same device")
    if not isinstance(borders, torch.Tensor):
        raise TypeError("borders must be a torch.Tensor")
    if borders.dtype not in (torch.float64, torch.complex128):
        raise TypeError("borders must have dtype torch.float64 or complex128")
    if borders.device != device:
        raise ValueError("spinors, weights, and borders must use the same device")
    if borders.ndim == 0:
        borders = borders.expand(weights.shape[0])
    if borders.shape != (weights.shape[0],):
        raise ValueError("borders must be scalar or have one entry per carrier")
    return weights.to(torch.complex128), borders.to(torch.complex128)


def _validate_grid(grid, spec: SphereSpec, target_l: int) -> None:
    required = ("target_l", "l_max", "n_alpha", "n_beta", "static_blocks")
    if not all(hasattr(grid, name) for name in required):
        raise ValueError("grid must provide the ProjectionGrid interface")
    if grid.target_l != target_l or grid.l_max != spec.l_max:
        raise ValueError("grid must match the supplied SphereSpec and target_l")
    if grid.n_alpha < 2 * spec.l_max + 1:
        raise ValueError("alpha rule does not satisfy the exact finite-band bound")
    if 2 * grid.n_beta - 1 < spec.l_max + target_l:
        raise ValueError("beta rule does not satisfy the exact polynomial bound")


def _validate_target_l(spec: SphereSpec, target_l: int) -> None:
    if not isinstance(target_l, int) or isinstance(target_l, bool):
        raise ValueError("target_l must be a Python integer")  # noqa: TRY004
    if target_l < 0 or target_l > spec.l_max:
        raise ValueError("target_l must satisfy 0 <= target_l <= spec.l_max")


def _validate_block_size(block_size: int, name: str) -> None:
    if (
        not isinstance(block_size, int)
        or isinstance(block_size, bool)
        or block_size <= 0
    ):
        raise ValueError(f"{name} must be a positive Python integer")


__all__ = ["project_carrier_block", "project_m0", "project_multiplet"]
