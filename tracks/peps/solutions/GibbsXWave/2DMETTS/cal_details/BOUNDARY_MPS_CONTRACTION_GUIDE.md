# 利用 Boundary-MPS 收缩有限 PEPS 双层环境网络

本文结合 `FinitePEPS_METTS_Ising` 项目的实际代码，详细说明如何使用 boundary-MPS 方法收缩有限开放边界 PEPS 的双层环境网络，以及 `boundary_mps.jl` 中各个函数的数学意义、张量指标和调用关系。

主要相关文件如下：

- [`boundary_mps.jl`](boundary_mps.jl)：双层张量、逐行吸收、SVD 压缩和最终闭合；
- [`state.jl`](state.jl)：有限 PEPS 数据结构和 Γ-Λ 到普通 PEPS 的转换；
- [`observables.jl`](observables.jl)：范数、单点和两点期望值；
- [`metts.jl`](metts.jl)：利用带投影的双层收缩计算 METTS collapse 条件概率；
- [`test/runtests.jl`](test/runtests.jl)：与小系统精确收缩的对照测试。

## 1. 方法概览

boundary-MPS 的基本思想是把有限二维 PEPS 的双层网络逐行消去：

```text
有限 PEPS
    ↓
每个格点构造 bra-ket 双层张量
    ↓
把一行双层张量视为 transfer MPO
    ↓
将 transfer MPO 作用到代表上方环境的 boundary MPS
    ↓
用 SVD 将 boundary MPS 键维数截断到 chi
    ↓
继续吸收下一行
    ↓
吸收最后一行并关闭所有开放腿
    ↓
得到范数、期望值分子或投影候选权重
```

这里的“环境”不是 CTMRG 中显式保存的四个角张量和四条边张量。当前代码把已经收缩完的上方若干行编码成一条横向 MPS。这条 boundary MPS 就是下一行看到的有效上环境。

代码的调用链是：

```text
boundary_mps_contract
    ├── double_layer
    ├── absorb_row
    ├── compress_boundary!
    └── close_boundary
```

## 2. 有限 PEPS 的局域张量

普通有限 PEPS 由 `DenseFinitePEPS` 表示。每个格点保存一个五阶数组：

```julia
tensor[l, t, p, r, b]
```

指标顺序固定为：

```text
(left, top, physical, right, bottom)
```

数学上写成

```math
A^p_{l,t,r,b}.
```

其中：

- `l`：左虚拟腿；
- `t`：上虚拟腿；
- `p`：局域物理腿；
- `r`：右虚拟腿；
- `b`：下虚拟腿。

对于横场 Ising 模型，物理维数为

```math
d=2.
```

如果内部 PEPS 键维数为 `D`，内部格点张量的典型尺寸是

```text
(D, D, 2, D, D).
```

项目采用有限开放边界：

- `x=1` 时左腿维数为 1；
- `x=Lx` 时右腿维数为 1；
- `y=1` 时上腿维数为 1；
- `y=Ly` 时下腿维数为 1。

这些条件由 [`validate_finite_peps`](state.jl) 检查。

### 2.1 从 Γ-Λ PEPS 转换为普通 PEPS

虚时演化阶段使用 Γ-Λ 表示。测量和 boundary-MPS 收缩前，代码把每条键谱的一半分配到键的两端：

```math
A_{x,y}
=
\Gamma_{x,y}
\sqrt{\Lambda_l}
\sqrt{\Lambda_t}
\sqrt{\Lambda_r}
\sqrt{\Lambda_b}.
```

转换入口是 [`DenseFinitePEPS(state::DenseFinitePEPSGammaLambda)`](state.jl)。每个局域张量随后除以自身范数。这只会给完整 PEPS 波函数乘上一个总体标量，因此不改变由分子和分母比值计算的期望值或条件概率。

## 3. 为什么要构造双层网络

PEPS 测量涉及

```math
\langle\psi|\psi\rangle
```

或

```math
\langle\psi|O|\psi\rangle.
```

因此需要把 ket PEPS 和共轭 bra PEPS 叠起来，并在每个格点收缩物理指标。

对于无算符格点，局域双层张量定义为

```math
E[I]_{(l,\bar l),(t,\bar t),(r,\bar r),(b,\bar b)}
=
\sum_p
A^p_{l,t,r,b}
\overline{A^p_{\bar l,\bar t,\bar r,\bar b}}.
```

对于插入局域算符 `O` 的格点：

