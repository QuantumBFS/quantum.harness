# 二维横场 Ising 模型 Hamiltonian 与有限 PEPS 构造详解

本文结合 `FinitePEPS_METTS_Ising` 中的实际代码，说明程序如何在有限开放方格上构造二维横场 Ising 模型的 Hamiltonian，以及如何从乘积态出发构造并演化有限尺寸 PEPS。

主要涉及以下文件：

| 文件 | 作用 |
| --- | --- |
| [`model.jl`](model.jl) | Pauli 算符、OBC 配位数、键 Hamiltonian、两体 Trotter 门和小系统严格对角化 |
| [`state.jl`](state.jl) | 有限 Γ-Λ PEPS、普通有限 PEPS、乘积态初始化、张量腿权重和结构检查 |
| [`simple_update.jl`](simple_update.jl) | 两体门作用、SVD 截断和虚时演化 |
| [`metts.jl`](metts.jl) | 从乘积态构造一个 METTS 的完整调用流程 |
| [`boundary_mps.jl`](boundary_mps.jl) | 普通有限 PEPS 的双层 boundary-MPS 收缩 |
| [`observables.jl`](observables.jl) | 能量、磁化和关联函数测量 |

## 1. 模型与物理约定

程序研究有限开放方格上的二维横场 Ising 模型

```math
H=-J\sum_{\langle i,j\rangle}Z_iZ_j-h\sum_iX_i.
```

代码使用 Pauli 矩阵

```math
Z=\begin{pmatrix}1&0\\0&-1\end{pmatrix},
\qquad
X=\begin{pmatrix}0&1\\1&0\end{pmatrix},
\qquad
I=\begin{pmatrix}1&0\\0&1\end{pmatrix}.
```

它们在 `model.jl` 开头定义为

```julia
const I2 = Matrix{Float64}(I, 2, 2)
const X = [0.0 1.0; 1.0 0.0]
const Z = [1.0 0.0; 0.0 -1.0]
```

这里使用的是 Pauli 矩阵本身，而不是自旋算符 `S^α=σ^α/2`。因此 `Z` 的本征值为 `+1` 和 `-1`。

格点坐标为

```math
x=1,\ldots,L_x,
\qquad
y=1,\ldots,L_y.
```

程序不做周期回绕，只枚举向右和向下的最近邻键，所以使用开放边界条件。总最近邻键数为

```math
N_b=(L_x-1)L_y+L_x(L_y-1).
```

## 2. 为什么按键构造 Hamiltonian

对于 `N=Lx*Ly` 个自旋，完整 Hilbert 空间维数为

```math
\dim\mathcal H=2^N.
```

完整 Hamiltonian 是 `2^N × 2^N` 矩阵，不能用于较大的二维系统。PEPS 虚时演化因此不构造完整矩阵，而是把 Hamiltonian 写成最近邻键项之和：

```math
H=\sum_{\langle i,j\rangle}h_{ij}.
```

每个 `h_ij` 只作用在两个自旋上，是一个 `4 × 4` 矩阵。程序随后逐键构造两体虚时门

```math
G_{ij}(\delta)=e^{-\delta h_{ij}},
```

并把这些门依次作用到相邻 PEPS 张量上。

## 3. OBC 下格点实际配位数

开放边界下，不同位置的格点具有不同配位数：

```math
z_i=
\begin{cases}
2,&\text{角点},\\
3,&\text{边界非角点},\\
4,&\text{内部点}.
\end{cases}
```

`site_degree` 通过检查四个方向是否存在相邻格点来计算该数值：

```julia
function site_degree(Lx, Ly, x, y)
    return (x > 1) + (x < Lx) + (y > 1) + (y < Ly)
end
```

在 Julia 中，布尔值参与加法时分别相当于 `0` 和 `1`，所以四个判断之和就是实际相邻键数。

## 4. 将格点横场正确分配到键上

相互作用项 `-J Z_i Z_j` 天然属于一条键，而横场项 `-h X_i` 属于单个格点。为了只使用两体门演化，需要把每个格点的横场分配到与它相连的所有实际键上。

程序对键 `⟨i,j⟩` 定义

```math
h_{ij}
=
-JZ_iZ_j
-\frac{h}{z_i}X_i
-\frac{h}{z_j}X_j.
```

