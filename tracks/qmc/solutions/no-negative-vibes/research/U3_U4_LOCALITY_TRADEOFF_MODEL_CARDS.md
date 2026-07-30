# U3/U4 非常规模型卡：固定分块与相似轨道的 locality tradeoff

日期：2026-07-29
状态：理论构造与最小可编码实例；不修改主方向或成果总账。

## 统一口径

本页只开采已经严格成立的两类正性来源：

1. 固定 partition 的 odd block-TN 半群；
2. TN 路径半群及其一个固定相似变换轨道。

因此下面没有新的矩阵正性定理。目标是把同一严格正性写成不同物理外观，并把代价量化：

```text
长程或多体 Hermitian
<-> synthetic-dimension 中的稀疏 Gaussian branches
<-> 局域 pseudo-Hermitian / non-Hermitian
```

每张卡都必须区分：

- 用来证明逐历史正性的 auxiliary branch；
- 真正定义物理配分函数的 transfer/Hamiltonian；
- 相似变换的条件数；
- 单粒子与完整 Fock 空间条件数的不同标度。

---

## 卡 U3-A：同步 `C3` synthetic ladder 与连续时间 Hermitian 模型

### 1. 单粒子 branch

取三个固定 flavor blocks，每个 block 有 `m` 个按路径排列的模式。顺序为

```text
(a=0,x=0..m-1), (a=1,x=0..m-1), (a=2,x=0..m-1).
```

令

```text
P = [[0,I_m,0],
     [0,0,I_m],
     [I_m,0,0]],

D = diag(X_0,X_1,X_2),
B = P D.
```

其中每个 `X_a` 是可逆 TN contraction：

```text
X_a is TN,    ||X_a||_2 <= 1.
```

`B` 是固定 partition 下的 `C3` block-TN 元素。其转置

```text
B^T = D^T P^(-1)
```

也属于同一个 fixed-partition block-TN 半群。

`X_a` 可以由 flavor `a` 上的三对角 Metzler 路径生成元指数得到；`P` 是每个 synthetic
site 上同方向的同步 flavor cycle。关键限制是所有 `x` 共用同一个 route，不能独立选择
方向。后者正是已有 `det(I+XR)=-2` 反例关闭的 crossed-partition 推广。

### 2. 连续时间 Hermitian 主模型

在数守恒 Fock 空间记二次量子化为 `Gamma(B)`。直接定义

```text
H_CT = -sum_a q_a [Gamma(B_a) + Gamma(B_a)^dagger],
q_a >= 0.
```

这里每个 atom

```text
B_a = P^(g_a) diag(X_(a,0),X_(a,1),X_(a,2)),
g_a in {0,+1,-1},
```

都必须使用同一个三块 partition；各 block 是 TN。因为矩阵为实数，
`Gamma(B_a)^dagger=Gamma(B_a^T)`，所以 `H_CT` 是直接定义的 Hermitian、数守恒
Hamiltonian。

这是本卡的主版本。它不要求 `q_a<1/2`，也不需要先造正定 transfer 再取 `-log`。
`Gamma(B_a)` 本身是 Gaussian Fock operator，但把它与 adjoint 相加后当作
Hamiltonian，一般不是二次 Hamiltonian；在 occupation 展开里可一直出现到 `3m`
模式支撑。

### 3. 连续时间的任意阶逐历史正性

对任意 `tau>=0` 作连续时间 Taylor 展开：

```text
Z_CT(tau)
  = Tr exp(-tau H_CT)
  = sum_(ell>=0) tau^ell/ell! Tr[(-H_CT)^ell].
```

把每个幂展开后，每个 history 都是从

```text
{B_1,B_1^T,B_2,B_2^T,...}
```

中取出的一个 word，系数是 `tau^ell/ell!` 与若干 `q_a` 的乘积，全部非负。又因为
这组 atoms 与其转置都在同一个 fixed-partition `C3` block-TN 半群中，

```text
Gamma(B_(s_1))...Gamma(B_(s_ell))
  = Gamma(B_(s_1)...B_(s_ell)),

Tr Gamma(B_(s_1)...B_(s_ell))
  = det(I+B_(s_1)...B_(s_ell))
  >= 0.
```

因此 `Z_CT(tau)` 在任意 Taylor order、任意 propagation depth 都逐 history 非负。
关键是 fixed-partition theorem；短 word 枚举只是代码回归，不是证明。这个结论允许
任意多个共享同一 partition 的 atoms，也没有 coupling 上界。

