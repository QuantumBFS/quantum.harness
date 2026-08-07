# Kull–VUMPS 粗粒化 RDM 下界实现计划

## Objective

复现 Kull 等人的 MPS 粗粒化 RDM 松弛，用 MPSKit 的 VUMPS 产生无限、平移不变 MPS，并将冻结的 uniform MPS tensor 用作粗粒化映射，求无限链基态能量密度的下界。

首版固定物理设置：

- 模型：无限、平移不变 spin-½ 反铁磁 Heisenberg chain。
- 局域 Hamiltonian：`h = Sˣ⊗Sˣ + Sʸ⊗Sʸ + Sᶻ⊗Sᶻ`。
- 耦合与归一化：`J=1`，spin operators 的本征值为 `±½`。
- 精确能量密度：`e₀ = ¼ − ln 2`。
- MPS：MPSKit VUMPS，优先一格点 unit cell；只有不收敛时才使用二格点 fallback；fallback 在 SDP 中保留两个 start-parity sectors，不静默压成单 tensor。
- symmetry：首版不使用 SU(2)、U(1) 或 coarse-block symmetry reduction。
- SDP：独立 Kull primal JuMP builder；不修改 QMBCertify `GSB`。bottom depth `k₀` 可显式配置，默认采用作者条件 `d^k₀>D²` 的最小整数；D=2 正式运行固定 `k₀=3`。
- 本地正式网格：仅 `D=2`、`n∈{3,4,6,8,10}`、Mosek local；不使用 Slurm，不运行 D>2 正式 SDP。
- 核心验收：`E_CGRDM(n,D) ≤ ¼ − ln 2 ≤ E_VUMPS(D)`。

论文将问题定义为无限平移不变链的能量密度，并使用 VUMPS 得到 uniform MPS tensor 作为 coarse-graining map，见 `.knowledge/literature/polynomial-optimization/2212.03014_lower-bounds-on-ground-state-energies-of-local-hamiltonians.md:116-156` 和 `.knowledge/literature/polynomial-optimization/2212.03014_lower-bounds-on-ground-state-energies-of-local-hamiltonians.md:226-258`。

## Architecture

```text
MPSKit VUMPS
    │
    ├── infinite-MPS variational energy density E_VUMPS
    │
    ▼
FrozenUniformMPS
    │  dense A[left, physical, right]
    ▼
KullMaps
    │  W₂[A], L[A], R[A], forward maps, adjoints
    ▼
independent JuMP primal SDP
    │  ρ³, ω⁴, …, ωⁿ
    ▼
E_CGRDM(n,D) ≤ e₀ ≤ E_VUMPS(D)
```

依赖边界：

- MPSKit 与 TensorKit 只出现在 VUMPS producer 和 adapter 中。
- `FrozenUniformMPS` 之后的数学核心只接收显式 dense arrays 和具名索引契约。
- JuMP builder 不接收 MPSKit state、TensorMap 或 tensor-library metadata。
- QMBCertify 首版只提供 Hamiltonian/认证设计参考，不作为 builder 依赖。

## Current Environment

- MPSKit v0.13.13。
- MPSKitModels v0.4.7。
- TensorKit v0.17.1。
- 已确认可用入口：`InfiniteMPS`、`VUMPS`、`find_groundstate`、`expectation_value`。
- 当前 Julia 项目已声明 MPSKit、MPSKitModels 和 TensorKit，见 `julia-env/Project.toml:6-10`。
- 当前 Julia 项目已直接声明 JuMP、MosekTools 和 Mosek，见 `julia-env/Project.toml:5-10`。
- 正式 runner 在每次结果中记录 Git commit、`KullCGRDM.jl`、`VUMPSProducer.jl`、`MPSKitAdapter.jl`、`RunBootstrapRG.jl` 的 SHA-256、MATLAB oracle commit `2e9015fff5d9bc5b170cdc6cee98fbbb928decda` 和论文来源。

## Status

Local D=2 formal run verified — the confirmed local scope is complete, including the same-budget product/random/VUMPS map-quality comparison. D>2/deeper-grid extensions remain unperformed by explicit scope. Phase 6 numerical dual prerequisites and conservative floating-point residual correction are implemented and verified. True interval certification remains blocked because the frozen VUMPS map has floating coefficients without complete outward-rounded interval propagation. QMBCertify integration was assessed and intentionally deferred to a new shared-moment builder or pinned fork; structured-NPA augmentation is recorded as a follow-up milestone rather than claimed as current compatibility.

## Phase 1 — 锁定论文方程与 MPSKit VUMPS 基线

