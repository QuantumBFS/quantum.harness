# quantumevolve — #117 Lennard-Jones Cluster Global Optimization

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |
| **PR** | [QuantumBFS/quantum.harness#181](https://github.com/QuantumBFS/quantum.harness/pull/181) |

## Challenge

| | |
|---|---|
| **Issue** | [#117](https://github.com/QuantumBFS/quantum.harness/issues/117) |
| **出题人** | Lei Wang (王磊), IOP CAS |
| **Track** | `globalopt` — Global optimization / basin-hopping |
| **目标** | 打破单组分 Lennard-Jones 团簇能量记录 |
| **基准** | LJ38 E_GM = −173.928427（已知困难基准，复现不算成果） |

## Approach

OmniEvolve：LLM 驱动的进化算法发现。进化 *程序*（Python 代码），而非直接优化坐标。
种子代码是一个 L-BFGS 局部优化器，从随机初始构型出发优化原子位置。

### 种子策略

- 算法：L-BFGS 梯度下降（scipy.optimize.minimize）
- 起点：随机初始构型
- 缺陷：只做单点局部优化，没有全局搜索策略（无 basin hopping、遗传算法、模拟退火）
- 种子能量：E = −173.1343（FCC-like 局部最优）

### 评估架构

两步验证：
1. `main.py` 候选代码运行 LJ 优化，输出最终构型和能量
2. `verify_lj.py` 独立验证：重算能量 + 检查力范数收敛 + 与 E_GM 比较

score = (S_known − E_candidate) / (S_known − S_seed)

## Results

| 指标 | 值 |
|------|-----|
| DB 数 | 25 |
| 总评估 | 203 |
| LLM 调用 | 457 |
| Token | ~2.55M |
| 种子能量 | E = −173.1343, 力范数 5.2×10⁻⁴ |
| **最佳能量** | **E = −173.1343**（= 种子，无改进） |
| 目标能量 | E_GM = −173.9284 |
| **能量 gap** | **0.7941**（差 0.46%，未跨越双漏斗） |

### 迭代轨迹

```
gen=0  score=0.9834  E=−173.1343  force=5.2×10⁻⁴  fevals=218,233  ← 种子
gen=1a score=0.9834  E=−173.1343  force=5.2×10⁻⁴  fevals=187,063  ← 效率↑14%
gen=1b score=0.9834  E=−173.1343  force=5.2×10⁻⁴  fevals=185,721  ← 效率↑15%
gen=1c score=0.9834  E=−173.1343  force=3.0×10⁻⁴  fevals=229,781  ← 局部更好
```

**所有候选能量完全一致（−173.1343），进化陷入同一能量盆地。**

## Analysis

### 失败原因

1. **LJ38 双漏斗地形**：E=−173.13 是 FCC-like 局部最优，跨越到 E=−173.93 的 icosa 全局最优需要大规模结构重排——单点 L-BFGS 无法实现
2. **LLM 调参而非发明策略**：变异集中在 L-BFGS 步长/容差/迭代次数，没有发明 basin hopping、genetic operators、thermal cycling
3. **缺乏多样性**：所有候选从同一起点出发，收敛到同一局部最优
4. **score=1.0 的误导**：LJ924 frontier 归一化分数掩盖了实际差距

### 框架层面成功

1. 端到端链路完整打通
2. verify_lj.py 有效防止坐标注入作弊
3. 力范数评估比纯能量更严格
4. 效率优化确实有效（fevals 降低 14-15%）

## Materials

| 文件 | 说明 |
|------|------|
| `challenges/omnievolve/examples/lennard_jones/initial_code.py` | 种子代码 |
| `challenges/omnievolve/examples/lennard_jones/evaluator.py` | 评估器 |
| `challenges/omnievolve/examples/lennard_jones/verify_lj.py` | 独立验证器 |
| `challenges/omnievolve/examples/lennard_jones/lj_ref.py` | LJ 参考数据 |
| `challenges/omnievolve/examples/lennard_jones/frontier_evaluator.py` | Frontier 评估器 |
| `challenges/omnievolve/examples/lennard_jones/frontier_initial_code.py` | Frontier 种子 |
| `challenges/omnievolve/configs/lennard_jones.toml` | 进化配置 |
| [Phase 1 结果](../../results/quantumevolve-phase-1/) | 第一阶段回顾 |
| [Phase 2 结果](../../results/quantumevolve-phase-2/) | 第二阶段结果 |
| [详细报告](../../../qcs/solutions/quantumevolve/reports/challenge_report_117_lennard_jones.md) | 逐题分析 |
| [完整比赛报告](../../../docs/final_competition_report.md) | 691 行总报告 |

## Run

```bash
cd challenges/omnievolve
.venv/Scripts/omnievolve.exe run examples/lennard_jones/initial_code.py \
    -e examples.lennard_jones.evaluator:LennardJonesEvaluator \
    -c configs/lennard_jones.toml --gens 20 --trusted
```

---

*quantumevolve · 2026-07-30*
# quantumevolve — #117 Lennard-Jones Cluster Global Optimization

## Team

| | |
|---|---|
| **Team name** | quantumevolve |
| **Members** | 結凪 (UynajGI) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Discover record-beating Lennard-Jones cluster ground-state geometries using evolutionary code optimization (OmniEvolve/AlphaEvolve-style LLM-driven algorithm discovery). |
| **Catalog issue** | Addresses #117 — released by Lei Wang (王磊), IOP CAS. |
| **Track** | `globalopt` — from the issue's Method field (Global optimization / basin-hopping). |

## Approach

OmniEvolve: evolutionary algorithm discovery powered by LLM-guided code mutation and multi-population island-model search. The optimizer evolves *algorithms* (Python programs) that are evaluated against LJ energy landscapes, selecting for both solution quality and computational efficiency.