### 4. 保留的离散 transfer / `-log` 版本

如果算法更适合固定离散时间步，仍可使用单 atom transfer

```text
T_beta = I + beta [Gamma(B) + Gamma(B)^dagger],
0 < beta < 1/2.
```

因为 `||B||_2<=1`，所以 `||Gamma(B)||_2<=1`，从而

```text
(1-2 beta) I <= T_beta <= (1+2 beta) I.
```

这时可定义

```text
H_eff = -(1/dtau) log(T_beta),
Z_L   = Tr[T_beta^L] = Tr[exp(-L dtau H_eff)].
```

每一步展开为 `I,beta Gamma(B),beta Gamma(B^T)`，同一个半群定理保证任意离散深度
非负。`H_eff` 一般有一直到 `3m` 模式支撑的数守恒多体项。这个版本保留下来作为
discrete transfer 实现，而不再承担“必须通过 `-log` 才能得到物理模型”的角色。

### 5. locality tradeoff

```text
Hermitian side:
    H_CT = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^dagger]
    direct, generally all-support/all-body interaction

optional discrete side:
    H_eff = -log T_beta
    generic all-range, all-body interaction

auxiliary/synthetic side:
    X_a generators: nearest-neighbour along x
    P: onsite flavor cycle, but globally synchronized
    one branch cost: O(m)
```

可以把 `P` 看成一束作用于全部 synthetic sites 的全局 clock pulse。若把它拆成每个
`x` 独立的随机局域 route，就离开 fixed partition，并回到已知精确负权边界。

### 6. 条件数与尺寸标度

连续时间正性本身没有小 coupling 条件；代价转移到长虚时间传播的普通谱 conditioning：

```text
kappa_2(exp(-tau H_CT))
  = exp[tau (lambda_max(H_CT)-lambda_min(H_CT))].
```

实际算法应直接采样 Taylor words，而不是显式构造这个 `2^(3m)` 维指数矩阵。

离散版本的单步 transfer 则有尺寸无关界：

```text
kappa_2(T_beta) <= (1+2 beta)/(1-2 beta).
```

`beta=1/4` 时上界为 `3`。branch 的稳定性取决于 `X_a` 的收缩强度，但不需要非酉
similarity metric。

`H_eff` 的矩阵维数同样为 `2^(3m)`，不能靠显式 `-log` 扩到大 `m`；算法必须采样三个
Gaussian branches，而不是构造完整矩阵。

### 7. 六模式最小实例

取 `m=2`：

```text
X_0 = [[1/2, 1/4],
       [1/4, 1/2]],

X_1 = [[3/8, 1/8],
       [1/8, 3/8]],

X_2 = [[2/5, 1/10],
       [1/10, 3/10]],

q = 1,
beta = 1/4.
```

三块均为 SPD、TN contraction。公共单粒子锚点：

```text
||B||_2                         = 0.75
||B B^T - B^T B||_F            = sqrt(581)/50
                                  = 0.482078831727758...
det(I+B)                        = 15193/12800
                                  = 1.186953125
det(I+B B^T)                   = 3705269/1310720
                                  = 2.8268959045410156...
```

连续时间 `H_CT=-[Gamma(B)+Gamma(B)^dagger]` 的 `64 x 64` Fock 锚点：

```text
lambda_min(H_CT)               = -2
lambda_max(H_CT)               = 0.7545228368047133
||offdiag(H_CT)||_F            = 1.916847896776111
full six-density coefficient   = -1.63640625
Tr[(-H_CT)^ell], ell=0..5      =
    (64,
     2.37390625,
     7.711480883789062,
     9.374264806621554,
     18.379026128446057,
     33.852820467751584)
```

离散 transfer 锚点仍为：

```text
lambda_min(T_beta)             = 0.8113692907988211
lambda_max(T_beta)             = 1.5
kappa_2(T_beta)                = 1.8487266119268542
```

非零 commutator 避免了把该实例误当成可交换 `C3` 玩具。实现位于
`oracle/odd_block_tn_effective.py`；测试不仅检查短 word 非负，还逐阶核对
“所有 determinant history 之和”等于直接计算的 `Tr[(-H_CT)^ell]`。

### 8. 已知类风险与停止条件

