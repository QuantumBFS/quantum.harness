# 有限圆柱看见的 \(0.3J_1\)，能否穿过无限体系的证书？

## 三角晶格 \(J_1\)–\(J_2\) 模型体谱隙的一次热力学极限认证探索

**Team Fox · 肖元 and 冷昊阳 · PolyOpt Track · Challenge #88**

> **结论等级：开放问题（`inconclusive`）**  
> 我们尚未得到 \(\Delta_{\mathrm{bulk}}<0.20J_1\) 或
> \(\Delta_{\mathrm{bulk}}<0.30J_1\) 的数学证书。得到的是一条完整、可审计的
> 热力学极限判定链，以及对当前 SDP 层级分辨率的定量诊断。

## 摘要

有限圆柱可以显示一个谱隙，却不能决定这个谱隙是否属于无限平面。对受挫量子磁体而言，宽度、边界条件与外推形式都可能把有限尺度结构放大为看似稳定的能标。三角晶格自旋 \(1/2\)
\(J_1\)–\(J_2\) Heisenberg 模型在 \(g=J_2/J_1=0.10\) 附近正提供了一个尖锐测试：早期 DMRG 报告了约 \(0.3J_1\) 的 singlet/triplet gap，并据此支持有隙自旋液体图景；若能在不构造基态波函数、也不诉诸有限尺寸外推的条件下证明
\(\Delta_{\mathrm{bulk}}<0.20J_1\)，这一“大而稳健的完整体谱隙”便会被直接排除。

我们把这个物理问题写成一个嵌套的半正定可行性问题。无限体系基态在任意有限局域算符空间上的限制必须同时满足归一化、正性、平稳性和谱隙正性。若某个有限层级已经不可行，并且不可行性由独立验证的 Farkas 射线证明，那么假设的体谱隙 \(\gamma\) 在无限体系中不可能成立。反之，可行性只说明该层级尚未看见矛盾，绝不证明体系有隙。

在最小的 \(d=1\)、Rung-A 层级上，我们在
\(\gamma/J_1=0,0.1,0.2,0.3,0.6,1.2,2.4,4.8\) 得到八个独立验证的精确 primal 见证。这打通了从三角晶格算符代数到证书验证的完整链条，同时也给出一个明确的负面信息：该层级甚至不能排除 \(4.8J_1\)，因而没有解析 \(0.2\)–\(0.3J_1\) 物理尺度的能力。下一层 \(d=2\) 已被精确构造为含 60,467 个变量、507 个仿射等式及两个 PSD 块的规范锥问题；现有 \(\gamma=0\) 求解记录没有产生完整候选，因此严格归类为 `unknown`。物理争议仍然开放，但它已被压缩为一个定义精确、可继续、不能被数值状态误读的证书搜索问题。

---

## 1. 物理赌注：同一个“谱隙”并非同一个数学对象

取 \(J_1=1\)，研究

\[
H_\triangle(g)=
\sum_{\langle i,j\rangle}\mathbf S_i\!\cdot\!\mathbf S_j
+g\sum_{\langle\!\langle i,j\rangle\!\rangle}
\mathbf S_i\!\cdot\!\mathbf S_j,
\qquad
g=\frac{1}{10},
\]

\[
\mathbf S_i\!\cdot\!\mathbf S_j
=\frac14(X_iX_j+Y_iY_j+Z_iZ_j).
\]

这里的目标是无限平面上、不固定自旋或拓扑扇区的 **full bulk gap**
\(\Delta_{\mathrm{bulk}}\)。它不同于有限圆柱上某个 singlet 或 triplet
扇区内的最低激发能，也不同于对若干有限宽度数据所作的外推值。

这一差别决定了证书的物理含义：

\[
\boxed{\text{若能认证 }\Delta_{\mathrm{bulk}}<0.20J_1,
\text{则约 }0.3J_1\text{ 的稳健完整体谱隙不可能存在。}}
\]

