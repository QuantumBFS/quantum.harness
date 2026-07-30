# quantum.harness 仓库结构概览

> 本文档描述 **Harnessing Quantum 2026** 挑战提交分支 `challenge/mps-dissipative-floquet`（team-fork `EricLi-0321/quantum.harness`，PR #207）的代码库结构。该分支基于上游 `QuantumBFS/quantum.harness`，并围绕挑战 [#123](https://github.com/QuantumBFS/quantum.harness/issues/123)（多体耗散 Floquet 系统，超越 Markov 近似）展开。

---

## 1. 仓库定位

`quantum.harness` 是一个面向量子多体问题的计算研究 harness：

- 以 **模型卡**（`.knowledge/models/`）和 **物理卡**（`.knowledge/physics/`）组织领域知识；
- 以 **Skills**（`skills/`）提供可对话调用的研究流程；
- 以 **Tracks**（`tracks/`）存放各方法赛道（ED、MPS、QMC、QCS、PEPS、PolyOpt 等）的参考实现与挑战解答；
- 以 `scripts/` 提供脚本化的辅助工具（参数扫描、集群守护、网站建设等）。

本 PR 的工作集中在 **MPS 赛道**的 `tracks/mps/solutions/` 下，分为两条线：

1. **严格单自旋复刻**：`reproduction/floquet_spin_boson/`；
2. **多体研究原型**：`FloIM/`（边界浴驱动 Ising 链的增广 MPS + Redfield–Magnus 基准）。

---

## 2. 顶层文件与目录

| 路径 | 说明 |
|------|------|
| `README.md` | 项目简介、安装入口、示例提示词、方法贡献者列表。 |
| `AGENTS.md` | 给 AI agent 的完整操作规范：确认 setup、验证流程、UI/UX、集群使用、技能管理等。 |
| `Makefile` | 工作流入口，`make help` 列出可安装工具与目标；`make skills` 同步 Ion 管理的技能。 |
| `Ion.toml` / `Ion.lock` | Ion 技能管理器的配置与锁定文件，定义本仓库依赖哪些本地/远程技能。 |
| `.knowledge/` | 领域知识库：模型卡、物理卡、方法论文献、约定与极限速查。 |
| `skills/` | 对话式 Skills（`SKILL.md`），例如 `/method-mps`、`/reproduce-paper`、`/using-slurm` 等；每个工具 skill 通常配有 `stack.toml` 说明软件栈。 |
| `scripts/` | 可独立运行的 Python 辅助脚本：参数扫描、缩放拟合、集群探测、网站建设、测试套件等。 |
| `design/` | 非代码资产（如 T 恤设计）。 |
| `docs/` | 设计文档与本文档。关键文件包括 `uniTEMPO-vs-PT-TEBD-comparison.md`、两篇 `2026-07-28-*` 多体设计稿。 |
| `tracks/` | 各方法赛道的参考实现与学生解答。 |
| `julia-env/` | 全局 Julia 环境配置，部分脚本默认使用。 |
| `viz/` | 可视化辅助与示例。 |

---

## 3. Skills 目录（与本项目最相关）

`skills/` 下每个子目录对应一个可对话调用的 Skill。与本 PR 工作直接相关的有：

| Skill | 文件 | 用途 |
|-------|------|------|
| `method-mps` | `skills/method-mps/SKILL.md` | MPS/DMRG/TEBD 方法路由与参数建议。 |
| `using-itensors` | `skills/using-itensors/SKILL.md` | ITensors.jl 使用指南。 |
| `using-tenpy` | `skills/using-tenpy/SKILL.md` | TeNPy（Python）使用指南。 |
| `using-slurm` | `skills/using-slurm/SKILL.md` + `profiles/*.toml` | 集群提交与分区配置。 |
| `reproduce-paper` | `skills/reproduce-paper/SKILL.md` + `build_report.py` | 论文复现流程与 HTML 报告生成。 |
| `report` | `skills/report/SKILL.md` + `render_report.py` | 渲染自包含 HTML 报告。 |
| `cross-method-check` | `skills/cross-method-check/SKILL.md` | 独立方法交叉验证流程。 |

---

## 4. Tracks 目录

`tracks/` 按计算方法分赛道：

| 赛道 | 路径 | 说明 |
|------|------|------|
| ED | `tracks/ed/` | 精确对角化赛道说明与参考论文。 |
| MPS | `tracks/mps/` | 矩阵乘积态 / DMRG / TEBD 赛道，本 PR 工作落于此处。 |
| QMC | `tracks/qmc/` | 量子蒙特卡洛赛道说明。 |
| QCS | `tracks/qcs/` | 量子电路模拟赛道说明。 |
| PEPS | `tracks/peps/` | 二维张量网络赛道说明。 |
| PolyOpt | `tracks/polyopt/` | 多项式优化 / SDP 赛道说明。 |
| agent-kb | `tracks/agent-kb/` | AI agent 与知识库相关实现。 |

