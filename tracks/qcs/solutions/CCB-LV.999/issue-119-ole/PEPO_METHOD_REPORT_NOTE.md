# 49-qubit Operator Loschmidt Echo：PEPO/Heisenberg-picture 方法报告

更新日期：2026-07-29

对应任务：Quantum Harness issue #119

状态：方法实现与 49-qubit 执行链验证通过；`Dop=512` 的经验误差已达标，最大角点仍缺直接 `χenv` 截面

## 1. 摘要

本工作使用有限尺寸的 projected entangled-pair operator（PEPO）在
Heisenberg picture 中计算 49-qubit operator Loschmidt echo（OLE）：

```text
F = 2⁻⁴⁹ Tr[O C† O C]
O = Z52 Z59 Z72
```

这里不构造 2⁴⁹ 维量子态，也不随机采样初态。算法从局域 Pauli 算符 `O` 出发，
沿电路的反向光锥演化 `C† O C`，将演化后的算符压缩成有限键维的 PEPO；随后把
它与原始 `O` 做归一化 Hilbert–Schmidt 内积。

当前最大参数点为：

```text
Dop = 512
χenv = 64
FPEPO = 0.8225508376024053
```

该值与本次 BP-TN 均值 `0.8183229131612796` 相差 `0.0042279244`，与公开
BP-TN `χ=512` 中心值 `0.8216584890` 相差 `0.0008923486`。`Dop=384→512`
的变化已经降到 `0.0001970707`，只有前一步的约 19.50%；加上继承自
`Dop=128` 的环境变化 proxy 后，`εPEPO=0.0002108962<10⁻³`。但最大角点
没有直接的 `χenv` 截面，因此当前结论是：

> PEPO 的 `Dop` 方向已经通过经验精度目标，但尚未完成最大角点的双参数内部收敛；
> 不能因为有限 `Dop` 接近某个 BP-TN 中心值就宣称 baseline benchmark 已通过。

## 2. 问题定义

### 2.1 输入电路

计算使用经过审计的 49-active-site OpenQASM 2 电路：

| 项目 | 值 |
| --- | --- |
| active sites | 49 |
| circuit layers | 73 |
| CZ gates | 648 |
| 扰动参数 | `δ=0.15` |
| 扰动门 | 24 个已审计的 `Rz(0.3)` |
| observable | `O=Z52 Z59 Z72` |
| QASM SHA-256 | `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455` |

代码同时支持 `δ=0` 控制：它不会换用另一份电路，而是把审计到的 24 个
`Rz(0.3)` 扰动角替换为零。这样可以保持其余门序列完全一致。

### 2.2 目标量的物理含义

令 `C` 为完整量子电路，`O` 为局域 Pauli 乘积。Heisenberg 演化后的算符为

```text
O_H = C† O C
```

OLE 是原始算符和演化后算符的归一化 Hilbert–Schmidt overlap：

```text
F = 2⁻ᴺ Tr[O O_H],  N=49
```

直观上：

- `F≈1`：演化后的算符仍与原始算符高度相似；
- `F≈0`：算符已经传播并失去与原始局域结构的 overlap；
- 本问题中的 `F` 是确定性 trace，不依赖随机 seed。

## 3. 方法思路

### 3.1 从 Schrödinger picture 到 Heisenberg picture

先把完整电路写成按时间执行的门序列：

```text
C = Gₘ ⋯ G₂ G₁
```

量子态最先经过 `G₁`，最后经过 `Gₘ`。在通常的 Schrödinger picture 中，
量子态随时间演化，而测量算符 `O` 保持不变：

```text
                    Schrödinger picture

|ψin⟩ ──G₁──G₂── ··· ──Gₘ──► |ψout⟩ ── measure O
  state changes                         O stays fixed
```

其中

```text
|ψout⟩ = C|ψin⟩.
```

也可以把所有门从量子态一侧移到算符一侧。对任意输入态都有

```text
⟨ψout|O|ψout⟩
  = ⟨ψin|C† O C|ψin⟩
  = ⟨ψin|O_H|ψin⟩,

O_H = C† O C.
```

符号 `†` 叫作 dagger，表示复共轭转置。因此，在 Heisenberg picture 中，
输入态保持不变，算符从电路末端向前传播：

```text
                    Heisenberg picture

O⁽⁰⁾ = O
  │  conjugate by Gₘ
  ▼
O⁽¹⁾ = Gₘ† O⁽⁰⁾ Gₘ
  │  conjugate by Gₘ₋₁
  ▼
  ···
  │  conjugate by G₁
  ▼
O⁽ᵐ⁾ = C† O C = O_H
```

更一般地，第 `r` 次反向更新是

```text
O⁽ʳ⁾ = Gₘ₋ᵣ₊₁† O⁽ʳ⁻¹⁾ Gₘ₋ᵣ₊₁,   r=1,…,m.
```

