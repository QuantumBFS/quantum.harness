# 有限 PEPS + Simple Update + Boundary-MPS + METTS 求解二维横场 Ising 模型有限温性质

本目录实现有限开放方格上的二维横场 Ising 模型

```math
H=-J\sum_{\langle i,j\rangle}Z_iZ_j-h\sum_iX_i
```

的有限温 METTS（minimally entangled typical thermal states）计算。程序组合了四个部分：

1. 用有限开放边界 PEPS 表示每一个典型热纯态；
2. 用二阶 Suzuki-Trotter 和 simple update 近似作用 `exp(-beta H/2)`；
3. 用双层 boundary-MPS 收缩计算范数、观测量和条件投影概率；
4. 用 METTS Markov 链对有限温 Gibbs 系综进行随机采样。

实现参考相邻目录 [`FinitePEPS_Z2_Ising`](../FinitePEPS_Z2_Ising/) 的有限 PEPS、simple update 和 boundary-MPS 结构，但不能直接使用其中的严格 `Z_2` 对称张量。本项目在奇数次 collapse 使用 `Z` 基、偶数次 collapse 使用 `X` 基；尤其是 `Z` 基塌缩得到的乘积态一般不保持全局自旋翻转对称性。新模块因此使用无对称的稠密有限 PEPS。

## 1. 目录结构

| 文件 | 主要功能 |
| --- | --- |
| [`FinitePEPSMETTS.jl`](FinitePEPSMETTS.jl) | 模块入口、默认参数和公共 API |
| [`model.jl`](model.jl) | 局域算符、有限 OBC 键 Hamiltonian、Trotter 门和小系统严格对角化 |
| [`state.jl`](state.jl) | 稠密 Γ-Λ PEPS、普通有限 PEPS、乘积态初始化和结构检查 |
| [`simple_update.jl`](simple_update.jl) | 水平/竖直键更新、二阶 Trotter 扫描和 `beta/2` 虚时演化 |
| [`boundary_mps.jl`](boundary_mps.jl) | 双层 transfer tensor、逐行吸收和 boundary-MPS SVD 压缩 |
| [`observables.jl`](observables.jl) | 能量、磁化、最近邻关联和中心行关联函数 |
| [`metts.jl`](metts.jl) | `Z-X` 交替顺序塌缩、Markov 链、自相关和分块误差 |
| [`run_metts_tfim.jl`](run_metts_tfim.jl) | smoke test、默认计算、终端输出和 CSV 样本输出 |
| [`test/runtests.jl`](test/runtests.jl) | 精确收缩、解析极限和 METTS 链测试 |

## 2. METTS 有限温分解

METTS 可以在任意完备正交乘积基中进行塌缩。本项目交替使用 `Z` 和 `X` 两组乘积基：

```math
\{\lvert\phi_i^Z\rangle\}
=
\{\lvert\sigma^z_1,\sigma^z_2,\ldots,\sigma^z_N\rangle\},
```

```math
\{\lvert\phi_i^X\rangle\}
=
\{\lvert\sigma^x_1,\sigma^x_2,\ldots,\sigma^x_N\rangle\}.
```

定义

```math
p_i=\langle\phi_i\rvert e^{-\beta H}\lvert\phi_i\rangle
```

以及归一化典型热纯态

```math
\lvert\psi_i\rangle
=
\frac{e^{-\beta H/2}\lvert\phi_i\rangle}{\sqrt{p_i}}.
```

热平均可以写成

```math
\langle O\rangle_\beta
=
\sum_i\frac{p_i}{Z}
\langle\psi_i\rvert O\lvert\psi_i\rangle.
```

程序不枚举所有乘积态，也不显式计算所有权重 `p_i`，而是重复

```text
乘积态 |φ_j> → 虚时演化 → METTS |ψ_j> → Z 或 X 基投影 → |φ_{j+1}>
```

从 `|ψ_j>` 投影到下一个乘积态的转移概率为

```math
P(i\rightarrow j)=\left|\langle\phi_j\vert\psi_i\rangle\right|^2.
```

每一组完备基都给出单位分解，因此在 `Z`、`X` 两组完备基之间交替转移仍保持正确的 Gibbs 热平均。交替基底通常还可以减弱固定基底下的构型滞留。丢弃热化阶段后，有限温观测量由样本平均估计：

```math
\langle O\rangle_\beta
\simeq
\frac{1}{N_s}\sum_{j=1}^{N_s}
\langle\psi_j\rvert O\lvert\psi_j\rangle.
```

完整控制函数是 [`run_metts`](metts.jl)。

## 3. 物理基底与为什么不保留严格 Z₂ 对称性

