from __future__ import annotations

import pytest

from src.result_schema import ResultSchemaError, validate_result_document
from src.verify_checkpoint import adopt_checkpoint_energy


def _valid_result() -> dict:
    return {
        "schema_version": 1,
        "status": "completed",
        "instance": "tiny",
        "method": "block2-dmrg",
        "sector": {"norb": 2, "nelec": 2, "ms2": 0, "spin": 0},
        "input": {"sha256": "a" * 64},
        "ordering": {"method": "fiedler", "permutation": [0, 1]},
        "stages": [
            {
                "bond_dimension": 8,
                "energy_hartree": -0.8,
                "discarded_weight": 1.0e-6,
            }
        ],
        "headline": {
            "kind": "finite_m_mps_expectation",
            "bond_dimension": 8,
            "energy_hartree": -0.8,
        },
    }


def test_result_schema_accepts_finite_mps_headline() -> None:
    result = _valid_result()

    assert validate_result_document(result) == result


def test_result_schema_rejects_extrapolated_headline() -> None:
    result = _valid_result()
    result["headline"]["kind"] = "discarded_weight_extrapolation"

    with pytest.raises(ResultSchemaError, match="finite-M MPS"):
        validate_result_document(result)


def test_result_schema_rejects_nonmonotone_stage_energy() -> None:
    result = _valid_result()
    result["stages"].append(
        {
            "bond_dimension": 16,
            "energy_hartree": -0.7,
            "discarded_weight": 5.0e-7,
        }
    )
    result["headline"]["bond_dimension"] = 16
    result["headline"]["energy_hartree"] = -0.7

    with pytest.raises(ResultSchemaError, match="non-increasing"):
        validate_result_document(result)


def test_checkpoint_energy_replaces_sweep_value_without_hiding_it() -> None:
    result = _valid_result()

    updated = adopt_checkpoint_energy(result, -0.79)

    assert updated["stages"][-1]["energy_hartree"] == -0.79
    assert updated["stages"][-1]["sweep_energy_hartree"] == -0.8
    assert updated["headline"]["energy_hartree"] == -0.79
