# TN 平面网络的精确物理顶点与 stoquastic 边界

日期：2026-07-28

## 结论先行

本轮从 TN 的 elementary Jacobi 因子得到一个完整的算符级逆 HS 结果：

- 四个可逆 TN 单粒子矩阵的等正权和，精确等于一个三站点 Hermitian
  相互作用顶点；
- 顶点包含真正的四费米 density-assisted hopping；
- 它可在开放有序链的重叠三站点上任意铺设，任意辅助场历史的单
  determinant 权重严格为正；
- 三个物理耦合可独立取任意正值；
- 但 Jordan--Wigner 变换把它精确送到无挫折的 hard-core-boson /
  ferromagnetic XY hopping，因此它不是新的“隐藏无符号”物理类。

所以本轮同时完成了两件事：

1. TN 确实可以从矩阵机制反推出局域、相互作用、可采样的物理模型；
2. 固定 Fock 基、正标量 TN Gaussian 正和本身有一个一般
   stoquastic 边界，不能靠继续扩大这种正和搜索得到真正非
   stoquastic 的新 Hamiltonian 类。

## 四场精确恒等式

在三个连续排序的模式上定义

```text
x_01(a) = I + a E_01,
x_12(b) = I + b E_12,                   a,b > 0,

X = x_01(a) x_12(b),
Y = x_12(b) x_01(a).
```

elementary Jacobi shear 是 TN；TN 对乘法和转置封闭，所以

```text
X, Y, X^T, Y^T
```

全部是可逆 TN 矩阵。记数守恒 Gaussian/Fock lift 为
`Gaussian(B)`。因为

```text
Gaussian(I + a E_ij) = 1 + a c_i^dag c_j
```

以及 Gaussian lift 保持乘法，

```text
Gaussian(X) + Gaussian(Y)
  = 2 + 2a c_0^dag c_1 + 2b c_1^dag c_2
      + ab c_0^dag (1-2n_1) c_2.
```

再加转置场，得到 Hermitian 恒等式

```text
Q_012 =
    Gaussian(X) + Gaussian(Y)
  + Gaussian(X^T) + Gaussian(Y^T)

  = 4
  + 2a (c_0^dag c_1 + h.c.)
  + 2b (c_1^dag c_2 + h.c.)
  + ab [c_0^dag (1-2n_1)c_2 + h.c.].        (*)
```

`oracle/tn_network_hs.py` 用两种独立方式构造等式两边：

1. 从 `X,Y,X^T,Y^T` 的全部子式生成完整 `8 x 8` Fock 矩阵；
2. 从显式 Jordan--Wigner `c_i` 矩阵生成右边的物理算符。

多个非退化参数点逐矩阵元相等。

## 对应的局域 Hamiltonian

取任意 `g>0`，定义连续时间 interaction-expansion 顶点

```text
-v_012 = (g/4) Q_012
       = sum_(s=1)^4 (g/4) Gaussian(B_s).
```

去掉不影响本征态和观测量的常数 `-g` 后，

```text
v_012 ~
  -t_L (c_0^dag c_1 + h.c.)
  -t_R (c_1^dag c_2 + h.c.)
  -J [c_0^dag (1-2n_1)c_2 + h.c.],

t_L = ga/2,
t_R = gb/2,
J   = gab/4.
```

这三个正耦合没有隐藏约束。给定任意

```text
t_L > 0, t_R > 0, J > 0,
```

可取

```text
g = t_L t_R / J,
a = 2J / t_R,
b = 2J / t_L.
```

因此 `(*)` 不是一个只能落在微小参数曲线上的特殊点，而覆盖全部
ferromagnetic-sign 三耦合正象限。

在长链上可把 `v_(i,i+1,i+2)` 平移到所有连续三站点并相加。还可加入：

- 任意化学势；
- TN-compatible 的额外开放路径 hopping；
- 由正对角 HS 场产生的有限程 density-density interaction。

得到的是一个可调、局域、单 flavor、单 determinant 的相互作用费米
模型。

## 为什么任意历史都无符号

一次顶点插入从四个 TN 矩阵中选一个，标量系数恒为 `g/4>0`。把
`3 x 3` TN 矩阵嵌入一个更长矩阵的连续主块，相当于与左右单位块作
有序直和，仍为 TN。

任意重叠顶点和任意 TN-compatible 自由传播的时间序乘积 `D_C` 仍是
TN。因此

```text
det(I + D_C)
  = sum_(S subset sites) det D_C[S,S]
  >= 1.
```

完整构型权重为

```text
W_C = (g/4)^k det(I+D_C) > 0.
```

