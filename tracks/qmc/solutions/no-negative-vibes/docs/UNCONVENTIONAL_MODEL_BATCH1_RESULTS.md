# 非常规模型第一批结果：一台模型工厂与八种试制品

更新时间：2026-07-29

状态：第一批严格构造的汇总；不修改“确认的新无符号物理类”计数。

## 结论先行

最简单的说法是：

> 我们这次首先得到的不是“八个新的正性矩阵类”，而是一台把已有严格正性批量变成
> Hermitian 相互作用模型的机器；随后用它和几种精确变换造出了八种外观很不寻常的
> 模型。

这批结果已经说明“矩阵正性成立以后，最直接的物理映射不好看”并不是终点。长程、
全局耦合、任意体相互作用、Wilson string、守恒 ancilla 和 pseudo-Hermitian
Hamiltonian 都可以先作为完整对象保留下来，再研究能否约化成更自然的物理。

但当前必须同时说清楚：

- 八种构造都有解析恒等式、任意深度证明或精确变换作为证据，不是只看了少量随机数值；
- 它们复用了 tensor-square、block-TN、graded monomial、TN path 等已有正性来源；
- Wilson gauge、Stark similarity 和 star-to-chain 已有明确的已知约化；
- tensor-square、grade-charge full model 和 adjoint lift 仍有值得排重的模型内容，
  但尚未证明为新的物理类；
- **当前 L3 数量仍为零，不能宣称已经发现新的无符号 Hamiltonian 类。**

这里的三层口径是：

- **L1**：完整模型或 transfer，且权重对任意历史深度严格非负；
- **L2**：再给出精确相似变换、投影、对偶或基变换，把 L1 对象约化到另一个清楚模型；
- **L3**：还具备可控热力学极限、可测量量、算法价值以及未被已知类覆盖的证据。

## 核心结果：正半群到 Hermitian 模型的通用工厂

### 输入

设 `C` 是一族实矩阵，并满足：

```text
1. B,C in C  =>  BC in C;
2. B in C    =>  B^T in C;
3. D in C    =>  det(I+D) >= 0.
```

第三条可以来自任何已经证明的矩阵定理，例如 tensor-square、固定 partition 的
odd block-TN，或其他乘法封闭正性半群。任取有限多个 atoms

```text
B_a in C,    q_a > 0,
```

在数守恒 Fock 空间定义

```text
H_C = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^dagger].     (1)
```

`Gamma(B)` 是单粒子矩阵 `B` 的 Gaussian/Fock lift。由于 `B_a` 为实矩阵，

```text
Gamma(B_a)^dagger = Gamma(B_a^T),
```

所以 (1) 是一个直接定义的 Hermitian、数守恒 Hamiltonian。它通常不是简单的二次
Hamiltonian：`Gamma(B)` 的 occupation/minor 展开可含多种体数，因而 (1) 可以自然
产生长程或一直到全支撑的相互作用。

### 为什么每条历史都非负

连续时间展开为

```text
Z(beta)
 = Tr exp(-beta H_C)
 = sum_(ell>=0) beta^ell/ell!
   sum_(s_1,...,s_ell)
   [product_j q_(a_j)]
   Tr[Gamma(C_(s_1))...Gamma(C_(s_ell))],            (2)
```

其中每个 oriented branch `C_s` 是某个 `B_a` 或 `B_a^T`。式 (2) 中的
`beta^ell/ell!` 和所有 `q_a` 的乘积均非负。另一方面，

```text
Gamma(C_(s_1))...Gamma(C_(s_ell))
  = Gamma(D),

D = C_(s_1)...C_(s_ell) in C,
```

而数守恒 Fock trace 恒等式给出

```text
Tr Gamma(D) = det(I+D) >= 0.                         (3)
```

