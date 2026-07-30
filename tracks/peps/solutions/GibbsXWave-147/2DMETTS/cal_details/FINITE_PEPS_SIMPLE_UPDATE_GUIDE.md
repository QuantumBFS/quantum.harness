# 有限大 PEPS 的 Simple Update 详解

本文结合本项目的实际代码，详细说明如何对有限开放边界 PEPS 做 simple update，以及 [`simple_update.jl`](simple_update.jl) 中各个函数在虚时演化中的作用。

相关文件包括：

- [`simple_update.jl`](simple_update.jl)：单键更新、Trotter 扫描和完整虚时演化；
- [`state.jl`](state.jl)：有限 Γ–Λ PEPS、键谱乘除和普通有限 PEPS 转换；
- [`model.jl`](model.jl)：有限 OBC 键 Hamiltonian 和两体 Trotter 门；
- [`metts.jl`](metts.jl)：建立乘积 PEPS 并调用 simple update。

## 1. Simple update 的任务

每个 METTS 样本从乘积态 `|φᵢ⟩` 出发，需要近似计算

```math
|\psi_i\rangle\propto e^{-\beta H/2}|\phi_i\rangle.
```

程序用 Suzuki–Trotter 分解把 `exp(-βH/2)` 拆成许多两体虚时门，再逐条水平键和竖直键作用这些门。两体门会增加纠缠和虚拟键维数，所以每次作用门后立即做 SVD，只保留最大的 `D` 个奇异值。

调用关系为：

```text
imaginary_time_evolve!
    └── apply_trotter_step!
            ├── update_horizontal_bond!
            │       └── normalized_singular_values
            └── update_vertical_bond!
                    └── normalized_singular_values
```

## 2. 有限 Γ–Λ PEPS

每个格点保存一个五阶 `Γ` 张量和四条对角键谱：

```julia
mutable struct DenseGammaLambdaSite{T<:Number}
    gamma::Array{T,5}
    left::Vector{Float64}
    top::Vector{Float64}
    right::Vector{Float64}
    bottom::Vector{Float64}
end
```

`gamma` 的固定指标顺序是：

```text
(left, top, physical, right, bottom),
```

即 `Γ[l,t,s,r,b]`。四个向量表示 `Λl, Λt, Λr, Λb`。

相邻站点在同一内部键上保存相同的谱：

```julia
state[x, y].right == state[x + 1, y].left
state[x, y].bottom == state[x, y + 1].top
```

有限 PEPS 使用开放边界，不存在外部邻居的虚拟腿维数为 1：

```math
x=1\Rightarrow D_l=1,\quad x=L_x\Rightarrow D_r=1,
```

```math
y=1\Rightarrow D_t=1,\quad y=L_y\Rightarrow D_b=1.
```

每个格点仍统一保留五个指标，因此角点、边界点和体内点使用同一套更新代码。

## 3. 从乘积态开始

每次 METTS 转移首先调用：

```julia
gamma_lambda_state = product_peps(configuration; basis=product_basis)
```

每个站点的初始形状为：

```text
(1, 1, 2, 1, 1).
```

四条键谱均为 `ones(1)`，所以初始内部键维数为 1，状态没有格点间纠缠。之后虚时门逐渐产生纠缠，SVD 产生的新内部键维数始终截断到不超过 `D`。

## 4. Simple update 的环境近似

严格优化门作用后的两点张量需要考虑其余整个二维 PEPS 的环境。simple update 不收缩这个完整环境，而是用两个目标站点周围的对角键谱近似它：

```math
\text{完整二维环境}
\quad\longrightarrow\quad
\text{相邻外腿上的对角 }\Lambda.
```

因此一次局域更新只需要：

1. 两个站点的 `Γ`；
2. 两站点周围的外腿 `Λ`；
3. 两站点之间的目标键谱；
4. 当前键上的两体 Trotter 门。

本项目的 boundary-MPS 只用于后续测量和 collapse，不反馈到 SU 截断，所以当前实现不是 full update。

## 5. `normalized_singular_values`

```julia
function normalized_singular_values(values::AbstractVector)
    normalization = norm(values)
    normalization > 0 || error("two-site update produced a zero state")
    return collect(real(values ./ normalization)), normalization
end
```

