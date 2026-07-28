# Graded monomial crossing：首轮结果

日期：2026-07-28

## 一句话结果

我们找到了纯 TN 之外的一个严格正性机制：

> 允许单粒子网络出现 permutation crossing，并让每个 crossing 携带它的置换奇偶
> 标量符号，则这个符号会在任意长历史中精确抵消 determinant 的符号。

它反推出一个局域、Hermitian、真正含相互作用的 spinless-fermion 模型；在三角形等
奇环上，该模型不能靠站点 `+/-` gauge 变成固定 Fock 基 stoquastic hopping。

这已经是 `physical-candidate`，但不是 `challenge-ready`：`r=1` 边界与 graded
permutation / `su(1|1)` 模型有关，符号重组也与 meron/loop 思想相邻，文献优先权和
已知机制排重尚未完成。

## 最直观的理解

TN 网络不允许线交叉，所以每个子式都非负。我们现在允许两根线交换一次。一次交换会
带来一个负号：

```text
crossing parity = -1.
```

若历史里交换了 `k` 次，所有交换合成后的置换奇偶性就是 `(-1)^k`。另一方面，这类
矩阵的 `det(I+B)` 也恰好有同一个符号。连续时间展开本来每插入一次 Hamiltonian
顶点就有一个负号，所以

```text
Taylor sign * determinant sign
  = (-1)^k * (-1)^k
  = +1.
```

这不是先算出负权再取绝对值，而是每个构型的两个符号解析地逐一相消。

## 一般定理

考虑正 monomial 矩阵

```text
B = P diag(d_1,...,d_n),       d_i >= 1,
chi(B) = sgn(P).
```

这类矩阵对乘法封闭，`chi` 也是乘法同态。把 `P` 写成不交循环。一个长度为 `ell`
的循环 `C` 对 `det(I+B)` 的贡献是

```text
1 + (-1)^(ell-1) product_(i in C) d_i.
```

- 奇循环给正因子；
- 偶循环给非正因子；
- 偶循环数目的奇偶性正好等于 `sgn(P)`。

因此对任意矩阵和任意深度，

```text
chi(B) det(I+B) >= 0.                         (1)
```

这补上了此前 odd-order positive-monomial 结果的缺口。旧结果通过禁止偶置换得到
正权；这里保留 transposition，并用一个可乘 grade 抵消其 determinant 符号。

## 精确物理顶点

在任意一条边 `e=(i,j)` 上定义

```text
B_e(r) = identity outside (i,j)
         direct-sum r [[0,1],[1,0]],          r>1.
```

它是一次 dilated mode transposition，置换 grade 为 `-1`。完整 Fock lift 逐
矩阵元满足

```text
Gamma(B_e)
 = 1 - n_i - n_j
   + (1-r^2)n_i n_j
   + r(c_i^dag c_j + c_j^dag c_i).           (2)
```

取

```text
H = sum_e q_e Gamma(B_e),                    q_e>0.
```

连续时间展开一次插入是 `-q_e Gamma(B_e)`。长度 `k` 历史的 scalar sign 为
`(-1)^k`，由 `(1)` 得

```text
W_C
 = product_e q_e * (-1)^k det(I+B_C)
 >= 0                                                    (3)
```

对任意边顺序、任意重叠和任意展开阶数成立。

去掉常数和边化学势后，`(2)` 是

```text
+t_e(c_i^dag c_j+h.c.) - U_e n_i n_j,

t_e = q_e r_e,
U_e = q_e(r_e^2-1).
```

也就是正号 hopping 加吸引相互作用。给定任意 `t_e,U_e>0`，方程

```text
U_e/t_e = r_e - 1/r_e
```

都有唯一 `r_e>1`，所以 hopping 与 attraction 可独立指定；额外的边化学势是
`-q_e(n_i+n_j)`。

## 为什么三角模型不是原来的 stoquastic TN 模型

在一粒子 sector，三角形三条边的 hopping matrix element 全为正。站点符号规范
`c_i -> s_i c_i` 若要把每条边都变成非正，需要

```text
s_0 s_1 = s_1 s_2 = s_2 s_0 = -1.
```

