# No Negative Vibes

> **Formal submission:** [complete challenge report](CHALLENGE_REPORT.md) ·
> [exact reproduction guide](REPRODUCE.md) ·
> [publication draft](docs/ODDCYCLE_PAPER_DRAFT.md).
>
> The report includes every positive, negative, reduced, numerical, and
> unfinished result from both collaborators and the shared integration branch.

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
| 接着推进项目 | [当前状态与下一步](START_HERE.md) |
| 查某项完整证明或反例 | [分类文档导航](docs/README.md) |
| 查看协作与交付状态 | [合作者进展说明](docs/COLLABORATOR_UPDATE.zh-CN.md) |

候选卡和历史计划继续保留用于研究审计，但不代表当前结论。日常只从成果总账或
`START_HERE.md` 进入。

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
