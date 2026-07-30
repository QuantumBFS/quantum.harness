# 2D_TN_Challenge

**二维横场 Ising 模型有限温张量网络（METTS）基准项目** —— 以 METTS（Minimally Entangled Typical Thermal States）为主算法路线，PEPO 为探索性对照路线，与同尺寸无符号问题 QMC 参考结果系统比较，验证有限温张量网络方法在二维量子多体系统中的准确性、收敛性、稳定性与计算代价。项目同时提供数据处理、收敛分析、图像生成、运行元数据记录和技术报告自动生成的完整流程。

作者：Jing Yang, Peng Peng / 2D-TN-Team

---

## 项目目的

研究对象为具有开放边界条件（OBC）的二维横场 Ising 模型：

$$H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z-h\sum_i\sigma_i^x,\qquad J=1.$$

主基准系统：

- 二维正方格子，$10\times10$，OBC；
- 横场参数 $h/J\in\{2.5,\ 3.0,\ 3.5\}$，取在量子临界点 $h_c/J\approx3.044$ 附近；
- 逆温度范围 $\beta J\in[0.1,\,1.0]$。

其中 $h/J=3.0$ 附近是本项目的重点压力测试区域：能隙较小、关联长度增加，有限温张量网络压缩更具挑战性。模型无符号问题，QMC（SSE / worm）提供同尺寸数值精确基准。

项目计算并验证以下热力学量：

$$f=-\frac{\ln Z}{\beta N},\qquad u=\frac{\langle H\rangle}{N},\qquad C=\frac{\beta^2\big(\langle H^2\rangle-\langle H\rangle^2\big)}{N},$$

可选计算均匀磁化率：

$$\chi=\frac{\beta}{N}\left\langle\left(\sum_i\sigma_i^z\right)^2\right\rangle.$$

最终结果在相同的 $10\times10$ OBC 系统上与 QMC 数据比较，并报告：

- 内能密度 $u$ 和比热 $C$ 的相对误差（目标：$\epsilon_{\rm rel}(u)<1\%$，$\epsilon_{\rm rel}(C)<3\%$）；
- METTS 样本数、键维数、虚时间步长与环境参数的收敛性；
- 可稳定计算的最大 $\beta J$；
- 墙钟时间、峰值内存与误差之间的关系；加分项：与 tanTRG / MPO-LTRG 基线的精度–代价对比；
- 可复现实验所需的配置、随机种子、Git 版本与软硬件环境。

完整技术方案见 **[`docs/reports/report.md`](docs/reports/report.md)**。

---

## 项目结构

```text
2D_TN_Challenge/
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── raw/
│   │   ├── metts/                 # METTS 原始输出
│   │   ├── qmc/                   # QMC 原始输出
│   │   ├── pepo/                  # PEPO 探索性输出
│   │   └── ed/                    # 小尺寸精确对角化输出
│   ├── processed/
│   │   ├── benchmark.csv          # 主基准处理结果
│   │   ├── convergence.csv        # 收敛性结果
│   │   └── summary.json           # 自动汇总的核心指标
│   ├── logs/
│   │   ├── runs/                  # 每次运行的日志
│   │   └── environment/           # Python、硬件、Git 等环境信息
│   └── manifests/
│       ├── run_manifest.json      # 单次或批量运行的元数据
│       └── checksums.sha256       # 输出文件校验和
│
├── docs/
│   ├── reports/
│   │   ├── report.template.md     # 技术报告模板
│   │   └── report.md              # 自动生成的正式技术报告
│   ├── spec/                      # 需求与设计说明
│   ├── skills/                    # 方法笔记
│   └── memories/                  # 实验过程记录
│
├── results/
│   ├── figures/                   # 自动生成的图像（Fig. 1–12）
│   ├── tables/                    # 自动生成的 Markdown / CSV 表格片段
│   ├── logs/                      # 结果侧日志
│   └── report_metadata.json       # 报告变量与结果摘要
│
├── scripts/
│   ├── run_all.ps1                # PowerShell 一键复现脚本（Windows 友好）
│   ├── config.yaml                # 集中参数配置（L=10、h/J 列表、β 网格、演化/TRG 参数等）
│   ├── test_all.sh                # 一键测试（单元测试 + ED 检查 + 小规模回归）
│   ├── reproduce_all.sh           # 一键复现完整基准（Linux / macOS）
│   ├── run_metts.py               # METTS 主计算
│   ├── run_qmc.py                 # QMC 基准计算
│   ├── run_ed_sanity_check.py     # 小尺寸 ED 开发期检查
│   ├── process_results.py         # 处理原始结果与计算误差
│   ├── make_figures.py            # 生成图像
│   ├── collect_environment.py     # 收集硬件、软件和 Git 信息
│   ├── generate_report_data.py    # 生成报告变量和表格
│   ├── render_report.py           # 渲染报告模板
│   └── check_report.py            # 检查报告未替换变量
│
├── src/
│   └── tn_challenge/              # 项目源代码
│       ├── __init__.py            # 包入口
│       ├── io.py                  # 数据读写（raw / processed、manifest、校验和）
│       ├── plot.py                # 结果图像生成
│       └── profiling.py           # 墙钟计时与峰值内存记录
│
├── tests/                         # 单元测试与回归测试
│
└── .vscode/
    └── tasks.json                 # VS Code 一键任务配置
```

