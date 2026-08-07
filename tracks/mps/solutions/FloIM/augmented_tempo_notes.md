# 增广 MPS 模块说明与审计笔记

日期：2026-07-28
代码：`tracks/mps/solutions/src/augmented_tempo.jl`（模块 `AugmentedTEMPO`）；测试在 `tracks/mps/solutions/test/`，画图脚本放 `tracks/mps/solutions/plot/`
设计文档：`docs/design/2026-07-28-floquet-unitempo-manybody-ising.md`
配套推导：`docs/design/2026-07-28-redfield-benchmark-manybody-ising.md`

---

## 1. 解决什么问题

驱动斜场 Ising 链

$$
H_{\rm sys}(t) = \sum_{i=1}^{N-1} J\, \sigma_z^i \sigma_z^{i+1} + \sum_{i=1}^N \left[ h_z(t)\, \sigma_z^i + h_x\, \sigma_x^i \right], \qquad h_z(t) = h_z + A\cos(\omega_d t)
$$

左端点（站点 1）耦合零温 Ohmic 浴（$J(\omega) = \alpha \omega e^{-\omega/\omega_c}$）。

**关键结构**：浴只挂在站点 1 上 → 影响泛函（IF）只含站点 1 的 Liouville 路径 → IF 精确等于单自旋的 uniTEMPO 均匀 MPO，与 $N$、驱动均无关。所以记忆键维 $\chi_b$ 就是已验证的单自旋值（论文参数下 $\chi_b = 41$），**不随时间增长、不随 $N$ 增长**。唯一的张量网络近似是空间 MPS 的键维 $\chi_s$ 截断。

## 2. 文件清单

| 文件 | 作用 |
|---|---|
| `src/augmented_tempo.jl` | 模块本体（`AugmentedTEMPO`）：增广 MPS 数据结构、TEBD 基元、浴步、观测量（含键流）、主循环 |
| `src/redfield_ising.jl` | M3 新增（`RedfieldIsing`）：多体 Redfield–Magnus Liouvillian（Bohr 频率形式，无久期近似） |
| `test/m0_m1_checks.jl` | M0/M1 验证驱动（对照论文图 2 数据与 ED），一键重跑 |
| `test/m1a_error_analysis.jl` | M1(a) 误差归因：N=6（永不截断）的 δt 收敛序列 |
| `test/m1a_error_analysis_n10.jl` | M1(a) 误差归因：N=10 的 δt / χ_s 对照（大计算，宜上集群） |
| `test/test_merged_bonds.jl` | merge_bonds 优化的 N=6 对照（封闭 + 真实浴两种情形） |
| `test/m3_redfield_check.jl` | M3 高频 Redfield 一致性：N=1 接线 + N=2,3 对照（N=6 传参 `"6"` 单跑） |
| `test/m4_heat_current.jl` | M4 热流：流算符 ED 对照 + NESS 逐站点连续性 + j̄(ω_d) 首扫 |
| `test/floquet_spin_boson_fig2.jl` | 更早的单自旋图 2 复刻脚本（本项目的验证基准来源） |

运行方式（以 M0/M1 为例）：

```bash
julia --project=tracks/mps/env_floquet tracks/mps/solutions/test/m0_m1_checks.jl
```

## 3. 数据结构与约定

```
Ψ(μ_1, …, μ_N; m) = Σ B[m, μ_1, a_1] A[1][a_1, μ_2, a_2] ⋯ A[N-1][a_{N-1}, μ_N]
```

- `B[m, μ, a]`：站点 1 边界张量。m = 记忆腿（维度 $\chi_b$），μ = Liouville 指标（1..4），a = 空间键（维度 $\chi_s$）。
- `A[i-1][l, μ, r]`：站点 i = 2..N 的体部张量。
- **cap**：用 `pt.v_l` 收缩记忆腿 m，得到普通 MPS（站点 1 左边界维度 1），即系统的 Liouville 矢量 ρ。

与 UniformTEMPO.jl 严格对齐的约定（改动前先看模块头注释）：

