# TN 路径类的新机制审计

更新时间：2026-07-28

## 结论

现在已经能验证一个比“扫描没发现负数”强得多的结论：

> 全非负（TN）路径类是一个严格成立的单行列式非负机制，并且整个矩阵类不可能通过固定
> 换基约化为 Kramers 配对、split-orthogonal 群、实收缩锥或 Wei 2024 的
> Majorana contraction-semigroup 条件。

这里的“新”是**相对于本挑战要求排除的已有 QMC 矩阵机制**，不是说全非负矩阵是新数学。
TN、Cauchy--Binet 和三对角 cooperative system 都是经典结果。

仍不能仅凭这一页宣称“文献史上首次发现”。目前的精确检索没有找到把 TN 半群直接作为
DQMC/AFQMC 逐构型充分条件的论文，但检索无命中不是首创证明。最终优先权判断仍需做引用链
审计，并请领域专家或出题人核对。

## 审计对象

令

```text
G_n = {A in R^(n x n):
       A is tridiagonal,
       A_(i,i+1) >= 0,
       A_(i+1,i) >= 0,
       A_(i,i) arbitrary}.
```

对任意 `A_l in G_n` 定义

```text
B_l = exp(A_l),
D   = B_1 ... B_L,
w   = det(I + D).
```

Schwarz 的全正微分系统定理给出每个 `B_l` 全非负；Cauchy--Binet 给出 TN 矩阵对乘法
封闭；主子式展开给出

```text
w = sum_S det D[S,S] >= 1.
```

所以恒正性已经是任意维数、任意深度的定理，不是数值存活结论。

## 排重结果表

| 已知解释 | 结果 | 核心证据 |
|---|---|---|
| split-orthogonal 固定度量 | 排除 | 类中同时含 `I` 与 `-I` |
| 实 contraction/expansion cone | 排除 | 同一固定度量不可能同时容纳 `I` 与 `-I` |
| 固定相似变换后的上述两类 | 排除 | `S I S^-1=I`，障碍不随换基消失 |
| Kramers `T^2=-1` | 排除 | 所有实对角矩阵的共同反幺正对称只能平方为正 |
| 偶 flavor 平方或共轭配对 | 排除 | 结论对单个行列式和奇数维数也成立 |
| Majorana reflection positivity | 排除整个类 | 它是 Wei 2024 对称 `J_1` 情形，而完整 Wei 条件已排除 |
| Wei 2024 contraction semigroup | 排除 | `+D/-D` 迫使收缩不等式为等式，逐站点反对易关系与 `J_2^2=-I` 矛盾 |
| 一维 Jordan--Wigner/worldline | 尚非矩阵约化；物理上邻近 | 解释开放链为何不意外，但不把 TN 矩阵定理变成上述固定度量/配对机制 |

## 证明 1：不存在固定 split 或实收缩度量

`G_n` 包含任意实对角矩阵，特别是 `I` 和 `-I`。

若存在固定非退化对称矩阵 `eta`，使每个生成元满足

```text
A^T eta + eta A = 0,
```

代入 `A=I` 立即得到 `2 eta=0`，矛盾。

若把等式放宽成某一固定方向的不等式

```text
A^T eta + eta A >= 0,
```

代入 `I` 得到 `eta>=0`，代入 `-I` 得到 `-eta>=0`，仍只能有 `eta=0`。反向不等式
完全相同。因此整个类既不在固定 contraction cone，也不在固定 expansion cone。

任何固定相似变换都保留 `+I/-I`，所以换基不能绕过这个障碍。

## 证明 2：不存在固定 Kramers 对称

设固定反幺正算符为 `T=U K`，其中 `K` 是复共轭，并要求 `T^2=-I`。如果它保护整个
`G_n`，就必须与其中每个实对角矩阵 `D` 对易。于是 `U` 与全部对角矩阵对易，故 `U`
本身只能是对角矩阵。

但

```text
T^2 = U conjugate(U)
```

的每个对角元都是正的 `|u_i|^2`；若 `U` 是幺正矩阵则恰为 `1`。它不可能等于 `-I`。
所以 TN 的正性不是 Kramers 简并或共轭谱配对。这个结论对固定复换基同样成立，因为可把
假设的反幺正对称拉回原基。

