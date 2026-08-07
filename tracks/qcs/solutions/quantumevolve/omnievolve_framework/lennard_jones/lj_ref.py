"""Lennard-Jones 参考势能核（约化单位 epsilon=sigma=1）。

本文件是 #117 挑战在 OmniEvolve 沙箱内的**单一真值源**：
- 候选代码 (main.py) 用它做搜索时的能量/力计算；
- 验证器 (verify_lj.py) 用它从候选输出的坐标**独立重算**能量与力范数。

定义与 Cambridge Cluster Database 完全一致：无截断、无平移、所有原子对求和。
E = 4 * sum_{i<j} [(1/r_ij)^12 - (1/r_ij)^6]

来源：harness tracks/globalopt/solutions/lj_energy.py（Wales & Doye, JPCA 101, 5111, 1997）。
为使 submodule 自包含，此处内联一份；公式为数学定义，无漂移风险。
"""

from __future__ import annotations

import numpy as np

# Cambridge Cluster Database 文献参考能量（ putative global minima）。
# 键 = 原子数 N，值 = 已知最低能量（约化单位）。
LJ_REFERENCES: dict[int, float] = {
    7: -16.505384,
    13: -44.326801,
    19: -72.659782,
    38: -173.928426,  # fcc 截角八面体（真 GM）；-173.252378 是二十面体亚稳漏斗底
    55: -279.242431,
    75: -396.282249,
    98: -543.642957,
}

# LJ38 的二十面体亚稳漏斗底（用于诊断是否陷入亚稳漏斗）。
LJ38_ICOSAHEDRAL = -173.252378


def lj_energy(coords: np.ndarray) -> float:
    """LJ 总势能（Python 循环版，用于小规模交叉校验）。"""
    N = coords.shape[0]
    energy = 0.0
    for i in range(N):
        for j in range(i + 1, N):
            r = np.linalg.norm(coords[i] - coords[j])
            r6 = r ** 6
            r12 = r6 * r6
            energy += 4.0 * (1.0 / r12 - 1.0 / r6)
    return energy


def lj_energy_fast(coords: np.ndarray) -> float:
    """LJ 总势能（向量化版，大团簇用）。"""
    N = coords.shape[0]
    diff = coords[:, None, :] - coords[None, :, :]  # (N, N, 3)
    r2 = np.sum(diff ** 2, axis=-1)  # (N, N)
    np.fill_diagonal(r2, np.inf)  # 去掉自相互作用
    r6 = r2 ** 3
    r12 = r6 * r6
    mask = np.triu(np.ones((N, N), dtype=bool), k=1)
    inv_r6 = 1.0 / r6[mask]
    inv_r12 = 1.0 / r12[mask]
    return float(4.0 * np.sum(inv_r12 - inv_r6))


def lj_forces(coords: np.ndarray) -> np.ndarray:
    """每个原子上的解析力 F_i = -dE/dr_i。

    F_i = 24 * sum_{j!=i} (2/r_ij^14 - 1/r_ij^8) * (r_i - r_j)
    """
    N = coords.shape[0]
    diff = coords[:, None, :] - coords[None, :, :]  # (N, N, 3)
    r2 = np.sum(diff ** 2, axis=-1)  # (N, N)
    np.fill_diagonal(r2, 1.0)  # 避免除零
    r8 = r2 ** 4
    r14 = r2 ** 7
    coeff = 24.0 * (2.0 / r14 - 1.0 / r8)  # (N, N)
    np.fill_diagonal(coeff, 0.0)
    forces = np.sum(coeff[:, :, None] * diff, axis=1)  # (N, 3)
    return forces


def max_force_norm(coords: np.ndarray) -> float:
    """最大单原子力范数 —— 在极小点处应趋近于 0（验证是否为真极小而非鞍点）。"""
    f = lj_forces(coords)
    return float(np.max(np.linalg.norm(f, axis=1)))
