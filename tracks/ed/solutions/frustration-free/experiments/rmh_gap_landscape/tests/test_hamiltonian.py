"""Test Hamiltonian construction and properties."""

import sys
from pathlib import Path

import numpy as np
import pytest

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))
from src.model import RiceMeleHubbardModel


class TestHermiticity:
    @pytest.mark.parametrize("delta,Delta", [
        (0.0, 0.0), (0.0, 2.0), (0.5, 0.0), (-0.3, 4.0), (0.0, -8.0),
    ])
    def test_hermiticity_various_params(self, delta, Delta):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=delta, Delta=Delta, U=12.0,
                                 N_up=2, N_down=2)
        assert m.hermiticity_error() < 1e-12

    def test_hermiticity_all_sectors(self):
        sectors = [(2, 2), (3, 1), (3, 2), (1, 2)]
        for n_up, n_down in sectors:
            m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.3, Delta=1.5, U=12.0,
                                     N_up=n_up, N_down=n_down)
            assert m.hermiticity_error() < 1e-12

    def test_hermiticity_large_L(self):
        m = RiceMeleHubbardModel(L=10, t=1.0, delta=0.0, Delta=0.0, U=12.0,
                                 N_up=5, N_down=5)
        assert m.hermiticity_error() < 1e-12

    def test_validate_hermiticity_raises(self):
        # A real model should never fail, so this is a smoke test
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=0.0,
                                 N_up=2, N_down=2)
        m.validate_hermiticity(tolerance=1e-12)  # should not raise


class TestParameterValidation:
    def test_L5_construction_works(self):
        """L=5 (odd) still produces a valid Hamiltonian."""
        m = RiceMeleHubbardModel(L=5, t=1.0, delta=0.0, Delta=0.0, U=0.0,
                                 N_up=2, N_down=2)
        assert m.dim > 0

    def test_rejects_invalid_N_up(self):
        with pytest.raises(ValueError, match="N_up"):
            RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=0.0,
                                 N_up=5, N_down=2)

    def test_rejects_non_finite_params(self):
        with pytest.raises(ValueError, match="finite"):
            RiceMeleHubbardModel(L=4, t=float("inf"), delta=0.0, Delta=0.0, U=0.0,
                                 N_up=2, N_down=2)


class TestUZeroLimit:
    def test_U_zero_hamiltonian_valid(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=0.0,
                                 N_up=2, N_down=2)
        assert m.hermiticity_error() < 1e-12

    def test_U_negative_hamiltonian_valid(self):
        m = RiceMeleHubbardModel(L=4, t=1.0, delta=0.0, Delta=0.0, U=-4.0,
                                 N_up=2, N_down=2)
        assert m.hermiticity_error() < 1e-12
