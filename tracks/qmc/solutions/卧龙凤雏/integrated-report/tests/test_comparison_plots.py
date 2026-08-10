from PIL import Image

from analysis.comparison_plots import build_comparison_plots


def test_builds_four_nonempty_pngs(models, tmp_path):
    paths = build_comparison_plots(models, tmp_path)

    assert set(paths) == {
        "central-charge-intervals",
        "target-deviation",
        "precision-runtime",
        "validation-gates",
    }
    for path in paths.values():
        assert path.stat().st_size > 20_000
        with Image.open(path) as image:
            assert image.width >= 1200
            assert image.height >= 700
            assert image.mode in {"RGB", "RGBA"}


def test_plot_generation_is_deterministic(models, tmp_path):
    first = build_comparison_plots(models, tmp_path / "first")
    second = build_comparison_plots(models, tmp_path / "second")

    assert {
        name: path.read_bytes() for name, path in first.items()
    } == {
        name: path.read_bytes() for name, path in second.items()
    }