设 SVD 截断后保留的奇异值为 `s₁,…,sD`。函数计算

```math
n=\|s\|_2=\sqrt{\sum_\alpha s_\alpha^2},
```

并生成归一化的新键谱

```math
\lambda_\alpha'=\frac{s_\alpha}{n},
\qquad
\sum_\alpha(\lambda_\alpha')^2=1.
```

返回值为：

- `normalized_values`：新的目标键谱；
- `normalization`：被剥离的局域整体尺度。

虚时门不是幺正门，连续作用会改变波函数范数。归一化键谱可避免张量数值指数增大或减小。若所有保留奇异值均为零，则两点状态是零张量，函数直接报错。

## 6. 水平键更新 `update_horizontal_bond!`

函数更新水平相邻格点

```math
A=(x,y),\qquad B=(x+1,y).
```

签名为：

```julia
function update_horizontal_bond!(
    state::DenseFinitePEPSGammaLambda,
    x::Int,
    y::Int,
    max_bond_dimension::Int,
    gate::Array{<:Number,4},
)
```

`!` 表示函数原地修改 `state`。

### 6.1 取出目标站点

```julia
left = state[x, y]
right = state[x + 1, y]
```

局部结构为：

```text
             ΛtA                    ΛtB
              |                      |
ΛlA —— ΓA —— ΛAB —— ΓB —— ΛrB
              |                      |
             ΛbA                    ΛbB
```

目标键是 `left.right` 和 `right.left` 表示的 `ΛAB`。

### 6.2 吸收左张量的键谱

```julia
left_tensor = multiply_leg(left.gamma, left.left, 1)
left_tensor = multiply_leg(left_tensor, left.top, 2)
left_tensor = multiply_leg(left_tensor, left.bottom, 5)
left_tensor = multiply_leg(left_tensor, left.right, 4)
```

相当于

```math
\widetilde\Gamma_A
=\Lambda_{l_A}\Lambda_{t_A}\Lambda_{b_A}
\Gamma_A\Lambda_{AB}.
```

数字 `1,2,4,5` 对应 `left, top, right, bottom` 腿；第 3 腿是物理腿。

### 6.3 吸收右张量的外部键谱

```julia
right_tensor = multiply_leg(right.gamma, right.top, 2)
right_tensor = multiply_leg(right_tensor, right.right, 4)
right_tensor = multiply_leg(right_tensor, right.bottom, 5)
```

即

```math
\widetilde\Gamma_B
=\Lambda_{t_B}\Gamma_B\Lambda_{r_B}\Lambda_{b_B}.
```

这里不乘 `right.left`，因为它与 `left.right` 是同一条目标谱的两个副本。目标 `ΛAB` 只能在两点波函数中出现一次，否则会错误地得到 `ΛAB²`。

### 6.4 作用两体门并收缩目标键

```julia
@tensor theta[l, t1, b1, p1, p2, t2, r, b2] :=
    left_tensor[l, t1, q1, bond, b1] *
    right_tensor[bond, t2, q2, r, b2] *
    gate[p1, p2, q1, q2]
```

其中：

- `bond` 是旧的目标虚拟键；
- `q1,q2` 是门作用前的物理指标；
- `p1,p2` 是门作用后的物理指标。

数学上：

```math
\Theta^{p_1p_2}
=\sum_{q_1q_2,\alpha}
G^{p_1p_2}_{q_1q_2}
\widetilde\Gamma_A^{q_1,\alpha}
\widetilde\Gamma_B^{q_2,\alpha}.
```

`theta` 的指标顺序是：

```text
(l, t1, b1, p1, p2, t2, r, b2).
```

### 6.5 重组为矩阵并做 SVD

```julia
left_dims = size(theta)[1:4]
right_dims = size(theta)[5:8]
factorization = svd(reshape(theta, prod(left_dims), prod(right_dims)))
```

左右复合指标为：

```math
L=(l,t_1,b_1,p_1),\qquad R=(p_2,t_2,r,b_2).
```

因此

```math
\Theta_{L,R}=USV^\dagger.
```

SVD 的奇异值指标成为更新后的水平虚拟键。

### 6.6 截断到最大键维数 D

```julia
kept = min(max_bond_dimension, length(factorization.S))
```