- Liouville vec 列主序：μ = r + 2(c−1) ↔ 基元 |r⟩⟨c|。
- `pt.q` 形状 (χ_b, 4, χ_b, 4) = （记忆-out, 系统-out, 记忆-in, 系统-in）；`q_matrix` 重排成 (χ_b·4)×(χ_b·4) 矩阵作用在 vec（记忆⊗系统） 上。
- 局域通道 = `kron(conj(u), u)`。
- 每步结构 onsite(δt/2) → bonds(δt/2) → 浴步（Q) → bonds(δt/2) → onsite(δt/2)；N=1 时退化为 `UniformTEMPO.evolve` 的 u1 → q → u2。所有 J σzσz 键门互相对易，键门次序无关。
- `UniformPTMPO(2, δt)` 给出 χ_b=1 的平凡 IF（α=0 封闭系统测试用）。

## 4. 模块函数地图

`AugmentedTEMPO`（`src/augmented_tempo.jl`）：

| 分组 | 函数 | 说明 |
|---|---|---|
| 构造 | `q_matrix, init_amps, onsite_superop, bond_superop, bond_covector, op2` | IF 矩阵化、乘积初态、单点/两点 Liouville 门与余矢量；`op2(Oi,Oj)=kron(Oj,Oi)` 处理两点算符的 kron 因子序（M4 新增，见 §6.5 坑 (i)） |
| TEBD | `onsite!, bath_step!, bond12_step!, bulk_bond_step!, bond_sweep!` | 单点门、浴步（Q 作用于 B）、键 (1,2) 与体部键的 gate+SVD、键层扫描 |
| 观测量 | `capped_mps, expect, expect_bond, sz_all, trace_rho, purity, energy_ising, site_energies, current_bond, current_profile` | **全部在 capped MPS 上收缩**，O(N χ²)～O(N χ³)，与 2^N 无关；`site_energies/current_*` 为 M4 新增（键流与能量密度） |
| 驱动 | `trotter_step!, run_chain` | Strang 步与主循环（`measure` 回调注入观测量）；开关 `merge_bonds`（键层合并，§7-4）与 `keep_state`（返回末态 amps 供接续演化，M4 NESS 协议用） |
| 调试 | `cap_density` | 全收缩出 2^N×2^N 密度矩阵，**仅 N≲12 的 ED 对照用** |

`RedfieldIsing`（`src/redfield_ising.jl`，M3 新增）：

| 函数 | 说明 |
|---|---|
| `site_op, build_H0` | 镜像约定的单点算符与静态 Ising H_0（与增广 MPS 模块同一站点↔kron 映射） |
| `bath_Gamma` | Γ(ω) = ∫₀^∞ ds e^{iωs} η(s)，SpecialFunctions 的 `expinti/expint`，约定与已验证单自旋脚本一致 |
| `redfield_liouvillian` | 组装 `RedfieldModel`（H_F 的 ED、能量基 S、Liouville 超算符 L，4^N×4^N） |
| `evolve_redfield / expect_redfield / steady_state_redfield` | 稠密演化（N≤3；N=6 在测试脚本里用 KrylovKit 步进）、能量基期望、L 零本征矢稳态 |

## 5. 观测量：为什么不用 cap_density（本次重构要点）

旧实现里 `run_chain` 每步调 `cap_density` 生成完整 2^N×2^N 密度矩阵再算 ⟨σz⟩、E——内存和时间都随 N 指数增长，N≳14 就不可用，违背了 MPS 方法的初衷。

新实现利用

$$
\langle O \rangle = \operatorname{tr}(O\rho) = \sum_\mu \rho_\mu \, c_O[\mu], \qquad c_O[\mu] = \langle c | O | r \rangle = \mathrm{vec}(O^T)[\mu]
$$

即每个站点乘一个 4 维余矢量后全收缩（无算符站点用迹余矢量 `[1,0,0,1]`）。两点算符（如 σzσz 键）用 `bond_covector` 生成 16 维余矢量一次收缩两个站点。纯度 tr ρ²（ρ 厄米时）= Liouville 矢量范数²，用双层收缩 `mps_norm2` 计算；截断会轻微破坏厄米性，此时 `mps_norm2` 给出的是 tr(ρ†ρ)，作为纯度代理仍单调可信。

`run_chain` 不再存密度矩阵：新增 `measure=(amps, vl, t) -> NamedTuple` 回调，每个报告帧就地收缩观测量。返回 `(times, records)`。ED 对照（仍需要完整矩阵时）只在驱动脚本的参考一侧做，N 受 ED 限制 ≤12，这是对照的性质，不是求解器的限制。