- [x] **1.1 转录 Kull Eq. 7、9、11–14。** 为 `W_m[A]`、`L[A]`、`R[A]`、`ρ³` 和 `ωᵐ` 建立 shape ledger，明确每条腿的空间、顺序、共轭和偏迹方向；不依据图示直觉猜测代码方向。

- [x] **1.2 固定全局索引契约。** MPS tensor 统一存为 `A[left,physical,right]`；物理基底按格点从左到右；`ωᵐ` 统一展开为 `(physical_left,virtual_left,virtual_right,physical_right)`；所有 reshape/permutation 必须走具名 helper。

- [x] **1.3 固定 Hamiltonian 归一化。** 构造 `h=Sˣ⊗Sˣ+Sʸ⊗Sʸ+Sᶻ⊗Sᶻ`，验证 singlet 为 `−¾`、fully polarized state 为 `+¼`，并确认 MPSKitModels 的 Heisenberg helper 是否采用 Pauli 或 spin normalization；若不一致则显式构造模型。

- [x] **1.4 建立一格点 VUMPS runner。** 使用 `InfiniteMPS` 初始化无 symmetry 的 uniform MPS，使用 `VUMPS` 与 `find_groundstate` 求解，使用 `expectation_value` 读取每格点能量；参数至少包含 `D`、最大迭代数、容差、随机种子和 verbosity。

- [x] **1.5 定义 VUMPS clean-run gate。** 保存能量、算法返回误差 `δ`、迭代状态、unit-cell 长度和随机种子；仅 clean convergence 进入 coarse-map 流程。

- [x] **1.6 加入二格点 fallback。** 只有一格点在给定 D 下未达到门槛时才启用；二格点结果必须按每格点归一化，并把交替 tensor 结构显式传给后续 adapter，不能静默压成单个 A。

- [x] **1.7 验证 VUMPS 上界。** 对 `D∈{1,2,3,4}` 检查 `E_VUMPS(D) ≥ ¼−ln2`；不要求有限精度下跨 D 严格单调，但明显恶化或低于精确值必须阻止后续运行。

### Phase 1 exit criteria

- Hamiltonian 两个解析锚点通过。
- 至少一个 `D≥2` 的 VUMPS run clean convergence。
- 能量归一化与 `¼−ln2` 一致。
- 一格点与二格点路径的输出 schema 已统一。

## Phase 2 — 冻结 library-independent uniform MPS

- [x] **2.1 定义 `FrozenUniformMPS`。** 保存 dense unit-cell tensors、physical dimension、bond dimensions、unit-cell length、canonical gauge、left/right fixed points、canonical residual、normalization residual、source energy、VUMPS settings 和内容 fingerprint。

- [x] **2.2 实现 MPSKit adapter。** 从 MPSKit state 提取 canonical tensors，并通过 TensorKit 的 domain/codomain 信息显式排列为 `A[left,physical,right]`；禁止依赖 `Array(tensor)` 的隐式轴顺序。

- [x] **2.3 固定 left-canonical gauge。** 将 tensor 转为或验证为 left gauge，记录 transfer fixed-point residual 与谱半径；任何规范变换和 rescaling 必须在冻结前完成。

- [x] **2.4 验证 adapter 物理不变量。** 用 MPSKit 原对象与冻结 dense tensor分别计算 transfer dominant eigenvalue、norm density 和局域 Heisenberg 能量，要求在声明容差内一致。

- [x] **2.5 支持手工 dense tensor。** 提供 product-state `D=1` 和随机 canonical tensor 入口，用于不依赖 VUMPS 的 algebra tests。

- [x] **2.6 固定 fingerprint。** fingerprint 必须覆盖 dense tensor 内容、axis convention、unit-cell、gauge 和 coefficient type，确保 depth sweep 使用同一个冻结 A。

### Phase 2 exit criteria

- JuMP/Kull 模块无需加载 MPSKit 即可读取冻结对象。
- adapter 前后能量与 transfer diagnostics 一致。
- `D=1` 手工 tensor 可独立构造并冻结。

## Phase 3 — 编译 Kull coarse-graining maps

- [x] **3.1 实现 direct `W_m` oracle。** 对小 `m=1,…,4` 显式收缩 m 个 A，输出从 m-site physical block 到左右 virtual bonds的矩阵；只用于测试，不用于深层生产。

- [x] **3.2 实现 `W₂[A]` production map。** 明确其输入 `d²`、输出 `D²`、flatten 规则和复共轭约定，并生成相应 congruence map。