约定：

- `data/raw/` 保存原始计算输出，视为只读数据，不手工修改；
- `data/processed/`、`results/` 下的内容由脚本自动生成，不手工编辑；
- `data/manifests/` 保存每次运行的环境、配置、随机种子、Git 版本和文件哈希，用于复现与追踪；
- `docs/reports/report.md` 中的数值、图路径和运行信息一律由脚本自动填充，不手工复制。

---

## 安装

### 前置要求

- Python 3.10 或更高版本（推荐 3.11+）；
- Git；
- 可选：Conda；
- 可选：Julia ≥ 1.10（复算 tanTRG / MPO-LTRG 基线，基于 ThermoTN）；
- 可选：支持 CUDA 的 GPU，用于加速张量网络计算；
- 推荐使用 VS Code 运行项目内置任务。

### 克隆项目

```bash
git clone <repository-url>
cd 2D_TN_Challenge
```

### 使用 Python 虚拟环境安装

Linux 或 macOS：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如 PowerShell 阻止激活脚本，可在当前用户范围内执行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 可选：Conda

```bash
conda env create -f environment.yml
conda activate 2d-tn-challenge
```

### 可选：Julia 组件（tanTRG 基线复算）

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

---

## 快速开始

完整运行前，先执行单元测试和小尺寸精确对角化检查：

```bash
python -m pytest
python scripts/run_ed_sanity_check.py
```

小尺寸 ED 检查（$4\times4$）用于验证：哈密顿量构造、观测量定义、虚时间演化符号、高温极限、$Z_2$ 对称化实现、METTS 与 QMC 的基础实现、张量收缩和归一化逻辑。

---

## 一键复现

### 方式一：VS Code（推荐）

1. 使用 VS Code 打开项目根目录；
2. 按 `Ctrl+Shift+P`，选择 `Tasks: Run Task`；
3. 选择 **`TN: 一键复现`**。

该任务按顺序执行：单元测试 → ED 检查 → METTS 主基准计算 → QMC 参考计算 → 数据处理与误差计算 → 图像生成 → 环境与 Git 信息收集 → 报告变量生成 → 报告渲染 → 报告完整性检查。

### 方式二：一键脚本

```bash
bash scripts/test_all.sh        # 先跑测试：单元测试 + ED sanity check + 小规模回归
bash scripts/reproduce_all.sh   # 测试通过后复现完整基准
```

Windows PowerShell 对应入口：`.\scripts\run_all.ps1`（与 `reproduce_all.sh` 等效的一键复现脚本）。

### 方式三：命令行分步复现

使用主配置文件 `scripts/config.yaml`：

```bash
python scripts/run_metts.py --config scripts/config.yaml   # METTS 主计算
python scripts/run_qmc.py  --config scripts/config.yaml    # QMC 参考计算
python scripts/process_results.py                                   # 处理结果、对齐温度网格、计算误差
python scripts/make_figures.py                                      # 生成全部图像
python scripts/collect_environment.py                               # 收集运行环境
python scripts/generate_report_data.py                              # 生成报告变量与汇总
python scripts/render_report.py \
  --template docs/reports/report.template.md \
  --metadata results/report_metadata.json \
  --output docs/reports/report.md                                   # 渲染技术报告
python scripts/check_report.py --fail-on-unresolved-auto            # 检查未替换变量
```

---

## 配置说明

主实验配置位于 `scripts/config.yaml`，统一设置：