在两自旋 Hilbert 空间中写成

```math
h_{ij}
=
-J(Z\otimes Z)
-\frac{h}{z_i}(X\otimes I)
-\frac{h}{z_j}(I\otimes X).
```

对应 `bond_hamiltonian`：

```julia
return -para[:J] * kron(Z, Z) -
       (para[:h] / degree1) * kron(X, I2) -
       (para[:h] / degree2) * kron(I2, X)
```

这一分配在 OBC 下非常重要。格点 `i` 一共属于 `z_i` 条键，所以对所有相关键求和时

```math
\sum_{j\in\partial i}-\frac{h}{z_i}X_i=-hX_i.
```

因此

```math
\sum_{\langle i,j\rangle}h_{ij}
=
-J\sum_{\langle i,j\rangle}Z_iZ_j
-h\sum_iX_i,
```

精确恢复原始 Hamiltonian。

如果对所有键都固定分配 `h/4`，内部点虽然正确，但角点只能得到 `h/2`，普通边界点只能得到 `3h/4`，从而改变有限尺寸模型本身。

## 5. 键坐标与方向

`bond_sites` 接收起点 `(x,y)` 和方向：

```julia
direction === :right && return (x, y), (x + 1, y)
direction === :down  && return (x, y), (x, y + 1)
```

程序只使用两类键：

```text
:right  (x,y) —— (x+1,y)
:down   (x,y) —— (x,y+1)
```

这样每条 OBC 最近邻键只出现一次，不会重复计数。

## 6. 两体虚时门及其指标顺序

`trotter_gate` 首先计算

```julia
matrix = exp(-delta * bond_hamiltonian(...))
```

即

```math
G_{ij}(\delta)=e^{-\delta h_{ij}}.
```

这个对象最初是 `4 × 4` 矩阵，随后被整理成四阶张量

```math
G^{p_1p_2}_{q_1q_2}.
```

代码中固定按照

```julia
gate[p1, p2, q1, q2]
```

使用，其中：

- `q1,q2` 是门作用前的物理指标；
- `p1,p2` 是门作用后的物理指标。

`reshape` 后的 `permutedims` 用来调整 Julia 的列主序和 `kron` 基底顺序，使门的指标约定与后面的 `@tensor` 收缩一致。

需要区分：

- `H=Σh_ij` 的键分解是精确的；
- 用各个 `exp(-δh_ij)` 的乘积近似 `exp(-δH)` 是 Trotter 近似，因为相邻键项一般不对易。

## 7. METTS 为什么演化 `β/2`

一个 METTS 定义为

```math
|\psi_\phi\rangle
=
\frac{e^{-\beta H/2}|\phi\rangle}
{\sqrt{\langle\phi|e^{-\beta H}|\phi\rangle}}.
```

因此 ket 只需要演化虚时间 `β/2`；计算期望值时 bra 再贡献另外一半。

`imaginary_time_evolve!` 设置

```julia
target_time = beta / 2
steps = max(1, ceil(Int, target_time / requested_tau))
delta = target_time / steps
```

所以实际步长可能比输入的 `tau` 略小，但所有步长之和严格等于 `β/2`。

默认二阶 Trotter 的一次完整时间步使用半步门 `G(delta/2)`，执行顺序为：

1. 所有水平键正向扫描；
2. 所有竖直键正向扫描；
3. 所有竖直键反向扫描；
4. 所有水平键反向扫描。

这个回文序列构成二阶对称 Trotter 分解。

## 8. 有限 PEPS 的局域张量

每个有限 PEPS 格点使用五阶张量

```math
A^s_{l,t,r,b},
```

代码中的数组指标顺序固定为

```text
(left, top, physical, right, bottom).
```

形状为

```math
(D_l,D_t,2,D_r,D_b).
```

第三个指标是维数为 2 的物理腿，其余四个是虚拟腿。

有限 PEPS 显式保存全部 `Lx*Ly` 个格点张量，不要求平移不变，也不使用周期坐标映射。

## 9. 演化阶段的 Γ-Λ 表示

`DenseGammaLambdaSite` 定义为