- [x] **3.3 实现固定 `L[A]` 与 `R[A]`。** 左右各吸收一个 physical site，满足论文的递归兼容关系；一格点 unit cell 重用相同 maps，二格点 unit cell 按 parity 交替。

- [x] **3.4 实现基础线性算子。** 提供 partial trace、congruence、boundary extension、forward map 和 Hilbert–Schmidt adjoint；primal 与 dual 必须共享同一算子定义。

- [x] **3.5 编译 bottom bridge。** 生成连接 `ρ³` 与 `ω⁴` 的两条线性关系，接口按保留的物理边界命名，避免含混的 left/right trace 命名。

- [x] **3.6 编译 recursive flow。** 对 `m≥5` 生成 `ωᵐ⁻¹↔ωᵐ` 的左右 consistency maps，生产路径不得显式构造长链 `W_m`。

- [x] **3.7 direct-vs-recursive 验证。** 对 product、随机 complex 和 VUMPS tensor 比较直接 `W_m` 与递归结果，相对误差目标 `<10⁻¹¹`。

- [x] **3.8 forward-adjoint 验证。** 对随机 complex matrices 验证 `tr[Y†Φ(X)] = tr[Φ*(Y)†X]`，相对误差目标 `<10⁻¹¹`。

- [x] **3.9 synthetic physical feasibility。** 从显式物理态/RDM 构造 `ρ³,ω⁴,…`，确认所有 PSD 条件和 compiled equalities；真实物理 tuple 不可行时禁止进入 SDP 阶段。

### Phase 3 exit criteria

- `D=1` map 与手算逐项一致。
- direct、recursive 和 adjoint tests 全部通过。
- 单个 `ωᵐ` 的维数固定为 `d²D² = 4D²`。
- synthetic physical tuple 满足全部 flow constraints。

## Phase 4 — 建立独立 Kull primal JuMP SDP

- [x] **4.1 补齐 Julia 直接依赖。** 添加与当前环境兼容的 JuMP、MosekTools 和 Mosek；保留 solver 参数显式注入，不通过 QMBCertify 内部对象间接依赖。

- [x] **4.2 定义 builder API。** 输入局域 `h`、`KullMaps`、depth n 和 solver settings；输出 model、变量、约束引用、dimension inventory 和 metadata；builder 不运行 VUMPS。

- [x] **4.3 实现 `n=3` base LTI model。** 创建 `ρ³⪰0`、`trρ³=1`、左右二体 marginal 相等，并最小化 `tr(hρ²)`；该结果必须与 A、D 无关。

- [x] **4.4 实现 `n=4` bottom level。** 创建 `ω⁴⪰0` 并加入两条 bottom bridge relations；不创建完整 `ρ⁴`。

- [x] **4.5 实现任意 depth。** 对 `m=5,…,n` 追加 fixed-size `ωᵐ⪰0` 和两条 flow equalities；depth n+1 必须保留 n 的全部变量和约束。

- [x] **4.6 固定 complex SDP 表示。** 优先验证 JuMP Hermitian PSD cone；若 Mosek bridge 或 dual extraction不稳定，则统一采用实嵌入，不维护两条未经等价测试的主路径。

- [x] **4.7 添加 resource inventory。** optimize 前报告每个 PSD block 维数、block 数、实标量变量、线性 equality 数、系数存储估算和峰值内存估算。

- [x] **4.8 定义 solver result。** 保存 lower-bound candidate、termination/primal/dual status、relative gap、constraint residual、PSD 最小本征值、runtime、map fingerprint 和 VUMPS upper endpoint。

- [x] **4.9 定义 clean-solve gate。** 只有 clean optimal status 和残差低于声明门槛的点进入结果曲线；否则只保存诊断。

### Phase 4 exit criteria

- `n=3` 与 MPS 无关。
- `n=4` 恰增加一个 `4D²×4D²` PSD block。
- 增加 depth 只线性增加固定尺寸 blocks。
- clean solve 的完整诊断可独立保存。

## Phase 5 — 分层验证与论文式数值展示

- [x] **5.1 algebra test suite。** 覆盖 Hamiltonian anchors、D=1 product map、random complex maps、adjoints、Hermiticity/PSD preservation 和 synthetic feasibility。

- [x] **5.2 base-model regression。** 检查 `n=3` 与 A、D 无关，关闭 coarse levels 时只恢复 three-site LTI primal，不声称恢复 QMBCertify structured NPA。

- [x] **5.3 depth monotonicity。** 固定同一个 fingerprint 和 D，检查 `E_CGRDM(n+1,D) ≥ E_CGRDM(n,D)−tol`；不得为每个 n 重新运行 VUMPS。