即

```math
D_{\rm keep}=\min(D,N_S).
```

`D` 是上限，实际键维数可能小于 `D`。

截断误差为：

```julia
discarded = sum(abs2, @view factorization.S[(kept + 1):end])
total = sum(abs2, factorization.S)
truncation_error = total == 0 ? 0.0 : discarded / total
```

即

```math
\epsilon_D
=\frac{\sum_{\alpha>D_{\rm keep}}s_\alpha^2}
       {\sum_\alpha s_\alpha^2}.
```

这是当前两点 SVD 的局域丢弃权重，不是整个 PEPS 的全局波函数误差或能量误差。

### 6.7 构造新目标键谱

```julia
singular_values, normalization = normalized_singular_values(
    @view factorization.S[1:kept],
)
```

所以

```math
\Lambda_{AB}'=\frac{S_{\rm kept}}{\|S_{\rm kept}\|_2}.
```

### 6.8 从 U 恢复左 Γ

```julia
new_left = reshape(
    @view(factorization.U[:, 1:kept]),
    left_dims...,
    kept,
)
```

此时顺序为：

```text
(l, t1, b1, p1, new_bond).
```

执行

```julia
new_left = permutedims(new_left, (1, 2, 4, 5, 3))
```

得到标准顺序：

```text
(l, t1, p1, new_bond, b1)
= (left, top, physical, right, bottom).
```

然后除掉此前吸收的外腿谱：

```julia
new_left = remove_leg_weight(new_left, left.left, 1)
new_left = remove_leg_weight(new_left, left.top, 2)
new_left = remove_leg_weight(new_left, left.bottom, 5)
```

即

```math
\Gamma_A'
=\Lambda_{l_A}^{-1}\Lambda_{t_A}^{-1}\Lambda_{b_A}^{-1}U.
```

不除新目标谱，因为它会单独保存为 `left.right`。

### 6.9 从 V† 恢复右 Γ

```julia
new_right = reshape(
    @view(factorization.Vt[1:kept, :]),
    kept,
    right_dims...,
)
```

初始顺序为：

```text
(new_bond, p2, t2, r, b2).
```

经过

```julia
new_right = permutedims(new_right, (1, 3, 2, 4, 5))
```

变成标准顺序：

```text
(new_bond, t2, p2, r, b2).
```

再移除右站点的外部谱：

```julia
new_right = remove_leg_weight(new_right, right.top, 2)
new_right = remove_leg_weight(new_right, right.right, 4)
new_right = remove_leg_weight(new_right, right.bottom, 5)
```

### 6.10 写回更新结果

```julia
left.gamma = Array(new_left)
right.gamma = Array(new_right)
left.right = singular_values
right.left = singular_values
```

更新后的局部网络重新写成

```math
\Gamma_A'\Lambda_{AB}'\Gamma_B'.
```

函数返回：

```julia
return truncation_error, normalization
```

## 7. 竖直键更新 `update_vertical_bond!`

该函数更新

```math
A=(x,y),\qquad B=(x,y+1),
```

即 `upper` 和 `lower` 两个站点。算法与水平更新相同，区别主要是指标排列。

上张量吸收 `left/top/right` 外谱和目标 `bottom` 谱；下张量吸收 `left/right/bottom` 外谱，不再乘与目标谱重复的 `lower.top`。

两点张量为：

```julia
@tensor theta[l1, t, r1, p1, p2, l2, r2, b] :=
    upper_tensor[l1, t, q1, r1, bond] *
    lower_tensor[l2, bond, q2, r2, b] *
    gate[p1, p2, q1, q2]
```

SVD 划分为：

```text
(l1, t, r1, p1 | p2, l2, r2, b).
```

`U` reshape 后通过

```julia
permutedims(new_upper, (1, 2, 4, 3, 5))
```

变成

```text
(l1, t, p1, r1, new_bond),
```

所以新键是上张量的 `bottom` 腿。

`Vt` reshape 后通过

```julia
permutedims(new_lower, (3, 1, 2, 4, 5))
```

变成

```text
(l2, new_bond, p2, r2, b),
```

所以新键是下张量的 `top` 腿。最后同步写入：

```julia
upper.bottom = singular_values
lower.top = singular_values
```

