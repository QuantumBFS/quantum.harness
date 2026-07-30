from pathlib import Path

from analysis.plots import make_plots, plot_data_hashes
from summary_fixture import summary_fixture


def test_all_bilingual_plots_are_generated_from_identical_data(tmp_path: Path):
    summary = summary_fixture()
    english = make_plots(summary, "en", tmp_path / "en")
    chinese = make_plots(summary, "zh", tmp_path / "zh")

    assert len(english) == len(chinese) == 10
    assert {path.name for path in english} == {path.name for path in chinese}
    assert all(path.read_bytes().startswith(b"\x89PNG") for path in english + chinese)
    assert plot_data_hashes(summary, "en") == plot_data_hashes(summary, "zh")