三式相乘得到 `+1=-1`，不可能。代码枚举全部站点 gauge 也得到空集；开放路径对照
则唯一幸存。

更强的全 Fock-sector 普通 hopping 图 no-go 已在
[COMPOUND_GAUGE_NO_GO.md](COMPOUND_GAUGE_NO_GO.md)证明。这里之所以能绕开原来的
TN 正和障碍，是因为每个 Gaussian 顶点的 scalar coefficient 不再为正，而是与
crossing grade 一起乘法传播。

## 把每个场真正写成实矩阵指数

单独的 `B_e` 有负 determinant，不能等于一个实矩阵指数。为避免把这一点藏起来，
我们还构造了一个只增加一个守恒模式的 grade-ancilla lift：

```text
Btilde_e = B_e direct-sum (-r_e).
```

`B_e` 的负本征值 `-r_e` 与 ancilla 的 `-r_e` 成对，因此存在显式实矩阵
`A_e` 使

```text
exp(A_e) = Btilde_e.
```

代码用“endpoint 反对称模—ancilla 模”平面内的 `pi` 实旋转给出这个 `A_e`，
并由 `scipy.linalg.expm` 逐矩阵元验证。

长度 `k` 历史满足

```text
det(I+Btilde_C)
 = det(I+B_C) [1 + (-1)^k product_l r_l] > 0.          (4)
```

两个因子的符号都为 `(-1)^k`。因此加强版具有：

- 每个单时间片都是 `exp(real A_e)`；
- auxiliary scalar 全部为正；
- 任意历史的扩展 determinant 逐构型严格为正。

把 ancilla 固定在占据 sector 时，它的 Fock matrix element 正是 `-r_e`，所以会
还原原始 signed-grade 物理模型，只改变可吸收到 `q_e` 的正尺度。若对 ancilla 两个
sector 都取迹，完整扩展模型本身也由 `(4)` 保正。

代价是这个 grade ancilla 对一个连通分量内所有边共享；它是守恒的全局
superselection/算法模式，不应伪装成普通局域物质自由度。能否把它局域化为 gauge
constraint 是下一道物理问题。

## 可执行证据

`oracle/graded_monomial.py` 实现：

- positive monomial 的 permutation、dilation 与循环证书；
- graded determinant；
- dilated transposition 与完整 Fock lift；
- hopping/attraction 反参数化；
- arbitrary-history signed weight；
- grade-ancilla 实生成元和扩展 determinant；
- 站点 stoquastic gauge 穷举。

`tests/test_graded_monomial.py` 覆盖：

- 相邻与非相邻模式的完整 Fock 恒等式；
- 四模式全部 `24` 个置换的循环公式；
- 三角图不等参数、深度 `0--7` 的历史；
- grade-ancilla 的显式实指数；
- 物理 Hamiltonian Taylor 系数与 auxiliary-history 求和一致；
- 三角失败与路径成功的 gauge 对照。

当前结果：

```text
19 targeted tests passed
```

全 solution suite 将在提交前重新运行。

## 文献与结论边界

必须主动保守：

1. `r=1` 的局部算符是 fermionic/graded permutation 的近亲；`su(1|1)`
   permutation chain 本身已有系统研究，例如
   [Carrasco et al., 2016](https://arxiv.org/abs/1603.03668)。
2. 把 fermion permutation sign 通过构型重组消掉是 meron-cluster 的核心思想之一，
   见 [Chandrasekharan and Wiese, 1999](https://arxiv.org/abs/cond-mat/9902128)。
3. 初步检索尚未找到与这里完全相同的 `r>1` monomial determinant grade、奇环吸引
   模型和单-mode real-log lift；这只能算“尚未找到”，不能替代完整引用链。
4. 仍需检查它是否可重新解释成已知 meron/loop、fermion-bag、Majorana 或 split
   机制。

因此当前可以说：

> 找到并证明了一个不同于纯 TN 正和的 graded crossing 正性构造，并给出受挫局域
> 相互作用模型与实指数 ancilla lift。

当前还不能说：

> 发现了文献史上全新的无符号 QMC 类。

