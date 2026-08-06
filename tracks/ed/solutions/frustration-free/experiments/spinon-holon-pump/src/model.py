"""Two-sector wrapper for the Rice-Mele-Hubbard model.

Holds models for both half-filling (N_up=N_down=L/2) and one-hole
(N_up=L/2-1, N_down=L/2) sectors with identical boundary conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent
_PC_SRC = _HERE.parent.parent / "pump-correlation" / "src"
if str(_PC_SRC) not in sys.path:
    sys.path.insert(0, str(_PC_SRC))

import model as _pc_model  # noqa: E402
SplitRMHModel = _pc_model.SplitRMHModel
_is_antiperiodic = _pc_model._is_antiperiodic


@dataclass
class TwoSectorModel:
    """Half-filling and one-hole RMH models sharing the same L, U, t.

    model_N:   (N_up=L/2,   N_down=L/2) — half-filling reference
    model_Nm1: (N_up=L/2-1, N_down=L/2) — one spin-up hole
    """

    L: int
    U: float
    t: float = 1.0
    model_N: SplitRMHModel = field(init=False)
    model_Nm1: SplitRMHModel = field(init=False)

    def __post_init__(self) -> None:
        n = self.L // 2
        object.__setattr__(
            self, "model_N",
            SplitRMHModel(L=self.L, U=self.U, t=self.t),
        )
        object.__setattr__(
            self, "model_Nm1",
            SplitRMHModel(L=self.L, U=self.U, t=self.t,
                          N_up=n - 1, N_down=n),
        )

    @property
    def dim_N(self) -> int:
        return self.model_N.dim

    @property
    def dim_Nm1(self) -> int:
        return self.model_Nm1.dim

    @property
    def antiperiodic(self) -> bool:
        return self.model_N.antiperiodic


@dataclass
class ThreeSectorModel:
    """Half-filling, one-hole, and one-particle RMH models.

    model_N:   (N_up=L/2,   N_down=L/2) — half-filling reference
    model_Nm1: (N_up=L/2-1, N_down=L/2) — one spin-up hole (N-1)
    model_Np1: (N_up=L/2+1, N_down=L/2) — one spin-up extra particle (N+1)
    """

    L: int
    U: float
    t: float = 1.0
    model_N: SplitRMHModel = field(init=False)
    model_Nm1: SplitRMHModel = field(init=False)
    model_Np1: SplitRMHModel = field(init=False)

    def __post_init__(self) -> None:
        n = self.L // 2
        object.__setattr__(
            self, "model_N",
            SplitRMHModel(L=self.L, U=self.U, t=self.t),
        )
        object.__setattr__(
            self, "model_Nm1",
            SplitRMHModel(L=self.L, U=self.U, t=self.t,
                          N_up=n - 1, N_down=n),
        )
        object.__setattr__(
            self, "model_Np1",
            SplitRMHModel(L=self.L, U=self.U, t=self.t,
                          N_up=n + 1, N_down=n),
        )

    @property
    def dim_N(self) -> int:
        return self.model_N.dim

    @property
    def dim_Nm1(self) -> int:
        return self.model_Nm1.dim

    @property
    def dim_Np1(self) -> int:
        return self.model_Np1.dim

    @property
    def antiperiodic(self) -> bool:
        return self.model_N.antiperiodic
