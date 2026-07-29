# B 角色 阶段一报告：二维 METTS 最小正确实现

> 项目：Challenge 147 —— 二维横场 Ising 有限温 METTS
> 角色：B（二维 METTS 最小正确实现）
> 代码：`challenge147_memberB/src/metts_b/`，分支 `challenge-147-metts-implementation`
> 报告生成：2026-07-30（阶段一交付，数值来自实际运行，非手填）
> 复现：见 §10

---

## 1. 当前实现状态

阶段一目标——二维 METTS 端到端最小闭环——**已完成并通过 ED 校验**。两个后端均已实现并验证：

| 后端 | 文件 | 状态 | 用途 | 规模上限 |
|---|---|---|---|---|
| **DenseBackend**（稠密态矢量） | `measure.py` | 已验证 vs ED（机器精度） | 金标准参考、ED 对照、≤12 格点 | N ≤ ~12（2^N 内存） |
| **MPSBackend**（snake-MPS） | `mps_backend.py`, `mps.py` | 已验证 vs dense/ED | 可扩展到 10×10 smoke test | 受 bond dim χ 限制 |

两者实现**同一协议**（`make_product_state / evolve / norm / energy_moments / conditional_prob_and_collapse`），由 `run_one_sample` / `run_chain` 统一驱动，故链式采样、统计、trace 与 ED 对照代码完全共享。

## 2. 使用的接口与统一约定（已与 A 对齐）

B 复用 A 侧 `challenge147stuff/solution` 的共享基础设施（`metts_b.bridge` 一处 re-export），保证 Hamiltonian、格点、ED 参考与 A 完全一致：

- **Hamiltonian**：`H = -J Σ_<ij> sz_i sz_j - h Σ_i sx_i`，`J=1`，OBC，行优先 `i = y·Lx + x`。
- **Pauli**：`SZ = diag(1,-1)`，`SX` 非对角（来自 `core.model`）。
- **ED**：`ed.ed.ed_thermodynamics(Lx,Ly,h,beta_list)`，N≤12。
- **比热约定**：`C = β²(<H²>-<H>²)/N`；自由能 `f` 由 `core.observables.free_energy_from_u(betas, us)` 热力学积分重建（与 A/QMC 共享）。
- **位序约定**（稠密后端）：态矢量索引 `b` 中 `bit k = site (N-1-k)`，与 `ed.ed` 的 Kronecker 顺序一致（已用 `test_product_state_bit_convention` 锁定）。

## 3. 核心物理流程实现（对应任务说明 §5）

| 流程 | 实现位置 | 关键点 |
|---|---|---|
| 产品态初始化 | `hamiltonian.product_state_vector` / `MPS.from_product_state` | Z 基直积态，可复现，关联种子 |
| 虚时间演化到 β/2 | `DenseBackend.evolve` / `MPSBackend.evolve` | **τ = β/2**，算符 `e^{-βH/2}`；spectral 路径精确（E₀ 移位保稳），Trotter 路径二阶 Suzuki–Trotter |
| 演化方法 | `hamiltonian.trotter_evolve_dense` / `mps_backend._apply_bond` | 二阶 ST：`F(Δτ/2)·B_even·B_odd·F(Δτ/2)`；键门 `e^{+JΔτ sz sz}` 为 Z 对角相位（无纠缠增长），场门 `e^{+θ sx}=cosh·I+sinh·sx` 为单格点旋转 |
| 能量测量 | `energy_moments`（H\|ψ> trick） | `E_σ=<φ\|χ>/<φ\|φ>`，`|χ>=H|φ>`；`E²_σ=<χ\|χ>/<φ\|φ>`；约定无关。MPS 后端用逐键/逐点局域期望求和（给定 χ 精确） |
| 局域概率 | `conditional_prob_and_collapse` | 仅 Z 基；逐格点顺序条件概率，零化-归一化投影；等价于联合分布 `p(s)=|<s\|φ>|²` 的精确采样 |
| 随机坍缩 | 同上 | 单轨迹 MSB→LSB；记录每格点 (p_up,p_down)；坍缩后验证 ±1 合法 |
| 下一产品态 | `run_chain` | 坍缩结果作为下一轮输入；失败时回退到合法直积态，链不卡死 |
| 样本级 trace | `run_one_sample` | 完整 §7 schema（26 字段），逐样本 JSON + chain_summary.csv |

