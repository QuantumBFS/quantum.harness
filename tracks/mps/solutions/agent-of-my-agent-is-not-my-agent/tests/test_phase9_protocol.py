from pathlib import Path

import pytest

from lrtfim.phase9_protocol import (
    GAMMA_NN,
    MEAN_FIELD_BENCHMARKS,
    MEAN_FIELD_SIZES,
    NN_SIZES,
    analyze_mean_field,
    analyze_nn,
    analyze_sigma18_z,
    build_mean_field_spec,
    build_nn_spec,
    build_sigma18_z_spec,
    published_gamma_comparison,
    state_diagnostics,
)


def _summary(
    length: int,
    gamma: float,
    sector: str,
    energy: float,
    *,
    r_xi: float | None = None,
    variance: float = 1.0e-12,
    discarded: float = 1.0e-9,
    sweeps: int = 12,
    max_sweeps: int = 30,
) -> dict:
    raw = {} if r_xi is None else {"r_xi": r_xi}
    return {
        "status": "success",
        "settings": {
            "length": length,
            "gamma": gamma,
            "sectors": [sector],
            "max_sweeps": max_sweeps,
        },
        "direct": {
            sector: {
                "energy": energy,
                "variance": variance,
                "discarded_weight": discarded,
                "reached_chi": 64,
                "sweeps": sweeps,
            }
        },
        "raw_observables": raw,
    }


def test_nn_spec_contains_all_eighteen_fixed_chi64_cells(tmp_path: Path):
    spec = build_nn_spec(tmp_path)

    assert len(spec["cells"]) == 18
    assert [
        (cell["L"], cell["Gamma"], cell["sector"], cell["chi"])
        for cell in spec["cells"]
    ] == [
        (
            length,
            gamma,
            sector,
            64,
        )
        for length in NN_SIZES
        for gamma in GAMMA_NN
        for sector in ("even", "odd")
    ]
    assert spec["settings"]["automatic_chi128"] is False
    assert spec["settings"]["adaptive_gamma"] is False


def test_mean_field_spec_excludes_unqualified_sigma_zero_four_cells(
    tmp_path: Path,
):
    fits = {
        2.0 / 3.0: Path("fit-two-thirds.json"),
    }
    spec = build_mean_field_spec(tmp_path, fits)

    assert len(spec["cells"]) == 8
    assert [
        (
            cell["sigma"],
            cell["L"],
            cell["Gamma"],
            cell["sector"],
            cell["chi"],
        )
        for cell in spec["cells"]
    ] == [
        (
            benchmark["sigma"],
            length,
            benchmark["Gamma"],
            sector,
            64,
        )
        for benchmark in MEAN_FIELD_BENCHMARKS
        if benchmark["sigma"] == 2.0 / 3.0
        for length in MEAN_FIELD_SIZES
        for sector in ("even", "odd")
    ]
    assert spec["settings"]["K"] == 24
    assert spec["settings"]["automatic_chi128"] is False
    assert spec["settings"]["reported_exponents"] == ["z"]
    assert spec["settings"]["excluded_benchmarks"] == [
        {
            "sigma": 0.4,
            "Gamma": 5.85,
            "reason": "K32_finite_ring_error_above_1_percent",
        }
    ]


def test_sigma18_spec_locks_ten_fixed_field_chi128_cells(tmp_path: Path):
    spec = build_sigma18_z_spec(tmp_path)

    assert len(spec["cells"]) == 10
    assert [
        (cell["L"], cell["Gamma"], cell["sector"], cell["K"], cell["chi"])
        for cell in spec["cells"]
    ] == [
        (length, 1.5288, sector, 24, 128)
        for length in (16, 32, 64, 96, 128)
        for sector in ("even", "odd")
    ]
    assert spec["settings"]["field_role"] == "external_published_benchmark"
    assert spec["settings"]["automatic_chi_increase"] is False


