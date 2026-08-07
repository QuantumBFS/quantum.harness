# Issue #119：Operator Loschmidt Echo G2 Baseline Benchmark 详细报告

- 整理日期：2026-07-28
- Harness challenge：[#119 — Advantage or artifact? Hunt on the Quantum Advantage Tracker](https://github.com/QuantumBFS/quantum.harness/issues/119)
- Tracker 实例：[Operator Loschmidt Echo 49×648](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/10)
- 当前阶段：G2 baseline reproduction
- 结论等级：**通过 baseline reproduction；尚未达到高精度/独立交叉验证等级**

## 1. 一句话结论

我们用 BP-TN 在同一组 20 个随机初态上完成了 χ=192 和 χ=512 的
49-qubit OLE 计算。两个均值与 tracker 公开结果的差分别为 0.85 SE 和
1.68 SE，均落在当前复现的 95% 统计区间内，也满足预先写入代码的 G2
接受规则。因此，**当前结果足以证明 runner 已接入正确问题、能稳定复现
baseline 的数值尺度并满足 G2 benchmark 条件**。

但它还不能被描述为“OLE 真值已经收敛到 10⁻³ 或更高精度”。当前主要限制是
20 个随机初态带来的约 2.0×10⁻³ 标准误差，此外还缺少独立实现的交叉验证、
更多中间 χ 点和完整的 BP 系统误差包络。

## 2. 问题背景

### 2.1 Quantum Advantage Tracker 在比较什么

Quantum Advantage Tracker 把具体的量子优势声明变成可下载、可复核的问题实例。
对于 observable estimation 路线，输入是一条量子线路和一个 observable，参与者
需要给出期望值及可信的误差说明。由于大规模实例通常没有可直接查询的精确答案，
可信度来自：

1. 输入和门约定可审计；
2. 数值参数收敛；
3. 统计误差明确；
4. 不同算法或实现之间相互一致。

Issue #119 要求先在已有经典结果的 baseline 上学会完整工作流，再把同一套方法
迁移到仍有争议的 active candidate。我们选择的第一步是
`operator_loschmidt_echo_49x648`；其更深但问题设置一致的 active 目标是
`operator_loschmidt_echo_49x1296`。

### 2.2 什么是 Operator Loschmidt Echo

普通 Loschmidt echo 可以理解为“向前演化—施加小扰动—尝试倒放”，然后检查系统
能否回到原状。Operator Loschmidt echo（OLE）把这个思想用于算符传播：

`fδ(O) = 2⁻ⁿ Tr[U O U† Vδ† U O U† Vδ]`。

其中：

- `n` 是 active qubit 数；
- `U` 是 Ising-like Floquet 量子线路；
- `O` 是被跟踪的局域 Pauli 算符；
- `Vδ = exp(−iδG)` 是强度为 δ 的局域扰动；
- `2⁻ⁿTr` 是无限温度归一化 trace。

当 δ 很小时，OLE 与演化后的算符和扰动生成元之间的对易子范数相关。若 `U`
没有把 `O` 传播到扰动区域，`O` 与 `G` 近似对易，OLE 接近 1；若算符已经传播并
与扰动发生强烈非对易，回声会下降。因此 OLE 是 operator spreading、信息传播和
量子多体混沌的诊断量。

### 2.3 为什么 49 qubits 仍然是困难问题

49-qubit 完整波函数有 `2⁴⁹` 个复振幅。用 ComplexF64（每个复数 16 bytes）
存储仅一个 statevector 就需要约 8 PiB，普通单节点无法承载。

这个实例的相互作用图是带环的 heavy-hex 子图。线路包含 648 个 CZ gates，会在
图上产生纠缠。BP-TN 通过局域张量和有限 bond dimension 压缩波函数，绕过完整
statevector 的指数内存，但代价是引入 bond truncation 和近似环境收缩误差。

## 3. 本次实际求解的问题

### 3.1 冻结的输入

本次 runner 直接使用 2026-07-27 从 tracker issue #10 下载的当前附件，并按内容
固定：

| 输入项 | 实际值 | 含义 |
|---|---:|---|
| 文件大小 | 150,686 bytes | 当前 tracker 附件的实际字节数 |
| SHA-256 | `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455` | 输入内容身份；任何字节变化都会停止运行 |
| OpenQASM register | `q[156]` | QASM 可使用的物理编号空间，不代表模拟 156 qubits |
| active qubits | 49 | 实际参加线路的物理 qubit 数 |
| barrier-defined layers | 73 | runner 的逐层更新与 checkpoint 边界 |
| CZ gates | 648 | 产生图上纠缠的双比特门数 |
| all non-barrier gates | 4,756 | 单比特门和双比特门总数 |

QASM 使用 IBM 物理 qubit 标签，例如 52、59、72。程序先收集实际出现的 49 个
标签，再建立 `physical label ↔ internal tensor index` 显式映射。因此
`q[156]` 只是地址空间，不会被错误地构造成 156-qubit state。

早期计划记录过 162,721 bytes 和另一个 Git blob hash，它们与当前附件不一致。
所以本报告只对上述 SHA-256 对应的线路负责。这个内容寻址检查防止了不同版本
QASM 的结果被静默混合。

### 3.2 目标 observable

目标量为：

`O = Z₅₂ Z₅₉ Z₇₂`。

它是作用在三个指定物理 qubit 上的 Pauli-Z string。对于计算基初态 `|z⟩`，
其本征值或初态 parity 为：

`σz = ⟨z|O|z⟩ ∈ {−1,+1}`。

这三个位置定义了我们追踪的初始算符支撑。OLE 测量的是线路演化后，这个三点算符
与 perturbation 的相容程度，而不是某个单独 qubit 的占据概率。

## 4. 求解算法：BP-TN 加随机 trace estimator

### 4.1 为什么要随机采样 trace

OLE 中的归一化 trace 等价于对全部 `2⁴⁹` 个计算基态求平均。完整枚举不可能，
因此从计算基均匀抽取 `N_init` 个 bitstrings。对于第 i 个初态：

1. 计算初态 parity `σᵢ=⟨zᵢ|O|zᵢ⟩`；
2. 用 QASM 线路演化 `|zᵢ⟩`；
3. 计算末态的 `O` 期望值；
4. 定义单样本 `xᵢ = σᵢ × Re⟨O⟩ᵢ`；
5. 以 `μ = N_init⁻¹ Σᵢxᵢ` 估计 OLE。

样本标准误差为 `SE=s/√N_init`。它描述随机初态有限采样造成的不确定度，与
tensor-network 截断误差是两种不同误差。

### 4.2 BP-TN 如何表示和演化状态

本实现使用
[TensorNetworkQuantumSimulator.jl](https://github.com/JoeyT1994/TensorNetworkQuantumSimulator.jl)
0.4.4。每个 active qubit 对应一个局域张量，heavy-hex 上的连接对应虚拟 bond。

每个 seed 的计算流程是：

1. 从 SHA-256 派生的确定性规则生成 49-bit 计算基初态；
2. 从 QASM 提取相互作用图并构造 product-state tensor network；
3. 按 73 个 QASM layers 依次施加单比特门和 CZ gates；
4. 双比特门使 bond 增长时进行 simple-update SVD，并按 `χ` 与 `cutoff` 截断；
5. 每层更新 belief-propagation（BP）messages；
6. 用 BP 近似整个带环网络对局域张量的环境；
7. 计算最终 `Z₅₂Z₅₉Z₇₂` 期望值并乘初态 parity；
8. 保存逐层 bond、截断指标、BP residual、wall time 和 peak RSS。

BP message 可以理解为“网络一侧通过一条 bond 对另一侧产生的有效环境”。在树图
上 BP 是精确的；在有环 heavy-hex 图上，它是近似 fixed point。较小 BP residual
说明 message 迭代已稳定，但**不等于 BP 近似本身相对精确解的误差已经严格有界**。

### 4.3 χ 如何控制精度

双比特门会增加虚拟 bond dimension。SVD 把局域波函数按该 bond 分解为一组
singular components，χ 规定最多保留多少个主要分量：

- χ 较小：速度快、内存低，但丢失更多纠缠信息；
- χ 较大：保留更多纠缠信息，通常截断误差更小；
- χ→足够大时，observable 应形成稳定平台。

χ 是最大允许值，不代表每一条 bond 始终等于 χ。本次 χ=512 的实测内存远低于
“所有 bonds 同时饱和到 512”的上界，正是因为实际 bond 尺寸随位置和 layer 变化。

## 5. 计算参数及其物理/数值意义

### 5.1 物理与线路参数

| 参数 | 本次值 | 物理意义 | 改变它会发生什么 |
|---|---:|---|---|
| `n` | 49 | 实际参与动力学的 qubit 数，即系统规模 | 增大 n 会扩大 Hilbert space 和传播空间 |
| lattice | 49-site heavy-hex subgraph | 定义 qubits 的连接与局域相互作用几何 | 改变图会改变 operator spreading 路径和 TN 难度 |
| `L` | 3 | Floquet block 的重复次数；这里对应 `2L` 个 Trotter steps | 增大 L 会加深演化、通常增加 operator spreading 和纠缠 |
| `b` | 0.25 | `U_b` 中一组 sites 的横向 kick/rotation angle；另一组 sites 使用 `3π/8` | 控制局域旋转与散射强度，影响动力学和可积性破缺 |
| `δ` | 0.15 | `Vδ=exp(−iδG)` 的无量纲扰动强度 | δ=0 时 OLE 应为 1；δ 增大通常使 echo 更明显下降 |
| perturbation gates | 24 个 `rz(0.3)` | QASM 中扰动的具体编码；Qiskit `Rz(θ)=exp(−iθZ/2)`，所以角度 `0.3=2δ` | 规定扰动的空间支撑与实际门约定 |
| observable | `Z₅₂Z₅₉Z₇₂` | 被追踪的三点 Pauli-Z operator | 改变位置或 Pauli 类型会测到不同的传播通道 |
| CZ gates | 648 | 产生相互作用和纠缠的双比特门数 | 更多 CZ 通常提高 tensor-network 表示难度 |
| layers | 73 | QASM barrier 划分的执行层数 | 是实现和 checkpoint 单位，不是独立物理可调参数 |

这里的 `L` 不是格点边长，`b` 也不是以能量单位表示的静态磁场；二者都是
Floquet/Trotter 线路定义中的无量纲参数。真正执行的门序和角度以冻结的 QASM
为准。

### 5.2 随机 trace 参数

| 参数 | 本次值 | 含义 | 对误差的影响 |
|---|---:|---|---|
| `N_init` | 20 | 均匀抽取的计算基初态数量 | SE 近似按 `1/√N_init` 下降 |
| seed IDs | 1–20 | 固定的 20 个样本编号 | 使不同 χ 使用完全相同的初态，可做低噪声 paired comparison |
| seed namespace | `issue119-ole-v1` | seed 到 bitstring 的版本化映射标签 | 防止 Julia RNG 版本变化导致样本集合漂移 |

本实现不是调用语言默认 RNG，而是对
`namespace:seed:physical_label` 做 SHA-256 映射来生成每一位。这保证重新运行时
seed 1–20 对应完全相同的 20 个计算基态。

### 5.3 Tensor-network 数值参数

| 参数 | 本次值 | 数值意义 | 判断方式 |
|---|---:|---|---|
| bond dimension `χ` | 192、512 | 每条虚拟 bond 最多保留的分量数，是主要 truncation knob | 比较同一 seeds 在不同 χ 下的 paired differences |
| SVD `cutoff` | `1×10⁻¹²` | 允许 SVD 丢弃极小 singular spectrum weight 的次级阈值 | 若 χ 未饱和，cutoff 可能主导；若 χ 饱和，maxdim 主导 |
| dtype | `ComplexF64` | 双精度复数，约 15–16 位十进制有效数字 | 控制浮点舍入误差和内存 |
| `normalize_tensors` | `true` | 每步对局域张量归一化，改善数值条件 | 会丢失独立追踪全局 norm 所需的 scale |
| `bp_maxiter` | 25 | 每次 BP update 最多进行 25 轮 message 迭代 | 太小可能停在未稳定 message 上 |
| `bp_tolerance` | `1×10⁻⁸` | BP fixed-point 的停止阈值 | residual 低于该值视为 message 迭代收敛 |
| rescaling | 不使用 | headline 是 raw OLE，没有除以 δ=0 结果 | 避免用归一化修正掩盖未知系统偏差 |

`normalize_tensors=true` 使逐层 global norm defect 无法可靠重建，所以结果文件明确
把该诊断标为 unavailable，而不是报告一个看似精确但含义错误的数。δ=0 identity
control 被单独用于验证协议。

### 5.4 计算资源参数

| 参数 | 本次值 | 含义 |
|---|---:|---|
| Julia threads | 1/cell | Julia 顶层任务不并行，减少不可控并发 |
| BLAS threads | 16/cell | SVD 和线性代数使用 16 个 CPU threads |
| Slurm partition | `batch` | 普通 CPU 分区 |
| requested memory | 16 GiB/cell | 调度申请；实测峰值不超过 3.34 GiB |
| SCNet / bigmem | 未使用 | 本次不依赖特殊网络或大内存分区 |

这些参数改变运行时间和资源利用率，但在算法、精度参数完全相同的前提下不应改变
物理结果。

## 6. 计算结果

### 6.1 20-seed 统计结果

接受规则在计算前已固定为：

`|μ − reference| ≤ max(0.002, 3SE)`。

| χ | N | mean `μ` | sample SD | SE | 95% CI | public reference | difference | tolerance | accepted |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 192 | 20 | 0.8185618335 | 0.0088759361 | 0.0019847196 | [0.8144077675, 0.8227158994] | 0.8202512915 | 0.0016894580 | 0.0059541589 | 是 |
| 512 | 20 | 0.8183229132 | 0.0088809258 | 0.0019858354 | [0.8141665120, 0.8224793144] | 0.8216584890 | 0.0033355758 | 0.0059575061 | 是 |

两个公开值都落在本次相应的 95% CI 内：

- χ=192 的偏差为 `0.85 SE`；
- χ=512 的偏差为 `1.68 SE`。

因此没有统计证据表明本次均值与公开中心值不相容。

### 6.2 同 seeds 的 χ 配对比较

不同 χ 使用完全相同的 20 个初态，所以可以逐 seed 相减，消除大部分由初态选择
造成的波动。定义：

`dᵢ = xᵢ(χ=512) − xᵢ(χ=192)`。

结果为：

| paired quantity | value |
|---|---:|
| mean | −0.0002389203 |
| SE | 0.0000065177 |
| 95% CI | [−0.0002525621, −0.0002252785] |
| maximum absolute difference | 0.0002807823 |
| negative differences | 20/20 |

这说明对本次固定 seed bank，χ=192→512 带来稳定但很小的负向修正，约
`−2.39×10⁻⁴`。它远小于 20-seed 均值的统计 SE `≈1.99×10⁻³`，所以当前总误差
主要由随机 trace sampling 控制，而不是 χ=192 与 χ=512 之间的差。

注意：paired SE 很小只说明“这 20 个相同初态上的 χ 差值”测得很精确，并不意味
OLE 总体均值也具有同样小的误差。

### 6.3 δ=0 identity control

在 δ=0、seed 1、χ=64 时：

- OLE = 1.0000000；
- 最大实际 bond dimension = 32；
- 最大 truncation indicator = `8.92×10⁻²⁹`。

δ=0 时 QASM 中恰好 24 个 `rz(0.3)` perturbation gates 被替换为 `rz(0.0)`；
替换数不等于 24 时程序会拒绝运行。这个结果验证了扰动定位、逆线路结构、parity
和 observable 测量的一致性。

它是强协议 sanity check，但由于只运行了 seed 1、χ=64，不能替代完整的高 χ
系统误差扫描。

### 6.4 BP 与截断诊断

| χ | mean wall | max wall | mean peak RSS | max peak RSS | max truncation indicator | max BP residual | non-converged layers |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 192 | 120.2 s | 129.3 s | 2.27 GiB | 2.37 GiB | 2.50×10⁻⁴ | 4.40×10⁻¹¹ | 0 |
| 512 | 134.2 s | 162.0 s | 3.07 GiB | 3.34 GiB | 9.99×10⁻¹³ | 2.84×10⁻¹⁶ | 0 |

χ=512 的最大局域 truncation indicator 比 χ=192 小约八个数量级，且所有 BP
fixed points 都满足 `1×10⁻⁸` tolerance。这表明：

1. 当前实现的 SVD 截断在 χ=512 上已非常弱；
2. BP message iteration 数值稳定；
3. 40 个生产结果没有 NaN、OOM 或未收敛 layer。

但是局域 discarded weight 和 BP residual 都不是对最终 OLE 系统误差的严格数学
上界，不能单独把它们解释成最终 error bar。

### 6.5 计算成本

40 个 χ=192/512 cells 共消耗：

- aggregate task wall time：1.41 小时；
- allocated CPU time：22.61 CPU-hours；
- 完整结果：40/40。

Slurm production array 为 job `410814`。χ=192 和 χ=512 的单点资源探针分别是
jobs `410808` 和 `410810`。

## 7. 与之前公开结果的比较

### 7.1 公开 baseline

| 来源 | 方法 | 公开结果 | 公开 error bound | 公开 runtime |
|---|---|---:|---|---:|
| [Tracker #15](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/15) | BP-TN, χ=192, raw | 0.8202512915 | N/A | 118 s |
| [Tracker #18](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/18) | BP-TN, χ=512, raw | 0.8216584890 | 未提供 | 149 s |

公开条目没有给出 `N_init`、seed bank、SE、χ 扫描数据以及完整的 BP/SVD 参数。
因此可比较的是中心值和计算量级，不能做 bit-for-bit replication，也不能把公开
值当作无误差真值。

### 7.2 中心值比较

| χ | 本次 mean | 公开值 | 本次−公开 | 相对本次 SE |
|---:|---:|---:|---:|---:|
| 192 | 0.8185618335 | 0.8202512915 | −0.0016894580 | −0.85 SE |
| 512 | 0.8183229132 | 0.8216584890 | −0.0033355758 | −1.68 SE |

本次两个均值都低于公开值，但偏差均小于 2 SE，且公开值都在本次 95% CI 内。
在 N=20 的采样噪声下，这属于统计上相容，而不是显著冲突。

### 7.3 χ 趋势为何与公开中心值方向不同

公开中心值给出：

`0.8216584890 − 0.8202512915 = +0.0014071975`。

本次同 seeds paired comparison 给出：

`0.8183229132 − 0.8185618335 = −0.0002389203`。

两者方向相反，不能把公开两点直接解释为 χ 收敛曲线。最可能的原因是公开两个
条目没有说明是否使用同一 seed bank，初态采样波动足以覆盖 `10⁻³` 量级的 χ
变化；公开设置也可能存在未记录差异。

因此本次能作出的稳健判断是：

- 对我们固定的 20 seeds，χ=192→512 修正很小且为负；
- 公开两个中心值与本次总体统计区间相容；
- 目前不能从四个中心值推断唯一的 χ→∞ 外推方向。

### 7.4 runtime 比较

本次 χ=192 平均 120.2 s，与公开 118 s 相差约 +1.9%；χ=512 平均 134.2 s，
比公开 149 s 约快 10.0%。两者属于相同运行量级。

由于 CPU 型号、线程设置、首次编译和测量口径不完全相同，这只能说明资源估算
合理，不能作为严格性能排名。

### 7.5 逐 seed、公开经典结果与量子硬件结果

![49×648 OLE 的逐 seed 与公开结果比较](../../../../../results/issue119-ole-g2-paired-rest/ole-seed-public-quantum-comparison.png)

左图给出 20 个 seed 的 χ=192/512 原始结果。相同 seed 的两个 marker 成对出现；
它们之间的距离远小于不同 seed 之间约 `10⁻²` 的波动。三条水平线分别是 tracker
公开的 BP-TN χ=192 raw、BP-TN χ=512 raw，以及 IBM Heron R3 的
global-rescaled 量子硬件值。

右图把本次两个均值及其 95% Student-t CI 与三个公开点并列。公开条目没有提供
error bound，因此只画 marker，不添加人为误差条。图中可直接看出：

1. 两个公开 BP-TN 点都落在本次相应的 95% CI 内；
2. IBM Heron R3 的 0.824 也位于 20-seed 样本分布范围内；
3. 当前 seed-to-seed 波动明显大于 χ=192→512 的修正；
4. IBM 点经过 δ=0 global rescaling，而当前和公开 BP-TN 点是 raw 数据，所以
   IBM 点只能作为背景比较，不能用于一对一的精度判定。

## 8. 当前结果是否 solid

### 8.1 证据矩阵

| 证据项 | 当前状态 | 评价 |
|---|---|---|
| 输入身份 | QASM byte count 与 SHA-256 固定 | 强 |
| 物理标签映射 | 49 active labels 显式映射，非 156-qubit 误读 | 强 |
| 门集合与角度 | strict parser；未知 gate 或 hash 变化即停止 | 强 |
| 可重复随机样本 | versioned seed namespace，χ 间共享 seeds | 强 |
| 统计误差 | 报告 SD、SE、95% CI；但仅 N=20 | 中等 |
| χ 诊断 | χ=192/512 paired；局域 truncation 明显改善 | 中等 |
| BP 数值收敛 | 40/40 完成，未收敛 layers=0 | 强 |
| δ=0 控制 | OLE=1，但仅 seed 1、χ=64 | 中等 |
| 与公开值比较 | 两个公开值均在本次 95% CI 内 | 强于“只比较小数”，但受公开元数据缺失限制 |
| 独立算法/实现 | 尚无完整实例的独立交叉检查 | 缺失 |
| 严格系统误差上界 | BP 与局域截断指标不是 rigorous global bound | 缺失 |
| 高精度统计区间 | 95% half-width 约 0.00415 | 尚不足 |

### 8.2 分层判定

**判定 A：能否满足当前 G2 baseline benchmark？——能。**

理由：

1. 输入、实现和 seed bank 均可重复；
2. χ=192/512 各 20 seeds 全部完成；
3. 两个均值都通过预先声明的
   `|μ−reference|≤max(0.002,3SE)`；
4. 公开中心值均位于对应 95% CI；
5. BP 全部收敛，χ=512 局域截断指标显著降低；
6. δ=0 控制返回精确的 1。

这足以满足 issue #119 的“先在 49×648 baseline 上重复一个已有经典结果”的
Rung 0/G2 目标。

**判定 B：能否声称获得了比公开结果更准确的 baseline 数值？——不能。**

原因：

1. `N_init=20` 给出的 SE 约为 `2×10⁻³`，统计误差仍主导；
2. 95% CI 半宽约 `4.15×10⁻³`，远宽于 χ 修正 `2.39×10⁻⁴`；
3. 尚未完成 χ=256/384 的中间点和 χ→∞ 误差包络；
4. 没有独立 PEPO、exact contraction 或另一实现的完整实例交叉检查；
5. BP 在有环图上的近似误差没有严格全局上界；
6. 公开条目缺少 seed、error bound 和完整设置，无法逐项复刻。

**综合结论：当前结果对“baseline reproduction”是 solid 的；对“高精度
baseline improvement”还不是 solid 的。**

## 9. G2 接受规则是否过于宽松

G2 tolerance 取 `max(0.002,3SE)`。在 N=20 时，两个 χ 的 `3SE≈0.00596`，
所以实际门槛约为 0.006。该门槛适合判断 runner 是否接入了正确的线路、observable
和数值方法；它不是最终科学误差条，也不是 tracker 的统一官方 acceptance rule。

当前 χ=512 与公开值相差 0.00334，虽然通过 G2，但大于固定 absolute floor
0.002。它是依靠“偏差小于 3SE”通过的。这正说明：

- G2 的通过结论成立；
- 继续增加 χ 并不能有效缩窄当前统计区间；
- 下一步最先应该增加 `N_init`，而不是只追求更大 χ。

按当前 χ=512 样本 SD 粗略估计：

- 若目标是 `SE≤5×10⁻⁴`，需要约 316 个 seeds；
- 若目标是正态近似下 95% CI half-width `≤5×10⁻⁴`，需要约 1,212 个 seeds。

实际应按追加样本后的方差重新估计，并用 Student-t interval 或 bootstrap 报告，
而不是把上述粗估当作固定任务量。

## 10. 达到高精度 baseline 的建议

### 10.1 第一优先级：增加同一 seed bank 的样本数

沿用 `issue119-ole-v1`，只追加 seed 21、22、……，不替换现有样本。建议设置
20→40→80→160→320 的 checkpoint，每次更新 mean、SE 和 95% CI。这样可以直接
检验 `1/√N_init` 收敛，并避免选择性保留“更接近公开值”的 seeds。

### 10.2 第二优先级：补齐 χ 误差包络

至少在共享 seeds 上加入 χ=256、384，比较：

- `μ₂₅₆`、`μ₃₈₄`、`μ₅₁₂`；
- 每个 seed 的 paired differences；
- 最大局域 truncation indicator；
- 是否形成单调或可解释的平台。

χ 扫描的目标不是把结果推向某个公开值，而是量化有限 bond dimension 的系统
误差。

### 10.3 第三优先级：独立方法交叉检查

按既定计划测试 PEPO/Heisenberg-picture 2D tensor network。它直接演化 operator，
与当前 BP-TN Schrödinger-picture 随机初态方法具有不同系统误差。PEPO 需要同时
扫描：

- operator bond dimension `Dop`；
- environment contraction dimension `χenv`。

在完整 49×648 前，先用小系统 exact statevector/contraction 验证门序、
`UOU†`/`U†OU` 约定和 δ=0 identity。只有 BP-TN 与独立方法的收敛区间重叠，才适合
声称高精度 baseline 已建立。

### 10.4 第四优先级：再进入 active instance

完成 baseline 统计误差和算法系统误差拆分后，再把同一协议迁移到 49×1296。
否则更深线路上的 raw/rescaled 差异无法判断是物理 operator spreading，还是
truncation/BP artifact。

## 11. 可复现性与文件位置

### 11.1 核心文件

- `configs/baseline-49x648.toml`：完整问题、软件和数值配置；
- `INPUT_AUDIT.md`：QASM 内容身份与输入差异审计；
- `src/OLEProtocol.jl`：strict QASM parser、标签映射和固定 seed bank；
- `src/BPTNRunner.jl`：BP-TN layer evolution 与逐层诊断；
- `src/ErrorBudget.jl`：统计摘要和 G2 acceptance；
- `scripts/run_bp.jl`：单 seed 可审计 runner；
- `scripts/analyze.jl`：20-seed 汇总；
- `G2_RESULTS.md`：最终 baseline 结果摘要；
- `RESOURCE_ESTIMATE.md`：资源探针与 Slurm 生产成本；
- `runs/baseline-49x648/delta-0p15/chi-192/summary.toml`：χ=192 summary；
- `runs/baseline-49x648/delta-0p15/chi-512/summary.toml`：χ=512 summary；
- `../../../../../results/issue119-ole-g2-paired-rest/g2-paired-20.csv`：
  逐 seed 配对数据；
- `../../../../../results/issue119-ole-g2-paired-rest/g2-paired-20.png`：
  配对结果图。
- `../../../../../results/issue119-ole-g2-paired-rest/ole-seed-public-quantum-comparison.png`：
  逐 seed、公开 BP-TN 与 IBM Heron R3 比较图；
- `../../../../../results/issue119-ole-g2-paired-rest/ole-seed-public-quantum-comparison.pdf`：
  同一比较图的矢量版本；
- `../../../../../results/issue119-ole-g2-paired-rest/ole-seed-public-quantum-comparison.json`：
  图中数据、公开来源和 raw/rescaled provenance sidecar。

### 11.2 软件版本

- Julia：≥1.10；
- TensorNetworkQuantumSimulator.jl：0.4.4；
- TNQS commit：`b5d4089849de1cc23806aa8325e8db56a55f2e0b`；
- dtype：ComplexF64；
- solution-local `Project.toml` 与 `Manifest.toml` 固定依赖环境。

### 11.3 已完成测试

- Julia G2 tests：60/60；
- Python array-entry tests：5/5；
- repository tests：223/223，coverage 95%；
- production scan：success 38、failed 0、missing 0、pending 0；
- χ=192/512 summaries：20 seeds each，accepted=true。

这些测试覆盖输入解析、稳定 seed、δ=0 gate replacement、真实 TNQS inverse
circuit、run record 和统计逻辑。它们不应被误写为“第二种物理算法已经验证完整
49×648 结果”；独立方法交叉检查仍属于后续工作。

## 12. 最终判定

> **Baseline benchmark：PASS。**
>
> 当前实现已经以可审计输入、固定 20-seed bank、两个 χ、统计区间、逐层 BP/SVD
> 诊断和实测资源复现 49×648 BP-TN baseline。两个公开参考值均位于对应 95% CI，
> 且通过预先声明的 G2 acceptance gate。
>
> **高精度/改进结果：NOT YET。**
>
> N=20 的统计误差仍大于观察到的 χ 修正；完整 χ 包络和独立方法交叉验证尚未
> 完成。因此正确表述是“G2 baseline reproduction solid”，而不是“已经得到
> OLE 的最终高精度经典答案”。

## 参考资料

1. [Quantum Harness issue #119](https://github.com/QuantumBFS/quantum.harness/issues/119)
2. [Tracker OLE 49×648 instance #10](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/10)
3. [Tracker BP-TN χ=192 result #15](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/15)
4. [Tracker BP-TN χ=512 result #18](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/18)
5. [TensorNetworkQuantumSimulator.jl](https://github.com/JoeyT1994/TensorNetworkQuantumSimulator.jl)
6. [Gauging tensor networks with belief propagation](https://scipost.org/10.21468/SciPostPhys.15.6.222)
7. [OLE model description and theory](https://algorithmiq.fi/wp-content/uploads/2025/11/model-information-flow-complex-material-document.pdf)
