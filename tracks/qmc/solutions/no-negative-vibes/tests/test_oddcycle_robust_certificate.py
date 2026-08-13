import importlib


def test_robust_certificate_replays_every_exact_publication_gate():
    certificate = importlib.import_module(
        "oracle.oddcycle_robust_certificate"
    )

    result = certificate.robust_certificate_summary()

    assert result["status"] == "all-exact-gates-passed"
    assert result["candidate"] == {
        "cell_id": "cell-4321",
        "dimension": 5,
        "points": [
            ["1/2000", "11/10", "9/10"],
            ["49/40", "11/10", "9/10"],
        ],
        "alphabet": (
            "B(1/2000,11/10,9/10)",
            "B(1/2000,11/10,9/10)^T",
            "B(49/40,11/10,9/10)",
            "B(49/40,11/10,9/10)^T",
        ),
    }
    assert result["gates"] == {
        "arbitrary_word_determinant_positive": True,
        "no_common_strict_quadratic_metric": True,
        "hermitian_interacting_positive_field_model": True,
    }
    assert result["theorem"]["metric_denominator"] == 1_000_000_000
    assert result["theorem"]["split_inertias_passed"] == 4
    assert result["theorem"]["transition_gaps_passed"] == 16
    assert result["theorem"]["future_transitions_passed"] == 16
    assert result["novelty"]["projection_denominator"] == 100_000_000
    assert result["novelty"]["normalization_trace"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert result["novelty"]["positive_multipliers"] == 4
    assert result["physical"] == {
        "fock_dimension": 32,
        "shift": 37,
        "minimum_row_margin": "7949/10000",
        "field_coefficients": (
            "37/41",
            "1/41",
            "1/41",
            "1/41",
            "1/41",
        ),
        "real_log_letters": 4,
        "non_gaussian_entry_count": 58,
        "first_normalized_non_gaussian_entry": (0, 0, "4/41"),
    }
    assert len(result["exact_certificate_sha256"]) == 64
