# 激进候选首批结果：奇数阶路由与宇称分辨 Majorana

更新时间：2026-07-28

## 一句话结论

首批曾得到两个值得继续追、但物理映射尚未完成的结构：

1. **奇数阶 positive-monomial / block-TN 路由半群**：有任意深度的一般正性证明，
   包含 ordinary TN 之外的矩阵，也不能由固定 Kramers 或公共范数收缩解释；
2. **Majorana reflection-positive cone 的宇称分辨规律**：640 条 auxiliary-field 历史
   在 canonical convention 下完全符合 `pi_*=(-1)^[m(m+1)/2]` 的受保护扇区猜想；
   每条历史分别计算 even、odd 和完整 Fock 迹，另一扇区在每个测试维数都观察到数值负权。

后续排重和局域闭环已经改变第一项的判断：

- monomial cycle-factor 是已知特征多项式公式的直接推论，矩阵端不再主张新定理；
- 固定 block partition 的正性定理仍成立；
- independent local `C3` routes 与 crossed TN hopping 已有六模式、两层、整数矩阵
  反例 `det(I+XR)=-2`，自然局域物理推广关闭。

因此 odd monomial / block-TN 已降为 `math-only / natural-local-closure-falsified`。
第二项仍只是高质量数值猜想。两者都不能声称新的物理无符号模型。

同时，四个看似自然的放松全部被淘汰：

- 偶阶 monomial 路由；
- 每片改变收缩范数；
- reciprocal-parabolic 的双向反馈；
- “几乎可交换”的时间片并集。

split `D_4` Lusztig 锥也零负例，但它整体位于已知 `SO(4,4)` split-orthogonal 恒等分支，
不是新机制。

## 固定 determinant 扫描

协议：
[`speculative-structures-v1`](../protocols/speculative-structures-v1/README.md)。

- 12 个候选或边界对照；
- 维数 3–8；
- 深度 `2,3,4,8,16`；
- 尺度 `0.5,1,2,3`；
- 四个固定种子；
- 每格 200 个权重；
- 960/960 格成功，合计 192,000 个 determinant 权重；
- 全部结构残差小于 `7.3e-16`；
- 正式扫描约 96 秒本机墙钟时间。

| 结构 | 样本 | 负权 | zero | uncertain | 首批判断 |
|---|---:|---:|---:|---:|---|
| `odd_monomial_c3` | 16,000 | 0 | 0 | 176 | `rigorous_survivor` |
| `odd_monomial_c5` | 16,000 | 0 | 0 | 528 | `rigorous_survivor` |
| `odd_block_tn_c3` | 16,000 | 0 | 228 | 1,714 | `rigorous_survivor` |
| `even_monomial_v4` | 16,000 | 5,500 | 1,032 | 31 | `falsified` |
| `linf_contract4` | 16,000 | 0 | 0 | 0 | `rigorous_survivor`，但属于公共范数收缩 |
| `linf_moving_metric4` | 16,000 | 4,542 | 0 | 0 | `falsified` |
| `reciprocal_parabolic4` | 16,000 | 0 | 0 | 226 | `rigorous_survivor`，三角因子化闭包 |
| `reciprocal_bicoupled4` | 16,000 | 3,894 | 2 | 581 | `falsified` |
| `lusztig_d4_positive` | 16,000 | 0 | 307 | 2,071 | `known_reduction` |
| `lusztig_d4_signed` | 16,000 | 0 | 17 | 803 | `known_reduction` |
| `commuting_dense4` | 16,000 | 0 | 0 | 17 | `rigorous_survivor`，可积对照 |
| `near_commuting4` | 16,000 | 846 | 4 | 143 | `falsified` |

`uncertain` 是 `I+D` 在 float64 下过度病态；`zero` 是 float64 `slogdet` 返回精确零。
两者都不用于支持正性。特别是 odd block-TN 的定理给出严格正权，其 228 个 `zero`
只能是浮点乘积的数值坍缩；V4 则允许真实零权。所有严格幸存者的结论来自下面的一般证明，
不依赖这些病态样本。

## 数学幸存、物理降级：奇数阶 positive-monomial 半群