代码使用通常的 `Z` 本征基：

```math
Z=\begin{pmatrix}1&0\\0&-1\end{pmatrix},
\qquad
X=\begin{pmatrix}0&1\\1&0\end{pmatrix}.
```

`Z` 基对应投影密度矩阵为

```math
P_\uparrow=\lvert\uparrow\rangle\langle\uparrow\rvert,
\qquad
P_\downarrow=\lvert\downarrow\rangle\langle\downarrow\rvert.
```

`X` 基局域态及其投影密度矩阵为

```math
\lvert\pm_x\rangle
=
\frac{\lvert\uparrow_z\rangle\pm\lvert\downarrow_z\rangle}{\sqrt2},
```

```math
\rho_\pm^X
=
\lvert\pm_x\rangle\langle\pm_x\rvert
=
\frac{I\pm X}{2}
=
\frac12
\begin{pmatrix}
1&\pm1\\
\pm1&1
\end{pmatrix}.
```

`X` 基投影在当前 `Z` 表象中含有非对角元。计算 collapse 概率时必须把完整的 `rho_±^X` 插入双层网络，不能只替换对角元素。代码通过 [`collapse_projectors`](model.jl) 返回 `Z` 或 `X` 基的正确投影密度矩阵。

这些算符定义在 [`model.jl`](model.jl)。

相邻基态代码使用全局 `Z_2` 对称 PEPS，但单个 `Z` 基乘积态，例如全向上态，并不是自旋翻转对称态。交替链中至少每个奇数 collapse 都可能得到一般的对称破缺乘积态。因此本模块使用普通稠密数组，而不是强制对称的 `TensorMap`。

单个 METTS 可以有非零 `⟨Z⟩`。在没有纵场时，充分采样后的有限温系综平均应恢复对称性：

```math
\overline{\langle Z\rangle}\rightarrow0.
```

## 4. 有限 Γ-Λ PEPS

每个格点保存

```julia
mutable struct DenseGammaLambdaSite{T<:Number}
    gamma::Array{T,5}
    left::Vector{Float64}
    top::Vector{Float64}
    right::Vector{Float64}
    bottom::Vector{Float64}
end
```

`gamma` 的指标顺序固定为

```text
(left, top, physical, right, bottom).
```

`left`、`top`、`right`、`bottom` 是 simple update 使用的四条对角键谱 `Lambda`。相邻格点在同一内部键上保存相同的键谱。

### 4.1 乘积态初始化

[`product_peps`](state.jl) 接收一个元素为 `+1` 或 `-1` 的 `Lx × Ly` 矩阵和基底标签 `basis=:Z` 或 `basis=:X`：

```julia
configuration[x, y] = +1  # Z 向上
configuration[x, y] = -1  # Z 向下
```

在 `X` 基中，相同的 `+1/-1` 分别表示 `|+x>` 和 `|-x>`。程序仍在 `Z` 表象保存物理腿，因此 `X` 基局域张量写成

```math
A^{s}_{1,1,1,1}
=
\frac{1}{\sqrt2}(1,\pm1)_s.
```

每个格点张量初始形状为

```text
(1, 1, 2, 1, 1).
```

只有与局域测量结果对应的物理分量为 1，所有虚拟腿维数都为 1。因此初态是严格的无纠缠 `D=1` PEPS。

### 4.2 开放边界

有限 PEPS 不使用周期坐标映射。四条外边界虚腿严格为一维：

- `x=1` 的左腿维数为 1；
- `x=Lx` 的右腿维数为 1；
- `y=1` 的上腿维数为 1；
- `y=Ly` 的下腿维数为 1。

[`validate_finite_peps`](state.jl) 检查所有外边界和相邻虚拟键维数是否一致。

## 5. 有限 OBC Hamiltonian 分解

开放边界下，角点、边界点和内部点的配位数分别为 2、3、4。若对每条键统一分配 `h/4` 的横场项，角点和边界点的 Hamiltonian 会出错。

程序定义格点实际配位数

```math
z_i=\#\{\text{与格点 }i\text{ 相连的 OBC 键}\}
```

并对每条最近邻键使用

```math
h_{ij}
=
-JZ_iZ_j
-\frac{h}{z_i}X_i
-\frac{h}{z_j}X_j.
```

因为每个格点恰好属于 `z_i` 条实际键，求和后得到

```math
\sum_{\langle i,j\rangle}h_{ij}
=
-J\sum_{\langle i,j\rangle}Z_iZ_j
-h\sum_iX_i.
```

实现位于 [`site_degree` 和 `bond_hamiltonian`](model.jl)。两体虚时门为