但这个结论不会自动证明 Dirac 自旋液体、弱磁序或严格无隙；它只排除一类具有给定最小体谱隙的无限体积极限。这里追求的是一个单向但严格的裁决，而不是相图的过度解释。

## 2. 从无限晶格到有限证书

### 2.1 基态作为正线性泛函

不显式构造波函数，而以无限体系基态期望

\[
\omega(A)=\langle A\rangle
\]

作为基本对象。任何物理态都必须满足

\[
\omega(\mathbb I)=1,\qquad
\omega(A^\dagger A)\ge 0.
\]

选择有限的局域算符族
\(\mathcal B_d=\{B_1,\ldots,B_m\}\)，便得到矩量矩阵

\[
M^{(d)}_{ab}=\omega(B_a^\dagger B_b),\qquad M^{(d)}\succeq0.
\]

增大局域窗口、Pauli word 的次数或基的 rung，会加入更多物理上必需的约束。因此得到的是嵌套外逼近：

\[
\mathcal F_{1}\supseteq\mathcal F_{2}\supseteq\cdots
\supseteq\mathcal F_{\mathrm{physical}}.
\]

有限层级的可行域比真实基态集合更大；这正是“可行不能证明有隙，而不可行可以排除谱隙”的逻辑来源。

### 2.2 平稳性与谱隙矩阵

基态对局域动力学必须平稳：

\[
\omega([H,B_a])=0.
\]

若完整体谱隙至少为 \(\gamma\)，局域激发还必须满足相应的能量—方差不等式。在本层级中，它被写成 Hermitian 矩阵

\[
G^{(d)}_{ab}(\gamma)=K_{ab}
-\gamma\,V_{ab}\succeq0,
\]

其中

\[
K_{ab}
=\frac12\left[
\omega\!\left(B_a^\dagger[H,B_b]\right)
-\omega\!\left([H,B_a^\dagger]B_b\right)
\right],
\]

\[
V_{ab}
=\omega(B_a^\dagger B_b)
-\omega(B_a^\dagger)\omega(B_b).
\]

\(V\) 是去除基态分量后的协方差矩阵，\(K\) 则测量局域激发在 Hamiltonian
下的能量代价。对任意系数向量 \(c\)，条件

\[
c^\dagger G^{(d)}(\gamma)c\ge0
\]

表达了由 \(O=\sum_a c_aB_a\) 产生的每一个局域变分激发都不能以小于
\(\gamma\) 的能量脱离基态。

乘积 \(\omega(B_a^\dagger)\omega(B_b)\) 由状态矩的多项式层级表示。所有
Pauli 乘法、\(g=1/10\) 以及 Heisenberg 项中的 \(1/4\) 系数均在构造阶段保持精确有理数；复 Hermitian 矩阵通过

\[
M\longmapsto
\begin{pmatrix}
\operatorname{Re}M&-\operatorname{Im}M\\
\operatorname{Im}M& \operatorname{Re}M
\end{pmatrix}
\]

转化为实对称 PSD 块。

### 2.3 为什么这里没有有限尺寸外推

计算使用有限开放局域窗口，但窗口不是被当作一个有限物理样品求谱。它只承载无限体系必须服从的局域代数恒等式。为了避免把截断边缘误写进对易子，构造在更大的 halo 上计算
\([H,B_a]\)，仅保留支撑严格闭合的 inner words，并核对其与开放窗口表达完全一致。

因此，边界不参与能级量子化，也没有圆柱周长需要外推。有限的是证书的复杂度，而不是被宣称为物理体系的尺寸。

## 3. 什么才算一个证明？

每个层级最终化为规范锥可行性问题

\[
Ax=b,\qquad
F_k(x)=F_{k,0}+\sum_i x_iF_{k,i}\succeq0.
\]

优化器只负责寻找候选；数学结论由与优化器分离的验证器给出。

