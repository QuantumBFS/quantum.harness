"""#34 种子候选：N-queens 精确计数。

读取环境变量 NQUEENS_N，通过位掩码回溯精确计算 Q(N)，
并输出到 candidate_result.json。

这是被 OmniEvolve 进化的对象——进化目标是改进收缩策略
（路径优化、分治、边界 MPS 等），使更大 N 可行。
"""

from __future__ import annotations

import json
import os
import time


def contract_nqueens(n: int) -> int:
    """用位掩码回溯精确计算 Q(N).

    这是无需可选依赖且始终正确的种子基线。后续进化可以用 TN、
    MPS、对称性分解或更强的位运算策略替换它。
    """
    if n < 0:
        raise ValueError("n must be non-negative")

    full = (1 << n) - 1

    def search(columns: int, diag_left: int, diag_right: int) -> int:
        if columns == full:
            return 1

        available = full & ~(columns | diag_left | diag_right)
        total = 0
        while available:
            bit = available & -available
            available ^= bit
            total += search(
                columns | bit,
                ((diag_left | bit) << 1) & full,
                (diag_right | bit) >> 1,
            )
        return total

    return search(0, 0, 0)


def main():
    n = int(os.environ.get("NQUEENS_N", "8"))
    t0 = time.time()
    q_n = contract_nqueens(n)
    wall = time.time() - t0

    result = {
        "n": n,
        "q_n": q_n,
        "wall_time_sec": wall,
        "method": "exact_bitmask_backtracking",
    }
    with open("candidate_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(json.dumps({"status": "ok", "n": n, "q_n": q_n, "wall_sec": round(wall, 3)}))


if __name__ == "__main__":
    main()
