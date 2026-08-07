# Heisenberg-picture PEPO 初学者讲解设计

日期：2026-07-28

目标文档：
`tracks/qcs/solutions/CCB-LV.999/issue-119-ole/PEPO_METHOD_REPORT_NOTE.md`

## 目标

扩写目标文档的“方法思路”部分，使首次接触张量网络的读者能够回答以下问题：

1. 为什么可以不演化量子态，而改为演化算符？
2. PEPO 如何把指数规模的多体算符拆成局域张量？
3. 单量子比特门和双量子比特门如何更新 PEPO？
4. `Dop` 在哪里截断，`χenv` 又在哪里截断？
5. 最终怎样从闭合张量网络得到 OLE？

本次只增强方法说明和图示，不修改代码、计算参数、原始结果或收敛结论。

## 表达方案

使用 Unicode 公式和纯文本简图，不依赖 LaTeX、Mermaid 或外部图片。这样同一份
Markdown 可在 GitHub、飞书、终端和普通文本编辑器中阅读。

所有公式使用同一组符号：

- `C = Gₘ⋯G₂G₁`：按时间顺序执行的完整电路；
- `O⁽⁰⁾ = O`：初始乘积 Pauli 算符；
- `O⁽ʳ⁾ = Gₘ₋ᵣ₊₁† O⁽ʳ⁻¹⁾ Gₘ₋ᵣ₊₁`：第 `r` 次逆时间
  Heisenberg 更新；
- `O_H = C†OC`：完整演化后的算符；
- `Dop`：算符 PEPO 的最大虚拟键维；
- `χenv`：闭合网络压缩收缩的最大中间键维；
- `F = 2⁻ᴺ Tr[O O_H]`：目标 operator Loschmidt echo。

## 章节结构

现有第 3 节改写为由浅入深的七个小节。

### 1. 从态演化换到算符演化

先给出期望值恒等式：

```text
|ψout⟩ = C|ψin⟩

⟨ψout|O|ψout⟩
  = ⟨ψin|C†OC|ψin⟩
  = ⟨ψin|O_H|ψin⟩
```

配一张左右对照图，说明 Schrödinger picture 移动态、Heisenberg picture 移动
算符，二者给出同一可观测量。

### 2. OLE 为什么是算符内积

把 OLE 写成归一化 Hilbert–Schmidt 内积：

```text
(A,B)HS = 2⁻ᴺ Tr[A†B]
F = (O,O_H)HS = 2⁻ᴺ Tr[O C†OC]
```

说明本问题的 Pauli 算符满足 `O†=O`，因此不需要额外 dagger。指出该 trace 是
确定性求和，不需要随机初态或 seed。

### 3. PEPO 如何表示一个算符

先从乘积算符开始：

```text
O = ⊗ᵢ Oᵢ,   Oᵢ ∈ {I,Z}
```

每个局域张量有两个物理腿（输入 `sᵢ`、输出 `sᵢ′`），并通过虚拟腿连接相邻
site。初始乘积算符不含跨 site 的算符纠缠，所以所有虚拟腿维数均为 1。

一般 PEPO 使用公式：

```text
O_H ≈ Σ_{s,s′,{α}}
      [∏ᵢ Aᵢ(sᵢ′,sᵢ; {αᵢⱼ})]
      |s₁′…sN′⟩⟨s₁…sN|
```

配局域张量和一小块网络的简图。解释虚拟指标 `αᵢⱼ` 传递 site 间的相关性，
其维数上限就是 `Dop`。

### 4. 门怎样反向更新 PEPO

令 `C=Gₘ⋯G₁`。代码从 `O` 出发，按 `Gₘ,Gₘ₋₁,…,G₁` 的逆时间顺序更新：

```text
O ← Gₖ† O Gₖ
```

单量子比特门只改变一个局域张量。双量子比特门先合并两个相邻张量并施加
`Gᵢⱼ†(·)Gᵢⱼ`，再沿两 site 之间的虚拟键做 SVD：

```text
Θ′ = Gᵢⱼ† Θ Gᵢⱼ
Θ′ = U S V†
   ≈ Σₐ₌₁ᴰᵒᵖ sₐ uₐvₐ†
```

配“合并 → 施门 → SVD → 截断 → 拆回”的流程图。明确这是 `Dop` 误差出现的
位置；simple update 还使用邻接键 gauge 近似周围环境。

### 5. 反向光锥为什么能跳过一些门

维护当前算符支撑集合 `S`。从最后一个门向前扫描：

```text
Qₖ ∩ S = ∅  → 跳过 Gₖ
Qₖ ∩ S ≠ ∅ → 保留 Gₖ，并令 S ← S ∪ Qₖ
```

当门作用在与 `S` 不相交的 qubit 上时，它与当前算符作用在不同 Hilbert 空间，
所以 `Gₖ†OGₖ=O`。配一个三层小电路，用实线标出被保留的反向光锥。

### 6. 怎样闭合网络得到 OLE

把演化后的 PEPO `O_H` 与原始乘积算符 `O` 在每个 site 上闭合输入、输出物理
腿，得到只剩虚拟腿的二维 scalar network：

```text
F(Dop,χenv)
  = 2⁻ᴺ Contract[ PEPO_Dop(O_H) × O ]
```

配“PEPO → 插入 Oᵢ → 闭合物理腿 → 压缩收缩 → 标量 F”的简图。说明
`contract_compressed` 在收缩过程中以 `χenv` 限制中间键维；这是第二种近似，
发生在 `O_H` 已经构造完成之后。

### 7. 三量子比特玩具例子和完整流程

使用链 `0—1—2`、初始 `O=Z₂` 和两个双量子比特门说明支撑传播：

```text
初始：S={2}
检查 G₁₂：命中 → S={1,2}
检查 G₀₁：命中 → S={0,1,2}
```

最后用一张总流程图串联：

```text
QASM → 初始 bond-1 PEPO → 反向光锥
     → 逐门 Heisenberg 更新与 Dop 截断
     → 插入原始 O 并闭合物理腿
     → χenv 压缩收缩 → 乘 2⁻ᴺ → F
```

## 初学者阅读辅助

- 第一次出现 `dagger`、物理腿、虚拟腿、bond dimension、operator
  entanglement 和 Hilbert–Schmidt 内积时立即给出一句定义。
- 每个公式后给一句“这条公式实际在做什么”，不只列符号。
- 图中始终用 `Dop` 标记演化截断，用 `χenv` 标记收缩截断。
- 明确 PEPO 的局域张量网络结构沿 QASM 的 CZ interaction graph 建立；简图
  使用链或小方格只是为了说明索引结构，不把 49-site heavy-hex 画成方格模型。
- 不把 successive-`Dop` difference 描述成严格误差界。

## 验证标准

编辑完成后检查：

1. 公式的门顺序与 `engine.py` 的反向遍历和 `gate_dagger` 一致；
2. OLE 归一化与 `contraction.py` 的 `2⁻ᴺ` 一致；
3. `Dop` 和 `χenv` 在文字、公式和图中没有混用；
4. 所有简图在等宽纯文本中可读；
5. 原有结果表、资源数据和“尚未内部收敛”结论保持不变；
6. Markdown 无断链、TODO、TBD 或尾随空白。
