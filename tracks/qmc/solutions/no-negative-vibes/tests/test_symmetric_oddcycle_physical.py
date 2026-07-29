from oracle.symmetric_oddcycle_physical import (
    exact_physical_transfer_certificate,
)


def test_fixed_candidate_has_exact_interacting_sign_free_transfer():
    result = exact_physical_transfer_certificate()

    assert result["status"] == "exact-sign-free-physical-transfer"
    assert result["fock_dimension"] == 32
    assert result["c"] == 19
    assert result["strict_diagonal_dominance"] == {
        "maximum_requirement": 18,
        "maximizing_rows_zero_based": (19, 23, 29, 30),
        "minimum_row_margin": 1,
        "conclusion": "T_c is real symmetric positive definite",
    }
    assert result["principal_real_log_gate"] == {
        "determinant": 8,
        "characteristic_coefficients": (1, -2, 1, -7, 16, -8),
        "p_minus_t_coefficients": (-1, -2, -1, -7, -16, -8),
        "spectrum_avoids_nonpositive_real_axis": True,
    }
    assert result["normalized_auxiliary_fields"]["coefficients"] == (
        "19/21",
        "1/21",
        "1/21",
    )
    assert result["trace_replay"]["multiplicative"]
    assert result["trace_replay"]["fock_trace"] == (
        result["trace_replay"]["determinant"]
    )
    assert result["non_gaussian_gate"]["nonzero_entry_count"] == 58
    assert result["non_gaussian_gate"]["first_nonzero_entry"] == (0, 0, 42)
