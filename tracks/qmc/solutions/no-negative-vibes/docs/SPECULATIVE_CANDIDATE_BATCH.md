# 激进候选批次：从未开拓的表示与离散路由找恒正半群

更新时间：2026-07-28

## 本文的作用

这是一份方向占位和可证伪清单，不是“发现声明”。它把下一批候选的定义、正性理由、
最小数值实验、排重条件和停止条件固定下来，避免两位合作者重复扫同一片参数空间。

统一目标仍是

```text
w(A_1,...,A_L) = det[I + exp(A_1)...exp(A_L)] >= 0
```

对任意允许的时间片、任意深度都成立。一次负权足以淘汰；随机零失败只算候选，只有一般
证明或精确证书才能升级结论。

## 首批回填

第一批代码、192,000 个 determinant 权重、640 条宇称分辨 Majorana 历史和 80 位反例
已经完成，详见[首批结果](SPECULATIVE_STRUCTURE_RESULTS.md)。每条 Majorana 历史分别
计算 even、odd 和完整 Fock 迹。

- odd monomial / block-TN：升级为有一般证明的主候选，物理映射仍开放；
- fixed `l_infinity`、reciprocal-parabolic、commuting：严格正，但新颖性较低；
- moving metric、双向 reciprocal、near-commuting、偶阶 monomial：已有负权，关闭；
- `D_4` Lusztig：约化到已知 split `SO(4,4)`，不作为新机制；
- Majorana 宇称公式：首批完全符合，但仍是待证明猜想。

## 第一优先级：本轮立即实现

### S1. 奇数阶 positive-monomial 半群

令

```text
B = P_g diag(d_1,...,d_n),   d_i > 0,
```

其中 `g` 来自一个奇数阶置换群。乘积仍是同型；奇数阶群元素的每个置换循环长度都是奇数。
把最终传播子按循环分块后，

```text
det(I+B) = product_C [1 + product_{i in C} d_i] > 0.
```

这个类包含 ordinary TN 之外的元素：三循环置换矩阵已经有负的非主子式；在奇维也
不可能靠全局
`J^2=-I` Kramers 结构解释。每个正 monomial 因子若只含奇循环，则没有负实本征值，存在
实矩阵对数，所以可以写回 `B=exp(A)`。

首批实例：

- `odd_monomial_c3`
- `odd_monomial_c5`
- `even_monomial_v4`：偶阶双换位群边界对照，预期失败

停止/升级条件：

- 找到稳定负权：立即淘汰对应定义并保存反例；
- C3/C5 零失败后不靠样本宣称，直接使用上面的循环分解定理；
- 下一步只在能得到局域 HS 离散路由时继续做物理映射。

### S2. 奇数循环的 block-TN wreath 半群

把 monomial 的正标量换成可逆 TN 块 `X_i`。长度为奇数的块循环贡献

```text
det(I + X_l ... X_1) >= 0,
```

因为可逆 TN 块乘积仍 TN。它把已有开放路径传播子通过离散奇循环路由起来，可能产生比单条
链更丰富的辅助场几何。

对本轮可逆块，奇循环的奇次幂在对角块上给出正谱 TN 乘积，因此原循环没有负实本征值；
由 Culver real-log criterion，它仍能写成一个实矩阵指数。奇异 TN 只作为闭包边界。

首批实例：

- `odd_block_tn_c3`，三个站点、每站一个 `2 x 2` TN 块；
- 后续只有 C3 通过结构审计后才扩到 C5。

### S3. 固定加权 `l_infinity` 收缩锥

固定 `h_i>0`，要求

```text
a_ii + sum_{j != i} |a_ij| h_j/h_i <= 0.
```

则 `diag(h)^(-1) exp(A) diag(h)` 的无穷范数不超过 1。任意乘积的谱半径不超过 1；
实本征值位于 `[-1,1]`，非实本征值共轭成对，所以 `det(I+D)>=0`。这个锥允许稠密、
带符号、有环的单粒子图，而 ordinary TN 路径不覆盖这些一般矩阵；这里不主张两类有
简单的集合包含关系。

它在 QMC 语境里的新颖性有限：本质仍是公共 Banach 范数收缩，但不等同于已有固定二次
metric 锥。必须同时测试每片独立改变 `h` 的并集；后者预期像 rotated cones 一样失败。

首批实例：

- `linf_contract4`
- `linf_moving_metric4`

### S4. reciprocal-parabolic 半群

取

```text
A = [[ H,  Q],
     [ 0, -H^T]],
```

其中 `H,Q` 为任意实矩阵。任意指数乘积都有

```text
D = [[X, Y],
     [0, X^(-T)]],   det(X)>0,
```

从而

```text
det(I+D) = det(I+X)^2 / det(X) >= 0.
```

`Q` 不要求对称或反对称，因此整个类一般不保存固定 symplectic/split form；但正性来自
上三角因子化，属于“严格但可能只是闭包操作”的中等新颖性结果。

首批实例：

- `reciprocal_parabolic4`
- `reciprocal_bicoupled4`：打开任意 lower block 的边界对照

### S5. split `D_4` 的 Lusztig/Chevalley 正锥（已降级）

对 split `SO(4,4)` 的八维向量表示，取 Cartan 元加上所有 simple-root Chevalley
生成元的非负组合。每片指数落在 Lusztig totally nonnegative monoid 的闭包，乘积仍在
其中。

原候选证明设想不要求八维矩阵本身 ordinary TN。对每个外幂表示，

