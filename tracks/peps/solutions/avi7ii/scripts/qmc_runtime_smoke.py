"""Compile the QMC kernels and verify deterministic checkpoint resume."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile


def main() -> int:
    print(json.dumps({"event": "qmc_smoke_import_start"}), flush=True)
    import numba
    import numpy as np

    from qh147.qmc import QMCConfig, run_chain

    print(
        json.dumps(
            {"event": "qmc_smoke_import_complete", "numba": numba.__version__}
        ),
        flush=True,
    )
    config = QMCConfig(
        lx=2,
        ly=1,
        beta=0.2,
        h=1.0,
        j=1.0,
        m=4,
        thermal_sweeps=4,
        measure_sweeps=8,
        bins=4,
        seed=147,
    )
    with tempfile.TemporaryDirectory(prefix="qh147-qmc-smoke-") as temporary:
        output = Path(temporary) / "chain"
        partial = run_chain(config, output, stop_after=4)
        resumed = run_chain(config, output)
        fresh = run_chain(config, Path(temporary) / "fresh")
    if len(partial.bin_energy) != 2:
        raise RuntimeError("partial QMC smoke did not stop at two bins")
    if not np.array_equal(resumed.bin_energy, fresh.bin_energy):
        raise RuntimeError("resumed QMC smoke differs from a fresh chain")
    print(
        json.dumps(
            {
                "event": "qmc_smoke_success",
                "bins": len(resumed.bin_energy),
                "u": resumed.mean_energy,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