## 6. 验证结果与误差归因

### 6.1 M0/M1 结果（2026-07-28，全部通过）

| 检查 | 结果 | 判据 |
|---|---|---|
| M0：N=1 vs 图 2 exact（t 到 200） | 7.5×10⁻¹⁴ | ≲10⁻⁶ ✓ |
| M1(b)：N=4 站点 1 vs 论文（ω_d=2.5/10） | 1.3×10⁻¹³ / 5.0×10⁻¹⁴ | ≲10⁻⁶ ✓ |
| M1(a)：α=0 封闭链 N=10 vs Krylov ED（t=5） | Δ⟨σz⟩=2.1×10⁻³，ΔE=5.9×10⁻³ | Trotter 阶 ✓ |

### 6.2 M1(a) 的 2×10⁻³ 从哪来

两个候选：Trotter 误差（Strang  splitting，全局 O(δt²)）与 χ_s=256 截断。用小 N 分离：

**N=6 实验**（`m1a_error_analysis.jl`）：N=6 的 MPS 最大只需要 χ=4³=64，设 maxdim=64 后截断**永不触发**，残差即纯 Trotter。对同一细步 ED 参考（δt/16 中点法）：

| δt | max\|Δ⟨σz₁⟩\| | max\|ΔE\| | ΔE 比值 |
|---|---|---|---|
| π/60 | 4.7×10⁻⁴ | 3.3×10⁻³ | – |
| π/120 | 1.1×10⁻⁴ | 8.1×10⁻⁴ | 4.04 |
| π/240 | 2.7×10⁻⁵ | 1.9×10⁻⁴ | 4.17 |

比值 ≈ 4，即误差 ∝ δt²，教科书式 Strang 行为。结论：**M1(a) 的误差以 Trotter 为主**（δt=π/60 时 N=6 的 ΔE≈3.3×10⁻³，N=10 的 5.9×10⁻³ 大部分也是 Trotter，系数随键数增长）。截断贡献（N=10、χ_s=256、聚积丢弃权重 3.7×10⁻³）的定量拆分需要 χ_s=512 对照运行——本地跑过一次被中止（太慢），**应上集群**（见 §7）。

另一个实测警告：驱动链 Liouville 纠缠增长极快，N=10、A=1、ω_d=2.5 时 χ_s 在 t≈5（不到一个驱动周期）就触顶 256。这决定 M4 必须直奔稳态而非硬跑长暂态。

### 6.3 已修复的实现 bug（都有单元测试/数值仲裁）

1. Julia 解构 `U,s,Vt = svd(M)` 拿到的第三项是 **V 不是 V†**（形状侥幸吻合但缺共轭）——显式取 `F.Vt`。
2. kron 镜像约定：cap 出的 ρ 站点 1 是最快指标，Julia `kron` 最后因子最快，故 ED 一侧的 `site_op(op,i,N)` 要把站点 i 映射到 kron 位置 N+1−i。
3. `AugMPS` 必须是 mutable struct（张量原地 resize）。
4. ED/TEBD 逐帧对比必须显式记录 t=0 帧，否则匹配循环卡死。
5. `UniformPTMPO` 的字段名是 `delta_t` 不是 `δt`。

### 6.4 M3 高频 Redfield 一致性（2026-07-28，通过）

**目标**（设计文档 §7 M3）：在高频驱动 ω_d = 20 h_x 下，精确求解器必须与 Redfield–Magnus 主方程汇合——同一份算力既验证多体接线（J≠0 的键门、站点 ≥2 的门作用），又验证物理内容。

**做了什么**：