```math
G_{ij}(\Delta\tau)=e^{-\Delta\tau h_{ij}}.
```

## 6. 为什么演化 exp(-beta H/2)

每个 METTS 的定义是

```math
\lvert\psi_i\rangle
\propto
e^{-\beta H/2}\lvert\phi_i\rangle,
```

而不是 `exp(-beta H)`。计算期望值时 bra 和 ket 各贡献一半虚时演化：

```math
\frac{
\langle\phi_i\rvert e^{-\beta H/2}Oe^{-\beta H/2}\lvert\phi_i\rangle
}{
\langle\phi_i\rvert e^{-\beta H}\lvert\phi_i\rangle
}.
```

[`imaginary_time_evolve!`](simple_update.jl) 设置

```julia
target_time = beta / 2
steps = ceil(Int, target_time / tau)
delta = target_time / steps
```

实际步长 `delta` 会略微调整，使所有步长之和严格等于 `beta/2`。

## 7. 二阶 Suzuki-Trotter 扫描

默认 `TrotterOrder=2`。一次完整时间步使用半步门 `G(delta/2)`，顺序为：

1. 所有水平键正向更新；
2. 所有竖直键正向更新；
3. 所有竖直键反向更新；
4. 所有水平键反向更新。

该回文序列给出二阶 Trotter 近似。实现位于 [`apply_trotter_step!`](simple_update.jl)。若设置 `TrotterOrder=1`，则每条键只作用一次完整 `G(delta)`。

## 8. Simple update 的两点截断

以水平键 `(x,y)-(x+1,y)` 为例。

### 8.1 吸收局域键谱

左张量吸收其 `left`、`top`、`bottom` 和目标 `right` 键谱，右张量吸收 `top`、`right`、`bottom` 键谱。这些对角键谱构成 simple update 对二维环境的局域近似。

### 8.2 作用两体门

收缩两个张量、目标键谱和 Trotter 门，得到门作用后的两点波函数 `theta`：

```math
\Theta
=
G_{ij}
\left(
\Lambda_l\Lambda_t\Lambda_b
\Gamma_A\Lambda_{AB}\Gamma_B
\Lambda_t\Lambda_r\Lambda_b
\right).
```

水平实现是 [`update_horizontal_bond!`](simple_update.jl)，竖直实现是 [`update_vertical_bond!`](simple_update.jl)。

### 8.3 SVD 与最大键维数 D

将 `theta` 重排成矩阵：左格点外腿和物理腿作为左指标，右格点指标作为右指标，然后执行

```math
\Theta_{L,R}=USV^\dagger.
```

只保留最大的 `D` 个奇异值。记录的 simple-update 截断误差是

```math
\epsilon_D
=
\frac{\sum_{\alpha>D}S_\alpha^2}
{\sum_\alpha S_\alpha^2}.
```

保留的奇异值归一化为新的目标键谱：

```math
\Lambda'_{AB}=\frac{S_D}{\lVert S_D\rVert}.
```

从 `U` 和 `V^dagger` 中移除之前吸收的外腿键谱后，得到更新后的 `Gamma_A` 和 `Gamma_B`。[`remove_leg_weight`](state.jl) 使用 cutoff 伪逆，避免直接除以数值上接近零的键谱。

### 8.4 Simple update 的含义

simple update 只用相邻对角键谱近似环境，没有使用 boundary-MPS 环境反馈优化两点截断。因此：

- `D` 是虚时演化纠缠截断的主要控制参数；
- boundary-MPS 只在测量和投影采样阶段使用；
- 当前实现不是 full update，也不是论文使用的 NTU。

## 9. Γ-Λ 到普通有限 PEPS

虚时演化结束后，程序将键谱平均分配给两端张量：

```math
A_{x,y}
=
\Gamma_{x,y}
\sqrt{\Lambda_l}
\sqrt{\Lambda_t}
\sqrt{\Lambda_r}
\sqrt{\Lambda_b}.
```

转换入口是 [`DenseFinitePEPS`](state.jl)。每个局域张量随后除以自身范数。这只给完整波函数乘上一个整体标量，不会改变由分子和分母比值计算的期望值或条件概率。

## 10. Boundary-MPS 收缩

### 10.1 双层 transfer tensor

对每个 PEPS 张量构造 bra-ket 双层：

```math
T_{(l,l'),(t,t'),(r,r'),(b,b')}
=
\sum_s
A^s_{l,t,r,b}
\overline{A^s_{l',t',r',b'}}.
```

原 PEPS 虚拟维数为 `D` 时，双层有效腿维数为 `D^2`。若在该格点测量算符 `O`，则构造