### 4.1 `tracks/mps/solutions/` 结构

```text
tracks/mps/solutions/
├── FloIM/                          # 本 PR 的多体研究原型
│   ├── README.md                   # FloIM 项目总览、当前证据、运行命令
│   ├── augmented_tempo_notes.md    # 增广 MPS 实现审计、数据结构、误差分析
│   ├── env_floquet/                # Julia 项目环境（Project.toml / Manifest.toml）
│   ├── src/                        # 库代码
│   ├── test/                       # 检查与研究脚本
│   ├── plot/                       # 绘图脚本
│   └── result/                     # 已 push 的精选图片（git-tracked）
└── reproduction/
    ├── floquet_spin_boson/         # 严格单自旋复刻（Mickiewicz et al. PRL 2026）
    │   ├── README.md
    │   ├── envs/current/           # 当前可运行 Julia 环境
    │   ├── envs/paper/             # 论文时期环境占位（未解析）
    │   ├── src/                    # 模块代码（FloquetSpinBoson.jl）
    │   ├── test/                   # 测试套件
    │   ├── scripts/                # 复现 Fig.2/3/5 与收敛性、基准的生产脚本
    │   ├── configs/                # TOML 参数配置
    │   └── validation/             # 已记录的验证点（git-tracked）
    └── unitempo_partial/           # 基于外部 UniformTEMPO.jl 的独立部分复刻
        ├── README.md
        ├── scripts/                # 独立 runnable 脚本
        └── validation/             # 与作者数据对比的图和指标
```

---

## 5. FloIM 多体研究原型（`tracks/mps/solutions/FloIM/`）

### 5.1 物理目标

将 Mickiewicz–Link–Strunz 的 **Floquet 影响泛函（Floquet-IF）**从单自旋推广到一维边界浴驱动 Ising 链：

```
H_sys(t) = Σ_{i=1}^{N-1} J σ_z^i σ_z^{i+1}
           + Σ_i [ (h_z + A cos(ω_d t)) σ_z^i + h_x σ_x^i ]
```

仅 **左端点（i=1）**耦合零温 Ohmic 浴，因此影响泛函完全等价于已验证的单自旋 uniTEMPO IF，记忆键维 χ_b 不随 N 增长。

### 5.2 源文件 `src/`

| 文件 | 说明 |
|------|------|
| `augmented_tempo.jl` | 核心模块 `AugmentedTEMPO`。定义增广 MPS 数据结构、TEBD 演化（ onsite / bond / bath 步）、capped-MPS 观测量（期望、键流、能量密度、纯度等）。 |
| `redfield_ising.jl` | 模块 `RedfieldIsing`。多体 Floquet–Magnus + Redfield 基准：静态有效哈密顿量、Bohr 频率形式的 Liouvillian、稠密演化与稳态。 |

### 5.3 测试/研究脚本 `test/`

| 文件 | 说明 |
|------|------|
| `m0_m1_checks.jl` | M0/M1 验证：N=1 对接单自旋 Fig.2；N=4 J=0 对接论文数据；N=10 封闭链对接 Krylov ED。 |
| `m1a_error_analysis.jl` | N=6 纯 Trotter 误差标度（δt 收敛序列），分离截断与 Trotter 贡献。 |
| `m1a_error_analysis_n10.jl` | N=10 的 δt / χ_s 对照（大计算，建议上集群）。 |
| `test_merged_bonds.jl` | `merge_bonds` 优化验证：封闭系统 + 真实浴的对照实验。 |
| `m3_redfield_check.jl` | N=1/2/3 的 Redfield–Magnus 与增广 MPS 逐帧/稳态对照。 |
| `m4_heat_current.jl` | 热流算符验证、NESS 连续性、j̄(ω_d) 初步扫描。 |
| `m4a_fig3_reproduction.jl` | 单自旋 Fig.3 六个参数组的热流谱复刻脚本。 |
| `m4b_heat_current_n4.jl` | 边界耦合 N=4 热流谱探索脚本。 |
| `floquet_spin_boson_fig2.jl` | 早期单自旋 Fig.2 复刻脚本，作为验证基准来源。 |
| `diag_m4a_corr.jl` | 相关函数对角化辅助脚本。 |

### 5.4 绘图脚本 `plot/`

| 文件 | 说明 |
|------|------|
| `m4a_fig3.jl` | 绘制 Fig.3 六个参数组的 `j̄(ω)` 对比图（ours vs Zenodo 作者数据）。 |
| `m4b_n4_vs_n1.jl` | 绘制 N=4 与 N=1 热流谱对比。 |

### 5.5 说明文档

