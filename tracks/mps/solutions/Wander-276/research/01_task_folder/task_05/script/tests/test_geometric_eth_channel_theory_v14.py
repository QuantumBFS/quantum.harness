"""Contracts for the v14 effective-channel theorem and executable audit."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[4]
SPEC = REPO / "docs/plans/2026-08-17-geometric-eth-theorem-specification.md"
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    SCRIPT_ROOT
    / "output/geometric_eth_theory_v14/channel_theory_v14.json"
)
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from derive_geometric_eth_channel_theory_v14 import (
    build_payload,
    canonical_quantize_payload,
    canonical_scientific_json,
    write_payload,
)
from lgeth.geometric_eth_channel_theory import (
    commutant_dimension,
    complex_second_moments,
    effective_channel_number,
    normalize_weights,
    predicted_cumulant_scale,
    run_theory_audit,
    standardized_complex_fourth_cumulant,
)


def test_theorem_specification_contract() -> None:
    text = SPEC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    lowered = normalized.lower()

    for token in (
        r"Y_\alpha",
        r"\mathbb E Y_\alpha=0",
        r"w_\alpha",
        r"Z=\sum_\alpha w_\alpha Y_\alpha",
        r"C_\alpha",
        r"P_\alpha",
        r"\kappa_k(Z)=\sum_\alpha w_\alpha^k\kappa_k(Y_\alpha)",
        r"N_{\mathrm{eff}}=\frac{(\sum_\alpha w_\alpha^2)^2}{\sum_\alpha w_\alpha^4}",
        "Burnside",
        r"\mathcal A_X",
    ):
        assert token in normalized

    for phrase in (
        "independent centered complex channels",
        "ordinary covariance",
        "pseudocovariance",
        "finite fourth moments",
        "variance normalization",
        "weighted cumulant additivity",
        "irreducibility is necessary",
        "does not imply gaussianity or eth",
        "correlated channels",
        "heavy-tailed channels without fourth moments",
        "growing single-channel dominance",
        "symmetry-unresolved blocks",
        "nonstationary tangent ensembles",
        "closing external gap",
        "10 significant decimal digits",
        "serialization and signature only",
        "does not alter the raw monte carlo calculation",
        "non-finite values are rejected",
    ):
        assert phrase in lowered

    assert "assumptions" in lowered
    assert "conclusion" in lowered
    assert "failure branches" in lowered


@pytest.mark.parametrize("count", (2, 8, 32))
def test_equal_weight_effective_channels(count: int) -> None:
    weights = normalize_weights(np.ones(count))

    assert np.sum(weights**2) == pytest.approx(1.0)
    assert effective_channel_number(weights) == pytest.approx(float(count))
    assert np.sum(weights**4) == pytest.approx(1.0 / count)


def test_effective_channel_number_is_scale_invariant() -> None:
    weights = np.array([0.3, -0.7, 1.2, 0.4])
    assert effective_channel_number(19.0 * weights) == pytest.approx(
        effective_channel_number(weights)
    )


@pytest.mark.parametrize(
    "bad",
    (
        np.array([]),
        np.array([0.0, 0.0]),
        np.array([1.0, np.nan]),
        np.ones((2, 2)),
    ),
)
def test_invalid_weights_fail_closed(bad: np.ndarray) -> None:
    with pytest.raises(ValueError):
        normalize_weights(bad)
    with pytest.raises(ValueError):
        effective_channel_number(bad)


def test_predicted_cumulant_scale_keeps_channel_dependence() -> None:
    weights = np.array([0.25, 0.5, 1.0])
    channel_kappa4 = np.array([3.0, -2.0, 7.0])
    expected = np.sum(weights**4 * channel_kappa4) / np.sum(weights**2) ** 2

    assert predicted_cumulant_scale(weights, channel_kappa4) == pytest.approx(
        expected
    )
    equal = normalize_weights(np.ones(8))
    assert predicted_cumulant_scale(equal, np.full(8, 6.0)) == pytest.approx(
        6.0 / 8.0
    )

    with pytest.raises(ValueError, match="same shape"):
        predicted_cumulant_scale(weights, channel_kappa4[:2])
    with pytest.raises(ValueError, match="finite"):
        predicted_cumulant_scale(weights, np.array([1.0, np.inf, 2.0]))


def test_complex_second_moments_retain_pseudocovariance() -> None:
    # Repeating this four-row panel keeps its sample mean exactly zero.  The
    # two coordinates are real, perfectly correlated, and therefore have
    # equal ordinary covariance and pseudocovariance.
    samples = np.tile(
        np.array([[1.0, 2.0], [-1.0, -2.0], [1.0, 2.0], [-1.0, -2.0]]),
        (16, 1),
    ).astype(complex)
    covariance, pseudocovariance = complex_second_moments(samples)

    expected = np.array([[1.0, 2.0], [2.0, 4.0]], dtype=complex)
    assert np.allclose(covariance, expected)
    assert np.allclose(pseudocovariance, expected)


def test_complete_standardized_complex_fourth_cumulant() -> None:
    proper_unit_phases = np.tile(
        np.array([1.0, 1.0j, -1.0, -1.0j]), 64
    )
    # E|z|^4 - 2 E|z|^2^2 - |E z^2|^2 = 1 - 2 - 0.
    assert standardized_complex_fourth_cumulant(proper_unit_phases) == pytest.approx(
        -1.0
    )


def test_commutant_dimensions_resolve_irreducibility_only() -> None:
    identity = np.eye(2, dtype=complex)
    sx = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    sz = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)

    assert commutant_dimension([sx, sz], tolerance=1e-12) == 1
    assert commutant_dimension([sz], tolerance=1e-12) == 2
    assert commutant_dimension([identity], tolerance=1e-12) == 4

    with pytest.raises(ValueError, match="square"):
        commutant_dimension([np.ones((2, 3))], tolerance=1e-12)
    with pytest.raises(ValueError, match="common shape"):
        commutant_dimension([identity, np.eye(3)], tolerance=1e-12)
    with pytest.raises(ValueError, match="nonempty"):
        commutant_dimension([], tolerance=1e-12)


def test_fixed_prediction_monte_carlo_oracle() -> None:
    audit = run_theory_audit()

    assert audit["registered_channel_counts"] == [4, 8, 16, 32, 64]
    assert audit["seed"] == 20260817
    assert audit["matrix_draws"] == 50_000
    assert audit["matrix_shape"] == [2, 2]
    assert audit["block_count"] == 25
    assert audit["maximum_relative_error_threshold"] == pytest.approx(0.08)
    assert audit["maximum_relative_error"] <= 0.08
    assert audit["all_checks_pass"] is True
    assert all(audit["checks"].values())
    assert "fitted_exponent" not in audit
    assert audit["no_exponent_fit"] is True
    assert set(audit["weight_profiles"]) == {"equal", "linear_unequal"}

    cases = audit["monte_carlo_cases"]
    assert len(cases) == 10
    for case in cases:
        assert case["channel_count"] in audit["registered_channel_counts"]
        assert case["effective_channel_number"] > 0.0
        assert case["predicted_standardized_fourth_cumulant"] > 0.0
        assert case["relative_error"] <= 0.08
        assert case["block_standard_error"] >= 0.0
        assert len(case["ordinary_covariance"]["real"]) == 4
        assert len(case["pseudocovariance"]["real"]) == 4
        assert case["empirical_mean_norm"] < 0.03

    claim_boundary = " ".join(audit["claim_boundary"]).lower()
    assert "irreducibility" in claim_boundary
    assert "does not imply eth" in claim_boundary
    assert "finite-channel" in claim_boundary
    assert "universal" in claim_boundary


def test_runner_payload_is_deterministic_and_self_authenticating(
    tmp_path: Path,
) -> None:
    first = build_payload()
    second = build_payload()
    assert canonical_scientific_json(first) == canonical_scientific_json(second)
    assert first["version"] == "v14"
    assert first["schema"] == "geometric_eth_channel_theory_v14"
    assert first["all_checks_pass"] is True

    unsigned = deepcopy(first)
    digest = unsigned.pop("scientific_payload_sha256")
    assert digest == hashlib.sha256(
        canonical_scientific_json(unsigned).encode("utf-8")
    ).hexdigest()

    output = tmp_path / "channel_theory_v14.json"
    write_payload(first, output)
    assert json.loads(output.read_text(encoding="utf-8")) == first


def test_canonical_quantization_is_recursive_explicit_and_finite() -> None:
    left = {
        "scalar": 1.23456789012344,
        "nested": [9.87654321098744e-19, {"zero": -0.0}],
        "integer": 17,
        "flag": True,
    }
    right = {
        "scalar": 1.23456789012346,
        "nested": [9.87654321098746e-19, {"zero": 0.0}],
        "integer": 17,
        "flag": True,
    }

    quantized_left = canonical_quantize_payload(left)
    quantized_right = canonical_quantize_payload(right)
    assert quantized_left == quantized_right
    assert quantized_left["scalar"] == 1.23456789
    assert quantized_left["nested"][0] == 9.876543211e-19
    assert quantized_left["nested"][1]["zero"] == 0.0
    assert isinstance(quantized_left["integer"], int)
    assert isinstance(quantized_left["flag"], bool)

    for nonfinite in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="non-finite"):
            canonical_quantize_payload({"nested": [nonfinite]})


def test_cold_start_bytes_and_hash_are_blas_thread_stable(
    tmp_path: Path,
) -> None:
    command = (
        "import sys; from pathlib import Path; "
        "from derive_geometric_eth_channel_theory_v14 import "
        "build_payload, write_payload; "
        "write_payload(build_payload(), Path(sys.argv[1]))"
    )
    outputs = []
    alternate_python = shutil.which("python3") or sys.executable
    interpreters_and_threads = (
        (sys.executable, "1"),
        (alternate_python, "3"),
    )
    for index, (interpreter, threads) in enumerate(interpreters_and_threads):
        output = tmp_path / f"cold_start_{index}.json"
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONPATH": str(SCRIPT_ROOT),
                "PYTHONHASHSEED": str(700 + index),
                "OPENBLAS_NUM_THREADS": threads,
                "OMP_NUM_THREADS": threads,
                "MKL_NUM_THREADS": threads,
                "VECLIB_MAXIMUM_THREADS": threads,
                "NUMEXPR_NUM_THREADS": threads,
            }
        )
        subprocess.run(
            [interpreter, "-c", command, str(output)],
            cwd=REPO,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(output.read_bytes())

    assert outputs[0] == outputs[1]
    first = json.loads(outputs[0])
    second = json.loads(outputs[1])
    assert first["scientific_payload_sha256"] == second["scientific_payload_sha256"]
    assert hashlib.sha256(outputs[0]).hexdigest() == hashlib.sha256(
        outputs[1]
    ).hexdigest()


def test_checked_in_audit_matches_runner() -> None:
    expected = build_payload()
    observed = json.loads(OUTPUT.read_text(encoding="utf-8"))

    assert observed == expected