```math
T^O
=
\sum_{s,s'}
A^s O_{s',s}\overline{A^{s'}}.
```

实现位于 [`double_layer`](boundary_mps.jl)。

### 10.2 逐行吸收

已经收缩的上半部分表示为一条 boundary MPS。当前行的 transfer tensors 构成一条 MPO，并通过 [`absorb_row`](boundary_mps.jl) 吸收到旧边界中。

### 10.3 压缩到 chi

吸收一行后 boundary MPS 键维数增长。程序从左到右做 SVD，并将每条边界键截断到最大维数 `chi`。丢弃权重为

```math
\epsilon_\chi
=
\frac{\sum_{\alpha>\chi}s_\alpha^2}
{\sum_\alpha s_\alpha^2}.
```

实现位于 [`compress_boundary!`](boundary_mps.jl)。全部行吸收后，开放的上下边界维数都为 1，最终收缩得到范数或带算符插入的分子。总入口是 [`boundary_mps_contract`](boundary_mps.jl)。

## 11. 单个 METTS 的观测量

每个 METTS 都是普通纯态。任意观测量按

```math
O_j
=
\frac{\langle\psi_j\rvert O\lvert\psi_j\rangle}
{\langle\psi_j\vert\psi_j\rangle}
```

计算。代码先收缩一次范数，再在分子网络中插入算符。

[`metts_observables`](observables.jl) 测量：

- 总能量和每格点能量；
- 平均横向磁化 `⟨X⟩`；
- 平均纵向磁化 `⟨Z⟩`；
- 最近邻平均 `⟨ZZ⟩`；
- 中心格点沿水平方向的关联函数 `C_R=⟨Z_c Z_{c+R}⟩`。

总能量直接按原 Hamiltonian 组装：

```math
E_j
=
-J\sum_{\langle i,j\rangle}\langle Z_iZ_j\rangle_j
-h\sum_i\langle X_i\rangle_j.
```

## 12. Z-X 交替顺序投影采样

通用入口 [`collapse_basis`](metts.jl) 按行、从左到右依次测量所有站点。`collapse_z_basis` 和 `collapse_x_basis` 是固定基底的便捷封装。

### 12.1 为什么 PEPS 不能照搬 MPS 的正则中心

对一维开边界 MPS，可以把正交中心移动到待测站点。中心左边和右边的张量分别满足左、右正交条件，因此中心张量的物理腿范数直接给出局域条件概率。测量一个站点后，只需吸收投影结果、重新正交化并把中心移动到下一个站点。

二维 PEPS 含有闭合虚拟回路，一般不存在同时消去整个二维环境的严格全局正则形式。simple update 保存的四组 `Lambda` 只是局域环境近似，不能直接当成 Born 概率所需的完整环境。因此本实现不在 PEPS 中规定或移动正则中心，而是让 boundary-MPS 承担环境收缩的角色：对每个候选测量结果，把此前已选投影和当前候选投影插入双层 PEPS，再近似收缩整个二维网络。

两种方法的对应关系可以概括为：

| MPS METTS | 当前 PEPS METTS |
| --- | --- |
| 移动正则中心到当前站点 | 固定 PEPS，用 boundary-MPS 收缩当前站点的二维环境 |
| 中心张量给出局域概率 | 两次带投影的全局收缩给出 `w_+`、`w_-` |
| 测量后更新中心张量 | 把选中的投影加入 `insertions` |
| 沿链移动到下一站点 | 按行从左到右继续下一个格点 |

### 12.2 完整分布与顺序条件采样

设虚时演化后尚未归一化的 METTS 为

```math
\lvert\phi\rangle=e^{-\beta H/2}\lvert i\rangle.
```

在基底 `B` 中得到完整乘积构型 `s_1,...,s_N` 的 Born 概率是

```math
P(s_1,\ldots,s_N)
=
\frac{
\langle\phi\rvert\prod_{k=1}^{N}P_{s_k}^{B}\lvert\phi\rangle
}{
\langle\phi\vert\phi\rangle
}.
```

程序不枚举全部 `2^N` 个构型，而是使用概率的链式分解

```math
P(s_1,\ldots,s_N)
=P(s_1)P(s_2\mid s_1)\cdots P(s_N\mid s_1,\ldots,s_{N-1}).
```

假设前 `i-1` 个格点已经采样，并定义累积投影

```math
Q_{i-1}=\prod_{k=1}^{i-1}P_{s_k}^{B}.
```

当前格点的两个未归一化条件权重为

```math
w_+
=\langle\phi\rvert Q_{i-1}P_{i,+}^{B}\lvert\phi\rangle,
```