两种 picture 只是把同一个计算写在不同位置；它们给出的物理期望值完全相同。
本方法选择 Heisenberg picture，是因为初始算符
`O=Z52 Z59 Z72` 的支撑很小，可以从一个非常简单的张量网络开始。

### 3.2 OLE 是两个算符的内积

两个 `N`-qubit 算符 `A` 和 `B` 的归一化 Hilbert–Schmidt 内积定义为

```text
(A,B)HS = 2⁻ᴺ Tr[A†B].
```

它和普通向量内积的作用相似，只是比较对象从向量换成了矩阵。因子 `2⁻ᴺ`
使 Pauli 乘积构成归一化正交基。例如，
`2⁻ᴺ Tr[O†O]=1`。

本问题中的 `O` 是 Pauli `Z` 的乘积，因此 `O†=O`。OLE 正是原始算符 `O`
与演化后算符 `O_H` 的 Hilbert–Schmidt 内积：

```text
F = (O,O_H)HS
  = 2⁻ᴺ Tr[O O_H]
  = 2⁻ᴺ Tr[O C† O C].
```

可以把 `F` 理解成“演化后的算符在原始算符方向上的分量”：

- `F=1` 表示 `O_H=O`；
- `F≈0` 表示 `O_H` 几乎没有原始 `O` 的分量；
- 这里直接计算完整 trace，因此没有随机初态，也没有 sampling seed。

### 3.3 PEPO 怎样表示一个多体算符

#### 从乘积算符开始

初始算符可以写成各 site 上局域算符的直积：

```text
O = ⊗ᵢ Oᵢ,

Oᵢ = Z,  i∈{52,59,72},
Oᵢ = I,  otherwise.
```

如果直接把一般 `N`-qubit 算符保存成矩阵，需要 `4ᴺ` 个复数。PEPO
（projected entangled-pair operator）不保存这张大矩阵，而是给每个 site
放置一个小张量 `Aᵢ`，再用虚拟指标把相邻张量连接起来。

一个 PEPO 局域张量可以画成：

```text
                         output physical leg sᵢ′
                                  │
                                  │
                    αleft ───── [ Aᵢ ] ───── αright
                               ╱       ╲
                           αup           αdown
                                  │
                                  │
                          input physical leg sᵢ
```

这里有两类“腿”：

- **physical leg（物理腿）** `sᵢ,sᵢ′`：分别对应局域矩阵的输入和输出指标；
  对 qubit 而言，每条物理腿的维数都是 2。
- **virtual leg（虚拟腿）** `αᵢⱼ`：连接相邻 site，记录算符在不同 site
  之间的相关性。虚拟腿的维数称为 bond dimension（键维数）。

为了看清连接方式，可以先画一个三 site 链：

```text
        s₀′                 s₁′                 s₂′
         │                   │                   │
       [ A₀ ] ─── α₀₁ ─── [ A₁ ] ─── α₁₂ ─── [ A₂ ]
         │                   │                   │
        s₀                  s₁                  s₂
```

这张链图只用于解释指标；49-qubit 计算中的 PEPO 实际沿 QASM 中 CZ 门定义的
heavy-hex interaction graph 连接，并不是把物理系统改成一维链或方格。

一般 PEPO 表示为

```text
O_H ≈ Σ_{s,s′,{α}}
      [∏ᵢ Aᵢ(sᵢ′,sᵢ; {αᵢⱼ})]
      |s₁′…sN′⟩⟨s₁…sN|.
```

对初始乘积算符 `O=⊗ᵢOᵢ`，每个 `Aᵢ` 就是局域矩阵 `Oᵢ`，所有虚拟腿维数
都是 1。这称为 bond-1 PEPO，而且是精确表示。

纠缠门作用后，`O_H` 通常不能再拆成单 site 算符的直积。这里所谓
operator entanglement（算符纠缠），就是跨过某个空间切分时，算符不能只用
一个左侧算符乘一个右侧算符表示。跨过一个 `L|R` 切分，可以作 operator
Schmidt decomposition：

```text
O_H = Σₐ₌₁ᴿ sₐ Lₐ ⊗ Rₐ.
```

乘积算符只有一项，即 `R=1`；算符纠缠增长时需要更多项。PEPO 穿过该切分的
虚拟键正是用来携带这个求和指标 `a`。代码参数 `Dop`（也写作 `Dₒₚ`）
就是演化过程中允许的最大 PEPO 虚拟键维数：

```text
1 ≤ dim(αᵢⱼ) ≤ Dop.
```

### 3.4 量子门怎样更新 PEPO

#### 单量子比特门

若门 `Uᵢ` 只作用在 site `i`，Heisenberg 更新是

```text
O′ = Uᵢ† O Uᵢ.
```

它只改变 `Aᵢ` 的两个物理腿，不会直接建立新的 site 间虚拟连接。

#### 双量子比特门

