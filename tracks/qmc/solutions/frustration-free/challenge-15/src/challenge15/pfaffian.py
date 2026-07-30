from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np

_SKEW_TOLERANCE = 1e-12


def _raise_if_not_skew(matrix) -> None:
    array = np.asarray(matrix)
    if array.size and np.max(np.abs(array + array.T)) > _SKEW_TOLERANCE:
        raise ValueError(
            f"Pfaffian input must be skew-symmetric within {_SKEW_TOLERANCE:g}"
        )


def _checked_skew_matrix(matrix, *, even: bool) -> jax.Array:
    array = jnp.asarray(matrix)
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError("Pfaffian input must be a square matrix")
    if (array.shape[0] % 2 == 0) != even:
        parity = "even" if even else "odd"
        raise ValueError(f"Pfaffian input dimension must be {parity}")
    if isinstance(array, jax.core.Tracer):
        jax.debug.callback(_raise_if_not_skew, array, ordered=True)
    else:
        _raise_if_not_skew(array)
    return array


def _checked_even_skew_matrix(matrix) -> jax.Array:
    return _checked_skew_matrix(matrix, even=True)


def _pfaffian_elimination(matrix: jax.Array) -> jax.Array:
    """Complete-pivot skew elimination with the Pfaffian phase tracked."""
    size = matrix.shape[0]
    if size == 0:
        return jnp.ones((), dtype=matrix.dtype)

    work = matrix
    phase = jnp.ones((), dtype=matrix.dtype)
    log_magnitude = jnp.zeros((), dtype=matrix.real.dtype)
    rank_deficient = jnp.array(False)
    indices = jnp.arange(size)

    for start in range(0, size, 2):
        allowed = (
            (indices[:, None] >= start)
            & (indices[None, :] >= start)
            & (indices[:, None] < indices[None, :])
        )
        pivot_scores = jnp.where(allowed, jnp.abs(work), -jnp.ones_like(jnp.abs(work)))
        flat_pivot = jnp.argmax(pivot_scores)
        first = flat_pivot // size
        second = flat_pivot % size

        first_permutation = indices.at[start].set(first).at[first].set(start)
        work = work[first_permutation][:, first_permutation]
        phase = jnp.where(first == start, phase, -phase)

        second_permutation = indices.at[start + 1].set(second).at[second].set(start + 1)
        work = work[second_permutation][:, second_permutation]
        phase = jnp.where(second == start + 1, phase, -phase)

        pivot = work[start, start + 1]
        pivot_magnitude = jnp.abs(pivot)
        pivot_is_zero = pivot_magnitude == 0
        rank_deficient = rank_deficient | pivot_is_zero
        safe_pivot = jnp.where(pivot_is_zero, jnp.ones_like(pivot), pivot)
        safe_magnitude = jnp.where(
            pivot_is_zero, jnp.ones_like(pivot_magnitude), pivot_magnitude
        )
        phase = phase * safe_pivot / safe_magnitude
        log_magnitude = log_magnitude + jnp.log(safe_magnitude)

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
            work = work.at[start + 2 :, start + 2 :].set(trailing + correction)

    value = phase * jnp.exp(log_magnitude)
    return jnp.where(rank_deficient, jnp.zeros_like(value), value)


@jax.custom_jvp
def _trusted_pfaffian(matrix) -> jax.Array:
    """JIT-compatible Pfaffian primitive for already validated skew matrices."""
    return _pfaffian_elimination(matrix)


@_trusted_pfaffian.defjvp
def _trusted_pfaffian_jvp(primals, tangents):
    (matrix,), (tangent,) = primals, tangents
    value = _pfaffian_elimination(matrix)
    if matrix.shape[0] == 0:
        return value, jnp.zeros_like(value)

    derivative = jnp.zeros_like(value)
    for first in range(matrix.shape[0]):
        for second in range(first + 1, matrix.shape[0]):
            retained = tuple(
                index
                for index in range(matrix.shape[0])
                if index not in (first, second)
            )
            retained_indices = jnp.asarray(retained, dtype=jnp.int32)
            minor = matrix[
                retained_indices[:, None],
                retained_indices[None, :],
            ]
            sign = -1 if (first + second + 1) % 2 else 1
            derivative = (
                derivative
                + sign * _pfaffian_elimination(minor) * tangent[first, second]
            )
    return value, derivative


def pfaffian(matrix) -> jax.Array:
    """Validate and return the complex Pfaffian of an even skew matrix.

    This checked public boundary validates numerical skew symmetry in eager and
    compiled calls. Internal callers with a construction-level skew guarantee
    use ``_trusted_pfaffian`` to avoid host callbacks.
    """
    return _trusted_pfaffian(_checked_even_skew_matrix(matrix))


def bordered_pfaffian(matrix, border) -> jax.Array:
    """Pfaffian after appending ``border`` as the final column."""
    matrix_array = _checked_skew_matrix(matrix, even=False)
    border_array = jnp.asarray(border)
    if border_array.shape != (matrix_array.shape[0],):
        raise ValueError("border must have one entry per matrix row")
    return _trusted_bordered_pfaffian(matrix_array, border_array)


def _trusted_bordered_pfaffian(matrix, border) -> jax.Array:
    """JIT-compatible bordered primitive for a trusted odd skew matrix."""
    matrix_array = jnp.asarray(matrix)
    border_array = jnp.asarray(border)
    dtype = jnp.result_type(matrix_array, border_array)
    augmented = jnp.zeros(
        (matrix_array.shape[0] + 1, matrix_array.shape[0] + 1), dtype=dtype
    )
    augmented = augmented.at[:-1, :-1].set(matrix_array)
    augmented = augmented.at[:-1, -1].set(border_array)
    augmented = augmented.at[-1, :-1].set(-border_array)
    return _trusted_pfaffian(augmented)