代码穷举了一个五站点、四个重叠顶点的全部 `4^4=256` 条短历史；
这只是实现回归，一般结论来自 TN 乘法闭包和主子式恒等式。

## 它是什么物理模型

令 `P_1=1-2n_1`。Jordan--Wigner 变换给出

```text
c_0^dag P_1 c_2 + h.c.
    <--> b_0^dag b_2 + h.c.
```

其中 `b_i` 是 hard-core boson/spin lowering operator。普通最近邻
fermion hopping 同样映到 hard-core-boson 最近邻 hopping。所以
`(*)` 精确等价于一个带最近邻和次近邻 XY exchange 的自旋链局域
顶点。

这不是形式上的猜测：测试在完整八维局域 Hilbert 空间逐矩阵元验证了
fermion parity-string 顶点与 hard-core-boson 顶点完全相等。

这类模型是有实际多体内容的。次近邻 XY exchange 经 Jordan--Wigner
会产生 ordinary next-neighbor hopping 与 density-assisted hopping
的固定组合；这一标准映射可直接对照
[Verkholyak, Honecker and Brenig, 2006, Eq. (2)](
https://arxiv.org/abs/cond-mat/0505654)。density-dependent hopping
本身也广泛出现在一维 anyon 和受约束动力学模型中，例如
[Kwan et al., 2020](https://www.nature.com/articles/s42005-020-0364-9)。

但我们这里所有 XY hopping 都取 ferromagnetic/stoquastic 符号，所以
没有覆盖反铁磁 `J_1-J_2` 竞争导致的 frustrated 区域。

## 一般边界：正 TN Gaussian 正和必然 stoquastic

本例暴露出一个不依赖三站点细节的一般命题。

若局域连续时间顶点满足

```text
-v = sum_s p_s Gaussian(B_s),
p_s >= 0,
B_s TN
```

且使用固定的有序 Fock 基，则：

1. `Gaussian(B_s)` 的每个固定粒子数扇区矩阵元是 `B_s` 的一个子式；
2. TN 定义保证这些矩阵元全部非负；
3. 正系数求和后 `-v` 仍逐元非负；
4. 因而 `v` 的所有非对角矩阵元非正。

也就是说，这种物理 Hamiltonian 顶点在同一个 Fock 基中已经
stoquastic。若自由部分也来自 TN 连续生成元，则完整 Hamiltonian
同样 stoquastic。

所以此前的

```text
G_physical = sum_s p_s Gaussian(B_s),
p_s >= 0, B_s TN
```

不应继续被当作寻找“隐藏的 fermion-only sign-free Hamiltonian”的
无限搜索空间。它适合：

- 构造精确 determinant 算法；
- 设计 correlated-hopping / hard-core-boson 物理模型；
- 优化不同 HS 表示的数值性能；
- 给出 fixed-basis 正表示的严格边界。

若目标是超越 worldline/SSE 已显然无符号的模型，至少要放宽一项：

- 允许 scalar sign 与一个可乘的 matrix grade 抵消；
- 使用时间边界上 telescope 的 moving frame/groupoid；
- 改变 Hilbert 空间、引入非平凡 gauge constraint；
- 转到 pairing/Pfaffian/Spin 表示。

这正是王磊 split-orthogonal 工作中 constant shift、群分支和完整权重
抵消提供的教训。

## 结果定位

| 层次 | 本轮状态 |
|---|---|
| 三站点算符恒等式 | 精确完成 |
| 每个辅助场 TN | 全部子式验证，并有 Jacobi 乘法证明 |
| 任意历史正性 | 一般证明 |
| 局域 Hermitian Hamiltonian | 完成 |
| 是否真实含相互作用 | 是，含 density-assisted hopping |
| 物理可调性 | 三个正耦合可独立指定 |
| 是否新 sign-free 机制 | 否，仍是 TN |
| 是否隐藏非-stoquastic 模型 | 否，精确约化到 ferromagnetic XY/hard-core boson |
| 文献史首创 | 不主张 |

这是一项有价值的正结果和边界结果，但不是挑战最终需要的“新且非平凡
物理类”。四模式 pair-hopping 的纯正 TN 正和也受同一 stoquastic
命题限制，因此本分支不再盲目扩大此类枚举。

## 可执行证据

- `oracle/tn_network_hs.py`
  - Jacobi/TN 四场；
  - Gaussian/Fock lift；
  - 解析 parity-string 顶点；
  - hard-core-boson 映射；
  - 重叠历史权重。
- `tests/test_tn_network_hs.py`
  - 完整 Fock 恒等式；
  - 全部子式；
  - Hermiticity 与 stoquasticity；
  - Jordan--Wigner 等价；
  - `4^4` 条重叠历史。