1. 新模块 `src/redfield_ising.jl`（`RedfieldIsing`，约 120 行）：多体 Redfield–Magnus Liouvillian。依据推导文档：驱动轴 ∥ 耦合轴 → 一阶 Floquet–Magnus 修正恒为零，H_F = H_0（静态 Ising），kick 只影响非 σz 型观测量。在 H_0 能量基按 Bohr 频率组装耗散生元（无久期近似），Γ(ω) 用 SpecialFunctions 的 `expinti/expint`，kron 闭式组装 L（列主序 vec），全程与已验证单自旋脚本同一约定。
2. 新测试 `test/m3_redfield_check.jl`：A 节 N=1 接线检查（新 Liouvillian vs 已验证 RM 数据列）；B 节 N=2,3 稠密对照（增广 MPS vs Redfield 逐帧 ⟨σz_i⟩、频闪帧 tr(H_0ρ)、t=150 稳态 vs L 零本征矢）；C 节 N=6（Redfield 侧 Krylov 步进，传参 `"6"` 单跑）。
3. 参数：h_x=0.5, A=1, ω_d=10 (=20 h_x), J=0.5, h_z=0.3；浴同论文（α=0.05, ω_c=2.5, δt=π/60, χ_b=41）；初态全 |↑⟩。⟨σz⟩ 对微运动免疫（[K,σz]=0）故逐帧直接对照，能量在频闪帧（K=I）对照。

**结果**：

| 检查 | 结果 | 判据 |
|---|---|---|
| N=1 Liouvillian vs 已验证 RM 数据列 | 6.7×10⁻¹⁶ | 接线 ✓ |
| 健康检查 | max Re λ(L) ≤ 0，tr 守恒 ~10⁻¹⁴ | ✓ |
| 稳态 ⟨σz⟩ 差 | 0.0096（N=2，t=150 vs 零本征矢）/ 0.056（N=3）/ 0.0085（N=6，t=60） | O(α) 内 ✓ |
| 频闪帧 tr(H_0ρ) 差 | 0.06（N=2,3） | O(α) 内 ✓ |
| NESS 结构 | 两侧 AFM 近基态（N=3：ours (−0.62,+0.41,−0.59) vs RM (−0.68,+0.46,−0.63) vs ED 基态 (−0.55,+0.34,−0.55)） | ✓ |
| 暂态差（峰值 t≈2） | 0.15–0.21，对 N=2,3,6 **逐位相同** | 溯源为单体 RM 近似误差（见下） |

**两个概念修正（引用时注意）**：

- 论文复刻报告的 "RM max|Δ|=1.2×10⁻⁵" 是**我方 RM 代码 vs 作者 Zenodo RM 数据**的代码验证数，不是 exact-vs-RM 的物理一致数。实测同参数 N=1 的 exact-vs-RM 暂态误差本身就是 0.08（hz=0）–0.19（hz=0.3，峰值 t≈2-3）——Born 二阶 + Markov + 一阶 Magnus 的本征暂态误差。多体暂态偏差与此同量级且 N 无关 → 非接线缺陷；接线判据看晚时与稳态。
- 能量对照两侧都必须用 tr(H_0ρ)：含时 lab 能量 H(t) 在频闪帧取驱动最大值（cos=1），直接用 h(t) 会引入 A·N 虚假偏差（首轮实测 ΔE=2/3/6 即此 bug）。

**遗留**：N=6 t=150 稳态对照、ω_d=20 加密点（验证偏差 ∝ A²/ω_d² 收缩），宜集群。

### 6.5 体系内部键流的机制验证（2026-07-28；**不是热流密度**）

> **定义改正（2026-07-29）**：本项目"热流密度"的**唯一正确**定义是设计文档附录 B 的频率分辨公式
> $$\bar j(\omega) = 2\omega J(\omega)\,\mathrm{Re}\int_0^\infty d\tau\, e^{-i\omega\tau}\,\bar C(\tau)$$
> 由双时关联函数 $\bar C(\tau)$ 计算（Mickiewicz et al. End Matter Eq. (17)–(25)）。本节验证的**体系内部键流** $j_{i,i+1}$ 是另一个物理量：它不能给出浴模式分辨，在 $N=1$ 无定义，此前把它当作"热流密度"是错误定位，已改正。键流机制保留为**体系侧诊断工具**（连续性检验、能量平衡式 $\bar I = \bar P$ 的右端计算），见附录 B 式 (B.10)。

**保留的验证事实**（均为体系内部量，与热流密度无关但机制可复用）：