- **odd block-TN**：正性就是已有定理；不能申报新机制。
- **synthetic dimension / Floquet**：同步 `C3` pulse 很可能只是标准三腿 synthetic
  ladder 的非幺正 Euclidean 写法。
- **stoquastic/loop**：需分别对六模式 `H_CT` 和 `H_eff` 枚举 onsite/Fock diagonal
  gauges；若可逐元 stoquastic 化，则降级。
- **Majorana**：每个 branch 是 Gaussian，但直接的 `H_CT` 和正和后的 `H_eff` 都是
  interacting operator。需检查它们是否整体落入 Majorana reflection positivity；
  若是，降级。
- **局域性停止线**：若要求独立局域 route 才能解释物理实验，则本卡不能越过已有
  crossed-partition `-2` 反例，只保留为全局 clock 模型。

---

## 卡 U4-A：单向 Stark-TN 链与稠密 Hermitian Fourier partner

### 1. 局域非 Hermitian Hamiltonian

令

```text
D_N = diag(0,1,...,N-1),
J_+ = sum_(j=0)^(N-2) |j><j+1|,
R_g = exp(g J_+).
```

因为 `[J_+,D_N]=J_+`，

```text
R_g^(-1) (Delta D_N) R_g
  = Delta D_N - g Delta J_+.
```

定义

```text
h_NH = Delta D_N - g Delta J_+,
H_NH = sum_(ij) c_i^dagger (h_NH)_ij c_j.
```

它只有 onsite Stark ramp 和一个方向的最近邻 hopping，是稀疏局域非 Hermitian
Hamiltonian。Euclidean generator

```text
A = -dtau h_NH
```

的唯一非对角方向为 `+dtau g Delta J_+`；当 `g Delta>=0` 时它是三对角 Metzler，
所以 `exp(A)` 是 TN。

### 2. 稠密 Hermitian partner

令 `F_N` 为离散 Fourier 矩阵，取

```text
h_H = F_N (Delta D_N) F_N^dagger,
S   = F_N R_g.
```

则

```text
h_NH = S^(-1) h_H S.
```

`h_H` 是 Hermitian、circulant 且全连接。若 `r=x-y mod N`，

```text
(h_H)_(xx) = Delta (N-1)/2,

(h_H)_(xy) = -Delta/[1-exp(2 pi i r/N)],   r != 0.
```

其 hopping 大小为

```text
Delta/[2 |sin(pi r/N)|].
```

所以同一个谱既可以解释为：

```text
局域单向 non-Hermitian Stark chain
<-> 长程 chiral Hermitian ring.
```

### 3. pseudo-Hermitian metric

按 `h_NH=S^(-1)h_H S` 的约定，

```text
eta = S^dagger S = R_g^dagger R_g > 0,
h_NH^dagger eta = eta h_NH.
```

Fourier unitary完全消失于 metric，说明 Hermitian partner 的“对角”或“稠密 Fourier”
外观并不唯一；真正决定非 Hermitian 内积的是 nilpotent shear。

### 4. 任意深度正性

静态自由模型直接有

```text
Z_L = det[I + exp(-dtau h_NH)^L] >= 1
```

因为每片都是 TN。更一般地，只要所有时间片仍为

```text
A_l = diagonal_l + t_l J_+,   t_l>=0,
```

任意 product 都 TN，逐历史正性仍成立。

但是时间依赖的任意 diagonal auxiliary fields 一般不共享上面的固定 `eta`。此时可以
继续声称 TN transfer model，不能继续声称同一个封闭 pseudo-Hermitian Hamiltonian。

### 5. 条件数与尺寸标度

因为 `||J_+||_2=1`，

```text
||R_g||_2 <= exp(|g|),
||R_g^(-1)||_2 <= exp(|g|),
kappa_2(S) <= exp(2|g|),
kappa_2(eta) <= exp(4|g|).
```

这些单粒子界与 `N` 无关。代价出现在完整 Fock metric：

```text
kappa(Gamma(S)) <= kappa(S)^N,
kappa(eta_Fock) <= kappa(eta)^N,
```

所以固定 `g` 时最坏情形仍可随粒子数指数恶化。

另一个热力学代价是 Stark bandwidth 为 `Delta(N-1)`。若把 `Delta` 缩成 `1/N` 保持
bandwidth 有界，同时保持 `g=t/Delta` 固定，则单向 hopping 也缩成 `1/N`。若 hopping
保持常数，则 `g=O(N)`，metric condition number 转为指数恶化。

