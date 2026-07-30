from oracle.oddcycle_pair_physical import exact_pair_physical_certificate


def test_leading_pair_has_a_positive_field_hermitian_interacting_target():
    result = exact_pair_physical_certificate()

    assert result["status"] == "exact-hermitian-interacting-transfer"
    assert result["fock_dimension"] == 32
    assert result["c"] == 37
    assert result["strict_diagonal_dominance"] == {
        "maximum_requirement": "36",
        "minimum_row_margin": "1",
        "conclusion": "T is real symmetric positive definite",
    }
    assert result["normalized_auxiliary_fields"]["all_coefficients_positive"]
    assert result["normalized_auxiliary_fields"]["coefficient_sum"] == "1"
    assert all(
        atom["real_log_exists"] for atom in result["auxiliary_atoms"]
    )
    assert result["normalized_auxiliary_fields"]["coefficients"] == (
        "37/41",
        "1/41",
        "1/41",
        "1/41",
        "1/41",
    )
    assert result["non_gaussian_gate"]["nonzero_entry_count"] == 58
    assert result["non_gaussian_gate"]["first_nonzero_entry"] == (
        0,
        0,
        "164",
    )
    assert result["sign_free_gate"].startswith("closed by")