此外，TN 定理对奇数 `n` 和一个 determinant 已经成立，不能解释成两个 flavor 的平方。

## 证明 3：排除 Wei 2024 条件，包括固定复正交换基

Wei 2024 对复反对称 Majorana 系数矩阵 `M` 的条件包含

```text
i (J_2 M - conjugate(M) J_2) <= 0,                 (W)
```

其中固定的 `J_2` 是实、正交、反对称矩阵，因此 `J_2^2=-I`。论文还允许先做一个固定
复正交换基。

只需看 TN 类中的实对角子类

```text
D = diag(d_1, ..., d_n).
```

在逐站点排列的 `2n` 个 Majorana 基中，忽略不影响符号的标量 `trace(D)/2`，相应系数为

```text
M(D) = i direct_sum_j (d_j J),
J    = [[0, 1], [-1, 0]].
```

假设存在固定复正交矩阵 `Q`，使

```text
M'(D) = Q^T M(D) Q
```

对全部 `D` 满足 `(W)`。因为 `D` 与 `-D` 都允许，`(W)` 的左端及其负数都必须半负定，
故它只能恒等于零。

利用 `conjugate(M(D))=-M(D)`，并定义

```text
K = conjugate(Q) J_2 Q^T,
```

可把这个等式拉回为

```text
K M(D) + M(D) K = 0
```

对每个实对角 `D` 都成立。逐个只打开一个 `d_j`，立刻得到：

1. `K` 的所有站点间 `2 x 2` 块都为零；
2. 每个站点内块必须具有

```text
X_j = [[a_j, b_j],
       [b_j,-a_j]].
```

另一方面，`Q^T Q=I` 和 `J_2^2=-I` 给出

```text
K conjugate(K) = -I.
```

可是任意上述局部块都有

```text
[X_j conjugate(X_j)]_(1,1) = |a_j|^2 + |b_j|^2 >= 0,
```

不可能等于 `-1`。矛盾。

因此，不只是标准实 Majorana 基：**任何固定复正交换基之后，完整 TN 类仍不属于
Wei 2024 的两个 sign-free semigroups**。由于证明只使用 Wei 条件中的 `J_2` 不等式，
无需再为不存在的 `J_2` 检查 `J_1`。

`oracle/tn_novelty.py` 和 `tests/test_tn_novelty.py` 用精确整数/SymPy 回归了共同反对易空间：
其复维数恰为 `2n`，且只由每个站点的上述 `X/Z` 两个方向组成。

## “新机制”现在可以说到哪一步

可以说：

```text
我们得到一个经典 TN 理论诱导的、新于挑战所列固定度量和配对条件的
determinantal-QMC 矩阵充分条件。
```

暂时不要说：

```text
我们首次发现了一个新的无符号物理模型。
```

原因是矩阵机制的新颖性与物理模型的新颖性是两关：

1. **矩阵关：** 正确性已证明，挑战列出的主要已知机制已代数排除；
2. **文献关：** 精确关键词检索无直接命中，但尚未完成全引用链和专家核对；
3. **物理关：** 已有 Hubbard 与单 flavor `t-V` 开链基线，但开放一维本身有已知无符号
   解释；还需找到超出普通开链的 HS 可达子类。

这正好符合先确认矩阵类、再映射物理模型的推进顺序。下一步不是继续盲扫 TN 本身，而是：

1. 把本证明交给合作者或出题人检查，尤其核对 Majorana 约定；
2. 完成 TN/DQMC 的引用链排重；
3. 从 TN 的正双对角和平面网络分解寻找不等价于普通一维开链的 HS 实现；
4. 若物理映射始终退化为一维非交叉世界线，就把本结果定位为新矩阵表述与边界定理，再
   搜索比 TN 更大的乘法半群。

## 主要来源

- [挑战 issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121)
- [Wei, Semigroup approach, PRB 110, 075146 (2024)](https://arxiv.org/abs/1712.09412)
- [Margaliot and Sontag, totally positive differential systems](https://arxiv.org/abs/1802.09590)
- [Wei et al., Majorana positivity (2016)](https://arxiv.org/abs/1601.01994)