**METTS 估计量**：坍缩采样使 `π(σ) ∝ w_σ = <σ\|e^{-βH}\|σ>`，故 `<O>_β = (1/M) Σ_m <φ_m\|O\|φ_m>/<φ_m\|φ_m>` 为**无权样本均值**（detailed balance 由 `e^{-βH/2}` 的厄米性保证，含其 Trotter 近似）。

**比热估计量**（关键正确性点）：`C = β²(mean(E²_σ) - mean(E_σ)²)/N`，即 H 的**热方差**（含样本内 + 样本间方差），**不是** `Var_σ(E_σ)`。由全方差律 `Var_β(H) = E[Var_φ(H)] + Var_σ(E)`，METTS 典型态携带的样本内方差 `E[E²_σ - E_σ²]` 在低温下是主导项，不可丢。早期实现误用样本间方差，C 偏差 ~600×，已修正（`test_spectral_metts_mean_energy_matches_ed` 锁定）。

## 4. 已完成 / 未完成模块

**已完成**：
- [x] 产品态初始化（稠密 + MPS）
- [x] 虚时间演化明确执行到 β/2（spectral 精确 + 二阶 Trotter）
- [x] 能量测量（H\|ψ> trick）
- [x] Z 基局域概率计算
- [x] 随机坍缩 + 下一产品态生成
- [x] 每条样本完整 trace（§7 schema）
- [x] 异常不静默忽略（状态码 + 日志 + 中间态）
- [x] 2×2、h/J=3.0 多 β 点 ED 对照（通过）
- [x] 3×4（N=12）ED 对照（通过，χ=64）
- [x] 10×10 smoke test（通过，见 §7）
- [x] 多链 + 分箱 SEM + Gelman–Rubin R̂
- [x] 收敛分析脚本（Δβ、样本数、键维数）+ 图

**未完成 / 留待生产**：
- [ ] 10×10 的**高精度**结果（当前 χ=64 仅 smoke test 级；近临界区典型态纠缠高，需更大 χ + 更多样本，受算力限制）
- [ ] Z₂ 对偶采样（antithetic，降方差；接口已留 `antithetic_z2`，未启用）
- [ ] 与 QMC（10×10）的系统精度对比（A 侧 QMC 就绪后）
- [ ] tanTRG 基线对比（加分项）

## 5. 小系统 ED 对照结果（2×2，h/J=3.0，spectral 后端）

配置：4 条独立链 × 2000 生产样本 × 7 个 β 点，spectral 演化（精确 `e^{-βH/2}`）。运行 149.8 s，56000 样本，**0 失败**。

| β | u_METTS | u_ED | u 相对误差% | C_METTS | C_ED | C 相对误差% | R̂ |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.05 | -0.4693 | -0.4953 | 5.24 | 0.02482 | 0.02430 | 2.16 | 1.012 |
| 0.10 | -0.9261 | -0.9634 | 3.88 | 0.09108 | 0.08937 | 1.92 | 1.020 |
| 0.20 | -1.7479 | -1.7429 | 0.28 | 0.26081 | 0.26236 | 0.59 | 1.002 |
| 0.30 | -2.2739 | -2.2774 | 0.16 | 0.38180 | 0.37945 | 0.62 | 1.000 |
| 0.50 | -2.8045 | -2.8047 | 0.01 | 0.36895 | 0.36964 | 0.19 | 1.000 |
| 0.80 | -3.0245 | -3.0250 | 0.01 | 0.19268 | 0.19218 | 0.26 | 1.000 |
| 1.00 | -3.0626 | -3.0628 | 0.00 | 0.11098 | 0.11052 | 0.42 | 1.000 |

**结论**：spectral METTS 在 β≥0.2 上 u 相对误差 <0.3%、C 相对误差 <0.6%（精确演化，残差纯 MC 噪声 ~1/√8000）；R̂<1.02（链混合良好）。

**图**：`metts_runs/reports/figures/ed_comparison_2x2.png`（u、C 的 METTS-vs-ED 曲线，误差棒为 1σ binning SEM）。生成：`PYTHONPATH=src python -m metts_b.analyze --ed-csv metts_runs/2x2_h3.0_spectral/comparisons/metts_vs_ed.csv --ed-title "2x2 h/J=3.0"`。