- 格点尺寸 $L_x=L_y=10$，开放边界条件；
- 耦合常数 $J=1$，横场 $h/J\in\{2.5,\ 3.0,\ 3.5\}$，逆温范围 $\beta J\in[0.1,1.0]$ 与温度网格；
- METTS：样本数序列与生产样本数、独立链数、热化样本数、测量间隔、分箱大小、坍缩基（$\sigma^z$ 乘积基 + $Z_2$ 对偶采样）；
- 张量参数：最大键维数、截断阈值、虚时间步长 $\Delta\beta$、环境维数 $\chi_{\rm env}$；
- $Z_2$ 对称性开关；
- QMC：热化步数、测量步数、测量间隔与分箱参数；
- 随机种子、输出目录与日志级别。

每次运行自动记录配置文件路径和 SHA-256 哈希，确保结果可追溯到对应参数。

---

## 输出内容

完整复现完成后，生成原始数据、处理结果表、收敛数据、图像、运行元数据和技术报告。

### 原始数据（`data/raw/`）

- METTS 每个参数点的原始测量数据（按链编号）；
- QMC 原始测量和统计误差数据；
- 小尺寸 ED 对照结果；
- 运行日志和中间检查点；
- 失败、终止或重启任务的信息。

### 处理后的数据（`data/processed/`）

| 文件 | 内容 |
|---|---|
| `benchmark.csv` | METTS、QMC 与 PEPO 的标准化热力学结果 |
| `convergence.csv` | 样本数、键维数、虚时间步长及环境维数收敛数据 |
| `summary.json` | MAE、RMSE、最大误差、低温稳定性等核心指标 |
| `error_summary.csv` | 相对误差与绝对误差汇总 |
| `performance.csv` | 墙钟时间、峰值内存与算法参数记录 |
| `susceptibility.csv` | 均匀磁化率结果；如未启用则不生成 |

`benchmark.csv` 字段（每行 = 方法 × 横场 × 温度点 × 算法参数）：

```text
run_id, method, field_h, beta, temperature, Lx, Ly, boundary,
bond_dimension, environment_dimension, delta_beta, sample_count, chain_id,
free_energy_density, internal_energy_density, specific_heat, susceptibility,
stderr_free_energy, stderr_energy, stderr_specific_heat, stderr_susceptibility,
wall_time_s, peak_memory_mb, seed, git_commit, config_sha256, status
```

### 自动生成的图像（`results/figures/`）

| 图像文件 | 内容 | 必/选 |
|---|---|---|
| `free_energy_vs_temperature.pdf` | 三个横场下的自由能密度 $f(T)$ | 必选 |
| `internal_energy_vs_temperature.pdf` | METTS 与 QMC 的 $u(T)$ 对比 | 必选 |
| `specific_heat_vs_temperature.pdf` | METTS 与 QMC 的 $C(T)$ 对比 | 必选 |
| `relative_error_energy.pdf` | $u$ 的相对误差随 $\beta J$（半对数） | 必选 |
| `relative_error_specific_heat.pdf` | $C$ 的相对误差随 $\beta J$（半对数） | 必选 |
| `convergence_vs_samples.pdf` | METTS 样本数收敛（验证 $1/\sqrt M$，附 $\hat R$） | 必选 |
| `convergence_vs_bond_dimension.pdf` | 键维数收敛（$\beta J=0.1,0.5,0.8,1.0$） | 必选 |
| `delta_beta_convergence.pdf` | 虚时间步长收敛与 Trotter 阶数拟合 | 推荐 |
| `environment_convergence.pdf` | 环境维数 $\chi_{\rm env}$ 收敛 | 推荐 |
| `runtime_vs_error.pdf` | 精度–耗时权衡（METTS / PEPO / tanTRG） | 加分 |
| `memory_vs_parameter.pdf` | 峰值内存与样本数或键维数关系 | 加分 |
| `susceptibility_vs_temperature.pdf` | 均匀磁化率 $\chi(T)$ | 加分 |
| `metts_vs_qmc_summary.pdf` | METTS 与 QMC 结果总览 | 推荐 |

### 自动生成的表格（`results/tables/`）

| 文件 | 内容 |
|---|---|
| `qmc_validation_summary.md` | METTS 与 QMC 的精度汇总表 |
| `convergence_summary.md` | 样本数、键维数和步长收敛汇总 |
| `stability_summary.md` | 各横场下可保持目标精度的最大 $\beta J$ |
| `performance_summary.md` | 时间、内存和误差比较 |
| `run_summary.md` | 本次运行参数、环境和输出概览 |

