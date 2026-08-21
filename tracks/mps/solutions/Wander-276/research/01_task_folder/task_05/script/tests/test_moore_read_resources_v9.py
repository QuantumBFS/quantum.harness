"""Exact combinatorial resource estimates for Moore--Read production."""

from __future__ import annotations

from estimate_moore_read_resources_v9 import estimate_case


def test_n8_constraint_sparsity_is_exact() -> None:
    result = estimate_case(8)
    assert result["n_flux"] == 10
    assert result["basis_dimension"] == 24_310
    assert result["zero_mode_rank"] == 275
    assert result["constraint_rows"] == 200_200
    assert result["triples_per_row"] == 220
    assert result["constraint_nnz"] == 44_044_000
    assert result["classification"] == "registered_benchmark_candidate"


def test_n10_is_rejected_by_per_action_work_not_hidden_memory_guess() -> None:
    result = estimate_case(10)
    assert result["basis_dimension"] == 352_716
    assert result["zero_mode_rank"] == 546
    assert result["constraint_nnz"] == 1_668_086_784
    assert result["parent_action_nonzero_products"] == 1_834_895_462_400
    assert result["classification"] == "solver_reformulation_required"
    assert result["fits_final_sparse_memory"] is True
    assert result["fits_registered_action_budget"] is False