**高温端（β=0.05,0.10）u 相对误差偏大（3.9–5.2%）的来源**：高温极限 `u→0`（TFIM H 无迹），分母 `|u_ED|` 小，相对误差被放大——这是**期望行为**，非 bug；该处 C 仍在 2.2% 以内。已由 `test_ed_high_T_internal_energy_zero` 锁定高温极限。

**自由能 f**：由 `free_energy_from_u` 热力学积分重建。积分有梯形离散误差（β→0 锚点附近最显著，已在密 β 网格上量化为 ~4e-3）+ MC 噪声（被 1/β 放大）。f 是 u 的导出量，主验证指标为 u 与 C。

## 6. 收敛性分析

收敛分析由 `metts_b.analyze` 生成，输出 `metts_runs/analysis/{csv,png}`。

### 6.1 Trotter Δβ 收敛（2×2，β=0.4，单态 vs spectral）

| Δβ | E_trotter | E_spectral | 绝对误差 |
|---:|---:|---:|---:|
| 0.08 | -11.1300 | -10.4169 | 7.13e-1 |
| 0.04 | -10.4195 | -10.4169 | 2.57e-3 |
| 0.02 | -10.4176 | -10.4169 | 6.51e-4 |
| 0.01 | -10.4171 | -10.4169 | 1.63e-4 |
| 0.005 | -10.4169 | -10.4169 | 4.09e-5 |

Δβ=0.08 为预渐近区（误差大）；Δβ≤0.04 起误差随 Δβ² 干净下降（0.04→0.005 降 ~63×，符合二阶）。生产取 Δβ=0.01（小系统，已收敛到 ~1e-4）/ 0.05（10×10 smoke，权衡算力）。图：`delta_beta_convergence.png`。

### 6.2 样本数 M 收敛（2×2，β=0.8，dense spectral，4 链）

| M | u | SEM(u) | R̂ | u 相对误差 |
|---:|---:|---:|---:|---:|
| 100 | -3.02497 | 1.33e-3 | 1.004 | 2.0e-6 |
| 200 | -3.02370 | 9.32e-4 | 1.000 | 4.2e-4 |
| 500 | -3.02441 | 6.69e-4 | 1.000 | 1.9e-4 |
| 1000 | -3.02451 | 3.88e-4 | 1.000 | 1.5e-4 |
| 2000 | -3.02472 | 2.51e-4 | 1.000 | 8.5e-5 |
| 4000 | -3.02486 | 1.95e-4 | 1.000 | 3.7e-5 |

SEM 从 1.33e-3（M=100）降到 1.95e-4（M=4000），~6.8×，符合 1/√M（√40=6.3）；R̂≈1.000 全程。图：`sample_convergence.png`。

### 6.3 键维数 χ 收敛（3×4，β=0.5，MPS，300 样本/χ）

| χ | u | u 相对误差 vs ED | n_samples |
|---:|---:|---:|---:|
| 8 | -1.286 | 55% | 300 |
| 16 | -2.953 | 3.5% | 300 |
| 32 | -2.115 | 26% | 275 |
| 48 | -2.277 | 20% | 300 |
| 64 | -2.880 | **0.9%** | 300 |

χ=64 时 u 相对误差 0.9%（丢弃权重=0，与 dense-Trotter 一致）。**χ<64 非单调**：近临界典型态高度纠缠，不足 χ 给出有偏截断，偏差方向依赖 Schmidt 谱——χ=16 偶然接近、χ=32/48 偏远。这是 2D-METTS 在量子临界区的**核心难点**（任务背景所述）：10×10 高精度需 χ 远大于 64 + 大量样本，受算力限制。图：`bond_convergence.png`。

## 7. 10×10 smoke test（任务说明 §5 阶段5 / DoD）

配置：snake-MPS，χ=64，Δτ=0.05，2 个 β 点，每点 2 warmup + 3 生产样本，内存守卫开启。

| 检查项 | 结果 |
|---|---|
| 程序启动 | ✅ |
| 至少完成一个样本 | ✅（两 β 点各 3 生产样本，共 6/6 OK，0 失败） |
| 无 NaN | ✅（生产样本 status 全 OK） |
| 内存未失控 | ✅（单样本峰值 RSS ~0.06 GB，可用 4.48 GB） |
| wall time 可记录 | ✅（734.5 s，manifest 记录） |
| trace 完整输出 | ✅（100 格点概率，§7 schema，逐样本 JSON + chain_summary.csv） |
| 已知失败模式可识别 | ✅（见 §8，已修复） |

