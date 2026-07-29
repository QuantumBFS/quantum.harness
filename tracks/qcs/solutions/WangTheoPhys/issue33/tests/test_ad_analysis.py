from vqetape.ad_analysis import (
    analyze_contraction_steps,
    analyze_spatial_transfer,
    reverse_einsum_equation,
)
from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spec import TFIMVQESpec
from vqetape.tn_program import ContractionStep


def test_reverse_equations_for_matrix_product():
    equation = "ab,bc->ac"

    assert reverse_einsum_equation(equation, 0) == "ac,bc->ab"
    assert reverse_einsum_equation(equation, 1) == "ac,ab->bc"


def test_reverse_equation_for_scalar_inner_product():
    equation = "ab,ab->"

    assert reverse_einsum_equation(equation, 0) == ",ab->ab"
    assert reverse_einsum_equation(equation, 1) == ",ab->ab"


def test_differentiated_contraction_cost_is_accounted():
    input_shapes = ((2, 3), (3, 4), (2, 4))
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

    cost, reverse = analyze_contraction_steps(
        input_shapes,
        steps,
    )

    assert cost.forward_flops > 0
    assert cost.backward_flops > cost.forward_flops
    assert cost.residual_elements == 6 + 12 + 8 + 8
    assert (
        cost.peak_live_residual_elements
        == cost.residual_elements
    )
    assert cost.forward_contractions == 2
    assert cost.backward_contractions == 4
    assert len(reverse) == 2
    assert tuple(len(group) for group in reverse) == (2, 2)
    assert cost.total_flops == (
        cost.forward_flops + cost.backward_flops
    )
    assert cost.traffic_elements > 0


def test_spatial_ad_cost_multiplies_repeated_blocks():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    one = analyze_spatial_transfer(
        plan_spatial_transfer(
            spec,
            "greedy",
            block_width=1,
        )
    )
    two = analyze_spatial_transfer(
        plan_spatial_transfer(
            spec,
            "greedy",
            block_width=2,
        )
    )

    assert one.bulk_block_count == 6
    assert two.bulk_block_count == 3
    assert one.total_forward_flops > 0
    assert one.total_backward_flops > 0
    assert one.total_traffic_bytes > 0
    assert one.static_score > 0
    assert one.total_forward_flops == (
        one.first.forward_flops
        + 6 * one.bulk.forward_flops
        + one.last.forward_flops
    )
    assert one.to_dict()["roles"]["bulk"] is not None