### 定义

令 `G` 是奇数阶置换群，允许的有限单粒子传播子为

```text
B = P_g diag(d_1,...,d_n),   g in G,   d_i>0.
```

两个这种矩阵的乘积仍是正 monomial 矩阵，最终 permutation grade 仍在 `G` 中。

### 三行证明

奇数阶群中每个元素的阶都是奇数，所以它的每个置换循环 `C` 都有奇数长度。一个加权
循环块满足

```text
det(I+B_C) = 1 - (-1)^|C| product_{i in C} d_i
           = 1 + product_{i in C} d_i > 0.
```

不同循环分块因子化，因此任意深度都有

```text
det(I+B) = product_C [1 + product_{i in C} d_i] > 0.
```

等价地，所有非零主子式都来自若干完整奇循环，且每个奇循环 permutation 的符号为正，
所以最终矩阵是 `P0`，`det(I+B)` 是全部主子式之和。

### 它确实能写成 QMC 时间片

奇长度正加权循环的本征值是一个正数的奇次根：有一个正实根，其余成非实共轭对，没有
负实本征值。矩阵非奇异，因此存在实矩阵对数 `A`，可以写成 `B=exp(A)`。

生成器通过正 lognormal 权和可逆双对角分解保证严格可逆；结构 residual 只审计
monomial/TN pattern，不单独证明可逆性。回归测试对代表样本调用 `real_log_audit`，并用
“实 permutation 对数 + TN block-diagonal 对数”两个实指数 witness 重构原 factor。
即使把一个 macro-factor 拆成两个普通时间片，正性定理仍覆盖整条序列。

### 为什么不是已有结果的明显换皮

- **不是 ordinary TN**：三循环

  ```text
  P = [[0,0,1],
       [1,0,0],
       [0,1,0]]
  ```

  的 rows `(0,1)`、columns `(0,2)` 二阶子式为 `-1`；
- **不是固定 Kramers**：类包含全部正对角矩阵。与全部正对角矩阵对易的任意固定复矩阵
  `J` 都只能是对角矩阵，因此 `J conjugate(J)=diag(|J_ii|^2)` 不可能等于 `-I`；
- **不是公共范数收缩**：类包含 `dI`，且 `d` 可大于 1，所以任何矩阵范数都有
  `||dI||>=rho(dI)=d>1`；
- **不是固定换基后的 TN**：三循环的本征值包含
  `exp(+/- 2 pi i/3)`，而 TN 矩阵的本征值为非负实数。相似变换保谱，因此不存在一个
  固定相似变换把整个类送进 TN。

后续文献核对确认，monomial 矩阵的特征多项式按 permutation cycles 分解是已知结果；
上述正性是对奇数阶群和正权的直接推论。因此它仍是正确的 QMC 证书，但不作为新的矩阵
定理主张。

### block-TN 推广

把正标量换成可逆 TN 块 `X_i`。一个长度为 `ell` 的块循环贡献

```text
det[I + (-1)^(ell-1) X_ell...X_1].
```

`ell` 为奇数时，这就是 `det(I+X_ell...X_1)`。TN 乘法闭合，后者等于所有主子式之和，
因此非负。首批 `C3`、每站 `2 x 2` 可逆 TN 块的 16,000 个样本零稳定负权。

实对数链也闭合：块循环的 `ell` 次幂在对角块上给出可逆 TN 乘积，其谱为正实数；奇数
`ell` 因而不可能让原块循环产生负实本征值。按照 Culver 的 real-log criterion，该实
可逆矩阵存在实对数。奇异 TN 只属于数学闭包边界，不是本轮 `B=exp(A)` 生成器的一部分。

这条推广曾被认为可能把一维 TN 传播通过离散奇循环 HS 变量进行路由。后续
[局域闭环审计](ODD_BLOCK_TN_LOCALITY_AUDIT.md)表明：让路由在每个格点独立局域化，
再用 flavor-preserving TN hopping 连通格点，会在最短两层产生精确负权 `-2`。
固定全局 block partition 的定理未被否定，但尚无自然局域 Hamiltonian。

## 四个被击穿的边界

### 偶阶路由

