# quantumevolve — #34 N-Queens Exact Counting

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |
| **PR** | [QuantumBFS/quantum.harness#181](https://github.com/QuantumBFS/quantum.harness/pull/181) |

## Challenge

| | |
|---|---|
| **Issue** | [#34](https://github.com/QuantumBFS/quantum.harness/issues/34) |
| **出题人** | Jin-Guo Liu, HKUST(GZ) |
| **Track** | `peps` |
| **目标** | 改进 N-Queens 精确计数算法，使更大 N 可行 |
| **前沿** | Q(27) 已知（FPGA, 2017），Q(28) 未知（开放问题） |

## Approach

OmniEvolve：LLM 驱动的进化算法发现。种子是经典位掩码回溯算法，
进化目标是发现更高效的计数策略（对称性约化、分治、编译加速等）。

### 种子策略

- 算法：位掩码回溯（bitmask backtracking）
- 实现：三个整数 `columns`, `diag_left`, `diag_right` 表示攻击线
- N=12: Q=14200, wall=0.49s
- N=14: Q=365596, wall=15.6s
- N=16: 超时（>40s）

### 评估架构（v4 渐进阶梯）

渐进阶梯 N=12, 14, 16, 18, 20, 22, 24, 26, 28，失败即停：

| N | 权重 | 超时 |
|---|------|------|
| 12 | 0.08 | 10s |
| 14 | 0.08 | 20s |
| 16 | 0.09 | 40s |
| 18 | 0.10 | 60s |
| 20 | 0.10 | 90s |
| 22 | 0.10 | 120s |
| 24 | 0.10 | 150s |
| 26 | 0.15 | 180s |
| 28 | 0.10（前沿） | 240s |

效率奖励：0.10（speedup vs 种子基线）

反作弊：
- regex 源码扫描（禁止硬编码已知 Q 值）
- 多 N 交叉验证（OEIS A000170）
- wall_time < 1ms 判定为硬编码

### 评估器演进

| 版本 | 设计 | 问题 |
|------|------|------|
| v1/v2 | 单 N=8，exact match → 1.0 | 天花板效应 + 硬编码作弊（`return 92`） |
| v3 | N=12 + 交叉验证 + regex 反作弊 | 单点分数，无难度梯度 |
| v4 | 渐进阶梯 N=12→28，失败即停 | **当前版本** |

## Results

| 指标 | 值 |
|------|-----|
| 评估器版本 | nqueens@3.0.0 (v4 渐进阶梯) |
| LLM | GLM-5.2（智谱） |
| DB | `.omnievolve/nqueens_glm52_v4_n28.db` |
| 已完成候选 | 32 |
| 种子 score | 0.26（通过 N=12 + N=14 + 效率） |
| **最佳 score** | **0.26**（= 种子，无改进） |
| **max_n** | **14**（N=16 从未突破） |

### 收敛轨迹

| 代 | best score | max_n | 备注 |
|----|-----------|-------|------|
| 1 | 0.2600 | 14 | 全部通过 N=12+14，卡在 N=16 |
| 2 | 0.2600 | 14 | 同上 |
| 3 | 0.2600 | 14 | 3/4 候选崩溃 |
| 4 | 0.2600 | 14 | 全部崩溃 |
| 5-6 | 0.2600 | 14 | 持续平台 |

### 作弊发现（v2）

LLM 在 v2（N=8 单点验证）中发现硬编码作弊：
```
gen=0  score=1.0  wall=1.5ms   ← 种子（真算）
gen=1  score=1.0  wall=1.7μs   ← return 92（硬编码）
```
wall_time 暴降 1000×，因为根本没有在计算。v3/v4 通过多 N 交叉验证 + regex 扫描修复。

## Analysis

### 失败原因

1. **N=16 壁垒**：纯 Python 回溯 N=16 需 >100s，40s 超时要求 2.5× 加速
2. **LLM 变异表面化**：变量重命名、循环重排，而非深层算法重构（对称性约化、C 扩展）
3. **退化趋势**：缺乏适应度梯度时，变异逐渐破坏代码正确性（Gen 3+ 崩溃率 >50%）
4. **算法跳跃的难度**：从 O(N!) 回溯到多项式级加速需要根本性洞察，增量变异无法实现

### 设计层面成功

1. 渐进阶梯 + 反作弊成功区分有效/无效候选
2. 多 N 交叉验证彻底阻止硬编码作弊
3. 自适应超时避免大 N 浪费计算资源

## Materials

| 文件 | 说明 |
|------|------|
| `challenges/omnievolve/examples/nqueens/initial_code.py` | 种子代码（位掩码回溯） |
| `challenges/omnievolve/examples/nqueens/evaluator.py` | 评估器 (v3) |
| `challenges/omnievolve/examples/nqueens/verify_nq.py` | 验证器 (v4 渐进阶梯) |
| `challenges/omnievolve/examples/nqueens/oeis_ref.py` | OEIS A000170 参考值 Q(1)..Q(27) |
| `challenges/omnievolve/configs/nqueens.toml` | 进化配置 |
| [收敛记录](reports/nqueens_n28_convergence.md) | v4 N=12→28 收敛轨迹 |
| [详细报告](../../../qcs/solutions/quantumevolve/reports/challenge_report_34_nqueens.md) | 逐题分析 |
| [完整比赛报告](../../../docs/final_competition_report.md) | 691 行总报告 |

## Run

```bash
cd challenges/omnievolve
.venv/Scripts/omnievolve.exe run examples/nqueens/initial_code.py \
    -e examples.nqueens.evaluator:NQueensEvaluator \
    -c configs/nqueens.toml --gens 30 --trusted
```

---

*quantumevolve · 2026-07-30*