因此每一个 Taylor word 都有非负权重。这是任意阶、任意传播深度的结论，不需要小
coupling，也不依赖短 word 枚举。代码
`oracle/semigroup_model_factory.py` 独立核对了 (3)、Hermiticity、数守恒性、
tensor-square atoms 到深度 `5` 的 oriented words，以及非对称 TN atom 与其转置到
深度 `7` 的全部 words；对应回归在
`tests/test_semigroup_model_factory.py`。

这里的代码是**条件构造器**，不会替调用者自动证明一个任意输入矩阵属于 `C`。
每组 atoms 的乘法闭包、转置闭包和 determinant 正性必须先由对应的 TN、
tensor-square 或 block-TN 定理提供；否则不能仅因函数成功返回矩阵就声称无符号。

### 这项结果是什么，不是什么

它是一个可复用的 **Hermitian model factory**：

```text
已有乘法半群正性
    -> 选择若干不必局域、也不必对称的 Gaussian atoms
    -> 与各自 adjoint 作正系数和
    -> 得到逐 word 无符号的 Hermitian interacting Hamiltonian.
```

它不是新的 determinant 正性定理；新颖性只能来自工厂生成的 Hamiltonian 是否形成
以前未研究的模型族、是否有好的约化以及是否提供新的算法能力。实际大尺寸算法也应采样
这些 Gaussian vertices，而不是显式构造 `2^N` 维 Fock Hamiltonian。

## 八种第一批构造

| # | 构造与物理外观 | 严格证据 | 当前层级 | 已知机制与新颖性风险 |
|---:|---|---|---|---|
| 1 | **Tensor-square 连续模型**：`H=K-(1/2) sum_a g_a Q_a^2`；`Q_a` 可为集体密度或同步 bond，平方后含 correlated pair hopping | 任意非对易 Gaussian-HS 历史保持 `X tensor X`；谱配对公式解析证明 determinant 非负；Fock、pair hopping、Kac scaling 和 `m=2,3` 回归已编码 | L1；当前最值得向 L3 推进，但尚非 L3 | determinant 机制已知；`m=2` 属 conformal split `O(2,2)`；一般 `m` 的 Majorana / contraction-semigroup 排重未完成 |
| 2 | **Tensor-square 正 transfer 的精确 `-log`**：`T=T_K^(1/2) cosh(Q_u) T_K^(1/2)`，`H_eff=-log(T)/dt`；可产生一直到全系统的密度相互作用 | `T` Hermitian 正定且 `exp(-dt H_eff)=T`；occupation-basis Möbius 变换完整重构，`m=3` 一般可出现一至九体项 | L1；是完整有效模型，不是低阶近似 | 与 #1 共用已有 tensor-square 正性；主要价值是精确 all-body 映射，不是新矩阵类 |
| 3 | **Adjoint lift / difference-coordinate 模型**：对 `det X>0` 取 `B(X)=X tensor X^(-T)`；可形成正的两场 cosh transfer，也可送入通用 Hermitian 工厂 | `B(X)B(Y)=B(XY)`；`det(I+B)=2^m product_(i<j)(lambda_i+lambda_j)^2/(det X)^(m-1)>=0`；保持 swap metric；非对易历史与正定 Hermitian gate 已编码 | L1 transfer；完整模型排重与物理约化未完成 | 它落在带 signature 的 pseudo-orthogonal/adjoint representation 中，极可能与已有 split/Majorana 语言重叠；不能按“新正性机制”申报 |
| 4 | **固定 `C3` odd block-TN**：同步三腿 synthetic ladder；主模型 `H_CT=-sum_a q_a[Gamma(B_a)+Gamma(B_a)^dagger]`，另有 `T_beta`/`-log` 离散版 | fixed-partition block-TN theorem 给任意 Taylor order 正性；六模式实例为 Hermitian、数守恒，并有非零六体密度系数；离散 `T_beta` 严格正定 | L1，需 Majorana/stoquastic 排重 | 正性定理本身已知；独立局域 route 会离开 fixed partition 并碰到已有负权反例；可能只是全局同步 synthetic pulse |
| 5 | **分组 grade-charge ancilla**：一个全局 ancilla、每 patch 一个，或每边一个；每边版本是三模式局域 Hermitian vertex | history weight 精确分解为 `det(I+D_h) product_g[1+(-1)^(k_g)R_g]`，两部分 parity 严格相消；任意图和任意深度成立；正 fugacity 紧边界为 `x_g>=1/min_(e in g) r_e` | full trace 为 L1；全占据 projection 是已知 L2 reduction | 正性仍是 graded monomial factorization；全占据 sector 已知 Majorana-reflection-positive；full Hamiltonian family 是否已有文献先例仍待查 |
| 6 | **Gauss 投影 Wilson-string fermion-gauge model**：fermion hopping 携带随 ordering interval 增长的 `Z2` Wilson compensator，并可加入 plaquette dynamics | Gauss law 把 fermion exchange sign 精确改写成 Wilson phase；每个受约束 hopping/plaquette vertex 在同一 basis 逐元非负；`2x2` 完整 constrained Hamiltonian、`2x3` ladder 与闭合 words 均有精确回归 | L1 + L2 | code-space isometry 精确映到局域 stoquastic kinetically constrained link-spin model；是有用表示，不是新正性机制 |
| 7 | **单向 Stark pseudo-Hermitian 链**：局域非 Hermitian `h_NH=Delta D-g Delta J_+`，可配一个稠密长程 Hermitian Fourier partner | `R_g=exp(gJ_+)` 给 `h_NH=R_g^(-1)(Delta D)R_g`；正 metric `eta=R_g^dagger R_g` 精确满足 pseudo-Hermiticity；history determinant 在固定 similarity 下不变 | L2 calibration；不升级 | imaginary-gauge/Hatano-Nelson 风险高；同一个 `h_NH` 也有对角 Hermitian partner，故“存在长程 partner”本身不构成新物理 |
| 8 | **稠密 star bath 到 endpoint-interacting TN chain**：任意实对称 bath 加单 impurity Hubbard，相互作用在变换后仍留在链端 | 以 impurity 为首 Krylov vector 的正交 Lanczos 变换给 `Q^T h_star Q=h_chain` 且 `kappa(Q)=1`；四轨道 MWE 已检查所有 Hirsch branches 的 minors，并穷举两 spin、深度 `1–4` histories 的 basis-invariant 正权 | L2 calibration；不升级 | 标准 Wilson/Lanczos star-to-chain mapping；作为“长程 Hermitian 模型如何显露 TN 正性”的接口有用，但基本已知 |

