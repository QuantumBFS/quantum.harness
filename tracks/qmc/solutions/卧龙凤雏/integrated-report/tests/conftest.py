from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


@pytest.fixture(scope="session")
def models(repo_root):
    from analysis.sources import load_all_models

    return load_all_models(repo_root)
