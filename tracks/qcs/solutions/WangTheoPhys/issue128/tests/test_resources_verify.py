import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from trottercert.anticommuting import sqrt_fraction_upper
from trottercert.resources import (
    ceil_nth_root_fraction,
    four_matching_resources,
    required_steps,
    symmetric_group_exponentials,
    three_l_path_resources,
)
from trottercert.verify import _verify_d4_sidecar, verify_certificate


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


def _write_synthetic_d4_sidecar(
    root: Path,
    payload: dict[str, object],
    *,
    digest: str | None = None,
) -> tuple[Path, dict[str, object]]:
    sidecar = root / "d4.json"
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    sidecar.write_bytes(raw)
    main = root / "main.json"
    main.write_text("{}")
    metadata = {
        "path": sidecar.name,
        "sha256": (
            hashlib.sha256(raw).hexdigest()
            if digest is None
            else digest
        ),
        "max_group_size": 3,
        "cell_norm_upper": payload["cell_bound"],
    }
    return main, {"d4_certificate": metadata}


def _synthetic_d4_payload() -> dict[str, object]:
    bound = sqrt_fraction_upper(Fraction(3))
    return {
        "schema_version": 1,
        "coefficient_denominator": 1,
        "terms": [
            [0, 1, 1, 1],
            [1, 0, 1, 1],
            [1, 1, 1, 1],
        ],
        "sqrt_denominator": bound.denominator,
        "groups": [
            [[0, 1, 2], bound.numerator],
        ],
        "cell_bound": [bound.numerator, bound.denominator],
    }


def test_d4_sidecar_rejects_coverage_corruption(tmp_path) -> None:
    payload = _synthetic_d4_payload()
    payload["groups"][0][0].pop()
    main, candidate = _write_synthetic_d4_sidecar(tmp_path, payload)
    with pytest.raises(ValueError, match="coverage"):
        _verify_d4_sidecar(main, candidate)


def test_d4_sidecar_rejects_commuting_group(tmp_path) -> None:
    payload = _synthetic_d4_payload()
    payload["terms"][2][:2] = [2, 0]
    main, candidate = _write_synthetic_d4_sidecar(tmp_path, payload)
    with pytest.raises(ValueError, match="anticommute"):
        _verify_d4_sidecar(main, candidate)


def test_d4_sidecar_rejects_reduced_group_bound(tmp_path) -> None:
    payload = _synthetic_d4_payload()
    payload["groups"][0][1] -= 1
    main, candidate = _write_synthetic_d4_sidecar(tmp_path, payload)
    with pytest.raises(ValueError, match="group bound"):
        _verify_d4_sidecar(main, candidate)


def test_d4_sidecar_rejects_digest_corruption(tmp_path) -> None:
    payload = _synthetic_d4_payload()
    main, candidate = _write_synthetic_d4_sidecar(
        tmp_path,
        payload,
        digest="0" * 64,
    )
    with pytest.raises(ValueError, match="sidecar digest"):
        _verify_d4_sidecar(main, candidate)


def test_v3_deliverable_fast_verifies() -> None:
    root = Path(__file__).resolve().parents[1]
    result = verify_certificate(
        root / "certificates" / "issue128-certificate.json"
    )
    assert result["global_twofold_target_met"]
    assert result["global_fourfold_target_met"]
    assert result["candidate_steps"] == 97
    assert result["published_steps"] == 393
    assert result["d4_term_count"] == 75_324
    assert result["d4_group_count"] == 7_576