| 文件 | 说明 |
|------|------|
| `README.md` | 团队、科学目标、双层实现、当前证据表、复现命令、剩余工作。 |
| `augmented_tempo_notes.md` | 数据结构、与 `UniformTEMPO.jl` 的约定、函数地图、MPS 观测量设计、验证结果与误差归因、已踩过的坑。 |

---

## 6. 严格单自旋复刻（`tracks/mps/solutions/reproduction/floquet_spin_boson/`）

### 6.1 物理目标

复现 Mickiewicz, Link & Strunz, *PRL* **136**, 200201 (2026) 的图 2、3、5：

```
H_sys(t) = Ω/2 σ_x + ε_d cos(ω_d t) σ_z   （横向驱动）
或  H_drive = ε_d cos(ω_d t) σ_x           （纵向驱动）
S = σ_z,  J(ω) = α ω e^{-ω/ω_c},  T = 0
```

### 6.2 源文件 `src/`

| 文件 | 说明 |
|------|------|
| `FloquetSpinBoson.jl` | 顶层模块入口。 |
| `model.jl` | 系统哈密顿量、驱动、浴关联函数等物理定义。 |
| `bath.jl` | 零温 Ohmic 浴关联函数与谱函数。 |
| `uniform_if.jl` | 构建/缓存 uniTEMPO 均匀影响泛函 MPO。 |
| `floquet_operator.jl` | Floquet 一周期传播子、Floquet 谱与 kick 算符。 |
| `steady_state.jl` | 通过周期映射主本征矢求 Floquet 稳态。 |
| `correlations.jl` | 有序两点关联函数及其周期/衰减分解。 |
| `heat_current.jl` | 连续热流谱 `j̄(ω)` 与谐波 δ 峰权重。 |
| `redfield_magnus.jl` | Redfield–Magnus 基准实现。 |
| `augmented_step.jl` | 增广步传播子（矩阵-free）。 |
| `convergence.jl` | 收敛性诊断。 |
| `diagnostics.jl` | 物理一致性检查（正定性、残差、C(0)、尾衰减等）。 |
| `reference_data.jl` | 读取 Zenodo 作者 CSV 数据。 |
| `checkpoint.jl` | 可恢复的检查点与 manifest 管理。 |
| `config.jl` | 配置解析与默认值。 |

### 6.3 测试 `test/`

| 文件 | 说明 |
|------|------|
| `runtests.jl` | 完整测试套件入口。 |
| `test_model.jl` | 模型与浴关联函数测试。 |
| `test_uniform_if.jl` / `test_uniform_if_cli.jl` | 影响泛函构建与 CLI 缓存测试。 |
| `test_floquet_operator.jl` | Floquet 传播子测试。 |
| `test_steady_state.jl` | 稳态求解测试。 |
| `test_correlations.jl` / `test_correlation_decomposition.jl` | 关联函数测试。 |
| `test_heat_current.jl` | 热流计算测试。 |
| `test_fig5.jl` | Fig.5 总热流测试。 |
| `test_regression.jl` | 回归测试。 |
| `test_convergence.jl` | 收敛性测试。 |

### 6.4 生产脚本 `scripts/`

| 文件 | 说明 |
|------|------|
| `reproduce_fig2.jl` | 复现 Fig.2 两面板暂态。 |
| `reproduce_fig3.jl` | 复现 Fig.3 热流谱（支持并行、断点续跑）。 |
| `reproduce_fig5.jl` | 复现 Fig.5 总热流扫描。 |
| `run_convergence.jl` | 多轴收敛性扫描。 |
| `benchmark.jl` | 性能基准。 |
| `cache_uniform_if.jl` | 预构建/刷新 IF 缓存。 |
| `refresh_redfield_baseline.jl` | 刷新 Redfield 基准数据。 |
| `plot_results.py` | Python 绘图与对比（Fig.2/3/5）。 |

### 6.5 配置 `configs/`

| 文件 | 说明 |
|------|------|
| `fig2.toml` / `fig3.toml` / `fig5.toml` | 对应图形的完整/生产参数。 |
| `quick.toml` / `fig*_quick.toml` | 快速冒烟参数。 |
| `fig3_cluster_quick.toml` | 集群快速验证配置。 |

### 6.6 已记录的验证点 `validation/`

| 目录 | 内容 |
|------|------|
| `20260730-fig2/` | 完整 Fig.2 两面板复刻（严格 `1e-10` 压缩）。 |
| `20260729-fig3-longitudinal-wd5/` | 纵向驱动 `ω_d=5Ω` 严格验证点。 |
| `20260730-fig3-transversal-wd1/` | 横向驱动 `ω_d=1Ω` 严格验证点（8192 lag）。 |
| `20260730-fig5-peak/` | `ω_d=1.25Ω` 横向峰的代表性验证点。 |

---