## 8. 键谱辅助函数

### 8.1 `multiply_leg`

`multiply_leg(tensor, weights, leg)` 沿指定张量腿乘一个对角权重。例如沿右腿：

```math
A'_{l,t,s,r,b}=A_{l,t,s,r,b}\Lambda_r(r).
```

函数首先检查该腿的维数是否等于键谱长度。

### 8.2 `remove_leg_weight`

`remove_leg_weight(tensor, weights, leg)` 用于除掉此前吸收的外腿键谱。它使用带 `cutoff=1e-12` 的伪逆：

```math
\Lambda^{-1}(\alpha)=
\begin{cases}
1/\Lambda(\alpha),&|\Lambda(\alpha)|>\epsilon,\\
0,&|\Lambda(\alpha)|\le\epsilon.
\end{cases}
```

这样可以避免除以接近零的奇异值导致张量元素爆炸。

## 9. 完整时间步 `apply_trotter_step!`

该函数在整个有限方格上完成一个长度为 `delta` 的 Trotter 时间步。

### 9.1 阶数和门时间

```julia
order = get(para, :TrotterOrder, 2)
D = para[:D]
gate_delta = order == 1 ? delta : delta / 2
```

- 一阶：每条键作用一次 `G(delta)`；
- 二阶：每条键正向、反向各作用一次 `G(delta/2)`。

### 9.2 构造有限 OBC 的全部门

```julia
horizontal_gates = [
    trotter_gate(state.Lx, state.Ly, x, y, :right, gate_delta, para)
    for x in 1:(state.Lx - 1), y in 1:state.Ly
]
```

```julia
vertical_gates = [
    trotter_gate(state.Lx, state.Ly, x, y, :down, gate_delta, para)
    for x in 1:state.Lx, y in 1:(state.Ly - 1)
]
```

有限 OBC 中不同位置端点的配位数不同，键 Hamiltonian 中分配到的横场系数也可能不同，所以程序为每条键分别构造门。

### 9.3 正向和反向扫描

正向扫描顺序为：

1. 水平键逐行从左到右；
2. 竖直键逐列从上到下。

二阶情况下再执行：

3. 竖直键逐列从下到上；
4. 水平键逐行从右到左。

因此局域门序列为回文形式：

```math
g_1(\delta/2)\cdots g_M(\delta/2)
g_M(\delta/2)\cdots g_1(\delta/2).
```

忽略有限 `D` 截断时，对称分解的单步误差是 `O(delta³)`，固定总虚时间后的累计误差是 `O(delta²)`。

### 9.4 数值诊断

每条键更新后执行：

```julia
max_error = max(max_error, error)
log_normalization += log(normalization)
```

返回：

```julia
(;
    max_truncation_error=max_error,
    log_normalization,
)
```

`max_truncation_error` 是该时间步内最严重的一次局域截断，不是所有误差的总和。

## 10. 完整虚时演化 `imaginary_time_evolve!`

这是 `simple_update.jl` 的最高层入口。

### 10.1 目标虚时间

METTS 使用

```math
|\psi_i\rangle\propto e^{-\beta H/2}|\phi_i\rangle,
```

所以代码设置：

```julia
target_time = beta / 2
```

当 `beta == 0` 时不需要作用任何门，直接返回空历史。

### 10.2 实际时间步

```julia
steps = max(1, ceil(Int, target_time / requested_tau))
delta = target_time / steps
```

即

```math
N_\tau=\max\left(1,\left\lceil\frac{\beta/2}{\tau}\right\rceil\right),
\qquad
\delta=\frac{\beta/2}{N_\tau}.
```

实际 `delta` 可能略小于用户输入的 `tau`，但严格满足

```math
N_\tau\delta=\beta/2.
```

### 10.3 重复 Trotter 步

```julia
for step in 1:steps
    update = apply_trotter_step!(state, delta, para)
    push!(history, (; step, steps, delta, update...))
end
```

`state` 被原地更新；返回的 `history` 是诊断记录，每项包含：

```text
step
steps
delta
max_truncation_error
log_normalization
```

## 11. 转成普通有限 PEPS

SU 演化结束后，程序调用：

```julia
peps = DenseFinitePEPS(gamma_lambda_state)
```