```julia
mutable struct DenseGammaLambdaSite{T<:Number}
    gamma::Array{T,5}
    left::Vector{Float64}
    top::Vector{Float64}
    right::Vector{Float64}
    bottom::Vector{Float64}
end
```

其中：

- `gamma` 是局域五阶张量 `Γ`；
- `left/top/right/bottom` 是四条腿对应的对角键谱 `Λ`。

每个 `Λ` 只保存对角元素，因此使用一维向量。例如

```julia
right = [0.91, 0.37, 0.12]
```

表示

```math
\Lambda_r=\operatorname{diag}(0.91,0.37,0.12).
```

相邻格点在同一条键上保存相同的谱：

```math
\Lambda^R_{x,y}=\Lambda^L_{x+1,y},
```

```math
\Lambda^B_{x,y}=\Lambda^T_{x,y+1}.
```

整个 Γ-Λ PEPS 由

```julia
struct DenseFinitePEPSGammaLambda{T<:Number}
    sites::Matrix{DenseGammaLambdaSite{T}}
    Lx::Int
    Ly::Int
end
```

保存，主要用于 simple-update 虚时演化。

## 10. 普通有限 PEPS 表示

测量阶段使用

```julia
struct DenseFinitePEPS{T<:Number}
    sites::Matrix{Array{T,5}}
    Lx::Int
    Ly::Int
end
```

这里每个位置直接保存完整局域张量 `A[x,y]`，不再单独保存 `Γ` 和 `Λ`。它主要用于：

- boundary-MPS 收缩；
- 范数和观测量计算；
- METTS 条件投影概率；
- `2 × 2` 小系统精确收缩。

代码重载了 `getindex`，所以可以直接写

```julia
state[x, y]
```

代替 `state.sites[x,y]`。

## 11. 从 Z/X 基乘积态初始化 PEPS

`product_peps(configuration; basis)` 接收一个 `Lx × Ly` 构型矩阵

```math
c_{x,y}\in\{+1,-1\}.
```

每个格点初始张量形状为

```julia
gamma = zeros(dtype, 1, 1, 2, 1, 1)
```

即

```math
(D_l,D_t,d,D_r,D_b)=(1,1,2,1,1).
```

所有虚拟腿维数都是 1，所以初始态没有纠缠，是严格的 `D=1` 乘积 PEPS。

### 11.1 Z 基乘积态

当 `basis=:Z` 时，代码使用

```math
c_{x,y}=+1
\quad\Longrightarrow\quad
|\uparrow_z\rangle=(1,0)^T,
```

```math
c_{x,y}=-1
\quad\Longrightarrow\quad
|\downarrow_z\rangle=(0,1)^T.
```

整个状态是

```math
|\phi\rangle=\bigotimes_{x,y}|\sigma^z_{x,y}\rangle.
```

### 11.2 X 基乘积态

当 `basis=:X` 时，物理腿仍然在 Z 基中存储，但局域分量写成

```math
|+x\rangle
=\frac{|\uparrow_z\rangle+|\downarrow_z\rangle}{\sqrt2},
```

```math
|-x\rangle
=\frac{|\uparrow_z\rangle-|\downarrow_z\rangle}{\sqrt2}.
```

也就是

```math
\Gamma^s=\frac1{\sqrt2}(1,\pm1)_s.
```

所有初始键谱均为

```math
\Lambda=(1).
```

## 12. 开放边界如何编码进有限 PEPS

四条外边界的向外虚拟腿严格为一维：

```math
D_l(1,y)=1,
\qquad
D_r(L_x,y)=1,
```

```math
D_t(x,1)=1,
\qquad
D_b(x,L_y)=1.
```

内部相邻虚腿必须满足

```math
D_r(x,y)=D_l(x+1,y),
```

```math
D_b(x,y)=D_t(x,y+1).
```

`validate_finite_peps` 检查：

1. 每个格点张量必须是五阶；
2. 第三个物理指标维数必须是 2；
3. 四条外边界腿必须为一维；
4. 所有水平和竖直内部键维数必须匹配。

这些检查保证张量网络确实表示一个可收缩的有限 OBC PEPS。

## 13. `multiply_leg`：把键谱乘到张量腿上

`multiply_leg(tensor, weights, leg)` 实现

