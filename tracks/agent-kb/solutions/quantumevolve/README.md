# quantumevolve — 比赛提交主入口

> **从这里开始阅读。** 本文件是提交的导航页，指引您到所有材料。

---

## 团队

| | |
|---|---|
| **Team** | quantumevolve |
| **Members** | 結凪 (UynajGI) |
| **PR** | [QuantumBFS/quantum.harness#181](https://github.com/QuantumBFS/quantum.harness/pull/181) |
| **主注册** | [#133](https://github.com/QuantumBFS/quantum.harness/issues/133)（The Problem Factory） |
| **附带参与** | #34, #71, #117, #232, #233 |

---

## 阅读指南

| 您想了解 | 读这个 | 时间 |
|----------|--------|------|
| **核心成果（最硬的结果）** | [**highlight_232_exact_certificates.md**](highlight_232_exact_certificates.md) | 10 分钟 |
| **核心成果（人类可读版）** | [**note_232_human_readable.md**](note_232_human_readable.md) | 8 分钟 |
| **我们做了什么、结果如何** | 本文件下方 §1-§3 | 5 分钟 |
| **OmniEvolve 框架技术细节** | [omnievolve_technical_intro.md](omnievolve_technical_intro.md) | 10 分钟 |
| **五题逐题深入分析** | [final_competition_report.md](final_competition_report.md)（691 行） | 30 分钟 |
| **与 #133 的关系和定位** | 本文件 §4 | 3 分钟 |
| **代码和证书材料** | 本文件 §5 材料索引 | 按需 |

---

## §1 一句话总结

我们用自主开发的 **OmniEvolve 进化框架**（LLM 驱动代码变异 + 沙箱评估 + MCTS 搜索）
尝试求解五道 benchmark 清晰的科研问题，验证了 #133 求解器组件的能力边界。

**最成功的成果**：#232 非对易多项式优化——获得 **31 个精确闭合常数**（含 6 个 Table 4 开放问题，论文未解决）。

---

## §2 五题结果

| Issue | 赛题 | 赛道 | 结果 | 一句话 |
|-------|------|------|------|--------|
| [#232](https://github.com/QuantumBFS/quantum.harness/issues/232) | 非对易多项式优化 | polyopt | ✅ **31 精确闭合**（25 + 6 Table 4） | 最成功：AI 搜索 + 人工精确化 |
| [#71](https://github.com/QuantumBFS/quantum.harness/issues/71) | Occam's Circuit | qcs | score=0.9960 | 接近满分，score 悬崖效应 |
| [#117](https://github.com/QuantumBFS/quantum.harness/issues/117) | Lennard-Jones 团簇 | globalopt | E=−173.13 | 困在同一能量盆地 |
| [#34](https://github.com/QuantumBFS/quantum.harness/issues/34) | N-Queens 计数 | peps | max_n=14 | N=16 壁垒，42 候选无突破 |
| [#233](https://github.com/QuantumBFS/quantum.harness/issues/233) | PXP 谱间隙证书 | polyopt | score=0.0 | 数学层面存在结构性困难 |

**投入**：69+ 实验 DB，600+ 候选，1300+ LLM 调用，~10M tokens

---

## §3 核心发现

1. **LLM 擅长已知框架内组合搜索，不擅长跳出框架发明新方法**
   - #232 成功：在 SOHS 框架内搜索基词组合
   - #117 失败：需要发明 basin hopping，LLM 只会调 L-BFGS 参数

2. **评估器设计比 LLM 能力更重要**
   - 连续梯度（#232）→ 有效进化
   - 天花板/悬崖效应（#34, #71）→ 进化停滞

3. **反作弊是证书类挑战的核心难题**
   - #233 经历 4 轮攻防：LLM 发明 inverse iteration、手写 Lanczos 等绕过方式
   - 解法：递归调用链分析（AST BFS）

4. **AI+人类协同比纯 AI 更有效**
   - #232 的 25 个精确闭合 = AI 数值搜索 + 人工有理化 + AI 验证

---

## §4 与 #133 的关系

#133（The Problem Factory）的完整链路：

```
问题生成器 ──→ 求解器 ──→ 发表
 (Tier 1)      (Tier 2)    (Tier 3)
```

**OmniEvolve = 求解器组件的 demo 验证。**

- ✅ 实现了：给定问题 + 验证门 → 进化求解 → 积累启发式
- ❌ 未实现：自动问题生成（Tier 1）、自动发表（Tier 3）

我们的贡献是给求解器设计提供了**第一手实验证据**：
- 什么问题适合进化求解（连续梯度 + 组合搜索空间）
- 什么问题不适合（需要范式跳跃 + 离散目标）
- LLM 会怎么作弊、怎么防御
- 评估器怎么设计才有效

详见 [omnievolve_technical_intro.md](omnievolve_technical_intro.md) §15 设计原则。

---

## §5 材料索引

### 介绍文档（读这些了解项目）

| 文件 | 内容 | 行数 |
|------|------|------|
| **本文件** | 导航 + 结果摘要 + #133 定位 | — |
| [omnievolve_technical_intro.md](omnievolve_technical_intro.md) | 框架技术介绍（基于源码调研） | 400+ |
| [final_competition_report.md](final_competition_report.md) | 完整比赛报告（逐题分析 + 跨题对比 + 框架反思） | 691 |

### 细分报告（按赛题深入）

| 文件 | 赛题 |
|------|------|
| [reports/challenge_report_71_occam_circuit.md](../../../qcs/solutions/quantumevolve/reports/challenge_report_71_occam_circuit.md) | #71 Occam's Circuit |
| [reports/challenge_report_117_lennard_jones.md](../../../qcs/solutions/quantumevolve/reports/challenge_report_117_lennard_jones.md) | #117 Lennard-Jones |
| [reports/challenge_report_232_polyopt.md](../../../qcs/solutions/quantumevolve/reports/challenge_report_232_polyopt.md) | #232 非对易多项式优化 |
| [reports/challenge_report_233_rydberg_gap.md](../../../qcs/solutions/quantumevolve/reports/challenge_report_233_rydberg_gap.md) | #233 PXP 谱间隙 |
| [reports/challenge_report_34_nqueens.md](../../../qcs/solutions/quantumevolve/reports/challenge_report_34_nqueens.md) | #34 N-Queens |
| [nqueens_convergence.md](../../../peps/solutions/quantumevolve/reports/nqueens_n28_convergence.md) | #34 收敛记录（42 候选） |

### 代码与证书（实验材料）

| 目录 | 内容 |
|------|------|
| [25 个精确闭合证书](../../../polyopt/solutions/quantumevolve/certificates/) | #232 核心成果（JSON） |
| [graph33 子项目](../../../polyopt/solutions/quantumevolve/graph33/) | #232 进化 + 验证代码 |
| [mystery 电路预测](../../../qcs/solutions/quantumevolve/predictions/) | #71 测试集输出 |
| [五题评估器代码](../../../qcs/solutions/quantumevolve/omnievolve_framework/) | 种子 + 评估器 + 配置 |
| [Rydberg gap 代码](../../../polyopt/solutions/quantumevolve/rydberg-gap-233/) | #233 ED + SDP 尝试 |
| `challenges/omnievolve/` | OmniEvolve 框架源码（23,730 行） |

### 各赛道 README（提交结构）

| 赛道 | README |
|------|--------|
| agent-kb（主） | 本文件 |
| [qcs](../../../qcs/solutions/quantumevolve/README.md) | #71 为主 + 五题总览 |
| [globalopt](../../../globalopt/solutions/quantumevolve/README.md) | #117 |
| [peps](../../../peps/solutions/quantumevolve/README.md) | #34 |
| [polyopt](../../../polyopt/solutions/quantumevolve/README.md) | #232 + #233 |

---

*quantumevolve · 2026-07-30*
