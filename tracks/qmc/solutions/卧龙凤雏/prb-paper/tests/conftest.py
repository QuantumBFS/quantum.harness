from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def paper_dir() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]
