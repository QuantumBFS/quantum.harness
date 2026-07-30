from __future__ import annotations

from pathlib import Path

from heat_valve_fixtures import valid_heat_valve_manifest

from floquet_if_manybody.plotting import (
    plot_dark_diagnostics,
    plot_error_maps,
    plot_heat_valve_hero,
    plot_model_variants,
    plot_n3_sector_heat,
    plot_odd_sector_difference,
)


def _n3_manifest() -> dict[str, object]:
    points = []
    diagnostics = []
    for sector in ("even", "odd"):
        for j in (0.25, 0.5, 1.0):
            points.append(
                {
                    "sector": sector,
                    "adaptive_converged": True,
                    "model": {"j": j},
                    "frequency": [0.0, 1.0, 2.0],
                    "continuous": [0.0, j, 0.0],
                }
            )
            diagnostics.append(
                {
                    "sector": sector,
                    "j": j,
                    "integrated_continuous_heat": j,
                    "period_variance": 0.5,
                    "strongest_transitions": [
                        {"source": 0, "target": 1, "weight": j}
                    ],
                }
            )
    return {"points": points, "dark_diagnostics": diagnostics}


def test_all_paper_plots_render_pdf_and_png(tmp_path: Path) -> None:
    n3 = _n3_manifest()
    plot_n3_sector_heat(n3, tmp_path / "sector")
    plot_odd_sector_difference(n3, tmp_path / "odd")
    plot_dark_diagnostics(n3, tmp_path / "dark")
    error = {
        "points": [
            {
                "alpha": alpha,
                "drive_ratio": ratio,
                "status": "converged",
                "metrics": {
                    "trace_distance": 0.1,
                    "correlation": 0.2,
                    "heat": 0.3,
                },
            }
            for alpha in (0.025, 0.05, 0.1)
            for ratio in (0.75, 1.0, 1.25)
        ]
    }
    plot_error_maps(error, tmp_path / "errors")
    models = {
        "points": [
            {
                "adaptive_converged": True,
                "variant": name,
                "frequency": [0.0, 1.0],
                "continuous": [0.0, 1.0],
                "continuous_eta_rescaled": [0.0, 2.0],
            }
            for name in ("bounded_no_ct", "bounded_ct", "kac_no_ct", "kac_ct")
        ]
    }
    plot_model_variants(models, tmp_path / "models")
    assert len(list(tmp_path.glob("*.pdf"))) == 5
    assert len(list(tmp_path.glob("*.png"))) == 5


def test_heat_valve_hero_writes_png_and_pdf(tmp_path: Path) -> None:
    plot_heat_valve_hero(
        valid_heat_valve_manifest(),
        tmp_path / "heat_valve_hero",
    )
    assert (tmp_path / "heat_valve_hero.png").is_file()
    assert (tmp_path / "heat_valve_hero.pdf").is_file()