若门 `Gᵢⱼ` 同时作用在相邻 sites `i,j`，更新需要先把两个局域张量合并为
`Θᵢⱼ`，施加 `Gᵢⱼ†(·)Gᵢⱼ`，再把结果拆回两个张量：

```text
 [ Aᵢ ]──α──[ Aⱼ ]             current PEPO tensors
          │
          │ merge tensors
          ▼
       [  Θᵢⱼ  ]
          │
          │ Θ′ᵢⱼ = Gᵢⱼ† Θᵢⱼ Gᵢⱼ
          ▼
       [  Θ′ᵢⱼ ]
          │
          │ reshape across i | j and perform SVD
          ▼
       U ── S ── V†
          │
          │ keep at most Dop singular components
          ▼
 [ Aᵢ′ ]──α′──[ Aⱼ′ ]          dim(α′) ≤ Dop
```

SVD（singular-value decomposition，奇异值分解）写成

```text
Θ′ᵢⱼ = U S V†
      = Σₐ₌₁ʳ sₐ uₐvₐ†
      ≈ Σ_{a=1,…,min(r,Dop)} sₐ uₐvₐ†.
```

上式最后一行表示只保留最大的至多 `Dop` 个奇异值。代码没有覆盖 quimb 的
`cutoff_mode`，因此沿用默认的相对阈值 `rel`：

```text
sₐ < evolution_cutoff × s₁  → discard sₐ,

evolution_cutoff = 10⁻¹².
```

如果精确秩 `r≤Dop`，这一步不因 `Dop` 产生截断；如果 `r>Dop`，被丢弃的
奇异分量就是第一类数值近似的来源。即使 `r≤Dop`，相对 cutoff 仍可能删除
极小的奇异分量。

本实现使用 simple update：SVD 时用相邻虚拟键上的局域 gauge 近似周围环境，
而不为每次门更新计算完整的二维全局环境。它使 49-site 演化可执行，但也意味着
`Dop` 必须通过扫描来检查，而不能把单次有限 `Dop` 结果当作精确答案。

### 3.5 反向光锥怎样减少工作量

局域算符最初只作用在少数 qubit 上。定义当前 causal support（因果支撑）
集合 `S` 为“当前算符可能不是单位算符的 qubit 集合”，并令 `Qₖ` 为门
`Gₖ` 作用的 qubit 集合。从最后一个门向前扫描时：

```text
Qₖ ∩ S = ∅  → skip Gₖ,

Qₖ ∩ S ≠ ∅ → keep Gₖ and update S ← S ∪ Qₖ.
```

若 `Qₖ∩S=∅`，门和当前算符作用在互不相交的 Hilbert 空间，因此

```text
Gₖ† Ocurrent Gₖ = Ocurrent.
```

这样的门可以严格跳过，不产生近似。下面的三量子比特例子展示了 support
怎样沿逆时间方向扩展：

```text
time ─────────────────────────────────────────────►

              G₀₁          U₀          G₁₂       O=Z₂
q0  ───────────●──────────[ U ]─────────────────────
               │
q1  ───────────●───────────────────────●────────────
                                       │
q2  ───────────────────────────────────●────────[ Z ]

reverse scan:
  start at O=Z₂:   S={2}
  inspect G₁₂:     Q₁₂∩S≠∅  → keep, S={1,2}
  inspect U₀:      Q₀∩S=∅    → skip, S={1,2}
  inspect G₀₁:     Q₀₁∩S≠∅  → keep, S={0,1,2}
```

相交的门也可能因为特殊对易关系而不真正扩大精确算符支撑；这里取并集是一种
安全的保守选择，不会漏掉可能有贡献的门。所有被保留门组成 observable 的
reverse light cone（反向光锥）。在当前 49-qubit 电路中，光锥最终传播到
全部 49 个 active sites，共包含 3,937 个 causal gates。

### 3.6 怎样把 PEPO 收缩成 OLE

完成所有反向门更新后，得到有限 `Dop` 的近似算符
`PEPO_Dop(O_H)`。接下来需要计算

```text
Tr[O O_H]
  = Σ_{s,s′} [∏ᵢ (Oᵢ)_{sᵢsᵢ′}] (O_H)_{s′,s}.
```

这条公式表示：在每个 site 上，把演化后张量 `Aᵢ` 的两条物理腿连接到原始
局域算符 `Oᵢ`，然后对 `sᵢ,sᵢ′` 求和，也就是闭合物理腿：

```text
          virtual legs                 virtual legs
        ───────[ Aᵢ ]────────────────────────
                   ╲ sᵢ′        sᵢ ╱
                    ╲            ╱
                       [ Oᵢ ]

            close both physical legs
                       │
                       ▼
        ─────────────[ Bᵢ ]───────────────────
              only virtual legs remain
```

对全部 site 做这一步后，网络已经没有开放的物理腿，但仍有许多彼此连接的
虚拟腿。把它完全收缩会得到一个标量。记 `χenv` 为压缩收缩过程中允许的最大
中间键维数，则有限参数结果是