### 6. 四模式最小实例

取

```text
N=4, Delta=1, g=1/2,

h_NH =
[[0,-1/2,0,0],
 [0,1,-1/2,0],
 [0,0,2,-1/2],
 [0,0,0,3]],

R =
[[1,1/2,1/8,1/48],
 [0,1,1/2,1/8],
 [0,0,1,1/2],
 [0,0,0,1]].
```

Fourier partner 为

```text
h_H =
[[ 3/2, -(1-i)/2, -1/2, -(1+i)/2],
 [-(1+i)/2, 3/2, -(1-i)/2, -1/2],
 [-1/2, -(1+i)/2, 3/2, -(1-i)/2],
 [-(1-i)/2, -1/2, -(1+i)/2, 3/2]].
```

数值锚点：

```text
kappa_2(S)   = 2.240537807163964
kappa_2(eta) = 5.020009665331104
```

当前工作区的 `oracle/similarity_models.py::stark_similarity_model` 已实现同一证书。

### 7. 已知类风险与停止条件

- **Hatano-Nelson / imaginary gauge**：单向 hopping 与非酉 gauge 是最直接的先例风险；
  线性 Stark ramp 只让 shear metric 得到特别简单的闭式。
- **pseudo-Hermitian 非唯一性**：Fourier partner 的长程性可以通过另一个 unitary
  描述消掉，不能把它冒充新物理。
- **Jordan-Wigner / stoquastic**：`h_NH` 的 Euclidean generator在 path ordering 中
  已是 TN/逐元 cooperative；它是已知一维结构。
- **Majorana**：自由数守恒模型无需 Majorana 解释；加入 interacting HS 后必须重新排重，
  且固定 metric 通常失效。
- **停止线**：本卡最多是一个条件数可控的 L2 locality-duality 证书，不应升级为新的
  sign-free Hamiltonian 类。

---

## 卡 U4-B：稠密 Hermitian bath 的 unitary star-to-TN-chain impurity 模型

### 1. 原始长程 Hermitian Hamiltonian

取一个 spinful interacting impurity `d`，连接任意实对称 bath：

```text
H_star =
  sum_sigma c_sigma^dagger h_star c_sigma
  + U (n_(d,up)-1/2)(n_(d,down)-1/2),
U>=0.
```

`h_star` 可以是稠密矩阵：impurity 同时连接 `O(N)` 个 bath orbitals，bath 内部也可
全连接。要求两个 spin flavor 共享同一个实 `h_star`。

### 2. 固定 unitary Krylov/Lanczos 变换

以 impurity orbital `|d>` 为第一个 Krylov vector，对 `h_star` 做 Lanczos：

```text
Q^T h_star Q = h_chain,
Q e_0 = e_d,
```

其中

```text
h_chain =
diag(alpha_0,...,alpha_(N-1))
- sum_j beta_j (|j><j+1|+|j+1><j|),
beta_j>0.
```

必要时使用交替符号 gauge 固定负 hopping。因为 `Q` 保持第一个 orbital，

```text
n_(d,sigma) = n_(0,sigma),
```

所以 onsite Hubbard interaction 不会被变成长程相互作用。

### 3. 完整 auxiliary-field transfer

使用 Hirsch field：

```text
exp[-dtau U(n_up-1/2)(n_down-1/2)]
 = C sum_(s=+-1) exp[lambda s(n_up-n_down)],

cosh(lambda)=exp(dtau U/2),   C>0.
```

每个 spin 的 chain-basis 时间片为

```text
B_(l,sigma) =
 exp(-dtau h_chain/2)
 exp[sigma lambda s_l |0><0|]
 exp(-dtau h_chain/2).
```

`-h_chain` 是三对角 Metzler，中间因子为正对角，所以每个 `B_(l,sigma)` 是 TN。
因此每个 spin determinant 单独满足

```text
det[I + product_l B_(l,sigma)] >= 1.
```

回到 star basis：

```text
B_star = Q B_chain Q^T.
```

它通常稠密且不 TN，但固定 unitary similarity 保持每条历史的 determinant weight。

### 4. locality tradeoff 与条件数

