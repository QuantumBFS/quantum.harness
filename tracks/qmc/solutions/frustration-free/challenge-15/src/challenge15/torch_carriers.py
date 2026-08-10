from __future__ import annotations

import torch

from challenge15.physics_data import orbital_table, pair_channel_indices
from challenge15.spec import SphereSpec
from challenge15.torch_pfaffian import bordered_pfaffian, pfaffian

_WEIGHT_DTYPES = (torch.float64, torch.complex128)


def _checked_spinors(
    spinors: torch.Tensor, *, expected_shape: tuple[int, ...] | None = None
) -> torch.Tensor:
    if not isinstance(spinors, torch.Tensor):
        raise TypeError("spinors must be a torch.Tensor")
    if spinors.dtype != torch.complex128:
        raise TypeError("spinors must have dtype torch.complex128")
    if spinors.ndim == 0 or spinors.shape[-1] != 2:
        raise ValueError("spinors must have last axis of length 2")
    if expected_shape is not None and spinors.shape != expected_shape:
        raise ValueError(f"spinors must have shape {expected_shape}")
    return spinors


def raw_north_lll_polynomials(
    spinors: torch.Tensor, spec: SphereSpec
) -> torch.Tensor:
    """Evaluate unnormalized homogeneous north-chart LLL polynomials."""
    values = _checked_spinors(spinors)
    table = orbital_table(spec)
    normalizations = torch.tensor(
        table.normalizations, dtype=torch.complex128, device=values.device
    )
    u_powers = torch.tensor(
        table.u_powers, dtype=torch.int64, device=values.device
    )
    v_powers = torch.tensor(
        table.v_powers, dtype=torch.int64, device=values.device
    )
    u = values[..., 0, None]
    v = values[..., 1, None]
    return normalizations * u**u_powers * v**v_powers


def _checked_weights(
    pair_weights: torch.Tensor,
    spec: SphereSpec,
    *,
    device: torch.device,
    require_bank: bool,
) -> torch.Tensor:
    if not isinstance(pair_weights, torch.Tensor):
        raise TypeError("pair_weights must be a torch.Tensor")
    if pair_weights.dtype not in _WEIGHT_DTYPES:
        raise TypeError("pair_weights must have dtype torch.float64 or complex128")
    if pair_weights.device != device:
        raise ValueError("spinors and pair_weights must be on the same device")
    if pair_weights.ndim not in (1, 2):
        raise ValueError("pair_weights must have one or two dimensions")
    if require_bank and pair_weights.ndim != 2:
        raise ValueError("pair_weights must contain a leading carrier axis")
    channel_count = len(pair_channel_indices(spec)[0])
    if pair_weights.shape[-1] != channel_count:
        raise ValueError(
            "pair_weights must have one entry per positive-m channel "
            f"({channel_count})"
        )
    return pair_weights.to(dtype=torch.complex128)


def _checked_borders(
    border_weight,
    *,
    carriers: int | None,
    device: torch.device,
) -> torch.Tensor:
    if isinstance(border_weight, torch.Tensor):
        if border_weight.dtype not in _WEIGHT_DTYPES:
            raise TypeError(
                "border_weight must have dtype torch.float64 or complex128"
            )
        if border_weight.device != device:
            raise ValueError("spinors and border_weight must be on the same device")
        borders = border_weight.to(dtype=torch.complex128)
    else:
        try:
            borders = torch.as_tensor(
                border_weight, dtype=torch.complex128, device=device
            )
        except (TypeError, ValueError) as error:
            raise TypeError("border_weight must be a real or complex scalar") from error

    if carriers is None:
        if borders.ndim != 0:
            raise ValueError("border_weight must be scalar for one carrier")
        return borders
    if borders.ndim == 0:
        return borders.expand(carriers)
    if borders.shape != (carriers,):
        raise ValueError(
            "border_weight must be scalar or have one entry per carrier"
        )
    return borders


def _carrier_bank(
    spinors: torch.Tensor,
    spec: SphereSpec,
    pair_weights: torch.Tensor,
    border_weight,
) -> torch.Tensor:
    weights = _checked_weights(
        pair_weights,
        spec,
        device=spinors.device,
        require_bank=False,
    )
    carriers = None if weights.ndim == 1 else weights.shape[0]
    borders = _checked_borders(
        border_weight, carriers=carriers, device=spinors.device
    )
    orbitals = raw_north_lll_polynomials(spinors, spec)
    positive, negative = pair_channel_indices(spec)
    positive_indices = torch.tensor(
        positive, dtype=torch.int64, device=spinors.device
    )
    negative_indices = torch.tensor(
        negative, dtype=torch.int64, device=spinors.device
    )
    positive_values = orbitals.index_select(1, positive_indices)
    negative_values = orbitals.index_select(1, negative_indices)
    forward = torch.einsum(
        "ik,...k,jk->...ij", positive_values, weights, negative_values
    )
    pair_matrix = forward - forward.transpose(-1, -2)

    if spec.particles % 2 == 0:
        return pfaffian(pair_matrix)

    zero_orbital = spec.two_m_values.index(0)
    border = borders[..., None] * orbitals[:, zero_orbital]
    return bordered_pfaffian(pair_matrix, border)


def carrier_amplitudes(
    spinors: torch.Tensor,
    spec: SphereSpec,
    pair_weights: torch.Tensor,
    border_weight=1.0,
) -> torch.Tensor:
    """Evaluate one carrier or a leading-axis bank of carriers."""
    values = _checked_spinors(
        spinors, expected_shape=(spec.particles, 2)
    )
    return _carrier_bank(values, spec, pair_weights, border_weight)


def batched_carrier_amplitudes(
    spinors: torch.Tensor,
    spec: SphereSpec,
    pair_weights: torch.Tensor,
    border_weight=1.0,
) -> torch.Tensor:
    """Evaluate a walker/carrier block with shape ``[walker, carrier]``."""
    values = _checked_spinors(spinors)
    if values.ndim != 3 or values.shape[1:] != (spec.particles, 2):
        raise ValueError(
            "spinors must have shape (walkers, spec.particles, 2)"
        )
    weights = _checked_weights(
        pair_weights,
        spec,
        device=values.device,
        require_bank=True,
    )
    borders = _checked_borders(
        border_weight, carriers=weights.shape[0], device=values.device
    )
    if values.shape[0] == 0:
        return torch.empty(
            (0, weights.shape[0]), dtype=torch.complex128, device=values.device
        )
    return torch.stack(
        [
            _carrier_bank(walker, spec, weights, borders)
            for walker in values.unbind(0)
        ]
    )


__all__ = [
    "batched_carrier_amplitudes",
    "carrier_amplitudes",
    "raw_north_lll_polynomials",
]