```math
A'_{i_1\cdots i_{\rm leg}\cdots i_5}
=
w_{i_{\rm leg}}
A_{i_1\cdots i_{\rm leg}\cdots i_5}.
```

例如

```julia
multiply_leg(tensor, site.left, 1)
```

表示

```math
A'_{l,t,s,r,b}=\Lambda_l(l)A_{l,t,s,r,b}.
```

函数通过 reshape 和广播实现这一操作，不需要显式构造对角矩阵。

## 14. 两体门如何产生纠缠

以水平键 `(x,y)-(x+1,y)` 为例，记左格点为 `A`，右格点为 `B`。

程序先把周围键谱吸收到两个 Γ 张量中，再将两个张量、目标键和两体门收缩成两点张量 `Theta`：

```math
\Theta
=
G_{AB}
\left(
\Lambda_{\rm env,A}\Gamma_A
\Lambda_{AB}
\Gamma_B\Lambda_{\rm env,B}
\right).
```

水平更新中的核心代码是

```julia
@tensor theta[l, t1, b1, p1, p2, t2, r, b2] :=
    left_tensor[l, t1, q1, bond, b1] *
    right_tensor[bond, t2, q2, r, b2] *
    gate[p1, p2, q1, q2]
```

门将两个格点的物理自由度耦合起来，因此原来的乘积态一般不再能够写成两个独立张量的乘积，目标虚拟键的秩会增长。这就是虚时演化在 PEPS 中产生纠缠的方式。

## 15. SVD 与最大键维数 D

程序将 `Theta` 按两个格点划分成矩阵：

```math
\Theta_{L,R}=USV^\dagger.
```

只保留最大的

```math
D_{\rm keep}=\min(D,\operatorname{rank}\Theta)
```

个奇异值。被丢弃的相对权重定义为

```math
\epsilon_D
=
\frac{\sum_{\alpha>D}S_\alpha^2}
{\sum_\alpha S_\alpha^2}.
```

保留的奇异值归一化后成为目标键的新键谱：

```math
\Lambda'_{AB}
=
\frac{S_{\rm keep}}
{\|S_{\rm keep}\|_2}.
```

随后：

- `U` reshape 成新的 `Gamma_A`；
- `V†` reshape 成新的 `Gamma_B`；
- 移除构造 `Theta` 时吸收的外部键谱；
- 把同一个新 `Lambda_AB` 保存到目标键两端。

水平键更新后：

```julia
left.right = singular_values
right.left = singular_values
```

竖直键更新后：

```julia
upper.bottom = singular_values
lower.top = singular_values
```

因此演化过程可以概括为

```text
D=1 乘积 PEPS
    → 两体门产生纠缠
    → 两点张量 SVD
    → 截断到最大键维数 D
    → 更新 Γ 和 Λ
```

`D` 是 PEPS 自身的虚拟键维数，控制能够保留的纠缠量。它不同于 boundary-MPS 收缩使用的 `chi`：

- `D` 控制波函数近似；
- `chi` 控制双层 PEPS 环境收缩近似。

## 16. `remove_leg_weight`：稳定地移除外部键谱

SVD 后要从新张量中除掉先前吸收的环境 `Lambda`。形式上需要乘 `1/Lambda`，但极小奇异值会导致数值爆炸。

`remove_leg_weight` 因而使用带 cutoff 的伪逆：

```math
\Lambda_\alpha^+
=
\begin{cases}
1/\Lambda_\alpha,&|\Lambda_\alpha|>\epsilon,\\
0,&|\Lambda_\alpha|\leq\epsilon,
\end{cases}
```

其中默认阈值为

```math
\epsilon=10^{-12}\max(\|\Lambda\|_\infty,1).
```

这避免除零并抑制近零键谱对浮点误差的放大。

## 17. 从 Γ-Λ 表示转换成普通有限 PEPS

虚时演化结束后，`DenseFinitePEPS(gamma_lambda_state)` 将每条键谱平均分配给相邻两端：

```math
A_{x,y}
=
\Gamma_{x,y}
\sqrt{\Lambda_l}
\sqrt{\Lambda_t}
\sqrt{\Lambda_r}
\sqrt{\Lambda_b}.
```

对于一条内部键，左端吸收 `sqrt(Lambda)`，右端也吸收 `sqrt(Lambda)`。收缩该键时恰好恢复