```math
w_-
=\langle\phi\rvert Q_{i-1}P_{i,-}^{B}\lvert\phi\rangle.
```

由于 `P_{i,+}^B+P_{i,-}^B=I`，精确收缩时有

```math
w_++w_-=\langle\phi\rvert Q_{i-1}\lvert\phi\rangle.
```

因此不需要单独保存或归一化条件波函数，直接使用

```math
p_+=\frac{w_+}{w_++w_-},
\qquad
p_-=\frac{w_-}{w_++w_-}
```

采样即可。所有 PEPS 整体归一化因子也在这一比值中消去。

### 12.3 投影如何进入双层 PEPS

对局域 PEPS 张量 `A^s_{lurd}`，无算符的双层 transfer tensor 为

```math
E[I]
=\sum_s A^s_{lurd}\overline{A^s_{\bar l\bar u\bar r\bar d}}.
```

若该格点插入投影 `P`，则 [`double_layer`](boundary_mps.jl) 构造

```math
E[P]
=\sum_{s,s'}
A^s_{lurd}P_{s',s}
\overline{A^{s'}_{\bar l\bar u\bar r\bar d}}.
```

[`boundary_mps_contract`](boundary_mps.jl) 从上到下吸收这些双层张量，每吸收一行便用 SVD 把 boundary-MPS 压缩到 `chi`，最后关闭所有开放边界并返回标量权重。此前已经采样的格点使用 `insertions` 中固定的投影；尚未采样的格点插入单位算符；当前格点分别尝试正、负两个投影。

对应的核心代码逻辑是

```julia
trial_positive = copy(insertions)
trial_positive[site] = projector_positive
trial_negative = copy(insertions)
trial_negative[site] = projector_negative

w_positive = boundary_mps_contract(
    state; chi, insertions=trial_positive
).value
w_negative = boundary_mps_contract(
    state; chi, insertions=trial_negative
).value

probabilities = sanitize_probability_weights(
    real.([w_positive, w_negative])
)
```

抽样后只把被选中的投影写回 `insertions`。这里没有在每一步显式修改 PEPS 张量；累积投影在后续全局收缩中已经严格表示了条件测量后的状态。所有局域投影彼此对易，所以在精确收缩极限下，顺序采样与一次性投影到完整乘积态等价。

### 12.4 Z-X 交替规则

第 `n` 次 collapse 使用

```math
\mathcal B_n=
\begin{cases}
Z\text{ basis}, & n\text{ 为奇数},\\
X\text{ basis}, & n\text{ 为偶数}.
\end{cases}
```

代码在 [`run_metts`](metts.jl) 中通过

```julia
next_basis = isodd(transition) ? :Z : :X
```

保证奇数次 collapse 使用 `Z` 基、偶数次 collapse 使用 `X` 基。交替互补基底可以减少 Markov 链在某类经典构型附近的滞留。

### 12.5 X 基 collapse 为什么必须包含密度矩阵非对角元

在代码使用的 `Z` 表象中，某个格点在此前测量结果条件下的未归一化约化密度矩阵可写为

```math
\rho_i^{\mathrm{cond}}
=
\begin{pmatrix}
\rho_{\uparrow\uparrow}&\rho_{\uparrow\downarrow}\\
\rho_{\downarrow\uparrow}&\rho_{\downarrow\downarrow}
\end{pmatrix}.
```

`Z` 基投影只读取对角元素：

```math
w_{Z,+}=\rho_{\uparrow\uparrow},
\qquad
w_{Z,-}=\rho_{\downarrow\downarrow}.
```

但 `X` 基投影为

```math
P_{X,\pm}=\frac{I\pm X}{2}
=\frac12
\begin{pmatrix}
1&\pm1\\
\pm1&1
\end{pmatrix},
```

所以正确权重是

```math
w_{X,+}
=\frac12\left(
\rho_{\uparrow\uparrow}+\rho_{\downarrow\downarrow}
+\rho_{\uparrow\downarrow}+\rho_{\downarrow\uparrow}
\right),
```

```math
w_{X,-}
=\frac12\left(
\rho_{\uparrow\uparrow}+\rho_{\downarrow\downarrow}
-\rho_{\uparrow\downarrow}-\rho_{\downarrow\uparrow}
\right).
```

因此不能只用 `Z` 表象 density matrix 的对角部分计算 X collapse，也不能把 Z 概率简单重新标记为 X 概率。本实现不显式形成 `rho_i^cond`，而是把完整的 `P_{X,+}` 或 `P_{X,-}` 插入双层 PEPS。投影矩阵的非对角元会自动收缩到 `rho_{up,down}` 和 `rho_{down,up}`，从而得到正确的 X 基 Born 概率。

