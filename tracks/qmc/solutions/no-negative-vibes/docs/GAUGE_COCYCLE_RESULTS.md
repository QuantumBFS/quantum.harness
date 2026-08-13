# 局域 gauge/cocycle 第一轮：消号成功，局域性失败

更新时间：2026-07-29

## 一句话结论

我们精确完成了候选清单中的四模式方环和六模式共边方环：

```text
GF(2) 费米符号抵消：成功
Gauss 约束与任意历史一致性：成功
固定大小的局域补偿：失败
```

在最朴素的 edge-electric `Z2` gauge ansatz 中，补偿相位只是把
Jordan--Wigner string 从物质占据数搬到了 gauge links。对 `2 x L` 梯子的中央竖边，
相位被迫读取其余全部 `L-1` 条竖边，作用半径随系统长度增长。

这关闭的是一个明确子候选，不是所有 modified-Gauss-law bosonization。

## 1. 我们实际测试的对象

在每条 hopping 边 `e` 上放一个 GF(2) link bit `a_e`，并施加

```text
n_v = q_v + sum_(e incident v) a_e mod 2.              (1)
```

费米子沿边 `e=(i,j)` 跳跃时：

```text
n_i -> n_i+1,
n_j -> n_j+1,
a_e -> a_e+1                                           (2)
```

全部按模 2 计算。(2) 自动保持两个端点的 Gauss 约束。

在固定 Fock 排序中，一次 hop 的矩阵元符号为

```text
(-1)^[sum_(i<r<j) n_r].                                (3)
```

我们寻找只依赖 link bits 的 affine phase

```text
(-1)^[c_e + sum_f h_(e,f) a_f]                         (4)
```

逐次抵消 (3)。

这比普通站点 `+/-` gauge 更强，因为 link bits 会随历史动态改变；但它仍比一般
exact bosonization 窄，因为 Gauss law 固定为 (1)，phase 限定为实 affine GF(2)
函数。

## 2. GF(2) 方程为什么能精确解

令 `S_e` 是 Fock 排序中两个端点之间的站点集合。把 (1) 代入 (3)：

```text
sum_(v in S_e) n_v
  = constant + sum_(f in boundary(S_e)) a_f mod 2.     (5)
```

所以补偿系数就是集合 `S_e` 的 edge boundary。它不是拟合或随机搜索，而是精确
GF(2) 解。

只在“恰有一个端点占据”的合法 hop 子空间上，可以再加一次 endpoint Gauss
constraint。代码比较这两个等价 affine 表达并选 locality radius 最小者。没有其他
link constraint 时，这已经穷尽全部 affine 解。

## 3. 最小方环与两个共边方环

### 一个方环：四模式、四条 link

穷举：

```text
gauge states                 16
legal transitions            32
fermion/gauge sign failures   0
Gauss-law failures            0
reverse/Hermiticity failures  0
```

消号完全成功，但一条竖边的 phase 需要两条其他 link，覆盖整个 plaquette，而不是
只使用被跳的 link。

### 两个共边方环：六模式、七条 link

穷举：

```text
gauge states                128
legal transitions           448
fermion/gauge sign failures   0
Gauss-law failures            0
reverse/Hermiticity failures  0
```

共享的中央竖边需要四个 link variables，其中包括左右两条外侧竖边。它已经同时读取
两个 plaquette。

深度 1–8 的闭合合法 histories 数为

```text
0, 448, 0, 3840, 0, 40768, 0, 480768.
```

每一步的 fermion sign 都被 gauge phase 精确抵消。因此问题不在历史深度，而在空间
support。

## 4. 一般 `2 x L` 梯子的严格障碍

采用 row-major Fock ordering，考虑第 `c` 列的竖边。两个端点之间的排序区间包含：

- `c` 右边的所有上排站点；
- `c` 左边的所有下排站点。

因此每一条其他竖边都恰有一个端点落入该区间。根据 (5)，补偿 phase 必然包含其余
全部 `L-1` 个 rung variables。

合法-hop constraint 只涉及目标端点附近的水平边，不能消掉这些远端 rung
variables。所以对中央竖边：

```text
rung variables in phase = L-1,
phase support            = L+1        (L>=3),
locality radius          = ceil((L-1)/2).
```

精确计数：

| `L` | link variables | phase support | rung variables | radius |
|---:|---:|---:|---:|---:|
| 2 | 4 | 2 | 1 | 1 |
| 3 | 7 | 4 | 2 | 1 |
| 4 | 10 | 5 | 3 | 2 |
| 5 | 13 | 6 | 4 | 2 |
| 6 | 16 | 7 | 5 | 3 |
| 7 | 19 | 8 | 6 | 3 |
| 8 | 22 | 9 | 7 | 4 |
| 9 | 25 | 10 | 8 | 4 |
| 10 | 28 | 11 | 9 | 5 |

这不是“小系统看起来不够好”，而是解析的线性增长。

## 5. 为什么不能偷偷固定 plaquette flux 来缩短 phase

在静态 GF(2) 方程中，若额外假设某些 plaquette parities 固定，可以用 plaquette
边界改写 (5)，有时把 support 搬回局部。

但 (2) 每次只翻转被 hop 的一条 link，它会改变相邻 plaquette parity。因此那些
静态约束并不被本 ansatz 的动力学保持，不能作为合法等价式使用。若要同时保持它们，
必须修改 Gauss law 或让一个 hop 翻转更多 gauge variables；那已经进入另一种
exact-bosonization 编码。

## 6. 文献边界：更聪明的局域 bosonization 已知，但不自动解决 QMC

二维 exact bosonization 确实可以通过更特殊的 gauge constraint，在保持 Hamiltonian
局域性的同时把费米系统映射到 lattice gauge theory：

- [Chen, Kapustin, Radicevic, 2018](https://arxiv.org/abs/1711.00515)；
- [Chen, 2020](https://arxiv.org/abs/1911.00017)。

这些工作同时说明，欧氏作用量会带 Chern--Simons-like 或 Steenrod-square
topological term。也就是说，“局域 fermion-to-qubit/gauge 映射存在”不等于
“每个 Monte Carlo 构型权重非负”。

进一步的二维分类结果认为，局域保持的 fermion-to-qubit mappings 在适当等价关系下
都可从 exact bosonization 产生：
[Chen and Xu, 2023](https://doi.org/10.1103/PRXQuantum.4.010326)。
因此仅发明另一种 gauge encoding 不是本挑战需要的新正性机制。

真正值得继续的对象必须额外给出：

```text
局域 projected transfer-matrix cone
+ 正系数 HS 可达性
+ 每个 gauge/auxiliary history 的非负权
+ 与已知 exact bosonization/stoquastic/Majorana 类的区别
```

## 7. 当前判定

第一版 edge-electric affine gauge/cocycle：

```text
状态：falsified as a scalable local mechanism
原因：精确消号需要 system-size Wilson string
```

保留的较窄开放问题：

```text
modified Gauss law + topological term
是否存在一个新的、逐构型非负的 projected semigroup cone？
```

但它的文献饱和度很高，且“表示局域”远弱于“QMC 正权”。在出现明确的正 transfer
matrix 候选前，不应把大量时间投入一般 gauge encoding。下一主线转到
non-induced exterior cone；本方向仅在能写出具体 projected cone/HS 时重开。

## 可执行证据

- `oracle/gauge_cocycle.py`
- `tests/test_gauge_cocycle.py`
- `fixtures/gauge_cocycle_certificates.json`
- `protocols/gauge-cocycle-ladder-v1/`
