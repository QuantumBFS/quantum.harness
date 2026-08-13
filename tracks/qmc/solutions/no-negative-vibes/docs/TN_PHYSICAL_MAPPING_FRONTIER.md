# TN 正性机制的物理映射前沿

更新时间：2026-07-28

## 现在可以怎样表述

最准确的一句话是：

> 我们得到一个相对于挑战所列 Kramers、split-orthogonal 和 Majorana contraction
> semigroup 条件不可约化的、严格成立的 TN 正性机制候选；还构造了它对普通排斥
> `t-V` 链的精确非对称辅助场实现，但目前没有找到一个只有依靠这个机制才无符号的
> 新物理 Hamiltonian。

因此：

- 可以说“发现了一个新的**候选矩阵正性机制**”，并明确“新”是相对于已经完成的代数排重；
- 可以说它已经有有意义的物理/算法实现，不再只是外在的纯矩阵例子；
- 暂时不能说“文献史上首次”，精确关键词无命中不能替代完整引用链和专家复核；
- 暂时不能说“发现了新的无符号物理模型”，因为当前 Hamiltonian 还是已知的一维开放
  `t-V` 链。

矩阵机制、辅助场算法和物理模型的新颖性是三关，不应合并成一句过强的结论。

## 一个连续时间的硬边界

设一个光滑单粒子半群从恒等元出发，

```text
B(dt) = I + dt A + O(dt^2),
```

并要求对任意充分小的 `dt >= 0`，`B(dt)` 都是 TN。则 `A` 必须是三对角 Metzler
矩阵：只有主对角和相邻上下对角元可以非零，且相邻非对角元非负。

这个结论也可直接从小子式看出：

1. 所有 `1 x 1` 子式非负，给出 `A_ij >= 0 (i != j)`；
2. 对 `j > i+1`，取行 `{i,i+1}`、列 `{i+1,j}` 的 `2 x 2` 子式，其一阶项是
   `-dt A_ij`，所以 `A_ij <= 0`；
3. 下三角远邻元同理，故所有远邻元为零。

这解释了前一轮扫描的边界：若一个普通 Hamiltonian 的每个无穷小动能传播子自身都要靠
TN 保正，那么固定单粒子排序下的 hopping 图只能是开放路径。环、分支和远程 hopping
不能直接进入这个连续 TN 生成元锥。

任意稠密 TN 矩阵仍可作为一个**有限离散步**的传播子，但它的任意分数次幂未必 TN；若
不能把 Trotter 步长送到零，它更自然地描述离散虚时间电路或转移矩阵，而不是普通连续
时间 Hamiltonian。这个 no-go 把“为什么一直退化回一维”从直觉提升成了边界定理。