## 各构造的关键证据边界

### 1–2. Tensor-square：当前最完整的模型主线

令 base-space 总历史为 `X=X_1...X_L`，则 product lattice 上的历史严格为

```text
X tensor X.
```

若 `lambda_i` 是 `X` 的本征值，

```text
det(I+X tensor X)
 = product_i(1+lambda_i^2)
   [product_(i<j)(1+lambda_i lambda_j)]^2
 >= 0.
```

这使多个不对易实对称 `A_a` 的 Gaussian fields 也能共享同一任意深度证明。连续模型

```text
K   = dGamma(k tensor I + I tensor k),
Q_a = dGamma(A_a tensor I + I tensor A_a),
H   = K - 1/2 sum_a g_a Q_a^2
```

已经展示集体密度、bond-square 和 pair hopping。物理模式数为 `N=m^2` 时，若
`||A_a||=O(1)`，集体耦合应取 `g_a=O(1/N)` 的 Kac scaling 才保持能量 extensive。

离散 `cosh(Q)` 路线则展示了另一种潜力：我们不必先猜一个简单 Hamiltonian，而可从
严格正 transfer 精确取 `-log`，接受它产生高体数相互作用，再寻找其低秩、对称或
低能结构。完整 MWE 与边界见 `docs/TENSOR_SQUARE_EFFECTIVE_MWE.md`。

### 3. Adjoint lift：代数上很整齐，排重风险也很高