```text
F(Dop,χenv)
  = 2⁻ᴺ Contract[PEPO_Dop(O_H) × O].
```

二维张量网络的精确收缩通常仍是指数困难的。本实现使用
`contract_compressed`：每当收缩产生较大的中间张量时，再做一次压缩，并把
中间键维数限制为 `χenv`。因此：

- `Dop` 控制“演化后的算符表示得多准确”；
- `χenv` 控制“已经构造好的闭合网络收缩得多准确”。

它们位于算法的不同阶段，是两种独立误差源，不能统称为同一个 bond
dimension。最后乘 `2⁻ᴺ` 是 Hilbert–Schmidt 归一化，不是额外拟合参数。

### 3.7 三量子比特例子与完整流程

把上一节的三量子比特链具体写成两个一般的纠缠门

```text
C = G₁₂ G₀₁,   O=Z₂.
```

因为 `G₁₂` 是电路中后执行的门，Heisenberg 演化先处理它：

```text
O⁽⁰⁾ = I₀ ⊗ I₁ ⊗ Z₂

O⁽¹⁾ = G₁₂† O⁽⁰⁾ G₁₂
      causal support: {2} → {1,2}

O⁽²⁾ = G₀₁† O⁽¹⁾ G₀₁
      causal support: {1,2} → {0,1,2}

O⁽²⁾ = C† O C.
```

这说明“反向”指的是门的处理顺序，不是把矩阵公式写成 `COC†`。最终 OLE
仍然是 `2⁻³Tr[O O⁽²⁾]`。

49-qubit 实现与这个小例子的逻辑完全相同，只是 PEPO 虚拟键和光锥更大。
完整数据流可以概括为：

```text
audited QASM C + product observable O
                   │
                   ▼
CZ interaction graph + exact bond-1 PEPO(O)
                   │
                   ▼
reverse-light-cone gate selection
                   │
                   ▼
Gₘ, Gₘ₋₁, …, G₁ Heisenberg updates
                   │
                   ├── SVD/simple-update compression
                   │      dim(virtual bond) ≤ Dop
                   │      approximation source 1
                   ▼
             PEPO_Dop(O_H)
                   │
                   ▼
insert every Oᵢ and close all physical legs
                   │
                   ▼
       closed two-dimensional virtual network
                   │
                   ├── compressed contraction
                   │      dim(intermediate bond) ≤ χenv
                   │      approximation source 2
                   ▼
              scalar Tr[O O_H]
                   │
                   ▼
             multiply by 2⁻ᴺ
                   │
                   ▼
              F(Dop,χenv)
```

对应到实际代码，执行步骤是：

1. **验证输入。** 检查 QASM 字节数、SHA-256、支持的门类型、active sites 和
   pinned quimb revision。
2. **建立几何。** 从 QASM 中所有 CZ 门提取 heavy-hex interaction edges。
3. **初始化算符。** 在 sites `52,59,72` 放置 Pauli `Z`，其余 sites 放置单位算符。
4. **求反向光锥。** 只保留会影响当前 support 的门。
5. **演化并截断。** 逆序施加 gate dagger，以 `Dop` 和
   `evolution_cutoff` 约束 simple-update SVD。
6. **闭合物理指标。** 在每个 site 插入原始 `Oᵢ` 并对输入、输出指标求和。
7. **压缩收缩。** 以 `χenv` 和 `contraction_cutoff` 收缩剩余虚拟网络。
8. **归一化。** 将 scalar trace 乘 `2⁻ᴺ` 得到 `F`。
9. **验证并记录。** 检查有限性、虚部和物理范围，原子化写入 result 与 manifest。

## 4. 参数定义

### 4.1 物理参数

| 参数 | 当前值 | 含义 |
| --- | ---: | --- |
| `N` | 49 | active qubit 数，也是归一化因子 `2⁻ᴺ` 中的 `N` |
| `δ` | 0.15 | OLE 电路的扰动强度标签；QASM 中对应 24 个已审计扰动门 |
| `observable_sites` | `[52,59,72]` | Pauli `Z` 乘积的物理 qubit labels |
| `O` | `Z52 Z59 Z72` | 与 `C†OC` 做 overlap 的初始局域算符 |

### 4.2 数值截断参数

| 参数 | 本次范围/值 | 控制的误差 | 增大后的代价 |
| --- | ---: | --- | --- |
| `Dop` | `2…512` | Heisenberg 算符演化中的 PEPO 截断 | SVD 时间和张量内存快速增加 |
| `χenv` | `16,32,64` | 最终闭合张量网络的压缩收缩误差 | contraction 时间和中间张量内存增加 |
| `evolution_cutoff` | `10⁻¹²` | 演化阶段 SVD 的奇异值 cutoff | cutoff 越小，保留的小奇异值越多 |
| `contraction_cutoff` | `10⁻¹²` | 最终 compressed contraction 的 cutoff | cutoff 越小，收缩更精细 |
| `progress_every` | 100 | 每处理多少 causal gates 写一次进度 | 只影响日志频率，不改变物理结果 |