经典的 Schwarz/全正微分系统背景见
[Margaliot and Sontag](https://arxiv.org/abs/1802.09590)；TN 的双对角和平面网络参数化
背景见 [Fomin and Zelevinsky](https://arxiv.org/abs/math/9912128)。

## 更强的边界：正和也救不了普通非相邻 hopping

也许可以绕开上一节：不要求物理门本身是一个 TN 高斯算符，而把它写成正和

```text
G_physical = sum_s p_s Gamma(B_s),    p_s >= 0, B_s TN.
```

新构造确实采用了这条思路。但对普通数守恒 hopping，它仍有一个简单的必要条件。对任意
`N x N` 单粒子矩阵 `B`，高斯算符在 `k` 粒子扇区的矩阵元是 `B` 的 `k x k` 子式：

```text
<R|Gamma(B)|C> = det B[R,C].
```

若 `B` 是 TN，`Gamma(B)` 在按站点排序的全部 Fock 基中的每个矩阵元都非负；它们的任何
正和也必然逐元非负。

现在考虑排序中不相邻的 `i<j` 之间的普通费米 hopping。单粒子扇区中
`c_i^dag c_j` 的矩阵元为正；若在 `i,j` 之间多占据一个站点，Jordan--Wigner 宇称使同一
hopping 的矩阵元反号。因此对

```text
h_ij = -t(c_i^dag c_j + h.c.)
```

和充分小的正 `dt`，`exp(-dt h_ij)` 在一个扇区有正非对角元，在另一个扇区必有负
非对角元。它不可能是 TN 高斯算符的正和。密度相互作用只改对角元，不能消掉这个一阶
障碍。

于是，在不加 ancilla、保持普通数守恒 hopping 的条件下：

> 能由 TN 高斯正和逐局部门实现的 hopping 图，经过固定站点排序后仍只能是若干开放路径。

环至少有一条闭合边不相邻；真正分支至少有一个度数大于二的点，也不可能把所有边都排成
相邻。直接给路径“多加几个辅助场”不能越过一维。自动测试用三站点 `1<->3` hopping
显式验证了：一粒子矩阵元为正，而中间站点已占据的二粒子矩阵元为负。

即使允许每个粒子数扇区各自选择独立的固定符号规范，结论仍不改变。一般图论证明、2–6
站点全部连通图穷举和可执行 signed-graph 检查见
[复合矩阵规范 no-go](COMPOUND_GAUGE_NO_GO.md)。

## 新构造：排斥键门的精确非对称高斯分解

考虑两站点单 flavor Hamiltonian

```text
h_b = -t(c_1^dag c_2 + c_2^dag c_1)
      +V n_1 n_2 - mu_b(n_1+n_2),       V >= 0.
```

在局部 Fock 基

```text
|0>, |1>, |2>, |12>
```

中，物理键门分块为

```text
exp(-dt h_b) = 1 direct_sum M direct_sum q,

M = exp[dt(mu_b I + t sigma_x)]
  = [[a,b],[b,a]],

q = det(M) exp(-dt V).
```

记

```text
Delta   = det(M) = a^2-b^2,
r       = exp(-dt V),
epsilon = kappa b,                         0 <= kappa < 1,
delta   = sqrt[epsilon^2 + Delta(1-r)].
```

定义两个非对称单粒子传播子

```text
B_+ = [[a+delta, b+epsilon],
       [b-epsilon, a-delta]],

B_- = [[a-delta, b-epsilon],
       [b+epsilon, a+delta]].
```

对任意数守恒单粒子矩阵 `B`，其二次量子化高斯算符满足

```text
Gamma(B) = 1 direct_sum B direct_sum det(B).
```

而上述两个矩阵严格满足

```text
(B_+ + B_-)/2 = M,
det(B_+) = det(B_-) = Delta r = q.
```

所以得到精确的正系数离散辅助场恒等式

```text
exp(-dt h_b) = [Gamma(B_+) + Gamma(B_-)] / 2.       (*)
```

它不是小 `dt` 展开：每个局部键门在任意有限 `dt` 上都精确。

## 为什么每个辅助场构型都 TN

对 `0 <= kappa < 1`，

```text
b-epsilon = (1-kappa)b >= 0,
a^2-delta^2 = (1-kappa^2)b^2 + Delta r > 0.
```

因此 `a-delta>0`，两个 `B` 的全部元素非负，行列式又等于 `Delta r>0`。对 `2 x 2`
矩阵，这已经等价于可逆 TN。

它们还有正实特征值，并且

```text
log(B) = alpha I + beta B,    beta > 0,
```

所以 `log(B_+)` 和 `log(B_-)` 的两个非对角元也都非负：每个辅助场因子确实是 TN
路径生成元的指数，不只是偶然落在 TN 边界上的矩阵。

把这些 `2 x 2` 因子嵌入开放链的相邻键，再按 even/odd checkerboard 相乘，每个辅助场
构型仍是 TN，因而

```text
det(I + product B_l) >= 1.
```

每个 Ising 键场的标量概率为 `1/2`，总 Monte Carlo 权重严格为正。

## 它确实实现了“非对称”，但要怎样排重

当 `kappa>0` 时，单个正对角规范若要把 `B` 对称化，所需的规范比满足

```text
(s_2/s_1)^2 = B_21/B_12.
```

`B_+` 与 `B_-` 所需的比值分别是

```text
(1-kappa)/(1+kappa)
```

及其倒数，所以不存在一个共同的**对角**规范。

不过科学上必须再多走一步：只看一个孤立键时，这两个矩阵仍共享一个非对角正定度量，
所以两站点例子本身还可被共同相似变换为实对称矩阵。真正消除这个退化的是三个以上站点
的**重叠键**：

- 对一个局部键传播子 `diag(B,I)`，共同对称度量方程
  `H diag(B,I)=diag(B^T,I) H` 在 `1` 不是 `B` 特征值时迫使键内外块为零；
- 同时要求 `(1,2)` 和 `(2,3)` 两条重叠键成立，就迫使全局 `H` 为对角；
- 正 `kappa` 下，同一键的 `B_+/-` 又不接受共同对角度量。

所以对一般参数的开放链重叠键集合，不存在一个固定全局正定度量把全部辅助场传播子同时
Hermitian 化。自动测试还直接求解了三站点的共同对称 intertwiner 线性空间，在所用非退化
参数上其维数为零。

这说明新构造真正进入了 TN 定理允许的非对称区域，而不是把整个场集合偷偷换回一个固定
Hermitian 基。但物理 Hamiltonian 本身仍是普通 Hermitian `t-V` 链。

## 这项结果的定位

| 层次 | 当前状态 |
|---|---|
| TN 行列式正性 | 一般定理，完成 |
| 相对挑战既有机制的排重 | 固定 Kramers/split/Wei 2024 已代数排除 |
| 物理辅助场可达性 | 已完成精确非对称键场恒等式 `(*)` |
| 是否只是单个键的换基 | 重叠键已排除固定全局 Hermitian 度量 |
| 新的无符号 Hamiltonian | 未完成；当前仍是已知一维 `t-V` 链 |
| 文献史首创 | 未确认 |

Hirsch 的经典离散 HS 工作说明了用辅助 Ising 场消去四费米相互作用的基本框架
（[Phys. Rev. B 28, 4059](https://journals.aps.org/prb/abstract/10.1103/PhysRevB.28.4059)）。
现有 AFMC 形式本来也允许辅助场产生一般非 Hermitian 单粒子矩阵；真正需要排重的不是
“非 Hermitian”三个字，而是这里这个**正系数、逐构型 TN、重叠键无共同 Hermitian
度量**的具体离散分解。目前的精确检索尚未找到同一公式的直接先例，仍需沿离散 HS、
bond-channel decoupling 和 non-Hermitian AFQMC 的引用链核对。

## 接下来啃哪块硬骨头

现在最有信息量的推进顺序是：

1. **做引用链排重。** 搜索这个两场键门恒等式是否以 hopping/bond channel HS 的语言
   出现过；若有，比较其 sign-free 证明是否已经等价于 TN。
2. **把算法跑成闭环。** 用相同 checkerboard Trotter 门，对不同 `kappa` 穷举/采样，
   验证配分函数不变，并比较权重方差、条件数和局部更新代价。`kappa` 是一个不改变物理
   模型的辅助场“规范参数”，即使不产生新模型也可能有算法价值。
3. **沿 no-go 的缺口找新物理。** 连续 TN 自身只能给路径，因此不能再靠“多加一条边”
   盲试；正和 no-go 又关闭了普通非相邻 hopping。真正可能越过一维边界的入口只剩：
   - 引入带非平凡 gauge constraint/编码的 ancilla；简单 Fock 投影或偏迹仍保持逐元
     非负，不能修复普通远邻 hopping 的负矩阵元；
   - 研究带 Jordan--Wigner 宇称串的相关 hopping；它不是普通二次 hopping，但可消掉
     随中间占据翻转的符号；
   - 允许 pairing，转入 Majorana/Pfaffian 高斯算符；这已不由普通 TN 子式直接控制；
   - 研究离散虚时间平面网络/转移矩阵模型，而不冒充连续 Hamiltonian；
   - 寻找严格大于 TN、仍对乘法封闭且主子式非负的半群。
4. **优先攻击 ancilla 和宇称串。** 直接三站点远邻 hopping 已有解析障碍；下一候选应
   明确利用额外自由度或相关 hopping 改变该负矩阵元，而不是重复一个已被 no-go 关闭的
   正和拟合。

## 可执行证据

- `oracle/tn_bond_hs.py`：公式、Fock 高斯矩阵、相邻键嵌入和逐构型权重；
- `tests/test_tn_bond_hs.py`：局部精确恒等式、TN/对数生成元、孤立键与重叠键度量排重、
  512 个四站点 checkerboard 构型、`kappa` 不变的枚举配分、全部子式生成的 Fock
  高斯矩阵，以及非相邻 hopping 的扇区符号翻转。
