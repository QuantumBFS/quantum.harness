# Issue #122：Born-rule 开放量子临界中心荷复现计划

> 项目：QuantumBFS/quantum.harness
> 挑战：[Issue #122 — Criticality in open quantum matter](https://github.com/QuantumBFS/quantum.harness/issues/122)
> 团队：Born Critical
> 成员：Yansheng Tu
> 方法注册：QMC（实际实现为 Born-rule Monte Carlo、张量网络/自由费米子传输矩阵和有限尺寸拟合）
> 文档状态：已完成；阶段 0–4 的全部验收门通过
> 最后更新：2026-07-29

## 0. 实施状态

| 阶段 | 状态 | 证据 |
|---|---|---|
| 阶段 0：规范与小系统 oracle | 已完成 | Slurm job `17167`，20/20 测试通过，manifest 状态 `success` |
| 阶段 1：公共数值内核 | 已完成 | Slurm job `17173`，43/43 测试通过，含 \(10^5\) 层 QR smoke |
| 阶段 2：干净 Ising | 已完成 | Slurm job `17178`，48/48 测试通过，M0/M1 均复现 \(c=1/2\) |
| 阶段 3：Nishimori RBIM | 已完成 | 320/320 生产 cell，10,000/10,000 bootstrap，13/13 验收门通过；回归 job `17307` 52/52 |
| 阶段 4：弱自对偶 Born 临界点 | 已完成 | 512/512 生产 cell，10,000/10,000 bootstrap，6/6 合并验收门通过；回归 job `18120` 61/61 |

阶段 0 的机器可读结果位于
`tracks/qmc/results/born-critical/stage0-tests/job-17167/`。该目录按仓库
规则不进入 Git；可提交的阶段报告位于
`tracks/qmc/solutions/Born-Critical-122/STAGE0-REPORT.md`。

阶段 1 的机器可读结果位于
`tracks/qmc/results/born-critical/stage1-tests/job-17173/`，可提交的阶段
报告位于 `tracks/qmc/solutions/Born-Critical-122/STAGE1-REPORT.md`。

阶段 2 的机器可读结果位于
`tracks/qmc/results/born-critical/stage2-clean-ising/job-17178/`，可提交的
阶段报告位于
`tracks/qmc/solutions/Born-Critical-122/STAGE2-REPORT.md`。主 M0 结果为
\(c=0.5011803410\)，M1 修正结果为 \(c=0.4999790414\)。

阶段 3 的机器可读结果位于
`tracks/qmc/results/born-critical/rbim-production-v1/`，交叉验证位于
`tracks/qmc/results/born-critical/stage3-crosschecks/job-17301/`，合并
验收文件为
`tracks/qmc/results/born-critical/stage3-acceptance.json`。主 M1 结果为
\(c_{\rm eff}=0.4597565\)，bootstrap 95% 区间为
\([0.4588332,0.4606509]\)，与 \(0.464\pm0.004\) 的目标区间相交。
可提交的阶段报告位于
`tracks/qmc/solutions/Born-Critical-122/STAGE3-REPORT.md`。

阶段 4 的机器可读结果位于
`tracks/qmc/results/born-critical/selfdual-production-v1/`，Metropolis 与
各向同性交叉验证位于
`tracks/qmc/results/born-critical/stage4-crosschecks/job-17613/`，合并
验收文件为
`tracks/qmc/results/born-critical/stage4-acceptance.json`。主 M1 结果为
\(c_{\rm Casimir}=0.4477180\)，bootstrap 95% 区间为
\([0.4468820,0.4485672]\)，与 \(0.447\pm0.001\) 相交。可提交的阶段报告
位于 `tracks/qmc/solutions/Born-Critical-122/STAGE4-REPORT.md`。

## 1. 目标、边界和完成定义

### 1.1 必做范围

按同一套有限尺寸 Casimir 分析复现三个临界点：

| 模型 | 目标值 | 本项目中的作用 |
|---|---:|---|
| 干净二维 Ising | \(c=1/2\) | 验证传输矩阵、符号、归一化和拟合程序 |
| Nishimori 点的二维 \(\pm J\) RBIM | \(c_{\rm eff}=0.464(4)\) | 第一项带无序的正式结果 |
| 弱自对偶 Born 临界点 | \(c_{\rm Casimir}=0.447(1)\) | 核心任务：相关 Born 无序与自由 Majorana 网络 |

最终必须交付：

1. 可复现的 Born 采样、传输矩阵/网络演化、QR 稳定化和有限尺寸拟合代码；
2. Nishimori 和弱自对偶结果的 Monte Carlo 误差条及拟合窗口稳定性分析；
3. 每个生产运行的不可变配置、随机种子、代码版本、单元状态和聚合结果；
4. 一份短报告，解释模型映射、采样、数值稳定性、有限尺寸拟合和结论。

### 1.2 非关键路径

下列内容只有在三个必做结果通过验收门槛后才开始：

- 低能完整 Lyapunov 谱和标度维数；
- 非结构化 MIPT 的中心荷；
- arXiv:2512.19786 的 DIII Majorana 金属—绝缘体学习转变；
- 相互作用费米子或非阿贝尔拓扑序。

“强提交”内容不能挤占三项中心荷复现的计算预算。

### 1.3 总体验收门槛

每个正式数值结论必须同时满足：

- 至少使用 5 个进入最终拟合的横向尺寸 \(L\)；
- 报告主拟合、去掉最小尺寸后的拟合和加入首个次领项后的拟合；
- 统计误差来自独立轨迹/无序块的重采样，而不是只使用最小二乘协方差；
- 95% 置信区间与挑战目标区间相交，且中心值没有持续的 \(L_{\min}\) 漂移；
- 所有纳入分析的 cell 均有成功 manifest；失败、超时或未收敛 cell 不得静默混入；
- 从原始 cell 数据重新聚合可以生成完全相同的表和图。

## 2. 文献审计及其对实现的约束

以下资料均已按 Issue #122 的引用逐项核对。这里记录的不是泛泛摘要，而是会直接影响实现的决定。

| 来源 | 核对到的关键内容 | 对本项目的直接作用 |
|---|---|---|
| [Zamolodchikov, JETP Lett. 43, 730 (1986)](https://cds.cern.ch/record/437291) | 固定点的 \(c\) 是 CFT 数据，沿幺正 RG 流单调 | 理论背景；不直接给数值算法 |
| [arXiv:1908.08051](https://arxiv.org/abs/1908.08051) | 监测电路的 replica 统计力学映射及临界共形结构 | 解释 Born 轨迹为何产生二维统计模型 |
| [arXiv:2107.03393](https://arxiv.org/abs/2107.03393) | 随机传输矩阵、有效中心荷、算符谱；各向异性 \(\alpha\) 须由空间/时间关联匹配校准 | 规定一般情形中的 \(\alpha\) 校准和 bootstrap 方法 |
| [arXiv:2208.11136](https://arxiv.org/abs/2208.11136) | 浅层确定性电路中由测量结果产生 Nishimori 无序；张量网络加 Monte Carlo | 支持 Born 无序与 Nishimori 映射 |
| [arXiv:2309.02863](https://arxiv.org/abs/2309.02863) | Born 规则将有效温度和无序锁定在 Nishimori 线上 | 为 Nishimori 约束提供实验与理论背景 |
| [arXiv:2208.11699](https://arxiv.org/abs/2208.11699) | 测量制备量子临界点与经典 Ising/规范理论解码映射 | 确定测量记录与经典缺陷变量的关系 |
| [arXiv:quant-ph/0110143](https://arxiv.org/abs/quant-ph/0110143) | 表面码误差阈值到无序统计模型的映射 | 固定“错误率—无序键”物理解释 |
| [arXiv:cond-mat/0010143](https://arxiv.org/abs/cond-mat/0010143) | 周期条带自由能 \(L^{-2}\) Casimir 拟合；旧结果 \(c=0.464(4)\)；其 \(\beta\) 约定是本计划标准 Ising 耦合 \(K\) 的两倍 | Nishimori 主目标和拟合基准；必须做约定转换测试 |
| [arXiv:2403.04767](https://arxiv.org/abs/2403.04767) | 表面码传态对应含 Nishimori 型无序的 Ashkin–Teller/自对偶线 | 自对偶模型的物理背景 |
| [arXiv:2504.12385](https://arxiv.org/abs/2504.12385) | 变形 toric code、学习转变及 TN+MC | 采样与学习可观测量的辅助参考 |
| [arXiv:2502.14034](https://arxiv.org/abs/2502.14034) | 弱自对偶模型的 Born 权重、随机 \(M_Z/M_X\) 门、Majorana 映射、真空扇区、Lyapunov 谱；\(c_{\rm Casimir}=0.447(1)\)；各向同性构造 \(\alpha=1\) | 弱自对偶实现的主要技术规范 |
| [KITP chalk talk](https://online.kitp.ucsb.edu/online/finestructure25/zhu/) | Guo-Yi Zhu 2025 年项目演讲页面；播放器页面当前不能稳定抓取 | 仅作模型概览；公式和数值以 arXiv:2502.14034 为准 |
| [arXiv:2511.02907](https://arxiv.org/abs/2511.02907) | 高精度 \(p_c=0.1092212(4)\)；费米子传输矩阵、Householder QR、稳定化间隔测试及大尺寸数据 | Nishimori 临界点、算法稳定性和高精度交叉验证 |
| [配套 RBIM 代码](https://github.com/Zhouquan-Wan/fermionic-transfer-matrix-rbim) | C++17、Eigen、MKL、PFAPACK、MPI；输入/二进制输出格式和稳定化参数 | 作为独立基线；固定版本 `814c24775b6b46cab77f3b4829c9c3802cab2146` |
| [arXiv:2512.19786](https://arxiv.org/abs/2512.19786) | 一般测量角对应 DIII 类无序自由费米子网络和未知中心荷的学习转变 | 仅在必做任务完成后进入开放挑战 |

文献给出的样本数、系统尺寸和 QR 间隔是起点而非盲目照搬。生产参数必须由本机实现的精度—耗时 pilot 决定。

## 3. 冻结的科学规格

在任何生产提交之前，把本节内容复制到 `run_spec.json`，由实现者复核后锁定。改变模型、边界、扇区或归一化必须创建新 run id，禁止覆盖旧结果。

### 3.1 公共几何与 Casimir 约定

- 几何：二维长圆柱；横向周长 \(L\) 周期边界，传播方向长度 \(N_\tau\gg L\)。
- 横向尺寸优先取偶数，防止两亚晶格/费米子边界条件混杂。
- 三个主模型都选用方格各向同性构造，主分析取 \(\alpha=1\)。
- 干净 Ising 和弱自对偶模型还必须做一次空间/时间尺度一致性检查；若偏差超过 1%，停止并显式拟合或校准 \(\alpha\)。
- 所有对数权重均在 log 域累积，禁止直接连乘大矩阵或直接保存 \(Z\)。

为避免文献中“自由能”符号不同，代码内部只保存明确命名的量：

\[
g_L=\frac{1}{N_\tau}\,\mathbb E[\ln Z],\qquad
\phi_L=\frac{g_L}{L}.
\]

对标准周期二维统计模型，使用

\[
\phi_L=\phi_\infty+\frac{\pi c_{\rm eff}\alpha}{6L^2}
             +\frac{a_4}{L^4}+O(L^{-6}).
\]

对由归一化逐步 Born 条件概率得到的 Shannon surprisal，

\[
h_L=-\frac{1}{L N_\tau}\,
       \mathbb E[\ln P(m)]
    =h_\infty-\frac{\pi c_{\rm Casimir}\alpha}{6L^2}
             +\frac{b_4}{L^4}+O(L^{-6}).
\]

两者的 Casimir 符号相反。测试必须用解析 Ising 结果分别验证符号，不能通过取绝对值“修正”结果。

每条 Born 轨迹同时记录 `log_Z` 和 `log_P`，从而分别报告 Issue
定义的

\[
F_Z=-\mathbb E_P[\ln Z_m]
\]

以及 Shannon 量 \(H=-\mathbb E_P[\ln P(m)]\)。当
\(P=Z/\mathcal Z\) 时，用
\(H=F_Z+\ln\mathcal Z\) 作归一化恒等式检查；弱自对偶模型中则按其
\(P\propto |Z|^2\) 的精确约定检查。不能在不同模型间默认一个未经证明的
因子。弱自对偶目标 \(0.447(1)\) 的主估计使用原文定义的 Shannon/Casimir
量，同时把 \(F_Z\) 作为挑战定义的独立输出。

### 3.2 干净 Ising

- 哈密顿权重：
  \[
  Z=\sum_{\{\sigma\}}\exp\left[
  K_c\sum_{\langle ij\rangle}\sigma_i\sigma_j\right],
  \quad K_c=\frac12\ln(1+\sqrt2).
  \]
- 横向周期边界，无缺陷线。
- 主可观测量：最大行传输矩阵本征值的 \(\ln\lambda_0\)。
- 确切目标：\(c=0.5\)。

### 3.3 Nishimori RBIM

采用唯一的内部规范：

\[
Z(\tau)=\sum_{\{\sigma\}}\exp\left[
K\sum_{\langle ij\rangle}\tau_{ij}\sigma_i\sigma_j\right],
\quad
\Pr(\tau_{ij}=-1)=p,\quad
\Pr(\tau_{ij}=+1)=1-p.
\]

Nishimori 条件为

\[
e^{-2K_N}=\frac{p}{1-p},\qquad
K_N=\frac12\ln\frac{1-p}{p}.
\]

生产中心使用

\[
p_c=0.1092212,\qquad K=K_N(p_c).
\]

Honecker–Picco–Pujol 的局部 \(\delta\) 能量约定写成
\(e^\beta=(1-p)/p\)，即这里的 \(\beta=2K\)。程序必须用小系统枚举证明两种写法给出相同 Boltzmann 比值。

- 横向周期边界，主结果位于无扭曲扇区。
- \(\tau_{ij}\) 独立抽样；不同 \(L\)、replica 和 seed 互不复用 RNG 子流。
- 主可观测量：\(\mathbb E_\tau[\ln Z(\tau)]/(LN_\tau)\)。
- 交叉验证：同一无序样本的周期/反周期自由能差及 clean \(p=0\) 极限。

### 3.4 弱自对偶 Born 模型

按 arXiv:2502.14034 固定：

- 自对偶角 \(\theta=\pi/4\)；
- \(\tanh\beta=\sin\theta\)、\(\tanh\beta'=\cos\theta\)，因此
  \[
  \beta=\beta'=\ln(1+\sqrt2);
  \]
- 每层随机非幺正门
  \[
  M_Z=\exp\left[\frac\beta2\sum_j s_{j,y}Z_jZ_{j+1}\right],
  \qquad
  M_X=\exp\left[\frac{\beta'}2\sum_j t_{j,y}X_j\right];
  \]
- \(s=-1\) 和 \(t=-1\) 分别编码 \(m\) 与 \(e\) string；
- 在圆柱真空扇区强制对应 Wilson loop 为 \(+1\)；
- Jordan–Wigner 后用 \(2L\) 个 Majorana 模式的 Gaussian 演化；
- 方格时空各向同性，主结果 \(\alpha=1\)。

轨迹权重必须是真正的 Born 概率，而非独立同分布的随机符号：

\[
P(e,m)=\frac{\left|Z(e,m)\right|^2}
              {\sum_{e',m'}\left|Z(e',m')\right|^2}.
\]

主采样器采用逐门/逐层条件 Born 采样：由当前 Gaussian 协方差矩阵和范数计算两个可能结果的归一化条件概率，抽样后更新状态。这样

\[
\ln P(e,m)=\sum_k\ln P(o_k\mid o_{<k})
\]

可直接累积，不需要另估全局配分函数。局部 Metropolis TN 采样只作为独立交叉验证，不作为主结果来源。

在 \(\theta=\pi/4\) 的必要 sanity check：

\[
\langle e\rangle=\langle m\rangle=\frac38.
\]

## 4. 代码与数据布局

实现阶段采用以下布局：

```text
tracks/qmc/solutions/Born-Critical-122/
├── README.md
├── environment.yml
├── pyproject.toml
├── configs/
│   ├── ising-pilot.json
│   ├── rbim-pilot.json
│   ├── selfdual-pilot.json
│   └── production-*.json
├── src/borncritical/
│   ├── conventions.py
│   ├── rng.py
│   ├── io.py
│   ├── ising_transfer.py
│   ├── rbim_transfer.py
│   ├── gaussian_majorana.py
│   ├── born_sampler.py
│   ├── lyapunov.py
│   └── casimir_fit.py
├── cpp/
│   ├── rbim_baseline/
│   └── majorana_transfer/
├── scripts/
│   ├── make_run_spec.py
│   ├── run_cell.py
│   ├── aggregate.py
│   ├── fit_casimir.py
│   └── make_report.py
├── slurm/
│   ├── submit_ws0.sh
│   └── born-critical-cpu.sbatch
└── tests/
    ├── test_conventions.py
    ├── test_exact_enumeration.py
    ├── test_qr_stability.py
    ├── test_born_sampler.py
    ├── test_resume.py
    └── test_casimir_fit.py

tracks/qmc/results/born-critical/<run-id>/
├── run_spec.json
├── source.json
├── cells/<cell-id>/
│   ├── manifest.json
│   ├── blocks.parquet
│   ├── observables.json
│   └── run.log
├── aggregate/
│   ├── size_summary.csv
│   ├── bootstrap_samples.parquet
│   ├── fit_summary.json
│   └── exclusions.json
└── figures/
```

`run_spec.json` 是不可变真源，至少包含：

```json
{
  "schema_version": 1,
  "run_id": "model-date-revision",
  "git_commit": "<40-char sha>",
  "model": "ising|rbim_nishimori|selfdual",
  "geometry": {"bc_x": "periodic", "sector": "vacuum"},
  "couplings": {},
  "sizes": [],
  "replicas_per_size": 0,
  "rows_burnin": 0,
  "rows_measure": 0,
  "block_rows": 0,
  "qr_interval": 0,
  "base_seed": 0,
  "alpha": 1.0,
  "software": {},
  "cells": [{"cell_id": "opaque-id", "params": {}}]
}
```

每个 `manifest.json` 必须记录开始/结束时间、host、Slurm job/task id、seed、参数、退出状态、最后完成 block、QR 正交误差、有限值检查、输出 checksum 和 convergence 标签。只有 `"status": "success"` 的 cell 可进入聚合。

## 5. 分阶段实施与 go/no-go 门槛

### 阶段 0：模型约定和参考实现冻结

任务：

1. 把第 3 节所有公式写入 `conventions.py` 的文档字符串和单元测试；
2. 将配套 RBIM 仓库固定到 commit
   `814c24775b6b46cab77f3b4829c9c3802cab2146`，只作为 vendor/reference，不直接修改上游快照；
3. 记录编译器、BLAS/LAPACK、Eigen、PFAPACK、Python 和包版本；
4. 用 \(2\times2\)、\(2\times3\) 枚举比较：
   - 直接求和的 \(Z\)；
   - 行传输矩阵；
   - Gaussian/Majorana 表示；
   - Nishimori 两种耦合规范；
5. 锁定边界条件、Jordan–Wigner 奇偶扇区和 Wilson loop 符号。

通过门槛：

- 小系统的 \(\ln Z\) 绝对误差 \(<10^{-11}\)；
- Gaussian 与显式自旋结果相对误差 \(<10^{-10}\)；
- 所有概率非负且归一化误差 \(<10^{-12}\)；
- 对应全局自旋翻转/规范变换的不变量通过。

未通过时不得提交 pilot。

### 阶段 1：公共数值内核

实现：

1. counter-based 或 `SeedSequence` 分裂 RNG，seed 由
   `(base_seed, model, L, replica)` 唯一确定；
2. 流式 block accumulator，只保存块统计和必要的诊断，不保存每一行矩阵；
3. Householder QR 稳定化：
   - 每 `qr_interval` 层分解；
   - 固定 \(R\) 对角符号；
   - 累积 \(\ln |R_{ii}|\)；
   - 监测 \(Q^\dagger Q-I\) 的最大范数；
4. checkpoint/resume：
   - 保存 RNG 状态、Gaussian 状态、累计器和最后一块；
   - 原子写临时文件后 rename；
   - resume 结果必须逐位或在浮点容限内等于不中断运行；
5. domain-specific Casimir 拟合器，显式使用
   \([1,L^{-2}]\) 或 \([1,L^{-2},L^{-4}]\) 基底。

不能直接使用一般的“对 \(1/L\) 做二次多项式”替代偶次 Casimir 基底。

通过门槛：

- QR interval = 1、2、5 对同一固定序列的最大 Lyapunov 指数在 \(5\times10^{-10}\) 内一致；
- \(10^5\) 层 smoke 中无 NaN/Inf，正交误差始终低于 \(10^{-10}\)；
- checkpoint 恢复测试通过；
- 人工合成数据能在统计误差内恢复已知 \(c\)。

### 阶段 2：干净 Ising warm-up

#### 2A. 小规模正确性

- 尺寸：\(L=2,4,6,8,10\)；
- 对 \(L\le 10\) 构造显式传输矩阵；
- 与 Onsager/自由费米子表达和直接枚举比较 \(\ln\lambda_0\)。

#### 2B. 有限尺寸生产

- 初始尺寸：\(L=4,6,8,10,12,16,20,24,32,48,64\)；
- 主拟合 M0：\(\phi_\infty+A_2/L^2\)，使用大尺寸窗口；
- 独立修正拟合 M1：\(\phi_\infty+A_2/L^2+A_4/L^4\)；
- \(c=6A_2/\pi\)，\(\alpha=1\)；
- 通过逐个提高 \(L_{\min}\) 评估截断系统误差。

通过门槛：

- 主结果与 0.5 的相对偏差 \(<0.5\%\)；
- 去掉两个最小尺寸后偏移小于预声明的 0.5% 系统容差；对于后续含
  Monte Carlo 噪声的数据，另要求偏移小于主拟合 1 个重采样标准误；
- M0/M1 结果差异小于 0.5%；
- Casimir 符号和单位测试全部通过。

若失败，优先检查自由能符号、是否除以 \(L\)、边界扇区和 \(\alpha\)，不得靠增大样本数掩盖系统误差。

### 阶段 3：Nishimori RBIM

#### 3A. 上游基线复现

1. 在计算节点编译固定 commit 的配套代码；
2. 复现仓库示例输入；
3. 对小尺寸将其二进制输出转换为本项目通用 observables；
4. 用本项目枚举/传输矩阵独立比较同一个键配置；
5. 在至少 1000 个固定无序样本上比较 `qr_interval=1` 与 5。

通过门槛：两实现的逐样本 \(\ln Z\) 差异符合双精度舍入误差，且 interval 变化不产生可见偏差。

#### 3B. Pilot

- 尺寸：\(L=4,6,8,10,12\)；
- 每尺寸 8 个独立 replica；
- 每 replica：burn-in \(20L\)，之后先跑 \(2^{14}\) 行；
- block 长度初值 `max(256, 8L)`；
- 记录每秒行数、RSS、块间相关、QR 误差和单块方差。

Pilot 后按以下规则冻结生产参数：

- 若相邻 block 的相关系数绝对值 \(>0.1\)，block 长度翻倍；
- 若 QR interval 1 与 5 的差超过 pilot 标准误的 0.1 倍，生产取 1；否则取 5；
- 生产总行数由目标 `SE(phi_L) <= min(2e-6, 0.05*|Casimir signal at L|)` 反推；
- 若预计单 cell 超过 24 小时，优先增加 replica 数而非延长单条轨迹；
- 单个 \(L\) 的有效独立块数不得少于 200。

#### 3C. 生产

候选尺寸：

\[
L=6,8,10,12,14,16,20,24,30,32.
\]

Pilot 后可删除成本失控的最大尺寸，但进入最终拟合的尺寸不得少于 5 个，且必须包含至少 3 个 \(L\ge16\) 的尺寸。每个 \(L\) 初始 32 个 replica；统计预算不足时扩展到 64 或 128，不能重启并覆盖已有 seed。

额外交叉运行：

- \(p=p_c\pm4\times10^{-7}\)，只用一组代表性尺寸检查临界点误差；
- \(p=0\) 检查 clean 极限；
- 同无序样本的 P/AP 缺陷自由能检查临界行为；
- 至少一个尺寸比较内部实现和上游实现的完整分布。

#### 3D. 拟合与验收

- 主拟合：M1，\(\phi_L=\phi_\infty+\pi c/(6L^2)+a_4/L^4\)；
- 稳定性拟合：大尺寸 M0，逐步提高 \(L_{\min}\)；
- 每次 bootstrap 在每个 \(L\) 内重采样完整 replica/独立 block，再重新拟合；
- 至少 5000 次有效 bootstrap；记录奇异或失败次数；
- 报告 bootstrap 中位数、68% 和 95% 区间、\(\chi^2/{\rm dof}\)、\(L_{\min}\)、模型和残差。

通过门槛：

- 95% CI 与 \(0.464\pm0.004\) 相交；
- M0/M1 和相邻 \(L_{\min}\) 结果相差不超过合并 1.5 个标准差；
- \(p_c\) 误差传播小于当前统计误差；
- 最大尺寸的 Casimir 信号至少是其误差的 5 倍；
- 内部与上游基线无统计显著差异。

### 阶段 4：弱自对偶 Born 临界点

#### 4A. 小尺寸完全枚举

对 \(L=2,4\)、短传播长度执行：

1. 枚举全部允许的 \(e,m\) 记录；
2. 直接计算并归一化 \(|Z(e,m)|^2\)；
3. 比较逐步条件 Born 采样器的精确概率；
4. 比较 Gaussian 和显式自旋/TN 振幅；
5. 检查真空 Wilson loop；
6. 检查 \(\langle e\rangle=\langle m\rangle=3/8\)。

通过门槛：

- 全分布总变差距离 \(<10^{-10}\)（精确算法对精确枚举）；
- Monte Carlo smoke 的分布在预先计算的 95% 多项分布区间内；
- 禁止扇区的采样次数严格为 0；
- log-probability 的链式和等于直接归一化概率的对数。

#### 4B. Gaussian Born 轨迹和 Lyapunov 内核

每层按固定、写入 manifest 的门次序执行：

1. 从当前 Gaussian 状态计算当前测量的 \(P(+)\)、\(P(-)\)；
2. 以独立 RNG 子流抽样结果；
3. 累积归一化的 `log_conditional_probability`；
4. 更新协方差矩阵、轨迹 `log_Z`、范数和 Majorana 传输矩阵；
5. 每 `qr_interval` 层 QR，累积 Lyapunov 指数；
6. 每个 block 输出 Shannon rate、最大指数、低位指数、缺陷密度、正交误差和扇区标签；
7. burn-in 数据只用于稳定状态诊断，不进入物理平均。

低位谱按文献约定由 \(R\) 对角得到单粒子 \(\epsilon_n\)，再组合

\[
E_m\simeq\frac{2\pi}{L}
\left(\Delta_m-\frac{c_{\rm eff}}{12}\right).
\]

主中心荷从 Shannon/Casimir 项提取；完整谱是交叉验证和可选增强项。

#### 4C. Pilot

- 尺寸：\(L=4,6,8,10,12\)；
- 每尺寸 16 条独立轨迹；
- burn-in 初值 \(50L\)；
- 测量长度初值 \(2^{14}\) 层；
- QR interval 比较 1、2、4、8；
- block 长度初值 `max(512, 16L)`。

冻结生产参数的规则与 RBIM 相同，另加：

- \(e/m\) 密度偏离 \(3/8\) 超过 4 个标准误则立即停止；
- 空间和时间相关长度比偏离 1 超过 1%，不得继续假定 \(\alpha=1\)；
- 条件概率小于 0、超过 1 或归一化误差 \(>10^{-12}\) 均为硬失败；
- QR 正交误差 \(>10^{-9}\) 的 cell 不进入聚合。

#### 4D. 生产

候选尺寸：

\[
L=6,8,10,12,16,20,24,30.
\]

- 每尺寸初始 64 条独立轨迹；
- 每条生产长度由 pilot 反推，目标是
  `SE(h_L) <= min(2e-6, 0.05*|Casimir signal at L|)`；
- 最大尺寸若误差不足，增加到 128 条轨迹；
- 不允许把多个从同一 checkpoint 分叉的轨迹当成独立 burn-in 样本。

独立交叉验证：

- 对 \(L\le8\) 使用局部 Metropolis TN 采样；
- 接受率
  \(\min[1,\exp(2\Delta\ln|Z|)]\)；
- 报告热化、自相关时间和两种采样器的 observable 差异；
- Metropolis 结果不用于替代主采样器缺失的全局归一化常数。

#### 4E. 拟合与验收

主拟合：

\[
h_L=h_\infty-\frac{\pi c_{\rm Casimir}}{6L^2}
              +\frac{b_4}{L^4}.
\]

bootstrap 和 \(L_{\min}\) 流程与 RBIM 相同。

通过门槛：

- 95% CI 与 \(0.447\pm0.001\) 相交；
- \(e/m\) 密度与 \(3/8\) 一致；
- 独立各向同性检查支持 \(\alpha=1\)；
- M0/M1 和 \(L_{\min}\) 稳定性满足 RBIM 同类门槛；
- 逐步 Born 采样与小尺寸枚举、Metropolis 交叉验证一致。

## 6. 统计分析细则

### 6.1 误差层级

误差按以下层级传播：

```text
时间/行 block
  → 单条独立 replica 的均值
  → 同一 L 的 disorder/trajectory ensemble
  → 对全部 L 的 bootstrap Casimir 拟合
  → 拟合窗口和次领项的系统误差包络
```

禁止把高度相关的逐行数据当成独立样本。若 integrated autocorrelation time 可稳定估计，同时报告它和 block 长度；否则使用保守的倍增 block 稳定性测试。

### 6.2 预先声明的拟合

每次命令只运行一个明确指定的模型和窗口，不能自动遍历后挑最接近目标的结果。

- M0：`basis = [1, L^-2]`；
- M1：`basis = [1, L^-2, L^-4]`；
- 主模型：M1；
- 主窗口：pilot 后在不看目标偏差的条件下，选择最小的、残差无趋势且 M1 条件数可接受的 \(L_{\min}\)；
- M0 仅在较大 \(L_{\min}\) 上作交叉验证；
- 结果表必须列出所有预先声明的窗口，包括“不好看”的结果。

拟合器输出参数相关矩阵、设计矩阵条件数、标准化残差和 bootstrap 分布。若条件数 \(>10^{10}\)，该拟合标记为病态，不用于主结论。

### 6.3 目标值的使用

目标值只用于最终验收，不用于：

- 调参到目标；
- 选择 \(L_{\min}\)；
- 删除 outlier；
- 决定随机种子；
- 终止 bootstrap。

任何剔除必须是预先定义的数值失败、manifest 失败或明确记录的硬件/软件异常，并写入 `exclusions.json`。

## 7. ws0、Slurm 和无共享存储执行设计

### 7.1 不可违反的本地约束

- `ws0` 是登录节点，只做编辑、版本控制、轻量文件检查、排队、监控和结果汇总；不进行编译 benchmark、矩阵计算或 Monte Carlo。
- 仓库当前没有 `skills/using-slurm/profiles/active.toml`。第一次提交前必须把三份本地权威文档转换为并人工复核一个 ws0 本地集群配置，或让自定义 wrapper 显式携带同等信息；配置完成前只能生成通用脚本和做静态检查，不能采用未知默认分区或资源值。
- 计算节点之间以及与 ws0 没有共享项目目录。
- 作业搬运必须参考 `/home/ystu/command/submit_.sh`：
  开始时从 ws0 `rsync` 固定源快照，结束时把结果 `rsync` 回 ws0。
- 提交前重新读取：
  - `/home/ystu/command/SlurmResources.md`
  - `/home/ystu/command/ClusterHardware.md`
  - `/home/ystu/command/submit_.sh`
- CPU-only 作业仍受“每个未分配 GPU 预留 4 个 CPU”的规则约束；
  不得根据 QOS 上限假设物理资源一定可用。
- `normal` QOS 同时 RUNNING 最多 8 个作业、RUNNING+PENDING 最多 16 个；
  array 并发上限初始设为 `%8`。

### 7.2 作业类型

本项目初始全部为 CPU 作业：

- dense QR、Eigen/MKL、PFAPACK 和传输矩阵主要使用 CPU；
- 不为“占住节点”无故申请 GPU；
- 只有独立 CUDA prototype 显示实际加速后，才另写 GPU 资源方案。

初始资源模板（仅用于 feasibility test，正式值由队列探测和 pilot ratify）：

| 作业 | CPU | 内存 | 时间 | array 并发 |
|---|---:|---:|---:|---:|
| 编译/单元测试 | 4 | 8 GiB | 00:30:00 | 1 |
| 小系统/pilot cell | 4 | 16 GiB | 02:00:00 | 4 |
| 生产 cell | 4–8 | 16–32 GiB | 最多 24:00:00 | 最多 8 |

不得在计划阶段硬编码节点。每次真实提交前用 `sinfo`、`squeue` 和资源文档比较 ws1–ws5 的空闲 CPU、内存和作业负载，再确定节点/分区；ws2 的坏核以及 ws5 的保留核交给 Slurm 分配约束处理，不手写 CPU id。

### 7.3 无共享存储 wrapper

`slurm/submit_ws0.sh` 负责：

1. 检查当前 git 状态并记录到 `source.json`；
2. 拒绝静默发送未获授权的 dirty worktree；
3. 生成只包含所需代码、配置和锁文件的源归档/checksum；
4. 运行 `sbatch --test-only` 或等效 feasibility 检查；
5. 探测并明确记录最终 partition/节点选择；
6. 提交 array 并保存 job id、cell map 和 exact sbatch 命令；
7. 只重提没有 success manifest 的 cell。

计算节点脚本采用每 job 独立目录，例如：

```bash
work_root="${TMPDIR:-/tmp}/born-critical/${SLURM_JOB_ID}/${SLURM_ARRAY_TASK_ID:-0}"
mkdir -p "$work_root"/{src,result,logs}
```

随后：

1. 从 `ystu@ws0:/home/ystu/...` 拉取固定源归档和 `run_spec.json`；
2. 校验 checksum；
3. 在本地 scratch 解包、创建/激活环境；
4. 读取 opaque `cell_id`，绝不在 sbatch 脚本硬编码扫描轴；
5. 运行 cell，将 stdout/stderr 同时写入本地 `logs/run.log`；
6. 使用 `trap` 捕获 `EXIT TERM INT`，先写 manifest，再把该 cell 目录原子地回传到 ws0；
7. 回传到临时目录，校验后 rename，防止半写结果被聚合；
8. 作业结束后由 Slurm/scratch 生命周期清理本地副本。

回传失败时 manifest 留在计算节点本地日志中，调度状态不能视为科学成功；只有 ws0 上 checksum 正确的 success manifest 才完成 cell。

### 7.4 提交、监控和恢复顺序

每个 run 严格执行：

1. `git status --porcelain`，确认要发送的源范围；
2. `sinfo`/`squeue` 探测队列并确认资源选择；
3. 用 exact sbatch 脚本执行 test-only feasibility；
4. 先提交一个 smoke cell；
5. 运行后 1–3 分钟确认不是只处于 PENDING；
6. 首次 RUNNING 后查看日志，确认实际进入计算；
7. smoke manifest 和数值 sanity check 通过后提交 pilot array；
8. pilot 聚合并冻结 production run spec；
9. production array 最多 8 个并发；
10. 用 `sacct` 加 manifest 分类每个 cell：
    success、OOM、timeout、logic failure、not converged、transfer failure；
11. 只在明确批准后重提失败 cell，且保留原失败记录；
12. 多小时作业每 30–60 分钟检查状态和至少一个运行日志。

## 8. 预期命令接口

以下是实现后应成立的接口；本计划阶段不执行它们：

```bash
# 生成不可变 cell map
python tracks/qmc/solutions/Born-Critical-122/scripts/make_run_spec.py \
  --config tracks/qmc/solutions/Born-Critical-122/configs/rbim-pilot.json \
  --output tracks/qmc/results/born-critical/rbim-pilot-v1/run_spec.json

# 在计算节点运行一个 opaque cell
python tracks/qmc/solutions/Born-Critical-122/scripts/run_cell.py \
  --run-spec /local/path/run_spec.json \
  --cell-id rbim-L08-r003 \
  --output /local/path/result

# ws0 只做提交/监控/文件操作
bash tracks/qmc/solutions/Born-Critical-122/slurm/submit_ws0.sh \
  --run tracks/qmc/results/born-critical/rbim-pilot-v1 \
  --test-only

bash tracks/qmc/solutions/Born-Critical-122/slurm/submit_ws0.sh \
  --run tracks/qmc/results/born-critical/rbim-pilot-v1 \
  --array-concurrency 4

# 完成回传后，在允许的计算环境执行聚合与拟合
python tracks/qmc/solutions/Born-Critical-122/scripts/aggregate.py \
  --run tracks/qmc/results/born-critical/rbim-production-v1

python tracks/qmc/solutions/Born-Critical-122/scripts/fit_casimir.py \
  --run tracks/qmc/results/born-critical/rbim-production-v1 \
  --observable phi \
  --model M1 \
  --lmin 8 \
  --bootstrap 5000
```

由于 ws0 不开放计算能力，最后两条若聚合涉及大 parquet 或 5000 次 bootstrap，也必须包装为短 Slurm CPU 作业；ws0 仅查看已经回传的摘要 JSON/CSV/PNG。

## 9. 报告与图表清单

最终报告至少包含：

1. 三个模型的定义、映射、边界条件、扇区和耦合规范；
2. Born 条件采样算法伪代码；
3. 传输矩阵/Gaussian 演化和 QR 稳定化说明；
4. clean Ising 的 \(\phi_L\) 对 \(1/L^2\) 图和 \(c=1/2\) 拟合；
5. Nishimori 每个 \(L\) 的均值、误差、有效样本数和 Casimir 拟合；
6. 弱自对偶每个 \(L\) 的 Shannon rate、\(e/m\) 密度和 Casimir 拟合；
7. 两个正式结果随 \(L_{\min}\) 的稳定性图；
8. QR interval、block size、轨迹长度和自相关诊断；
9. 目标值与本项目 68%/95% CI 的对照表；
10. 失败 cell、剔除理由和资源用量；
11. 代码 commit、环境锁、run id 和复现命令。

图的原始数据必须同时保存；报告不得只给截图。

## 10. 里程碑和停止条件

| 里程碑 | 产物 | go/no-go |
|---|---|---|
| M0 规范冻结 | 枚举测试、环境锁、固定上游 commit | 第 0 阶段全部通过 |
| M1 数值内核 | QR、RNG、checkpoint、拟合测试 | 无稳定性失败 |
| M2 Ising | \(c=0.5\) 图表和 fit JSON | 相对误差 <0.5% |
| M3 RBIM pilot | 性能/方差/资源报告 | 可在配额内达到目标 SE |
| M4 RBIM production | \(0.464(4)\) 结果 | 第 3D 节门槛通过 |
| M5 自对偶枚举与 pilot | Born 分布、密度、各向同性验证 | 第 4A/4C 节门槛通过 |
| M6 自对偶 production | \(0.447(1)\) 结果 | 第 4E 节门槛通过 |
| M7 提交材料 | 代码、results、短报告 | 全部 manifest 和复现审计通过 |
| M8 可选扩展 | Lyapunov 谱或开放研究结果 | 仅在 M7 后 |

立即停止并回到诊断的条件：

- Ising warm-up 未通过；
- Born 小系统分布不一致；
- \(\alpha=1\) 检查失败；
- 概率、QR 或 log-weight 出现非有限值；
- 最大尺寸 Casimir 信号被噪声淹没，且按 pilot 外推会突破现有配额；
- 不同 QR interval 或独立实现给出超过统计误差的偏差；
- 回传 manifest/checksum 不完整。

## 11. 已知风险和缓解

| 风险 | 后果 | 缓解 |
|---|---|---|
| 自由能/Shannon 符号混淆 | 得到负的或错误中心荷 | 两套显式公式；Ising 解析测试；禁止取绝对值 |
| Nishimori \(\beta\) 约定差一倍 | 临界点完全错误 | 小系统 Boltzmann 比值测试；内部只用 \(K\) |
| 把 Born 无序当 iid | 弱自对偶结果物理错误 | 逐步归一化条件采样；精确枚举与 Metropolis 双检 |
| Jordan–Wigner/真空扇区错误 | 谱和 Casimir 系数错误 | 枚举比较、Wilson loop 硬断言 |
| 乘积矩阵数值溢出 | Lyapunov 指数偏差/NaN | 周期 Householder QR、log 累积和 interval 扫描 |
| 相关样本低估误差 | 虚假的高精度 | 独立 replica、blocking、bootstrap 全流程 |
| 按目标值挑拟合窗口 | 结果偏倚 | 预注册模型/窗口规则，保留全部拟合 |
| ws0 被误用作计算节点 | 违反集群规定 | 所有测试、编译 benchmark、MC 和 bootstrap 经 Slurm |
| 无共享存储导致半结果 | 数据丢失或被误聚合 | job-local scratch、trap 回传、临时目录和 checksum |
| array 超出 QOS/CPU 预留 | 排队或拒绝 | probe、test-only、并发上限 8、按 GPU 空闲量保留 CPU |
| 单 cell 过长 | timeout 后损失 | checkpoint、24 h 上限、增加 replica 而非无限延长 |

## 12. 第一轮实施清单

计划获确认后，按以下顺序开始，不越级：

- [x] 建立第 4 节代码目录和环境锁；
- [x] 实现耦合/符号/边界规范及小系统枚举；
- [x] 在 Slurm 计算节点完成环境编译和单元测试；
- [x] 实现通用 QR、RNG、manifest、checkpoint 与拟合器；
- [x] 完成 clean Ising，达到 M2（job `17178`）；
- [x] 接入固定版本 RBIM 上游基线；
- [x] 生成 RBIM pilot run spec，先 test-only 再单 cell；
- [x] 根据 pilot 冻结 RBIM production 参数；
- [x] 完成 RBIM production 与统计验收；
- [x] 实现自对偶 Gaussian Born sampler 和精确枚举测试；
- [x] 生成自对偶 pilot，验证缺陷密度与各向同性；
- [x] 冻结并完成自对偶 production；
- [x] 生成报告、图、运行审计和复现说明；
- [x] 三项必做结果全部通过；完整谱与开放转变留作可选扩展。

这份计划不把“Slurm 作业完成”视为科学完成。最终完成的唯一依据是：已回传、校验成功、可从 manifest 和原始 block 数据重建，并通过上述物理与统计门槛的结果。
