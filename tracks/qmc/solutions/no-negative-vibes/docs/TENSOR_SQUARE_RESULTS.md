# Tensor-square 半群与四模式物理闭环

更新时间：2026-07-29

## 一句话结论

`B=X tensor X` 是一个任意维数、任意深度严格非负的 determinant 矩阵类；我们还
构造了一个正系数两场 HS，把它精确映射到四模式方形 hopping 加对角两角排斥作用。
但这个最小局域模型因底矩阵只有 `2 x 2`，严格落回已知 split `O(2,2)` 机制；
可能超出已知类的 `m>=3` 版本则把每个局域操作提升成随系统长度增长的整条行列。

因此：

```text
严格矩阵定理：成功
四模式局域 HS：成功
新的可扩展局域无符号物理类：尚未得到
```

## 1. 任意深度恒正定理

令每个实时间片为

```text
B_l = X_l tensor X_l.
```

Kronecker 乘法立即给出

```text
B_L ... B_1 = X_tot tensor X_tot,
X_tot = X_L ... X_1.
```

若 `lambda_i` 是实矩阵 `X_tot` 的复本征值，则

```text
det(I + X_tot tensor X_tot)
  = product_i (1 + lambda_i^2)
    [product_(i<j) (1 + lambda_i lambda_j)]^2.
```

第二个方括号是实数的平方。第一个乘积中，实本征值给出严格正因子，
非实本征值按共轭对给出 `|1+lambda_i^2|^2`。因此整个权重非负。

`m=2` 时只需迹 `tau=Tr(X)` 和行列式 `delta=det(X)`：

```text
det(I + X tensor X)
  = (1+delta)^2 [(1-delta)^2 + tau^2].
```

这不是普通 two-flavor 权重 `det(I+X)^2`。

## 2. 它严格超出普通 TN/P0

取实旋转

```text
X = [[0,-1],[1,0]].
```

`X tensor X` 的主子矩阵 `{0,3}` 和 `{1,2}` 都有行列式 `-1`，所以不属于
P0/TN；但

```text
det(I + X tensor X) = 0.
```

因此 tensor-square 正性不是“所有主子式非负”的改写。

## 3. 四模式正系数 HS

用四个物理模式

```text
(00), (01), (10), (11)
```

并在两维底空间取

```text
D_+ = diag(exp(lambda), exp(-lambda))
D_- = diag(exp(-lambda), exp(lambda)).
```

四模式一体传播子为

```text
B_+ = D_+ tensor D_+
B_- = D_- tensor D_-.
```

令

```text
kappa = log cosh(2 lambda).
```

直接在 16 维 Fock 空间逐态计算得到精确恒等式

```text
[Gamma(B_+) + Gamma(B_-)] / 2
  = exp[kappa (n_00+n_11-2 n_00 n_11)].
```

右侧对应排斥作用

```text
V = 2 kappa / dt
```

和两个角上的化学势

```text
mu = kappa / dt.
```

再令

```text
K = exp[dt t sigma_x / 2],
X_+ = K D_+ K,
X_- = K D_- K.
```

则每个辅助场仍为 `X_s tensor X_s`，而正系数平均精确等于

```text
Gamma(K tensor K)
exp[kappa (n_00+n_11-2 n_00 n_11)]
Gamma(K tensor K).
```

`K tensor K` 的生成元是四条边

```text
(00)-(01), (00)-(10), (01)-(11), (10)-(11),
```

即一个方形 hopping。于是我们确实得到一个局域、Hermitian、相互作用的四模式
Trotter 顶点，而不只是抽象矩阵。

固定测试点

```text
dt=0.2, t=1.1, lambda=0.6
```

满足：

- 两个 `X_s` 的 commutator norm 为 `0.9468634384`，不是交换模型；
- lifted slice 的最小二阶 minor 为 `-0.4866284690`，不在 ordinary TN；
- 深度 1–8 的全部 `2^1+...+2^8=510` 条历史均严格正；
- 任意深度正性由上面的 tensor-square 定理保证，不依赖这 510 条枚举。

## 4. 为什么这个局域模型仍是已知类

对任意 `2 x 2` 实矩阵定义

```text
epsilon = [[0,1],[-1,0]]
eta = epsilon tensor epsilon.
```

`eta` 是 signature `(2,2)` 的实对称矩阵，而且

```text
(X tensor X)^T eta (X tensor X)
  = det(X)^2 eta.
```

本模型的 `X_+/-` 都满足 `det(X_s)=1`，因此每个时间片严格位于 split
`O(2,2)`。这正是王磊等人提出的 split-orthogonal 无符号原则覆盖的情形：
[Split orthogonal group](https://arxiv.org/abs/1506.05349)。

所以四模式构造虽然物理和 HS 都完整，却不能计作新的无符号物理类。

## 5. `m>=3` 的直接局域性障碍

一般底维数为 `m` 时，一条底图局域边 `h_(ab)` 提升为

```text
h_(ab) tensor I + I tensor h_(ab).
```

它在 `m x m` 乘积图上同时作用 `2m` 条边，而不是一个固定大小 plaquette。

类似地，底空间对角场 `u` 提升为

```text
v_(ij) = u_i + u_j.
```

对最局域的非平凡选择

```text
u = (1,-1,0,...,0),
```

非零 lifted onsite potentials 已有

```text
4m-6
```

个。一个辅助变量会同时关联整条行和整条列，支持随系统长度增长。

具体计数：

| `m` | lifted hopping edges | lifted diagonal support |
|---:|---:|---:|
| 2 | 4 | 2 |
| 3 | 6 | 6 |
| 5 | 10 | 14 |
| 8 | 16 | 26 |

若改成每个乘积格点都有独立 HS 场，就不再保持 tensor-square。已有精确负例：

```text
X1 = [[2,-3],[-3,7]]
X2 = [[4,4],[4,5]]
Z  = diag(16,1,1/8,1/16)

det[I + (X1 tensor X1) Z (X2 tensor X2)]
  = -155085/32.
```

`X1`、`X2` 都是对称正定矩阵。也就是说，“让场真正局域且彼此独立”不是一个
小扰动，而会直接破坏正性机制。

## 6. 当前判定

保留：

- 一般 `m` 的严格 tensor-square determinant 定理；
- ordinary TN/P0 之外的精确非包含例；
- 四模式非交换正系数 HS 和方形相互作用顶点；
- 独立 onsite 场的精确失败证书；
- `m>=3` 条带支持的可扩展性障碍。

降级：

- `m=2` 四模式物理模型属于已知 split `O(2,2)`；
- 直接 `m>=3` product-lattice 解释不是几何局域模型；
- 尚不能把 tensor-square 计入“新的无符号物理类”。

只有找到一种局域拼接，使每个辅助场保持固定大小支持、同时全局历史仍等价于同一个
tensor-square，才值得重新升级这条物理主线。

机器可读证据：

- `oracle/tensor_square.py`
- `tests/test_tensor_square.py`
- `fixtures/tensor_square_certificates.json`
- `protocols/tensor-square-plaquette-v1/`
