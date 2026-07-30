"""#117 Lennard-Jones 团簇全局优化 —— 种子候选（被 OmniEvolve 进化的对象）。

任务：对 LJ38 找到尽可能低的势能构型（fcc 截角八面体全局极小 E_GM = -173.928426）。
难点：真 GM 藏在一个**窄而深的 fcc 漏斗**底，而宽浅的二十面体漏斗（底 -173.252）
会捕获几乎所有搜索。进化应聚焦**搜索策略**：步长/温度退火调度、重启策略、
扰动方式、漏斗逃逸机制——而非势能函数本身（势能由参考核 lj_ref 提供，不可改）。

==== 输出契约（验证器 verify_lj.py 依赖，勿破坏）====
运行结束后必须写出 candidate_result.json：
    {
        "N": 38,
        "best_energy": <float>,            # 用 lj_ref.lj_energy_fast 算得的能量
        "best_coords_flat": <[3N float]>,  # 行主序展平的 (N,3) 坐标
        "n_force_evals": <int>
    }
验证器会用 lj_ref 从坐标独立重算能量与力范数；自报能量与重算不一致会判 invalid。

==== 进化提示 ====
- 可改：HYPERPARAMETERS、退火调度、重启逻辑、扰动分布、是否加入 reheat/盆地跳跃变体。
- 不可改：势能定义（一律调用 lj_ref.lj_energy_fast / lj_ref.lj_forces）。
- 约束：总运行时间须在沙箱超时内（约 120s）。
"""

from __future__ import annotations

import json
import os
import time

import numpy as np
from scipy.optimize import minimize

import lj_ref

# ---- 时间预算（搜索评估器可通过环境变量缩短；完整复核默认 140s）----
TIME_BUDGET_SEC = float(os.environ.get("LJ_TIME_BUDGET_SEC", "140.0"))
_T0 = time.perf_counter()

# ---- 目标团簇 ----
N = 38

# ---- 可进化的超参数（搜索策略）----
HYPERPARAMETERS = {
    "n_restarts": 6,       # 随机重启次数（含 1 次 fcc 晶格种子）
    "n_steps": 250,        # 每次重启的 basin-hopping 步数
    "step_start": 0.8,     # 初始扰动步长（更大 → 更易穿越漏斗）
    "step_end": 0.05,      # 终止扰动步长
    "temp_start": 5.0,     # 初始 Metropolis 温度（更高 → 更易逃离二十面体漏斗）
    "temp_end": 0.1,       # 终止温度
    "reheat_threshold": 50, # 连续 N 步无改善则 reheat
    "reheat_temp": 3.0,    # reheat 温度
    "lbfgs_maxiter": 5000,
    "seed": 42,
}


def random_init(n: int, rng: np.random.Generator, scale: float = 1.5) -> np.ndarray:
    """随机初始构型：n 个原子分布在半径 ~ scale*n^(1/3) 的球内。"""
    coords = rng.standard_normal((n, 3))
    r = np.linalg.norm(coords, axis=1, keepdims=True)
    r[r < 1e-10] = 1.0
    target_r = scale * (n ** (1.0 / 3.0)) * (rng.random((n, 1)) ** (1.0 / 3.0))
    return coords / r * target_r


def fcc_seed(n: int, rng: np.random.Generator) -> np.ndarray:
    """构造以八面体空隙为中心的 fcc 三壳层截角八面体。

    LJ38 的全局极小是 fcc 截角八面体（O_h 对称性），但它的漏斗很窄。
    38 个格点必须是围绕 fcc 八面体空隙的 6+8+24 三层；若以原子为中心
    按半径取 38 点，会切断 24 重简并壳层并破坏 O_h 对称性。
    """
    if n != 38:
        raise ValueError("the symmetry-preserving fcc seed is defined for LJ38")
    nearest_neighbor = 2.0 ** (1.0 / 6.0)
    conventional_a = np.sqrt(2.0) * nearest_neighbor
    half_a = conventional_a / 2.0
    sites = np.array(
        [
            (i, j, k)
            for i in range(-4, 5)
            for j in range(-4, 5)
            for k in range(-4, 5)
            if (i + j + k) % 2 == 0
        ],
        dtype=float,
    ) * half_a
    octahedral_void = np.array([half_a, 0.0, 0.0])
    dists = np.linalg.norm(sites - octahedral_void, axis=1)
    idx = np.argsort(dists)[:n]
    coords = sites[idx].copy()
    coords -= coords.mean(axis=0)
    return coords


def local_minimize(coords: np.ndarray, maxiter: int) -> tuple[float, np.ndarray, int]:
    """从给定初值局部极小化 LJ 势能（L-BFGS-B）。返回 (能量, 坐标, 力评估次数)。"""
    n_evals = [0]
    flat = coords.flatten()

    def objective(x):
        n_evals[0] += 1
        return lj_ref.lj_energy_fast(x.reshape(-1, 3))

    def gradient(x):
        return -lj_ref.lj_forces(x.reshape(-1, 3)).flatten()

    result = minimize(
        objective, flat, jac=gradient, method="L-BFGS-B",
        options={"maxiter": maxiter, "ftol": 1e-10, "gtol": 1e-8},
    )
    return float(result.fun), result.x.reshape(-1, 3), n_evals[0]


