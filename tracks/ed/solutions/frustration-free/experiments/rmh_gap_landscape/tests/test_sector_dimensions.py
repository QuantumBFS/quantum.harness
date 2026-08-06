"""Test sector Hilbert space dimensions."""

import sys
from math import comb
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
from src.model import RiceMeleHubbardModel


def dim(L: int, N_up: int, N_down: int) -> int:
    return comb(L, N_up) * comb(L, N_down)


class TestL6Dimensions:
    @pytest.mark.parametrize("n_up,n_down,expected", [
        (3, 3, 400),
        (4, 2, 225),
        (4, 3, 300),
        (2, 3, 300),
    ])
    def test_dimension(self, n_up, n_down, expected):
        m = RiceMeleHubbardModel(L=6, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=n_up, N_down=n_down)
        assert m.dim == expected
        assert m.dim == dim(6, n_up, n_down)


class TestL10Dimensions:
    @pytest.mark.parametrize("n_up,n_down,expected", [
        (5, 5, 63504),
        (6, 4, 44100),
        (6, 5, 52920),
        (4, 5, 52920),
    ])
    def test_dimension(self, n_up, n_down, expected):
        m = RiceMeleHubbardModel(L=10, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=n_up, N_down=n_down)
        assert m.dim == expected
        assert m.dim == dim(10, n_up, n_down)


class TestL4Dimensions:
    @pytest.mark.parametrize("n_up,n_down,expected", [
        (2, 2, 36),
        (3, 1, 16),
        (3, 2, 24),
        (1, 2, 24),
    ])
    def test_dimension(self, n_up, n_down, expected):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=n_up, N_down=n_down)
        assert m.dim == expected