```text
physical/star basis:
    Hermitian, dense or long-range bath
    interaction only on impurity

synthetic/Krylov basis:
    Hermitian nearest-neighbour chain
    interaction remains at chain endpoint
    TN proof manifest
```

这里

```text
kappa_2(Q)=1,
eta=I.
```

不存在 pseudo-Hermitian conditioning 代价。代价是 orbital locality：一个 chain orbital
通常是 `O(N)` 个原 bath orbitals 的线性组合，局域 bath observable 会变成 dense。

Lanczos 构造需 `O(N^2)` dense matvec work；若原 bath 稀疏，则约为 `O(N E)`。若 Krylov
提前 breakdown，模型分裂成若干独立 paths，TN 结论仍保持。

### 5. 四 orbital 最小实例

先定义 synthetic chain

```text
h_chain =
[[ 0,-1, 0, 0],
 [-1,0.4,-0.8,0],
 [0,-0.8,0.9,-0.6],
 [0,0,-0.6,1.5]].
```

取 `Q=1 direct_sum U_3`，其中

```text
U_3 =
[[1/sqrt(3),  1/sqrt(2),  1/sqrt(6)],
 [1/sqrt(3), -1/sqrt(2),  1/sqrt(6)],
 [1/sqrt(3),          0, -2/sqrt(6)]].
```

则 `h_star=Q h_chain Q^T` 数值为

```text
[[ 0,       -0.577350,-0.577350,-0.577350],
 [-0.577350,-0.166274,-0.066667,-0.346855],
 [-0.577350,-0.066667, 1.832941,-0.386478],
 [-0.577350,-0.346855,-0.386478, 1.133333]].
```

impurity 等幅连接三个 bath orbitals，bath block 本身稠密；但同一个 `Q` 精确恢复局域
chain，并保持 impurity interaction。

该实例已由
`oracle/similarity_models.py::build_star_to_chain_impurity_mwe` 编码。回归穷举两个
spin、深度 `1–4` 的全部 Hirsch histories，检查 chain basis 的全部 minors 非负，
并逐 history 核对 star/chain determinant 完全相同。

### 6. 已知类风险与停止条件

- **Wilson/Lanczos star-to-chain**：这是标准 impurity/open-system chain mapping 的直接
  应用，先例非常强；只能作为 L2 模型卡和 TN 物理接口。
- **Jordan-Wigner / stoquastic**：在 Krylov basis 中就是一条开放链，物理上完全符合已知
  一维消号直觉。
- **Kramers/Majorana**：两个 spin flavor 共享 bath 时可能另有平方或时间反演解释；
  本卡应强调每个 spin determinant 已由 TN 单独保正，不能据此声称新类。
- **多 impurity 停止线**：若相互作用支撑在多个不能同时作为 block-Lanczos 首块保留的
  orbitals，上述标量 path 证明会变成 block chain；必须重新检查 block-TN，而不能直接
  外推。

相关已知 chain-mapping 文献：

- <https://arxiv.org/abs/1006.4507>
- <https://arxiv.org/abs/1112.6280>

---

## 三卡比较

| 卡 | 严格正性来源 | Hermitian 端 | 稀疏/局域端 | conditioning | 当前等级 |
|---|---|---|---|---|---|
| U3-A | fixed `C3` block-TN | 直接 `H_CT`；可选 `-log T_beta`，长程多体 | synthetic ladder Gaussian branches | CT 无小耦合条件；离散 `kappa(T)` 尺寸无关 | L1，需排重 |
| U4-A | TN 路径 + 固定 similarity | 稠密 chiral long-range ring | 单向 Stark chain | 单粒子有界；Fock 最坏指数 | L2/已知风险高 |
| U4-B | TN 路径 + unitary orbit | 稠密 interacting star bath | endpoint-interacting Wilson chain | `kappa(Q)=1` | L2/基本已知 |

## 建议执行顺序

1. 先以已编码的六模式 `H_CT` 为主做 Fock gauge、Majorana 和 body-support 分解；
   `T_beta/-log` 只作为离散 transfer 对照；
2. 直接复用现有 `similarity_models.py` 完成 U4-A 的尺度表，不再另写重复 oracle；
3. U4-B 的四 orbital 回归和已知文献标签已经完成，不投入大扫描；
4. 若 U3-A 也约化为 stoquastic/Majorana，则 U3/U4 的主要产物应定位为清楚的
   locality/conditioning tradeoff，而不是新无符号类。