`Dop` 和 `χenv` 不是同一个“bond dimension”：

- `Dop` 作用于 `C†OC` 的构造；
- `χenv` 作用于构造完成后的 scalar contraction。

当前误差明显由 `Dop` 主导。在 `Dop=128` 的完整环境截面上，
`χenv=32→64` 只改变 `1.38×10⁻⁵`；最新 `Dop=384→512` 改变
`1.97×10⁻⁴`。两项之和已低于目标，但环境数值仍只是低 `Dop` proxy，
不能代替最大角点的直接扫描。

### 4.3 验证参数和 provenance

| 参数 | 值 | 作用 |
| --- | --- | --- |
| result tolerance | `10⁻⁸` | 限制非物理虚部和实部越界 |
| quimb commit | `3c89529fe0a3487133a3928201691161e110abdf` | 固定 PEPO/SVD 实现 |
| numerical-core digest | `cb55b3bd68415d10cbfd4d23f980fdd3fe99dea07e7387f4ce59070c10e4715f` | 绑定 QASM、门、演化和收缩核心源码 |
| duplicate tolerance | `10⁻¹²` | 判断跨 run 重复坐标是否确定性一致 |
| convergence target | `10⁻³` | PEPO 经验误差预算目标 |

诊断量 `max_retained_tail_ratio` 是某次局部 SVD 中“最后一个保留奇异值/第一个
奇异值”的最大值。它不是 discarded-weight error bound。当前观测到的 `1.0`
表示至少有局部保留谱较平，并支持“有限 `Dop` 截断仍强”的判断，但不能直接转成
`F` 的严格误差条。

## 5. 代码结构与关键函数

### 5.1 调用关系

```text
parameter_scan.py
  └─ run_pepo_array_cell.py
       ├─ selected_payload()
       └─ run_cell()
            ├─ run_pepo.py dry-run → confirmation_token
            └─ run_pepo.py --execute
                 └─ execute()
                      ├─ validate_small_oracle()
                      ├─ read_validated_qasm()
                      └─ evolve_and_contract()
                           ├─ build_pepo_circuit()
                           ├─ ProductObservablePEPO.evolve_product()
                           │    └─ reverse_lightcone_indices()
                           └─ normalized_overlap_compressed()

analyze_pepo.py
  └─ analyze_run_directories()
       ├─ manifest/provenance consensus
       ├─ assess_convergence()
       ├─ assessment.json
       └─ convergence PNG/PDF + short report
```

### 5.2 关键文件和函数

| 文件/函数 | 作用 |
| --- | --- |
| [`qasm.py`](pepo/src/ole_pepo/qasm.py) `read_validated_qasm()` | 在解析前验证 QASM 长度和 SHA-256 |
| `qasm.py` `parse_qasm()` | 严格解析当前 QASM 子集并保存 layer/gate labels |
| `qasm.py` `replace_perturbations()` | 构造 `δ=0` 控制电路 |
| [`gates.py`](pepo/src/ole_pepo/gates.py) `gate_matrix()` | 为 `rx/rz/s/sdg/sx/sxdg/cz` 构造审计矩阵 |
| `gates.py` `interaction_edges()` | 从 CZ 门提取 PEPO 几何 |
| [`engine.py`](pepo/src/ole_pepo/engine.py) `reverse_lightcone_indices()` | 只选择会影响 observable 的反向 causal gates |
| `engine.py` `ProductObservablePEPO.evolve_product()` | 反向施加 gate dagger，并以 `Dop`/cutoff 做 simple update |
| `engine.py` `build_pepo_circuit()` | 将 QASM gates 和 CZ geometry 组装为 quimb PEPO circuit |
| [`contraction.py`](pepo/src/ole_pepo/contraction.py) `product_overlap_network()` | 把演化算符与原始 product observable 闭合 |
| `contraction.py` `normalized_overlap_compressed()` | 以 `χenv` 压缩收缩并乘 `2⁻ᴺ` |
| [`run_pepo.py`](scripts/run_pepo.py) `validate_small_oracle()` | 阻止过期或失败的小系统证书进入 49Q 计算 |
| `run_pepo.py` `confirmation_payload()` | 将输入、参数、代码 digest 和输出路径绑定到 token |
| `run_pepo.py` `execute()` | 输出进度，检查物理范围，原子化写 result |
| [`run_pepo_array_cell.py`](scripts/run_pepo_array_cell.py) `run_cell()` | 从 run spec 选择 cell，先 dry-run 再携 token 执行 |
| [`records.py`](pepo/src/ole_pepo/records.py) `atomic_write_json()` | 通过临时文件、`fsync` 和 replace 防止半写 manifest |
| [`analyze_pepo.py`](scripts/analyze_pepo.py) `assess_convergence()` | 计算 `ΔDop`、`Δχenv`、经验误差和 BP comparison status |

