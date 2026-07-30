# R3b：局域正交收缩 Hamiltonian

日期：2026-07-30
状态：`active-survivor / conventional-exclusion-and-literature-open`

## 一句话结果

R3 的原 fixed weighted `l_infinity` 类因不对 adjoint 闭合而关闭，但其
transpose-stable 修复在正交边界产生了一个真正存活的 Hamiltonian 类：

> 在重叠四模式 plaquettes 上放置非对易 `SO(4)` Gaussian-unitary vertices，
> 得到局域、extensive、interacting、任意历史无符号，且不能由 occupation-basis
> 对角 `+/-1` gauge 化为 stoquastic 的 fermion Hamiltonian。

其正性属于已知公共二范数收缩机制；按照本轮新标准，这不妨碍模型本身成为物理候选。

## Hamiltonian 家族

对每个四模式 plaquette `p` 选择有限个实 skew generators

```text
K_(p,a)^T = -K_(p,a),  O_(p,a)=exp(K_(p,a)) in SO(4),
```

并把 `O_(p,a)` 以 identity 嵌入全系统单粒子空间。定义

```text
H_L = -sum_(p,a) q_(p,a)
      [Gamma(O_(p,a)) + Gamma(O_(p,a))^dagger],   q_(p,a)>0.    (1)
```

`Gamma(O_(p,a))` 只作用在 plaquette 的四个费米模式，因此 (1) 是局域四模式
Hamiltonian，而不是系统尺度的全局 vertex。允许 plaquettes 重叠，故相邻项一般不对易。

每项算符范数至多 `2q_(p,a)`。若 plaquette 数和每 plaquette atom 数均为 `O(L)`/
常数，且 `q=O(1)`，则 `||H_L||=O(L)`，无需 Kac 缩放。

## 任意历史正性

连续时间展开的每个 oriented vertex 是 `O_(p,a)` 或其转置。任意 word

```text
D = O_1 O_2 ... O_k
```

仍为实正交矩阵。其本征值由 `+1`、`-1` 和复共轭单位圆 pairs 组成，所以

```text
det(I+D)
 = product_(lambda=+1) 2
   product_(complex pairs) |1+lambda|^2
   product_(lambda=-1) 0
 >= 0.
```

Fock trace identity `Tr Gamma(D)=det(I+D)` 因而给任意深度逐历史非负权。QMC 只维护
`N x N` 的一粒子正交乘积，不构造指数维 Fock operator。

## 四模式显式锚点

取 `K_a=0.6 M_a`，

```text
M_0 =
[[ 0, 1,-1,-1],
 [-1, 0, 1, 0],
 [ 1,-1, 0,-1],
 [ 1, 0, 1, 0]],

M_1 =
[[ 0,-1,-1, 1],
 [ 1, 0, 1,-1],
 [ 1,-1, 0,-1],
 [-1, 1, 1, 0]],
```

以及 `q=(1,0.8)`。可执行结果：

- `O_0,O_1 in SO(4)`，orthogonality residual `<1e-15`；
- `||[O_0,O_1]||=1.8153056369...`；
- occupation Möbius audit 有非零四体 coefficient
  `-1.06364126546...`，所以不是二次自由 Hamiltonian；
- 深度 `1–5` 的 1,364 个 oriented words 全部非负，
  最小权严格正，Fock/determinant trace residual `<1e-12`；
- 每个固定粒子数 sector 的 occupation graph 都连通，component sizes 恰为
  `1,4,6,4,1`，没有额外明显静态 sector。

## 对角 stoquastic gauge 的精确障碍

若用 occupation states 的 `+/-1` phases 试图令全部 off-diagonal 元非正，每条边要求

```text
s_i s_j = -sign(H_ij).
```

锚点在 states

```text
8 -> 1 -> 2 -> 4 -> 8
```

形成 sign pattern

```text
(-,-,+,-).
```

四条约束的乘积为 `-1`，故无解。这是有限 plaquette 内的 frustrated sign cycle；
把 plaquette 嵌入更大晶格不会消除该局部障碍。

这已排除 occupation basis 的所有对角实 sign gauges，包括普通 site-sign gauge。
它尚未排除非对角局域 basis change、Majorana/Pfaffian 表示或更强的 classical solver。

