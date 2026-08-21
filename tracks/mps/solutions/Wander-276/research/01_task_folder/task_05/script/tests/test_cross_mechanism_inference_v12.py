"""Fail-closed cross-mechanism Geometric-ETH inference tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from analyze_cross_mechanism_geometric_eth_v12 import (
    REQUIRED_MODELS,
    build_cross_model_manifest,
    select_branch,
    validate_cross_model_contract,
)


def test_repository_artifacts_form_a_complete_opened_manifest() -> None:
    manifest = build_cross_model_manifest()
    assert set(manifest["models"]) == set(REQUIRED_MODELS)
    assert validate_cross_model_contract(manifest) == []
    assert manifest["prospective_cases_opened"] is False
    assert manifest["null_parameters_refit"] is False
    assert select_branch(manifest) == "domain_limited_geometric_eth"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda value: value["models"].pop("moore_read"), "missing models"),
        (
            lambda value: value.__setitem__("prospective_cases_opened", True),
            "prospective cases",
        ),
        (
            lambda value: value["models"]["lattice_susy"].__setitem__(
                "response_convention", "different_resolvent"
            ),
            "response convention",
        ),
        (
            lambda value: value.__setitem__("null_parameters_refit", True),
            "refitted null",
        ),
    ],
)
def test_contract_rejects_missing_unsealed_or_refitted_inputs(
    mutation,
    expected: str,
) -> None:
    manifest = build_cross_model_manifest()
    broken = deepcopy(manifest)
    mutation(broken)
    errors = validate_cross_model_contract(broken)
    assert errors
    assert any(expected in error for error in errors)


def test_branch_selection_refuses_invalid_manifest() -> None:
    manifest = build_cross_model_manifest()
    manifest["models"].pop("xcube")
    with pytest.raises(ValueError, match="missing models"):
        select_branch(manifest)