```math
\sqrt\Lambda\sqrt\Lambda=\Lambda.
```

如果两端都吸收完整 `Lambda`，则会错误地产生 `Lambda^2`。

转换时每个局域张量还会除以自身 Frobenius 范数：

```math
\widetilde A_{x,y}
=
\frac{A_{x,y}}{\|A_{x,y}\|}.
```

这只给完整波函数乘上一个整体标量。由于观测量和投影概率都由归一化比值计算，整体标量会在分子和分母中抵消，不改变物理结果。

## 18. `2 × 2` PEPS 的精确波函数

`exact_wavefunction` 专门用于测试 `2 × 2` 普通有限 PEPS。格点和物理指标排列为

```text
p1 —— p2
|       |
p3 —— p4
```

去掉四周维数为 1 的外边界腿后，精确收缩四条内部键：

```math
\Psi_{p_1p_2p_3p_4}
=
\sum_{a,b,c,d}
A^{\rm UL}_{p_1,a,b}
A^{\rm UR}_{a,p_2,c}
A^{\rm LL}_{b,p_3,d}
A^{\rm LR}_{d,c,p_4}.
```

返回数组形状为 `(2,2,2,2)`，包含全部 `2^4=16` 个波函数振幅。它用于把精确范数和观测量与 boundary-MPS 收缩结果比较。

## 19. 完整构造流程

`run_metts` 中构造一个有限 PEPS METTS 的核心调用是

```julia
gamma_lambda_state = product_peps(configuration; basis=product_basis)
evolution_history = imaginary_time_evolve!(gamma_lambda_state, para)
peps = DenseFinitePEPS(gamma_lambda_state)
validate_finite_peps(peps)
```

完整逻辑为

```text
±1 经典构型
    │
    ▼
Z 或 X 基局域态
    │
    ▼
D=1、无纠缠 Γ-Λ 乘积 PEPS
    │
    ▼
按 OBC 配位数构造每条键的 h_ij
    │
    ▼
构造 G_ij(delta)=exp(-delta*h_ij)
    │
    ▼
二阶 Trotter 逐键作用到 β/2
    │
    ▼
每条键做 SVD 并截断到最大 D
    │
    ▼
得到纠缠的 Γ-Λ PEPS
    │
    ▼
将 sqrt(Lambda) 分配给相邻张量
    │
    ▼
普通有限 OBC PEPS
    │
    ├── boundary-MPS 测量
    └── Z/X 基条件投影产生下一乘积态
```

## 20. 严格对角化函数的验证作用

`model.jl` 中的 `exact_thermal_observables` 不参与较大系统的 PEPS 演化，而是在最多 10 个格点的完整 `2^N` 维 Hilbert 空间中显式构造

```math
H=-J\sum_{\langle i,j\rangle}Z_iZ_j-h\sum_iX_i,
```

并完整对角化得到 Gibbs 密度矩阵

```math
\rho_\beta=\frac{e^{-\beta H}}{\operatorname{Tr}e^{-\beta H}}.
```

它提供小系统严格结果，用来验证：

- Hamiltonian 的符号和边界条件；
- Trotter 步长误差；
- PEPS 键维数 `D` 的截断误差；
- boundary-MPS 的 `chi` 截断误差；
- METTS 的有限样本统计误差。

## 21. 总结

这套实现的核心思想是：

1. 根据有限 OBC 格点的真实配位数，把横场严格分配到实际最近邻键上；
2. 将 Hamiltonian 写成局域两体键项之和，并构造两体虚时门；
3. 从 Z 或 X 基的 `D=1` 乘积 PEPS 出发；
4. 用二阶 Trotter 和 simple update 逐键产生纠缠；
5. 用 SVD 将每条虚拟键截断到最大维数 `D`；
6. 将 Γ-Λ 表示转换为显式保存全部 `Lx × Ly` 格点张量的普通有限 OBC PEPS；
7. 使用 boundary-MPS 对该有限 PEPS 进行测量和 METTS collapse。

因此，代码既没有构造大系统的完整 Hamiltonian 矩阵，也没有假设无限平移不变 PEPS，而是直接围绕有限开放方格的局域键结构构造和演化张量网络。
