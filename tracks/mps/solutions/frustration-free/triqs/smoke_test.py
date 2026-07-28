"""Minimal import and construction test for the isolated TRIQS/CT-HYB runtime."""

from __future__ import annotations

import triqs
import triqs_cthyb
from triqs.utility import mpi
from triqs_cthyb import Solver


def main() -> None:
    solver = Solver(
        beta=2.0,
        gf_struct=[("up", 1), ("down", 1)],
        n_iw=16,
        n_tau=65,
    )
    assert solver.G0_iw.mesh.beta == 2.0
    assert set(solver.G0_iw.indices) == {"up", "down"}
    if mpi.is_master_node():
        print(
            "SMOKE TEST ONLY — NO SCIENTIFIC COMPARISON:",
            "TRIQS/CT-HYB import and constructor passed;",
            f"triqs={triqs.__file__}",
            f"triqs_cthyb={triqs_cthyb.__file__}",
        )


if __name__ == "__main__":
    main()
