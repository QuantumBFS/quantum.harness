# Graded monomial crossing：结果与已知类排重

日期：2026-07-28

## 一句话结果

我们证明了纯 TN 之外的一个严格 graded determinant 恒等式：

> 允许单粒子网络出现 permutation crossing，并让每个 crossing 携带它的置换奇偶
> 标量符号，则这个符号会在任意长历史中精确抵消 determinant 的符号。

它反推出一个局域、Hermitian、真正含相互作用的 spinless-fermion 模型；在三角形等
奇环上，该模型不能靠站点 `+/-` gauge 变成固定 Fock 基 stoquastic hopping。

但文献排重改变了新颖性判断：

- `r=1` 时局部算符**精确等于**已知的 `su(1|1)` graded permutation；
- `r>1` 物理 Hamiltonian 可严格写成 Majorana reflection positivity 已覆盖的
  “负半定一体核 + 吸引密度相互作用”；
- 所以它不是一个新的无符号 Hamiltonian 类，也不能作为 challenge 的最终新类；
- monomial cycle factorization 本身也是已知矩阵事实，grade 不等式是它的直接推论；
- 保留下来的是把这些已知事实组织成逐历史 QMC 正权的一种特殊 CT 展开和可执行证书。

当前状态应降为
`known-monomial-factorization / known-majorana-subclass / useful-reformulation`。
不再主张新的矩阵正性定理或新的无符号 Hamiltonian 类。

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

## 为什么物理模型属于已知 Majorana 正性类

“不能做站点符号 gauge”不等于“超出所有已知无符号机制”。把每条边的密度相互作用
改写为半填充形式，令

```text
t_e = q_e r_e,
U_e = q_e(r_e^2-1),
a_e = q_e + U_e/2 = q_e(r_e^2+1)/2.
```

则

```text
q_e Gamma(B_e)
 = t_e(c_i^dag c_j+h.c.)
   - U_e(n_i-1/2)(n_j-1/2)
   - a_e(n_i+n_j)
   + q_e + U_e/4.                                  (5)
```

忽略常数后，一体 kernel 在边 `(i,j)` 上的块是

```text
K_e = [[-a_e, t_e],
       [ t_e,-a_e]].
```

它的两个本征值恰为

```text
-q_e(r_e-1)^2/2,   -q_e(r_e+1)^2/2,
```

所以每个 `K_e` 都负半定，任意图上求和后的 `K=sum_e K_e` 仍负半定。另一方面，
所有 centered density coupling 都是 `V_ij=-U_e<0`。把所有 site 放在 Majorana
reflection decomposition 的同一部分，便得到

```text
H_0 = -c^dag B_1 c,       B_1=-K >= 0,
V_ij <= 0                 (same reflection part).
```

这正是
[Wei et al., 2016](https://arxiv.org/abs/1601.01994) Eq. (7)--(10) 的
Majorana-reflection-positive 充分条件。它允许同一分区内的吸引作用和半正定的一体
块，因此不要求物理 hopping 图本身是二分图。

`majorana_reflection_certificate()` 现在直接构造 `K`、`B_1=-K` 和负的
`V_ij`，测试还逐 Fock 矩阵验证了式 `(5)`。这不是仅凭文献语言相似做出的归类。

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
20 targeted tests passed
```

全 solution suite 将在提交前重新运行。

## 文献与结论边界

必须主动保守：

1. `r=1` 的局部算符**就是** fermionic/graded permutation：
   `1-n_i-n_j+c_i^dag c_j+c_j^dag c_i`；`su(1|1)` permutation chain
   已有系统研究，例如
   [Carrasco et al., 2016](https://arxiv.org/abs/1603.03668)。
2. 把 fermion permutation sign 通过构型重组消掉是 meron-cluster 的核心思想之一，
   见 [Chandrasekharan and Wiese, 1999](https://arxiv.org/abs/cond-mat/9902128)。
3. 连续时间 fermion-bag 也使用“指数化键算符的乘积迹逐构型为正”，见
   [Huffman and Chandrasekharan, 2017](https://arxiv.org/abs/1709.03578)；
   其标准键矩阵是 determinant `+1` 的 hyperbolic block，示例是二分晶格上的
   staggered/repulsive `t-V` 模型，并非这里的 dilated transposition。
4. 决定性的排重是
   [Wei et al., 2016](https://arxiv.org/abs/1601.01994)：式 `(5)` 给出了对其
   Majorana reflection positivity 类的显式包含证书。
5. [Wei, 2024 version](https://arxiv.org/abs/1712.09412) 又说明 Majorana
   reflection positivity 等价于其 contraction-semigroup 框架中的一类，因此不能因
   我们的 matrix history 写法不同就把物理模型重新称为新类。
6. monomial 矩阵的特征多项式按置换循环分解也是已知结果：
   [Egan et al., 2019](https://ajc.maths.uq.edu.au/pdf/73/ajc_v73_p501.pdf)
   Proposition 3.3 给出
   `chi_M(x)=product_C (x^|C|-c_C)`。本文的 determinant cycle factor 是代入
   `x=-1` 后的直接推论；再用 `c_C>=1` 判断偶循环符号即可得到 grade 不等式。

因此当前可以说：

> 给出了一个不同于 pure-TN 表述的 graded crossing CT 展开、局域模型、实指数
> ancilla lift，以及对已知 monomial factorization 和 Majorana 正性类的显式约化。

当前还不能说：

> 发现了新的矩阵正性定理或新的无符号 Hamiltonian 类。
