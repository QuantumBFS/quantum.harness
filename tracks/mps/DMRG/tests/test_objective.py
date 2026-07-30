from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vmcrg_ref.objective import (
    ChainSet,
    ObjectiveProtocol,
    bar_free_energy_difference,
    bar_from_exact_two_state_ensembles,
    bridge_objective,
    chain_jackknife,
    hierarchical_paired_bootstrap,
    objective_protocol_from_mapping,
    paired_objective_difference,
)


def test_bar_recovers_two_state_free_energy() -> None:
    exact = np.log((1.0 + np.exp(-1.0)) / 2.0)
    result = bar_from_exact_two_state_ensembles(
        delta_energy=np.array([0.0, 1.0])
    )
    assert result.delta_log_z == pytest.approx(exact, abs=1e-10)
    assert result.classification == "IDENTIFIABLE"


def test_bar_recovers_constant_energy_shift() -> None:
    forward = np.ones((4, 16), dtype=np.float64)
    reverse = np.ones((4, 16), dtype=np.float64)
    result = bar_free_energy_difference(
        forward,
        reverse,
        root_tolerance=1e-12,
    )
    assert result.delta_log_z == pytest.approx(-1.0, abs=1e-12)
    assert result.overlap == pytest.approx(0.5, abs=1e-12)
    assert result.forward_kish_fraction == pytest.approx(1.0)
    assert result.reverse_kish_fraction == pytest.approx(1.0)


def test_failed_overlap_is_unidentifiable() -> None:
    result = bar_free_energy_difference(
        np.full(100, 1000.0),
        np.full(100, -1000.0),
        root_tolerance=1e-12,
    )
    assert result.classification == "UNIDENTIFIABLE_OVERLAP"
    assert result.overlap < 0.03


def test_chain_jackknife_uses_whole_chain_as_unit() -> None:
    values = np.array([[1.0, 1.0], [3.0, 3.0], [5.0, 5.0]])
    result = chain_jackknife(values)
    assert result["estimate"] == pytest.approx(3.0)
    assert result["standard_error"] == pytest.approx(np.sqrt(4.0 / 3.0))
    with pytest.raises(ValueError, match="chain axis"):
        chain_jackknife(values, chain_axis=1)


def _chain_set(
    value: float,
    lambda_value: float | None,
    stream: str,
    sample_hash: str,
) -> ChainSet:
    return ChainSet(
        energies=np.full((4, 16), value, dtype=np.float64),
        lambda_value=lambda_value,
        stream_hash=stream,
        sample_hash=sample_hash,
    )


def test_bridge_objective_uses_total_energy_then_normalizes_once() -> None:
    protocol = ObjectiveProtocol(
        lambda_ladder=(0.0, 0.5, 1.0),
        site_count=9,
        root_tolerance=1e-12,
    )
    result = bridge_objective(
        anchor=_chain_set(2.0, 0.0, "anchor-stream", "common-anchor"),
        bridges=(
            _chain_set(2.0, 0.5, "bridge-half", "half-samples"),
            _chain_set(2.0, 1.0, "bridge-one", "one-samples"),
        ),
        target_energies=_chain_set(2.0, None, "target-stream", "target-samples"),
        protocol=protocol,
    )
    assert result.classification == "IDENTIFIABLE"
    assert result.log_z_ratio_total == pytest.approx(-2.0, abs=1e-12)
    assert result.target_expectation_total == pytest.approx(2.0, abs=1e-12)
    assert result.objective_total == pytest.approx(0.0, abs=1e-12)
    assert result.objective_per_site == pytest.approx(0.0, abs=1e-12)


def test_paired_objective_requires_common_anchor_and_independent_bridges() -> None:
    protocol = ObjectiveProtocol(lambda_ladder=(0.0, 1.0), site_count=1)
    neural = bridge_objective(
        _chain_set(1.0, 0.0, "shared-anchor-stream", "shared-anchor"),
        (_chain_set(1.0, 1.0, "neural-bridge", "neural-samples"),),
        _chain_set(1.0, None, "neural-target", "neural-target-samples"),
        protocol,
    )
    linear = bridge_objective(
        _chain_set(2.0, 0.0, "shared-anchor-stream", "shared-anchor"),
        (_chain_set(2.0, 1.0, "linear-bridge", "linear-samples"),),
        _chain_set(2.0, None, "linear-target", "linear-target-samples"),
        protocol,
    )
    paired = paired_objective_difference(neural, linear)
    assert paired.classification == "IDENTIFIABLE"
    assert paired.delta_objective_total == pytest.approx(0.0, abs=1e-12)

    wrong_anchor = bridge_objective(
        _chain_set(2.0, 0.0, "other-anchor-stream", "other-anchor"),
        (_chain_set(2.0, 1.0, "other-bridge", "other-samples"),),
        _chain_set(2.0, None, "other-target", "other-target-samples"),
        protocol,
    )
    with pytest.raises(ValueError, match="common zero-bias anchor"):
        paired_objective_difference(neural, wrong_anchor)


def test_hierarchical_bootstrap_pairs_before_aggregation() -> None:
    linear = np.arange(20, dtype=np.float64).reshape(5, 4)
    neural = linear - 0.5
    report = hierarchical_paired_bootstrap(
        neural,
        linear,
        replicates=500,
        seed=2026072806,
    )
    assert report["paired_estimate"] == pytest.approx(-0.5)
    assert report["ci95_low"] == pytest.approx(-0.5)
    assert report["ci95_high"] == pytest.approx(-0.5)
    assert report["bootstrap_unit"] == ["seed_bundle", "independent_chain"]


def test_pilot_objective_config_freezes_estimator_and_overlap_gates() -> None:
    value = json.loads(Path("config/issue28_pilot_v1.json").read_text(encoding="ascii"))
    protocol = objective_protocol_from_mapping(value["objective"], site_count=225)
    assert protocol.lambda_ladder == (0.0, 0.125, 0.25, 0.5, 0.75, 0.875, 1.0)
    assert protocol.minimum_overlap == 0.03
    assert protocol.minimum_kish_fraction == 0.10
    assert protocol.maximum_closure_z == 3.0
    assert protocol.jackknife_unit == "independent_chain"
    assert protocol.unidentifiable_classification == "UNIDENTIFIABLE_OVERLAP"
    assert protocol.bootstrap_hierarchy == ("seed_bundle", "independent_chain")
    assert protocol.common_zero_bias_anchor is True
    assert protocol.independent_nonzero_streams is True


def test_objective_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.bridge_objective is bridge_objective
    assert vmcrg_ref.bar_free_energy_difference is bar_free_energy_difference
