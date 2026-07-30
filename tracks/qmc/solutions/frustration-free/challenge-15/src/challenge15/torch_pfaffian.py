from __future__ import annotations

import torch

_SKEW_TOLERANCE = 1e-12


def _checked_matrix(
    matrix: torch.Tensor, *, even: bool, check_skew: bool
) -> torch.Tensor:
    if not isinstance(matrix, torch.Tensor):
        raise TypeError("Pfaffian input must be a torch.Tensor")
    if matrix.dtype != torch.complex128:
        raise TypeError("Pfaffian input must have dtype torch.complex128")
    if matrix.ndim < 2 or matrix.shape[-2] != matrix.shape[-1]:
        raise ValueError("Pfaffian input must be a square matrix")
    if (matrix.shape[-1] % 2 == 0) != even:
        parity = "even" if even else "odd"
        raise ValueError(f"Pfaffian input dimension must be {parity}")
    if check_skew and not torch.allclose(
        matrix,
        -matrix.transpose(-1, -2),
        rtol=0.0,
        atol=_SKEW_TOLERANCE,
    ):
        raise ValueError(
            f"Pfaffian input must be skew-symmetric within {_SKEW_TOLERANCE:g}"
        )
    return matrix


def _single_pfaffian_elimination(matrix: torch.Tensor) -> torch.Tensor:
    size = matrix.shape[-1]
    if size == 0:
        return torch.ones((), dtype=matrix.dtype, device=matrix.device)

    work = matrix
    phase = torch.ones((), dtype=matrix.dtype, device=matrix.device)
    log_magnitude = torch.zeros(
        (), dtype=matrix.real.dtype, device=matrix.device
    )
    rank_deficient = torch.zeros((), dtype=torch.bool, device=matrix.device)
    indices = torch.arange(size, device=matrix.device)

    for start in range(0, size, 2):
        allowed = (
            (indices[:, None] >= start)
            & (indices[None, :] >= start)
            & (indices[:, None] < indices[None, :])
        )
        magnitudes = torch.abs(work)
        pivot_scores = torch.where(allowed, magnitudes, -torch.ones_like(magnitudes))
        flat_pivot = torch.argmax(pivot_scores)
        first = torch.div(flat_pivot, size, rounding_mode="floor")
        second = flat_pivot % size

        first_permutation = torch.where(
            indices == start,
            first,
            torch.where(indices == first, start, indices),
        )
        work = work.index_select(0, first_permutation).index_select(
            1, first_permutation
        )
        phase = torch.where(first == start, phase, -phase)

        second_permutation = torch.where(
            indices == start + 1,
            second,
            torch.where(indices == second, start + 1, indices),
        )
        work = work.index_select(0, second_permutation).index_select(
            1, second_permutation
        )
        phase = torch.where(second == start + 1, phase, -phase)

        pivot = work[start, start + 1]
        pivot_magnitude = torch.abs(pivot)
        pivot_is_zero = pivot_magnitude == 0
        rank_deficient = rank_deficient | pivot_is_zero
        safe_pivot = torch.where(pivot_is_zero, torch.ones_like(pivot), pivot)
        safe_magnitude = torch.where(
            pivot_is_zero, torch.ones_like(pivot_magnitude), pivot_magnitude
        )
        phase = phase * safe_pivot / safe_magnitude
        log_magnitude = log_magnitude + torch.log(safe_magnitude)

        if start + 2 < size:
            first_row = work[start, start + 2 :]
            second_row = work[start + 1, start + 2 :]
            trailing = work[start + 2 :, start + 2 :]
            scaled_first_row = first_row / safe_pivot
            scaled_second_row = second_row / safe_pivot
            correction = (
                scaled_second_row[:, None] * first_row[None, :]
                - scaled_first_row[:, None] * second_row[None, :]
            )
            updated_trailing = trailing + correction
            work = torch.cat(
                (
                    work[: start + 2],
                    torch.cat(
                        (work[start + 2 :, : start + 2], updated_trailing), dim=1
                    ),
                ),
                dim=0,
            )

    value = phase * torch.exp(log_magnitude)
    return torch.where(rank_deficient, torch.zeros_like(value), value)


def _trusted_pfaffian_elimination(matrix: torch.Tensor) -> torch.Tensor:
    """Return stable values after structural checks for a trusted skew matrix."""
    matrix = _checked_matrix(matrix, even=True, check_skew=False)
    batch_shape = matrix.shape[:-2]
    if matrix.shape[-1] == 0:
        return torch.ones(batch_shape, dtype=matrix.dtype, device=matrix.device)

    flat = matrix.reshape((-1, matrix.shape[-2], matrix.shape[-1]))
    if flat.shape[0] == 0:
        return torch.empty(batch_shape, dtype=matrix.dtype, device=matrix.device)
    values = [_single_pfaffian_elimination(item) for item in flat.unbind(0)]
    return torch.stack(values).reshape(batch_shape)