## 当前六关

| Gate | 状态 | 证据/缺口 |
|---|---|---|
| `HAMILTONIAN` | pass | 式 (1)，局域四模式 terms |
| `SCALING` | pass | 每项 norm bounded，`O(L)` plaquettes |
| `QMC` | pass | 任意 orthogonal word determinant 非负 |
| `EXCLUSION` | partial | 非二次 + frustrated sign cycle；更强 basis/Majorana 排重待做 |
| `PHYSICS` | open | 需固定二维/ladder geometry、observable 与有限温区 |
| `LITERATURE` | open | 需按“sum of local fermionic Gaussian unitaries/cosine of quadratic”检索 |

## 下一步

1. 在重叠 plaquette ladder 上定义平移不变的两-atom unit cell；
2. 验证局部 sign cycle、四体项和正交 word proof 随尺寸保持；
3. 审计是否可由局部 orbital rotation、Majorana reflection positivity、
   Pfaffian QMC 或 fermionic-linear-optics group algebra直接模拟；
4. 计算最小 ED 的能隙、密度关联和 plaquette current，选择非平凡物理问题；
5. 做模型级文献检索。

这些任务不与协作者的 tensor-square 相图、oddcycle seeds/joint-pair 或 exterior cones
重叠。

## 第二轮传统方法排除

### 固定单粒子 basis 分块：已排除

对四模式锚点的两个 `O_a`，求解共同 commutant

```text
X O_a = O_a X,  a=0,1.
```

对应线性系统 rank `15`、nullity `1`，最小非零奇异值 `0.5910...`；commutant 只有
标量。两个 skew generators 的 Lie closure 维数为 `6=dim so(4)`。因此不存在固定
orbital basis 把两个 atoms 同时分成互不耦合的二模式 rotation blocks。

### generalized JW / free fermions in disguise：该充分可解类已排除

四模式 Hamiltonian 的完整 JW Pauli 展开有 39 个非 identity terms，frustration graph
有 288 条边。它含 induced claw：

```text
center: IIZZ
leaves: IXIX, IYIY, XIXI.
```

三个 leaves 两两对易，却都与 center 反对易。因而 frustration graph 不是 claw-free，
也不可能是 line graph；Elman–Chapman–Flammia 的 `(even-hole, claw)-free`
“free fermions behind the disguise”求解框架不适用。

这比普通 JW 失败更强，但仍不是对所有可能非局域 duality 的复杂性证明。

### matchgate/fermionic-linear-optics：直接 circuit 定理不适用

每个 `Gamma(O_a)` 单独是 Gaussian/matchgate unitary；但 (1) 是这些 unitaries 的
**算符和**，而不是它们的 circuit product 或 quadratic generator。非零四体 coefficient
直接证明完整 `H` 不是 quadratic Hamiltonian。现有 matchgate classical-simulation
定理覆盖 Gaussian circuit composition，不能由此直接模拟 `exp(-beta H)`。

这是一项基于模型结构和已知定理适用范围的判断，不排除另一个专门的 group-algebra
算法。

## 初步文献边界

- Wei 的 contraction-semigroup 框架已经覆盖正性机制，所以不主张新的矩阵/QMC 定理；
- 定向检索尚未找到“重叠局域 plaquettes 上 Gaussian-unitary cosine terms 的和”这一
  具体多体 Hamiltonian 及其有限温相图；
- matchgate 文献研究 Gaussian circuits/states，不等同于这里的 interacting
  sum-of-unitaries Hamiltonian；
- 目前的文献空白仍是初步结论，必须继续查 fermionic Floquet/circuit Hamiltonians、
  group-algebra models 和 Majorana/Pfaffian QMC。

主要锚点：

- Zhong-Chao Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
  simulations*, <https://arxiv.org/abs/1712.09412>
- Elman, Chapman, Flammia, *Free fermions behind the disguise*,
  <https://arxiv.org/abs/2012.07857>
- Jozsa and Miyake, *Matchgates and classical simulation of quantum circuits*,
  <https://arxiv.org/abs/0804.4050>
- Brod, *Efficient classical simulation of matchgate circuits with generalized inputs
  and measurements*, <https://arxiv.org/abs/1602.03539>