### 5.3 安全与可复现设计

- 49Q runner 默认只做 dry-run；真实执行必须携带刚打印的 confirmation token。
- 输出只能写入 repo-root 下的 `results/issue119-pepo-*`。
- QASM hash、quimb commit 和 numerical-core digest 不一致时立即停止。
- 小系统 exact-oracle 证书过期时立即停止。
- result、partial progress 和 manifest 都采用原子写入。
- PEPO trace 是确定性的，因此 runner 没有 `--seed` 参数。

## 6. 使用方法

以下命令均从仓库根目录运行。

### 6.1 准备环境

```bash
make skills

OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv sync --project "$OLE_ROOT/pepo" --locked
```

### 6.2 验证七量子比特 exact oracle

先运行 inspection：

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
```

命令会打印 confirmation token，不进行计算。将打印出的 token 代入：

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py" \
  --execute --confirm TOKEN
```

当前证书的最大 PEPO–dense 误差为 `6.883×10⁻¹⁵`。

### 6.3 检查单个 49Q 参数点

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/run_pepo.py" \
  --dop 512 \
  --chi-env 64 \
  --delta 0.15 \
  --evolution-cutoff 1e-12 \
  --contraction-cutoff 1e-12 \
  --output results/issue119-pepo-example/pepo-result.json
```

这一步仍是 dry-run。确认输出中的 QASM hash、observable、`δ`、`Dop`、`χenv`
和输出路径后，再追加：

```text
--execute --confirm TOKEN
```

`Dop=512` 不适合在普通本地环境运行；本次使用远端 Slurm。

### 6.4 生成参数扫描

以 `Dop=512,χenv=64` 单点为例：

```bash
python3 scripts/parameter_scan.py plan \
  --axes "$OLE_ROOT/configs/pepo-dop512-axes.json" \
  --settings "$OLE_ROOT/configs/pepo-settings.json" \
  --provenance "$OLE_ROOT/configs/pepo-provenance.json" \
  --run-id issue119-pepo-49q-dop512 \
  --run-dir results/issue119-pepo-49q-dop512
```

提交前检查 selector：

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/run_pepo_array_cell.py" \
  --run-spec results/issue119-pepo-49q-dop512/run_spec.json \
  --selector 1 \
  --inspect-only
```

### 6.5 Slurm 提交示例

本次 `Dop=512` 使用 128 CPU、192 GiB、6 h：

```bash
scripts/harness_slurm.sh submit \
  --array 1 \
  --run-spec results/issue119-pepo-49q-dop512/run_spec.json \
  --command 'env OPENBLAS_NUM_THREADS=128 OMP_NUM_THREADS=128 MKL_NUM_THREADS=128 NUMEXPR_NUM_THREADS=128 /home/zyli/.local/bin/uv run --project tracks/qcs/solutions/CCB-LV.999/issue-119-ole/pepo python tracks/qcs/solutions/CCB-LV.999/issue-119-ole/scripts/run_pepo_array_cell.py' \
  --partition batch \
  --time 06:00:00 \
  --cpus 128 \
  --extra '--mem=192G'
```

集群连接、partition 和 `uv` 路径属于本地 profile 信息；换集群时应读取
`skills/using-slurm/profiles/active.toml`，不能直接复制这些机器相关值。

### 6.6 拉取并汇总结果

```bash
scripts/harness_slurm.sh fetch issue119-pepo-49q-dop512

python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-pepo-49q-dop512/run_spec.json \
  --success-field status \
  --success-value success \
  --value-field result.value_real
```

完整 D-scan 分析使用：

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/analyze_pepo.py" \
  --run-dir results/issue119-pepo-49q-pilot \
  --run-dir results/issue119-pepo-49q-wave-1-dop \
  --run-dir results/issue119-pepo-49q-wave-1-env \
  --run-dir results/issue119-pepo-49q-wave-2-dop \
  --run-dir results/issue119-pepo-49q-wave-3-dop \
  --run-dir results/issue119-pepo-49q-dop64-128 \
  --run-dir results/issue119-pepo-49q-dop256 \
  --run-dir results/issue119-pepo-49q-dop384 \
  --run-dir results/issue119-pepo-49q-dop512 \
  --output-dir results/issue119-pepo-49q-dop512-analysis