对 `det X>0`，

```text
B(X)=X tensor X^(-T)
```

既乘法封闭，也保持 product-space 的 swap metric。其 signature 为

```text
(m(m+1)/2, m(m-1)/2).
```

因此它提供了另一套严格非负 histories 和 Hermitian cosh gate，但这个 metric 同时
强烈提示它并非独立于 pseudo-orthogonal/split 结构。当前应把它当作“新增的精确模型
接口”，而不是“新增的正性锥”。

### 4. Odd block-TN：证明最硬，物理外观最怪

固定三块 partition 下

```text
B=P diag(X_0,X_1,X_2)
```

及其转置始终留在同一个 `C3` block-TN 半群，所以通用工厂直接给出连续时间
Hermitian 模型，无需 `q_a<1/2`。六模式锚点已经出现非零全六体 density coefficient。
如果更适合离散算法，也可取

```text
T_beta=I+beta[Gamma(B)+Gamma(B)^dagger],  0<beta<1/2,
```

并精确定义 `H_eff=-log(T_beta)/dt`。这里真正不可随意放松的是“固定 partition”：
若让各空间位置独立选择 crossed route，正性已经有精确反例。

### 5. Grade-charge：局域性可以用 ancilla 数量购买

每个 grade group 只需记忆其 history parity。一个全局 ancilla 的连接度随系统增长；
每条边各放一个 ancilla 时，每个 vertex 只作用于两个物理模式加一个 ancilla，却要付出
`O(|E|)` 个额外模式。这个 tradeoff 是完整而可执行的模型内容。

不过 full trace 的正性依旧来自已知 graded cycle factor。最值得继续问的是：在不投影
回已知 Majorana sector 的情况下，这个守恒 ancilla Hamiltonian 是否有新的统计物理、
算法或实验解释。

### 6–8. 三个校准对象

这三类对象很有用，但用途是划清边界：

- Wilson gauge 说明 system-size string 可能只是受约束编码的代价，因为投影后模型
  直接 stoquastic；
- Stark chain 说明非 Hermitian 局域模型确实可以相似到长程 Hermitian 模型，但
  Hermitian partner 非唯一，所以不能仅凭“长程 partner 存在”主张新物理；
- star-to-chain 说明一个稠密长程 bath 可通过 unitary Krylov basis 暴露为 TN path，
  但这正是标准 chain mapping。

它们应保留为后续候选的负面对照：新候选若只做到同样的表示变换，就不应升级。

## 当前最值得推进的三个候选

### A. 一般 `m>=3` 的 tensor-square 多通道模型

这是第一优先级。它已经同时具备完整 Hermitian Hamiltonian、多个不对易 HS channel、
任意深度证明、Kac scaling 和可执行 Fock MWE。缺口不是“再跑更多随机 histories”，
而是：

1. 对一般 `m` 做 Majorana positivity、fermion-bag、Pfaffian 与 contraction-semigroup
   的精确包含关系审计；
2. 找到一个已知条件不直接覆盖的最小多通道实例；
3. 选择有清楚 observable 的 subsystem/collective 模型并实现实际采样。

### B. Grade-charge full trace，而不是已知 occupied sector

第二优先级是保留动态或热 trace 中的守恒 grade ancillas，研究它是否仅是已知模型的
分块直和，还是提供了真正不同的可采样 ensemble。重点检查：

1. 小图 Fock diagonal gauge 是否可整体 stoquastic 化；
2. full partition function 是否等价于第二共轭 flavor或模平方；
3. `x_g>=1/r_(g,min)` 的连续 fugacity 区域是否产生有意义的相图或投影极限；
4. 每边 ancilla 的局域版本是否有自然 constraint/gauge 解释。

### C. Adjoint lift 的已知类审计

第三优先级是先排重，再谈模型。需要把 swap metric、Majorana bilinear basis 和
pseudo-orthogonal group 条件写成同一坐标，判断：