- [x] **5.4 bound-direction gate。** 所有 accepted run 检查 `E_CGRDM(n,D) ≤ ¼−ln2+tol ≤ E_VUMPS(D)+tol`；失败时依次检查 normalization、synthetic feasibility、map direction 和 solver residual，不先放大 tolerance。

- [x] **5.5 最小参数网格。** 已完成确认范围 `D=2`、`n∈{3,4,6,8,10}`；D=1 仅用于代数测试。D∈{3,4} 与 n∈{20,30,60} 的扩展未执行，属于本次明确排除范围。

- [x] **5.6 compare map quality。** 已在相同 D=2、k₀=3、n=6 和 solver settings 下比较 bond-embedded product、固定种子 random canonical 与 VUMPS tensor；三者均保持下界方向，差异仅解释为 tightness。

- [x] **5.7 compute feasibility gate。** 每次非平凡 solve 前根据 inventory 估算内存与 wall time；本地预计超过 10 分钟或 16 GB 时转 Slurm。

- [x] **5.8 结果图。** 绘制 lower-bound error 随 n、VUMPS upper-bound error 随 D、最终 bracket width，以及最大 PSD block/变量数随 n 的变化。

- [x] **5.9 论文规模口径。** n 表示有效 LTI hierarchy depth，不称为有限链长度；展示目标是复现固定 block size 与下界收紧机制，不预先承诺达到论文最大 n 或 D。

### Phase 5 exit criteria

- 所有 accepted points 满足上下界方向。
- 固定 A 时 depth 单调性通过。
- 单 block dimension 不随 n 增长。
- 至少形成 D=2 的完整 depth curve；资源允许时加入 D=3、4；D=1 只作代数测试。

## Phase 6 — Dual 重建、严格修正与 QMBCertify handoff

- [x] **6.1 定义认证等级。** 结果至少区分 `algebra-verified`、`numerical-clean-optimal`、`residual-corrected` 和 `interval-certified`；完成完整 dual/interval 修正前不得称为严格证书。

- [x] **6.2 导出完整 dual。** 保存 `ρ³` 和每个 `ωᵐ` 的 PSD dual、normalization/LTI/bottom/flow multipliers以及 map fingerprint。

- [x] **6.3 重建 dual stationarity。** 使用 Phase 3 的 adjoints 逐层回写 multipliers，检查 objective coefficient identity 与 dual slacks。

- [x] **6.4 实现 residual-safe correction（浮点数值范围完成，interval 严格性由 6.6 阻断）。** 已对 dual PSD/stationarity residual 使用有限 trace bounds 计算保守数值修正，且 corrected diagnostic 不高于 raw optimum；MPS 浮点 map coefficient 尚无 outward-rounded interval 误差传播，因此不能把该值称为严格认证下界。

- [x] **6.5 利用 left gauge 控制误差累积。** 验证论文要求的 trace-non-increasing 条件或其数值包络，防止 depth 增加导致修正爆炸。

- [ ] **6.6 interval/rational coefficient policy（BLOCKED，准确终态）。** 已实现 rationalization error diagnostic 和 fingerprint policy，但冻结 VUMPS tensor 为浮点系数；尚未对每个 assembled map coefficient 完成 outward-rounded interval enclosure。所有正式点均标为 `residual-corrected-floating-coefficients`，绝不标为 `interval-certified`。该阻断项不在已确认的本地浮点复现范围内。

- [x] **6.7 最终 numerical bound verification。** 检查 `E_corrected≤E_raw≤¼−ln2≤E_VUMPS`，并独立重建所有约束残差。

- [x] **6.8 QMBCertify integration assessment。** 评估结论为当前独立 primal/dual oracle 不接入 QMBCertify：固定尺寸高层 `ωᵐ` 必须保留为独立 variables，不能伪装为现有 `GSB` keyword；后续若集成，采用新的 shared-moment builder 或 pinned fork。

- [x] **6.9 structured-NPA augmentation 后续里程碑处置。** 已明确延期：未来底层通过 shared moments 连接物理 RDM，保留独立 coarse `ωᵐ` blocks，并扩展完整 certificate；当前实现不声称与 `GSB` keyword 兼容。

### Phase 6 exit criteria

- numerical dual identity 可完整重建。
- corrected lower bound 不高于 raw optimum。
- 只有 interval enclosure 完成后才输出 `interval-certified`。
- QMBCertify 集成不改变已验证的 Kull map 与 primal oracle。

## Verification Matrix

