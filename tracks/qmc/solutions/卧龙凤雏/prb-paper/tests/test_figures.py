from hashlib import sha256

from pypdf import PdfReader

from build_figures import EXPECTED_FIGURES, build_all_figures
from build_values import build_values


def test_value_macros_are_source_derived(repo_root, tmp_path):
    output = tmp_path / "headline_values.tex"

    build_values(repo_root, output)

    text = output.read_text(encoding="ascii")
    assert r"\newcommand{\CleanMCCharge}{0.498739}" in text
    assert r"\newcommand{\NishimoriCharge}{0.456469}" in text
    assert r"\newcommand{\WeakCharge}{0.444107}" in text
    assert r"\newcommand{\LearningCandidate}{0.30}" in text
    assert r"\newcommand{\LearningPublished}{false}" in text


def test_all_figures_are_deterministic_and_print_readable(repo_root, tmp_path):
    output = tmp_path / "figures"

    first = build_all_figures(repo_root, output)
    first_hashes = {
        path.name: sha256(path.read_bytes()).hexdigest() for path in first
    }
    second = build_all_figures(repo_root, output)
    second_hashes = {
        path.name: sha256(path.read_bytes()).hexdigest() for path in second
    }

    assert tuple(path.name for path in first) == EXPECTED_FIGURES
    assert first_hashes == second_hashes
    assert all(path.stat().st_size > 10_000 for path in first)
    for path in first:
        page = PdfReader(path).pages[0]
        width = float(page.mediabox.width) / 72.0
        height = float(page.mediabox.height) / 72.0
        assert 3.0 <= width <= 7.2
        assert 1.8 <= height <= 8.0