```math
E[O]_{(l,\bar l),(t,\bar t),(r,\bar r),(b,\bar b)}
=
\sum_{p,q}
A^p_{l,t,r,b}
O_{q,p}
\overline{A^q_{\bar l,\bar t,\bar r,\bar b}}.
```

原物理腿在局域双层张量内部已经被收缩。后续 boundary-MPS 处理的“物理腿”实际是二维网络切口上的双层虚拟腿。

如果单层 PEPS 虚拟腿维数是 `D`，融合 bra 和 ket 后双层腿维数为

```math
D^2.
```

## 4. `BoundaryMPSResult`

文件首先定义：

```julia
struct BoundaryMPSResult{T}
    value::T
    max_truncation_error::Float64
end
```

### 4.1 `value`

`value` 是最终完整双层网络收缩得到的标量。它的意义取决于算符插入：

- 无插入：`value ≈ ⟨ψ|ψ⟩`；
- 单点插入：`value ≈ ⟨ψ|Oᵢ|ψ⟩`；
- 多点插入：`value ≈ ⟨ψ|∏ᵢOᵢ|ψ⟩`；
- collapse 投影插入：`value` 是相应候选结果的联合 Born 权重。

类型参数 `T` 允许结果为实数或复数。

### 4.2 `max_truncation_error`

它记录一次完整收缩中所有 boundary-MPS SVD 切口的最大相对丢弃权重：

```math
\epsilon_{\max}
=
\max_{y,x}
\frac{\sum_{\alpha>\chi}s_{x,y,\alpha}^2}
{\sum_\alpha s_{x,y,\alpha}^2}.
```

这个量是数值诊断，不是最终标量误差的严格上界。实际收敛性需要通过增大 `chi` 后比较观测量来判断。

## 5. `double_layer`

函数接口是：

```julia
function double_layer(
    tensor::AbstractArray{<:Number,5},
    operator::Union{Nothing,AbstractMatrix}=nothing,
)
```

它把一个五阶单层 PEPS 张量转换成四阶双层 transfer tensor。

### 5.1 无算符分支

当 `operator === nothing` 时：

```julia
@tensor raw[l, lb, t, tb, r, rb, b, bb] :=
    tensor[l, t, p, r, b] *
    conj(tensor[lb, tb, p, rb, bb])
```

物理指标 `p` 同时出现在 ket 和 bra 中，因此被收缩。这等价于插入单位算符。

### 5.2 有算符分支

如果提供 `operator`，代码先检查其尺寸是否和局域物理空间一致，然后构造：

```julia
@tensor raw[l, lb, t, tb, r, rb, b, bb] :=
    tensor[l, t, p, r, b] *
    conj(tensor[lb, tb, q, rb, bb]) *
    operator[q, p]
```

这里：

- `p` 是 ket 物理指标；
- `q` 是 bra 物理指标；
- `operator[q,p]` 对应标准的 `⟨ψ|O|ψ⟩` 指标约定。

对于 `X` 基 collapse，这个分支会保留投影矩阵的非对角元，因而能够正确包含局域条件密度矩阵中的相干项。

### 5.3 融合 bra-ket 虚拟腿

中间张量 `raw` 有八个指标：

```text
(l, lb, t, tb, r, rb, b, bb)
```

代码通过 reshape 融合每个方向的 bra、ket 指标：

```julia
reshape(raw, left_dim^2, top_dim^2, right_dim^2, bottom_dim^2)
```

输出指标顺序为：

```text
(left_double, top_double, right_double, bottom_double)
```

即后续代码中的

```julia
layer[l, t, r, b]
```

其中每个内部双层腿的维数通常为 `D^2`。

## 6. 将一行双层张量看成 transfer MPO

固定第 `y` 行后，双层张量

```math
E^{[1,y]},E^{[2,y]},\ldots,E^{[L_x,y]}
```

沿水平方向通过左右腿连接，组成一条 transfer MPO：

- MPO 左右键：当前 PEPS 行的双层水平虚腿；
- MPO 输入物理腿：当前行的双层 `top` 腿；
- MPO 输出物理腿：当前行的双层 `bottom` 腿。

已收缩的上方区域表示为一条 boundary MPS：

```math
B^{[x]}_{a,t,c}.
```

三个指标依次为：

```text
(left boundary bond, vertical physical leg, right boundary bond)
```

