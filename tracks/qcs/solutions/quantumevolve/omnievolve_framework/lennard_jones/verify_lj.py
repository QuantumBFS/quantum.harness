"""#117 Lennard-Jones 验证器（沙箱内运行，不可作弊核心）。

读取候选代码 (main.py) 写出的 candidate_result.json，**用参考势能核 lj_ref 从坐标
独立重算**能量与力范数，绝不信任候选自报的能量。输出一行评分 JSON 到 stdout，
供评估器 parse_result 解析。

候选输出契约 (candidate_result.json)：
    {
        "N": 38,
        "best_energy": -173.9,            # 候选自报（仅用于一致性校验）
        "best_coords_flat": [3N 个浮点],   # 行主序展平的 (N, 3) 坐标
        "n_force_evals": 12345
    }

验证门：
    valid = (max_force_norm < FORCE_TOL) 且 (|E_recomputed - E_claimed| < ENERGY_TOL)
前者确保候选给的是真极小而非鞍点/未收敛结构；后者确保候选没有用错误的势能定义。
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

import lj_ref

# 验证容差
# FORCE_TOL：区分"已弛豫极小"（力量级 ~1e-4 或更低）与"未弛豫/鞍点"（~1 及以上）。
# 候选无作弊动机（非极小构型能量更高 → 分更低），故此门取宽松而有意义的 1e-3；
# 题面 #117 的 |F|<1e-8 是"认证纪录"的更高门槛，非进化评分门。
FORCE_TOL = 1e-3
ENERGY_TOL = 1e-4   # 自报能量与重算能量的一致性上界

CANDIDATE_OUTPUT = "candidate_result.json"
VERIFY_OUTPUT = "verify_result.json"


def _fail(reason: str) -> dict:
    """构造一个 valid=False 的评分结果（能量记为 +inf，评估器会打 0 分）。"""
    return {
        "energy_recomputed": float("inf"),
        "force_norm": float("inf"),
        "claimed_energy": None,
        "n_force_evals": 0,
        "N": 0,
        "valid": False,
        "catch": False,
        "gap_to_gm": None,
        "error": reason,
    }


def main() -> dict:
    if not os.path.exists(CANDIDATE_OUTPUT):
        return _fail(f"missing {CANDIDATE_OUTPUT}")

    try:
        with open(CANDIDATE_OUTPUT, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return _fail(f"cannot parse {CANDIDATE_OUTPUT}: {exc}")

    try:
        N = int(data["N"])
        claimed = float(data["best_energy"])
        coords_flat = np.asarray(data["best_coords_flat"], dtype=float)
        n_evals = int(data.get("n_force_evals", 0))
    except (KeyError, TypeError, ValueError) as exc:
        return _fail(f"malformed candidate output: {exc}")

    if coords_flat.size != 3 * N:
        return _fail(f"coords length {coords_flat.size} != 3*N={3 * N}")

    coords = coords_flat.reshape(N, 3)

    # 独立重算（参考定义：约化单位、无截断、所有对）
    if not np.all(np.isfinite(coords)):
        return _fail("non-finite coordinates")

    e_recomputed = lj_ref.lj_energy_fast(coords)
    force_norm = lj_ref.max_force_norm(coords)

    force_ok = force_norm < FORCE_TOL
    consistent = abs(e_recomputed - claimed) < ENERGY_TOL
    valid = bool(force_ok and consistent)

    e_gm = lj_ref.LJ_REFERENCES.get(N)
    gap_to_gm = (e_gm - e_recomputed) if e_gm is not None else None
    catch = bool(e_gm is not None and e_recomputed < e_gm + 1e-3)

    return {
        "energy_recomputed": float(e_recomputed),
        "force_norm": float(force_norm),
        "claimed_energy": float(claimed),
        "n_force_evals": n_evals,
        "N": N,
        "valid": valid,
        "catch": catch,
        "gap_to_gm": float(gap_to_gm) if gap_to_gm is not None else None,
        "error": "" if valid else (
            "force not converged" if not force_ok else "energy inconsistent with reference"
        ),
    }


if __name__ == "__main__":
    result = main()
    # 同时落盘（expected_output）与打印（评估器解析最后一行 JSON）
    with open(VERIFY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(json.dumps(result))
    sys.exit(0)