`V4` 的原子时间片只取正对角矩阵或无权双换位置换；每个原子都各自有实矩阵对数。两个
合法原子已经足以给出显式反例。取

```text
P = (0 1)(2 3),
Delta = diag(q,q,q^(-1),q^(-1)),
```

则

```text
det(I + P Delta)
  = (1-q^2)(1-q^(-2)).
```

`q=2` 时精确等于 `-9/4`。因此关键条件不是“monomial”本身，而是所有最终循环都必须为
奇长度。

### 80 位重放

正式扫描为每个失败族选择条件数最好的代表负例，并用 80 位算术重放：

| 失败族 | 代表格 | 80 位权重 |
|---|---|---:|
| `even_monomial_v4` | `cell-0173` | `-2.7597417428786535202...` |
| `linf_moving_metric4` | `cell-0475` | `-4.8440548787550050717...` |
| `reciprocal_bicoupled4` | `cell-0599` | `-0.43537531182142624176...` |
| `near_commuting4` | `cell-0941` | `-0.71634399847612158855...` |

四个例子的 `sigma_min(I+D)` 分别约为 `0.912,0.994,0.385,0.508`，都远离零，不是
浮点翻号。

由此得到三个一般边界判断：

- 每片分别在某个收缩范数中稳定，不代表整条时间序列有公共范数；
- reciprocal spectrum pairing 一旦打开任意 lower-block feedback 就会消失；
- 每片各自属于一个可交换代数，不代表两个相近可交换代数的并集仍安全。

## 严格幸存但不作为新核心

### 固定加权 `l_infinity` 收缩

固定 `h_i>0` 并要求

```text
a_ii + sum_{j!=i}|a_ij|h_j/h_i <= 0
```

时，所有时间片在同一个加权无穷范数下收缩。最终实传播子的谱半径不超过 1；实负本征值
只能在 `[-1,0]`，复本征值成共轭对，所以权非负。这是一个允许稠密带符号图的严格大类，
但物理上很可能对应强衰减/低密度区，数学机制仍是公共收缩。

### reciprocal-parabolic

对

```text
A = [[H,Q],[0,-H^T]]
```

任意指数乘积为 `[[X,Y],[0,X^(-T)]]`，且 `det X>0`，所以

```text
det(I+D) = det(I+X)^2 / det(X) >= 0.
```

它允许任意单向 nilpotent decoration，但正性只看对角块，属于有用闭包而非首选新机制。

### 稠密可交换代数

若所有 `A_l` 对易，乘积就是 `exp(sum_l A_l)`；单个实矩阵指数的 `det(I+exp S)` 总是
非负。这个严格对照证明 oracle 能保留稠密非对称正例；轻微换到另一个可交换 frame 后，
846 个负权立即说明“近似对易”没有保护。

### `D_4` 为什么降级

真正的八维 `D_4` simple-root 生成元满足同一个

```text
A^T eta + eta A = 0,
eta = [[0,I_4],[I_4,0]].
```

无论根系数是否非负，时间片及其乘积都留在 split `SO(4,4)` 恒等分支。因此 32,000 个
Lusztig/signed 样本的零负例只是复现主办方已知 split-orthogonal 机制；本结果无需诉诸
canonical-basis positivity，也不给新 QMC 类。

## Majorana 宇称分辨首批结果

协议：
[`majorana-parity-v1`](../protocols/majorana-parity-v1/README.md)。

在同一个已知 Majorana reflection-positive cone 中，代码直接构造 Fock/Spin 表示并分别
计算

```text
Z_even/odd = Tr[(1 +/- (-1)^F) U] / 2.
```

每次矩阵乘法后的归一化因子都是正实数，不改变符号。固定参数为深度 4、尺度 3、种子
`20260728`，每个模式数 128 条历史。公式和 even/odd 标签只针对 canonical `J1/J2`、
当前 Jordan-Wigner Majorana 排序与取向；orientation-reversing Majorana 重排可以交换
两个标签：

