from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
    fixed_rzz_rx_structure,
)
from vqetape.ansatz_cost import AnsatzCostWeights
from vqetape.ansatz_selection import (
    operators_commute,
    rank_ansatz_candidates,
    redundant_append,
)
from vqetape.ansatz_signals import AnsatzSignal


def _signal(
    operator: AnsatzOperator,
    score: float,
) -> AnsatzSignal:
    return AnsatzSignal(
        operator=operator,
        gradient=score**0.5,
        metric=1.0,
        normalized_signal=score,
    )


def test_policies_agree_when_candidate_costs_are_equal():
    structure = AnsatzStructure(3, ())
    signals = (
        _signal(AnsatzOperator("rx", 0), 0.5),
        _signal(AnsatzOperator("rx", 1), 0.7),
    )

    gradient = rank_ansatz_candidates(
        structure,
        signals,
        "gradient-only",
    )
    contraction = rank_ansatz_candidates(
        structure,
        signals,
        "contraction-aware",
    )

    assert gradient[0].operator == AnsatzOperator("rx", 1)
    assert contraction[0].operator == gradient[0].operator


def test_contraction_policy_can_reject_highest_gradient():
    structure = (
        fixed_rzz_rx_structure(4, 1)
        .append(AnsatzOperator("rzz", 0))
        .append(AnsatzOperator("rx", 0))
    )
    signals = (
        _signal(AnsatzOperator("rzz", 0), 1.1),
        _signal(AnsatzOperator("rx", 1), 1.0),
    )
    weights = AnsatzCostWeights(
        boundary=1.0,
        compile=0.0,
        warm=0.0,
        memory=1.0,
    )

    gradient = rank_ansatz_candidates(
        structure,
        signals,
        "gradient-only",
        weights=weights,
    )
    contraction = rank_ansatz_candidates(
        structure,
        signals,
        "contraction-aware",
        weights=weights,
    )

    assert gradient[0].operator.kind == "rzz"
    assert contraction[0].operator.kind == "rx"
    assert contraction[0].selected
    assert all(
        row.selected == (row.rank == 1)
        for row in contraction
    )


def test_repeated_operator_remains_a_legal_candidate():
    repeated = AnsatzOperator("rx", 0)
    structure = AnsatzStructure(
        3,
        (
            repeated,
            AnsatzOperator("rzz", 0),
        ),
    )
    ranked = rank_ansatz_candidates(
        structure,
        (_signal(repeated, 1.0),),
        "contraction-aware",
    )

    assert ranked[0].operator == repeated
    assert ranked[0].eligible
    assert structure.append(repeated).operators == (
        repeated,
        AnsatzOperator("rzz", 0),
        repeated,
    )


def test_ties_resolve_by_operator_label():
    structure = AnsatzStructure(3, ())
    ranked = rank_ansatz_candidates(
        structure,
        (
            _signal(AnsatzOperator("rx", 2), 1.0),
            _signal(AnsatzOperator("rx", 0), 1.0),
        ),
        "gradient-only",
    )

    assert [row.operator.label for row in ranked] == [
        "rx-0",
        "rx-2",
    ]


def test_commuting_tail_marks_exactly_redundant_append():
    rx0 = AnsatzOperator("rx", 0)
    assert operators_commute(
        rx0,
        AnsatzOperator("rx", 2),
    )
    assert not operators_commute(
        rx0,
        AnsatzOperator("rzz", 0),
    )
    assert redundant_append(
        AnsatzStructure(
            3,
            (rx0, AnsatzOperator("rx", 2)),
        ),
        rx0,
    )
    assert not redundant_append(
        AnsatzStructure(
            3,
            (rx0, AnsatzOperator("rzz", 0)),
        ),
        rx0,
    )