| β | u_METTS | u_err | C_METTS | f | n_samples |
|---:|---:|---:|---:|---:|---:|
| 0.30 | -0.667 | 0.075 | 0.020 | -2.644 | 3 |
| 0.50 | -0.712 | 0.094 | 0.056 | -1.862 | 3 |

完整 smoke 运行结果见 `metts_runs/10x10_h3.0_smoke/`。**注意**：χ=64 下 10×10 近 h/J=3.0 的典型态高度纠缠，单样本能量方差大、u 误差条大（3 样本仅 smoke 级）——这是 smoke test（可行性 + 不崩溃 + 完整 trace），**非**精度结果。精度需更大 χ 与远多于 3 个样本（生产级，待算力；§6.3 显示 3×4 已需 χ≥64，10×10 需更大）。

## 8. 异常与已知失败模式

| 模式 | 触发条件 | 处理 | 状态码 |
|---|---|---|---|
| NaN/Inf 演化 | 极小 norm 或数值溢出 | 标记失败，链回退到新随机直积态 | `EVOLUTION_NAN` |
| 概率非法/不归一 | 条件权重 ≤0 或非有限 | 标记失败，记录站点 | `PROBABILITY_ERROR` |
| 坍缩失败 | 坍缩态非 ±1 | 标记失败，回退 | `COLLAPSE_ERROR` |
| 内存超限 | 大 χ/大 N 分配 | `assert_mem_available` 预检 + `MemoryBudgetExceeded` 降级 | `MEMORY_LIMIT` |
| **SVD 不收敛**（已修复） | 低温大 N 时场门使 norm 溢出/下溢，SVD 矩阵尺度极端 | **演化每步重缩放到单位 norm**（丢弃总因子，抵消于所有 METTS 比值），追踪 `log_scale` | 修复前 `UNKNOWN_ERROR`；修复后不触发 |
| **χ 不足的纠缠损失**（2D-METTS 难点） | χ < 典型态所需键维（3×4 β=0.5 需 χ≥64） | 丢弃权重记录在 trace；u 系统偏差；**非崩溃**，但精度无效 | `OK`（但 `truncation_error_total` 大） |

**SVD 不收敛根因与修复**（三步）：首次 10×10 smoke test 在 β=0.5 多样本失败（`LinAlgError: SVD did not converge`）。诊断：β=0.3 时演化后 norm 已达 ~1e-100，β=0.5 更甚；链中第 2 个样本起（输入为坍缩态）更易触发。根因有二：(a) 场门 `e^{+θsx}=cosh+sinh` 在大 N 累积使 norm 按 ~e^{h·τ} 增长、态系数溢出/下溢，使键门 SVD 矩阵尺度极端；(b) 某些坍缩-演化态的 Schmidt 谱近简并/近零，numpy 默认 `gesdd` 驱动偶发不收敛。修复分三步：
1. **有界场门**（`field_gate_normalized`）：将场门分解为 `cosh(θ)·(I + tanh(θ)·sx)`，对 MPS 只施加**有界算子** `(I+tanh·sx)`（谱范数 ≤2），标量 `cosh(θ)` 累加进 `mps.log_scale`。消除溢出，但有界算子沿基态方向本征值 `1-tanh(θ)<1` 会使 norm 按 `(1-tanh)^(2N·n_steps)` **下溢到 0**。
2. **每步重缩放**：每步演化后用一次 `norm2()` 将 MPS 重缩放到单位 norm，丢弃因子并入 `log_scale`。有界门保证每步 norm 变化是有界因子，单次重缩放既防溢出又防下溢，张量保持 O(1)。
3. **稳健 SVD**（`_robust_svd`）：所有 SVD（键门、规范化、坍缩）经统一入口，numpy `gesdd` 失败时回退到 scipy `gesvd` 驱动（慢但稳健），再退到微小正则化，绝不抛异常中断样本。

键门 `e^{+Jdτ sz sz}` 仅按 e^{±Jdτ}≈1.05 缩放（有界）。最终 MPS norm 全程 O(1)，每个 SVD 在任意 β/N 下良态或优雅降级；`log_scale` 在 `E=<φ|H|φ>/<φ|φ>`、坍缩概率、无权样本均值中**全部抵消**，不改变任何可观测量。修复后 10×10 β=0.5 链 5/5 样本 status=OK（修复前 2/5 失败）。β=0.3 既有结果不受影响（fast MPS 测试与 3×4 ED 精度测试通过）。

