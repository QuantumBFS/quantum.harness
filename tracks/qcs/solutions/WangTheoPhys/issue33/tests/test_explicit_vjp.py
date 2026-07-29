import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.explicit_vjp import (
    build_explicit_contraction_vjp,
)
from vqetape.tn_program import ContractionStep


@pytest.mark.parametrize(
    ("equation", "shapes", "output_shape"),
    [
        ("ab,bc->ac", ((2, 3), (3, 4)), (2, 4)),
        ("ab,ab->", ((2, 3), (2, 3)), ()),
    ],
)
def test_explicit_complex_vjp_matches_jax(
    equation,
    shapes,
    output_shape,
):
    step = ContractionStep(
        positions=(0, 0),
        einsum=equation,
        output_subscript=equation.split(
            "->",
            maxsplit=1,
        )[1],
        output_elements=int(np.prod(output_shape)),
    )
    values = tuple(
        (
            jnp.arange(
                np.prod(shape),
                dtype=jnp.float32,
            ).reshape(shape)
            + 1j
            * jnp.linspace(
                0.1,
                0.9,
                np.prod(shape),
                dtype=jnp.float32,
            ).reshape(shape)
        )
        for shape in shapes
    )
    explicit = build_explicit_contraction_vjp(
        shapes,
        (step,),
    )
    reference = lambda *xs: jnp.einsum(
        equation,
        *xs,
        optimize=True,
    )
    output = explicit(*values)
    cotangent = jnp.full_like(output, 0.7 + 0.2j)
    actual_value, actual_pullback = jax.vjp(
        explicit,
        *values,
    )
    expected_value, expected_pullback = jax.vjp(
        reference,
        *values,
    )

    np.testing.assert_allclose(
        output,
        expected_value,
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        actual_value,
        expected_value,
        rtol=1e-5,
        atol=1e-5,
    )
    for actual, expected in zip(
        actual_pullback(cotangent),
        expected_pullback(cotangent),
        strict=True,
    ):
        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-5,
            atol=1e-5,
        )


def test_explicit_vjp_recomputes_a_multistep_tree():
    shapes = ((2, 3), (3, 4), (2, 4))
    steps = (
        ContractionStep(
            positions=(1, 0),
            einsum="bc,ab->ac",
            output_subscript="ac",
            output_elements=8,
        ),
        ContractionStep(
            positions=(1, 0),
            einsum="ac,ac->",
            output_subscript="",
            output_elements=1,
        ),
    )
    values = tuple(
        jnp.linspace(
            0.1,
            0.9,
            np.prod(shape),
            dtype=jnp.float32,
        ).reshape(shape)
        * (1 + 0.3j)
        for shape in shapes
    )
    explicit = build_explicit_contraction_vjp(
        shapes,
        steps,
    )

    def reference(a, b, c):
        intermediate = jnp.einsum(
            "bc,ab->ac",
            b,
            a,
        )
        return jnp.einsum(
            "ac,ac->",
            c,
            intermediate,
        )

    _, actual_pullback = jax.vjp(explicit, *values)
    _, expected_pullback = jax.vjp(reference, *values)
    cotangent = jnp.asarray(0.4 + 0.6j)

    for actual, expected in zip(
        actual_pullback(cotangent),
        expected_pullback(cotangent),
        strict=True,
    ):
        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-5,
            atol=1e-5,
        )