其中 boundary MPS 的“物理腿” `t` 是上方区域向下伸出的双层虚腿，不是原模型的自旋物理腿。

吸收第 `y` 行以后，boundary MPS 表示

```math
B_y(\{b_x\})
\approx
\sum_{\text{第 1 到第 }y\text{ 行的内部指标}}
\prod_{y'=1}^{y}\prod_x E^{[x,y']}.
```

它是第 `y+1` 行所看到的有效上环境。

## 7. `absorb_row`

函数接口是：

```julia
function absorb_row(
    boundary::Vector{<:AbstractArray},
    row::Vector{<:AbstractArray},
)
```

它把当前行的 transfer MPO 作用到旧 boundary MPS 上。

### 7.1 输入

旧 boundary tensor：

```math
B_{a,t,c},
```

形状为

```text
(left MPS bond, top double leg, right MPS bond).
```

当前行的双层 tensor：

```math
E_{l,t,r,b},
```

形状为

```text
(left MPO bond, top double leg, right MPO bond, bottom double leg).
```

函数首先检查 boundary MPS 和当前行拥有相同的横向长度，并检查

```math
\dim(t_{\mathrm{boundary}})=\dim(t_{\mathrm{row}}).
```

### 7.2 收缩共同竖直腿

局域收缩为：

```julia
@tensor combined[a, l, b; c, r] :=
    boundary_tensor[a, t, c] *
    layer[l, t, r, b]
```

数学上：

```math
C_{a,l,b,c,r}
=
\sum_t B_{a,t,c}E_{l,t,r,b}.
```

收缩掉的 `t` 是旧环境与当前行之间的竖直切口。

### 7.3 融合水平方向的键

新 boundary MPS 的左键和右键分别定义为

```math
\widetilde a=(a,l),
\qquad
\widetilde c=(c,r).
```

代码使用 reshape：

```julia
result[x] = reshape(
    combined,
    size(boundary_tensor, 1) * size(layer, 1),
    size(layer, 4),
    size(boundary_tensor, 3) * size(layer, 3),
)
```

得到

```math
B'_{\widetilde a,b,\widetilde c}.
```

它的尺寸是

```math
(\dim a\dim l,\ \dim b,\ \dim c\dim r).
```

新的 boundary 物理腿 `b` 是当前行向下伸出的双层腿，会在下一次吸收时与下一行的 `top` 腿连接。

### 7.4 为什么键维数会增长

如果旧 boundary 键已经为 `chi`，当前双层 PEPS 的水平腿维数为 `D^2`，吸收后边界键可能增大为

```math
\chi D^2.
```

继续逐行吸收而不压缩会导致键维数随系统高度指数增长。因此每次 `absorb_row` 后都必须调用 `compress_boundary!`。

## 8. `compress_boundary!`

函数接口是：

```julia
function compress_boundary!(
    boundary::Vector{<:AbstractArray},
    chi::Integer,
)
```

函数名末尾的 `!` 表示它会原地修改 boundary MPS。

它从左到右扫描所有内部 boundary 键，并用 SVD 把每条键截断到最大维数 `chi`。

### 8.1 将当前三阶张量矩阵化

对于

```math
B^{[x]}_{a,p,c},
```

融合左键和 boundary 物理腿：

```math
M_{(a,p),c}=B^{[x]}_{a,p,c}.
```

代码是：

```julia
matrix = reshape(boundary[x], left_dim * physical_dim, right_dim)
```

随后检查矩阵中不存在 `NaN` 或 `Inf`。

### 8.2 SVD

代码执行

```julia
factorization = svd(matrix; alg=LinearAlgebra.QRIteration())
```

即

```math
M=USV^\dagger.
```

保留数目是

```math
\chi_{\mathrm{kept}}
=
\min(\chi,\operatorname{length}(S)).
```

### 8.3 截断误差

当前切口的相对丢弃权重是

```math
\epsilon_\chi
=
\frac{\sum_{\alpha>\chi_{\mathrm{kept}}}s_\alpha^2}
{\sum_\alpha s_\alpha^2}.
```

如果输入矩阵为零，代码把误差定义为零，避免出现 `0/0`。

### 8.4 用 `U` 更新当前张量

保留的 `U` 被 reshape 回三阶张量：

```julia
boundary[x] = reshape(
    U[:, 1:kept],
    left_dim,
    physical_dim,
    kept,
)
```

因此当前张量的新右键维数变成 `kept ≤ chi`。同时当前张量处于左等距形式：