```text
adjoint lift
  subset of an existing split/Majorana class?
  or a useful,严格但此前未被单独开采的 structured subclass?
```

即使最终是已知类，它仍可能像 tensor-square 一样产生以前没有写出的差分坐标
collective-square Hamiltonian；但在审计前不能提高新颖性表述。

## 下一轮执行顺序

1. **先做包含关系，不再盲扫。** 对 tensor-square `m=3` 多通道与 adjoint lift 写出
   Majorana/split/contraction 的可判定证书和反证 witness。
2. **给 grade-charge full model 做快速降级测试。** 枚举小图 Fock sign gauges、
   occupation sectors 和 modulus-square factorization；若全部已知，及时停止。
3. **把模型工厂接到实际算法 MWE。** 选择 tensor-square 或 odd block-TN 的一个
   4–9 模式实例，直接采样 vertex words，核对解析 partition function、平均阶数和
   observable，而不是构造大 Fock 矩阵。
4. **量化物理代价。** 对幸存对象记录 support、body order、ancilla density、
   Kac scaling、similarity condition number 和系统尺寸标度。
5. **只在通过排重后讨论 L3。** 若一个对象只有“严格无符号但怪”，保留为 L1；
   若只与已知模型精确等价，保留为 L2 calibration；只有出现独立物理与算法内容才升级。

## 可执行文件索引

- 通用模型工厂：`oracle/semigroup_model_factory.py`，
  `tests/test_semigroup_model_factory.py`
- tensor-square 连续与 `-log`：`oracle/tensor_square_effective.py`，
  `tests/test_tensor_square_effective.py`
- adjoint lift：`oracle/adjoint_lift.py`，`tests/test_adjoint_lift.py`
- odd block-TN：`oracle/odd_block_tn_effective.py`，
  `tests/test_odd_block_tn_effective.py`
- grade-charge：`oracle/grade_charge_model.py`，`tests/test_grade_charge_model.py`
- 固定 similarity、Stark 与 star-to-chain：`oracle/similarity_models.py`，
  `tests/test_similarity_models.py`
- Wilson cocycle 与 constrained Hamiltonian：`oracle/gauge_cocycle.py`，
  `tests/test_gauge_cocycle.py`
- 详细模型卡：`research/U2_U5_UNCONVENTIONAL_MODEL_CARDS.md`，
  `research/U3_U4_LOCALITY_TRADEOFF_MODEL_CARDS.md`

本批相关定向回归为 `90 passed`；包含全部历史证书与既有模块的完整回归为
`350 passed`。有限枚举用于防止实现退化，任意深度结论仍以各节的解析证明为准。

## 已知机制核对入口

- Wang et al., [*Split orthogonal group: A guiding principle for
  sign-problem-free fermionic simulations*](https://arxiv.org/abs/1506.05349)
- Wei et al., [*Majorana positivity and the fermion sign problem of quantum
  Monte Carlo simulations*](https://arxiv.org/abs/1601.01994)
- Mostafazadeh, [*Pseudo-Hermitian Representation of Quantum Mechanics*](https://arxiv.org/abs/0810.5643)
- Chin et al., [orthogonal-polynomial star-to-chain mapping](https://arxiv.org/abs/1006.4507)
- Prior et al., [Lanczos/Krylov chain mapping](https://arxiv.org/abs/1112.6280)

这些文献只支持“哪些风险已知、该往哪里排重”；搜索不到完全相同的模型公式不能作为
首创性证明。

## 最终口径

第一批工作的成果是：

```text
一个通用 Hermitian semigroup model factory
+ 八种严格或精确可约化的非常规模型
+ 三个值得继续排重的候选接口
+ 三个明确告诉我们“什么不算新”的校准对象。
```

它把项目从“遇到不自然的物理映射就停止”推进到“先系统制造、再严格约化和排重”。
当前可以说我们已经建立了探索基础，不能说已经确认了新的 L3 无符号物理类。
