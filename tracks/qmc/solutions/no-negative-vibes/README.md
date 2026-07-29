# No Negative Vibes

这是“无符号问题量子蒙卡”挑战的队伍工作区。日常只需要从
[START_HERE.md](START_HERE.md) 进入；`quantum.harness` 其余目录是主办方提供的基础设施，
不属于本项目的阅读范围。

## 快速入口

| 想做什么 | 从哪里开始 |
|---|---|
| 查看当前论文主结果 | [四状态 Lorentz 路径度量定理](docs/ODDCYCLE_PATH_METRIC_CERTIFICATE.md) |
| 一条命令重放最终精确证书 | `python -m oracle.oddcycle_final_certificate` |
| 查看论文草稿与挑战完成审计 | [论文草稿](docs/ODDCYCLE_PAPER_DRAFT.md) · [#121 审计](docs/ODDCYCLE_CHALLENGE_AUDIT.md) |
| 第一次了解题目 | [中文零基础导读](docs/ONBOARDING.zh-CN.md) |
| 查看当前严格恒正候选 | [全非负路径半群](docs/TOTAL_NONNEGATIVE_PATH_CLASS.md) |
| 查看它离新物理模型还有多远 | [TN 物理映射前沿](docs/TN_PHYSICAL_MAPPING_FRONTIER.md) |
| 查看普通 hopping 为何只能是路径 | [复合矩阵规范 no-go](docs/COMPOUND_GAUGE_NO_GO.md) |
| 查看最新 139.2 万权重初筛 | [新半群初筛结果](docs/FRONTIER_SEMIGROUP_RESULTS.md) |
| 查看 AZ 幸存类的 14 万权重锥筛选 | [AZ 幸存类半群锥](docs/AZ_SURVIVOR_CONE_RESULTS.md) |
| 查看已占位的激进候选批次 | [新结构候选与证伪清单](docs/SPECULATIVE_CANDIDATE_BATCH.md) |
| 查看激进候选首批 19.2 万权重结果 | [奇数阶路由与宇称分辨 Majorana](docs/SPECULATIVE_STRUCTURE_RESULTS.md) |
| 查看当前结论和文献边界 | [研究地基](docs/FOUNDATIONS.md) |
| 接着推进项目 | [当前状态与下一步](START_HERE.md) |

后续的 oracle 代码、测试和运行说明也会从 `START_HERE.md` 统一索引，避免入口继续分散。

## 当前主结果

最终候选是五维四字母集合
`{B(1/1000), B(1/1000)^T, B(4/5), B(4/5)^T}`。四个精确有理
Lorentz 度量、16 个严格转移不等式和相干时间定向共同证明任意深度
`det(I+W)>0`。独立 Gordan–Stiemke 对偶证书排除了公共单个二次度量解释；
同一字母表构成正系数 `(37,1,1,1,1)/41` 的 Hermitian、数守恒、相互作用
五模 transfer。旧 continuum alphabet 已被证明属于已知 common-quadratic-metric 类，
只保留为严格对照，不再作为新发现。

## Team

| | |
|---|---|
| **Team name** | No Negative Vibes |
| **Members** | 金子博、潘籼至 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Find new physically realizable matrix classes whose determinantal QMC weights remain nonnegative beyond the known split-orthogonal and semigroup conditions. |
| **Catalog issue** | `Addresses #121` — “Sign-problem free hunter,” released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `qmc` — derived from the catalog issue’s `Method: Quantum Monte Carlo` field. |
