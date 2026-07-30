from pathlib import Path

from analysis.locale import get_locale
from analysis.plots import _entropy_coefficients, make_plots, plot_data_hashes
from summary_fixture import summary_fixture


def test_all_bilingual_plots_are_generated_from_identical_data(tmp_path: Path):
    summary = summary_fixture()
    english = make_plots(summary, "en", tmp_path / "en")
    chinese = make_plots(summary, "zh", tmp_path / "zh")

    assert len(english) == len(chinese) == 10
    assert {path.name for path in english} == {path.name for path in chinese}
    assert all(path.read_bytes().startswith(b"\x89PNG") for path in english + chinese)
    assert plot_data_hashes(summary, "en") == plot_data_hashes(summary, "zh")


def test_entropy_coefficients_use_phi_axis_and_separate_coefficient_panels():
    summary = summary_fixture()
    summary["entanglement"]["coefficients"] = [
        {
            "phi_pi": phi,
            "width": width,
            "v": phi / width,
            "c_prime": phi * width,
            "c": phi + width,
        }
        for phi in (0.06, 0.10, 0.14, 0.18)
        for width in (8, 12, 16, 24)
    ]

    figure, _ = _entropy_coefficients(summary, get_locale("en"))

    assert len(figure.axes) == 3
    assert figure.axes[-1].get_xlabel() == get_locale("en").labels["phi"]
    assert all(len(axis.lines) == 4 for axis in figure.axes)