```math
\sum_{a,p}
\overline{B^{[x]}_{a,p,\alpha}}
B^{[x]}_{a,p,\beta}
=
\delta_{\alpha\beta}.
```

### 8.5 把 `SV†` 传给右侧张量

代码构造

```julia
carry = Diagonal(S[1:kept]) * Vt[1:kept, :]
```

并吸收到右边相邻张量：

```math
B^{[x+1]\prime}_{\alpha,p,d}
=
\sum_c
(SV^\dagger)_{\alpha,c}
B^{[x+1]}_{c,p,d}.
```

如果没有丢弃奇异值，这只是 MPS 的精确重新分解，整条 boundary MPS 表示的张量不变。如果发生截断，则保留当前切口上权重最大的 `chi` 个 Schmidt 分量。

### 8.6 当前压缩策略的性质

当前实现采用一次从左到右的单向 SVD 压缩：

- 每个局部矩阵截断在 Frobenius 范数意义下最优；
- 扫描过程中 boundary MPS 被逐步左正交化；
- 没有右到左的第二次 sweep；
- 没有进行变分 MPS-MPO 压缩；
- 没有用双向环境进一步优化截断。

所以它结构简单、容易验证，但在相同 `chi` 下不一定达到变分压缩方法的最佳精度。

## 9. 顶边界初始化

第一次处理 `y=1` 时还没有旧 boundary MPS。`boundary_mps_contract` 初始化

```julia
tensor = zeros(eltype(row[x]), 1, size(row[x], 2), 1)
tensor[1, 1, 1] = one(eltype(tensor))
```

由于有限开放 PEPS 第一行的上腿维数为 1，实际得到

```math
B^{[x]}_{1,1,1}=1.
```

这表示网络上方没有任何张量，只有平凡的开放边界。

## 10. `close_boundary`

函数接口是：

```julia
function close_boundary(boundary::Vector{<:AbstractArray})
```

它在所有 PEPS 行都被吸收后，将最后一条 boundary MPS 收缩成标量。

### 10.1 检查底边界

最终 boundary tensor 的第二个指标来自最后一行的双层 `bottom` 腿。开放边界要求

```math
\dim(b_x)=1.
```

代码检查：

```julia
all(size(tensor, 2) == 1 for tensor in boundary)
```

如果不满足，说明仍然存在未收缩的竖直开放腿。

### 10.2 删除平凡竖直腿

每个三阶 tensor

```math
B^{[x]}_{a,1,c}
```

被取成矩阵：

```julia
boundary[x][:, 1, :]
```

### 10.3 收缩水平 boundary 键

程序从左到右进行矩阵乘法：

```math
M^{[1]}M^{[2]}\cdots M^{[L_x]}.
```

由于 PEPS 的最左和最右边界腿也是一维，最终结果必须是一个 `1×1` 矩阵。它的唯一元素就是完整二维双层网络的收缩值。

## 11. `boundary_mps_contract`

总入口是：

```julia
function boundary_mps_contract(
    state::DenseFinitePEPS;
    chi::Integer,
    insertions::AbstractDict=Dict{CartesianIndex{2},Any}(),
)
```

### 11.1 参数

`state` 是待收缩的有限开放边界 PEPS。

`chi` 是 boundary MPS 的最大内部键维数：

- `chi` 小：速度快、内存少、环境截断误差较大；
- `chi` 大：收缩更接近精确值，但 SVD 成本和内存快速增长。

`insertions` 是格点到局域算符的字典，例如：

```julia
Dict(
    CartesianIndex(2, 3) => Z,
    CartesianIndex(3, 3) => Z,
)
```

没有出现在字典中的格点自动使用单位算符。

### 11.2 从上到下扫描

程序按照

```math
y=1,2,\ldots,L_y
```

逐行处理。对当前行每个格点执行：

```julia
double_layer(
    state[x, y],
    get(insertions, CartesianIndex(x, y), nothing),
)
```

其中：

- 字典中存在当前格点：构造带算符的双层张量；
- 字典中不存在当前格点：构造恒等双层张量。

### 11.3 每一行的完整操作

对每一行，程序依次执行：

```julia
boundary = absorb_row(boundary, row)
max_error = max(max_error, compress_boundary!(boundary, chi))
```

即

```math
|B_y^{\mathrm{raw}}\rangle
=
\mathcal T_y|B_{y-1}\rangle,
```