- 键流算符 $j_{i,i+1} = J h_x(\sigma_y^i\sigma_z^{i+1} - \sigma_z^i\sigma_y^{i+1})$（连续性方程导出）与能量密度 $e_i$ 的 MPS 收缩（`current_bond/current_profile/site_energies/op2`）：ED 逐点对照 8.5×10⁻⁵ ✓；带浴积分连续性 1.5% ✓；无驱动极限 ~1e-8 ✓。
- 能量平衡检验（附录 B 式 (B.10) 右端）：N=3 NESS 下 $\bar s_1 - \bar\jmath_{1,2} = \bar P$（总流恒等式），$\omega_d=2.5$ 点 0.5% 内自洽。
- 慢模实测（直接促成附录 B.5 的稳态引擎选择）：T=0 Ohmic 浴小 Bohr 频率模衰减极慢且不单调，长暂态测不准小 NESS 量（~1e-4 流被 ~1e-3 残余掩盖）⇒ 必须周期映射主本征矢。
- 教训两条（已记入记忆 #4）：两点算符矩阵 kron 因子序（`op2` 辅助）；微运动幅度污染逐点差分检验。

### 6.6 M4a 图 3 复刻（2026-07-29，完成）

**目标**：单自旋频率分辨热流密度 $\bar j(\omega)$（附录 B 公式，唯一正确定义），对照 Zenodo 图 3 六组参数（横场 ω_d∈{1,1.5,2}，纵场 ω_d∈{2.5,5,10}；α=0.05，ω_c=2.5，δt=π/60，tol=1e-7 → χ_b=41；作者 χ=235）。

**协议**（附录 B.5）：传播到 NESS（t_ss=200，周期逐点差 ~1e-5–1e-10 验证）→ 一周期 M 个 t' 起点插入 `insert_diagonal_left!`（S=σz 左乘）→ 各传播 τ∈[0,100] 读出**复数** C(t',τ) → 周期平均 → C̄_decay 梯形傅里叶积分 ×2ωJ(ω)；C̄_asym 由 ⟨S(t)⟩ 傅里叶级数给 δ 峰权重 c_n。

**结果**（`results/20260729-augmps-m4a/`，对照图 `m4a_fig3_comparison.png`）：

| 组 | L2（ω≤10） | 主峰位置 | Ī vs P̄ | Ī vs 作者图 5 |
|---|---|---|---|---|
| 横场 ω_d=1 | 2.9% | 0.995 ✓ | 0.0641/0.0642 | 0.9% |
| 横场 ω_d=1.5 | 3.7% | 1.50 ✓ | 0.0753/0.0750 | 0.2% |
| 横场 ω_d=2 | 11% | 3.325 ✓ | 0.0399/0.0395 | 1.0% |
| 纵场 ω_d=2.5 | 0.15% | 1.48 ✓ | 0.0934/0.0932 | 0.1% |
| 纵场 ω_d=5 | 0.82% | 4.03 ✓ | 0.0527/0.0523 | 0.7% |
| 纵场 ω_d=10 | 6.3% | 9.04 ✓ | 0.0097/0.0093 | 4.7% |

三重独立检验全部通过：谱形 L2 ≲ 11%、能量平衡 Ī=P̄ <1%、图 5 总流 <5%。边带（nω_d±Ω）与 Mollow 三重峰结构全部复现；横场驱动 δ 峰权重 c_1≈0.098–0.139（奇数倍 ω_d）。残差集中在最尖锐峰的高度（χ_b=41 vs 作者 235 + τmax=100 宽化），改进方向：tol 收紧或 τmax 加大。

**实现坑（新增）**：(1) 双时关联是**复数**——虚部（对易子）对频谱积分有贡献；取 real 会把纵场谱主峰从 ω_d−Ω 错置到 Ω（首轮 L2=53–1510% 的原因）。(2) P̄ 的 sin 相位必须用绝对时间 (k_ss+m−1)·δt，否则得负功率。

**脚本**：`test/m4a_fig3_reproduction.jl`、`test/diag_m4a_corr.jl`（C̄ 结构诊断）、`plot/m4a_fig3.jl`。模块新增 `insert_diagonal_left!`。

### 6.7 M4b 首个多体点（2026-07-29，N=4 跑通）

**参数**：ω_d=2.5，J=0.5，h_x=0.5，h_z=0.3，A=1，t_ss=400，τmax=100，全程无截断（N=4 精确秩 ≤ min(χ_b·4^i, 4^{N−i})=64）。脚本 `test/m4b_heat_current_n4.jl`，图 `results/20260729-augmps-m4b/m4b_n4_vs_n1.png`。