对 `X` 基，双层网络实际收缩的是

```math
\sum_{s,s'}A^s(\rho_\pm^X)_{s',s}\overline{A^{s'}},
```

因此概率包含 `Z` 表象 density matrix 的非对角贡献，正确反映 collapse 到 `|±x>` 的概率。

### 12.6 Collapse 完成后如何进入下一条 METTS

全部格点测量完成后，`collapse_basis` 返回 `±1` 构型矩阵和当前基底标签。若刚完成 X collapse，矩阵中的 `+1/-1` 分别代表 `|+x>`、`|-x>`；若刚完成 Z collapse，则分别代表 `|up>`、`|down>`。

下一轮调用

```julia
product_peps(configuration; basis=product_basis)
```

重新构造严格的 `D=1` 乘积 PEPS，再用 simple update 作用 `exp(-beta H/2)`。因此一次 Markov 转移的数据流为

```text
当前 Z/X 乘积态
→ exp(-beta H/2) simple update
→ 有限 D 的 METTS PEPS
→ boundary-MPS 顺序条件采样
→ 新的 Z/X 乘积态
```

### 12.7 有限 chi、采样顺序和当前代价

精确 contraction 下，局域投影完备性保证 `w_++w_-` 等于此前条件分支的权重，最终联合分布也不依赖格点扫描顺序。有限 `chi` 的 boundary-MPS 截断会轻微破坏这些恒等式，因此可能产生小的顺序依赖和舍入量级负权重。

有限 `chi` 可能产生舍入量级的微小负权重。[`sanitize_probability_weights`](metts.jl) 会把容差内的负值截为零；若负值明显超过容差，则停止计算并提示增大 `chi`，避免用非物理概率继续采样。

当前透明基线实现对每个格点分别执行两次完整 boundary-MPS contraction，因此一次 `Lx × Ly` collapse 需要大约 `2LxLy` 次全局收缩。它优先保证公式与代码容易核查；后续可通过缓存上下边界及当前行左右环境，把它升级为 zipper 式增量采样，而不改变上述条件概率定义。

## 13. 完整 Markov 链数据流

[`run_metts`](metts.jl) 的每次循环执行：

```julia
gamma_lambda_state = product_peps(configuration; basis=product_basis)
evolution_history = imaginary_time_evolve!(gamma_lambda_state, para)
peps = DenseFinitePEPS(gamma_lambda_state)
observables = metts_observables(peps, para)
next_basis = isodd(transition) ? :Z : :X
configuration, diagnostics = collapse_basis(
    peps; basis=next_basis, chi=para[:chi], rng
)
product_basis = next_basis
```

具体流程为：

1. 从当前构型及其 `Z/X` 基底标签创建 `D=1` Γ-Λ PEPS；
2. 用 simple update 演化 `exp(-beta H/2)`；
3. 转换为普通有限 PEPS；
4. 用 boundary-MPS 计算当前 METTS 的观测量；
5. 奇数 collapse 选择 `Z` 基，偶数 collapse 选择 `X` 基；
6. 用对应投影 density matrix 和 boundary-MPS 条件概率逐站点抽样；
7. 保存下一构型及其基底标签并继续 Markov 链。

前 `burn_in` 次转移只用于接近平稳分布，不计入热平均。`thinning=k` 表示两个保留样本之间执行 `k` 次 Markov 转移。

## 14. 自相关、有效样本数和误差条

连续 METTS 样本一般相关，不能直接把它们当成独立样本。设丢弃 `burn_in` 后保留的某个标量观测量序列为

```math
O_1,O_2,\ldots,O_{N_s},
```

样本均值为

```math
\overline O=\frac{1}{N_s}\sum_{j=1}^{N_s}O_j.
```

程序先计算中心化序列 `delta O_j=O_j-overline O`，再用

```math
\rho(t)
=
\frac{
\frac{1}{N_s-t}\sum_{j=1}^{N_s-t}
(O_j-\overline O)(O_{j+t}-\overline O)
}{
\frac{1}{N_s}\sum_{j=1}^{N_s}(O_j-\overline O)^2
}
```

估计归一化自相关函数。积分自相关时间定义为

```math
\tau_{\mathrm{int}}
=
\max\left(1,1+2\sum_{t=1}^{t_*}\rho(t)\right).
```

当前实现最多检查

```math
t_{\max}
=
\min\left(N_s-1,\left\lfloor5\sqrt{N_s}\right\rfloor\right)
```

