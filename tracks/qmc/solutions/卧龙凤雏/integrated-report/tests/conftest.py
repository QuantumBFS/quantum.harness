from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


@pytest.fixture(scope="session")
def models(repo_root):
    from analysis.sources import load_all_models

    return load_all_models(repo_root)

@pytest.fixture(scope="session")
def learning_mit(repo_root):
    from analysis.sources import load_learning_mit

    return load_learning_mit(repo_root)


@pytest.fixture(scope="session")
def report(models, learning_mit):
    from analysis.comparison_plots import build_comparison_plots
    from analysis.report_model import build_report

    package_root = Path(__file__).resolve().parents[1]
    build_comparison_plots(models, package_root / "generated")
    return build_report(models, learning_mit)