def pfaffian_elimination(matrix: torch.Tensor) -> torch.Tensor:
    """Validate and eliminate even complex128 skew matrices."""
    return _trusted_pfaffian_elimination(
        _checked_matrix(matrix, even=True, check_skew=True)
    )


def _trusted_pfaffian_cofactors(matrix: torch.Tensor) -> torch.Tensor:
    """Return strict-upper signed minors for an internally trusted skew matrix."""
    matrix = _checked_matrix(matrix, even=True, check_skew=False)
    size = matrix.shape[-1]
    cofactors = torch.zeros_like(matrix)
    for first in range(size):
        for second in range(first + 1, size):
            retained = [
                index for index in range(size) if index not in (first, second)
            ]
            retained_indices = torch.tensor(
                retained, dtype=torch.long, device=matrix.device
            )
            minor = matrix.index_select(-2, retained_indices).index_select(
                -1, retained_indices
            )
            sign = -1 if (first + second + 1) % 2 else 1
            cofactors[..., first, second] = (
                sign * _trusted_pfaffian_elimination(minor)
            )
    return cofactors


def pfaffian_cofactors(matrix: torch.Tensor) -> torch.Tensor:
    """Validate and return signed minors in the strict upper triangle only."""
    return _trusted_pfaffian_cofactors(
        _checked_matrix(matrix, even=True, check_skew=True)
    )


class _RejectSecondDerivative(torch.autograd.Function):
    @staticmethod
    def forward(ctx, matrix: torch.Tensor, gradient: torch.Tensor) -> torch.Tensor:
        del ctx, matrix
        return gradient

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):
        del ctx, grad_output
        raise RuntimeError(
            "trying to differentiate twice a function marked once_differentiable"
        )


class _Pfaffian(torch.autograd.Function):
    @staticmethod
    def forward(matrix: torch.Tensor) -> torch.Tensor:
        return _trusted_pfaffian_elimination(matrix)

    @staticmethod
    def setup_context(ctx, inputs, output) -> None:
        del output
        (matrix,) = inputs
        ctx.save_for_backward(matrix)
        ctx.save_for_forward(matrix)

    @staticmethod
    @torch.autograd.function.once_differentiable
    def backward(ctx, grad_output: torch.Tensor) -> torch.Tensor:
        (matrix,) = ctx.saved_tensors
        cofactors = _trusted_pfaffian_cofactors(matrix.detach())
        gradient = grad_output[..., None, None] * cofactors.conj()
        with torch.enable_grad():
            return _RejectSecondDerivative.apply(matrix, gradient)

    @staticmethod
    def jvp(ctx, matrix_tangent: torch.Tensor) -> torch.Tensor:
        (matrix,) = ctx.saved_tensors
        cofactors = _trusted_pfaffian_cofactors(matrix.detach())
        return (cofactors * matrix_tangent).sum(dim=(-2, -1))


def _trusted_pfaffian(matrix: torch.Tensor) -> torch.Tensor:
    """Return the Pfaffian of an internally guaranteed skew matrix."""
    return _Pfaffian.apply(matrix)


def pfaffian(matrix: torch.Tensor) -> torch.Tensor:
    """Validate and return Pfaffians of even complex128 skew matrices."""
    return _trusted_pfaffian(
        _checked_matrix(matrix, even=True, check_skew=True)
    )


def _trusted_bordered_pfaffian(
    matrix: torch.Tensor, border: torch.Tensor
) -> torch.Tensor:
    size = matrix.shape[-1]
    augmented = torch.zeros(
        (*matrix.shape[:-2], size + 1, size + 1),
        dtype=matrix.dtype,
        device=matrix.device,
    )
    augmented[..., :-1, :-1] = matrix
    augmented[..., :-1, -1] = border
    augmented[..., -1, :-1] = -border
    return _trusted_pfaffian(augmented)


def bordered_pfaffian(
    matrix: torch.Tensor, border: torch.Tensor
) -> torch.Tensor:
    """Append ``border`` as the final column and return the Pfaffian."""
    matrix = _checked_matrix(matrix, even=False, check_skew=True)
    if not isinstance(border, torch.Tensor):
        raise TypeError("border must be a torch.Tensor")
    if border.dtype != torch.complex128:
        raise TypeError("border must have dtype torch.complex128")
    if border.device != matrix.device:
        raise ValueError("border and matrix must be on the same device")
    if border.shape != (*matrix.shape[:-2], matrix.shape[-1]):
        if border.shape[-1:] == (matrix.shape[-1],):
            raise ValueError("border must have matching leading batch axes")
        raise ValueError("border must have one entry per matrix row")
    return _trusted_bordered_pfaffian(matrix, border)


__all__ = [
    "bordered_pfaffian",
    "pfaffian",
    "pfaffian_cofactors",
    "pfaffian_elimination",
]
