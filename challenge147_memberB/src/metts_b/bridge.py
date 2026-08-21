"""Bridge to the shared infrastructure in challenge147stuff/solution.

B 角色（二维 METTS 最小正确实现）复用 A / 已有的 core 与 ED，不重复造轮子：
  - core.model   : TFIM 哈密顿量、Pauli 算子、键表
  - core.lattice : 正方格 + snake 映射
  - core.io      : assert_mem_available / MemoryBudgetExceeded / CSV / JSON 写出
  - core.observables : ThermoResult, rel_err, within_tol
  - ed.ed        : 精确对角化（2x2、3x4 等小系统精确基准）

本模块只负责把 solution 目录加入 sys.path 并 re-export，让 B 的代码以
``from metts_b.bridge import ...`` 一处引用，避免散落的路径硬编码。
"""
import os
import sys

# solution 目录相对于本仓库根：src/metts_b -> src -> challenge147_memberB -> repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
_SOLUTION = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "challenge147stuff", "solution")
)
if not os.path.isdir(_SOLUTION):
    raise RuntimeError(
        f"metts_b.bridge: shared solution dir not found at {_SOLUTION}. "
        "B 复用 challenge147stuff/solution 的 core/ed，请确认该目录存在。"
    )
if _SOLUTION not in sys.path:
    sys.path.insert(0, _SOLUTION)

# re-export 共享基础设施（导入即校验可用性）
from core.model import SZ, SX, tfim_bonds, z2_flip_invariant  # noqa: E402
from core.lattice import SquareLattice  # noqa: E402
from core.io import (  # noqa: E402
    MemoryBudgetExceeded,
    assert_mem_available,
    write_csv,
    write_manifest,
    read_csv,
)
from core.observables import (  # noqa: E402
    ThermoResult,
    rel_err,
    within_tol,
    thermodynamics_from_logZ,
    free_energy_from_u,
)
from ed.ed import build_sparse_hamiltonian, ed_thermodynamics  # noqa: E402

SOLUTION_PATH = _SOLUTION

__all__ = [
    "SZ", "SX", "tfim_bonds", "z2_flip_invariant",
    "SquareLattice",
    "MemoryBudgetExceeded", "assert_mem_available",
    "write_csv", "write_manifest", "read_csv",
    "ThermoResult", "rel_err", "within_tol",
    "thermodynamics_from_logZ", "free_energy_from_u",
    "build_sparse_hamiltonian", "ed_thermodynamics",
    "SOLUTION_PATH",
]