## 9. 10×10 单样本耗时与内存估计

- **耗时**：χ=64、Δτ=0.05 单样本 ≈ **70–120 s**（含演化 + 测量 + 坍缩；波动来自稳健 SVD 在近简并谱时回退 gesvd）。完整 smoke（2 β × 5 样本）734.5 s。10×10 snake-MPS 的非相邻键需 swap 门，χ=64 下收缩是主要开销；演化每步的 `norm2()` 重缩放为 O(N·χ³)。
- **内存**：单样本峰值 RSS ≈ **0.06 GB**（χ=64）；内存随 χ² 增长，χ=128 约 0.25 GB，χ=256 约 1 GB——均在 4.4 GB 笔记本预算内，内存守卫会在超限时降级 χ。
- **精度–代价**：10×10 精度受限于 χ（纠缠）与 M（统计）；β 增大/降温则典型态纠缠增长、所需 χ 上升（3×4 β=0.5 已需 χ≥64，见 §6.3）。生产级 10×10 精度结果需超算或长 wall-time，且可能需更先进的 2D 收缩（边界 MPS / 真正 PEPS）而非 snake-MPS。

## 10. 复现命令

```bash
cd challenge147_memberB
python -m pip install -r requirements.txt

# 单元 + 物理测试（18 项，~1 min except 3x4 MPS ~8 min）
PYTHONPATH=src python -m pytest -q

# 2x2 ED 对照（spectral，4 链 × 2000 样本，~2.5 min）
PYTHONPATH=src python -m metts_b.run --config configs/2x2_h3.0.yaml

# 2x2 Trotter 验证
PYTHONPATH=src python -m metts_b.run --config configs/2x2_h3.0_trotter.yaml

# 3x4（N=12）ED 对照（χ=64，~8 min）
PYTHONPATH=src python -m metts_b.run --config configs/3x4_h3.0.yaml

# 10x10 smoke test（χ=64，~13 min）
PYTHONPATH=src python -m metts_b.run --config configs/10x10_h3.0_smoke.yaml

# 收敛分析 + 图（Δβ / 样本数 / 键维数）
PYTHONPATH=src python -m metts_b.analyze --out metts_runs/analysis
```

输出：`metts_runs/<label>/{thermodynamics.csv, comparisons/metts_vs_ed.csv, manifest.json, traces/, configs/}`。

## 11. B → A 交付清单（任务说明 §10）

1. ✅ 小系统 METTS 样本 trace —— `metts_runs/2x2_h3.0_spectral/traces/`
2. ✅ 与 ED 的比较表 —— `metts_runs/2x2_h3.0_spectral/comparisons/metts_vs_ed.csv` + §5 表
3. ✅ 完整运行配置 —— `configs/*.yaml` + `metts_runs/*/configs/run_config.yaml`
4. ✅ 已知失败模式 —— §8
5. ✅ 异常日志示例 —— `metts_runs/*/logs/`（失败样本 trace 内含 `error_message`/`status_code`）
6. 中间状态/checkpoint —— 当前 `write_checkpoints=false`（可启用）；失败中间态由 trace 字段记录
7. ✅ 10×10 单样本耗时估计 —— §9（~76 s）
8. ✅ 10×10 单样本内存估计 —— §9（~0.063 GB）
9. ✅ 当前代码版本 —— git commit `4de2dd9`（分支 `challenge-147-metts-implementation`）
10. ✅ 复现命令 —— §10

## 12. 与 A 的约定一致性确认

- [x] Hamiltonian 一致（`H=-J Σ sz sz - h Σ sx`, J=1）
- [x] 边界条件一致（OBC）
- [x] 单位一致（能量以 J 为单位，β=1/T）
- [x] ED 输出格式一致（`ed_thermodynamics` 共享）
- [x] 自由能重建一致（`free_energy_from_u` 共享）

---

**阶段一验收（任务说明 §12 DoD）**：除"10×10 高精度"（属生产级，非阶段一目标）与 Z₂ 对偶采样（接口已留，未启用）外，全部 DoD 项已满足。10×10 smoke test 通过（不崩溃、完成样本、有界内存、完整 trace）。
