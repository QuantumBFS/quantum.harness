"""B 角色：二维 METTS 最小正确实现 (challenge147_memberB).

Public API:

  from metts_b.bridge import ...        # shared core/ed (A 侧基础设施)
  from metts_b.hamiltonian import ...   # H conventions, product states, gates
  from metts_b.measure import DenseBackend, run_one_sample
  from metts_b.chain import run_chain, metts_scan, binning_sem
  from metts_b.config import METTSConfig, load_config
  from metts_b import status

The dense backend is the gold reference (exact within Trotter error, no
truncation, N <= ~10-12); the snake-MPS backend (metts_b.mps_backend) extends
to 10x10. Both implement the same protocol used by run_one_sample.
"""
from . import status  # noqa: F401
from .measure import DenseBackend, run_one_sample  # noqa: F401
from .chain import (  # noqa: F401
    run_chain, metts_scan, binning_sem, iid_sem, config_hash, git_version,
)

__all__ = [
    "status", "DenseBackend", "run_one_sample",
    "run_chain", "metts_scan", "binning_sem", "iid_sem",
    "config_hash", "git_version",
]
