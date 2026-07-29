import json
from fractions import Fraction
from pathlib import Path

from trottercert.resources import (
    ceil_nth_root_fraction,
    four_matching_resources,
    required_steps,
    symmetric_group_exponentials,
    three_l_path_resources,
)
from trottercert.verify import verify_certificate


def test_integer_roots_and_stage_merging() -> None:
    assert ceil_nth_root_fraction(Fraction(10), 2) == 4
    assert required_steps(Fraction(378), Fraction(1, 1000), 2) == 615
    assert symmetric_group_exponentials(4, 3) == 19


def test_resource_counts() -> None:
    baseline = four_matching_resources(144, 615)
    candidate = three_l_path_resources(144, 559)
    assert baseline.local_propagators == 265_752
    assert candidate.local_propagators == 107_376


def test_verifier_recomputes_and_rejects_corruption(tmp_path) -> None:
    certificate = {
        "schema_version": 1,
        "benchmark": {
            "normalization": "(XX+YY+ZZ)/4",
            "length": 12,
            "tolerance": [1, 1000],
        },
        "proof": {
            "reference_length": 6,
            "baseline_density": [21, 8],
            "candidate_density": [13, 6],
        },
        "claimed_resources": {
            "baseline_steps": 615,
            "candidate_steps": 559,
            "baseline_local_propagators": 265752,
            "candidate_local_propagators": 107376,
            "baseline_cnot_upper": 797256,
            "candidate_cnot_upper": 966384,
        },
    }
    path = tmp_path / "certificate.json"
    path.write_text(json.dumps(certificate))
    result = verify_certificate(path)
    assert result["twofold_local_target_met"]
    assert not result["twofold_compiled_cnot_target_met"]
    certificate["proof"]["candidate_density"] = [2, 1]
    path.write_text(json.dumps(certificate))
    try:
        verify_certificate(path)
    except ValueError as error:
        assert "candidate density" in str(error)
    else:
        raise AssertionError("corrupted certificate was accepted")


def test_v3_deliverable_fast_verifies() -> None:
    root = Path(__file__).resolve().parents[1]
    result = verify_certificate(
        root / "certificates" / "issue128-certificate.json"
    )
    assert result["global_twofold_target_met"]
    assert result["candidate_steps"] == 116
    assert result["published_steps"] == 393