然后

```math
|B_y\rangle
\approx
\mathcal P_\chi|B_y^{\mathrm{raw}}\rangle,
```

其中 `P_chi` 表示逐键保留至多 `chi` 个奇异分量的压缩。

### 11.4 最终返回

所有行吸收完成后：

```julia
BoundaryMPSResult(
    close_boundary(boundary),
    max_error,
)
```

返回最终标量和整次收缩的最大局部截断误差。

## 12. 整个过程中张量形状的变化

### 12.1 单层 PEPS tensor

```math
A[l,t,p,r,b]
```

典型形状：

```text
(D, D, d, D, D)
```

### 12.2 `double_layer` 输出

```math
E[L,T,R,B]
```

典型形状：

```text
(D², D², D², D²)
```

### 12.3 吸收前的 boundary tensor

```math
B[a,T,c]
```

典型形状：

```text
(chi_left, D², chi_right)
```

### 12.4 `absorb_row` 后

```math
B'[(a,L),B,(c,R)]
```

典型形状：

```text
(chi_left * D², D², chi_right * D²)
```

### 12.5 `compress_boundary!` 后

内部位置大致恢复为

```text
(≤chi, D², ≤chi)
```

### 12.6 最后一行后

底边界维数为 1，因此形状为

```text
(≤chi, 1, ≤chi)
```

### 12.7 `close_boundary` 后

```text
scalar
```

## 13. 用于范数和可观测量

### 13.1 范数

```julia
norm_result = boundary_mps_contract(state; chi)
```

得到

```math
N_\chi
\approx
\langle\psi|\psi\rangle.
```

### 13.2 单点期望值

在格点 `i` 插入 `O`：

```math
M_{O,\chi}
\approx
\langle\psi|O_i|\psi\rangle.
```

归一化后：

```math
\langle O_i\rangle_\chi
=
\frac{M_{O,\chi}}{N_\chi}.
```

### 13.3 两点乘积算符

在两个格点分别插入 `O₁` 和 `O₂`：

```math
\langle O_iO_j\rangle_\chi
=
\frac{
\operatorname{tTr}\left(E_i[O_i]E_j[O_j]\prod_{k\ne i,j}E_k[I]\right)
}{N_\chi}.
```

这些操作由 [`expectation_insertions`](observables.jl)、[`expectation_one_site`](observables.jl) 和 [`expectation_product_two_site`](observables.jl) 封装。

`metts_observables` 会先收缩一次范数并复用该分母，但每一个单点或两点分子当前仍会重新进行一次完整二维收缩。

## 14. 用于 METTS 顺序 collapse

设前 `k-1` 个格点已经抽到结果

```math
\sigma_1,\ldots,\sigma_{k-1},
```

累计投影为

```math
Q_{k-1}
=
\prod_{i<k}P_i^{(\sigma_i)}.
```

对当前格点尝试 `+` 和 `-`，需要计算两个联合权重：

```math
W_k(+)
=
\langle\psi|Q_{k-1}P_k^{(+)}|\psi\rangle,
```

```math
W_k(-)
=
\langle\psi|Q_{k-1}P_k^{(-)}|\psi\rangle.
```

`collapse_basis` 用 `insertions` 字典保存已经确定的投影：

```julia
insertions = Dict{CartesianIndex{2},Any}()
```

对当前点分别构造：

```julia
trial_positive = copy(insertions)
trial_positive[site] = projector_positive

trial_negative = copy(insertions)
trial_negative[site] = projector_negative
```

然后做两次完整 boundary-MPS 收缩：

```julia
positive_result = boundary_mps_contract(
    state; chi, insertions=trial_positive,
)

negative_result = boundary_mps_contract(
    state; chi, insertions=trial_negative,
)
```

条件概率取为

```math
p_k(+|\mathrm{history})
=
\frac{W_k(+)}{W_k(+)+W_k(-)},
```

```math
p_k(-|\mathrm{history})
=
\frac{W_k(-)}{W_k(+)+W_k(-)}.
```

抽样后只把被选中的投影写回 `insertions`，原 PEPS 张量不需要被逐点修改。

原因是不同格点投影彼此对易，而且局域投影满足

```math
P_i^2=P_i.
```

所以在原始 PEPS 双层网络中累计插入历史投影，等价于显式构造每一步测量后的归一化中间状态。

## 15. 有限 `chi` 下的概率处理

精确收缩时，由