### 运行元数据与可追溯性文件

| 文件 | 内容 |
|---|---|
| `data/logs/environment/environment.json` | 操作系统、Python、依赖、CPU、GPU 与 Git 信息 |
| `data/manifests/run_manifest.json` | 运行命令、配置哈希、随机种子、耗时、内存和状态 |
| `data/manifests/checksums.sha256` | 关键输出文件 SHA-256 校验和 |
| `results/report_metadata.json` | 用于填充技术报告的自动变量和统计摘要 |

每张图、每个数据表均可由 `benchmark.csv` 与对应脚本唯一复现；原始数据与配置哈希、Git commit 一一对应，保证结果可溯源。

---

## 技术报告

最终技术报告生成至 `docs/reports/report.md`，内容包括：模型与研究目标；METTS 算法、PEPO 对照与 QMC 参考方法；实验参数；热力学结果；与 QMC 的误差比较；样本数 / 键维数 / 虚时步长 / 环境参数收敛；最大稳定逆温度；性能比较；Git 版本、配置哈希、随机种子和软硬件环境；最终验收清单；参考文献。

报告中的 `{{AUTO:...}}` 字段由脚本自动填充。检查是否存在未解析字段：

```bash
python scripts/check_report.py --fail-on-unresolved-auto
```

---

## 验证标准

所有最终结果在同一 $10\times10$ OBC 系统上比较，QMC 验证的重点指标为 $u$ 和 $C$。相对误差定义为

$$\epsilon_{\rm rel}(O;\beta)=\frac{\big|O_{\rm TN}(\beta)-O_{\rm QMC}(\beta)\big|}{\max\big(\big|O_{\rm QMC}(\beta)\big|,\,10^{-12}\big)}.$$

验收目标：

$$\epsilon_{\rm rel}(u)<1\%,\qquad \epsilon_{\rm rel}(C)<3\%.$$

METTS 样本数收敛至少在代表性温度点 $\beta J=0.8$ 进行；同时报告在满足目标误差条件下算法可稳定计算的最大逆温度。

---

## 开发建议

- 不手工编辑 `data/processed/` 的数值结果，不手工复制数值到技术报告中；
- 所有运行通过配置文件驱动，每次运行记录随机种子、配置哈希和 Git 提交；
- 修改算法、参数或依赖后，重新运行小尺寸 ED sanity check；
- 提交结果前，执行测试、生成图像、渲染报告并运行报告检查；
- 完整工作流建议通过 VS Code 的 `TN: 一键复现` 任务运行。

---

## 参考文献

1. S. R. White, *Minimally entangled typical quantum states at finite temperature*, Phys. Rev. Lett. **102**, 190601 (2009).
2. E. M. Stoudenmire, S. R. White, *Minimally entangled typical thermal state algorithms*, New J. Phys. **12**, 055026 (2010).
3. P. Czarnik *et al.*, *Variational tensor network renormalization in imaginary time: benchmark results in the Hubbard model at finite temperature*, Phys. Rev. B **94**, 235142 (2016).
4. M. Zhang, H. Zhang, C. Wang, L. He, *Scalable tensor network algorithm for thermal quantum many-body systems in two dimensions*, Phys. Rev. B **111**, 075146 (2025).
5. Q. Li *et al.*, *Tangent space approach for thermal tensor network simulations of the 2D Hubbard model*, Phys. Rev. Lett. **130**, 226502 (2023).
6. B.-B. Chen *et al.*, *Exponential thermal tensor network approach for quantum lattice models*, Phys. Rev. X **8**, 031082 (2018).
7. ThermoTN open-source thermal tensor network codes: <https://github.com/ThermoTN>.
8. H. W. J. Blöte, Y. Deng, *Cluster Monte Carlo simulation of the transverse Ising model*, Phys. Rev. E **66**, 066110 (2002).
9. A. W. Sandvik, J. Kurkijärvi, *Quantum Monte Carlo simulation method for spin systems*, Phys. Rev. B **43**, 5950 (1991); B. Bauer *et al.*, J. Stat. Mech. P05001 (2011)（ALPS）.

---

## 项目状态

- 主路线：METTS + QMC 基准验证；
- 探索路线：PEPO 对照实现与验证；
- 扩展路线：tanTRG / MPO-LTRG 精度–计算代价比较，均匀磁化率，有限尺寸分析。
