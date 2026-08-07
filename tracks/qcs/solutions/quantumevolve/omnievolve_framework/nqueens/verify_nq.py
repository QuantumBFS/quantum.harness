"""#34 N-queens 验证器（沙箱内运行）。

v3: 多 N 阶梯评估 + 反作弊 + 效率评分。

验证流程：
  1. 读 candidate_result.json（候选在 N=12 上的输出）
  2. 对 EVAL_NS 中的每个 N 运行候选代码，比对 OEIS
  3. 源码反作弊：检查是否硬编码 Q 值

评分（阶梯式）：
  - N=12 正确：0.3
  - N=14 正确：+0.3
  - N=16 正确：+0.2
  - 效率奖励：+0.2（加速比，硬编码归零）
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys

from oeis_ref import Q_EXACT

CANDIDATE_OUTPUT = "candidate_result.json"
VERIFY_OUTPUT = "verify_result.json"

# 阶梯评估 N 值（与 evaluator 一致）
EVAL_NS = [12, 14, 16]

# 每个 N 的分值
N_WEIGHTS = {12: 0.3, 14: 0.3, 16: 0.2}
EFFICIENCY_WEIGHT = 0.2
SEED_BASELINE_SEC = 0.7  # 种子在 N=12 上的基线时间

# 反作弊
_HARDCODE_Q_PATTERN = re.compile(
    r'\b(724|2680|14200|73712|365596|2279184|14772512)\b'
)


def _fail(reason: str) -> dict:
    return {"valid": False, "score": 0.0, "error": reason, "results": {}}


def check_no_hardcoded_q(source: str) -> tuple[bool, str]:
    matches = _HARDCODE_Q_PATTERN.findall(source)
    if matches:
        return False, f"hardcoded Q value: {matches[0]}"
    if re.search(r'return\s+(92|352|724|2680|14200)\b', source):
        return False, "direct return constant"
    return True, ""


def run_candidate_at_n(n: int) -> tuple[bool, int, float]:
    """运行候选代码在指定 N 上，返回 (正确, Q值, 耗时)。"""
    try:
        env = dict(os.environ)
        env["NQUEENS_N"] = str(n)
        proc = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        if proc.returncode != 0:
            return False, 0, 0
        for line in proc.stdout.strip().splitlines():
            try:
                obj = json.loads(line.strip())
                if isinstance(obj, dict) and "q_n" in obj:
                    q = int(obj["q_n"])
                    expected = Q_EXACT.get(n, 0)
                    wall = float(obj.get("wall_sec", obj.get("wall_time_sec", 0)))
                    return (q == expected), q, wall
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
        return False, 0, 0
    except (subprocess.TimeoutExpired, Exception):
        return False, 0, 0


def main() -> dict:
    # --- 反作弊 ---
    try:
        with open("main.py", encoding="utf-8") as f:
            source = f.read()
        clean, reason = check_no_hardcoded_q(source)
        if not clean:
            result = _fail(f"ANTI-CHEAT: {reason}")
            result["anti_cheat"] = reason
            return result
    except FileNotFoundError:
        return _fail("main.py not found")

    # --- 对每个 N 阶梯评估 ---
    results = {}
    total_score = 0.0
    all_walls = []

    for n in EVAL_NS:
        ok, q_val, wall = run_candidate_at_n(n)
        results[f"Q({n})"] = {"ok": ok, "q": q_val, "wall": wall, "expected": Q_EXACT.get(n)}
        if ok:
            total_score += N_WEIGHTS[n]
            if wall > 0.001:
                all_walls.append(wall)

    # --- 效率奖励 ---
    if all_walls:
        # 用最小的 wall_time（最快的 N）计算加速比
        best_wall = min(all_walls)
        speedup = min(1.0, SEED_BASELINE_SEC / best_wall)
        efficiency_bonus = EFFICIENCY_WEIGHT * speedup
    else:
        efficiency_bonus = 0.0

    total_score += efficiency_bonus

    # 读候选原始输出（用于 wall_time_sec 字段）
    wall_main = 0
    try:
        with open(CANDIDATE_OUTPUT, encoding="utf-8") as f:
            data = json.load(f)
        wall_main = float(data.get("wall_time_sec", data.get("wall_sec", 0)))
    except Exception:
        pass

    result = {
        "valid": True,
        "score": round(total_score, 4),
        "results": results,
        "wall_time_sec": wall_main,
        "efficiency_bonus": round(efficiency_bonus, 4),
        "error": "",
    }
    return result


if __name__ == "__main__":
    result = main()
    with open(VERIFY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(json.dumps(result))
    sys.exit(0)
