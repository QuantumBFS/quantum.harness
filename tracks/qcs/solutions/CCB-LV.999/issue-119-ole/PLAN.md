# Issue #119 Operator Loschmidt Echo Goal-based 计划

## 1. 路线决策

本目录服务于 Quantum Harness challenge
[#119：Advantage or artifact? Hunt on the Quantum Advantage Tracker](https://github.com/QuantumBFS/quantum.harness/issues/119)。
团队将 Operator Loschmidt Echo（OLE，算符 Loschmidt 回声）设为主路线：

1. 在 baseline 实例 `operator_loschmidt_echo_49x648` 上复现公开 BP-TN 结果。
2. 不以“多报几位小数”为精度提升，而是补齐统计误差、有限键维误差、浮点误差
   和 δ=0 重标度偏差，给出可审计的误差预算。
3. baseline 复现通过后，增加 PEPO/Heisenberg-picture 2D 张量网络测试，以
   operator bond dimension 和环境收缩维度的双重收敛检查，提供不同于 BP-TN
   Schrödinger-picture 的独立系统误差诊断。
4. 将完全相同的输入解析、BP-TN 演化、随机初态和误差分析迁移到 active 实例
   `operator_loschmidt_echo_49x1296`。
5. 只有 `49x1296` 通过资源和收敛门槛，才考虑 `70x1872`；本阶段不把
   `56x1488` 作为目标。

本计划按逐个可验收的 goal 组织，不按自然日组织。原有
[Variational 计划](../issue-119-variational/PLAN.md)保持不变，作为 OLE 路线受阻时
可独立启动的备选路线。

## 2. 初学者需要先理解的六件事

### 2.1 什么是 Loschmidt echo

普通 Loschmidt echo 可以想成：

1. 让一个量子态向前演化；
2. 在中途施加一个很小的扰动；
3. 尝试把演化倒放；
4. 检查最终状态能否回到起点。

若系统对扰动不敏感，回声接近 1；若演化把局域信息快速扩散到整个系统，小扰动会
被放大，回声下降。

本问题研究的不是一个特定量子态能否回来，而是一个算符 O 在演化后是否仍与扰动
Vδ 相容，因此叫 **operator** Loschmidt echo。官方目标量为

```text
fδ(O) = 2⁻ⁿ Tr(U O U† Vδ† U O U† Vδ).
```

这里：

- n 是量子比特数；
- O 是 Pauli-Z 字符串；
- U 是 Ising-like Floquet 电路；
- Vδ = exp(−iδG) 是在回声中间加入的扰动；
- fδ(O) 是无限温度下对所有基态取平均的算符相关量。

精确公式、文字推导和提交的 QASM 在算符排列上必须相互核对。Tracker 评分以官方
QASM 所定义的电路为准；若文字公式与 QASM 不一致，不能静默选择其中一个，而要在
报告中记录差异并用小系统精确计算判定实现。

### 2.2 为什么不能直接保存 49-qubit 波函数

49 个量子比特的完整状态包含 2⁴⁹ 个复振幅。即使每个复数只占 16 bytes，也需要
约 8 PiB 内存，因此 full statevector 不能作为完整实例的主方法。

Tensor network（张量网络）把波函数拆成许多局域张量。BP-TN 使用 belief
propagation（BP，置信传播）近似每个局域张量看到的环境，再通过奇异值分解截断
张量之间的连接。最大 bond dimension（键维）χ 控制保留的信息量：

- χ 越大，通常越准确；
- 内存和时间会快速上升；
- 单个 χ 的结果没有自动携带误差条，必须做 χ 收敛比较。

### 2.3 为什么还要随机初态

公式中的 trace 等价于对全部 2ⁿ 个计算基态求平均。不能枚举这些基态时，可从中
均匀随机抽取 N_init 个 bitstring。对第 i 个初态 zᵢ，先计算 observable 的初态
parity `σᵢ=⟨zᵢ|O|zᵢ⟩∈{−1,+1}`，再定义单样本
`xᵢ=σᵢ Re[fδᶻⁱ(O)]`：

```text
f̂δ(O) = (1/N_init) Σᵢ xᵢ.
```

样本均值的标准误差近似为 `s/√N_init`。这产生与 χ 截断完全不同的两类误差：

- 增加 N_init 只减少随机初态的统计误差；
- 增加 χ 主要减少张量网络截断偏差。

只增加样本数但固定过小 χ，不会修复系统偏差；只增加 χ 但只算少量初态，也无法
得到窄统计区间。

### 2.4 什么是 δ=0 重标度

当 δ=0 时没有扰动，精确 OLE 应为 1。有限 χ 的 BP-TN 或有噪声的量子硬件可能得到
S₀≠1，因此有人报告

```text
Sδ,rescaled = Sδ,raw / S₀,raw.
```

它可能抵消共同的归一化误差，也可能掩盖 δ=0 与 δ=0.15 的误差并不相同这一事实。
所以本计划规定：

- **主结果始终是 raw、未重标度的 Sδ**；
- S₀、Sδ/S₀ 和两者差值作为数值偏差诊断同时报告；
- 重标度结果不得在没有解释的情况下替代原始结果。

### 2.5 PEPO/Heisenberg-picture 与 BP-TN 有什么不同

BP-TN 主路线采用 Schrödinger picture：从许多随机计算基态出发，向前演化状态，
再用样本平均估计 trace。PEPO（projected entangled-pair operator，投影纠缠对
算符）采用 Heisenberg picture：不再逐个演化随机初态，而是直接演化目标算符。
例如把

```text
Õ = U O U†
```

表示成 heavy-hex 图上的二维 PEPO，再收缩
`2⁻ⁿTr(Õ Vδ† Õ Vδ)`。某些库默认计算的是 `U†OU` 而不是 `UOU†`，因此实际门序
必须通过 G1 的小系统 exact oracle 核对，不能只根据“Heisenberg picture”这个名字
推断。

PEPO 的虚拟键维记作 `Dop`。它限制演化算符能够保留的 operator entanglement
（算符纠缠）；最终二维网络的近似收缩还需要独立的环境维度 `χenv`。因此：

- 增大 `Dop` 主要减少算符演化的截断误差；
- 增大 `χenv` 主要减少最终二维网络的环境收缩误差；
- 若直接收缩归一化 trace，就不需要随机初态，也没有 `N_init` 统计误差；
- 只扫描 `Dop` 或只扫描 `χenv`，都不能宣称 PEPO 已收敛。

这条路线的价值不是保证比 BP-TN 更准，而是提供结构不同的近似：BP-TN 主要压缩
演化中的状态，PEPO 主要压缩传播后的算符。两者若收敛到一致区间，可显著增强
baseline 的可信度；若不一致，则能定位尚未被原误差预算捕捉的系统偏差。

### 2.6 为什么 `49x1296` 是最合适的 active 目标

Tracker 当前把 `49x648` 列为 baseline，把 `49x1296` 和 `70x1872` 列为 active
OLE 实例。前两个实例具有：

- 相同的 49-qubit heavy-hex 子图；
- 相同的 b=0.25、δ=0.15；
- 相同的 O=Z₅₂Z₅₉Z₇₂；
- 相同的门约定和 QASM 格式；
- 唯一主要难度变化是 L 从 3 增至 6，门数从 648 增至 1296。

因此 `49x648 → 49x1296` 是一次受控的电路深度扩展。相比之下：

- `70x1872` 同时增加 qubit 数和深度；
- `56x1488` 改变 δ、扰动结构、可观测量和 scattering 参数，当前 BP-TN
  `χ=768, N_init=20` 的公开计算约需 211 GPU-node-hours，不是第一步的平滑迁移。

## 3. 已有结果与我们要补的缺口

以下 tracker 状态和数值核对于 2026-07-27。Tracker 是活动项目；后续若条目变化，
G0 会把重新核对的日期和来源 commit 写进输入 manifest。

### 3.1 Baseline：`49x648`

官方参数：

| 项 | 值 |
|---|---|
| qubits | 49 |
| Floquet parameter | L=3 |
| b | 0.25 |
| perturbation | δ=0.15 |
| observable | O=Z₅₂Z₅₉Z₇₂ |
| official QASM size | 162,721 bytes |
| official QASM Git blob | `716305eb99ed9fafb356bf971269ff1d8d66b03e` |

公开参考：

| 方法 | 结果 | 公开运行时间 | 主要限制 |
|---|---:|---:|---|
| BP-TN, χ=192, raw | 0.8202512915 | 118 s, CPU | 无误差条 |
| BP-TN, χ=512, raw | **0.821658489** | 149 s, CPU | 无误差条 |
| Single-path Monte Carlo | 0.808 | 640 s, Apple M1 Max | 丢失 Pauli path 相位干涉 |
| IBM Heron R3, global rescaling | 0.824 | 4260 s, QPU | 无公开误差条 |

两个公开 BP-TN 结果之差为

```text
Δχ,published = 0.821658489 − 0.8202512915 = 0.0014071975.
```

这不是严格误差条，但提供了第一个可操作精度尺度。我们的第一目标是复现
χ=192/512 的中心值；第二目标是把 `Δχ,published` 替换为基于共同初态、更多 χ
和明确统计区间的误差预算。

### 3.2 Active：`49x1296`

官方参数与 baseline 相同，只将 L 改为 6。QASM 大小为 321,769 bytes，Git blob
为 `829be362d1526ea9afe8e13fe1594e2e00eaa2e2`。

公开参考：

| 方法 | 结果 | 公开运行时间 | 主要限制 |
|---|---:|---:|---|
| BP-TN, χ=512, raw | 0.88157984 | 1680 s, A100 80 GB | 无误差条 |
| BP-TN, χ=512, δ=0 rescaled | 0.94257142 | 1680 s, A100 80 GB | 与 raw 相差约 0.061 |
| Single-path Monte Carlo | 0.619 | 1492 s, Apple M1 Max | 相位不敏感，不能作精度基准 |
| IBM Heron R3, global rescaling | 0.649–0.662 | 4120–4260 s, QPU | 无公开误差条 |

这里最重要的不是哪一个数字“更像量子结果”，而是解释为何 raw 与 rescaled
差异如此大，以及 χ=512 是否已足够。一个可信的经典结果不应通过挑选重标度方案
去接近某个预期值。

## 4. 方法选择

### 4.1 主方法：BP-TN Schrödinger-picture 演化

主实现使用
[TensorNetworkQuantumSimulator.jl](https://github.com/JoeyT1994/TensorNetworkQuantumSimulator.jl)
0.4.4。它基于 ITensors.jl，公开支持：

- 任意图结构的 tensor-network state；
- heavy-hex lattice；
- `Rx`、`Rz`、`Rzz` 等本实例需要的门；
- `BeliefPropagationCache`；
- 通过 `maxdim=χ` 和 `cutoff` 控制截断；
- BP、boundary-MPS、loop correction 和小系统 exact contraction。

这是推荐主线，因为公开 χ=192/512 结果使用同一方法家族，且 49×648 与
49×1296 只需要替换 QASM 和 L，不需要更换表示。

计划撰写时上游 `main` 的参考 commit 为
`b5d4089849de1cc23806aa8325e8db56a55f2e0b`。正式实现使用 solution-local
`Project.toml` 与 `Manifest.toml` 固定实际解析出的包版本和 tree hash，不追踪
浮动的 `main`。根 Makefile 当前可安装 ITensors，但没有独立的 TNQS target；
因此 TNQS 由本 solution 的 Julia environment 明确拥有，不假装是全局依赖。

### 4.2 进阶测试：PEPO/Heisenberg-picture 2D 张量网络

PEPO 路线只在 G2 的 BP-TN baseline 复现通过后启动。它受
[Liao 等人的 127-qubit kicked-Ising PEPO 工作](https://arxiv.org/abs/2308.03082)
直接启发：从局域 Pauli 算符开始，在 Heisenberg picture 中反向穿过电路，用二维
PEPO 表示逐渐扩展的算符，并在每次双比特门后把增长的虚拟键截断到 `Dop`。

第一实现候选是 quimb 的
[`CircuitPEPOSimpleUpdate`](https://quimb.readthedocs.io/en/latest/autoapi/quimb/tensor/circuit/pepo/index.html)：
它支持 arbitrary-geometry edge list、反向 lightcone、Vidal-style gauging 和
`max_bond`/`cutoff` 截断，能够直接表示本实例的 heavy-hex 子图。正式实现仍须用
G1 exact oracle 验证门序、角度和 `UOU†`/`U†OU` 约定；不能因为 API 名称匹配就
跳过协议测试。根 Makefile 已提供 `make install quimb`，但依赖版本仍由本
solution 的锁定环境拥有。

`CircuitPEPOSimpleUpdate` 负责产生有限 `Dop` 的演化算符；OLE 的 PEPO–PEPO
闭合 overlap 另用带最大边界维度 `χenv` 的 boundary contraction 收缩，并在小系统
上用 cotengra exact contraction 复核。这样 `Dop` 和 `χenv` 才是两个可单独扫描的
误差来源，而不是一个含义不清的 `max_bond`。

这条路线使用两个独立精度旋钮：

- `Dop`：PEPO operator bond dimension，控制演化算符的压缩；
- `χenv`：最终 PEPO overlap/trace 的环境收缩维度，控制二维闭合网络的压缩。

它还记录逐门/逐层 discarded weight、operator norm drift、Hermiticity defect、
最终虚部、peak memory 和 walltime。PEPO 结果在完成 `Dop` 与 `χenv` 双扫描前
一律标记为 diagnostic；不能用单个较大 `Dop` 的数值替代 BP-TN baseline。

PEPO 暂不自动迁移到 `49x1296`。只有 G3P 在 `49x648` 上通过精度和资源门槛后，
才为 active 实例另做 feasibility gate，避免把 baseline 测试未经验证地升级成第二
条生产主线。

### 4.3 精确/更受控张量网络：验证方法

TensorCircuit-NG 或 quimb/cotengra 用作独立小系统 oracle；TNQS 自带的 exact、
boundary-MPS 和 loop correction 用作同语言交叉检查。它们的职责是：

- 在 n≤20、L≤2 的裁剪实例上验证 QASM 门序、角度符号和 observable mapping；
- 检查 BP 测量与 exact contraction 的差；
- 在完整 49-qubit 问题上只先做 contraction-path 与内存估计，不能未经估算直接
  发起精确 contraction。

它们不是完整 49×1296 的默认主方法，因为 exact contraction 的最大中间张量可能
突然超过内存。

### 4.4 Pauli propagation：负面对照，不作 headline

Single-path Pauli Monte Carlo 便宜，也能复现公开 0.808/0.619 附近的数值。但公开
方法说明它只按振幅平方选择 Pauli path，对旋转角 θ→−θ 不敏感，无法保留路径之间
的相位干涉；增大保留 Pauli 数时结果还出现不稳定漂移。

因此它只承担两个任务：

- 复现“符号翻转后结果不变”的失败模式；
- 作为低成本 runtime 和 operator-spreading 诊断。

它不能验证 BP-TN 的高精度 OLE，也不能提供最终误差条。

## 5. Goal 总览

| Goal | 产出 | 通过条件 |
|---|---|---|
| G0：冻结协议与环境 | QASM manifest、门/节点映射、锁定环境、资源卡 | 两个 QASM 的来源和 hash 固定；49 个逻辑 qubit 与物理标签映射明确 |
| G1：建立小系统精确 oracle | QASM parser tests、n≤20 精确结果、δ=0/逆电路检查 | 两个独立实现对同一小实例误差≤1×10⁻¹⁰ |
| G2：复现 49×648 公开基线 | χ=192/512 raw 结果、逐层截断记录 | χ=512 与 0.821658489 的差≤max(0.002, 3SE) |
| G3：提升 baseline 精度 | paired-χ 扫描、N_init 自适应、误差预算 | 给出 raw 中心值、统计区间和数值误差包络；不再报告无误差数字 |
| G3P：PEPO 进阶测试 | Heisenberg-picture PEPO direct-trace 结果、Dop/χenv 双扫描 | 小系统 exact 通过；完整 baseline 给出独立收敛包络或明确的失败边界 |
| G4：审计系统偏差 | δ=0、raw/rescaled、精度与方法交叉检查 | 每个误差来源分开量化；重标度不被冒充为严格修正 |
| G5：49×1296 可行性门 | active pilot、内存/时间模型、go/no-go | 生产设置满足 cluster 内存和 walltime 安全余量 |
| G6：49×1296 生产结果 | active raw 与 rescaled 结果、误差预算 | χ 趋势和初态统计可解释；否则明确标记 diagnostic |
| G7：可复现交付 | 脚本、配置、run records、图和短报告 | 从干净 checkout 可重跑；正面或负面结果均可审计 |
| G8：下一实例决策 | 70×1872 或停止的书面依据 | 仅在 G6 通过后决策，不阻塞本路线完成 |

## 6. Goal 详细设计

### G0：冻结协议、输入和软件环境

#### 要解决的问题

49 个活动 qubit 使用 IBM 物理编号，observable 出现 52、59、72，并不代表需要
73-qubit statevector。若解析器把物理编号直接当连续数组下标，计算会悄悄变成另一
个问题。QASM 门顺序、Qiskit rotation convention 和逆演化角度符号同样不能凭
文字描述重建。

#### 产出

1. 从 tracker 的固定 commit 下载：
   - `49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm`；
   - `49Q_OLE_circuit_L_6_b_0.25_delta0.15.qasm`。
2. 生成 manifest，记录 URL、tracker commit、Git blob SHA、SHA-256、字节数、
   QASM register、活动 qubit、门数、门类型和 observable；同时导出带明确门序、
   角度和内部节点编号的规范化 JSON gate manifest，供 Julia BP 与 Python PEPO
   runner 共同读取。
3. 解析 QASM 中的物理标签，生成显式 `physical_label ↔ internal_index` 映射。
4. 固定 Julia ≥1.10、TNQS 0.4.4、ITensors 0.9 和实际 Manifest；同时记录 Python
   minor version，并固定 quimb、cotengra、numpy 的实际解析版本。
5. 将公开提交未说明的 `N_init`、SVD cutoff、BP tolerance、message update
   schedule 和 dtype 列为 provenance gaps。默认 pilot 可采用上游示例中的
   `cutoff=1×10⁻¹²` 与 `normalize_tensors=true`，但在获得来源确认前不得声称这些
   就是公开 χ=512 计算的原始设置。
6. G0 只允许小规模本地检查。非平凡计算前确认
   `skills/using-slurm/profiles/active.toml`，若不存在则先完成 cluster 配置。

#### 通过条件

- L=3 与 L=6 文件分别解析为 49 个活动 qubit 和 648/1296 个 tracker 门；
- O 精确映射到三个指定物理 qubit；
- 不支持的 QASM gate、重复映射、未知参数或 hash 变化都会立即停止；
- 运行开头打印完整协议卡，等待团队确认：
  `QASM + gate convention + L + b + δ + O + N_init + χ + dtype + resource`。

### G1：建立小系统精确 oracle

#### 要解决的问题

在 49-qubit 结果附近得到一个数字不能证明门序正确。角度差一个负号、把 U 与 U†
对调或漏掉一次扰动，都可能产生看似合理的 OLE。

#### 方案

1. 从完整 heavy-hex 图中取包含 observable 和扰动支撑的连通局域 patch。
2. 建立 n=7、12、16、20 的裁剪实例，并取 L=0、1、2。
3. 用两个独立实现计算同一量：
   - TNQS exact contraction；
   - TensorCircuit-NG statevector 或 quimb exact contraction。
   JAX 路线必须显式启用 x64，不能把默认 float32 结果拿来验收 1×10⁻¹⁰ 阈值。
4. 至少验证：
   - L=0 的直接公式；
   - δ=0 时 f₀=1；
   - 空扰动集合时 fδ=1；
   - U 后接精确 U† 回到初态；
   - θ 与 −θ 的门顺序正确；
   - 结果虚部只包含浮点噪声。
5. 用同一个种子文件生成随机计算基态；禁止两个实现各自随机抽样。

#### 通过条件

- ComplexF64 下两个实现的每个小实例相差≤1×10⁻¹⁰；
- δ=0 和逆电路残差≤1×10⁻¹²；
- QASM 直接执行与从解析后 gate list 重建的结果相同；
- 若官方文字公式与 QASM 给出不同结果，报告两者差异，后续 tracker 结果使用
  QASM 路线，不静默“修正”输入。

### G2：复现 `49x648` 公开 BP-TN 基线

#### 方案

1. 使用固定 seed bank 的前 20 个随机初态做 pilot。
2. 先运行 χ=64、128，检查每层：
   - OLE partial estimate；
   - BP message 收敛状态；
   - SVD discarded weight/error；
   - norm 与 δ=0 defect；
   - peak memory 和 walltime。
3. 通过 pilot 后运行 χ=192，与公开 0.8202512915 对照。
4. 再从相同初态运行 χ=256、384、512；不同 χ 必须共享初态，形成 paired
   comparison。
5. 对 δ=0 和 δ=0.15 使用相同初态、相同 χ 和相同门排序。
6. 保存每个初态的结果，不只保存最终平均值。

#### 通过条件

- χ=192 与 χ=512 均成功完成且没有 NaN、BP 不收敛或内存溢出；
- χ=512 raw 均值满足
  `|f̂−0.821658489| ≤ max(0.002, 3×SE)`；
- χ 增大时逐层截断指标总体改善；若中心值不单调，必须由 paired differences
  和误差区间解释；
- δ=0 defect、raw 和 rescaled 三者都保存；
- 未达到条件时停在 G2，先排查协议或实现，不允许靠增大 N_init 掩盖偏差。

### G3：给 baseline 建立并收紧误差预算

#### 统计误差

对最高 χ 的 N 个初态结果 xᵢ，报告：

```text
μ = mean(xᵢ)
SE = std(xᵢ) / √N
95% statistical CI = μ ± t₀.₉₇₅,N−1 × SE.
```

先用 N=20 pilot 估计方差，再计算达到统计半宽
`εstat,target=5×10⁻⁴` 所需的 N。N 按 20→40→80→160→320→512 扩展，只追加
seed bank 后缀，不更换已有样本。若 N_required>512 或资源预算不允许，报告已达到
的统计区间，不伪装为目标精度。

#### 有限 χ 误差

同一初态在 χ=256、384、512 上形成 paired differences。定义保守包络：

```text
εχ = max(
  |μ512 − μ384|,
  |μ384 − μ256|
).
```

同时绘制每个初态的 paired difference，防止均值偶然抵消。若 χ=512 仍处在明显
漂移区，追加 χ=640 或 768 前必须先做资源预测；不能仅凭三点外推宣布收敛。

#### 浮点与重标度诊断

- 在固定 8 个初态、χ≤192 上比较 ComplexF32 与 ComplexF64，记最大均值差为 εfp。
- 计算 `d₀=|μδ=0−1|`。
- 计算 `εrescale=|μraw−μraw/μδ=0|`。

最终同时给出：

```text
raw estimate: μraw
statistical interval: t interval
numerical envelope: εnum = εχ + εfp + εrescale
conservative total half-width: εtotal = εstat,95% + εnum
```

`εtotal` 是统计区间与系统误差包络的保守相加，不宣称具有严格 95% coverage。
εrescale 也只是偏差敏感度，不是经过证明的误差上界。

#### 精度提升的分级验收

- **P1 必须完成**：首次给出明确统计区间和每个系统误差项。
- **P2 目标**：εχ 小于公开 χ=192→512 漂移 0.0014071975。
- **P3 stretch**：εtotal≤1×10⁻³。

P3 未达到不否定路线；只要 P1 完成且诚实说明限制，就比现有“中心值、无误差条”
更可审计。

### G3P：PEPO/Heisenberg-picture 2D 张量网络进阶测试

#### 固定问题

本 goal 只测试 baseline：49-qubit heavy-hex 子图、官方 QASM blob
`716305eb99ed9fafb356bf971269ff1d8d66b03e`、L=3、b=0.25、δ=0.15、
O=Z₅₂Z₅₉Z₇₂，并同时计算 δ=0。默认使用 ComplexF64。任何裁剪图或浅层电路只
用于 G1/G3P 的验证阶梯，不能替代完整 `49x648` 结果。

#### 表示与计算流程

1. 从 bond-dimension-1 的局域 Pauli PEPO 构造 O。
2. 按通过 G1 验证的反向门序施加共轭，得到近似 Õ；跳过反向 lightcone 之外的门。
3. 每次双比特门后用 simple-update/gauged SVD 截断到 `Dop`，保存 discarded
   weight；不静默改变 cutoff。
4. 构造闭合 overlap `2⁻ⁿTr(Õ Vδ† Õ Vδ)`，分别计算 δ=0 和 δ=0.15。
5. 用独立的 `χenv` 收缩闭合二维网络；在可精确收缩的小实例上同时保存 exact
   contraction。

PEPO 直接估计 trace，不使用 BP-TN 的随机初态 seed bank，也不报告虚构的
`N_init` 统计误差。它与 BP-TN 共享 QASM parser、物理节点映射、observable、
dtype 约定和 run metadata schema。

#### 测试阶梯

1. 在 G1 的 n≤20、L≤2 实例上关闭截断或把 `Dop` 提高到 exact 所需维度，
   验证 PEPO 与 statevector/exact contraction 的绝对误差≤1×10⁻¹⁰。
2. 在相同小实例上启用有限 `Dop`，确认 discarded weight、operator norm drift
   和 OLE 误差之间的关系可解释。
3. 在完整 `49x648` 上先运行 `Dop=4,8,16`；只有实测内存和 walltime 留有至少
   20% 安全余量时才追加 `Dop=32`。
4. 对每个 `Dop` 使用
   `χenv,low=max(32,Dop²)` 与 `χenv,high=2χenv,low`。若高值超过节点内存，
   该点记为 resource boundary，不用低 `χenv` 冒充收敛结果。
5. ComplexF32 只在 n≤20 和 `Dop≤8` 上作浮点敏感度对照；完整 baseline 的
   headline 候选保持 ComplexF64。

#### PEPO 误差包络

令 `Dhi` 是实际完成的最大 `Dop`，`Dprev` 是前一个值，并用最大 `Dop` 的两个
环境维度定义：

```text
εDop = |f(Dhi, χenv,high) − f(Dprev, χenv,high)|
εenv = |f(Dhi, χenv,high) − f(Dhi, χenv,low)|
εfp = 小系统 ComplexF32/F64 的最大差
d0,PEPO = |fδ=0(Dhi, χenv,high) − 1|
εPEPO = εDop + εenv + εfp + d0,PEPO
```

这是保守的数值收敛包络，不具有统计 coverage，也不假设 PEPO 随 `Dop` 变分或
单调。raw δ=0.15 始终作为主值；δ=0 ratio 只作为与 BP-TN 相同口径的诊断。

#### 通过条件与结果解释

- 小系统 exact oracle 通过，且 PEPO 的共轭方向和官方 QASM 完全一致；
- `|Im f|`、Hermiticity defect 和 operator norm drift 随精度旋钮总体下降，
  任何异常跳变都能追溯到具体门层；
- 至少完成 `Dop=8,16` 及各自两个 `χenv`，否则只交付 resource/convergence
  boundary；
- **PEPO-T1**：给出完整 baseline raw 值和分项 `εPEPO`；
- **PEPO-T2**：`εDop≤1×10⁻³` 且 `εenv≤1×10⁻³`；
- PEPO 与 BP-TN 包络重叠时记为 independent cross-check；不重叠时记为
  method discrepancy，进入 G4 排查，不能选择性丢弃其中一个结果。

PEPO-T2 是把该路线称为“baseline 精度提升候选”的最低门槛。若只达到 PEPO-T1，
它仍是有效的进阶测试，但不能作为更高精度 headline。

### G4：系统偏差与独立方法审计

1. 在 G1 小实例上比较 BP、boundary-MPS、loop-corrected BP 和 exact。
2. 逐步增加 L 和 patch 大小，找出 BP 偏差开始超过 1×10⁻³ 的位置。
3. 在完整 49×648 的低 χ 设置上比较 BP 与 boundary-MPS 可行的局部观测量。
4. 在相同小实例和完整 baseline 上比较 PEPO 与 BP，分别保留 BP 的 χ/N_init
   误差预算和 PEPO 的 Dop/χenv 误差包络，不把两者混成一个来源不明的误差条。
5. 运行 single-path Pauli propagation 的 θ→−θ 测试，展示其结果不变的已知
   失败模式；该测试通过反而证明它不能捕捉本问题所需的相位信息。
6. 分别画出：
   - fδ 对 χ；
   - fδ 对 Dop，并用不同曲线表示 χenv；
   - paired χ differences；
   - statistical CI 对 N_init；
   - S₀ 对 χ；
   - PEPO 的 δ=0 defect、Hermiticity defect 和 discarded weight；
   - BP 与 PEPO 的独立误差包络；
   - raw 与 rescaled 的差；
   - peak memory / time 对 χ、Dop 和 χenv。

只有当这些图共同支持一个稳定区间时，才能称 baseline “precision improved”。

### G5：`49x1296` active feasibility gate

#### 迁移原则

从 baseline 配置复制 active 配置时，只允许修改：

- QASM 文件及其固定 hash；
- L=3→6；
- 与实测成本相关的 Slurm walltime/memory。

observable、δ、b、随机 seed bank、dtype、BP 收敛规则、误差公式和输出 schema
全部保持不变。任何额外变化都必须在配置 diff 中显式出现。

#### Pilot

1. 使用与 baseline 相同 seed bank 的前 20 个初态。
2. 运行 χ=64、128、192。
3. 记录每个 χ 的最大 resident/device memory、单层时间、总时间和截断指标。
4. 分别拟合时间与内存随 χ 的经验模型；不能直接套用理论 χ³。
5. 外推 χ=256、384、512 和目标 N_init 的资源。

#### Go/no-go

只有同时满足下列条件才进入 G6：

- 预计 peak memory≤所选 partition/node 可用内存的 80%；
- 预计单 job walltime≤partition 上限的 70%；
- BP message 和 norm 没有随 L=6 明显失稳；
- χ=128→192 的 paired drift 没有发散；
- job array 能按初态拆分，单个失败可重跑而不损失全部结果。

未通过时输出 active cost report 和低 χ diagnostic result，停止生产扫描。这是有价值
的负面结论，不把资源不足伪装成数值收敛。

### G6：`49x1296` active 生产计算

1. 使用 χ=192→256→384→512，先完成共同的 N=20 paired set。
2. 只有最高两个 χ 的差稳定后，才扩大最高 χ 的 N_init。
3. N_init 使用与 G3 相同的自适应规则和 512 上限。
4. 同时计算 raw δ=0.15、raw δ=0 和 rescaled ratio。
5. 主表对照：
   - BP-TN χ=512 raw：0.88157984；
   - BP-TN χ=512 rescaled：0.94257142；
   - Heron R3 global-rescaled：0.649–0.662；
   - 我们的 raw、rescaled、εstat、εχ、εfp、εrescale。
6. 不把“更接近某一公开数字”当正确性证据。若 χ 收敛不稳定或 εrescale 主导
   εtotal，结果标记为 diagnostic，不提交为 high-precision classical benchmark。

G6 的成功不是必须“击败量子结果”，而是给 active candidate 一个比现有无误差
经典中心值更透明的经典估计，或明确证明当前 BP-TN 设置无法提供这种估计。

### G7：可复现交付与 tracker 决策

最终交付至少包含：

- 可从固定 QASM 和 Manifest 启动的 consolidated runner；
- 每个 run 的完整配置、Git SHA、seed、χ、dtype、资源和退出状态；
- 每个随机初态的增量结果，job 中断时最多损失一个初态；
- baseline 与 active 的 convergence/error-budget 图；
- 一份短报告，区分 reproduction、precision improvement 和 active result；
- 对 tracker submission 的 go/no-go 说明。

只有满足以下条件才建议向 tracker 提交：

- headline 与 QASM、代码 commit、seed bank 和 raw data 一一对应；
- 有误差条，且统计误差与系统误差未混成一个不明区间；
- 方法和计算资源达到 tracker 的公开提交要求；
- δ=0 重标度写明，未用它隐藏 raw 结果；
- 他人可以从干净环境重跑至少 baseline。

### G8：下一实例决策

完成 G6 后才比较两个方向：

1. **70×1872**：方法与 δ 保持一致，但 qubit 数和深度同时增加；适合在
   `49x1296` 已证明 χ/资源可控时继续。
2. **56×1488**：科学争议更强，但协议变化大且现有经典成本极高；应作为独立
   研究设计，不直接复用本计划的精度阈值。

G8 不阻塞本路线完成。若 `49x1296` 已揭示 BP-TN 的系统偏差不可控，应停止扩大
问题，而不是用更大的实例掩盖方法问题。

## 7. 计划中的文件边界

后续实现阶段预计在本目录增加：

```text
issue-119-ole/
├── PLAN.md                         # 本文，只描述已批准路线
├── Project.toml                    # solution-local Julia 依赖
├── Manifest.toml                   # 固定 TNQS/ITensors 版本
├── requirements-pepo.txt           # 固定 quimb/cotengra/numpy 版本
├── configs/
│   ├── baseline-49x648.toml        # L=3 协议与扫描参数
│   ├── baseline-pepo.toml          # Dop/χenv/cutoff 与资源门槛
│   └── active-49x1296.toml         # 只含经过审计的配置差异
├── scripts/
│   ├── fetch_inputs.jl             # 下载、hash、导出跨语言规范化 gate manifest
│   ├── validate_small.jl           # exact oracle 与 identity tests
│   ├── run_bp.jl                   # 单个 instance/χ/seed runner
│   ├── run_pepo.py                  # 单个 Dop/χenv 的 direct-trace runner
│   ├── run_array.sh                # cluster array 入口
│   ├── analyze.jl                  # BP paired differences 与误差预算
│   └── analyze_pepo.py             # Dop/χenv 收敛与 PEPO 误差包络
├── src/
│   ├── OLEProtocol.jl              # QASM、节点和 observable 定义
│   ├── BPTNRunner.jl               # BP-TN 演化与逐层 diagnostics
│   ├── ErrorBudget.jl              # BP 统计区间和系统误差包络
│   └── pepo_runner.py              # PEPO 构造、演化和闭合 overlap
├── tests/
│   ├── protocol_tests.jl
│   ├── exact_oracle_tests.jl
│   ├── error_budget_tests.jl
│   └── test_pepo_small.py           # PEPO 对 statevector/exact contraction
└── runs/                            # 运行产物；大 checkpoint 不提交 Git
```

每个文件只承担一个职责。`run_bp.jl` 不自行猜 observable 或 QASM 映射；
`run_pepo.py` 只能读取 G0 导出的规范化 gate manifest，不能独立重解释 QASM；
分析脚本不重新运行模拟；配置文件不包含隐藏默认值。

## 8. 计算资源策略

当前本地机器约 11 GiB RAM，只适合：

- G0 输入解析；
- G1 n≤20 exact oracle；
- G2 χ=64/128 的单初态 smoke test；
- G3P n≤20，以及完整图 `Dop=4` 的静态网络/路径估算；只有估算低于本地阈值时
  才执行完整图 probe；
- 结果分析和绘图。

χ=192/512、多初态 baseline 生产计算、完整图 `Dop≥8` 的 PEPO 扫描和全部 active
计算在启动前都必须：

1. 读取并确认 active Slurm profile；
2. BP 用一个初态做 probe；PEPO 用最低 `(Dop,χenv)` 网格点做 probe；
3. 选择满足实测需求的 partition；
4. BP job array 按初态并行；PEPO 按 `(Dop,χenv,δ)` 或 exact slices 并行；
5. 监控 `PD→R`、首个初态/网格点/slice 输出和增量结果；
6. stdout 每个层、初态、网格点或 slice 刷新一次，禁止长时间无进度输出。

公开的 118 s、149 s 和 1680 s 只能作为历史锚点，因为其 N_init、软件版本和具体
硬件并未完整披露，不能直接当我们的 walltime 保证。

PEPO 没有随机初态这一并行轴，主要并行轴是 `(Dop,χenv,δ)` 和闭合网络的 contraction
slices。启动完整 `49x648` 前，必须分别估算 PEPO 演化和最终 overlap contraction
的最大中间张量；若 `χenv,high` 超过节点内存，按 G3P 记录 resource boundary，
不能只完成低环境维度后宣称收敛。

## 9. 主要风险与停止条件

| 风险 | 识别信号 | 应对与停止条件 |
|---|---|---|
| QASM/公式约定错误 | 小系统两个实现不一致 | 停在 G1，定位门序和 U/U†；禁止跑 49 qubits |
| 物理 qubit 标签误映射 | 活动 qubit 数不是 49 或 O 落在错误节点 | G0 立即失败 |
| BP 未收敛 | message residual、norm 或结果随迭代振荡 | 增加迭代/换初始消息；仍失败则不报高精度值 |
| χ 偏差未收敛 | paired drift 不下降或 raw/rescaled 差持续扩大 | 结果只标 diagnostic；资源允许才试更高 χ |
| 统计成本过高 | pilot 推得 N_required>512 | 报告已达到 CI，不虚构窄误差 |
| 浮点误差 | ComplexF32/F64 差接近目标精度 | 生产改用 ComplexF64 或扩大 εfp |
| PEPO 算符纠缠增长过快 | discarded weight、norm/Hermiticity defect 随层数快速增大 | 提高 Dop 后仍不改善则停在 PEPO-T1；不迁移到 active |
| PEPO 环境未收敛 | χenv 翻倍后结果变化>1×10⁻³ 或内存超限 | 报告 εenv/resource boundary，不把该值作为高精度结果 |
| BP 与 PEPO 不一致 | 两个独立误差包络不重叠 | 回到小系统和逐层诊断；保留 discrepancy，不按偏好选值 |
| Pauli MC 给出“稳定”数字 | 符号翻转结果不变 | 只作负面对照，不升级为主方法 |
| active 资源超限 | χ=512 外推越过 80% memory 或 70% walltime | 交付 cost report 后停止 G6 |
| 上游代码漂移 | Manifest/tree hash 变化 | 固定旧环境；升级必须重新过 G1/G2 |

## 10. 路线完成定义

本 OLE 主路线在以下条件全部满足时完成：

1. `49x648` 的官方 QASM 和节点映射可追溯；
2. 小系统精确 oracle 通过；
3. χ=192/512 的 baseline 中心值得到复现；
4. baseline 至少达到 P1：有统计区间和分项数值误差预算；
5. G3P 至少完成 PEPO-T1，或给出可复现的 PEPO resource/convergence boundary；
6. `49x1296` 完成可行性 gate；
7. 若 gate 通过，产出带误差预算的 active 结果；若不通过，产出可复现实测 cost
   report 和停止依据；
8. 所有 headline 均能追溯到 raw per-seed/per-grid data、配置和 commit；
9. Variational 备选计划未被本路线修改。

这一定义允许“可信的负面结果”：证明 active 计算在当前资源或当前 BP-TN 精度下
不可行，也比提交一个没有误差、无法解释重标度的数字更符合 issue #119 的目标。

## 11. 公开依据

- [Quantum Advantage Tracker：Observable estimations](https://quantum-advantage-tracker.github.io/trackers/observable-estimations)
- [49×648 官方实例 #10](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/10)
- [49×1296 官方实例 #11](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/11)
- [49×648 BP-TN χ=192 #15](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/15)
- [49×648 BP-TN χ=512 #18](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/18)
- [49×1296 BP-TN raw #19](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/19)
- [49×1296 BP-TN rescaled #20](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/20)
- [Single-path Pauli MC 方法及限制 #63](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/63)
- [56×1488 BP-TN 成本 #203](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/203)
- [OLE 模型、测量协议与经典方法说明](https://algorithmiq.fi/files/model-information-flow-complex-material-document.pdf)
- [TensorNetworkQuantumSimulator.jl](https://github.com/JoeyT1994/TensorNetworkQuantumSimulator.jl)
- [Gauging tensor networks with belief propagation](https://scipost.org/10.21468/SciPostPhys.15.6.222)
- [Simulation of IBM's kicked Ising experiment with Projected Entangled Pair Operator](https://arxiv.org/abs/2308.03082)
- [quimb `CircuitPEPOSimpleUpdate` 文档](https://quimb.readthedocs.io/en/latest/autoapi/quimb/tensor/circuit/pepo/index.html)
