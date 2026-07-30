# 三个候选的排查结果：现在真正还剩什么

更新时间：2026-07-29

状态：解析排查和定向回归均已完成；不增加“确认的新无符号物理类”计数。

## 先说人话版结论

上一轮留下了三个看起来值得深挖的候选。现在逐个拆开以后：

| 候选 | 这轮发现了什么 | 当前处理 |
|---|---|---|
| tensor-square 多通道模型 | 正权公式本身还能分解成“复共轭模平方 × 实平方”；但 `m=3` 的完整矩阵族不存在固定的 split-orthogonal 度量，所以不能用最简单的已知对称性把它整体打发掉 | **唯一保留的主候选**。不再宣传新行列式机制，继续研究它产生的三通道相互作用模型是否有独立物理和算法价值 |
| grade-charge full trace | 所有 ancilla 占据数严格守恒；整个 Hamiltonian 只是许多静态扇区的直接相加，ancilla 不会运动，也不会产生新的量子动力学 | **降级为方法工具**。除非找到保持正性的 ancilla 动力学，否则不再作为新物理主线 |
| adjoint lift | 整个矩阵族严格位于一个已知 `O(p,q)` 的恒等连通分支；补齐较小 signature 后就是已有 split-orthogonal 定理 | **关闭为新正性机制**。保留作已知类的结构化参数化和测试样例 |

所以不是“研究三个候选，三个都没了”。准确说是：

```text
三个模糊候选
    -> 两个已经知道为什么正、为什么不够新
    -> 一个缩小为明确问题：tensor-square 的物理模型有没有新内容？
```

确认的新 L3 无符号物理类仍为零。这是正确的保守口径。

## 为什么同一个非厄米链有很多 Hermitian partner

设非厄米矩阵已经写成

```text
H_NH = S^(-1) D S,
```

其中 `D` 是实对角矩阵，所以它本身就是最简单的 Hermitian partner。现在任取一个
unitary 矩阵 `U`，定义

```text
h_U = U D U^dagger,
S_U = U S.
```

直接代回去仍有

```text
H_NH = S_U^(-1) h_U S_U.
```

这说明同一个 `H_NH` 不只对应一个 Hermitian 模型，而对应无穷多个。选择 `U=I`，
partner 就是完全对角、各格点互不作用的模型；选择 Fourier 变换或一般稠密 `U`，
同一组对角能级会在原来的格点标签下看成长程甚至全连接 hopping。

一个两能级玩具例子已经足够说明：

```text
D = diag(E1,E2)
```

在旋转基底中可变成

```text
h(theta)
 = [[E1 cos(theta)^2 + E2 sin(theta)^2,
     (E1-E2) sin(theta) cos(theta)],
    [(E1-E2) sin(theta) cos(theta),
     E1 sin(theta)^2 + E2 cos(theta)^2]].
```

非对角耦合的大小由任意选择的 `theta` 决定，不是原非厄米链唯一逼出的新相互作用。
更高维 Fourier 旋转只是把这件事变成一张长程 hopping 图。

因此“我找到了一个长程 Hermitian partner”本身没有物理新颖性。只有再证明以下内容，
它才可能升级：

1. 物理格点、局域可观测量和允许的基变换已经预先固定；
2. similarity `S` 在系统变大时仍是局域或准局域的；
3. `S` 的条件数不会随尺寸灾难性发散；
4. 长程项不是任意 unitary 换基制造的，而由这些物理约束唯一或近乎唯一地决定。

当前单向 Stark 例子不满足这个升级标准，所以保留为“检查变换代码是否正确”的方法校准，
不再当主候选。

## 候选一：tensor-square 到底还剩什么

### 新找到的隐藏分解

任意实矩阵 `X` 的 tensor-square 权重可精确写成

```text
det(I + X tensor X)
  = det(I + X^2) det(I + Lambda^2 X)^2
  = |det(I + i X)|^2 det(I + Lambda^2 X)^2.       (1)
```

这里 `Lambda^2 X` 是 `X` 在两粒子反对称空间上的作用。若 `lambda_i` 是 `X` 的
本征值，式 (1) 只是把所有因子分成两组：

```text
i=j:  product_i (1 + lambda_i^2),
i<j: [product_(i<j) (1 + lambda_i lambda_j)]^2.
```

这条恒等式是多项式恒等式，不依赖 `X` 可对角化。代码还使用整数矩阵做了精确
SymPy 锚点，而不只是浮点随机检查。

含义是：tensor-square 的 determinant 正性不是一个不可再拆的全新代数机制。它最终
也是“一个复数和它的共轭相乘，再乘一个实数平方”。

### 为什么它还没有被完全关闭

式 (1) 是对**整段历史乘积** `X=X_1...X_L` 的事后分解。里面的 `i` 和
`Lambda^2 X` 不会自动给出每个时间片上的普通双 flavor Hamiltonian，也不会自动把
已经构造出的

```text
H = K - (1/2) sum_a g_a Q_a^2
```

变成一个熟悉模型。因此：

- “tensor-square 是新的纯矩阵正性机制”这一说法关闭；
- “它能否生成以前没有被利用过的无符号相互作用模型”仍开放。

我们还对最小非平凡底空间 `m=3` 做了一个更强的排查。令所有 traceless `3 x 3`
生成元 `A` 在九维 product space 上作用为