| 复费米模式 `m` | 猜想保护扇区 | 保护扇区负权 | 另一扇区负权 | 完整迹负权 |
|---:|---|---:|---:|---:|
| 2 | odd | 0/128 | 39/128 | 0/128 |
| 3 | even | 0/128 | 51/128 | 0/128 |
| 4 | even | 0/128 | 34/128 | 0/128 |
| 5 | odd | 0/128 | 48/128 | 0/128 |
| 6 | odd | 0/128 | 32/128 | 0/128 |

全部 640 条历史中：

- 完整 Fock 迹全部正，复现已知 Majorana positivity；
- 猜想扇区全部正；
- 互补扇区累计 `204/640` 个负权；
- 0 complex、0 uncertain。

在这个 canonical convention 下，观察到的受保护宇称正好是

```text
pi_* = (-1)^[m(m+1)/2].
```

这可能来自 Majorana 反射在 Fock top form 上的取向符号，但目前没有证明。它也不是
“两个宇称扇区都正”：互补扇区在本协议中已经观察到离零约 `0.02–0.05` 的 normalized
float64 负权，但尚未做任意精度重放。如果能从 2016 reflection-positivity 证明中推出
这个分扇区命题，它会是一个有用的新 ensemble/parity 定理；如果不能，就继续加深/扩维
寻找猜想扇区反例。

## 当前优先级

| 方向 | 数学状态 | 新颖性状态 | 物理状态 |
|---|---|---|---|
| odd monomial / block-TN | 固定分块已有一般证明 | 底层公式已知 | 自然局域闭包有精确反例 |
| Majorana protected parity | canonical convention 下 640 条零失败猜想 | 有希望，需解析证明 | 可直接关联固定宇称 ensemble |
| fixed `l_infinity` | 已有一般证明 | 公共范数收缩，优先级低 | 可能只是强衰减区 |
| reciprocal parabolic | 已有一般证明 | 三角闭包，优先级中低 | 尚无自然模型 |
| `D_4` Lusztig | 已有已知 split 证明 | 已排重 | 不推进 |
| commuting dense | 已有一般证明 | 可积对照 | 不推进 |

接下来的真正门槛不是再把样本数乘十，而是：

1. odd/block-TN 转为存档和回归边界，不继续常规局域化；
2. 证明或推翻 Majorana 宇称公式；
3. 把 spinor-Metzler 或非诱导 exterior-cone 做成非已知机制的可行锥；
4. 只有出现 constrained gauge/ancilla 新机制时才重新打开 block-TN。

## 复现与代码

- 候选定义与停止条件：
  [`SPECULATIVE_CANDIDATE_BATCH.md`](SPECULATIVE_CANDIDATE_BATCH.md)
- monomial 生成、实对数审计与精确 V4 反例：
  `oracle/monomial_candidates.py`
- 其余 determinant 候选：
  `oracle/speculative_candidates.py`
- 通用扫描与 direct-factor 支持：
  `oracle/scan.py`
- Majorana 宇称直接迹：
  `oracle/majorana_parity.py`
- 机器可读宇称首批结果：
  `fixtures/majorana_parity_survey.json`
- 回归测试：
  `tests/test_monomial_candidates.py`、
  `tests/test_speculative_candidates.py`、
  `tests/test_majorana_parity.py`

完整逐格 manifest、CSV 和图按 harness 约定保存在本地
`tracks/qmc/results/no-negative-vibes/speculative-structures-v1/`，不提交 Git。协议、种子、
代码、汇总数字和显式反例均提交，因此合作者可完整重跑。

## 文献边界

- Culver, *On the existence and uniqueness of the real logarithm of a matrix*,
  Proc. AMS 17 (1966): <https://doi.org/10.1090/S0002-9939-1966-0202740-6>
- Fomin and Zelevinsky, *Totally nonnegative and oscillatory elements in
  semisimple groups*: <https://arxiv.org/abs/math/9811100>
- Wei et al., *Majorana positivity and the fermion sign problem of quantum
  Monte Carlo simulations*: <https://arxiv.org/abs/1601.01994>
- Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
  simulations*: <https://arxiv.org/abs/1712.09412>
- Han, Wan, and Yao, *Pfaffian quantum Monte Carlo*:
  <https://arxiv.org/abs/2408.10311>