个 lag，并在 `rho(t)` 第一次非正时停止求和；最后强制 `tau_int>=1`。若样本方差为零或样本数不超过 2，则返回 `tau_int=1`。对应代码是 [`integrated_autocorrelation_time`](metts.jl)。

有效独立样本数估计为

```math
N_{\mathrm{eff}}=\frac{N_s}{\tau_{\mathrm{int}}}.
```

### 14.1 Blocking 标准误差

程序取分块长度

```math
L_{\mathrm{block}}=\lceil\tau_{\mathrm{int}}\rceil
```

并使用完整 block 的数量

```math
N_{\mathrm{block}}
=
\left\lfloor\frac{N_s}{L_{\mathrm{block}}}\right\rfloor.
```

不足一个完整 block 的尾部样本不进入 blocking 误差估计。第 `b` 个 block 的均值为

```math
\overline O_b
=
\frac{1}{L_{\mathrm{block}}}
\sum_{j=(b-1)L_{\mathrm{block}}+1}^{bL_{\mathrm{block}}}O_j.
```

当 `N_block>=2` 时，README 和 CSV 中报告的 error bar 是 block 均值的标准误差

```math
\Delta O
=
\frac{
\operatorname{std}(\overline O_1,\ldots,\overline O_{N_{\mathrm{block}}})
}{
\sqrt{N_{\mathrm{block}}}
}.
```

这里 `std` 使用样本标准差。当完整 block 少于 2 个时，程序退化为

```math
\Delta O
=
\frac{\operatorname{std}(O_1,\ldots,O_{N_s})}
{\sqrt{N_{\mathrm{eff}}}}.
```

只有一个保留样本时无法估计统计误差，因此 `standard_error=NaN`。

例如 `6×6`、`beta=1` 的 100 个测量样本得到

```text
tau_int = 1.5961
L_block = 2
N_block = 50
E = -60.5772 +/- 0.0888
```

因此这里的 `0.0888` 来自 50 个相邻双样本 block 均值的标准误差，而不是把 100 个相关样本直接当作独立样本。若 `tau_int=1`，则 `L_block=1`，该表达式退化为通常的 `std(O)/sqrt(N_s)`。

[`scalar_sample_summary`](metts.jl) 执行上述 blocking 分析；[`summarize_samples`](metts.jl) 为每个标量观测量和每个距离 `R` 的关联函数返回：

```text
mean
standard_error
autocorrelation_time
effective_samples
block_size
block_count
```

总能量 `E` 和每格点能量 `E/N` 分别汇总。固定格点数 `N=Lx*Ly` 时，两者的误差严格满足

```math
\Delta(E/N)=\frac{\Delta E}{N}.
```

### 14.2 Error bar 不包含哪些误差

上述 error bar 只量化有限 Markov 样本和样本自相关造成的统计不确定度，不包含：

- 有限 `D` 的 simple-update 截断误差；
- 有限 `chi` 的 boundary-MPS 收缩误差；
- 有限 Trotter 步长 `tau` 的离散化误差；
- burn-in 不足或 Markov 链未充分混合造成的偏差；
- 有限尺寸和开放边界效应。

因此高 `beta` 下非常小的 Monte Carlo error bar 并不自动说明结果已经达到相同量级的物理精度。可靠结果仍需分别扫描 `D`、`chi`、`tau`、burn-in、样本数和系统尺寸，并优先比较多条独立 Markov 链。

## 15. 默认参数

默认参数定义在 [`default_metts_parameters`](FinitePEPSMETTS.jl)：

```julia
J = 1.0
h = 2.9
beta = 1 / 0.6085
D = 3
chi = 64
tau = 0.05
burn_in = 20
samples = 100
thinning = 1
initial_state = :all_up
initial_basis = :Z
TrotterOrder = 2
```

`h=2.9` 和 `beta=1/T_c` 对应参考论文中的临界温度参数，但默认 `samples=100` 只适合程序演示，不足以得到论文精度。生产计算通常需要数千个 METTS 样本，并应使用多条独立 Markov 链。

## 16. 运行方法

快速 `2×2` smoke test：

```bash
julia --project=PEPS_TensorKit-main \
  PEPS_TensorKit-main/FinitePEPS_METTS_Ising/run_metts_tfim.jl --smoke
```

默认 `4×4` 示例：

```bash
julia --project=PEPS_TensorKit-main \
  PEPS_TensorKit-main/FinitePEPS_METTS_Ising/run_metts_tfim.jl
```

运行测试：

```bash
julia --project=PEPS_TensorKit-main \
  PEPS_TensorKit-main/FinitePEPS_METTS_Ising/test/runtests.jl
```

