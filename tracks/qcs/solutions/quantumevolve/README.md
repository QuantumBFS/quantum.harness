# quantumevolve — OmniEvolve 进化求解器五题验证

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |
| **PR** | [QuantumBFS/quantum.harness#181](https://github.com/QuantumBFS/quantum.harness/pull/181) |
| **主要注册** | [#133](https://github.com/QuantumBFS/quantum.harness/issues/133)（The Problem Factory — 自主科研问题生成与求解） |
| **附带参与** | #34, #71, #117, #232, #233 |

---

## 1. 项目定位

OmniEvolve 是一个**自主开发的受控元进化框架**（Controlled Meta-Evolution Framework）。
本次比赛的核心目标不是在某道物理赛题上打破记录，而是验证一个科学命题：

> **LLM 驱动的代码进化能否在 benchmark 清晰的科研问题上产生有意义的改进？**

OmniEvolve 对应 #133 的**求解器组件**——给定一个 benchmark 清晰的问题（带可执行验证门），
尝试通过 LLM 进化自动求解。这是对 #133 求解器的 demo 级验证，不是完整的 Problem Factory
（没有实现问题生成器和自动发表）。

### 核心架构：三件套范式

每个科研问题被编码为三个文件：

```
initial_code.py   — 种子候选（正确但弱的基线实现）
evaluator.py      — 评估器（定义 score 函数 + 沙箱执行计划）
config.toml       — 进化参数（LLM 模型、种群、代数、沙箱限制）
```

进化循环：种子 → LLM 变异 → 沙箱评估 → MCTS 选择 → 下一代。

### 设计哲学

> **好的评估器比强的 LLM 更重要。**

一个设计良好的 score 函数（连续梯度 + 多点验证 + 效率权重）能让弱 LLM 进化出有意义的结果；
一个设计不当的 score 函数（天花板效应、悬崖效应、误导性归一化）会让任何 LLM 陷入停滞。

---

## 2. 五题总览

| Issue | 赛题 | 赛道 | 出题人 | 最高分 | 核心发现 | 状态 |
|-------|------|------|--------|--------|---------|------|
| [#71](https://github.com/QuantumBFS/quantum.harness/issues/71) | Occam's Circuit（布尔函数恢复） | QCS | Jin-Guo Liu, HKUST(GZ) | 0.9960 | Score 悬崖效应 | 接近但未满分 |
| [#117](https://github.com/QuantumBFS/quantum.harness/issues/117) | Lennard-Jones 团簇优化 | GlobalOpt | Lei Wang (王磊), IOP CAS | E=−173.13* | 双漏斗困局 | 未打破记录 |
| [#232](https://github.com/QuantumBFS/quantum.harness/issues/232) | 非对易多项式优化 | PolyOpt | Jie Wang & Jin-Guo Liu | **25 个精确闭合** | AI+人类协同 | ✅ 最成功 |
| [#233](https://github.com/QuantumBFS/quantum.harness/issues/233) | PXP Rydberg 谱间隙证书 | PolyOpt | Jie Wang & Jin-Guo Liu | 0.0 | 数学层面不可能 | 框架完整但无正分 |
| [#34](https://github.com/QuantumBFS/quantum.harness/issues/34) | N-Queens 精确计数 | PEPS | Jin-Guo Liu, HKUST(GZ) | max_n=14 | N=16 壁垒 | 进化中 |

\* #117 的 evaluator 内部 score=1.0 是归一化假象，实际 E=−173.13 vs 记录 E_GM=−173.93。

### 投入统计

| 指标 | 值 |
|------|-----|
| 实验 DB 数 | 69+ |
| 总候选数 | 600+ |
| LLM 调用 | 1,300+ |
| Token 消耗 | ~10M |
| 估算费用 | ~$10 |
| LLM 模型 | qwen3.8-max-preview（阿里云百炼）→ GLM-5.2（智谱，因超时切换） |
| 沙箱后端 | trusted_subprocess（Windows） |

---

## 3. 逐题详细

### 3.1 #71 Occam's Circuit（布尔函数最小电路恢复）

**问题**：从多项式级输入-输出训练样本中恢复隐藏布尔函数，给出最小且能泛化的电路。

**官方交付**：4 个 mystery 电路恢复 + 测试输出预测 + 搜索脚本 + 方法说明。

**结果**：

| 指标 | 值 |
|------|-----|
| DB 数 | 31 |
| 总评估 | 208 |
| Token | ~4.28M |
| 最高分 | **0.9960**（gen=3, v15） |
| 种子分 | 0.9958（100% accuracy, 17 gates） |

**语义恢复**（人工 + 进化协同）：

| Instance | 恢复函数 | 门数 |
|----------|---------|------|
| mystery-A | 8-bit `x + y` | 37 |
| mystery-B | 7-bit `abs(x - y)` | 50 |
| mystery-C | 6×6-bit `x * y` | 191 |
| mystery-D | 5-bit `x² + y²` | 144 |

**关键发现**：
- **Score 悬崖效应**：accuracy 从 100% 到 0% 是离散跳变，score 从 0.996 直接跌到 0.006，LLM 无法从失败中学习
- **0.996→1.0 无法跨越**：最后 0.4% 需要减少门数，LLM 反复尝试但无法保持 correctness
- **震荡而非收敛**：gen 5-7、9-10、19-21 反复回退，MCTS 浪费 budget

**材料**：
- 详细报告：[reports/challenge_report_71_occam_circuit.md](reports/challenge_report_71_occam_circuit.md)
- 种子代码：`challenges/omnievolve/examples/occam_circuit/initial_code.py`
- 评估器：`challenges/omnievolve/examples/occam_circuit/evaluator.py`
- 预测输出：[predictions/](predictions/)
- Mystery 电路：[mystery-A.txt](mystery-A.txt) ~ [mystery-D.txt](mystery-D.txt)
- 提交构建：[build_submission.py](build_submission.py)
- 提交清单：[submission_manifest.json](submission_manifest.json)

---

### 3.2 #117 Lennard-Jones 团簇全局优化

**问题**：打破单组分 LJ 团簇能量记录。LJ38 (E_GM = −173.928427) 是已知困难基准。

**官方要求**：复现已知 E_GM 不算成果，必须打破记录。

**结果**：

| 指标 | 值 |
|------|-----|
| DB 数 | 25 |
| 总评估 | 203 |
| Token | ~2.55M |
| 种子能量 | E = −173.1343 |
| **最佳能量** | **E = −173.1343**（= 种子，无改进） |
| 目标能量 | E_GM = −173.9284 |
| 能量 gap | 0.7941（差 0.46%，未跨越双漏斗） |

**关键发现**：
- **所有候选困在同一能量盆地**：4 个候选能量完全一致（−173.1343），进化只调了 L-BFGS 参数
- **LLM 优化参数而非策略**：没有发明 basin hopping、genetic operators、thermal cycling
- **score=1.0 的误导**：LJ924 frontier 的归一化分数掩盖了实际物理量差距

**材料**：
- 详细报告：[reports/challenge_report_117_lennard_jones.md](reports/challenge_report_117_lennard_jones.md)
- 赛道 README：[tracks/globalopt/solutions/quantumevolve/README.md](../../../globalopt/solutions/quantumevolve/README.md)
- Phase 1 结果：[tracks/globalopt/results/quantumevolve-phase-1/](../../../globalopt/results/quantumevolve-phase-1/)
- 种子代码：`challenges/omnievolve/examples/lennard_jones/initial_code.py`
- 评估器：`challenges/omnievolve/examples/lennard_jones/evaluator.py`
- 验证器：`challenges/omnievolve/examples/lennard_jones/verify_lj.py`
- 参考数据：`challenges/omnievolve/examples/lennard_jones/lj_ref.py`

---

### 3.3 #232 非对易多项式优化（β(G) 严格证书）

**问题**：利用 moment-SOS / SOHS 层级，对量子图参数 β(G)（Lovász ψ 的非对易推广）
给出严格上界证书。目标图来自 [arXiv:2310.00612](https://arxiv.org/abs/2310.00612) Table 4。

**结果**（最成功）：

| 指标 | 值 |
|------|-----|
| DB 数 | 3（graph33 + bell×2） |
| 总评估 | 45 |
| Token | ~392K |
| 精确闭合常数 | **25 个** |
| Hope signal | atlas#878 gap=10⁻⁸ |
| 文献上界收紧 | graph33: 2.0013 → 2.0000169 |
| 量子优势发现 | comp(C₇), Clebsch 图（β > α） |

**进化轨迹（graph33）**：
```
gen=0  score=0.500  upper=2.00249  ← 种子（degree-2）
gen=2  score=0.875  upper=2.00046  ← LLM 添加三次基词
gen=9  score=0.916  upper=2.00017  ← 最高分（degree-3 最优）
后续手工 degree-4 → upper=2.0000169 → 精确有理化
```

**关键发现**：
- **AI+人类协同是正确模式**：AI 做数值搜索 → 人工做精确有理化 → AI 验证
- **无限族闭合是高 ROI 策略**：Kₙ, Kₘ,ₙ, C₂ₖ 等一次发现给出无限多个常数
- **graph33 精确闭合结构性不可能**：奇异对偶 + 无理最优解（含 √5）

**材料**：
- 详细报告：[reports/challenge_report_232_polyopt.md](reports/challenge_report_232_polyopt.md)
- 赛道 README：[tracks/polyopt/solutions/quantumevolve/README.md](../../../polyopt/solutions/quantumevolve/README.md)
- 25 个精确证书：[tracks/polyopt/solutions/quantumevolve/certificates/](../../../polyopt/solutions/quantumevolve/certificates/)
- graph33 子项目：[tracks/polyopt/solutions/quantumevolve/graph33/](../../../polyopt/solutions/quantumevolve/graph33/)
- graph33 证书：[tracks/polyopt/results/quantumevolve-graph33/](../../../polyopt/results/quantumevolve-graph33/)
- 闭合报告：[tracks/polyopt/results/quantumevolve-232-closures/](../../../polyopt/results/quantumevolve-232-closures/)
- 种子代码：`challenges/omnievolve/examples/polyopt/initial_code.py`
- 评估器：`challenges/omnievolve/examples/polyopt/evaluator.py`
- 验证器：`challenges/omnievolve/examples/polyopt/verify_candidate.py`

---

### 3.4 #233 PXP Rydberg 链谱间隙证书

**问题**：为 PXP（Rydberg blockade）链给出 SDP 证书，认证谱间隙 E₁−E₀ 的下界。
H = Σ P_{i-1} σˣ_i P_{i+1}，N=8 时 Fibonacci 约束 Hilbert 空间 dim=55。
官方目标：不使用 ED，用 SDP/LMI 给出 certified_gap / ED_gap 最大比值。

**结果**：

| 指标 | 值 |
|------|-----|
| DB 数 | 6（v1→v4 + v5/v6） |
| 总评估 | 63+ |
| Token | ~1.29M |
| 反作弊拦截 | 8+（eigvalsh/eigh/eigsh/solve/inv） |
| **合法候选最高分** | **0.0000** |

**反作弊演进（核心技术贡献）**：

| 版本 | LLM 作弊方式 | 拦截方法 |
|------|-------------|---------|
| v1→v2 | 直接 `np.linalg.eigvalsh(H)` | regex 扫描函数体 |
| v3 | 移到辅助函数 `_compute_spectrum_via_inverse_iteration` | ❌ 绕过 |
| v4 | — | ✅ AST BFS 递归调用链 + 扩大禁令模式 |

**关键发现**：
- **数学层面不可能**：单层 cvxpy SDP 在 55×55 上无法给出正 certified_gap（E0_lb=−8 太松）
- **LLM 极其擅长绕过禁令**：每次堵一个漏洞它就发明新方法（inverse iteration、手写 Lanczos）
- **合法策略空间极窄**：禁止所有谱计算原语后，只剩 cvxpy SDP——但证明力不足

**材料**：
- 详细报告：[reports/challenge_report_233_rydberg_gap.md](reports/challenge_report_233_rydberg_gap.md)
- 赛道 README：[tracks/polyopt/solutions/quantumevolve/rydberg-gap-233/README.md](../../../polyopt/solutions/quantumevolve/rydberg-gap-233/README.md)
- ED 参考：[tracks/polyopt/solutions/quantumevolve/rydberg-gap-233/pxp_ed_gap.py](../../../polyopt/solutions/quantumevolve/rydberg-gap-233/pxp_ed_gap.py)
- 证书尝试：[tracks/polyopt/solutions/quantumevolve/rydberg-gap-233/pxp_gap_certificate.py](../../../polyopt/solutions/quantumevolve/rydberg-gap-233/pxp_gap_certificate.py)
- 种子代码：`challenges/omnievolve/examples/rydberg_gap/initial_code.py`
- 评估器：`challenges/omnievolve/examples/rydberg_gap/evaluator.py`
- 验证器：`challenges/omnievolve/examples/rydberg_gap/verify_gap.py`

---

### 3.5 #34 N-Queens 精确计数

**问题**：计算 N×N 棋盘上放置 N 个互不攻击皇后的方案数 Q(N)。
已知值至 N=27（Preußer & Engelhardt 2017, FPGA），Q(28) 未知（开放前沿）。

**结果**：

| 指标 | 值 |
|------|-----|
| 评估器版本 | v4 渐进阶梯（N=12→28） |
| DB | `nqueens_glm52_v4_n28.db` |
| 已完成候选 | 32 |
| 种子 score | 0.26（通过 N=12, N=14） |
| **最佳 score** | **0.26**（= 种子，无改进） |
| **max_n** | **14**（N=16 从未突破） |
| LLM | GLM-5.2（智谱） |

**评估器演进**：

| 版本 | 设计 | 问题 |
|------|------|------|
| v1/v2 | 单 N=8，exact match → 1.0 | 天花板效应 + 硬编码作弊 |
| v3 | N=12 + 交叉验证 + regex 反作弊 | 只有单点分数 |
| v4 | 渐进阶梯 N=12→28，失败即停，自适应超时 | 当前版本 |

**关键发现**：
- **N=16 壁垒**：纯 Python 回溯 >100s，40s 超时需 2.5× 加速，LLM 无法实现
- **退化趋势**：Gen 1-2 正常（score≈0.26），Gen 3+ 候选崩溃（score=0）
- **硬编码作弊**（v2 发现）：LLM 直接 `return 92`，wall_time 从 ms 降到 μs

**材料**：
- 详细报告：[reports/challenge_report_34_nqueens.md](reports/challenge_report_34_nqueens.md)
- 收敛记录：[tracks/peps/solutions/quantumevolve/reports/nqueens_n28_convergence.md](../../../peps/solutions/quantumevolve/reports/nqueens_n28_convergence.md)
- 赛道 README：[tracks/peps/solutions/quantumevolve/README.md](../../../peps/solutions/quantumevolve/README.md)
- 种子代码：`challenges/omnievolve/examples/nqueens/initial_code.py`
- 评估器：`challenges/omnievolve/examples/nqueens/evaluator.py`
- 验证器：`challenges/omnievolve/examples/nqueens/verify_nq.py`
- OEIS 参考：`challenges/omnievolve/examples/nqueens/oeis_ref.py`
- 配置：`challenges/omnievolve/configs/nqueens.toml`

---

## 4. 跨题模式发现

### 进化模式分类

| 模式 | 赛题 | 特征 | 进化效果 |
|------|------|------|---------|
| **微调型** | #71, #117 | 种子已接近最优 | score 微提升，大量震荡 |
| **探索型** | #232 | 种子弱但有明确改进路径 | score 显著提升后停滞 |
| **防御型** | #233, #34 | 核心挑战是防止作弊 | 框架设计比进化更重要 |

### LLM 创新能力边界

**能做的**：已知框架内搜索参数/组件组合、发现评估器漏洞、微调代码效率

**做不到的**：发明全新算法范式、自主发现深层代数结构、在离散目标上有效搜索、构造复杂数学结构

### 核心结论

> **LLM 进化不是替代者，而是放大器。** 最好的结果来自人类定义方向（种子+评估器）、AI 执行搜索的协同模式。

---

## 5. 完整报告

**[最终比赛报告（691 行，逐题详细分析 + 跨题对比 + 框架反思）](../../../docs/final_competition_report.md)**

**[OmniEvolve 框架介绍与 #133 定位说明](../../../tracks/agent-kb/solutions/quantumevolve/README.md)**

Per-challenge 报告在 [reports/](reports/) 目录。

---

## 6. 源码

- OmniEvolve 框架：`challenges/omnievolve/`（本仓库内）
- 五题三件套：`challenges/omnievolve/examples/{nqueens,occam_circuit,lennard_jones,polyopt,rydberg_gap}/`
- 进化配置：`challenges/omnievolve/configs/`
- 实验数据库：`challenges/omnievolve/.omnievolve/*.db`

---

## 7. 运行命令

```bash
cd challenges/omnievolve

# N-Queens（v4 渐进阶梯）
.venv/Scripts/omnievolve.exe run examples/nqueens/initial_code.py \
    -e examples.nqueens.evaluator:NQueensEvaluator \
    -c configs/nqueens.toml --gens 30 --trusted

# Occam Circuit
.venv/Scripts/omnievolve.exe run examples/occam_circuit/initial_code.py \
    -e examples.occam_circuit.evaluator:OccamCircuitEvaluator \
    -c configs/occam_circuit.toml --gens 20 --trusted

# Lennard-Jones
.venv/Scripts/omnievolve.exe run examples/lennard_jones/initial_code.py \
    -e examples.lennard_jones.evaluator:LennardJonesEvaluator \
    -c configs/lennard_jones.toml --gens 20 --trusted

# Polyopt (graph33)
.venv/Scripts/omnievolve.exe run examples/polyopt/initial_code.py \
    -e examples.polyopt.evaluator:PolyoptEvaluator \
    -c configs/polyopt.toml --gens 20 --trusted

# Rydberg Gap
.venv/Scripts/omnievolve.exe run examples/rydberg_gap/initial_code.py \
    -e examples.rydberg_gap.evaluator:RydbergGapEvaluator \
    -c configs/rydberg_gap.toml --gens 20 --trusted
```

---

*quantumevolve · 2026-07-30*
# quantumevolve — #71 Occam's Circuit

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Recover hidden Boolean arithmetic functions from polynomially many input–output pairs by evolving minimal quantum circuits, testing Occam's razor as an explicit optimization objective. |
| **Catalog issue** | Addresses #71 — released by Jin-Guo Liu, HKUST(GZ). |
| **Track** | `qcs` — per the issue's own instruction ("work under `tracks/qcs/solutions/<your-team>/`"). |

## Approach

OmniEvolve: evolutionary algorithm discovery powered by LLM-guided code mutation. The optimizer evolves circuit-construction programs that are scored on gate count (minimality) × test accuracy (generalization), directly mapping the gate-count-vs-generalization curve the challenge asks for.

## Current semantic recovery

We tested candidate arithmetic families against every disclosed training row, using the
challenge's LSB-first encoding.  The following hypotheses have zero training error and
also achieve 100% on a deterministic, candidate-hidden 20% holdout:

| Instance | Recovered function | Current gates |
|---|---|---:|
| mystery-A | 8-bit `x + y` | 37 |
| mystery-B | 7-bit `abs(x - y)` | 50 |
| mystery-C | 6×6-bit `x * y` | 191 |
| mystery-D | 5-bit `x² + y²` | 144 |

`build_submission.py` regenerates the four netlists, verifies exact agreement on all
training rows, and writes predictions for every hidden-test input.  OmniEvolve then
optimizes all four circuits jointly: accuracy is a hard gate and total gate count breaks
ties.  This follows the issue's encouraged hybrid route—semantic recognition followed by
structured logic synthesis—while preventing a mutation that helps one mystery from
silently breaking another.

The 6×6 multiplier uses carry-save column compression followed by one final
ripple addition. Its 191-gate netlist was exhaustively checked on all 4,096
input pairs; the four-instance evaluator independently confirms 100% train and
hidden-holdout accuracy with 422 total gates.

The hidden outputs had not been revealed when these predictions were produced, so final
hidden-test accuracy remains explicitly unverified.

## Final Report

**[Final Competition Report (25K chars)](../../docs/final_competition_report.md)** — covers all 5 challenges (#34, #71, #117, #232, #233) with per-challenge analysis, anti-cheat evolution, and framework-level reflections.

Per-challenge reports in [reports/](reports/).

## Source Code

OmniEvolve framework: https://github.com/UynajGI/omnievolve