```

## 7. 验证策略

### 7.1 小系统 exact-oracle

从原始 49Q QASM 截取七 site 子系统：

```text
sites = 33,39,49,50,51,52,53
O = Z52
```

结果为：

| quantity | dense | exact PEPO | absolute error |
| --- | ---: | ---: | ---: |
| `δ=0` | 0.99999999999997846 | 0.99999999999998535 | `6.883×10⁻¹⁵` |
| `δ=0.15` | 0.96509609391749107 | 0.96509609391749729 | `6.217×10⁻¹⁵` |

这证明了 QASM 解析、门矩阵、Heisenberg 演化方向、trace 归一化和 overlap
构造在可精确求解系统上相互一致。

### 7.2 49Q 执行证据

- 25/25 个 `δ=0.15` 执行记录成功；
- 无 failed、missing 或 pending cell；
- 重复的 `(Dop=8,χenv=64)` 两次结果相差 `3.04×10⁻¹⁸`；
- 每个最大-D cell 均处理 3,937 个 causal gates；
- final support 覆盖全部 49 active sites；
- `Dop=512` 的结果虚部为 `−1.61×10⁻¹⁵`；
- 当前 PEPO 测试为 131 passed。

这些证据证明代码与 49Q 执行链有效，但不等价于 `Dop→∞` 已收敛。

## 8. 49Q 数值结果

### 8.1 固定 `χenv=64` 的 `Dop` 序列

| `Dop` | `FPEPO` | 相邻变化 |
| ---: | ---: | ---: |
| 2 | `9.358350355066179×10⁻¹²` | — |
| 4 | `1.069098640490245×10⁻⁶` | `1.069089282×10⁻⁶` |
| 8 | `0.001097682438141984` | `0.001096613340` |
| 16 | `0.06861725067416627` | `0.067519568236` |
| 32 | `0.5172681916693251` | `0.448650940995` |
| 64 | `0.7202479157622051` | `0.202979724093` |
| 128 | `0.7987800319758508` | `0.078532116214` |
| 256 | `0.8213430762683898` | `0.022563044293` |
| 384 | `0.8223537668681797` | `0.001010690600` |
| 512 | `0.8225508376024053` | `0.000197070734` |

从 `Dop=32` 开始，相邻变化连续减小：

```text
0.44865 → 0.20298 → 0.07853 → 0.02256 → 0.00101 → 0.000197
```

最新变化/前一步变化约为 `0.1950`，即最新 `Dop` 增量下降约 80.5%。
`ΔDop=1.97×10⁻⁴` 已低于 `10⁻³` 目标；但单个 successive difference
仍不是严格误差界，也没有提供受控的 `Dop→∞` 外推。

### 8.2 最近的完整 `χenv` 截面

`Dop=512` 只计算了 `χenv=64`。最近的完整环境截面仍位于 `Dop=128`：

| `χenv` | `FPEPO(Dop=128)` | 相邻变化 |
| ---: | ---: | ---: |
| 16 | `0.7982962803124029` | — |
| 32 | `0.7987662065070368` | `0.000469926195` |
| 64 | `0.7987800319758508` | `0.000013825469` |

环境方向的最新变化已经低于 `10⁻³`，但它是从 `Dop=128` 继承到当前分析的
proxy。没有额外的 `Dop=512` 环境点，就不能直接认证最大角点的 `χenv` 收敛。

### 8.3 经验误差判据

分析器使用：

```text
ΔDop  = |F(Dmax,χmax) − F(Dprev,χmax)|
Δχenv = 最近完整 χ 截面的最后两个 χenv 之差
εPEPO = ΔDop + Δχenv
```

当前：

```text
ΔDop  = 0.00019707073422559063
Δχenv = 0.00001382546881401048  [Dop=128 proxy]
εPEPO = 0.0002108962030396011
target = 0.001
```

内部收敛要求：

1. `εPEPO≤10⁻³`；
2. 最新 `Dop` 和 `χenv` 变化不再增大；
3. `χenv` 截面必须直接位于最大 `Dop` 角点。

当前满足第 1、2 条；第 3 条仍未满足。因此 `internally_converged=false`：
可以说 `Dop` 精度与代理误差和已达标，但不能写成最大角点双轴“已经收敛”。

## 9. 与 BP-TN 和公开结果比较

| 结果 | 数值 | 与当前 PEPO 的差 |
| --- | ---: | ---: |
| 当前 PEPO，`Dop=512,χenv=64` | `0.8225508376` | — |
| 本次 BP-TN mean | `0.8183229132` | `0.0042279244` |
| 公开 BP-TN，`χ=192` raw | `0.8202512915` | `0.0022995461` |
| 公开 BP-TN，`χ=512` raw | `0.8216584890` | `0.0008923486` |
| IBM Heron R3，global-rescaled | `0.824` | `0.0014491624` |

IBM 数值经过 `δ=0` global rescaling，与 raw PEPO/BP-TN 口径不同，只能作为
背景参考。

当前 PEPO 与公开 `χ=512` BP-TN 中心值相差 `8.92×10⁻⁴`，但与本次
20-seed BP-TN 均值相差 `4.23×10⁻³`。PEPO 在 `Dop=128→256` 已越过本次
BP mean，`Dop=256→384→512` 又继续升高；这再次说明选择“最接近 BP 的有限
Dop”会产生选择偏差。独立方法比较只能在 PEPO 自身收敛后升级为
agreement/disagreement；当前状态保持为 `diagnostic`。

## 10. 计算资源

| 扫描点 | CPU 请求 | 最大 wall time | 最大 peak RSS |
| --- | ---: | ---: | ---: |
| `Dop=32`，三个 `χenv` | 8/cell | 107.27 s | 0.266 GiB |
| `Dop=64`，三个 `χenv` | 32/cell | 145.19 s | 1.149 GiB |
| `Dop=128`，三个 `χenv` | 32/cell | 252.70 s | 1.701 GiB |
| `Dop=256,χenv=64` | 64 | 807.07 s | 11.402 GiB |
| `Dop=384,χenv=64` | 96 | 2315.21 s | 21.508 GiB |
| `Dop=512,χenv=64` | 128 | 1755.86 s | 43.411 GiB |

`Dop=64/128` 的六个 cell 同时运行，每个进程实测使用约 29–30 核，总利用率约
176–180 核。`Dop=512` 对应 Slurm Job `412377`，请求 128 CPU、192 GiB、6 h，
实测约 29.26 min 和 43.411 GiB。它比 `Dop=384` 使用更多 CPU，所以 wall time
反而缩短约 24.2%，但 peak RSS 增长约 2.02 倍；资源缩放同时依赖 `Dop` 与
并行度，不能仅按 `Dop` 线性外推。

集群关闭了 Slurm accounting，因此 wall time 和 peak RSS 来自 Python manifest，
而不是 `sacct`。

## 11. 当前结论和局限

### 11.1 当前证据能够支持

- 小系统上算法和实现达到约 `10⁻¹⁴` 精度；
- 完整 49Q causal evolution、PEPO contraction 和 manifest 链路可执行；
- `Dop=32→64→128→256→384→512` 的变化连续减小，最新变化约为前一步的
  19.50%；
- `Dop=512` 的 `ΔDop=1.97×10⁻⁴`，代理误差和
  `εPEPO=2.11×10⁻⁴<10⁻³`；
- 当前 PEPO 与 BP-TN/公开 BP 中心值数值接近；
- `Dop≤128` 时 `χenv=64` 的收缩误差已经较小。

### 11.2 当前证据不能支持

- `Dop=512` 角点的直接 `χenv` 收敛；
- 受控的 `Dop→∞` 外推；
- PEPO 与 BP-TN 已正式 agreement；
- PEPO baseline benchmark 已完成。

### 11.3 后续最有信息量的计算

最有信息量的下一步是在同一 `Dop=512` 角点补充 `χenv=32`。当前
operator-bond 方向已经跨过 `10⁻³` 阈值；直接比较
`F(512,64)−F(512,32)` 才能替换来自 `Dop=128` 的环境 proxy，并判断
三项内部收敛条件是否同时满足。

## 12. 结果与源码索引

### 12.1 报告和图

- 当前方法报告：`PEPO_METHOD_REPORT_NOTE.md`
- 49Q 验证记录：[`PEPO_49Q_VALIDATION.md`](PEPO_49Q_VALIDATION.md)
- 小系统验证：[`PEPO_SMALL_VALIDATION.md`](PEPO_SMALL_VALIDATION.md)
- 最新 assessment：
  `results/issue119-pepo-49q-dop512-analysis/assessment.json`
- 最新收敛图：
  `results/issue119-pepo-49q-dop512-analysis/pepo-convergence.png`

![PEPO convergence through Dop=512](../../../../../results/issue119-pepo-49q-dop512-analysis/pepo-convergence.png)

图 A 是固定 `χenv=64` 的 `Dop` 序列；图 B 是最近的完整环境截面，
对应 `Dop=128`，不是 `Dop=512`。

### 12.2 运行结果

- `results/issue119-pepo-49q-dop512/`
- `results/issue119-pepo-49q-dop384/`
- `results/issue119-pepo-49q-dop256/`
- `results/issue119-pepo-49q-dop64-128/`
- `results/issue119-pepo-49q-wave-3-dop/`
- `results/issue119-pepo-49q-wave-2-dop/`
- `results/issue119-pepo-49q-wave-1-dop/`
- `results/issue119-pepo-49q-wave-1-env/`
- `results/issue119-pepo-49q-pilot/`
- `results/issue119-pepo-small-oracle/`

### 12.3 核心源码

- [`scripts/run_pepo.py`](scripts/run_pepo.py)
- [`scripts/run_pepo_array_cell.py`](scripts/run_pepo_array_cell.py)
- [`scripts/analyze_pepo.py`](scripts/analyze_pepo.py)
- [`pepo/src/ole_pepo/qasm.py`](pepo/src/ole_pepo/qasm.py)
- [`pepo/src/ole_pepo/gates.py`](pepo/src/ole_pepo/gates.py)
- [`pepo/src/ole_pepo/engine.py`](pepo/src/ole_pepo/engine.py)
- [`pepo/src/ole_pepo/contraction.py`](pepo/src/ole_pepo/contraction.py)
- [`pepo/src/ole_pepo/records.py`](pepo/src/ole_pepo/records.py)