### 可行见证

若一个 primal 候选经过有理重构和精确仿射校正，并且所有 PSD 块通过精确
\(LDL^\mathsf T\) 检验，则当前层级是可行的：

\[
\texttt{feasible at }(d,\gamma)
\quad\Longrightarrow\quad
\text{该层级尚不能排除 }\Delta_{\mathrm{bulk}}\ge\gamma.
\]

这个箭头不能反向。

### 不可行证书

若存在等式乘子 \(y\) 与 \(Z_k\succeq0\)，使

\[
A^\mathsf Ty+
\sum_k\bigl(F_{k,i}\bullet Z_k\bigr)_i=0,
\]

\[
\sum_k F_{k,0}\bullet Z_k-b^\mathsf Ty<0,
\]

则得到严格分离原可行域的 Farkas 射线。只有当共同仿射恒等式、对偶 PSD
条件和严格负 separation 均被独立验证后，才允许写出

\[
\boxed{
\texttt{certified\_infeasible at }\gamma
\quad\Longrightarrow\quad
\Delta_{\mathrm{bulk}}<\gamma.}
\]

若精确有理重构不能闭合证明，验证器还可以在 256-bit 精度下使用外向舍入区间、仿射可行点包含检验和区间 PSD 下界；它必须在同一个包含盒上同时证明全部条件。

### 三值语义

| 验证结果 | 数学含义 | 允许的物理表述 |
|:---|:---|:---|
| `feasible` | 找到并验证了当前松弛的 primal 点 | 本层级没有排除该 \(\gamma\) |
| `certified_infeasible` | 找到并验证了 Farkas 分离证书 | \(\Delta_{\mathrm{bulk}}<\gamma\) |
| `unknown` | 没有足以证明任一命题的候选 | 不产生物理结论 |

这种三值逻辑是整个工作的核心：数值计算可以没有答案，但不能制造答案。

## 4. 结果：层级看见了什么？

### 4.1 \(d=1\)：认证链闭合，但分辨率不足

对 unrestricted \(L=1,d=1\)、Rung-A 松弛，八个测试点均由
`primal_exact` 独立接受：

| \(\gamma/J_1\) | \(0\) | \(0.1\) | \(0.2\) | \(0.3\) | \(0.6\) | \(1.2\) | \(2.4\) | \(4.8\) |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 结论 | feasible | feasible | feasible | feasible | feasible | feasible | feasible | feasible |

这些点具有两个不同层面的意义。

第一，它们验证了端到端数学链：三角晶格几何、精确 Hamiltonian、Pauli
代数、矩量与谱隙 PSD 块、锥模型、primal 重构以及独立验证能够闭合为一致工件。

第二，它们诊断了层级的能力边界。连 \(\gamma=4.8J_1\) 都未被排除，说明
\(d=1\) 外逼近远大于真实基态集合。它对 \(0.2\)–\(0.3J_1\) 尺度没有判别力。这里的“大 \(\gamma\) 可行”不是奇异的物理预测，而是一把测量松弛粗糙度的尺。

由于没有 certified-infeasible 上端点，

\[
\texttt{verified\_bracket}=\varnothing.
\]

### 4.2 \(d=2\)：真正的数学前沿

将基扩展到 \(d=2\)、Rung A 后，规范问题的规模跃迁为

\[
\begin{aligned}
n_{\mathrm{var}}&=60\,467,\\
n_{\mathrm{eq}}&=507,\\
\dim F_1&=1430,\qquad \dim F_2=506,\\
|\mathcal B|&=715,\qquad
|\mathcal B_{\mathrm{inner}}|=253.
\end{aligned}
\]

局域几何包含 7 个站点、12 条最近邻键和 6 条次近邻键。第一 PSD 块含
511,940 个仿射条目。规范问题哈希为

```text
6a676246f483c2042fe60b597c0ee8e4a79bab7522db50703ae9feb64178d2da
```

