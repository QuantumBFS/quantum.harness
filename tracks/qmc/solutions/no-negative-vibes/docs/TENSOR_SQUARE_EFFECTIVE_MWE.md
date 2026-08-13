# Tensor-square Gaussian-HS 与有效 Hamiltonian 最小模型

更新时间：2026-07-29

## 结论先行

这条构造已经形成两个完整、可执行的模型：

1. 连续 Gaussian HS 主模型：允许多个不对易的实对称生成元，并对任意辅助场历史严格
   保证 determinant 非负；
2. 离散双场模型：正 transfer gate 可以精确取 `-log`，得到一个 Hermitian 有效
   Hamiltonian；对角相互作用可精确拆成各阶密度项。

这里确认的是一个严格矩阵机制及其物理映射，不声称发现了新的无符号 Hamiltonian 类。
`m=2` 还具有已知的 conformal split-orthogonal 描述；一般 `m` 仍须继续排查
Majorana positivity 和 contraction-semigroup 条件。

## 任意深度正性

令最终的 base-space 历史为

```text
X = X_1 X_2 ... X_L .
```

物理单粒子空间取为 product lattice `R^m tensor R^m`，每片传播子为
`X_l tensor X_l`。表示性质给出

```text
product_l (X_l tensor X_l) = X tensor X .
```

若 `lambda_i` 是 `X` 的本征值，则

```text
det(I + X tensor X)
  = product_i (1 + lambda_i^2)
    [product_(i<j) (1 + lambda_i lambda_j)]^2
  >= 0.
```

第二部分是实对称多项式的平方。第一部分中，实本征值给正因子；复本征值成共轭对并给出
模平方。因此证明覆盖任意维数和任意历史深度，不依赖有限枚举。

## 连续 Gaussian HS 主模型

定义

```text
K   = dGamma(k tensor I + I tensor k),
Q_a = dGamma(A_a tensor I + I tensor A_a),

H = K - 1/2 sum_a g_a Q_a^2,
```

其中 `k` 和所有 `A_a` 都是实对称矩阵，`g_a >= 0`。对每个 attractive square 使用
标准 Gaussian 恒等式后，一个实场 `s_a` 产生

```text
exp[s_a sqrt(dt g_a) Q_a].
```

其单粒子传播子严格等于

```text
exp(alpha A_a) tensor exp(alpha A_a),
alpha = s_a sqrt(dt g_a).
```

所以不同 `A_a` 即使不对易，按任意 Trotter 顺序相乘后仍是同一个 tensor-square
表示。Gaussian 测度本身为正，配置权重也因此非负。

### 物理内容

- 对角 `A_a`：`Q_a` 是 product lattice 上的集体密度
  `sum_(ij) (a_i+a_j) n_(ij)`；
- 非对角 `A_a`：`Q_a` 是沿两组坐标条带同步作用的 bond operator；
- `Q_a^2` 同时产生密度项、bond-square 和相关 pair hopping。`m=2` 的精确 Fock
  矩阵中，单次 `Q_a` 不能连接两个双占据状态，但 `Q_a^2` 的相应 pair-hopping
  矩阵元等于 `2`。

多个 `Q_a^2` 的有限步长拆分仍有普通 Trotter 误差；正性证明不受该误差影响。

### Kac scaling

product lattice 有 `N=m^2` 个单粒子模式。若 `A_a` 的算符范数随尺寸保持 `O(1)`，
则有限密度下 `Q_a=O(N)`，裸的 `Q_a^2` 是 `O(N^2)`。要保持能量为 `O(N)`，集体耦合
应取

```text
g_a = gbar_a / N = gbar_a / m^2.
```

代码中的 `kac_normalize=True` 明确执行这一缩放。若未来改用局域化或不同归一化的
`A_a`，必须重新检查尺度，不能机械沿用。

## 离散 cosh 与精确 `-log`

取对角 base field `u=(u_1,...,u_m)`，product-lattice 模式 `(i,j)` 的电荷为

```text
q_(ij) = u_i + u_j,
Q_u = sum_(ij) q_(ij) n_(ij).
```

两个 tensor-square 场 `+u`、`-u` 的正系数平均为

```text
T_density = 1/2 [exp(Q_u) + exp(-Q_u)] = cosh(Q_u).
```

它在 occupation basis 中严格正定。加入对称 kinetic sandwich 后，

```text
T = T_K^(1/2) cosh(Q_u) T_K^(1/2)
```

仍为 Hermitian 正定，所以

```text
H_eff = -log(T) / dt
```

是精确定义的 Hermitian Hamiltonian，并满足 `exp(-dt H_eff)=T`。这避免把有限步长
transfer gate 错说成某个未经证明的简单 Hamiltonian 指数。

当 `u=sqrt(dt g) u_0` 且 `dt -> 0` 时，

```text
-log cosh(Q_u) / dt = -g Q_(u_0)^2 / 2 + O(dt),
```

因此离散模型连续地接到上面的 attractive-square 主模型。

## occupation-basis Mobius 分解

对任意 occupation subset `S`，先计算

```text
E(S) = -log cosh(sum_(a in S) q_a) / dt.
```

唯一的多重线性密度展开

```text
E(n) = sum_T J_T product_(a in T) n_a
```

由 subset Mobius transform 给出

```text
J_T = sum_(S subset T) (-1)^(|T|-|S|) E(S).
```

实现对 `m=2` 的 4 个物理模式和 `m=3` 的 9 个物理模式逐项重构，并按 body order
报告项数、非零项数、最大绝对系数与二范数。一般非退化对角场在 `m=3` 已可产生一直到
九体的有效密度项；这不是近似截断，而是完整 `-log cosh` 的精确有限集合展开。

## 新颖性边界

- determinant 正性来自标准 tensor-square 谱配对公式，不应当作新的矩阵定理；
- `m=2` 可归入 conformal split `O(2,2)` 结构，不能主张新正性机制；
- 当前新内容只是把连续 collective-square Hamiltonian、非对角 bond-square/pair
  hopping、离散正 transfer gate 和精确 body-order 分解连成一个 MWE；
- 尚未完成对一般 `m` 的 Majorana、fermion-bag、Pfaffian 和 Wei 2024
  contraction-semigroup 排重；
- 若放开为每个 product-lattice 模式独立的 onsite HS 场，现有精确反例已经给出负权，
  因而绑定的 coordinate-sum 结构是机制的一部分，不是可随意去掉的技术选择。

## 可执行证据

- `oracle/tensor_square_effective.py`：连续模型、任意深度证书、Fock Hamiltonian、
  离散 transfer gate、`-log` 和 Mobius 分解；
- `tests/test_tensor_square_effective.py`：Fock lift、Hermiticity、pair hopping、
  Kac scaling、`m=2/3` 分解和任意深度正性回归。

运行：

```bash
python3 -m pytest -q tests/test_tensor_square_effective.py
```