运行脚本会打印各观测量的均值、标准误差、自相关时间和有效样本数，并将逐样本结果写入 CSV。

## 17. 误差来源与收敛检查

这套方法有五类相互独立的误差。

### 17.1 Trotter 误差

由有限 `tau` 引起。应至少比较多组递减时间步，例如

```text
tau = 0.1, 0.05, 0.025
```

并对关键观测量做 `tau → 0` 检查。

### 17.2 PEPS 截断误差

由有限 `D` 的 simple update SVD 截断引起。应扫描

```text
D = 2, 3, 4, ...
```

并监控每次演化记录的 `max_su_error`。

### 17.3 Boundary-MPS 误差

由有限 `chi` 引起，影响范数、观测量和投影概率。应扫描

```text
chi = 32, 64, 128, ...
```

并监控 `boundary_mps_truncation_error` 和每次投影的 `max_boundary_error`。

### 17.4 Monte Carlo 误差

由有限样本数、burn-in 和自相关引起。应检查：

- 不同初始乘积态是否给出一致结果；
- 增大 burn-in 后均值是否稳定；
- 运行平均是否进入稳定平台；
- `N_eff` 是否足够大；
- 多条独立 Markov 链是否相互一致。

### 17.5 有限尺寸和开放边界误差

应比较不同 `Lx,Ly`，并优先测量中心区域。临界温度附近，能量和最近邻关联可能已经对 `D`、`chi` 收敛，但长距离 `C_R` 仍可能有明显误差。

推荐按以下顺序验证：

```math
\tau\rightarrow0,
\qquad
D\uparrow,
\qquad
\chi\uparrow,
\qquad
N_s\uparrow,
\qquad
L\uparrow.
```

## 18. 小系统严格对角化和代码验证

[`exact_thermal_observables`](model.jl) 为最多 10 个格点提供严格对角化热力学结果，可用于检查能量、磁化和最近邻关联。

当前测试覆盖：

1. `D=1` 乘积 PEPS 与 `2×2` 完整波函数范数一致；
2. 对确定的 `Z` 或 `X` 基乘积态，在同一基底顺序投影严格返回原构型；
3. `X` 基投影 density matrix 满足完备性、幂等性，并且 `Z` 本征态在 `X` 基测量时得到严格的 `1/2-1/2` 概率；
4. 演化后的 `2×2` PEPS，boundary-MPS 范数、`⟨X⟩` 和 `⟨ZZ⟩` 与完整波函数收缩在机器精度内一致；
5. `J=0` 时复现解析结果

   ```math
   \langle X\rangle=\tanh(\beta h),
   \qquad
   E/N=-h\tanh(\beta h);
   ```

6. 小规模 METTS Markov 链严格按 `Z,X,Z,...` 顺序交替 collapse，并完成统计汇总；
7. 原有 `FinitePEPS_Z2_Ising` 基态模块回归测试保持通过。

## 19. 当前顺序采样的性能限制

当前 [`collapse_basis`](metts.jl) 为保持实现透明和便于精确验证，在每个待测站点分别执行两次完整 boundary-MPS 收缩，计算 `w_+` 和 `w_-`。一次完整塌缩因此需要大约

```math
2L_xL_y
```

次完整有限 PEPS 收缩。

该方法是正确的基线实现，但没有采用参考论文中的单层边界复用和 zipper 增量更新。它适合：

- 小尺寸物理验证；
- 检查 simple update、METTS 和统计流程；
- 作为后续高性能 sampler 的正确性基准。

若要实际计算论文规模的 `17×17`、`D=3-4` 和数千样本，应把当前投影部分升级为：

1. 预先缓存每一行的下边界；
2. 测量时逐行更新上边界；
3. 在当前行维护左右局域环境；
4. 对已投影区域利用单层 PEPS；
5. 用 zipper 方式逐站点更新混合边界。

这一升级不会改变 METTS 的物理定义、simple-update 虚时演化或统计分析，只会减少投影采样中的重复收缩。

## 20. 方法定位

当前代码是一套从物理定义到数值验证完整闭合的有限 PEPS-METTS 基线：

```text
D=1 乘积 PEPS
→ exp(-beta H/2) simple update
→ 有限 D METTS PEPS
→ boundary-MPS 测量
→ 奇数 Z / 偶数 X 的 boundary-MPS 条件投影
→ 新 D=1 乘积 PEPS
→ Markov 链和自相关统计
```

它已经能够求解小型和中等有限开放方格的有限温性质，并为后续 zipper sampler、多链并行、检查点续算及更大尺寸计算提供了可验证的基础。
