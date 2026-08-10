from pathlib import Path

from PIL import Image

from analysis.comparison_plots import build_comparison_plots
from analysis.locale import ZH_LOCALE
from analysis.source_plots_zh import build_chinese_source_plots


EXPECTED_SOURCE_PLOTS = {
    ("clean-ising", "free_energy_scaling.png"),
    ("clean-ising", "central_charge_comparison.png"),
    ("clean-ising", "energy_vs_k.png"),
    ("clean-ising", "integration_convergence.png"),
    ("clean-ising", "fit_stability.png"),
    ("clean-ising", "replica_diagnostics.png"),
    ("nishimori-ising", "free_energy_fit.png"),
    ("nishimori-ising", "central_charge_bootstrap.png"),
    ("nishimori-ising", "fit_window_stability.png"),
    ("nishimori-ising", "sampling_stability.png"),
    ("nishimori-ising", "nishimori_energy_identity.png"),
    ("nishimori-ising", "negative_bond_frequency.png"),
    ("weak-self-dual", "finite-size-scaling.png"),
    ("weak-self-dual", "residuals.png"),
    ("weak-self-dual", "fit-stability.png"),
    ("weak-self-dual", "convergence-ess.png"),
    ("weak-self-dual", "self-duality.png"),
}


def test_chinese_comparison_plots_are_separate_and_deterministic(models, tmp_path):
    first = build_comparison_plots(models, tmp_path / "first", ZH_LOCALE)
    second = build_comparison_plots(models, tmp_path / "second", ZH_LOCALE)

    assert set(first) == {
        "central-charge-intervals",
        "target-deviation",
        "precision-runtime",
        "validation-gates",
    }
    assert all(first[key].read_bytes() == second[key].read_bytes() for key in first)
    assert all(_valid_png(path) for path in first.values())


def test_builds_all_seventeen_chinese_source_plots(repo_root, tmp_path):
    first = build_chinese_source_plots(repo_root, tmp_path / "first")
    second = build_chinese_source_plots(repo_root, tmp_path / "second")

    assert set(first) == EXPECTED_SOURCE_PLOTS
    assert all(first[key].read_bytes() == second[key].read_bytes() for key in first)
    assert all(_valid_png(path) for path in first.values())


def _valid_png(path: Path) -> bool:
    if not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    with Image.open(path) as image:
        width, height = image.size
    return path.stat().st_size > 20_000 and width >= 800 and height >= 600