**数值健康**：NESS 周期逐点差 6e-6（N=1）/ 8e-7（N=4）；能量平衡 Ī=P̄：0.02913 vs 0.02923（N=1，0.3%）、0.06578 vs 0.0658（N=4，0.03%）。

**多体效应（N=4 vs 同场 N=1）**：

| 量 | N=1 | N=4 | 解读 |
|---|---|---|---|
| 总流 Ī | 0.0291 | 0.0658 | 2.3×（< N 倍 → 单端浴瓶颈，亚线性标度） |
| δ 峰权重 c_1 | 0.028 | 0.0024 | 相干峰基本消失（−92%） |
| 连续谱权重 | 0.0188 | 0.0649 | 3.4×，δ/相干权重重分布进连续谱 |
| 谱形 | 离散 Bohr 线（ω≈1.2, 1.7 + 边带） | 连续带（~0.5–3.5），峰宽化 | 16 能级 → Bohr 频率稠密化成带 |

Challenge #123 的核心问题（多体带来的谱权重重分布）在首个点即清晰显现。待办：ω_d 扫描 + N 标度（N=6 起上集群）、与 RM 对照（RM 预言 Ī≈0 的量级差异）。

## 7. 进一步优化计划

**短期（代码层面）**

1. ~~观测量 MPS 原生化~~ —— 已完成（§5）。
2. ~~χ_s 收敛序列产品化~~ —— 已完成：`run_chain` 每帧记录自动附加 `χs`（当前最大空间键维）与 `dw`（聚积丢弃权重），多次 maxdim 运行直接成表。N=10 的 χ_s=512 对照上集群跑（待做）。
3. ~~tr 与纯度漂移进默认记录~~ —— 已完成：`default_measure` = ⟨σz⟩ 全部站点 + tr ρ + 纯度（双层收缩 `mps_norm2`，每帧代价 O(N χ³)）。
4. ~~键门合并优化~~ —— 已完成，开关 `merge_bonds`（默认 false 保留原写法）。依据：σz 耦合下键门与浴步在 μ 指标上都是对角操作，[bonds, bath]=0，两个半阶键层合并为一个全阶键层是算符恒等（非近似）。N=6 对照测试（`test_merged_bonds.jl`，maxdim 设到不截断）：

   | 情形 | 标准 vs 合并 max\|Δ\| | 判据 |
   |---|---|---|
   | 封闭链（χ_b=1） | 2×10⁻¹³（sz）/ 5×10⁻¹³（E） | 机器精度 ✓，加速 1.8–1.9× |
   | 真实浴（χ_b=41） | 1.5×10⁻¹³（sz）/ 3×10⁻¹³（E） | 机器精度 ✓ |
   | 合并 vs ED（封闭） | ΔE = 3.3×10⁻³ | Trotter 阶不变 ✓ |

   两个实测注意点：(i) 带浴时**增广 MPS 的空间键精确秩含 χ_b 因子**——站点 i 后键的秩界是 min(χ_b·4^i, 4^{N−i})，N=6 时 (2,3) 键达 256；判断是否截断要用这个界，不是纯系统 MPS 的 4^i 界。(ii) 提速在 χ 封顶的生产情形成立（SVD 次数减半且尺寸相同）；不截断的对照运行里两模式秩增长路径不同，耗时不可比。

**中期（算法层面）**

5. ~~M2（无驱动冷却）~~ —— 用户决定跳过（2026-07-28）。
6. ~~M3（高频 Redfield 一致性）~~ —— 已完成（§6.4）：多体 Redfield Liouvillian（`RedfieldIsing`）实现并与增广 MPS 在高频下汇合；遗留 N=6 t=150 稳态对照与 ω_d=20 加密点（宜集群）。
7. 稳态直取：周期映射 𝒯 的主本征矢（幂迭代或 KrylovKit.eigsolve 作用于增广 MPS）。**由 M4 慢模实测（§6.5）升级为必要引擎**——高频 NESS 流（~1e-4）无法靠长暂态与小 Bohr 频率慢模残余（~1e-3）分离。

**长期（研究层面）**

8. 频率分辨热流 $\bar j(\omega)$：频稳态下测键流算符期望，扫 ω_d 找多体共振。
9. 双无限方案：空间 iTEBD × 时间 uniform IF（热力学极限直接稳态），见设计文档 §6。