```text
L(A) = A tensor I + I tensor A.
```

若整个族只是固定换基后的伪正交类，就应存在非零固定双线性型 `J`，使

```text
L(A)^T J + J L(A) = 0
```

对所有 `A` 成立。精确有理线性系统共有 81 个未知量，秩为 81，因此只有 `J=0`。
这严格排除了 `m=3` 完整 tensor-square 族的最简单固定 `O(p,q)` 解释。

它还没有排除更一般的 Majorana、Pfaffian、contraction-semigroup 表示，也没有证明
相应 Hamiltonian 是文献上新的。下一步应针对最小 `m=3` 多通道模型做这两个层面的
排重，而不是继续随机扩大 determinant 扫描。

## 候选二：grade-charge 为什么降级

grade-charge 模型给每一组物理边配一个费米 ancilla。关键事实是：Hamiltonian 中没有
任何改变 ancilla 占据数的项。因此每个 ancilla bit `z_g=0,1` 都是严格守恒量，完整
Hamiltonian 精确分块：

```text
H_full = direct_sum_z H_z.                          (2)
```

在固定扇区中，一条边的物理 Gaussian vertex 只会获得一个静态系数：

```text
z_g=0:  -q_e Gamma(B_e),
z_g=1:  +q_e r_e Gamma(B_e).
```

完整热迹就是所有这些静态扇区热迹的和。正 fugacity 改变的是各扇区的统计权重，
不是 ancilla 的动力学。代码已经对三种布局——全局一个、每个 patch 一个、每条边一个——
精确重排 Fock 基并验证了式 (2)。

所以它仍是一个严格、可采样的正权构造，但更像“把许多带不同固定耦合符号的模型放在
同一个文件夹里再求和”，而不是产生了会传播、纠缠或形成新相的辅助粒子。

只有出现以下新结构才值得重开：

```text
ancilla 能发生真实跃迁或相互作用
+ 每条辅助场历史仍严格非负
+ 不能再分解成已知静态扇区或 Majorana 正性模型。
```

## 候选三：adjoint lift 为什么可以关闭

定义

```text
B(X) = X tensor X^(-T),    det(X)>0.
```

令 `K` 是交换两个 tensor 因子的 swap metric。直接计算有

```text
B(X)^T K B(X) = K.
```

`K` 的正、负 signature 分别为

```text
p = m(m+1)/2,
q = m(m-1)/2.
```

因此 `B(X)` 位于固定 `O(p,q)`。更重要的是，`GL^+(m,R)` 是连通的，映射
`X -> B(X)` 连续且把单位矩阵送到单位矩阵，所以整个 adjoint-lift 族都在
`O(p,q)` 的恒等连通分支，而不只是偶然保存一个 metric。

由于 `p-q=m`，给较小的 signature 补上 `m` 个平凡单位方向后便得到 split
`O(p,p)`；同时

```text
det(I + padded B) = 2^m det(I+B).
```

所以它的非负性完整落入已有 split-orthogonal 定理。`m=2,3,4` 的数值证书检查了
metric、signature、`det B=1` 和精确的 `2^m` padding 比例。

结论是：adjoint lift 可能仍是一种方便的已知无符号模型参数化，但不是新的正性机制，
不应继续占用主候选名额。

## 下一步只集中在一个清楚的问题

接下来不再平行维护三个主候选。执行顺序收缩为：

1. 固定一个最小 `m=3` tensor-square 多通道 Hamiltonian；
2. 把它逐时间片翻译到 Majorana/Pfaffian 表示，检查是否属于已有正性条件；
3. 分析相互作用项、守恒量、空间支撑和可观测量，判断它是否只是熟悉模型的换基；
4. 若排重幸存，实现直接 vertex-word 采样 MWE，而不显式构造指数大的 Fock 矩阵；
5. grade-charge 和 adjoint lift 只作为对照测试，不再主动扩展。

这比“继续同时脑暴三个方向”更稳：下一轮每一步都直接回答 tensor-square 的物理价值，
不会再因为 partner、基底或静态 ancilla 的非唯一性制造虚假新颖性。

## 可复核入口

- tensor-square 分解与 `m=3` 固定度量 no-go：
  `oracle/tensor_square_effective.py`、`tests/test_tensor_square_effective.py`
- grade-charge 静态扇区分解：
  `oracle/grade_charge_model.py`、`tests/test_grade_charge_model.py`
- adjoint `O(p,q)` 连通分支证书：
  `oracle/adjoint_lift.py`、`tests/test_adjoint_lift.py`

相关已知充分条件的边界可对照：

- Wang et al., [*Split orthogonal group: A guiding principle for
  sign-problem-free fermionic simulations*](https://arxiv.org/abs/1506.05349)
- Wu and Zhang, [*Sufficient condition for absence of the sign problem in the
  fermionic quantum Monte Carlo algorithm*](https://arxiv.org/abs/cond-mat/0407272)
- Wei et al., [*Majorana positivity and the fermion sign problem of quantum
  Monte Carlo simulations*](https://arxiv.org/abs/1601.01994)

检索不到完全相同的 tensor-square Hamiltonian 公式不能作为首创性证明；这里确认的是
代数包含/非包含关系和下一步问题边界，不是文献首发声明。