```text
det(I+D) = sum_k Tr[Lambda^k(D)].
```

若 simple-root 指数在各不可约分量的 canonical basis 中逐项非负，则每个 character
非负，故总权非负。`D_4` 向量权图含菱形/循环，不能像标准 `C_n` 那样重排成一条 Jacobi
路径，因此它是这条表示论机制的第一个有意义测试。

首批实例：

- `lusztig_d4_positive`
- `lusztig_d4_signed`：允许任意根系数的边界对照

首批审计发现所有这些 simple-root 生成元已经满足同一个 split `SO(4,4)` 约束，而且
允许任意根系数的 signed 对照也仍受该约束保护。因此零失败无需诉诸上面的
canonical-basis 设想，当前状态已降为 `known_reduction`，不再推进为新机制。

### S6. 稠密可交换代数

所有时间片若属于同一实可交换代数，则

```text
product_l exp(A_l) = exp(sum_l A_l),
```

而单个实矩阵指数总有 `det(I+exp S)>=0`。这个类给 oracle 一个稠密、非对称但可严格
理解的正对照；加入不对易扰动应迅速失败。

首批实例：

- `commuting_dense4`
- `near_commuting4`

## 第二优先级：本轮占位，下一批编码

### S7. 非诱导 exterior-cone

为每个粒子数扇区独立选择可逆变换 `T_k`，要求

```text
T_k A^[k] T_k^(-1)
```

都是 Metzler。于是每个 multiplicative compound 的迹非负，严格推出总行列式非负。
真正的新意是 `T_k` 不来自同一个单粒子变换的外幂。下一步在 `n=4` 用线性规划寻找至少
两个不对易 extreme rays，并用 Pluecker 约束排除 induced gauge。若可行锥只剩标量、
flag 或 TN，立即停止。

### S8. spinor/Fock Metzler Majorana 锥

对 Majorana 二次生成元的两个费米宇称块 `h_+`、`h_-`，直接要求它们在固定 Fock 基中
为实 Metzler。两个块的任意指数乘积都有非负迹，因此真实 Spin/Pfaffian 权非负。这是
表示空间正性，不是单粒子 determinant 锥。

需要同时审计：

- 是否只是 Jordan-Wigner 后的 stoquastic/matchgate 子类；
- 是否自动落回 2016 Majorana reflection positivity 或 2024 contraction semigroup；
- 能否给 interacting Kitaev bond / pair-hopping 做正系数 HS 分解。

### S9. Majorana reflection positivity 的宇称分辨版本

分别扫描

```text
Z_even/odd = Tr[(1 +/- (-1)^F) U] / 2.
```

初步小样本提示可能只有一个随模式数变化的宇称扇区受保护。在 canonical `J1/J2`、
当前 Jordan-Wigner Majorana 排序和取向下，

```text
pi_* = (-1)^[m(m+1)/2].
```

这是 convention-dependent 猜想而非结果；orientation-reversing Majorana 重排可交换
even/odd 标签。另一扇区已有大量数值负样本。下一批应先系统重放，再检查 2016 证明中的
反射取向符号，不能把“总迹正”误读成“两扇区都正”。

### S10. pairwise-overlap Majorana cone nerve

让相邻时间片分别来自 `C0 intersect C1`、`C1 intersect C2`、`C2 intersect C0`，
测试“局部共享正锥但无全局共同锥”是否足够。宽角试算已经出现负权，因此本方向只值得
保存一个高精度反例；窄角零失败必须先排查隐藏的共同 `J2`。

## 严格正但不作为新机制主打

- 奇数阶非阿贝尔群代数：可分解成一个正 trivial sector 与复共轭块的模平方，实质接近
  已知 Kramers/共轭配对；
- 周期 moving-frame cone cocycle：闭合 holonomy 会望远镜约化到固定锥；
- block-upper-triangular 装饰：行列式只看对角块，是有用闭包但不是新核心；
- standard `C_n/Sp(2n)` Lusztig 正锥：在标准表示中经固定符号和权序重排就是已有 TN
  路径，已经从“新候选”降级。

## 本批判断纪律

每个候选最后只能进入下列四种状态之一：

1. `rigorous_survivor`：有一般证明，数值只做实现审计；
2. `numerical_survivor`：零失败但证明未闭合；
3. `known_reduction`：严格正，但约化到已知机制；
4. `falsified`：有稳定数值或精确反例。

只有同时满足“非已知机制换基、存在局域/可采样 HS 来源、证明覆盖任意深度”的候选，才有
资格进入最终“新物理无符号类”主张。

## 文献锚点

- Culver, *On the existence and uniqueness of the real logarithm of a matrix*,
  1966: <https://doi.org/10.1090/S0002-9939-1966-0202740-6>
- Fomin and Zelevinsky, *Totally nonnegative and oscillatory elements in
  semisimple groups*, 1998: <https://arxiv.org/abs/math/9811100>
- Fomin and Zelevinsky, *Double Bruhat cells and total positivity*, 1999:
  <https://arxiv.org/abs/math/9912128>
- Wei et al., *Majorana positivity and the fermion sign problem of quantum
  Monte Carlo simulations*, 2016: <https://arxiv.org/abs/1601.01994>
- Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
  simulations*, 2017/2024 version: <https://arxiv.org/abs/1712.09412>
- Han, Wan, and Yao, *Pfaffian quantum Monte Carlo*, 2024:
  <https://arxiv.org/abs/2408.10311>