def test_state_diagnostics_flags_without_requesting_refinement():
    summary = _summary(
        64,
        1.0,
        "odd",
        -64.0,
        variance=1.0e-5,
        discarded=2.0e-7,
        sweeps=30,
    )

    result = state_diagnostics(summary, "odd")

    assert result["accepted"] is False
    assert set(result["flags"]) == {
        "relative_variance",
        "discarded_weight",
        "sweep_cap",
    }
    assert result["refinement_requested"] is False


def test_nn_analysis_recovers_exact_fixture_scaling_without_precision_claim():
    summaries = {}
    for length in NN_SIZES:
        for gamma, offset in zip(GAMMA_NN, (-0.02, 0.0, 0.02), strict=True):
            summaries[(length, gamma, "even")] = _summary(
                length,
                gamma,
                "even",
                -float(length),
                r_xi=0.5 + offset * length / 16.0,
            )
            summaries[(length, gamma, "odd")] = _summary(
                length,
                gamma,
                "odd",
                -float(length) + 1.0 / length,
            )

    result = analyze_nn(summaries)

    assert [row["Gamma_x"] for row in result["crossings"]] == pytest.approx(
        [1.0, 1.0]
    )
    assert result["crossing_resolution"] == 0.01
    assert result["gap_scaling"]["direct"]["exponent"] == pytest.approx(1.0)
    assert len(result["cell_diagnostics"]) == 18
    assert all(record["accepted"] for record in result["cell_diagnostics"])
    assert result["interpretation"] == "scaling_pipeline_validation_only"
    assert result["precision_z_claim"] is False


def test_mean_field_analysis_reports_only_z():
    for benchmark in MEAN_FIELD_BENCHMARKS:
        summaries = {}
        sigma = benchmark["sigma"]
        gamma = benchmark["Gamma"]
        target_z = benchmark["expected_z"]
        for length in MEAN_FIELD_SIZES:
            even = -2.0 * length
            summaries[(length, gamma, "even")] = _summary(
                length,
                gamma,
                "even",
                even,
            )
            summaries[(length, gamma, "odd")] = _summary(
                length,
                gamma,
                "odd",
                even + length ** (-target_z),
            )

        result = analyze_mean_field(summaries, sigma=sigma, gamma=gamma)

        assert result["gap_scaling"]["direct"]["exponent"] == pytest.approx(
            target_z
        )
        assert result["reported_exponents"] == ["z"]
        rendered = repr(result)
        assert "beta/nu" not in rendered
    assert "gamma/nu" not in rendered


def test_sigma18_analysis_uses_generalized_pairs_and_sensitivity_coordinates():
    summaries = {}
    target_z = 0.95
    for length in (16, 32, 64, 96, 128):
        even = -2.0 * length
        for sector, energy in (
            ("even", even),
            ("odd", even + length ** (-target_z)),
        ):
            summaries[(length, 1.5288, sector)] = _summary(
                length,
                1.5288,
                sector,
                energy,
            )

    result = analyze_sigma18_z(summaries)

    assert result["gap_scaling"]["z_eff"]["pairs"] == [
        "16_32",
        "32_64",
        "64_96",
        "96_128",
    ]
    assert result["gap_scaling"]["z_eff"]["values"] == pytest.approx(
        [target_z] * 4
    )
    assert result["gap_scaling"]["correction_sensitivity"]["power"][
        "estimate"
    ] == pytest.approx(target_z)
    assert result["gap_scaling"]["correction_sensitivity"]["log"][
        "estimate"
    ] == pytest.approx(target_z)
    assert result["gap_scaling"]["length_convention"] == (
        "L_eff=sqrt(L1*L2)"
    )
    assert result["field_role"] == "external_published_benchmark"
    assert result["precision_reproduction_claim"] is False


def test_sigma2_is_finite_size_crossing_comparison():
    result = published_gamma_comparison()

    assert result["sigma"] == 2.0
    assert result["Gamma_x_32_64"] == pytest.approx(1.4284112034302971)
    assert result["published_Gamma_c"] == pytest.approx(1.4208)
    assert result["classification"] == "finite_size_crossing_comparison"
    assert result["exact_reproduction_claim"] is False
