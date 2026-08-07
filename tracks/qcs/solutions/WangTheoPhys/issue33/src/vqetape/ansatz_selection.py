"""Deterministic gradient and contraction-aware ansatz selection."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal

from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
)
from vqetape.ansatz_cost import (
    AnsatzCostDelta,
    AnsatzCostWeights,
    candidate_cost_delta,
    contraction_aware_score,
)
from vqetape.ansatz_signals import AnsatzSignal

AnsatzSelectionPolicy = Literal[
    "gradient-only",
    "contraction-aware",
]


@dataclass(frozen=True)
class AnsatzCandidateScore:
    """Complete audited score for one operator-pool candidate."""

    operator: AnsatzOperator
    signal: AnsatzSignal
    cost: AnsatzCostDelta
    gradient_score: float
    contraction_score: float
    selection_score: float
    eligible: bool
    exclusion_reason: str | None
    rank: int
    selected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator.to_dict(),
            "signal": self.signal.to_dict(),
            "cost": self.cost.to_dict(),
            "gradient_score": self.gradient_score,
            "contraction_score": self.contraction_score,
            "selection_score": self.selection_score,
            "eligible": self.eligible,
            "exclusion_reason": self.exclusion_reason,
            "rank": self.rank,
            "selected": self.selected,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzCandidateScore:
        values = dict(payload)
        values["operator"] = AnsatzOperator.from_dict(
            values["operator"]
        )
        values["signal"] = AnsatzSignal.from_dict(
            values["signal"]
        )
        values["cost"] = AnsatzCostDelta.from_dict(
            values["cost"]
        )
        return cls(**values)


def operators_commute(
    left: AnsatzOperator,
    right: AnsatzOperator,
) -> bool:
    """Return whether the two supported Pauli generators commute."""

    def paulis(
        operator: AnsatzOperator,
    ) -> dict[int, str]:
        if operator.kind == "rx":
            return {operator.wire: "X"}
        left_pauli, right_pauli = {
            "rzz": ("Z", "Z"),
            "yz": ("Y", "Z"),
            "zy": ("Z", "Y"),
        }[operator.kind]
        return {
            operator.wire: left_pauli,
            operator.wire + 1: right_pauli,
        }

    left_paulis = paulis(left)
    right_paulis = paulis(right)
    anticommuting_sites = sum(
        left_paulis[wire] != right_paulis[wire]
        for wire in left_paulis.keys()
        & right_paulis.keys()
    )
    return anticommuting_sites % 2 == 0


def redundant_append(
    structure: AnsatzStructure,
    candidate: AnsatzOperator,
) -> bool:
    """Detect an append that exactly fuses into an existing gate."""

    for existing in reversed(structure.operators):
        if existing == candidate:
            return True
        if not operators_commute(existing, candidate):
            return False
    return False


def rank_ansatz_candidates(
    structure: AnsatzStructure,
    signals: tuple[AnsatzSignal, ...],
    policy: AnsatzSelectionPolicy,
    *,
    weights: AnsatzCostWeights | None = None,
) -> tuple[AnsatzCandidateScore, ...]:
    """Score the full pool and return deterministic rank order."""

    if policy not in (
        "gradient-only",
        "contraction-aware",
    ):
        raise ValueError(
            f"unsupported ansatz selection policy: {policy}"
        )
    if not signals:
        raise ValueError("candidate signal pool is empty")
    if len({item.operator for item in signals}) != len(
        signals
    ):
        raise ValueError(
            "candidate signal pool contains duplicates"
        )
    selected_weights = weights or AnsatzCostWeights()
    unranked = []
    for signal in signals:
        if (
            signal.normalized_signal < 0
            or not isfinite(signal.normalized_signal)
        ):
            raise ValueError(
                f"invalid signal for {signal.operator.label}"
            )
        cost = candidate_cost_delta(
            structure,
            signal.operator,
        )
        contraction_score = contraction_aware_score(
            signal,
            cost,
            selected_weights,
        )
        selection_score = (
            signal.normalized_signal
            if policy == "gradient-only"
            else contraction_score
        )
        eligible = not redundant_append(
            structure,
            signal.operator,
        )
        unranked.append(
            (
                signal.operator.label,
                signal,
                cost,
                contraction_score,
                selection_score,
                eligible,
            )
        )
    if not any(item[5] for item in unranked):
        raise ValueError(
            "all ansatz candidates are algebraically redundant"
        )
    ordered = sorted(
        unranked,
        key=lambda item: (
            not item[5],
            -item[4],
            item[0],
        ),
    )
    return tuple(
        AnsatzCandidateScore(
            operator=signal.operator,
            signal=signal,
            cost=cost,
            gradient_score=signal.normalized_signal,
            contraction_score=contraction_score,
            selection_score=selection_score,
            eligible=eligible,
            exclusion_reason=(
                None
                if eligible
                else "fuses with a commuting prior gate"
            ),
            rank=rank,
            selected=rank == 1 and eligible,
        )
        for rank, (
            _,
            signal,
            cost,
            contraction_score,
            selection_score,
            eligible,
        ) in enumerate(ordered, start=1)
    )