## 7. UniTEMPO 独立部分复刻（`tracks/mps/solutions/reproduction/unitempo_partial/`）

使用外部 `UniformTEMPO.jl` 包直接复现 Fig.2–4，并运行边界浴 Ising 链热流试点。

| 路径 | 说明 |
|------|------|
| `scripts/unitempo_fig2.jl` / `unitempo_fig3.jl` / `unitempo_fig4_top.jl` | 直接复现 Fig.2/3/4。 |
| `scripts/compare_unitempo_fig*.jl` | 与 Zenodo 作者数据对比。 |
| `scripts/unitempo_boundary_ising_floquet_heat.jl` | L=3 边界浴 Ising 链热流试点。 |
| `validation/20260730-fig2-fig4/` | 与作者数据对比的图和指标。 |
| `validation/20260730-boundary-ising-floquet-heat-L3/` | 能量平衡、周期性检查、热流周期图。 |

---

## 8. 设计文档 `docs/`

| 文件 | 说明 |
|------|------|
| `uniTEMPO-vs-PT-TEBD-comparison.md` | 对比 Fux23（PT-TEMPO+TEBD）与 Link24（uniTEMPO），提出三条多体推广路线 A/B/C。 |
| `2026-07-28-floquet-unitempo-manybody-ising.md` | 边界浴驱动 Ising 链 + 增广 MPS 的完整设计方案：路径积分、均匀 IF、增广 MPS 表示、TEBD 排序、观测量、误差分析。 |
| `2026-07-28-redfield-benchmark-manybody-ising.md` | 同一模型的 Redfield–Magnus 多体基准推导：Born 二阶、Floquet–Magnus 约化、kick 免疫性、静态有效模型生成元。 |
| `github-team-push-guide.md` | 团队 fork 协作推送指南。 |
| `repository-overview.md` | 本文档。 |

---

## 9. 结果保存在哪里

本仓库遵循 **“大输出不入库，精选证据随 PR 走”** 的原则：

| 类型 | 本地位置（主工作树 `/home/philia/quantum.harness`） | PR 中可见位置（`quantum-harness-pr`） | 是否 git-tracked |
|------|--------------------------------------------------|--------------------------------------|------------------|
| 原始数值结果（CSV、稳态、关联、缓存、大图） | `tracks/mps/results/<timestamp>-<tag>/` | 不在 fork 中（被 `.gitignore` 忽略） | 否 |
| 严格单自旋验证摘要/检查点 | `tracks/mps/results/...` | `tracks/mps/solutions/reproduction/floquet_spin_boson/validation/` | 是 |
| 多体研究原型精选图 | `tracks/mps/results/20260729-augmps-m4a/` 等 | `tracks/mps/solutions/FloIM/result/` | 是 |
| HTML 报告 | `tracks/mps/results/<timestamp>-<tag>/report.html` | 未 push | 否 |
| 影响泛函缓存 | 运行时生成的大二进制文件 | 未 push | 否 |

> **复现时需要**：从 Zenodo 记录 [19593671](https://zenodo.org/records/19593671) 下载作者原始 CSV，放到本地 `tracks/mps/results/` 下对应目录，再运行脚本生成输出。

---

## 10. 常用运行入口

```bash
# 1. 严格单自旋完整测试套件
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$PROJ/envs/current" "$PROJ/test/runtests.jl"

# 2. 复现 Fig.2
julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig2.jl" \
  "$PROJ/configs/fig2.toml" /path/to/fig_2 output/fig2

# 3. 复现 Fig.3（并行 + 断点续跑）
julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig3.jl" \
  --parallel phases --resume --reference-dir /path/to/fig_3 \
  "$PROJ/configs/fig3.toml" output/fig3

# 4. FloIM 多体原型小检查
FLOIM=tracks/mps/solutions/FloIM
julia --project="$FLOIM/env_floquet" -e 'import Pkg; Pkg.instantiate()'
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$FLOIM/env_floquet" "$FLOIM/test/test_merged_bonds.jl"

# 5. Python 绘图测试
python -m pytest -q scripts/tests/test_floquet_plot_results.py
```

---

## 11. 分支与 Fork 关系

- **上游**：`QuantumBFS/quantum.harness`
- **团队 fork**：`EricLi-0321/quantum.harness`（`team-fork`）
- **个人 fork**：`entanglement99/quantum.harness`（`my-fork`）
- **本 PR 分支**：`challenge/mps-dissipative-floquet`
- **本地主工作树**：`/home/philia/quantum.harness`（未提交的多体代码与大量结果）
- **本地 PR 工作树**：`/home/philia/quantum-harness-pr`（用于 push 到 team-fork）

日常开发在主工作树进行；需要提交到 PR 时，将相关代码/图/验证点复制或 push 到 `quantum-harness-pr` 的 `challenge/mps-dissipative-floquet` 分支。