现有 \(\gamma=0\) 记录没有产生可供独立验证的完整 primal 或 dual
见证，因此其严格结论为 `unknown`。这不是不可行证书，也不能满足正式层级所要求的
\(\gamma=0\) feasible sanity gate。关键点 \(\gamma=0.20,0.30\) 尚无完整正式工件。

因此当前最强、也唯一正确的物理陈述仍然是：

\[
\boxed{\text{尚未得到 }\Delta_{\mathrm{bulk}}\text{ 的认证上界。}}
\]

## 5. 为什么一个开放结果仍然重要？

这项工作的推进不在于重新计算一次有限系统谱隙，而在于改变问题的逻辑形式。

有限尺寸方法通常提出一个估计问题：

\[
\text{“从若干圆柱能级，最合理的无限尺寸外推是多少？”}
\]

这里提出的是一个证明搜索问题：

\[
\text{“假设无限体系具有 }\Delta_{\mathrm{bulk}}\ge\gamma,
\text{局域基态约束是否已经自相矛盾？”}
\]

二者提供的是互补信息。前者可以高精度描绘候选相；后者一旦成功，则给出不依赖波函数 ansatz、圆柱边界或外推曲线的单向否定。

当前结果带来三点可以复用的认识：

1. **把物理争议变成了可证伪命题。**  
   “约 \(0.3J_1\) 的稳健体谱隙”不再只是数值解释，而对应
   \(\gamma=0.20,0.30\) 两个明确的锥可行性问题。

2. **把数值状态与数学结论分离。**  
   求解器的成功、停滞或异常都不是论文结论；只有被独立接受的 primal
   点或 Farkas 射线才改变知识状态。

3. **量化了需要跨越的层级尺度。**  
   \(d=1\) 明确过弱，而 \(d=2\) 已形成一个内容寻址、可继续求解的
   60,467 变量实例。下一步不必重新设计问题，只需在同一数学对象上获得并验证候选。

这不是对 \(0.3J_1\) 争议的裁决；它是对“怎样才算裁决”的精确定义。

## 6. 下一次决定性计算

正式顺序由逻辑而非便利性决定：

1. 在 \(d=2\)、Rung A 上首先证明 \(\gamma=0\) independently feasible；
2. 然后直接测试 \(\gamma=0.20\)；
3. 若 \(\gamma=0.20\) certified-infeasible，则立即得到
   \(\Delta_{\mathrm{bulk}}<0.20J_1\)，排除稳健的 \(0.3J_1\) 完整体谱隙；
4. 若 \(0.20\) feasible，则测试 \(0.30\)；若后者 certified-infeasible，
   得到同一松弛内的 verified bracket；
5. 若 Rung A 仍过弱，再以严格嵌套的 Rung B 收紧外逼近。

增强层级后，上界只能保持或收紧；随 \(\gamma\) 增大，可行性只能从可行走向不可行。任何违反这些单调关系的记录都必须被审计，而不能进入物理解释。

---

## 7. 精简复现与审计说明

本目录同时提供便于浏览的 `triangular-gap-certificate/` 源码树，以及包含源码与全部机器可读运行工件的
`Fox-triangular-gap-certificate.tar.gz`。要完整重放本文结果，先解压归档并进入其根目录：

```bash
mkdir fox-gap-reproduction
tar -xzf Fox-triangular-gap-certificate.tar.gz -C fox-gap-reproduction
cd fox-gap-reproduction
```

### 7.1 环境与测试

需要 Julia 1.10+；正式求解需要 MOSEK 及有效许可证。从项目根目录运行：

```bash
julia --startup-file=no --project=. -e \
  'using Pkg; Pkg.instantiate(); Pkg.test()'
```

显式 \(d=2\) 构造验收：

```bash
julia --startup-file=no --project=. test/performance_acceptance.jl
```