```math
P_k^{(+)}+P_k^{(-)}=I
```

可知

```math
W_k(+)+W_k(-)=W_{k-1}.
```

但当前代码对 `+` 和 `-` 两个候选分别进行一次带 SVD 截断的完整收缩。有限 `chi` 下通常只有

```math
W_k^{(\chi)}(+)+W_k^{(\chi)}(-)
\approx
W_{k-1}^{(\chi)}.
```

因此程序不直接使用前一步权重作为分母，而是使用同一步两个候选权重之和重新归一化。这保证数值概率严格相加为 1。

如果数值误差产生舍入尺度内的微小负权重，`sanitize_probability_weights` 会将其截为零；如果出现显著负权重，则程序报错并提示增大 `chi`。

## 16. `D` 和 `chi` 控制不同误差

项目中有两个容易混淆的键维数：

- `D`：有限 PEPS 自身的虚拟键维数，控制 simple-update 虚时演化中的状态截断；
- `chi`：boundary MPS 的最大键维数，控制双层环境网络的收缩精度。

它们对应不同误差来源：

```math
\text{总误差}
=
\text{Trotter 误差}
+\text{simple-update/}D\text{ 截断误差}
+\text{boundary-MPS/}\chi\text{ 收缩误差}
+\text{METTS 统计误差}.
```

当前 boundary-MPS 环境只用于测量和 collapse，没有反馈到 simple update 中优化 PEPS 张量。因此当前算法不是 full update。

## 17. 精确极限和测试

当 `chi` 足够大，使所有 SVD 都不发生截断时，逐行吸收只是完整二维张量网络的精确重排，因此得到有限开放 PEPS 双层网络的精确收缩值。

项目测试对 `2×2` PEPS 显式构造完整波函数，并比较：

- PEPS 范数；
- 单点 `X` 期望值；
- 两点 `ZZ` 期望值。

测试位于 [`test/runtests.jl`](test/runtests.jl)，boundary-MPS 结果与精确波函数收缩达到约 `1e-12` 的相对精度。

实际计算中，应该固定 `D` 和 Trotter 步长，逐渐增加 `chi`，检查：

- 能量是否稳定；
- 磁化是否稳定；
- 长程关联函数是否稳定；
- collapse 条件概率是否稳定；
- `max_truncation_error` 是否足够小。

## 18. 当前实现的性能特点

当前实现每次调用 `boundary_mps_contract` 都会从第一行到最后一行重新收缩完整网络。

一次包含全部 `N=L_xL_y` 个格点的 METTS collapse 中，每个格点需要计算 `+`、`-` 两个候选，因此大约需要

```math
2L_xL_y
```

次完整二维双层网络收缩。

当前版本没有实现：

- 上、下 boundary MPS 缓存；
- 当前行左、右环境复用；
- zipper 式逐点更新；
- 显式构造单点约化密度矩阵后同时得到两个候选概率；
- 双向或变分 boundary-MPS 压缩；
- 将 boundary-MPS 环境反馈给虚时演化截断。

因此当前实现的主要优点是：

- 数学公式直接；
- 代码结构透明；
- 容易检查张量指标；
- 容易与小系统精确结果对照；
- 适合作为后续环境复用和高效 collapse 算法的基线。

主要缺点是不同观测量和 collapse 候选之间存在大量重复收缩。

## 19. 最终总结

当前项目利用 boundary-MPS 收缩有限 PEPS 环境的核心过程可以写成：

```math
\boxed{
\text{有限 PEPS}
\rightarrow
\text{局域双层张量}
\rightarrow
\text{逐行 transfer MPO}
\rightarrow
\text{boundary MPS}
\rightarrow
\text{逐行 SVD 截断到 }\chi
\rightarrow
\text{最终标量}
}
```

其中 boundary MPS 表示已经收缩完成的上方二维区域；它的物理腿是当前水平切口上的双层竖直虚腿。每吸收一行，环境信息向下推进一层；每次 SVD 截断则用最大键维数 `chi` 压缩该环境在水平方向携带的关联和纠缠信息。

最终标量根据局域双层张量中插入内容的不同，可以是：

- PEPS 范数；
- 单点或多点算符期望值的分子；
- METTS 顺序 collapse 中某个候选结果的联合 Born 权重。

因此，`boundary_mps.jl` 的本质任务就是：用一条可控键维数的 MPS，近似表示并逐步传播有限二维 PEPS 双层网络的环境。