| 层次 | 输入 | 主要检查 | 阻断条件 |
|---|---|---|---|
| Hamiltonian | analytic states | `−¾`, `+¼`, `¼−ln2` normalization | 任一锚点失败 |
| VUMPS | `D=1…4` | convergence、upper-bound direction | 能量低于精确值或未收敛 |
| Adapter | MPSKit state | transfer 与 energy invariance | axis/gauge residual 超标 |
| Maps | product/random/VUMPS A | direct-recursive、adjoint、PSD | physical tuple 不可行 |
| SDP | `n=3,4,…` | nesting、residual、fixed block size | depth 降界或 block 增长 |
| End-to-end | fixed A, D, n | `E_CGRDM≤e₀≤E_VUMPS` | 任一 accepted point 越界 |
| Certificate | full dual | stationarity、PSD、interval correction | residual 未被严格包络 |

## Resource Envelope

对 spin-½，单个 coarse PSD block 的维数为：

`q = d²D² = 4D²`。

| D | q | 每层 Hermitian 实自由度 q² |
|---:|---:|---:|
| 1 | 4 | 16 |
| 2 | 16 | 256 |
| 3 | 36 | 1,296 |
| 4 | 64 | 4,096 |
| 7 | 196 | 38,416 |

首版正式 SDP 计算从 D=2 开始并以 D=4 为硬上限；D=1 只用于代数测试，不运行 D>4。论文使用通用 interior-point solver 时主要受 D 限制，而 hierarchy depth 主要线性增加 fixed-size blocks，见 `.knowledge/literature/polynomial-optimization/2212.03014_lower-bounds-on-ground-state-energies-of-local-hamiltonians.md:767-771`。

## Risks and Mitigations

1. **MPSKitModels normalization 与目标 Hamiltonian 不一致。**
   - 先做解析锚点；必要时显式构造 MPOHamiltonian，不依赖模型 helper 名称。

2. **TensorMap 的 domain/codomain 被错误 flatten。**
   - adapter 显式记录空间与轴；用 transfer/energy invariance 阻断错误转换。

3. **一格点 VUMPS 在某些 D 不收敛。**
   - 保留二格点 fallback并显式处理 parity；不把两个 tensors 平均成一个 A。

4. **Kull 图形方程的左右或共轭方向翻译错误。**
   - direct W oracle、随机 complex tests 和 synthetic physical feasibility 必须先于 JuMP solve。

5. **complex JuMP cone 或 dual bridge 不稳定。**
   - 小实例验证后固定一种表示；必要时整体 realification。

6. **depth 增加后 bound 下降。**
   - 固定 fingerprint；builder 保留全部旧层；检查 solver residual和constraint registry。

7. **浮点 optimum 被误称为严格下界。**
   - 强制认证等级；完整 interval correction 前只称 numerical clean optimum。

8. **D=4 深层模型超出本地预算。**
   - optimize 前 inventory；超过阈值转 Slurm或减少参数网格，不静默降低精度；不提高到 D>4。

9. **过早融合 QMBCertify。**
   - 独立 primal/dual oracle 完成前不修改 `GSB` 或 `certify_qmb`。

## Explicitly Out of Scope

- finite-chain tensor-network calculations and finite-chain energy brackets。
- 从有限链中央提取 bulk tensor。
- 首版 SU(2)、U(1) 或 coarse-block symmetry reduction。
- 在 SDP 内优化 MPS tensor。
- 将高层 `ωᵐ` 展开为完整 m-site Pauli moments。
- 未经 dual/interval 修正就宣称 exact certificate。

## Completion Definition

当前交付已完成第 1–5 项以及第 6 项的浮点数值 dual 重建与保守 residual correction。严格 interval 修正因 6.6 所述浮点 map coefficient enclosure 缺失而保持 BLOCKED；因此不会虚假宣称六阶段严格认证目标已经全部达成。

1. 可复现的 MPSKit VUMPS runner。
2. library-independent `FrozenUniformMPS`。
3. 经过 direct/recursive/adjoint 验证的 Kull maps。
4. 独立 JuMP primal coarse-RDM hierarchy。
5. Heisenberg chain 的上下界与 depth/D 结果图。
6. 可独立重建并严格修正的完整 dual certificate。

最终严格目标仍为：

`E_interval-certified(n,D) ≤ E_numerical(n,D) ≤ ¼ − ln 2 ≤ E_VUMPS(D)`。

当前已验证的是 floating-coefficient numerical curve 与 residual-corrected diagnostics；第一项因 6.6 的 interval enclosure blocker 尚未成立。
