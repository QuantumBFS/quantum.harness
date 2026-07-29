from __future__ import annotations

from lrtfim.fit_protocol import (
    PRIMARY_ALPHA,
    PRIMARY_K,
    fit_protocol_specs,
    regenerate_primary_sigma_fit,
    regenerate_sigma_fits,
)


def test_production_fit_protocol_is_locked() -> None:
    specs = fit_protocol_specs(l_max=256)
    tuples = {(item.num_exponentials, item.alpha, item.r_fit) for item in specs}

    assert PRIMARY_K == 24
    assert PRIMARY_ALPHA == 0.5
    assert (24, 0.5, 2048) in tuples
    assert {item.r_fit for item in specs if item.num_exponentials == 24 and item.alpha == 0.5} == {
        1024,
        2048,
        4096,
    }
    assert {item.num_exponentials for item in specs if item.alpha == 0.5 and item.r_fit == 2048} == {
        16,
        24,
        32,
    }
    assert {item.alpha for item in specs if item.num_exponentials == 24 and item.r_fit == 2048} == {
        0.25,
        0.5,
        1.0,
    }


def test_reduced_regeneration_records_hamiltonian_and_pending_physics() -> None:
    result = regenerate_sigma_fits(sigma=1.75, lengths=[4, 8], l_max=8)

    assert result["sigma"] == 1.75
    assert result["primary"]["r_fit"] == 64
    assert len(result["fits"]) == 7
    for record in result["fits"]:
        assert record["lambdas"]
        assert record["rates"]
        assert record["coefficients"]
        assert set(record["coupling_profiles"]) == {"4", "8"}
        assert record["min_rate_times_r_fit"] >= record["alpha"]
    assert result["K_comparison"]["hamiltonian"]["status"] == "complete"
    assert result["K_comparison"]["physics"] == {
        "status": "pending",
        "crossings": None,
        "gaps": None,
        "z_eff": None,
    }


def test_primary_only_regeneration_has_one_k24_fit() -> None:
    result = regenerate_primary_sigma_fit(
        sigma=1.75,
        lengths=[4],
        l_max=4,
    )

    assert result["primary"] == {
        "num_exponentials": 24,
        "alpha": 0.5,
        "r_fit": 32,
    }
    assert len(result["fits"]) == 1
    assert result["fits"][0]["num_exponentials"] == 24
    assert result["K_comparison"]["status"] == "deferred_representative_validation"