### 7.2 重放 \(d=2,\gamma=0\) 工件

```bash
julia --startup-file=no --project=. -e '
using TriangularGapCertificates
directory = "results/submission/g-0.10__gamma-0.00__L-1__d-2__rung-A__scope-unrestricted__deeaa9f08848"
record = load_run(directory)
println((raw=record.raw.termination_status,
         verifier=record.verification.method,
         verdict=Symbol(record.verdict),
         runtime=record.raw.runtime_seconds))
'
```

预期得到 `OTHER_ERROR`、`not_checked`、`unknown` 和运行时间
`725.9467329978943` 秒。这里重放的目标是确认记录没有被误解释，而不是把它变成排除证书。

### 7.3 工件结构

每个完成目录由五个文件构成：

| 文件 | 作用 |
|:---|:---|
| `spec.json` | 精确的 \(g,\gamma,L,d\)、rung 与 scope |
| `problem.json` | 规范有理数锥问题 |
| `solver_artifact.json` | 原始状态及未经信任的候选 |
| `verification.json` | 独立验证结果及候选绑定 |
| `run_record.json` | 源码、依赖、规模、状态与上述文件的哈希链 |

`load_run` 会从 `spec.json` 重建几何、basis 和 conic problem，比较规范字节及全部文件哈希，再重新验证候选。d=2 工件的文件 SHA-256 为：

| 文件 | SHA-256 |
|:---|:---|
| `spec.json` | `5f21477050bf353efd0058fd04c3ab032102065b614cd665faa024b40ae1fe2e` |
| `problem.json` | `e5fffd7906bc4ebecbadb659075219f1e87b898702f4d30cf967f3a286b559ba` |
| `solver_artifact.json` | `514d1d1ee863544ae486d56d31f59d22411090dc4d19d8d045fac276cfc54fcd` |
| `verification.json` | `a5e32d85ed9b3f622d6a7ba5f645319569e68207f3b0a97a656df0342c4c44cc` |
| `run_record.json` | `c46221f6a83660a3ac217cddece07293fe8f1efe59772fdf152342f06e4da42f` |

证书的规范、Farkas 符号约定、精确 \(LDL^\mathsf T\) 检验和区间后备路径详见
[`triangular-gap-certificate/docs/certificate-format.md`](triangular-gap-certificate/docs/certificate-format.md)。冻结的计算选择与发表门槛见
[`triangular-gap-certificate/docs/phase1-runbook.md`](triangular-gap-certificate/docs/phase1-runbook.md)。

## 8. 结语

三角晶格上的 \(0.3J_1\) 谱隙尚未被这项计算接受，也尚未被它排除。真正完成的工作，是在有限圆柱的数值信号与无限体系的数学命题之间架起了一座只允许可靠结论通过的桥。

在桥的这一端，\(d=1\) 告诉我们：局域约束还太稀疏，无法分辨目标能标。在另一端，\(d=2\) 已经把下一次尝试固定成一个明确的锥问题。未来若出现一条通过独立验证的 Farkas 射线，它将不只是“另一个谱隙数值”，而是一份关于无限三角晶格不能拥有某个谱隙的证明。

开放问题因此没有被掩盖；它被磨得更锋利了。

## 参考资料

1. X. Xu et al., “The bulk spectral gap is semi-decidable: a convergent family of certified upper bounds,” arXiv:2606.03836 (2026). <https://arxiv.org/abs/2606.03836>
2. Z. Zhu and S. R. White, “Spin liquid phase of the \(S=1/2\) \(J_1\)-\(J_2\) Heisenberg model on the triangular lattice,” *Phys. Rev. B* **92**, 041105(R) (2015). <https://arxiv.org/abs/1502.04831>
3. QuantumBFS/quantum.harness Issue #88, “Certified bulk spectral-gap bounds for frustrated spin-1/2 models.” <https://github.com/QuantumBFS/quantum.harness/issues/88>