def _time_left() -> float:
    return TIME_BUDGET_SEC - (time.perf_counter() - _T0)


def basin_hopping_anneal(n: int, hp: dict, seed: int, init_coords: np.ndarray | None = None) -> dict:
    """退火 basin-hopping + reheat 漏斗逃逸。返回本次轨迹的最优结果。"""
    rng = np.random.default_rng(seed)
    n_steps = hp["n_steps"]
    q_step = (hp["step_end"] / hp["step_start"]) ** (1.0 / n_steps)
    q_temp = (hp["temp_end"] / hp["temp_start"]) ** (1.0 / n_steps)

    total_evals = 0
    if init_coords is not None:
        coords = init_coords.copy()
    else:
        coords = random_init(n, rng)
    e_curr, coords, ev = local_minimize(coords, hp["lbfgs_maxiter"])
    total_evals += ev
    e_best, coords_best = e_curr, coords.copy()
    known_best = lj_ref.LJ_REFERENCES.get(n)
    if known_best is not None and e_best <= known_best + 1e-6:
        return {"best_energy": e_best, "best_coords": coords_best, "n_force_evals": total_evals}

    step_now = float(hp["step_start"])
    temp_now = float(hp["temp_start"])
    stagnation = 0

    for _ in range(n_steps):
        if _time_left() < 5.0:
            break
        perturbed = coords + rng.normal(0, step_now, coords.shape)
        e_new, coords_new, ev = local_minimize(perturbed, hp["lbfgs_maxiter"])
        total_evals += ev

        delta_e = e_new - e_curr
        if delta_e < 0 or rng.random() < np.exp(-delta_e / max(temp_now, 1e-10)):
            e_curr, coords = e_new, coords_new
            if e_curr < e_best:
                e_best, coords_best = e_curr, coords.copy()
                stagnation = 0
            else:
                stagnation += 1
        else:
            stagnation += 1

        # 漏斗逃逸：连续无改善 → reheat（跳回高温探索）
        if stagnation >= hp.get("reheat_threshold", 50):
            temp_now = hp.get("reheat_temp", 3.0)
            step_now = hp["step_start"] * 0.5
            stagnation = 0

        step_now *= q_step
        temp_now *= q_temp

    return {"best_energy": e_best, "best_coords": coords_best, "n_force_evals": total_evals}


def run() -> dict:
    hp = HYPERPARAMETERS
    rng = np.random.default_rng(hp["seed"])
    g_best, g_coords, g_evals = None, None, 0
    for r in range(hp["n_restarts"]):
        if g_best is not None and _time_left() < 10.0:
            break
        # 第一次重启用 fcc 晶格种子（针对 LJ38 的 fcc GM）
        if r == 0:
            init = fcc_seed(N, rng)
        else:
            init = None
        res = basin_hopping_anneal(N, hp, seed=hp["seed"] + r * 7, init_coords=init)
        g_evals += res["n_force_evals"]
        if g_best is None or res["best_energy"] < g_best:
            g_best = res["best_energy"]
            g_coords = res["best_coords"].copy()
        known_best = lj_ref.LJ_REFERENCES.get(N)
        if known_best is not None and g_best <= known_best + 1e-6:
            break
    # 对全局最优结构做一次紧致 polish，确保输出为收敛极小（力范数远低于验证门）
    if g_best is not None and _time_left() > 5.0:
        e_polish, coords_polish, ev = local_minimize(g_coords, maxiter=20000)
        g_evals += ev
        if e_polish < g_best:
            g_best, g_coords = e_polish, coords_polish
    return {"best_energy": g_best, "best_coords": g_coords, "n_force_evals": g_evals}


if __name__ == "__main__":
    out = run()
    # 用参考核重算一次能量，确保自报能量与参考定义一致（通过验证器一致性门）
    e_ref = lj_ref.lj_energy_fast(out["best_coords"])
    payload = {
        "N": N,
        "best_energy": float(e_ref),
        "best_coords_flat": out["best_coords"].flatten().tolist(),
        "n_force_evals": int(out["n_force_evals"]),
    }
    with open("candidate_result.json", "w", encoding="utf-8") as f:
        json.dump(payload, f)
    # 人类可读摘要（非评分 JSON；评分由 verify_lj.py 输出）
    e_gm = lj_ref.LJ_REFERENCES.get(N, float("nan"))
    print(f"LJ{N} seed: E={e_ref:.6f}  gap_to_GM={e_gm - e_ref:+.4f}  evals={out['n_force_evals']}")