转换规则是把每条键谱的平方根平均分配给两端：

```math
A_{x,y}
=\Gamma_{x,y}
\sqrt{\Lambda_l}\sqrt{\Lambda_t}
\sqrt{\Lambda_r}\sqrt{\Lambda_b}.
```

同一内部键的两个 `sqrt(Λ)` 收缩时恢复完整的 `Λ`：

```math
\sqrt\Lambda\sqrt\Lambda=\Lambda.
```

普通有限 PEPS 随后交给 boundary-MPS，用于范数、观测量和 METTS collapse 条件概率的计算。

## 12. 完整算法流程

```text
乘积态 configuration
        │
        ▼
product_peps：有限 Γ–Λ PEPS，初始 D=1
        │
        ▼
确定 target_time=beta/2 和实际 delta
        │
        ▼
为有限 OBC 每条键构造两体虚时门
        │
        ▼
水平正向 → 竖直正向 → 竖直反向 → 水平反向
        │
        ▼
每条键：吸收 Λ → 作用门 → SVD → 截断到 D
        │
        ▼
更新两个 Γ 和共享目标 Λ
        │
        ▼
重复时间步直到总虚时间 beta/2
        │
        ▼
将 sqrt(Λ) 平均吸入相邻 Γ
        │
        ▼
普通有限 PEPS，用于 boundary-MPS 收缩
```

## 13. 误差来源

### 13.1 Trotter 误差

由 `tau` 或实际 `delta` 控制。默认二阶方案在忽略截断时，固定总虚时间的误差约为 `O(delta²)`。

### 13.2 有限 D 截断误差

由 PEPS 最大虚拟键维数 `D` 控制。每次单键更新记录丢弃奇异值的相对平方权重。增加 `D` 可以保留更多纠缠，但会增加计算和内存成本。

### 13.3 Simple-update 环境误差

SU 只用周围对角键谱近似完整二维环境。即使 `D` 足够大、`tau` 足够小，这个局域环境近似仍可能造成系统误差。

### 13.4 Boundary-MPS 收缩误差

`chi` 控制测量和 collapse 时的 boundary-MPS 收缩精度，但不会反馈修正 SU 张量，因此增大 `chi` 不能恢复 SU 阶段已经丢弃的纠缠。

## 14. 重要实现细节

1. **目标键谱只吸收一次。** 水平更新乘 `left.right` 而不乘 `right.left`；竖直更新乘 `upper.bottom` 而不乘 `lower.top`。
2. **外谱在 SVD 后必须移除。** 外部 `Λ` 用来近似环境，新 `Γ` 中不能重复包含它们。
3. **奇异值单独保存。** 代码保留 `U S V†` 结构，把归一化后的 `S` 保存成新 `Λ`，而不是把 `sqrt(S)` 分别乘进两端 Γ。
4. **局域归一化只改变整体尺度。** 观测量和 collapse 概率均由分子、分母比值计算，整体 PEPS 标量会消去。
5. **有限 D 下存在扫描顺序依赖。** 不同门一般不对易，且每次门后立即截断；二阶回文扫描减弱时间离散的方向不对称，但不能完全消除截断带来的顺序影响。

## 15. 总结

本项目对有限 PEPS 做 simple update 的核心步骤是：

1. 用 Γ–Λ 形式保存有限开放边界 PEPS；
2. 从 `D=1` 的乘积态开始；
3. 为每条有限 OBC 最近邻键构造两体虚时门；
4. 将目标两点周围的外腿键谱吸入 Γ，以此近似二维环境；
5. 收缩两个站点并作用门，得到更新后的两点张量 `Theta`；
6. 按两个站点划分复合指标，对 `Theta` 做 SVD；
7. 只保留最大的 `D` 个奇异值并记录丢弃权重；
8. 将归一化奇异值保存为新的共享目标键谱；
9. 从 `U`、`V†` 中移除外腿谱，恢复新的两个 Γ；
10. 用二阶正向—反向扫描覆盖全部水平键和竖直键；
11. 重复时间步直到总虚时间达到 `beta/2`；
12. 最后把 `sqrt(Λ)` 平均吸收到相邻 Γ，得到用于测量和 collapse 的普通有限 PEPS。
